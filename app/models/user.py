from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SkinType(str, Enum):
    DRY = "dry"
    OILY = "oily"
    COMBINATION = "combination"
    NORMAL = "normal"
    SENSITIVE = "sensitive"

class SkinConcern(str, Enum):
    PIGMENTATION = "pigmentation"
    AGING = "aging"
    DULLNESS = "dullness"

class UserProfile(BaseModel):
    """User profile with skin information"""
    phone_number: str
    skin_type: Optional[SkinType] = None
    skin_concerns: List[SkinConcern] = []
    current_routine: dict = {}
    created_at: datetime = datetime.now()
    last_interaction: datetime = datetime.now()

class WhatsAppMessage(BaseModel):
    """WhatsApp message structure"""
    message_sid: str
    from_number: str
    body: str
    media_url: Optional[str] = None