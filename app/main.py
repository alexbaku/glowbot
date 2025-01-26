from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.services.claude import ClaudeService
from app.services.twilio import WhatsAppService
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

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "GlowBot.AI"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message_data = whatsapp_service.format_incoming_message(dict(form_data))
        
        response = await claude_service.get_response(message_data['body'])
        
        await whatsapp_service.send_message(
            to=message_data['from_number'],
            message=response
        )
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))