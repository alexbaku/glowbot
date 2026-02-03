"""User repository for user-related database operations"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, user_model, health_info_model):
        """Initialize with model classes"""
        self.user_model = user_model
        self.health_info_model = health_info_model
    
    async def get_by_phone(
        self, 
        db: AsyncSession, 
        phone_number: str
    ):
        """Get user by phone number with all relationships loaded"""
        stmt = (
            select(self.user_model)
            .where(self.user_model.phone_number == phone_number)
            .options(
                selectinload(self.user_model.health_info),
                selectinload(self.user_model.skin_concerns),
                selectinload(self.user_model.preferences),
                selectinload(self.user_model.routines),
                selectinload(self.user_model.conversations),
            )
        )
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_or_create(
        self, 
        db: AsyncSession, 
        phone_number: str,
        profile_name: Optional[str] = None
    ):
        """Get existing user or create new one"""
        user = await self.get_by_phone(db, phone_number)
        
        if not user:
            user = self.user_model(
                phone_number=phone_number,
                profile_name=profile_name
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Created new user: {phone_number}")
        
        return user