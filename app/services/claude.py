from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
import logging
from app.config import Settings

logger = logging.getLogger(__name__)

class ClaudeService:
    """Service for interacting with Claude AI"""
    def __init__(self, settings:Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.history = []
        self.MODEL = "claude-3-opus-20240229"
        self.system_prompt = """You are Glowbot, a smart skincare assistant who helps users create personalized skincare routines. 
            Interview users naturally, asking one question at a time while maintaining a friendly, conversational tone. 
            Focus on gathering essential information: age, skin type, current concerns, health considerations (pregnancy, medications, allergies), and current skincare routine.

            Be concise in your responses, remembering this is a chat conversation. 
            Progress through information gathering logically - start with basic skin information, then health safety checks, current routine assessment, and finally provide personalized recommendations. 
            Don't move to recommendations until you have all necessary information. If users mention severe skin conditions, always recommend consulting a dermatologist.

            When making recommendations, structure them into morning and evening routines with clear usage instructions. 
            Include basic safety information like patch testing and potential product interactions. 
            Keep responses brief but informative, and don't hesitate to ask clarifying questions when needed to ensure proper recommendations.
            """
    
    async def get_response(self, user_input: str) -> str:
        self.history.append({
            "role": "user",
            "content": user_input
        })
        try:
            response = await self.client.messages.create(
                model=self.MODEL,
                messages=self.history,
                system=self.system_prompt,
                max_tokens=1000
            )
            assert len(response.content) > 0
            assert response.content[0].type == "text"

            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return "I apologize, but I'm having trouble responding. Could you try again?"
        