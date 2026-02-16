"""
GlowBotService — the main orchestrator.

Single entry point: handle_message(phone, message, db, media_url?)
Agents are pure — they receive profile + history, return result.
All I/O lives here.
"""

import logging
from typing import Optional

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    UserPromptPart,
    TextPart,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interview import interview_agent
from app.agents.routine_planner import routine_planner_agent
from app.models.db import MessageRole
from app.repository import UserRepository
from app.schemas import ConversationPhase, SkincareRoutine, UserProfile
from app.services.message_splitter import split_for_whatsapp

logger = logging.getLogger(__name__)

# Maximum exchanges to feed back as message_history (user+assistant pairs)
MAX_HISTORY_PAIRS = 20

repo = UserRepository()


def _detect_language(text: str) -> str:
    """Detect Hebrew by Unicode range; default to English."""
    for ch in text:
        if "\u0590" <= ch <= "\u05ff":
            return "hebrew"
    return "english"


def _is_profile_sufficient(profile: UserProfile) -> bool:
    """Check that minimum data has been collected."""
    return bool(
        profile.age_verified
        and profile.skin_type
        and profile.concerns
        and profile.health.is_pregnant is not None
    )


def _serialize_history(history: list) -> list:
    """Convert pydantic-ai message objects to JSON-serializable dicts."""
    out = []
    for msg in history:
        if hasattr(msg, "model_dump"):
            out.append(msg.model_dump(mode="json"))
        elif isinstance(msg, dict):
            out.append(msg)
        else:
            out.append(str(msg))
    return out


def _deserialize_history(raw: list) -> list:
    """Reconstruct pydantic-ai message objects from stored JSON."""
    if not raw:
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        try:
            if kind == "request":
                result.append(ModelRequest.model_validate(item))
            elif kind == "response":
                result.append(ModelResponse.model_validate(item))
        except Exception:
            # Skip malformed entries
            continue
    return result


def _format_routine_short(routine: SkincareRoutine) -> str:
    """Short bullet-point summary for WhatsApp — concise and scannable."""
    lines: list[str] = []

    lines.append(routine.narrative_summary)
    lines.append("")

    if routine.morning:
        lines.append("*☀️ Morning*")
        for step in routine.morning:
            lines.append(f"  {step.order}. *{step.step_name}* — {step.why}")
        lines.append("")

    if routine.evening:
        lines.append("*🌙 Evening*")
        for step in routine.evening:
            lines.append(f"  {step.order}. *{step.step_name}* — {step.why}")
        lines.append("")

    if routine.ingredients_to_avoid:
        lines.append(f"*🚫 Avoid:* {', '.join(routine.ingredients_to_avoid)}")
        lines.append("")

    return "\n".join(lines)


def _format_routine_detailed(routine: SkincareRoutine) -> str:
    """Full detailed routine with tips and timelines."""
    lines: list[str] = []

    if routine.morning:
        lines.append("*☀️ Morning Routine — Detailed*")
        lines.append("")
        for step in routine.morning:
            lines.append(f"*{step.order}. {step.step_name}*")
            lines.append(f"  _{step.ingredient_category}_")
            lines.append(f"  {step.why}")
            if step.usage_tip:
                lines.append(f"  💡 {step.usage_tip}")
            if step.time_expectation:
                lines.append(f"  ⏱ {step.time_expectation}")
            lines.append("")

    if routine.evening:
        lines.append("*🌙 Evening Routine — Detailed*")
        lines.append("")
        for step in routine.evening:
            lines.append(f"*{step.order}. {step.step_name}*")
            lines.append(f"  _{step.ingredient_category}_")
            lines.append(f"  {step.why}")
            if step.usage_tip:
                lines.append(f"  💡 {step.usage_tip}")
            if step.time_expectation:
                lines.append(f"  ⏱ {step.time_expectation}")
            lines.append("")

    if routine.key_notes:
        lines.append("*📝 Key Notes*")
        for note in routine.key_notes:
            lines.append(f"  • {note}")

    return "\n".join(lines)


