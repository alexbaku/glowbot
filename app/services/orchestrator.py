"""
GlowBotService — the main orchestrator.

Single entry point: handle_message(phone, message, db, media_url?)
Thin dispatcher: fast paths for deterministic actions, agent path for everything else.
Code gates enforce phase transitions and safety rules.
"""

import logging
import re
from typing import Optional

from pydantic_ai import BinaryContent
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import (
    OrchestratorDeps,
    _format_routine_detailed,
    _format_routine_short,
    orchestrator_agent,
)
from app.agents.routine_planner import routine_planner_agent
from app.models.db import MessageRole
from app.repository import UserRepository
from app.schemas import ConversationPhase, SkincareRoutine, UserProfile
from app.services.message_splitter import split_for_whatsapp

logger = logging.getLogger(__name__)

# Maximum exchanges to feed back as message_history (user+assistant pairs)
MAX_HISTORY_PAIRS = 20

repo = UserRepository()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _detect_language(text: str) -> str:
    """Detect Hebrew by Unicode range; default to English."""
    for ch in text:
        if "\u0590" <= ch <= "\u05ff":
            return "hebrew"
    return "english"


def _is_profile_sufficient(profile: UserProfile) -> bool:
    """Check that all required data has been collected."""
    health_checked = (
        profile.health.is_pregnant is not None
        or profile.health.is_nursing is not None
        or profile.health.planning_pregnancy is not None
    )
    has_routine = bool(profile.current_routine_morning or profile.current_routine_evening)
    return bool(
        profile.age_verified
        and profile.skin_type
        and profile.concerns
        and health_checked
        and profile.health_screened
        and profile.sun_exposure
        and profile.budget
        and has_routine
    )


def _is_confirmation(message: str) -> bool:
    """Check if the message is a positive confirmation."""
    lower = message.lower().strip()
    signals = [
        "yes", "yeah", "yep", "correct", "looks good", "that's right",
        "confirmed", "confirm", "ok", "okay", "perfect", "great",
        "כן", "נכון", "מאשר", "מאשרת", "בסדר", "מצוין",
    ]
    return any(sig in lower for sig in signals)


def _wants_details(message: str) -> bool:
    """Check if the user wants the detailed routine."""
    lower = message.lower().strip()
    signals = ["detailed", "details", "more", "tips", "פירוט", "עוד"]
    return any(sig in lower for sig in signals)


def _wants_restart(message: str) -> bool:
    """Check if the user wants to start over.

    Uses word-boundary matching to avoid false positives from words like
    'מחדשת' (renewing/reapplying) accidentally matching 'מחדש' (start over).
    """
    lower = message.lower().strip()
    # English: use \b word boundaries
    # Hebrew: require the word to be surrounded by whitespace/punctuation or string edges
    patterns = [
        r"\bstart over\b",
        r"\brestart\b",
        r"\bnew consultation\b",
        r"\breset\b",
        r"(?:^|[\s,\.!?])מחדש(?:$|[\s,\.!?])",
        r"(?:^|[\s,\.!?])התחל מחדש(?:$|[\s,\.!?])",
    ]
    return any(re.search(p, lower) for p in patterns)


def _apply_profile_updates(profile: UserProfile, updates) -> UserProfile:
    """Merge incremental ProfileUpdates into the profile."""
    if updates is None:
        return profile

    for field_name, value in updates.model_dump(exclude_none=True).items():
        # Health sub-fields go into profile.health
        if field_name in (
            "is_pregnant", "is_nursing", "planning_pregnancy",
            "medications", "allergies", "sensitivities",
        ):
            setattr(profile.health, field_name, value)
        else:
            setattr(profile, field_name, value)
    return profile


def _serialize_history(history: list) -> list:
    """Convert pydantic-ai message objects to JSON-serializable dicts."""
    if not history:
        return []
    try:
        raw = ModelMessagesTypeAdapter.dump_json(history)
        import json
        return json.loads(raw)
    except Exception:
        logger.warning("Failed to serialize message history, returning empty")
        return []


def _deserialize_history(raw: list) -> list:
    """Reconstruct pydantic-ai message objects from stored JSON."""
    if not raw:
        return []
    try:
        import json
        return list(ModelMessagesTypeAdapter.validate_json(json.dumps(raw)))
    except Exception:
        logger.warning("Failed to deserialize message history, returning empty")
        return []


# ── Main service ────────────────────────────────────────────────────────────


