from anthropic import AsyncAnthropic
from anthropic.types import MessageParam
import json
import logging
from typing import Dict, Any, List
from app.config import Settings

logger = logging.getLogger(__name__)

class ClaudeService:
    """Enhanced service for interacting with Claude AI"""
    def __init__(self, settings:Settings):
        self.client = AsyncAnthropic(api_key=settings.claude_api_key)
        self.history = []
        self.MODEL = "claude-3-opus-20240229"
        self.base_system_prompt = """You are Glowbot, a smart skincare assistant who helps users create personalized skincare routines. 
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
        """Original method for simple response"""
        self.history.append({
            "role": "user",
            "content": user_input
        })
        try:
            response = await self.client.messages.create(
                model=self.MODEL,
                messages=self.history,
                system=self.base_system_prompt,
                max_tokens=1000
            )
            assert len(response.content) > 0
            assert response.content[0].type == "text"

            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return "I apologize, but I'm having trouble responding. Could you try again?"
    
    async def get_structured_response(self, user_input: str, system_prompt: str) -> Dict[str, Any]:
        """Enhanced method for state-based structured responses"""
        try:
            # Create a system prompt that instructs Claude to return JSON
            json_instruction = """
            IMPORTANT: You must respond with a valid JSON object containing these fields:
            {
                "message": "Your response to the user",
                "next_state": "The next conversation state",
                "context_updates": {
                    // Any context updates to store
                }
            }
            
            Do not include any text outside the JSON object.
            """
            
            full_prompt = f"{system_prompt}\n\n{json_instruction}"
            
            response = await self.client.messages.create(
                model=self.MODEL,
                messages=[{
                    "role": "user",
                    "content": user_input
                }],
                system=full_prompt,
                max_tokens=1000
            )
            
            # Extract JSON response
            if response.content and response.content[0].type == "text":
                response_text = response.content[0].text
                
                # Try to parse JSON from the response
                try:
                    # Clean the response to extract just the JSON part
                    json_str = self._extract_json(response_text)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from Claude response: {response_text}")
                    return {
                        "message": "I apologize, but I'm having trouble processing your request.",
                        "next_state": "same",
                        "context_updates": {}
                    }
            
            return {
                "message": "I apologize, but I'm having trouble generating a response.",
                "next_state": "same",
                "context_updates": {}
            }
        except Exception as e:
            logger.error(f"Error getting structured response: {str(e)}")
            return {
                "message": "I apologize, but I'm having trouble responding. Could you try again?",
                "next_state": "same",
                "context_updates": {}
            }
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from Claude's response text"""
        # Look for JSON between curly braces
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            return text[start_idx:end_idx+1]
        
        # If no JSON found, return empty JSON object
        return '{}'