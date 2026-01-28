import enum

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class RoutineTime(str, enum.Enum):
    """Enum for routine time of day"""

    MORNING = "morning"
    EVENING = "evening"


class RoutineStep(str, enum.Enum):
    """Enum for routine steps"""

    CLEANSER = "cleanser"
    TREATMENT = "treatment"
    MOISTURIZER = "moisturizer"
    SUNSCREEN = "sunscreen"
    MAKEUP_REMOVAL = "makeup_removal"


class UserRoutine(BaseModel):
    """User's current skincare routine"""

    __tablename__ = "user_routines"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_of_day = Column(SQLEnum(RoutineTime), nullable=False)
    step = Column(SQLEnum(RoutineStep), nullable=False)
    product = Column(String(200))

    user = relationship("User", back_populates="routines")

    def __repr__(self):
        return f"<UserRoutine(time={self.time_of_day}, step={self.step})>"
