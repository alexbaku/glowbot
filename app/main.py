import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crud import conversation_crud, user_crud
from app.database import close_db, get_db, init_db
from app.models.conversation import MessageRole
from app.services.claude import ClaudeService
from app.services.twilio import WhatsAppService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting up GlowBot...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
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

# Initialize services
settings = Settings()
claude_service = ClaudeService(settings)
whatsapp_service = WhatsAppService(settings)


@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "GlowBot.AI"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))

        phone_number = message_data["from_number"]
        user_message = message_data["body"]
        media_url = message_data.get("media_url")
        profile_name = message_data.get("profile_name")

        logger.info(f"Received message from {phone_number}: {user_message[:50]}...")

        # Step 1: Get or create user
        user = await user_crud.get_or_create(
            db, phone_number=phone_number, profile_name=profile_name
        )
        logger.info(f"User: {user.id} - {user.phone_number}")

        # Step 2: Get or create active conversation
        conversation = await conversation_crud.get_active_conversation(db, user.id)
        if not conversation:
            conversation = await conversation_crud.create_conversation(db, user.id)
            logger.info(f"Created new conversation: {conversation.id}")
        else:
            logger.info(f"Using existing conversation: {conversation.id}")

        # Step 3: Save user message to database
        await conversation_crud.add_message(
            db, conversation.id, MessageRole.USER, user_message, media_url
        )

        # Step 4: Get Claude response (will use conversation history)
        response = await claude_service.get_response(
            user_id=str(user.id), user_input=user_message
        )

        # Step 5: Save assistant message to database
        await conversation_crud.add_message(
            db, conversation.id, MessageRole.ASSISTANT, response
        )

        # Step 6: Send response via WhatsApp
        await whatsapp_service.send_message(to=phone_number, message=response)

        logger.info(f"Successfully processed message for user {user.id}")

        return {
            "status": "success",
            "user_id": user.id,
            "conversation_id": conversation.id,
        }

    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
