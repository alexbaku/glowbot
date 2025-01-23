from fastapi import Request, HTTPException
from app.core.chat import ChatManager
from app.services.twilio import WhatsAppService
import logging

logger = logging.getLogger(__name__)

class WebhookHandler:
    def __init__(self):
        self.whatsapp = WhatsAppService()
        self.chat_manager = ChatManager()

    async def handle_webhook(self, request: Request) -> dict:
        """Handle incoming WhatsApp webhook"""
        try:
            # Get form data from Twilio request
            form_data = await request.form()
            request_data = dict(form_data)

            # Format the incoming message
            message_data = self.whatsapp.format_incoming_message(request_data)
            
            # Process through chat flow manager
            response = await self.chat_manager.handle_message(
                user_id=message_data['from_number'],
                message=message_data['body'],
                media_url=message_data.get('media_url')
            )

            # Send response back to user
            await self.whatsapp.send_message(
                to=message_data['from_number'],
                message=response
            )

            return {
                "status": "success",
                "message": "Webhook processed successfully"
            }

        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))