import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.dashboard import router as dashboard_router
from app.database import close_db, get_db, init_db
from app.services.orchestrator import GlowBotService
from app.services.twilio import WhatsAppService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

        # Download image bytes server-side — Twilio URLs require Basic Auth
        # and cannot be fetched directly by Claude's API.
        image_data: bytes | None = None
        image_content_type = "image/jpeg"
        if media_url:
            try:
                image_data, image_content_type = await whatsapp_service.download_media(media_url)
                logger.info(f"Downloaded media ({image_content_type}, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to download media from {media_url}: {e}")

        responses = await glowbot.handle_message(
            phone_number=phone_number,
            message=user_message,
            db=db,
            media_url=media_url,
            image_data=image_data,
            image_content_type=image_content_type,
            profile_name=profile_name,
        )

        for part in responses:
            await whatsapp_service.send_message(to=phone_number, message=part)

        logger.info(f"Sent {len(responses)} message(s) to {phone_number}")
        return {"status": "success"}

    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
