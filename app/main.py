import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dashboard import router as dashboard_router
from app.database import AsyncSessionLocal, close_db, get_db, init_db
from app.services.orchestrator import GlowBotService
from app.services.twilio import WhatsAppService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Message debounce buffer ──────────────────────────────────────────────────
# Users often send multiple WhatsApp messages in quick succession. Each one
# triggers a separate Twilio webhook, which would cause the bot to respond to
# every individual message. The debounce buffer collects messages for a short
# window and processes them together as a single turn.

DEBOUNCE_SECONDS = 1.5


@dataclass
class _PendingMessage:
    text: str
    media_url: Optional[str] = None
    image_data: Optional[bytes] = None
    image_content_type: str = "image/jpeg"
    profile_name: Optional[str] = None


_message_buffers: dict[str, list[_PendingMessage]] = {}
_debounce_tasks: dict[str, asyncio.Task] = {}


async def _process_buffer(phone_number: str) -> None:
    """Process all buffered messages for a user as a single conversation turn."""
    messages = _message_buffers.pop(phone_number, [])
    _debounce_tasks.pop(phone_number, None)

    if not messages:
        return

    # Combine text from all buffered messages (skip empty strings from image-only messages)
    combined_text = "\n\n".join(m.text for m in messages if m.text)

    # Use the first image encountered, if any
    image_msg = next((m for m in messages if m.image_data), None)
    image_data = image_msg.image_data if image_msg else None
    image_content_type = image_msg.image_content_type if image_msg else "image/jpeg"
    media_url = image_msg.media_url if image_msg else None

    profile_name = next((m.profile_name for m in messages if m.profile_name), None)

    logger.info(
        f"Processing {len(messages)} buffered message(s) for {phone_number}: "
        f"{combined_text[:60]!r}..."
    )

    try:
        async with AsyncSessionLocal() as db:
            responses = await glowbot.handle_message(
                phone_number=phone_number,
                message=combined_text,
                db=db,
                media_url=media_url,
                image_data=image_data,
                image_content_type=image_content_type,
                profile_name=profile_name,
            )

        for part in responses:
            await whatsapp_service.send_message(to=phone_number, message=part)

        logger.info(f"Sent {len(responses)} message(s) to {phone_number}")

    except Exception as e:
        logger.error(f"Error processing buffered messages for {phone_number}: {e}", exc_info=True)


def _schedule_debounce(phone_number: str) -> None:
    """Cancel any existing debounce task and schedule a fresh one."""
    existing = _debounce_tasks.get(phone_number)
    if existing and not existing.done():
        existing.cancel()

    loop = asyncio.get_event_loop()
    task = loop.create_task(_debounced_process(phone_number))
    _debounce_tasks[phone_number] = task


async def _debounced_process(phone_number: str) -> None:
    """Wait for the debounce window, then process the buffer."""
    await asyncio.sleep(DEBOUNCE_SECONDS)
    await _process_buffer(phone_number)


# ── App setup ────────────────────────────────────────────────────────────────


def _run_migrations():
    """Run alembic migrations before app starts."""
    logger.info("Running database migrations...")
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations complete")
    except Exception as e:
        logger.error(f"Migration failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up GlowBot...")
    _run_migrations()
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down...")
    await close_db()


app = FastAPI(title="GlowBot.AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()
glowbot = GlowBotService()
whatsapp_service = WhatsAppService(settings)

app.include_router(dashboard_router, prefix="/dashboard")


@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "GlowBot.AI"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))

        phone_number = message_data["from_number"]
        user_message = message_data["body"]
        media_url = message_data.get("media_url")
        profile_name = message_data.get("profile_name")

        logger.info(f"Received message from {phone_number}: {user_message[:50]}...")

        # Download image bytes immediately — Twilio URLs require Basic Auth
        # and cannot be fetched later from a background task without credentials.
        image_data: bytes | None = None
        image_content_type = "image/jpeg"
        if media_url:
            try:
                image_data, image_content_type = await whatsapp_service.download_media(media_url)
                logger.info(f"Downloaded media ({image_content_type}, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to download media from {media_url}: {e}")

        # Buffer the message and reset the debounce timer.
        # This ensures rapid successive messages are processed together
        # as a single turn instead of each triggering a separate response.
        _message_buffers.setdefault(phone_number, []).append(
            _PendingMessage(
                text=user_message,
                media_url=media_url,
                image_data=image_data,
                image_content_type=image_content_type,
                profile_name=profile_name,
            )
        )
        _schedule_debounce(phone_number)

        # Return 200 immediately so Twilio doesn't retry the webhook.
        return {"status": "queued"}

    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
