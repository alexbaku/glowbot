import io
import logging
from typing import Optional

import httpx
from fastapi import HTTPException
from PIL import Image
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import Settings

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

    async def download_media(self, media_url: str) -> tuple[bytes, str]:
        """Download a Twilio media file using Basic Auth credentials, then compress it.

        Twilio media URLs require HTTP Basic Auth — Claude cannot fetch them
        directly. This method downloads the bytes server-side, resizes to a
        max of 1024px on the longest side, and re-encodes as JPEG before
        passing to Claude. This keeps the request size manageable.

        Returns (image_bytes, content_type), e.g. (b'...', 'image/jpeg').
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                media_url,
                auth=(self.settings.twilio_account_sid, self.settings.twilio_auth_token),
                follow_redirects=True,
                timeout=15.0,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            raw_bytes = response.content

        if content_type.startswith("image/"):
            try:
                raw_bytes, content_type = _compress_image(raw_bytes)
                logger.info(f"Compressed image to {len(raw_bytes)} bytes")
            except Exception as e:
                logger.warning(f"Image compression failed, using original: {e}")

        return raw_bytes, content_type


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


def _compress_image(data: bytes, max_px: int = 1024, quality: int = 85) -> tuple[bytes, str]:
    """Resize image so longest side <= max_px and re-encode as JPEG."""
    img = Image.open(io.BytesIO(data))
    # Convert to RGB so we can always save as JPEG (handles PNG/WebP with alpha)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), "image/jpeg"