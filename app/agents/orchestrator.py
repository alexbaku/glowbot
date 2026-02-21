"""
Orchestrator Agent — owns the full conversation thread across all phases.

Single agent handles: interview, review, post-routine Q&A.
Code gates in the service layer enforce hard rules (sufficiency, safety, phase transitions).
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from pydantic_ai import Agent, RunContext

from app.config import Settings
from app.schemas import (
    ConversationPhase,
    OrchestratorResult,
    SkincareRoutine,
    UserProfile,
)

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = Settings().claude_api_key


@dataclass
class OrchestratorDeps:
    """Everything the orchestrator needs for a single turn."""

    profile: UserProfile
    phase: ConversationPhase
    profile_sufficient: bool
    routine_json: Optional[dict] = None
    force_summarize: bool = False  # True when 2+ turns past sufficiency


orchestrator_agent = Agent(
    "anthropic:claude-sonnet-4-5-20250929",
    deps_type=OrchestratorDeps,
    output_type=OrchestratorResult,
)


# ── Prompt helpers ──────────────────────────────────────────────────────────


def _format_known(p: UserProfile) -> str:
    """Format what's known about the user."""
    known: list[str] = []

    if p.age_verified:
        known.append("Age verified (18+)")
    if p.skin_type:
        known.append(f"Skin type: {p.skin_type.value}")
    if p.concerns:
        known.append(f"Concerns: {', '.join(p.concerns)}")
    if p.health.is_pregnant is not None:
        known.append(f"Pregnant: {p.health.is_pregnant}")
    if p.health.is_nursing is not None:
        known.append(f"Nursing: {p.health.is_nursing}")
    if p.health.planning_pregnancy is not None:
        known.append(f"Planning pregnancy: {p.health.planning_pregnancy}")
    if p.health.allergies:
        known.append(f"Allergies: {', '.join(p.health.allergies)}")
    if p.health.medications:
        known.append(f"Medications: {', '.join(p.health.medications)}")
    if p.health.sensitivities:
        known.append(f"Sensitivities: {', '.join(p.health.sensitivities)}")
    if p.health_screened:
        if not p.health.allergies and not p.health.medications and not p.health.sensitivities:
            known.append("Health screening: no allergies, medications, or sensitivities")
    if p.sun_exposure:
        known.append(f"Sun exposure: {p.sun_exposure.value}")
    if p.budget:
        known.append(f"Budget: {p.budget.value}")
    if p.current_routine_morning:
        known.append(f"Morning routine: {p.current_routine_morning}")
    if p.current_routine_evening:
        known.append(f"Evening routine: {p.current_routine_evening}")
    if p.preferences:
        known.append(f"Preferences: {', '.join(p.preferences)}")
    if p.knowledge_level:
        known.append(f"Knowledge level: {p.knowledge_level.value}")
    if p.notes:
        known.append(f"Notes: {p.notes}")
    if p.image_analysis:
        known.append(f"Image analysis: {p.image_analysis}")

    return "\n".join(f"  - {k}" for k in known) if known else "  (nothing yet)"


def _format_missing(p: UserProfile) -> str:
    """Format what's still needed."""
    missing: list[str] = []

    if not p.age_verified:
        missing.append("Age verification (must be 18+)")
    if not p.skin_type:
        missing.append("Skin type")
    if not p.concerns:
        missing.append("Skin concerns")
    if (
        p.health.is_pregnant is None
        and p.health.is_nursing is None
        and p.health.planning_pregnancy is None
    ):
        missing.append("Pregnancy / nursing status")
    if not p.health_screened:
        missing.append("Health screening (allergies, sensitivities, medications)")
    if not p.sun_exposure:
        missing.append("Sun exposure level")
    if not p.budget:
        missing.append("Budget range")
    if not p.current_routine_morning and not p.current_routine_evening:
        missing.append("Current skincare routine (or confirmation they don't have one)")

    return "\n".join(f"  - {m}" for m in missing) if missing else "  (all required data collected!)"


