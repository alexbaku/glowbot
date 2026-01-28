from typing import Optional

from app.crud.base import CRUDBase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


class CRUDUser(CRUDBase[User, dict, dict]):
    """CRUD operations for User model"""

    async def get_by_phone(self, db: AsyncSession, phone_number: str) -> Optional[User]:
        """Get user by phone number with all relationships loaded"""
        result = await db.execute(
            select(User)
            .filter(User.phone_number == phone_number)
            .options(
                selectinload(User.health_info),
                selectinload(User.skin_concerns),
                selectinload(User.preferences),
                selectinload(User.routines),
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, db: AsyncSession, phone_number: str, profile_name: Optional[str] = None
    ) -> User:
        """Get existing user or create new one"""
        user = await self.get_by_phone(db, phone_number)
        if not user:
            user = User(phone_number=phone_number, profile_name=profile_name)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user


# Create singleton instance
user_crud = CRUDUser(User)
