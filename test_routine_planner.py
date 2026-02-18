"""Quick smoke test — calls the routine planner agent directly."""

import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)

from app.schemas import (
    HealthInfo,
    KnowledgeLevel,
    SkinType,
    SunExposure,
    BudgetRange,
    UserProfile,
)
from app.agents.routine_planner import routine_planner_agent

# Build a realistic test profile
test_profile = UserProfile(
    skin_type=SkinType.COMBINATION,
    concerns=["acne", "dark spots"],
    health=HealthInfo(is_pregnant=False, is_nursing=False),
    sun_exposure=SunExposure.MODERATE,
    budget=BudgetRange.MID_RANGE,
    knowledge_level=KnowledgeLevel.BEGINNER,
    age_verified=True,
    language="english",
    health_screened=True,
)


async def main():
    print("=" * 60)
    print("Calling routine planner agent...")
    print(f"Profile: {test_profile.model_dump_json(indent=2)}")
    print("=" * 60)

    try:
        result = await routine_planner_agent.run(
            "Generate a complete personalized skincare routine based on my profile.",
            deps=test_profile,
        )
        routine = result.output
        print("\nSUCCESS — Routine received:")
        print(f"  narrative_summary: {routine.narrative_summary[:100]}...")
        print(f"  morning steps: {len(routine.morning)}")
        print(f"  evening steps: {len(routine.evening)}")
        print(f"  ingredients_to_avoid: {routine.ingredients_to_avoid}")
        print(f"  key_notes: {routine.key_notes}")
        print("\nFull output:")
        print(routine.model_dump_json(indent=2))
    except Exception as e:
        print(f"\nFAILED — {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


asyncio.run(main())
