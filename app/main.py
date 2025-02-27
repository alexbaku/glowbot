from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.claude import ClaudeService
from app.services.twilio import WhatsAppService
from app.services.conversation import ConversationService
from app.config import Settings

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
conversation_service = ConversationService(claude_service)

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "GlowBot.AI"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))
        
        # Process the message through the conversation service
        response = await conversation_service.process_message(
            message_data['from_number'],
            message_data['body']
        )
        
        # Send response back through WhatsApp
        await whatsapp_service.send_message(
            to=message_data['from_number'],
            message=response
        )
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Development endpoint for testing conversation flow without WhatsApp
@app.post("/dev/chat")
async def dev_chat(request: Request):
    try:
        data = await request.json()
        user_id = data.get("user_id", "test_user")
        message = data.get("message", "")
        
        if not message:
            return {"error": "Message is required"}
        
        response = await conversation_service.process_message(user_id, message)
        
        # Also return the current context for debugging
        context = conversation_service.get_context(user_id)
        
        return {
            "response": response,
            "state": context.state,
            "context": context.to_dict()
        }
    except Exception as e:
        return {"error": str(e)}