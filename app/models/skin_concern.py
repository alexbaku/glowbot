from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class SkinConcern(BaseModel):
    """User's skin concerns"""

    __tablename__ = "skin_concerns"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concern = Column(String(100), nullable=False)

    user = relationship("User", back_populates="skin_concerns")

    def __repr__(self):
        return f"<SkinConcern(concern={self.concern})>"
