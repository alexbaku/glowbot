"""
SQLAlchemy models — two tables only.

`users`       — profile + conversation state (JSON blobs for profile & message history)
`message_log` — audit trail of all messages (dashboard / analytics only)
"""

import enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    profile_name = Column(String(100))
    profile_json = Column(JSON, default=dict)
    conversation_phase = Column(String(20), default="interviewing")
    message_history_json = Column(JSON, default=list)
    routine_json = Column(JSON, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    messages = relationship("MessageLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone_number})>"


class MessageLog(Base):
    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    media_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<MessageLog(id={self.id}, role={self.role})>"