class GlowBotService:
    """Main orchestrator — routes messages through fast paths or the agent."""

    async def handle_message(
        self,
        phone_number: str,
        message: str,
        db: AsyncSession,
        media_url: Optional[str] = None,
        image_data: Optional[bytes] = None,
        image_content_type: str = "image/jpeg",
        profile_name: Optional[str] = None,
    ) -> list[str]:
        """Process an incoming WhatsApp message. Returns a list of response strings."""
        try:
            # 1. Load or create user
            user = await repo.get_or_create(db, phone_number, profile_name)

            # 2. Deserialize state
            profile = UserProfile.model_validate(user.profile_json or {})
            phase = ConversationPhase(user.conversation_phase or "interviewing")
            message_history = _deserialize_history(user.message_history_json or [])
            routine_json = user.routine_json

            # 3. Detect language
            detected = _detect_language(message)
            if detected:
                profile.language = detected

            # 4. Log incoming message
            await repo.log_message(db, user.id, MessageRole.USER, message, media_url)

            # 5. Route: fast paths first, then agent
            responses: list[str]

            # ── Fast path: restart ──
            if _wants_restart(message):
                profile = UserProfile(language=profile.language)
                phase = ConversationPhase.INTERVIEWING
                message_history = []
                routine_json = None
                if profile.language == "hebrew":
                    responses = ["בואי נתחיל מחדש! ספרי לי קצת על העור שלך 😊"]
                else:
                    responses = ["Let's start fresh! Tell me a bit about your skin 😊"]

            # ── Fast path: confirmation in REVIEWING phase ──
            elif phase == ConversationPhase.REVIEWING and _is_confirmation(message):
                if routine_json:
                    # Routine already generated (e.g. duplicate webhook or race condition) — skip
                    logger.info("Routine already exists in REVIEWING confirmation — skipping duplicate generation")
                    routine = SkincareRoutine.model_validate(routine_json)
                    responses = split_for_whatsapp(_format_routine_short(routine))
                    phase = ConversationPhase.COMPLETE
                else:
                    logger.info("User confirmed profile — generating routine plan")
                    if profile.language == "hebrew":
                        ack = "מעולה! אני מכינה לך עכשיו תוכנית טיפוח מותאמת אישית... ⏳"
                    else:
                        ack = "Wonderful! Let me create your personalized skincare routine now... ⏳"

                    result = await routine_planner_agent.run(
                        "Generate a complete personalized skincare routine based on my profile.",
                        deps=profile,
                    )
                    routine = result.output
                    routine_json = routine.model_dump(mode="json")

                    short = _format_routine_short(routine)
                    if profile.language == "hebrew":
                        cta = "רוצה את הגרסה המפורטת עם טיפים ליישום? פשוט תגידי *כן* 😊"
                    else:
                        cta = "Want the detailed version with application tips? Just say *yes* 😊"

                    responses = [ack] + split_for_whatsapp(short) + [cta]
                    phase = ConversationPhase.COMPLETE

            # ── Fast path: detailed routine request in COMPLETE phase ──
            elif (
                phase == ConversationPhase.COMPLETE
                and _wants_details(message)
                and routine_json
            ):
                routine = SkincareRoutine.model_validate(routine_json)
                detailed = _format_routine_detailed(routine)
                responses = split_for_whatsapp(detailed)

            # ── Agent path: everything else ──
            else:
                # Handle legacy RECOMMENDING phase (shouldn't happen in new flow)
                if phase == ConversationPhase.RECOMMENDING:
                    phase = ConversationPhase.INTERVIEWING

                sufficient = _is_profile_sufficient(profile)
                force = sufficient and profile.turns_since_sufficient >= 2

                deps = OrchestratorDeps(
                    profile=profile,
                    phase=phase,
                    profile_sufficient=sufficient,
                    routine_json=routine_json,
                    force_summarize=force,
                )

                # Build user prompt — multimodal if image present
                if image_data:
                    user_prompt: str | list = [
                        BinaryContent(data=image_data, media_type=image_content_type),
                        message or "Here's a photo",
                    ]
                else:
                    user_prompt = message

                result = await orchestrator_agent.run(
                    user_prompt,
                    deps=deps,
                    message_history=message_history,
                )

                # Apply incremental profile updates
                if result.output.profile_updates:
                    profile = _apply_profile_updates(profile, result.output.profile_updates)

                # Capture routine if agent called generate_routine tool
                if deps.routine_json != routine_json:
                    routine_json = deps.routine_json
                    phase = ConversationPhase.COMPLETE

                # Code-controlled phase transitions
                new_sufficient = _is_profile_sufficient(profile)

                if phase == ConversationPhase.INTERVIEWING:
                    if new_sufficient:
                        profile.turns_since_sufficient += 1
                        if profile.turns_since_sufficient >= 2 or force:
                            # Force transition to REVIEWING
                            phase = ConversationPhase.REVIEWING
                            profile.turns_since_sufficient = 0
                    else:
                        profile.turns_since_sufficient = 0

                responses = split_for_whatsapp(result.output.response)
                message_history = message_history + list(result.new_messages())

            # 6. Persist state
            user.profile_json = profile.model_dump(mode="json")
            user.conversation_phase = phase.value
            user.routine_json = routine_json
            trimmed = message_history[-(MAX_HISTORY_PAIRS * 2):] if message_history else []
            user.message_history_json = _serialize_history(trimmed)
            await repo.save(db, user)

            # 7. Log outgoing messages
            full_response = "\n\n".join(responses)
            await repo.log_message(db, user.id, MessageRole.ASSISTANT, full_response)

            logger.info(
                f"Handled message | User: {phone_number} | Phase: {phase.value} | "
                f"Parts: {len(responses)}"
            )
            return responses

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            return ["I'm sorry, something went wrong. Could you try again?"]
