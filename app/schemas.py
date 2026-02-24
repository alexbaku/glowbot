"""
Pydantic schemas — the single source of truth for all data contracts.

UserProfile is the handoff contract between Interview and Routine Planner agents.
It is serialized as JSON in the DB for context recovery.
"""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class SkinType(str, enum.Enum):
    DRY = "dry"
    OILY = "oily"
    COMBINATION = "combination"
    NORMAL = "normal"
    SENSITIVE = "sensitive"


class SunExposure(str, enum.Enum):
    MINIMAL = "minimal"
    MODERATE = "moderate"
    HIGH = "high"


class BudgetRange(str, enum.Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    HIGH_END = "high_end"


class KnowledgeLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ConversationPhase(str, enum.Enum):
    INTERVIEWING = "interviewing"
    REVIEWING = "reviewing"
    RECOMMENDING = "recommending"
    COMPLETE = "complete"


# ── Profile sub-models ───────────────────────────────────────────────────────


class HealthInfo(BaseModel):
    is_pregnant: Optional[bool] = None
    is_nursing: Optional[bool] = None
    planning_pregnancy: Optional[bool] = None
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    sensitivities: list[str] = Field(default_factory=list)


# ── UserProfile — the core handoff contract ──────────────────────────────────


class UserProfile(BaseModel):
    """Hybrid profile: typed fields for structured data + free-form notes."""

    # Typed fields
    skin_type: Optional[SkinType] = None
    concerns: list[str] = Field(default_factory=list)
    health: HealthInfo = Field(default_factory=HealthInfo)
    sun_exposure: Optional[SunExposure] = None
    budget: Optional[BudgetRange] = None
    preferences: list[str] = Field(default_factory=list)
    current_routine_morning: Optional[str] = None
    current_routine_evening: Optional[str] = None

    # Adaptive
    knowledge_level: Optional[KnowledgeLevel] = None

    # Free-form
    notes: str = ""
    image_analysis: Optional[str] = None

    # Meta
    age_verified: bool = False
    language: str = "english"
    health_screened: bool = False  # True once allergies/sensitivities/meds addressed
    turns_since_sufficient: int = 0  # tracks turns after all required fields filled


# ── Agent result types ───────────────────────────────────────────────────────


class ProfileUpdates(BaseModel):
    """Incremental profile updates — None means no change for that field."""

    skin_type: Optional[SkinType] = None
    concerns: Optional[list[str]] = None
    age_verified: Optional[bool] = None
    is_pregnant: Optional[bool] = None
    is_nursing: Optional[bool] = None
    planning_pregnancy: Optional[bool] = None
    medications: Optional[list[str]] = None
    allergies: Optional[list[str]] = None
    sensitivities: Optional[list[str]] = None
    sun_exposure: Optional[SunExposure] = None
    budget: Optional[BudgetRange] = None
    preferences: Optional[list[str]] = None
    current_routine_morning: Optional[str] = None
    current_routine_evening: Optional[str] = None
    knowledge_level: Optional[KnowledgeLevel] = None
    notes: Optional[str] = None
    image_analysis: Optional[str] = None
    health_screened: Optional[bool] = None


class OrchestratorResult(BaseModel):
    """Returned by the orchestrator agent on every call."""

    response: str = Field(description="Message to send to the user")
    profile_updates: Optional[ProfileUpdates] = Field(
        default=None,
        description="Incremental profile updates extracted from this turn, or null if nothing new",
    )


class RoutineStep(BaseModel):
    """A single step in a skincare routine — structured for future affiliate matching."""

    order: int
    step_name: str = Field(description="e.g. 'Cleanser', 'Serum', 'Moisturizer'")
    ingredient_category: str = Field(
        description="e.g. 'gentle gel cleanser with salicylic acid'"
    )
    why: str = Field(description="Personalized reason for this step")
    usage_tip: str = Field(default="", description="How/when to apply")
    time_expectation: str = Field(
        default="", description="e.g. 'results in 4-6 weeks'"
    )


class SkincareRoutine(BaseModel):
    """Full routine plan returned by the routine planner agent."""

    narrative_summary: str = Field(
        description="Warm personalized paragraph — the 'wow, you get me' moment"
    )
    morning: list[RoutineStep] = Field(default_factory=list)
    evening: list[RoutineStep] = Field(default_factory=list)
    key_notes: list[str] = Field(default_factory=list)
    ingredients_to_avoid: list[str] = Field(default_factory=list)
