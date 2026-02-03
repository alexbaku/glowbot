from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class UserHealthInfo(BaseModel):
    """User health information for safety recommendations"""

    __tablename__ = "user_health_info"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Pregnancy status
    is_pregnant = Column(Boolean, default=False)
    is_nursing = Column(Boolean, default=False)
    planning_pregnancy = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="health_info")
    medications = relationship(
        "Medication", back_populates="health_info", cascade="all, delete-orphan"
    )
    allergies = relationship(
        "Allergy", back_populates="health_info", cascade="all, delete-orphan"
    )
    sensitivities = relationship(
        "Sensitivity", back_populates="health_info", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<HealthInfo(user_id={self.user_id})>"


class Medication(BaseModel):
    """Prescription medications that may affect skincare"""

    __tablename__ = "medications"

    health_info_id = Column(
        Integer, ForeignKey("user_health_info.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(200), nullable=False)

    health_info = relationship("UserHealthInfo", back_populates="medications")


class Allergy(BaseModel):
    """User allergies"""

    __tablename__ = "allergies"

    health_info_id = Column(
        Integer, ForeignKey("user_health_info.id", ondelete="CASCADE"), nullable=False
    )
    allergen = Column(String(200), nullable=False)

    health_info = relationship("UserHealthInfo", back_populates="allergies")


class Sensitivity(BaseModel):
    """Skin sensitivities"""

    __tablename__ = "sensitivities"

    health_info_id = Column(
        Integer, ForeignKey("user_health_info.id", ondelete="CASCADE"), nullable=False
    )
    sensitivity = Column(String(200), nullable=False)

    health_info = relationship("UserHealthInfo", back_populates="sensitivities")
