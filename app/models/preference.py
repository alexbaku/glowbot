from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserPreference(BaseModel):
    """User product preferences (vegan, cruelty-free, etc.)"""

    __tablename__ = "user_preferences"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    preference = Column(String(100), nullable=False)

    user = relationship("User", back_populates="preferences")

    def __repr__(self):
        return f"<UserPreference(preference={self.preference})>"
