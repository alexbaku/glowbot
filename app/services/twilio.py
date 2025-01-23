from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from fastapi import HTTPException
from app.config import Settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = Client(
            self.settings.twilio_account_sid, 
            self.settings.twilio_auth_token
        )
        self.whatsapp_number = self.settings.twilio_phone_number

    async def send_message(
        self, 
        to: str, 
        message: str, 
        media_url: Optional[str] = None
    ) -> dict:
        """Send a WhatsApp message using Twilio"""
        try:
            message_params = {
                'from_': f'whatsapp:{self.whatsapp_number}',
                'to': f'whatsapp:{to}',
                'body': message
            }

            if media_url:
                message_params['media_url'] = media_url

            twilio_message = self.client.messages.create(**message_params)
            
            return {
                "status": "success",
                "message_sid": twilio_message.sid,
                "to": to
            }
        except TwilioRestException as e:
            logger.error(f"Twilio error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to send message")

    def extract_media_url(self, request_data: dict) -> Optional[str]:
        """Extract media URL from Twilio request if present"""
        num_media = int(request_data.get('NumMedia', 0))
        if num_media > 0:
            return request_data.get('MediaUrl0')
        return None

    def format_incoming_message(self, request_data: dict) -> dict:
        """Format incoming WhatsApp message data"""
        return {
            "message_id": request_data.get('MessageSid'),
            "from_number": request_data.get('From', '').replace('whatsapp:', ''),
            "body": request_data.get('Body', ''),
            "media_url": self.extract_media_url(request_data),
            "profile_name": request_data.get('ProfileName'),
            "timestamp": request_data.get('Timestamp')
        }