"""
Routine Planner Agent — generates a personalized skincare routine plan.

Takes a completed UserProfile, returns a structured SkincareRoutine.
Recommends ingredient categories and step types, NOT specific brand products.
"""

import os

from pydantic_ai import Agent, RunContext

from app.config import Settings
from app.schemas import SkincareRoutine, UserProfile

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = Settings().claude_api_key

routine_planner_agent = Agent(
    "anthropic:claude-sonnet-4-5-20250929",
    deps_type=UserProfile,
    output_type=SkincareRoutine,
)


@routine_planner_agent.system_prompt
async def build_system_prompt(ctx: RunContext[UserProfile]) -> str:
    p = ctx.deps

    # Serialize profile into the prompt
    profile_lines = [
        f"Skin type: {p.skin_type.value if p.skin_type else 'unknown'}",
        f"Concerns: {', '.join(p.concerns) if p.concerns else 'none specified'}",
        f"Sun exposure: {p.sun_exposure.value if p.sun_exposure else 'unknown'}",
        f"Budget: {p.budget.value if p.budget else 'not specified'}",
        f"Preferences: {', '.join(p.preferences) if p.preferences else 'none'}",
        f"Knowledge level: {p.knowledge_level.value if p.knowledge_level else 'beginner'}",
    ]

    if p.current_routine_morning:
        profile_lines.append(f"Current morning routine: {p.current_routine_morning}")
    if p.current_routine_evening:
        profile_lines.append(f"Current evening routine: {p.current_routine_evening}")
    if p.notes:
        profile_lines.append(f"Additional notes: {p.notes}")
    if p.image_analysis:
        profile_lines.append(f"Skin image analysis: {p.image_analysis}")

    profile_str = "\n".join(f"  - {line}" for line in profile_lines)

    # Health / safety info
    safety_lines: list[str] = []
    if p.health.is_pregnant or p.health.is_nursing:
        safety_lines.append("PREGNANT OR NURSING — avoid retinoids, salicylic acid (high %), hydroquinone, chemical peels, benzoyl peroxide")
    if p.health.planning_pregnancy:
        safety_lines.append("PLANNING PREGNANCY — start transitioning away from retinoids now")
    if p.health.medications:
        safety_lines.append(f"MEDICATIONS: {', '.join(p.health.medications)} — check for interactions (e.g., isotretinoin contraindicates many actives)")
    if p.health.allergies:
        safety_lines.append(f"ALLERGIES: {', '.join(p.health.allergies)} — strictly avoid these")
    if p.health.sensitivities:
        safety_lines.append(f"SENSITIVITIES: {', '.join(p.health.sensitivities)} — introduce cautiously")

    safety_str = "\n".join(f"  ⚠ {s}" for s in safety_lines) if safety_lines else "  No special safety concerns."

    # Knowledge-level guidance
    knowledge = p.knowledge_level.value if p.knowledge_level else "beginner"
    if knowledge == "beginner":
        depth_instruction = """For this BEGINNER user:
- Keep the routine simple (3-5 steps max per time of day)
- Use plain language, avoid jargon
- Explain WHY each step matters
- Give clear usage tips (how much, how to apply)
- Set realistic expectations for when they'll see results"""
    elif knowledge == "intermediate":
        depth_instruction = """For this INTERMEDIATE user:
- Can handle 4-6 steps per routine
- Use proper ingredient names but still explain reasoning
- Can introduce layering concepts (thinnest to thickest)
- Mention percentage ranges where relevant"""
    else:
        depth_instruction = """For this ADVANCED user:
- Full ingredient layering with percentage guidance
- Can handle actives rotation schedules
- Discuss pH-dependent actives and wait times if relevant
- Optimization tips and ingredient synergies"""

    # Language instruction
    if p.language == "hebrew":
        lang_instruction = "Respond in Hebrew."
    else:
        lang_instruction = "Respond in the same language as the user's profile. Default to English."

    return f"""You are GlowBot, an expert skincare consultant creating a personalized routine plan.

{lang_instruction}

USER PROFILE:
{profile_str}

SAFETY CONSTRAINTS:
{safety_str}

{depth_instruction}

YOUR TASK:
Generate a complete skincare routine plan based on this profile.

IMPORTANT RULES:
1. Recommend INGREDIENT CATEGORIES and step types, NOT specific brand/product names
   - Good: "gentle gel cleanser with salicylic acid 0.5-2%"
   - Bad: "CeraVe SA Cleanser"
2. The narrative_summary should be a warm, personalized paragraph — the "wow" moment
   - Reference their specific concerns, lifestyle, and goals
   - NOT a dry list — a flowing narrative that shows you understand them
3. Each RoutineStep must include:
   - A clear step_name (e.g., "Cleanser", "Vitamin C Serum", "Sunscreen")
   - An ingredient_category describing what to look for
   - A personalized "why" explaining why THIS step matters for THEIR skin
   - A usage_tip for how to apply
   - A time_expectation for when they might see results (if applicable)
4. Morning routine MUST include sunscreen as the final step
5. List ingredients_to_avoid based on their allergies, sensitivities, medications, and health status
6. key_notes should include important warnings, patch-test reminders, and introduction strategy
   (e.g., "introduce one new product at a time, waiting 1-2 weeks between additions")"""