class GlowBotService:
    """Main orchestrator — routes messages through the correct agent."""

    async def handle_message(
        self,
        phone_number: str,
        message: str,
        db: AsyncSession,
        media_url: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> list[str]:
        """Process an incoming WhatsApp message. Returns a list of response strings."""
        try:
            # 1. Load or create user
            user = await repo.get_or_create(db, phone_number, profile_name)

            # 2. Deserialize profile & phase
            profile = UserProfile.model_validate(user.profile_json or {})
            phase = ConversationPhase(user.conversation_phase or "interviewing")
            message_history = _deserialize_history(user.message_history_json or [])

            # 3. Detect language
            detected = _detect_language(message)
            if detected:
                profile.language = detected

            # 4. Log incoming message
            await repo.log_message(db, user.id, MessageRole.USER, message, media_url)

            # 5. Route to handler
            if phase == ConversationPhase.INTERVIEWING:
                responses, profile, phase, message_history = await self._handle_interview(
                    profile, message, message_history, media_url
                )
            elif phase == ConversationPhase.REVIEWING:
                responses, profile, phase, message_history = await self._handle_review(
                    profile, message, message_history
                )
            elif phase == ConversationPhase.RECOMMENDING:
                responses, profile, phase = await self._handle_recommendation(profile)
                # Don't carry interview history into recommendation
            elif phase == ConversationPhase.COMPLETE:
                responses, profile, phase, message_history = await self._handle_complete(
                    profile, message, message_history
                )
            else:
                responses = ["Something went wrong. Let's start fresh!"]
                phase = ConversationPhase.INTERVIEWING
                profile = UserProfile(language=profile.language)
                message_history = []

            # 6. Persist state
            user.profile_json = profile.model_dump(mode="json")
            user.conversation_phase = phase.value
            # Trim history to last N pairs
            trimmed = message_history[-(MAX_HISTORY_PAIRS * 2) :] if message_history else []
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

    # ── Phase handlers ───────────────────────────────────────────────────

    async def _handle_interview(
        self,
        profile: UserProfile,
        message: str,
        history: list,
        media_url: Optional[str] = None,
    ) -> tuple[list[str], UserProfile, ConversationPhase, list]:
        """Run interview agent, collect data, check for completion."""

        # Build user prompt — multimodal if image present
        if media_url:
            user_prompt: str | list = [
                {"type": "image", "source": {"type": "url", "url": media_url}},
                {"type": "text", "text": message or "Here's a photo of my skin"},
            ]
        else:
            user_prompt = message

        result = await interview_agent.run(
            user_prompt,
            deps=profile,
            message_history=history,
        )

        new_profile = result.output.profile
        new_profile.language = profile.language  # preserve detected language
        response_text = result.output.response
        new_history = list(result.new_messages())

        # Check if interview is complete
        if result.output.interview_complete and _is_profile_sufficient(new_profile):
            new_profile.interview_complete = True
            return (
                split_for_whatsapp(response_text),
                new_profile,
                ConversationPhase.REVIEWING,
                history + new_history,
            )

        return (
            split_for_whatsapp(response_text),
            new_profile,
            ConversationPhase.INTERVIEWING,
            history + new_history,
        )

    async def _handle_review(
        self,
        profile: UserProfile,
        message: str,
        history: list,
    ) -> tuple[list[str], UserProfile, ConversationPhase, list]:
        """User confirms or corrects the summary."""
        # Simple heuristic: positive confirmation → proceed to recommendation
        lower = message.lower().strip()
        confirm_signals = [
            "yes", "yeah", "yep", "correct", "looks good", "that's right",
            "confirmed", "confirm", "ok", "okay", "perfect", "great",
            "כן", "נכון", "מאשר", "מאשרת", "בסדר", "מצוין",
        ]

        if any(sig in lower for sig in confirm_signals):
            # Generate recommendation immediately (don't wait for another message)
            logger.info("User confirmed profile — generating routine plan")
            if profile.language == "hebrew":
                ack = "מעולה! אני מכינה לך עכשיו תוכנית טיפוח מותאמת אישית... ⏳"
            else:
                ack = "Wonderful! Let me create your personalized skincare routine now... ⏳"

            routine_responses, profile, phase = await self._handle_recommendation(profile)
            return [ack] + routine_responses, profile, phase, history

        # Otherwise treat as a correction — send back to interview agent
        result = await interview_agent.run(
            message,
            deps=profile,
            message_history=history,
        )

        new_profile = result.output.profile
        new_profile.language = profile.language
        new_history = list(result.new_messages())

        if result.output.interview_complete and _is_profile_sufficient(new_profile):
            new_profile.interview_complete = True
            return (
                split_for_whatsapp(result.output.response),
                new_profile,
                ConversationPhase.REVIEWING,
                history + new_history,
            )

        return (
            split_for_whatsapp(result.output.response),
            new_profile,
            ConversationPhase.REVIEWING,
            history + new_history,
        )

    async def _handle_recommendation(
        self,
        profile: UserProfile,
    ) -> tuple[list[str], UserProfile, ConversationPhase]:
        """Generate the skincare routine plan."""
        logger.info("Calling routine planner agent")
        result = await routine_planner_agent.run(
            "Generate a complete personalized skincare routine based on my profile.",
            deps=profile,
        )
        logger.info("Routine planner agent completed")

        routine = result.output
        # Store routine in profile so we can serve the detailed version later
        profile.last_routine = routine.model_dump(mode="json")

        short = _format_routine_short(routine)
        if profile.language == "hebrew":
            cta = "רוצה את הגרסה המפורטת עם טיפים ליישום? פשוט תגידי *כן* 😊"
        else:
            cta = "Want the detailed version with application tips? Just say *yes* 😊"

        responses = split_for_whatsapp(short) + [cta]
        return (responses, profile, ConversationPhase.COMPLETE)

    async def _handle_complete(
        self,
        profile: UserProfile,
        message: str,
        history: list,
    ) -> tuple[list[str], UserProfile, ConversationPhase, list]:
        """Handle follow-up messages after recommendation is complete."""
        lower = message.lower().strip()
        restart_signals = [
            "start over", "restart", "new consultation", "reset",
            "מחדש", "התחל מחדש",
        ]
        detail_signals = [
            "yes", "yeah", "yep", "detailed", "details", "more", "tips",
            "כן", "פירוט", "עוד",
        ]

        if any(sig in lower for sig in restart_signals):
            new_profile = UserProfile(language=profile.language)
            if profile.language == "hebrew":
                msg = "בואי נתחיל מחדש! ספרי לי קצת על העור שלך 😊"
            else:
                msg = "Let's start fresh! Tell me a bit about your skin 😊"
            return [msg], new_profile, ConversationPhase.INTERVIEWING, []

        # Serve the detailed routine if user asks for it
        if any(sig in lower for sig in detail_signals) and profile.last_routine:
            routine = SkincareRoutine.model_validate(profile.last_routine)
            detailed = _format_routine_detailed(routine)
            profile.last_routine = None  # clear so we don't re-serve
            return split_for_whatsapp(detailed), profile, ConversationPhase.COMPLETE, history

        # For other messages, run interview agent as a Q&A helper
        result = await interview_agent.run(
            message,
            deps=profile,
            message_history=history,
        )
        new_history = list(result.new_messages())
        return (
            split_for_whatsapp(result.output.response),
            profile,
            ConversationPhase.COMPLETE,
            history + new_history,
        )
