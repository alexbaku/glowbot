import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.conversation import Message
from app.models.health_info import UserHealthInfo
from app.models.routine import RoutineTime
from app.models.user import SkinType, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard showing all users and their conversations."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.skin_concerns),
            selectinload(User.conversations),
        )
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    conversations = []
    for user in users:
        # Find the most recent active conversation, or most recent overall
        active_conv = None
        for conv in user.conversations:
            if conv.is_active:
                active_conv = conv
                break
        if not active_conv and user.conversations:
            active_conv = max(user.conversations, key=lambda c: c.created_at)

        concerns = [sc.concern for sc in user.skin_concerns]

        conversations.append({
            "user_id": user.phone_number,
            "profile_name": user.profile_name,
            "state": active_conv.state.value if active_conv else "no conversation",
            "language": user.language or "en",
            "skin_type": user.skin_type.value if user.skin_type and user.skin_type != SkinType.UNKNOWN else "Unknown",
            "concerns": concerns,
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
    result = await db.execute(
        select(User)
        .where(User.phone_number == user_id)
        .options(
            selectinload(User.health_info).selectinload(UserHealthInfo.medications),
            selectinload(User.health_info).selectinload(UserHealthInfo.allergies),
            selectinload(User.health_info).selectinload(UserHealthInfo.sensitivities),
            selectinload(User.skin_concerns),
            selectinload(User.preferences),
            selectinload(User.routines),
            selectinload(User.conversations),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        return HTMLResponse("<h1>User not found</h1>", status_code=404)

    # Find active conversation (or most recent)
    active_conv = None
    for conv in user.conversations:
        if conv.is_active:
            active_conv = conv
            break
    if not active_conv and user.conversations:
        active_conv = max(user.conversations, key=lambda c: c.created_at)

    # Load messages for the active conversation
    history = []
    if active_conv:
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == active_conv.id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()
        history = [{"role": msg.role.value, "content": msg.content} for msg in messages]

    # Build context dict with all collected data
    context = {
        "state": active_conv.state.value if active_conv else "no conversation",
        "language": (user.language or "en").upper(),
        "skin_profile": {
            "skin_type": user.skin_type.value if user.skin_type else None,
            "concerns": [sc.concern for sc in user.skin_concerns],
            "sun_exposure": user.sun_exposure.value if user.sun_exposure else None,
        },
        "health_info": None,
        "preferences": {
            "budget_range": user.budget_range,
            "requirements": [p.preference for p in user.preferences],
        },
        "routines": {
            "morning": [
                {"step": r.step.value, "product": r.product}
                for r in user.routines if r.time_of_day == RoutineTime.MORNING
            ],
            "evening": [
                {"step": r.step.value, "product": r.product}
                for r in user.routines if r.time_of_day == RoutineTime.EVENING
            ],
        },
        "account": {
            "profile_name": user.profile_name,
            "age_verified": user.age_verified,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else None,
            "updated_at": user.updated_at.strftime("%Y-%m-%d %H:%M") if user.updated_at else None,
        },
    }

    if user.health_info:
        context["health_info"] = {
            "is_pregnant": user.health_info.is_pregnant,
            "is_nursing": user.health_info.is_nursing,
            "planning_pregnancy": user.health_info.planning_pregnancy,
            "medications": [m.name for m in user.health_info.medications],
            "allergies": [a.allergen for a in user.health_info.allergies],
            "sensitivities": [s.sensitivity for s in user.health_info.sensitivities],
        }

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user_id": user_id,
        "context": context,
        "history": history,
    })
