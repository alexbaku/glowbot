import asyncio
from app.services.twilio import WhatsAppService
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_whatsapp():
    whatsapp = WhatsAppService()
    
    # Test message
    test_message = """Welcome to GlowBot.AI! 🌟
    
This is a test message to verify our WhatsApp integration.

Reply with:
1️⃣ To start skin analysis
2️⃣ To see a demo routine
3️⃣ To ask a skincare question"""

    try:
        # Replace with your test number
        test_number = "+14155238886"  
        
        result = await whatsapp.send_message(
            to=test_number,
            message=test_message
        )
        
        print(f"Message sent successfully! SID: {result['message_sid']}")
        
    except Exception as e:
        print(f"Error sending message: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_whatsapp())