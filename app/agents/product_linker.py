"""
Product Linker Agent — maps routine steps to iHerb affiliate search links.

Takes a completed SkincareRoutine + UserProfile, returns a ShoppingList.
Each recommendation contains:
  - An optimised iHerb search query for that step
  - A full affiliate URL built from the configurable search template
  - A personalised one-liner note referencing the user's skin profile

The affiliate URL template is read from config so it can be swapped
from referral code to a formal affiliate link without code changes.
"""

import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from pydantic_ai import Agent, RunContext

from app.config import Settings
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
    """Everything the product linker needs for one shopping list."""

    routine: SkincareRoutine
    profile: UserProfile
    search_template: str  # e.g. "https://il.iherb.com/search?query={query}&rcode=VZH480"


product_linker_agent = Agent(
    "anthropic:claude-sonnet-4-5-20250929",
    deps_type=ProductLinkerDeps,
    output_type=ShoppingList,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_iherb_url(search_template: str, search_query: str) -> str:
    """Construct a full iHerb affiliate URL from the template and raw query."""
    return search_template.format(query=quote_plus(search_query))


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

    return f"""You are GlowBot's product curator. Your job is to generate a personalised
iHerb shopping list that maps each step in the user's skincare routine to a
specific search query on iHerb.

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

ROUTINE STEPS TO MATCH:
{steps_str}

YOUR TASK:
For EACH routine step above, produce one ProductRecommendation with:

1. step_name      — copy exactly from the step (e.g. "Cleanser")
2. search_query   — 3-6 clean English keywords optimised for iHerb search
                    (iHerb is English-language; always write queries in English)
                    - Strip percentages and filler words
                    - Keep the key active ingredient(s) and product type
                    - Add "fragrance free" if the user has sensitivities
                    - Add "pregnancy safe" if pregnant/nursing
                    - Good: "salicylic acid gel cleanser fragrance free"
                    - Bad:  "gentle gel cleanser with salicylic acid 0.5-2%"
3. iherb_url      — leave this as an empty string "" — it will be filled in
                    automatically after you respond
4. note           — one personalised sentence explaining what to look for,
                    referencing the user's specific skin type or concern
                    e.g. "Look for fragrance-free formulas — your sensitivity
                    means even 'natural' fragrances can cause flare-ups"

INTRO: A warm single sentence introducing the shopping list.
OUTRO: A brief practical tip (e.g. sort by rating on iHerb, patch test first).

IMPORTANT:
- One recommendation per routine step — do not skip any step
- search_query must always be in English regardless of user language
- Do not invent product brand names — keep queries ingredient/category focused
- The iherb_url field MUST be left as "" (empty string)"""
