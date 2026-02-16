"""
Interview Agent — collects skincare profile through natural conversation.

Stateless per-call: all state lives in UserProfile (dep) + message_history.
The LLM decides what to ask next, detects knowledge level, and sets
interview_complete=True when minimum data is collected.
"""

import os

from pydantic_ai import Agent, RunContext

from app.config import Settings
from app.schemas import InterviewResult, UserProfile

# Ensure ANTHROPIC_API_KEY is set for pydantic-ai
if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = Settings().claude_api_key

interview_agent = Agent(
    "anthropic:claude-sonnet-4-5-20250929",
    deps_type=UserProfile,
    output_type=InterviewResult,
)


@interview_agent.system_prompt
async def build_system_prompt(ctx: RunContext[UserProfile]) -> str:
    p = ctx.deps

    # Build a snapshot of what's known vs missing
    known: list[str] = []
    missing: list[str] = []

    if p.age_verified:
        known.append("Age verified (18+)")
    else:
        missing.append("Age verification (must be 18+)")

    if p.skin_type:
        known.append(f"Skin type: {p.skin_type.value}")
    else:
        missing.append("Skin type")

    if p.concerns:
        known.append(f"Concerns: {', '.join(p.concerns)}")
    else:
        missing.append("Skin concerns")

    if p.health.is_pregnant is not None:
        known.append(f"Pregnant: {p.health.is_pregnant}")
    else:
        missing.append("Pregnancy / nursing status")

    if p.health.allergies:
        known.append(f"Allergies: {', '.join(p.health.allergies)}")
    if p.health.medications:
        known.append(f"Medications: {', '.join(p.health.medications)}")
    if p.health.sensitivities:
        known.append(f"Sensitivities: {', '.join(p.health.sensitivities)}")

    if p.sun_exposure:
        known.append(f"Sun exposure: {p.sun_exposure.value}")
    else:
        missing.append("Sun exposure level")

    if p.current_routine_morning or p.current_routine_evening:
        if p.current_routine_morning:
            known.append(f"Morning routine: {p.current_routine_morning}")
        if p.current_routine_evening:
            known.append(f"Evening routine: {p.current_routine_evening}")
    else:
        missing.append("Current skincare routine")

    if p.budget:
        known.append(f"Budget: {p.budget.value}")
    if p.preferences:
        known.append(f"Preferences: {', '.join(p.preferences)}")

    if p.knowledge_level:
        known.append(f"Knowledge level: {p.knowledge_level.value}")

    if p.notes:
        known.append(f"Notes: {p.notes}")
    if p.image_analysis:
        known.append(f"Image analysis: {p.image_analysis}")

    known_str = "\n".join(f"  - {k}" for k in known) if known else "  (nothing yet)"
    missing_str = "\n".join(f"  - {m}" for m in missing) if missing else "  (all minimum data collected!)"

    # Language instruction
    if p.language == "hebrew":
        lang_instruction = "The user speaks Hebrew. Respond in Hebrew."
    else:
        lang_instruction = "Respond in the same language the user writes in. Default to English."

    return f"""You are GlowBot, a warm and knowledgeable skincare consultant on WhatsApp.

{lang_instruction}

YOUR APPROACH:
- Have a natural conversation — you're a consultant, not a form
- Ask ONE question at a time
- Reference what the user already told you
- Be curious about unclear or contradictory info
- Be warm, professional, and genuinely interested in helping

KNOWLEDGE DETECTION:
- Pay attention to how the user describes their routine and concerns
- Someone who says "I double cleanse with oil then foam" is intermediate+
- Someone who says "I just wash my face with soap" is beginner
- Update the knowledge_level field accordingly (beginner/intermediate/advanced)

WHAT YOU KNOW SO FAR:
{known_str}

STILL NEEDED (minimum for a recommendation):
{missing_str}

MINIMUM DATA REQUIRED before setting interview_complete=True:
1. Age verified (18+)
2. Skin type identified
3. At least one skin concern
4. Pregnancy/nursing status checked (safety-critical)

WHEN COMPLETING THE INTERVIEW:
- Set interview_complete to true
- In the response field, write a warm personalized NARRATIVE paragraph summarizing everything you learned
- This should be the "wow, you really understand me" moment
- NOT a checklist — a flowing, empathetic paragraph that shows you listened
- End by asking the user to confirm this summary is accurate, or if they'd like to correct anything

CRITICAL RULES:
- Always return the FULL updated profile with ALL previously known data preserved
- Only ADD or UPDATE fields — never clear data that was already collected
- The profile you return completely replaces the stored profile, so include everything"""
