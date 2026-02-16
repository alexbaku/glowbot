"""
Simplified user repository — all DB access in one place.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import MessageLog, MessageRole, User

logger = logging.getLogger(__name__)


class UserRepository:
    """Single repository for all DB operations."""

    async def get_or_create(
        self,
        db: AsyncSession,
        phone_number: str,
        profile_name: Optional[str] = None,
    ) -> User:
        result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                phone_number=phone_number,
                profile_name=profile_name,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user: {phone_number}")
        return user

    async def save(self, db: AsyncSession, user: User) -> None:
        db.add(user)
        await db.commit()

    async def log_message(
        self,
        db: AsyncSession,
        user_id: int,
        role: MessageRole,
        content: str,
        media_url: Optional[str] = None,
    ) -> None:
        msg = MessageLog(
            user_id=user_id,
            role=role,
            content=content,
            media_url=media_url,
        )
        db.add(msg)
        await db.commit()

    async def get_all_users(self, db: AsyncSession) -> list[User]:
        result = await db.execute(select(User).order_by(User.created_at.desc()))
        return list(result.scalars().all())

    async def get_user_by_phone(self, db: AsyncSession, phone_number: str) -> Optional[User]:
        result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_messages_for_user(self, db: AsyncSession, user_id: int) -> list[MessageLog]:
        result = await db.execute(
            select(MessageLog)
            .where(MessageLog.user_id == user_id)
            .order_by(MessageLog.created_at)
        )
        return list(result.scalars().all())
