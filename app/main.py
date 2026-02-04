from app.dashboard import router as dashboard_router
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.crud  import conversation_crud, user_crud
from app.database import close_db, get_db, init_db
from app.models.conversation import MessageRole
from app.services.claude import ClaudeService
from app.services.twilio import WhatsAppService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, init_db, close_db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting up GlowBot.AI...")
    await init_db()
    logger.info("✓ Database initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("Shutting down GlowBot.AI...")
    await close_db()
    logger.info("Database connections closed")

app.include_router(dashboard_router, prefix="/dashboard")

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "GlowBot.AI"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)  # ADD THIS LINE
):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))
        
        phone_number = message_data['from_number']  # Rename for clarity
        user_message = message_data['body']
        
        logger.info(f"Received message from {phone_number}: {user_message[:50]}...")
        
        # Pass database session
        response = await claude_service.get_response(
            db=db,              # ADD THIS
            phone_number=phone_number,  # Use phone_number
            user_input=user_message
        )
        
        await whatsapp_service.send_message(
            to=phone_number,
            message=response
        )
        
        logger.info(f"Sent response to {phone_number}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))