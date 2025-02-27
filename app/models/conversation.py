from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class ConversationState(str, Enum):
    """Defines all possible states in the GlowBot conversation flow"""
    INITIAL = "initial"
    SKIN_TYPE = "skin_type"
    SKIN_CONCERNS = "skin_concerns"
    HEALTH_CHECK = "health_check"
    CURRENT_ROUTINE = "current_routine"
    PREFERENCES = "preferences"
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
    user_id: str
    state: ConversationState = ConversationState.INITIAL
    language: str = "en"  # Default language is English
    health_info: HealthInfo = Field(default_factory=HealthInfo)
    skin_profile: SkinProfile = Field(default_factory=SkinProfile)
    routine: UserRoutine = Field(default_factory=UserRoutine)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    missing_info: List[str] = []
    last_question: Optional[str] = None
    
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

class Message(BaseModel):
    """Message in a conversation"""
    user_id: str
    content: str
    role: str  # user or assistant
    timestamp: Optional[str] = None