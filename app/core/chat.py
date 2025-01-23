from app.models.user import WhatsAppMessage, UserProfile
from app.services.claude import ClaudeService
from typing import Optional
import json

class ChatManager:
    def __init__(self, settings):
        self.claude = ClaudeService()
        self.conversation_state = {}

    async def handle_message(self, message: WhatsAppMessage) -> str:
        """
        Handle incoming WhatsApp messages and return appropriate responses
        """
        # Get or create user state
        user_state = self.conversation_state.get(message.from_number, {
            'stage': 'initial',
            'data': {}
        })

        # Handle image if present
        if message.media_url:
            return await self._handle_image(message)

        # Handle text based on conversation stage
        if user_state['stage'] == 'initial':
            return self._get_initial_response()
        elif user_state['stage'] == 'skin_type':
            return await self._handle_skin_type(message, user_state)
        elif user_state['stage'] == 'concerns':
            return await self._handle_concerns(message, user_state)
        else:
            return await self._handle_general_query(message)

    def _get_initial_response(self) -> str:
        return """Welcome to GlowBot.AI! 👋 I'm here to help you achieve your skincare goals.

Let's start by understanding your skin better. Could you:
1. Share a selfie in natural lighting
2. Tell me about your skin type (dry/oily/combination/normal)
3. Describe your main skin concerns"""

    async def _handle_image(self, message: WhatsAppMessage) -> str:
        """Analyze skin photo using Claude vision"""
        analysis = await self.claude.analyze_image(message.media_url)
        
        # Update user state with analysis results
        self.conversation_state[message.from_number]['data']['skin_analysis'] = analysis
        
        return f"""Thank you for sharing your photo! Here's what I observe:

{analysis}

Would you like specific recommendations based on these observations?"""

    async def _handle_skin_type(self, message: WhatsAppMessage, user_state: dict) -> str:
        """Handle skin type response"""
        user_state['data']['skin_type'] = message.body
        user_state['stage'] = 'concerns'
        
        return "Great! Now, what are your main skin concerns? (e.g., pigmentation, aging, dullness)"

    async def _handle_concerns(self, message: WhatsAppMessage, user_state: dict) -> str:
        """Handle skin concerns response"""
        user_state['data']['concerns'] = message.body
        user_state['stage'] = 'recommendations'
        
        # Generate personalized recommendations
        recommendations = await self._generate_recommendations(user_state['data'])
        return recommendations

    async def _handle_general_query(self, message: WhatsAppMessage) -> str:
        """Handle general skincare questions"""
        response = await self.claude.get_response(message.body)
        return response

    async def _generate_recommendations(self, user_data: dict) -> str:
        """Generate personalized skincare recommendations"""
        # Create prompt for Claude
        prompt = f"""Based on:
- Skin type: {user_data.get('skin_type')}
- Concerns: {user_data.get('concerns')}
- Analysis: {user_data.get('skin_analysis')}

Provide a personalized skincare routine with specific recommendations."""

        recommendations = await self.claude.get_response(prompt)
        return recommendations