def _format_routine_for_prompt(routine: SkincareRoutine) -> str:
    """Condensed routine for inclusion in system prompt."""
    lines: list[str] = []
    if routine.morning:
        lines.append("Morning:")
        for step in routine.morning:
            lines.append(f"  {step.order}. {step.step_name} — {step.ingredient_category}")
    if routine.evening:
        lines.append("Evening:")
        for step in routine.evening:
            lines.append(f"  {step.order}. {step.step_name} — {step.ingredient_category}")
    if routine.ingredients_to_avoid:
        lines.append(f"Avoid: {', '.join(routine.ingredients_to_avoid)}")
    if routine.key_notes:
        lines.append("Notes: " + "; ".join(routine.key_notes))
    return "\n".join(lines)


# ── Dynamic system prompt ───────────────────────────────────────────────────


@orchestrator_agent.system_prompt
async def build_system_prompt(ctx: RunContext[OrchestratorDeps]) -> str:
    deps = ctx.deps
    p = deps.profile

    # Language instruction
    if p.language == "hebrew":
        lang_instruction = "The user speaks Hebrew. Respond in Hebrew."
    else:
        lang_instruction = "Respond in the same language the user writes in. Default to English."

    known = _format_known(p)
    missing = _format_missing(p)

    # Phase-specific block
    if deps.phase == ConversationPhase.INTERVIEWING:
        if deps.force_summarize:
            phase_block = f"""PHASE: INTERVIEW WRAP-UP (MANDATORY)
You have collected all required data. You MUST now:
1. Write a warm, personalized narrative paragraph summarizing everything about this user's skin
2. End by asking them to confirm the summary is accurate, or correct anything
3. Do NOT ask any more questions — go straight to the summary

PROFILE SNAPSHOT:
{known}"""
        elif deps.profile_sufficient:
            phase_block = f"""PHASE: INTERVIEW WRAP-UP
All required data has been collected. You should wrap up soon.
Finish acknowledging the user's current message, then write a warm personalized
narrative summary of everything you learned. End by asking them to confirm or correct.

PROFILE SNAPSHOT:
{known}"""
        else:
            phase_block = f"""PHASE: INTERVIEWING
Collect the user's skincare profile through natural conversation.

YOUR APPROACH:
- Ask ONE question at a time — you're a consultant, not a form
- Reference what the user already told you
- Be curious about unclear or contradictory info
- Be warm, professional, and genuinely interested in helping

KNOWLEDGE DETECTION:
- Pay attention to how the user describes their routine and concerns
- Someone who says "I double cleanse with oil then foam" is intermediate+
- Someone who says "I just wash my face with soap" is beginner
- Set knowledge_level in profile_updates accordingly

COLLECTED SO FAR:
{known}

STILL NEEDED:
{missing}

MINIMUM DATA REQUIRED (all must be collected):
1. Age verified (18+)
2. Skin type identified
3. At least one skin concern
4. Pregnancy/nursing status (safety-critical)
5. Health screening: ask about allergies, sensitivities, and medications
   (set health_screened=true in profile_updates once addressed, even if user has none)
6. Sun exposure level
7. Budget range
8. Current skincare routine (or confirmation they don't have one)

IMPORTANT:
- Extract any new profile data into profile_updates
- Only set fields that changed — null means "no change"
- For health fields (is_pregnant, is_nursing, etc.), set the specific field
- Set health_screened=true once you've asked about allergies/sensitivities/medications"""

    elif deps.phase == ConversationPhase.REVIEWING:
        phase_block = f"""PHASE: REVIEWING
The user is reviewing their profile summary.
- If they want to correct something, acknowledge the correction and update profile_updates
- Then present an updated summary and ask them to confirm again
- If they confirm, tell them you're generating their personalized routine now

PROFILE:
{known}"""

    elif deps.phase == ConversationPhase.COMPLETE:
        routine_ctx = ""
        if deps.routine_json:
            routine = SkincareRoutine.model_validate(deps.routine_json)
            routine_ctx = f"""
THE USER'S CURRENT ROUTINE:
{_format_routine_for_prompt(routine)}

ROUTINE NARRATIVE:
{routine.narrative_summary}
"""
        phase_block = f"""PHASE: POST-ROUTINE (Q&A and Product Recommendations)
The user has received their skincare routine. You can:
- Answer follow-up questions about the routine (order, timing, ingredients, etc.)
- Recommend specific product types or ingredient categories
- Explain why certain steps or ingredients were chosen
- Suggest modifications based on new information

You have full access to their routine and profile below.

PROFILE:
{known}
{routine_ctx}"""

    else:
        phase_block = f"PHASE: {deps.phase.value}\nPROFILE:\n{known}"

    return f"""You are GlowBot, a warm and knowledgeable skincare consultant on WhatsApp.

{lang_instruction}

PERSONALITY:
- Warm, professional, genuinely interested in helping
- Keep messages concise — this is WhatsApp, not email
- Reference what the user already told you

{phase_block}

VISION — WHEN THE USER SENDS AN IMAGE:
You may receive images alongside messages. Analyze them carefully and respond based on what you see.

Image types and how to handle each:

SKIN PHOTOS (bare skin, face, body area):
- Describe what you observe: texture, tone, visible concerns (acne, redness, dryness, oiliness, etc.)
- During INTERVIEWING: if you can infer skin type or concerns from the photo, include them in
  profile_updates (skin_type, concerns) — this pre-fills the interview naturally
- Always tell the user what you observed so they can confirm or correct
- Be careful: photos can be misleading (lighting, filters) — treat visual findings as helpful
  hints, not diagnoses

PRODUCT LABELS (ingredient lists, back of bottle):
- Extract and name the key active ingredients you can read
- Cross-check against the user's known allergies, sensitivities, and skin type
- Flag any concerning ingredients (e.g. fragrance for sensitive skin, comedogenic oils for oily skin)
- Tell the user whether this product looks suitable for their profile

PRODUCT PACKAGING / FRONT OF BOTTLE:
- Identify the product and brand if visible
- Assess whether the product category fits their current routine or skin goals
- Note anything that stands out (e.g. "SPF 15 is on the low side for high sun exposure")

OTHER IMAGES:
- Do your best to interpret how it relates to skincare
- If it seems unrelated, acknowledge it briefly and redirect to the consultation

ALWAYS:
- Store a concise summary of what you saw in profile_updates.image_analysis
  (e.g. "User sent photo of face — appears oily T-zone, visible blackheads on nose")
  (e.g. "User sent label of CeraVe moisturizer — key ingredients: ceramides, hyaluronic acid, niacinamide — suitable for their dry sensitive skin")
- If you cannot make out the image clearly, say so and ask the user to describe it

OUTPUT FORMAT:
- response: Your message to the user (WhatsApp-friendly, use *bold* for emphasis)
- profile_updates: Any new profile data extracted from this message (null if nothing new)
  Only include fields that changed — null means "no change" for that field"""


