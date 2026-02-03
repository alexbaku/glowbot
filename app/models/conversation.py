import enum

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ConversationState(str, enum.Enum):
    """Enum for conversation states"""

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


class MessageRole(str, enum.Enum):
    """Enum for message roles"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(BaseModel):
    """Conversation tracking between user and bot"""

    __tablename__ = "conversations"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state = Column(
        SQLEnum(ConversationState), default=ConversationState.GREETING, nullable=False
    )
    context = Column(JSON, default=dict)  # Store conversation context
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self):
        return (
            f"<Conversation(id={self.id}, user_id={self.user_id}, state={self.state})>"
        )


class Message(BaseModel):
    """Individual messages in a conversation"""

    __tablename__ = "messages"

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    media_url = Column(String(500))  # For image messages

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"
