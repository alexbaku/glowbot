"""
Product Linker Agent — maps routine steps to plain-text product recommendations.

Takes a completed SkincareRoutine + UserProfile, returns a ShoppingList.
Each recommendation contains:
  - 2-3 specific product name suggestions appropriate for the Israeli market
  - A personalised note referencing the user's skin profile
"""

import os
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from app.config import Settings
from app.data.cruelty_free_brands import ALL_CRUELTY_FREE_BRANDS, WELL_KNOWN_CF_BRANDS
from app.schemas import (
    BudgetRange,
    ShoppingList,
    SkincareRoutine,
    UserProfile,
)

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = Settings().claude_api_key


@dataclass
class ProductLinkerDeps:
    """Everything the product linker needs for one recommendation list."""

    routine: SkincareRoutine
    profile: UserProfile


product_linker_agent = Agent(
    "anthropic:claude-sonnet-4-5-20250929",
    deps_type=ProductLinkerDeps,
    output_type=ShoppingList,
)


# ── Dynamic system prompt ────────────────────────────────────────────────────


@product_linker_agent.system_prompt
async def build_system_prompt(ctx: RunContext[ProductLinkerDeps]) -> str:
    deps = ctx.deps
    p = deps.profile
    routine = deps.routine

    # Summarise the routine steps for context
    step_lines: list[str] = []
    for step in routine.morning:
        step_lines.append(f"  [Morning] {step.step_name}: {step.ingredient_category}")
    for step in routine.evening:
        step_lines.append(f"  [Evening] {step.step_name}: {step.ingredient_category}")
    steps_str = "\n".join(step_lines) if step_lines else "  (no steps)"

    # User constraints relevant to product matching
    constraint_lines: list[str] = []
    if p.health.allergies:
        constraint_lines.append(f"Allergies (MUST avoid): {', '.join(p.health.allergies)}")
    if p.health.sensitivities:
        constraint_lines.append(f"Sensitivities (flag if present): {', '.join(p.health.sensitivities)}")
    if p.health.is_pregnant or p.health.is_nursing:
        constraint_lines.append("Pregnant/nursing — avoid retinoids, high-% salicylic acid, benzoyl peroxide")
    if p.preferences:
        constraint_lines.append(f"Preferences: {', '.join(p.preferences)}")
    constraints_str = "\n".join(f"  - {c}" for c in constraint_lines) if constraint_lines else "  None"

    budget = p.budget.value if p.budget else "mid_range"
    budget_guidance = {
        BudgetRange.BUDGET.value: "Prioritise affordable, widely available brands. Keep search terms generic (avoid luxury brands).",
        BudgetRange.MID_RANGE.value: "Mid-range brands are fine. No need to filter by price explicitly.",
        BudgetRange.HIGH_END.value: "Premium options are welcome. Search terms can include quality-focused keywords.",
    }.get(budget, "Mid-range brands are fine.")

    lang = p.language
    if lang == "hebrew":
        lang_instruction = "Write the intro and outro in Hebrew."
    else:
        lang_instruction = "Write the intro and outro in English."

    # Cruelty-free constraint block
    if p.cruelty_free_preference is True:
        cf_brands_str = ", ".join(WELL_KNOWN_CF_BRANDS)
        cruelty_free_block = f"""
CRUELTY-FREE REQUIREMENT (MANDATORY):
  This user ONLY wants products from cruelty-free brands certified by Leaping Bunny or PETA.
  - ONLY recommend brands from this certified list (or others you know are Leaping Bunny/PETA certified):
    {cf_brands_str}
  - Do NOT recommend: CeraVe, La Roche-Posay, Neutrogena, Garnier, L'Oreal, Maybelline,
    Olay, Estée Lauder, MAC, Clinique, Lancôme, Kiehl's, or any brand owned by L'Oreal Group
    or Estée Lauder Companies unless they are independently certified cruelty-free.
  - If you are unsure whether a brand is cruelty-free, choose a brand from the list above instead.
  - Add "🐰 Leaping Bunny certified" in the note for each recommendation to reassure the user.
"""
    else:
        cruelty_free_block = ""

    return f"""You are GlowBot's product curator. Your job is to suggest specific, real products
for each step in the user's personalised skincare routine.

{lang_instruction}

USER PROFILE SUMMARY:
  - Skin type: {p.skin_type.value if p.skin_type else 'unknown'}
  - Concerns: {', '.join(p.concerns) if p.concerns else 'none'}
  - Budget: {budget}
  - Sun exposure: {p.sun_exposure.value if p.sun_exposure else 'unknown'}

SAFETY CONSTRAINTS:
{constraints_str}

BUDGET GUIDANCE:
  {budget_guidance}
{cruelty_free_block}
ROUTINE STEPS TO MATCH:
{steps_str}

YOUR TASK:
For EACH routine step above, produce one ProductRecommendation with:

1. step_name          — copy exactly from the step (e.g. "Cleanser")
2. product_suggestions — a list of 2-3 specific product names that fit this step.
                         Prioritise brands widely available in Israel (iHerb IL,
                         Amazon IL, or local pharmacies like Super-Pharm, Newpharm).
                         Use real, well-known products — no invented names.
                         Examples: "CeraVe Foaming Facial Cleanser",
                                   "La Roche-Posay Effaclar Purifying Gel",
                                   "The Ordinary Niacinamide 10% + Zinc 1%"
3. note               — one personalised sentence explaining what to look for
                         and why it suits this user's specific skin type or concern.
                         e.g. "Your combination skin needs something that removes
                         oil without stripping — avoid creamy or oil-based cleansers."

INTRO: A warm single sentence introducing the recommendations.
OUTRO: One practical tip (e.g. introduce one new product at a time, patch test first).

IMPORTANT:
- One recommendation per routine step — do not skip any step
- Only suggest products that genuinely exist and match the step's ingredient category
- Respect all safety constraints above — no retinoids if pregnant, avoid known allergens"""
