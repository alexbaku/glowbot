from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

# Enums
class ConsultationStage(str, Enum):
    INITIAL = "initial"
    HEALTH_CHECK = "health_check"
    SKIN_TYPE = "skin_type"
    CONCERNS = "concerns"
    PREFERENCES = "preferences"
    ROUTINE = "routine"
    RECOMMENDATIONS = "recommendations"

class SkinType(str, Enum):
    DRY = "dry"
    OILY = "oily"
    COMBINATION = "combination"
    NORMAL = "normal"
    SENSITIVE = "sensitive"

class InterviewAction(str, Enum):
    ASK = "ask"
    FOLLOWUP = "followup"
    DONE = "done"

# Data Models
class HealthInfo(BaseModel):
    is_adult: bool
    is_pregnant: bool
    has_allergies: bool
    medications: List[str]

class SkinConcerns(BaseModel):
    primary_concerns: List[str]
    skin_type: SkinType
    sun_exposure: str

class CurrentRoutine(BaseModel):
    morning_cleanser: Optional[str]
    morning_treatments: Optional[List[str]]
    morning_moisturizer: Optional[str]
    sunscreen: Optional[str]
    evening_cleanser: Optional[str]
    evening_treatments: Optional[List[str]]
    evening_moisturizer: Optional[str]

class UserPreferences(BaseModel):
    budget_range: str
    preferred_ingredients: List[str]
    avoided_ingredients: List[str]

class InterviewMessage(BaseModel):
    reflection: str
    action: InterviewAction
    message: str

class ConsultationState(BaseModel):
    stage: ConsultationStage
    health_info: Optional[HealthInfo]
    skin_concerns: Optional[SkinConcerns]
    current_routine: Optional[CurrentRoutine]
    preferences: Optional[UserPreferences]
    conversation_history: List[dict]

# Prompt templates for different stages
PROMPT_TEMPLATES = {
    ConsultationStage.INITIAL: """
Based on the user's message, gather initial information and respond in this structure:
{
    "reflection": "Brief summary of what you understood",
    "action": "ask|followup",
    "message": "Your next message to gather essential information"
}
Current stage: Initial Assessment
User message: {user_message}
""",

    ConsultationStage.HEALTH_CHECK: """
Gather critical health information. Respond in this structure:
{
    "reflection": "Health-related information gathered",
    "action": "ask|followup",
    "message": "Your next health-related question"
}
Current stage: Health Check
Previous information: {previous_info}
User message: {user_message}
""",

    ConsultationStage.CONCERNS: """
Understand skin concerns and goals. Respond in this structure:
{
    "reflection": "Skin concerns and goals identified",
    "action": "ask|followup",
    "message": "Your next question about skin concerns"
}
Current stage: Skin Concerns
Previous information: {previous_info}
User message: {user_message}
"""
}

# Example usage
class SkinCareConsultation:
    def __init__(self):
        self.state = ConsultationState(
            stage=ConsultationStage.INITIAL,
            conversation_history=[],
            health_info=None,
            skin_concerns=None,
            current_routine=None,
            preferences=None
        )

    def process_message(self, user_message: str) -> InterviewMessage:
        # Add message to history
        self.state.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Get appropriate prompt template
        prompt = PROMPT_TEMPLATES[self.state.stage].format(
            user_message=user_message,
            previous_info=self._get_previous_info()
        )

        # Get response from Claude (implementation depends on your setup)
        response = self._get_claude_response(prompt)
        
        # Parse response into InterviewMessage
        structured_response = InterviewMessage.parse_raw(response)
        
        # Update state based on response
        self._update_state(structured_response)
        
        return structured_response

    def _get_previous_info(self) -> str:
        # Implement logic to get relevant previous information
        pass

    def _get_claude_response(self, prompt: str) -> str:
        # Implement Claude API call
        pass

    def _update_state(self, response: InterviewMessage):
        # Implement state update logic based on response
        pass