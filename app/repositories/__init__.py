from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository

# Import your models
from app.models import (
    User,
    UserHealthInfo,
    Conversation,
    Message,
    ConversationState as DBConversationState,
    MessageRole,
    SkinConcern,
    UserPreference,
    UserRoutine,
)

# Import your Pydantic schemas
from app.models.conversation_schemas import (
    ConversationContext,
    ConversationState,
)


class RepositoryFactory:
    """Factory to create repository instances with proper dependencies"""
    
    @staticmethod
    def create_user_repository() -> UserRepository:
        """Create UserRepository with model dependencies"""
        return UserRepository(
            user_model=User,
            health_info_model=UserHealthInfo
        )
    
    @staticmethod
    def create_conversation_repository() -> ConversationRepository:
        """Create ConversationRepository with model and schema dependencies"""
        return ConversationRepository(
            conversation_model=Conversation,
            message_model=Message,
            db_conversation_state_enum=DBConversationState,
            message_role_enum=MessageRole,
            conversation_context_schema=ConversationContext,
            conversation_state_enum=ConversationState
        )


# Singleton instances (optional - you can also create fresh instances each time)
_user_repo = None
_conversation_repo = None


def get_user_repository() -> UserRepository:
    """Get singleton UserRepository instance"""
    global _user_repo
    if _user_repo is None:
        _user_repo = RepositoryFactory.create_user_repository()
    return _user_repo


def get_conversation_repository() -> ConversationRepository:
    """Get singleton ConversationRepository instance"""
    global _conversation_repo
    if _conversation_repo is None:
        _conversation_repo = RepositoryFactory.create_conversation_repository()
    return _conversation_repo