# ── Tools (for COMPLETE phase edge cases) ───────────────────────────────────


@orchestrator_agent.tool
async def generate_routine(ctx: RunContext[OrchestratorDeps]) -> str:
    """Generate a new personalized skincare routine. Use when the user wants
    a fresh routine (e.g., after updating their profile or concerns)."""
    from app.agents.routine_planner import routine_planner_agent
    from app.services.message_splitter import split_for_whatsapp

    profile = ctx.deps.profile
    result = await routine_planner_agent.run(
        "Generate a complete personalized skincare routine based on my profile.",
        deps=profile,
    )
    routine = result.output
    ctx.deps.routine_json = routine.model_dump(mode="json")

    # Return the formatted routine for the agent to relay
    return _format_routine_short(routine)


@orchestrator_agent.tool
async def get_detailed_routine(ctx: RunContext[OrchestratorDeps]) -> str:
    """Return the detailed version of the user's current routine with
    application tips, timing, and ingredient details."""
    if not ctx.deps.routine_json:
        return "No routine has been generated yet."
    routine = SkincareRoutine.model_validate(ctx.deps.routine_json)
    return _format_routine_detailed(routine)


# ── Routine formatting (ported from old orchestrator) ───────────────────────


def _format_routine_short(routine: SkincareRoutine) -> str:
    """Short bullet-point summary — concise and scannable."""
    lines: list[str] = []

    lines.append(routine.narrative_summary)
    lines.append("")

    if routine.morning:
        lines.append("*☀️ Morning*")
        for step in routine.morning:
            lines.append(f"  {step.order}. {step.step_name}")
        lines.append("")

    if routine.evening:
        lines.append("*🌙 Evening*")
        for step in routine.evening:
            lines.append(f"  {step.order}. {step.step_name}")
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
