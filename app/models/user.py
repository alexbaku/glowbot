import enum

from sqlalchemy import Boolean, Column, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class SkinType(str, enum.Enum):
    """Enum for skin types"""

    DRY = "dry"
    OILY = "oily"
    COMBINATION = "combination"
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    UNKNOWN = "unknown"


class SunExposure(str, enum.Enum):
    """Enum for sun exposure levels"""

    MINIMAL = "minimal"
    MODERATE = "moderate"
    HIGH = "high"


class User(BaseModel):
    """User model storing profile and skin information"""

    __tablename__ = "users"

    # Contact information
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    profile_name = Column(String(100))

    # Age verification
    age_verified = Column(Boolean, default=False)

    # Skin profile
    skin_type = Column(SQLEnum(SkinType), default=SkinType.UNKNOWN)
    sun_exposure = Column(SQLEnum(SunExposure))

    # User preferences
    language = Column(String(10), default="en")
    budget_range = Column(String(50))

    # Relationships
    health_info = relationship(
        "UserHealthInfo",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    skin_concerns = relationship(
        "SkinConcern", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan"
    )
    routines = relationship(
        "UserRoutine", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone_number})>"
