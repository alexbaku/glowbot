from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class InterviewAction(str, Enum):
    """Defines the possible actions the bot can take after processing user input"""
    ASK = "ask"  # Ask a new question
    FOLLOWUP = "followup"  # Ask for clarification or more details
    DONE = "done"  # Consultation complete

class InterviewMessage(BaseModel): 
    """Defines the structure of a chat message"""
    reflection: str = Field(
        description="A concise summary/reflection of the user's input. What facts and hints did you gather from the user's message?",
        min_length=10,
        max_length=500
    )

    action: InterviewAction = Field(
          description="The next action to take in the conversation"
    )

    message: str = Field(
        description="The message to send to the user",
        min_length=1,
        max_length=2000
    )
    
    # New field to track what information was collected
    collected_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Information collected from this exchange"
    )

class ConversationState(str, Enum):
    """Defines all possible states in the GlowBot conversation flow"""
    GREETING = "greeting"
    AGE_VERIFICATION = "age_verification"
    SKIN_TYPE = "skin_type"
    SKIN_CONCERNS = "skin_concerns"
    HEALTH_CHECK = "health_check"
    SUN_EXPOSURE = "sun_exposure"
    CURRENT_ROUTINE = "current_routine"
    PRODUCT_PREFERENCES = "product_preferences"
    SUMMARY = "summary"
    COMPLETE = "complete"

class HealthInfo(BaseModel):
    """Health-related information"""
    is_pregnant: Optional[bool] = None
    is_nursing: Optional[bool] = None
    planning_pregnancy: Optional[bool] = None
    medications: List[str] = []
    allergies: List[str] = []
    sensitivities: List[str] = []

class SkinProfile(BaseModel):
    """User's skin profile"""
    age_verified: Optional[bool] = None
    skin_type: Optional[str] = None  # dry, oily, combination, normal
    concerns: List[str] = []  # hyperpigmentation, aging, acne, etc.
    sun_exposure: Optional[str] = None  # minimal, moderate, high

class UserRoutine(BaseModel):
    """User's current skincare routine"""
    morning_cleanser: Optional[str] = None
    morning_treatments: List[str] = []
    morning_moisturizer: Optional[str] = None
    morning_sunscreen: Optional[str] = None
    evening_makeup_removal: Optional[str] = None
    evening_cleanser: Optional[str] = None
    evening_treatments: List[str] = []
    evening_moisturizer: Optional[str] = None

class UserPreferences(BaseModel):
    """User's product preferences"""
    budget_range: Optional[str] = None  # budget-friendly, mid-range, high-end
    requirements: List[str] = []  # vegan, cruelty-free, fragrance-free, etc.

class ConversationContext(BaseModel):
    """Maintains the context of the conversation"""
    user_id: str = "user"  # Default user ID
    state: ConversationState = ConversationState.GREETING
    language: str = "en"  # Default language is English
    health_info: HealthInfo = Field(default_factory=HealthInfo)
    skin_profile: SkinProfile = Field(default_factory=SkinProfile)
    routine: UserRoutine = Field(default_factory=UserRoutine)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    missing_info: List[str] = []
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update context with new information"""
        for key, value in updates.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel) and isinstance(value, dict):
                    # Update nested models
                    for subkey, subvalue in value.items():
                        if hasattr(getattr(self, key), subkey):
                            setattr(getattr(self, key), subkey, subvalue)
                else:
                    setattr(self, key, value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for storage"""
        return self.model_dump()
    
    def get_next_state(self) -> ConversationState:
        """Determine the next state based on current state and collected information"""
        current = self.state
        
        # Define the conversation flow
        if current == ConversationState.GREETING:
            return ConversationState.AGE_VERIFICATION
            
        elif current == ConversationState.AGE_VERIFICATION:
            if self.skin_profile.age_verified:
                return ConversationState.SKIN_TYPE
            return current  # Stay in this state until age is verified
            
        elif current == ConversationState.SKIN_TYPE:
            if self.skin_profile.skin_type:
                return ConversationState.SKIN_CONCERNS
            return current
            
        elif current == ConversationState.SKIN_CONCERNS:
            if len(self.skin_profile.concerns) > 0:
                return ConversationState.HEALTH_CHECK
            return current
            
        elif current == ConversationState.HEALTH_CHECK:
            # Check if we have the minimum health info
            if (self.health_info.is_pregnant is not None or 
                self.health_info.is_nursing is not None or
                self.health_info.planning_pregnancy is not None):
                return ConversationState.SUN_EXPOSURE
            return current
            
        elif current == ConversationState.SUN_EXPOSURE:
            if self.skin_profile.sun_exposure:
                return ConversationState.CURRENT_ROUTINE
            return current
            
        elif current == ConversationState.CURRENT_ROUTINE:
            # Check if we have at least one routine item
            if (self.routine.morning_cleanser or self.routine.morning_sunscreen or
                self.routine.evening_cleanser or self.routine.evening_moisturizer):
                return ConversationState.PRODUCT_PREFERENCES
            return current
            
        elif current == ConversationState.PRODUCT_PREFERENCES:
            if self.preferences.budget_range or len(self.preferences.requirements) > 0:
                return ConversationState.SUMMARY
            return current
            
        elif current == ConversationState.SUMMARY:
            return ConversationState.COMPLETE
            
        return current  # Default to staying in the same state

class Message(BaseModel):
    """Message in a conversation"""
    user_id: str
    content: str
    role: str  # user or assistant
    timestamp: Optional[str] = None