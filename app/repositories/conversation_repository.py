"""Conversation repository - bridges ClaudeService and database"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
import logging

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation operations and context management"""
    
    def __init__(
        self, 
        conversation_model,
        message_model,
        db_conversation_state_enum,
        message_role_enum,
        conversation_context_schema,
        conversation_state_enum
    ):
        """Initialize with model and schema classes"""
        self.conversation_model = conversation_model
        self.message_model = message_model
        self.db_state_enum = db_conversation_state_enum
        self.message_role = message_role_enum
        self.context_schema = conversation_context_schema
        self.state_enum = conversation_state_enum
    
    async def get_active_conversation(
        self, 
        db: AsyncSession, 
        user_id: int
    ):
        """Get user's active conversation with messages"""
        stmt = (
            select(self.conversation_model)
            .where(
                and_(
                    self.conversation_model.user_id == user_id,
                    self.conversation_model.is_active == True
                )
            )
            .options(selectinload(self.conversation_model.messages))
            .order_by(desc(self.conversation_model.created_at))
        )
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        state = None,
        context: Optional[dict] = None
    ):
        """Create a new conversation"""
        if state is None:
            state = self.db_state_enum.GREETING
        
        if context is None:
            context = {}
        
        conversation = self.conversation_model(
            user_id=user_id,
            state=state,
            context=context,
            is_active=True
        )
        
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(f"Created conversation {conversation.id} for user {user_id}")
        return conversation
    
    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        role,
        content: str,
        media_url: Optional[str] = None
    ):
        """Add a message to conversation"""
        message = self.message_model(
            conversation_id=conversation_id,
            role=role,
            content=content,
            media_url=media_url
        )
        
        db.add(message)
        await db.commit()
        await db.refresh(message)
        
        logger.debug(f"Added {role} message to conversation {conversation_id}")
        return message
    
    async def get_conversation_messages(
        self,
        db: AsyncSession,
        conversation_id: int,
        limit: Optional[int] = None
    ) -> List:
        """Get messages for a conversation"""
        stmt = (
            select(self.message_model)
            .where(self.message_model.conversation_id == conversation_id)
            .order_by(self.message_model.created_at)
        )
        
        if limit:
            stmt = stmt.limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
    
    async def deactivate_conversation(
        self,
        db: AsyncSession,
        conversation_id: int
    ):
        """Mark conversation as inactive"""
        stmt = select(self.conversation_model).where(
            self.conversation_model.id == conversation_id
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if conversation:
            conversation.is_active = False
            await db.commit()
            await db.refresh(conversation)
            logger.info(f"Deactivated conversation {conversation_id}")
        
        return conversation
    
    # === Key methods for ClaudeService ===
    
    async def load_context(
        self, 
        db: AsyncSession, 
        user_id: int,
        phone_number: str
    ):
        """Load conversation context from database"""
        # Get active conversation
        conversation = await self.get_active_conversation(db, user_id)
        
        if conversation and conversation.context:
            # Load context from database
            try:
                context = self.context_schema(**conversation.context)
                context.user_id = phone_number
                logger.info(
                    f"Loaded context for user {user_id}, "
                    f"state: {context.state}"
                )
            except Exception as e:
                logger.error(f"Error loading context from DB: {e}")
                context = self.context_schema(user_id=phone_number)
        else:
            # Create new context
            context = self.context_schema(user_id=phone_number)
            logger.info(f"Created new context for user {user_id}")
        
        return context
    
    async def save_context(
        self, 
        db: AsyncSession, 
        user_id: int,
        context
    ):
        """Save conversation context to database"""
        # Get or create active conversation
        conversation = await self.get_active_conversation(db, user_id)
        
        # Map Pydantic state to DB state
        db_state = self._map_pydantic_state_to_db(context.state)
        
        if not conversation:
            # Create new conversation
            conversation = await self.create_conversation(
                db=db,
                user_id=user_id,
                state=db_state,
                context=context.to_dict()
            )
        else:
            # Update existing conversation
            conversation.state = db_state
            conversation.context = context.to_dict()
            await db.commit()
            await db.refresh(conversation)
        
        logger.info(
            f"Saved context for user {user_id}, "
            f"state: {context.state}"
        )
        
        return conversation
    
    async def get_message_history(
        self,
        db: AsyncSession,
        user_id: int,
        limit: Optional[int] = 50
    ) -> List[dict]:
        """Get formatted message history for Claude API"""
        conversation = await self.get_active_conversation(db, user_id)
        
        if not conversation:
            return []
        
        messages = await self.get_conversation_messages(db, conversation.id, limit)
        
        # Format for Claude API
        formatted = []
        for msg in messages:
            formatted.append({
                "role": "user" if msg.role == self.message_role.USER else "assistant",
                "content": msg.content
            })
        
        return formatted
    
    async def add_user_message(
        self,
        db: AsyncSession,
        user_id: int,
        content: str,
        media_url: Optional[str] = None
    ):
        """Convenience method to add a user message"""
        conversation = await self.get_active_conversation(db, user_id)
        
        if not conversation:
            # Create conversation if it doesn't exist
            conversation = await self.create_conversation(db, user_id)
        
        return await self.add_message(
            db=db,
            conversation_id=conversation.id,
            role=self.message_role.USER,
            content=content,
            media_url=media_url
        )
    
    async def add_assistant_message(
        self,
        db: AsyncSession,
        user_id: int,
        content: str
    ):
        """Convenience method to add an assistant message"""
        conversation = await self.get_active_conversation(db, user_id)
        
        if not conversation:
            raise ValueError(f"No active conversation for user {user_id}")
        
        return await self.add_message(
            db=db,
            conversation_id=conversation.id,
            role=self.message_role.ASSISTANT,
            content=content
        )
    
    def _map_pydantic_state_to_db(self, pydantic_state):
        """Map Pydantic ConversationState to DB ConversationState"""
        return self.db_state_enum(pydantic_state.value)