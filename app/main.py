from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.claude import ClaudeService
from app.services.twilio import WhatsAppService
from app.services.conversation import ConversationService
from app.config import Settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GlowBot.AI")

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
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))

        user_id = message_data['from_number']
        user_message = message_data['body']
        
        # Process message with state-aware Claude service
        response = await claude_service.get_response(
            user_id=user_id,
            user_input=user_message
        )
        
        # Send response back through WhatsApp
        await whatsapp_service.send_message(
            to=message_data['from_number'],
            message=response
        )
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
