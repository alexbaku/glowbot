from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models.user import WhatsAppMessage, UserProfile
from app.services.claude import ClaudeService

app = FastAPI(title="GlowBot.AI")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
claude_service = ClaudeService()

@app.get("/")
async def health_check():
    """API health check endpoint"""
    return {"status": "healthy", "service": "GlowBot.AI"}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(message: WhatsAppMessage):
    """Handle incoming WhatsApp messages"""
    try:
        if message.media_url:
            # Handle image analysis
            analysis = await claude_service.analyze_skin(message.media_url)
            return {"analysis": analysis}
        else:
            # Handle text message
            response = "Thanks for your message! Please send a photo of your skin for analysis."
            return {"message": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))