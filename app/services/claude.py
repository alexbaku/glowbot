from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
import logging
from app.config import Settings

logger = logging.getLogger(__name__)

class ClaudeService:
    """Service for interacting with Claude AI"""
    def __init__(self, settings:Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.MODEL = "claude-3-opus-20240229"
        self.system_prompt = """You are GlowBot, a friendly skincare consultant. Provide concise, helpful skincare advice."""
    
    async def get_response(self, user_input: str) -> str:
        try:
            response = await self.client.messages.create(
                model=self.MODEL,
                messages=[{
                    "role": "user",
                    "content": user_input
                }],
                system=self.system_prompt,
                max_tokens=1000
            )
            assert len(response.content) > 0
            assert response.content[0].type == "text"

            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return "I apologize, but I'm having trouble responding. Could you try again?"