import logging
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repository import UserRepository
from app.schemas import SkincareRoutine, UserProfile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))

repo = UserRepository()


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request, db: AsyncSession = Depends(get_db)):
    users = await repo.get_all_users(db)

    conversations = []
    skin_type_counts: Counter = Counter()
    concern_counts: Counter = Counter()
    budget_counts: Counter = Counter()
    phase_counts: Counter = Counter()

    for user in users:
        profile = UserProfile.model_validate(user.profile_json or {})
        phase = user.conversation_phase or "interviewing"

        conversations.append({
            "user_id": user.phone_number,
            "profile_name": user.profile_name,
            "state": phase,
            "language": profile.language or "english",
            "skin_type": profile.skin_type.value if profile.skin_type else "Unknown",
            "concerns": profile.concerns,
        })

        phase_counts[phase] += 1
        if profile.skin_type:
            skin_type_counts[profile.skin_type.value] += 1
        concern_counts.update(profile.concerns)
        if profile.budget:
            budget_counts[profile.budget.value] += 1

    total_users = len(users)
    completed = phase_counts.get("complete", 0)
    in_interview = phase_counts.get("interviewing", 0)
    in_review = phase_counts.get("reviewing", 0)
    conversion_rate = round(completed / total_users * 100) if total_users else 0

    top_concerns = concern_counts.most_common(10)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_users": total_users,
        "completed": completed,
        "in_interview": in_interview,
        "in_review": in_review,
        "conversion_rate": conversion_rate,
        "conversations": conversations,
        # Chart data (JSON-safe)
        "skin_type_labels": list(skin_type_counts.keys()),
        "skin_type_values": list(skin_type_counts.values()),
        "concern_labels": [c[0] for c in top_concerns],
        "concern_values": [c[1] for c in top_concerns],
        "budget_labels": list(budget_counts.keys()),
        "budget_values": list(budget_counts.values()),
    })


@router.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    user = await repo.get_user_by_phone(db, user_id)

    if not user:
        return HTMLResponse("<h1>User not found</h1>", status_code=404)

    profile = UserProfile.model_validate(user.profile_json or {})

    # Parse generated routine if it exists
    routine = None
    if user.routine_json:
        try:
            routine = SkincareRoutine.model_validate(user.routine_json)
        except Exception:
            logger.warning(f"Failed to parse routine_json for user {user_id}")

    messages = await repo.get_messages_for_user(db, user.id)
    history = [{"role": msg.role.value, "content": msg.content} for msg in messages]

    context = {
        "state": user.conversation_phase or "interviewing",
        "language": (profile.language or "english").upper(),
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
        "routine": routine,
    })


@router.post("/user/{user_id}/reset")
async def reset_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await repo.get_user_by_phone(db, user_id)
    if not user:
        return HTMLResponse("<h1>User not found</h1>", status_code=404)

    user.profile_json = {}
    user.conversation_phase = "interviewing"
    user.message_history_json = []
    user.routine_json = None
    await repo.save(db, user)

    return RedirectResponse(url=f"/dashboard/user/{user_id}", status_code=303)
