from typing import List, Optional

from app.crud.base import CRUDBase
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import (
    Conversation,
    ConversationState,
    Message,
    MessageRole,
)


class CRUDConversation(CRUDBase[Conversation, dict, dict]):
    """CRUD operations for Conversation model"""

    async def get_active_conversation(
        self, db: AsyncSession, user_id: int
    ) -> Optional[Conversation]:
        """Get user's active conversation with messages"""
        result = await db.execute(
            select(Conversation)
            .filter(
                and_(Conversation.user_id == user_id, Conversation.is_active == True)
            )
            .options(selectinload(Conversation.messages))
            .order_by(desc(Conversation.created_at))
        )
        return result.scalar_one_or_none()

    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        state: ConversationState = ConversationState.GREETING,
    ) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(user_id=user_id, state=state)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        role: MessageRole,
        content: str,
        media_url: Optional[str] = None,
    ) -> Message:
        """Add a message to conversation"""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            media_url=media_url,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    async def update_state(
        self, db: AsyncSession, conversation_id: int, new_state: ConversationState
    ) -> Conversation:
        """Update conversation state"""
        conversation = await self.get(db, conversation_id)
        if conversation:
            conversation.state = new_state
            await db.commit()
            await db.refresh(conversation)
        return conversation

    async def update_context(
        self, db: AsyncSession, conversation_id: int, context: dict
    ) -> Conversation:
        """Update conversation context"""
        conversation = await self.get(db, conversation_id)
        if conversation:
            conversation.context = context
            await db.commit()
            await db.refresh(conversation)
        return conversation


# Create singleton instance
conversation_crud = CRUDConversation(Conversation)
