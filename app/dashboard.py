import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repository import UserRepository
from app.schemas import UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

repo = UserRepository()


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard showing all users and their conversations."""
    users = await repo.get_all_users(db)

    conversations = []
    for user in users:
        profile = UserProfile.model_validate(user.profile_json or {})
        conversations.append({
            "user_id": user.phone_number,
            "profile_name": user.profile_name,
            "state": user.conversation_phase or "interviewing",
            "language": profile.language or "en",
            "skin_type": profile.skin_type.value if profile.skin_type else "Unknown",
            "concerns": profile.concerns,
        })

    total_users = len(users)
    active_conversations = sum(
        1 for c in conversations if c["state"] not in ("complete", "no conversation")
    )
    completed_conversations = sum(
        1 for c in conversations if c["state"] == "complete"
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_users": total_users,
        "active_conversations": active_conversations,
        "completed_conversations": completed_conversations,
        "conversations": conversations,
    })


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """User detail page showing all collected data."""
    user = await repo.get_user_by_phone(db, user_id)

    if not user:
        return HTMLResponse("<h1>User not found</h1>", status_code=404)

    profile = UserProfile.model_validate(user.profile_json or {})

    # Load messages
    messages = await repo.get_messages_for_user(db, user.id)
    history = [{"role": msg.role.value, "content": msg.content} for msg in messages]

    context = {
        "state": user.conversation_phase or "interviewing",
        "language": (profile.language or "en").upper(),
        "skin_profile": {
            "skin_type": profile.skin_type.value if profile.skin_type else None,
            "concerns": profile.concerns,
            "sun_exposure": profile.sun_exposure.value if profile.sun_exposure else None,
        },
        "health_info": {
            "is_pregnant": profile.health.is_pregnant,
            "is_nursing": profile.health.is_nursing,
            "planning_pregnancy": profile.health.planning_pregnancy,
            "medications": profile.health.medications,
            "allergies": profile.health.allergies,
            "sensitivities": profile.health.sensitivities,
        },
        "preferences": {
            "budget_range": profile.budget.value if profile.budget else None,
            "requirements": profile.preferences,
        },
        "routines": {
            "morning": profile.current_routine_morning or "Not specified",
            "evening": profile.current_routine_evening or "Not specified",
        },
        "account": {
            "profile_name": user.profile_name,
            "age_verified": profile.age_verified,
            "knowledge_level": profile.knowledge_level.value if profile.knowledge_level else None,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else None,
            "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M") if user.updated_at else None,
        },
    }

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user_id": user_id,
        "context": context,
        "history": history,
    })
