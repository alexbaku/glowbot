"""
Unit tests for the hybrid orchestrator — mocks LLM calls, verifies state transitions.

Tests cover:
  Bug 1: Context preserved after routine delivery (follow-up Q&A works)
  Bug 2: Phase transitions with expanded sufficiency check
  General: Fast paths, profile update merging, restart flow
"""

import json
import pytest

from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.models.test import TestModel
from pydantic_ai.messages import (
    ModelResponse,
    ModelRequest,
    TextPart,
    ToolCallPart,
)

from app.schemas import (
    BudgetRange,
    ConversationPhase,
    HealthInfo,
    KnowledgeLevel,
    OrchestratorResult,
    ProfileUpdates,
    SkincareRoutine,
    SkinType,
    SunExposure,
    UserProfile,
    RoutineStep,
)
from app.agents.orchestrator import (
    OrchestratorDeps,
    orchestrator_agent,
    _format_known,
    _format_missing,
    _format_routine_short,
    _format_routine_detailed,
)
from app.services.orchestrator import (
    _apply_profile_updates,
    _is_profile_sufficient,
    _is_confirmation,
    _wants_details,
    _wants_restart,
    _serialize_history,
    _deserialize_history,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _empty_profile(**overrides) -> UserProfile:
    defaults = dict(language="english")
    defaults.update(overrides)
    return UserProfile(**defaults)


def _complete_profile(**overrides) -> UserProfile:
    """A profile with all 8 required fields filled."""
    defaults = dict(
        age_verified=True,
        skin_type=SkinType.COMBINATION,
        concerns=["acne", "dark spots"],
        health=HealthInfo(is_pregnant=False, is_nursing=False),
        health_screened=True,
        sun_exposure=SunExposure.MODERATE,
        budget=BudgetRange.MID_RANGE,
        current_routine_morning="wash face with soap",
        knowledge_level=KnowledgeLevel.BEGINNER,
        language="english",
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _sample_routine() -> SkincareRoutine:
    return SkincareRoutine(
        narrative_summary="A personalized routine for your combination skin.",
        morning=[
            RoutineStep(
                order=1,
                step_name="Cleanser",
                ingredient_category="gentle gel cleanser",
                why="Removes overnight buildup without stripping",
                usage_tip="Use lukewarm water",
                time_expectation="Immediate",
            ),
            RoutineStep(
                order=2,
                step_name="Sunscreen",
                ingredient_category="SPF 50 broad spectrum",
                why="Essential protection for your skin",
                usage_tip="Apply generously",
                time_expectation="Ongoing",
            ),
        ],
        evening=[
            RoutineStep(
                order=1,
                step_name="Cleanser",
                ingredient_category="oil-based cleanser",
                why="Dissolves sunscreen and makeup",
                usage_tip="Massage for 60 seconds",
                time_expectation="Immediate",
            ),
        ],
        key_notes=["Introduce one product at a time"],
        ingredients_to_avoid=["fragrance"],
    )


# ── Sufficiency check tests ────────────────────────────────────────────────


class TestProfileSufficiency:
    def test_empty_profile_not_sufficient(self):
        assert not _is_profile_sufficient(_empty_profile())

    def test_old_minimum_4_fields_not_sufficient(self):
        """The old 4-field check would pass, but we now require 8."""
        profile = UserProfile(
            age_verified=True,
            skin_type=SkinType.OILY,
            concerns=["acne"],
            health=HealthInfo(is_pregnant=False),
        )
        assert not _is_profile_sufficient(profile)

    def test_complete_profile_is_sufficient(self):
        assert _is_profile_sufficient(_complete_profile())

    def test_missing_sun_exposure_not_sufficient(self):
        assert not _is_profile_sufficient(_complete_profile(sun_exposure=None))

    def test_missing_budget_not_sufficient(self):
        assert not _is_profile_sufficient(_complete_profile(budget=None))

    def test_missing_routine_not_sufficient(self):
        assert not _is_profile_sufficient(
            _complete_profile(current_routine_morning=None, current_routine_evening=None)
        )

    def test_missing_health_screening_not_sufficient(self):
        assert not _is_profile_sufficient(_complete_profile(health_screened=False))

    def test_planning_pregnancy_satisfies_health_check(self):
        """Bug fix: any pregnancy/nursing field should satisfy the check."""
        profile = _complete_profile(
            health=HealthInfo(
                is_pregnant=None,
                is_nursing=None,
                planning_pregnancy=False,
            ),
        )
        assert _is_profile_sufficient(profile)

    def test_nursing_satisfies_health_check(self):
        profile = _complete_profile(
            health=HealthInfo(
                is_pregnant=None,
                is_nursing=True,
                planning_pregnancy=None,
            ),
        )
        assert _is_profile_sufficient(profile)

    def test_no_pregnancy_field_not_sufficient(self):
        profile = _complete_profile(
            health=HealthInfo(
                is_pregnant=None,
                is_nursing=None,
                planning_pregnancy=None,
            ),
        )
        # health_screened=True but no pregnancy field → not sufficient
        assert not _is_profile_sufficient(profile)


# ── Profile update merging tests ────────────────────────────────────────────


class TestProfileUpdates:
    def test_null_updates_returns_unchanged(self):
        profile = _empty_profile()
        result = _apply_profile_updates(profile, None)
        assert result is profile

    def test_basic_field_update(self):
        profile = _empty_profile()
        updates = ProfileUpdates(skin_type=SkinType.OILY, age_verified=True)
        result = _apply_profile_updates(profile, updates)
        assert result.skin_type == SkinType.OILY
        assert result.age_verified is True
        assert result.language == "english"  # preserved

    def test_health_subfields_merged_correctly(self):
        profile = _empty_profile()
        updates = ProfileUpdates(
            is_pregnant=False,
            allergies=["retinol"],
            health_screened=True,
        )
        result = _apply_profile_updates(profile, updates)
        assert result.health.is_pregnant is False
        assert result.health.allergies == ["retinol"]
        assert result.health_screened is True

    def test_incremental_updates_dont_overwrite(self):
        """Only non-None fields are applied."""
        profile = _complete_profile()
        updates = ProfileUpdates(budget=BudgetRange.HIGH_END)
        result = _apply_profile_updates(profile, updates)
        assert result.budget == BudgetRange.HIGH_END
        assert result.skin_type == SkinType.COMBINATION  # preserved
        assert result.concerns == ["acne", "dark spots"]  # preserved


# ── Fast path tests ─────────────────────────────────────────────────────────


class TestFastPaths:
    def test_confirmation_signals(self):
        assert _is_confirmation("yes")
        assert _is_confirmation("Yeah!")
        assert _is_confirmation("Looks good to me")
        assert _is_confirmation("כן")
        assert not _is_confirmation("no, that's wrong")
        assert not _is_confirmation("change my skin type")

    def test_detail_signals(self):
        assert _wants_details("show me the detailed version")
        assert _wants_details("more tips please")
        assert not _wants_details("yes")
        assert not _wants_details("what about retinol?")

    def test_restart_signals(self):
        assert _wants_restart("start over")
        assert _wants_restart("restart")
        assert _wants_restart("התחל מחדש")
        assert not _wants_restart("yes")
        assert not _wants_restart("hello")


# ── History serialization tests ─────────────────────────────────────────────


class TestHistorySerialization:
    def test_roundtrip(self):
        """Serialize then deserialize should reconstruct messages."""
        from pydantic_ai.messages import UserPromptPart
        request = ModelRequest(parts=[UserPromptPart(content="Hi")])
        response = ModelResponse(parts=[TextPart(content="Hello")])
        history = [request, response]

        serialized = _serialize_history(history)
        assert isinstance(serialized, list)
        assert len(serialized) == 2

        deserialized = _deserialize_history(serialized)
        assert len(deserialized) == 2
        assert isinstance(deserialized[0], ModelRequest)
        assert isinstance(deserialized[1], ModelResponse)

    def test_malformed_entries_skipped(self):
        """Deserializing with garbage entries should not crash."""
        # Use _serialize_history to get proper JSON-serializable dicts
        from pydantic_ai.messages import UserPromptPart

        msgs = [
            ModelRequest(parts=[UserPromptPart(content="test")]),
            ModelResponse(parts=[TextPart(content="hi")]),
        ]
        serialized = _serialize_history(msgs)
        assert len(serialized) == 2
        result = _deserialize_history(serialized)
        assert len(result) == 2

        # Garbage input should return empty, not crash
        result = _deserialize_history([{"garbage": True}, "not a dict", 42])
        assert result == []

    def test_empty_input(self):
        assert _deserialize_history([]) == []
        assert _deserialize_history(None) == []


# ── Prompt builder tests ────────────────────────────────────────────────────


class TestPromptBuilders:
    def test_format_known_empty_profile(self):
        result = _format_known(_empty_profile())
        assert "nothing yet" in result

    def test_format_known_complete_profile(self):
        result = _format_known(_complete_profile())
        assert "Age verified" in result
        assert "combination" in result.lower()
        assert "acne" in result

    def test_format_missing_empty_profile(self):
        result = _format_missing(_empty_profile())
        assert "Age verification" in result
        assert "Skin type" in result
        assert "Sun exposure" in result
        assert "Budget" in result
        assert "Health screening" in result

    def test_format_missing_complete_profile(self):
        result = _format_missing(_complete_profile())
        assert "all required data collected" in result

    def test_health_screened_no_issues_shown(self):
        """When health_screened but no allergies/meds, show that explicitly."""
        profile = _complete_profile()
        result = _format_known(profile)
        assert "no allergies" in result.lower()

    def test_planning_pregnancy_shown_in_known(self):
        profile = _complete_profile(
            health=HealthInfo(planning_pregnancy=False),
        )
        result = _format_known(profile)
        assert "Planning pregnancy" in result


# ── Routine formatting tests ────────────────────────────────────────────────


class TestRoutineFormatting:
    def test_short_format_concise(self):
        routine = _sample_routine()
        short = _format_routine_short(routine)
        # Short format should have step names but NOT ingredient categories
        assert "Cleanser" in short
        assert "Sunscreen" in short
        assert "gentle gel cleanser" not in short  # no ingredient detail

    def test_detailed_format_has_ingredients(self):
        routine = _sample_routine()
        detailed = _format_routine_detailed(routine)
        assert "gentle gel cleanser" in detailed
        assert "SPF 50" in detailed
        assert "Key Notes" in detailed

    def test_short_format_shorter_than_detailed(self):
        routine = _sample_routine()
        short = _format_routine_short(routine)
        detailed = _format_routine_detailed(routine)
        assert len(short) < len(detailed)


# ── Orchestrator agent integration tests (with FunctionModel) ───────────────


def _make_model_response(response_text: str, profile_updates: dict | None = None):
    """Create a ModelResponse that returns an OrchestratorResult via tool call."""
    result = OrchestratorResult(
        response=response_text,
        profile_updates=ProfileUpdates(**profile_updates) if profile_updates else None,
    )
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name="final_result",
                args=result.model_dump(mode="json"),
            )
        ]
    )


class TestOrchestratorAgent:
    @pytest.mark.anyio
    async def test_interview_phase_extracts_profile(self):
        """Agent returns profile updates that get applied correctly."""

        def mock_model(messages, info: AgentInfo):
            return _make_model_response(
                "Great! What's your skin type?",
                {"age_verified": True},
            )

        with orchestrator_agent.override(model=FunctionModel(mock_model)):
            deps = OrchestratorDeps(
                profile=_empty_profile(),
                phase=ConversationPhase.INTERVIEWING,
                profile_sufficient=False,
            )
            result = await orchestrator_agent.run("I'm 25", deps=deps)

            assert result.output.response == "Great! What's your skin type?"
            assert result.output.profile_updates.age_verified is True

    @pytest.mark.anyio
    async def test_complete_phase_has_routine_context(self):
        """Bug 1 fix: In COMPLETE phase, the system prompt includes the routine."""

        captured_messages = []

        def mock_model(messages, info: AgentInfo):
            captured_messages.extend(messages)
            return _make_model_response(
                "Your first step is the Cleanser — a gentle gel cleanser."
            )

        routine = _sample_routine()
        with orchestrator_agent.override(model=FunctionModel(mock_model)):
            deps = OrchestratorDeps(
                profile=_complete_profile(),
                phase=ConversationPhase.COMPLETE,
                profile_sufficient=True,
                routine_json=routine.model_dump(mode="json"),
            )
            result = await orchestrator_agent.run(
                "What's my first step in the morning?", deps=deps
            )

            # Verify the system prompt includes routine info
            system_parts = []
            for msg in captured_messages:
                if isinstance(msg, ModelRequest):
                    for part in msg.parts:
                        if hasattr(part, "content") and "POST-ROUTINE" in str(
                            getattr(part, "content", "")
                        ):
                            system_parts.append(part)

            assert len(system_parts) > 0, "System prompt should include POST-ROUTINE phase"

    @pytest.mark.anyio
    async def test_interview_nudge_when_sufficient(self):
        """Bug 2 fix: When profile is sufficient, system prompt nudges wrap-up."""

        captured_messages = []

        def mock_model(messages, info: AgentInfo):
            captured_messages.extend(messages)
            return _make_model_response("Here's your summary...")

        with orchestrator_agent.override(model=FunctionModel(mock_model)):
            deps = OrchestratorDeps(
                profile=_complete_profile(),
                phase=ConversationPhase.INTERVIEWING,
                profile_sufficient=True,
                force_summarize=False,
            )
            await orchestrator_agent.run("My budget is mid-range", deps=deps)

            # Check system prompt contains wrap-up nudge
            prompt_text = str(captured_messages)
            assert "wrap up" in prompt_text.lower() or "WRAP-UP" in prompt_text

    @pytest.mark.anyio
    async def test_force_summarize_after_2_turns(self):
        """Bug 2 fix: After 2 turns past sufficiency, force mandatory wrap-up."""

        captured_messages = []

        def mock_model(messages, info: AgentInfo):
            captured_messages.extend(messages)
            return _make_model_response("Here's your summary...")

        with orchestrator_agent.override(model=FunctionModel(mock_model)):
            deps = OrchestratorDeps(
                profile=_complete_profile(),
                phase=ConversationPhase.INTERVIEWING,
                profile_sufficient=True,
                force_summarize=True,
            )
            await orchestrator_agent.run("Anything else?", deps=deps)

            prompt_text = str(captured_messages)
            assert "MANDATORY" in prompt_text


# ── Phase transition logic tests ────────────────────────────────────────────


class TestPhaseTransitions:
    def test_turns_since_sufficient_increments(self):
        """Verify the counter logic for nudge/force."""
        profile = _complete_profile()
        assert profile.turns_since_sufficient == 0

        # Simulate what the service does
        if _is_profile_sufficient(profile):
            profile.turns_since_sufficient += 1
        assert profile.turns_since_sufficient == 1

        # Second turn
        if _is_profile_sufficient(profile):
            profile.turns_since_sufficient += 1
        assert profile.turns_since_sufficient == 2

        # At 2, force transition
        assert profile.turns_since_sufficient >= 2

    def test_turns_reset_when_not_sufficient(self):
        profile = _empty_profile(turns_since_sufficient=1)
        if not _is_profile_sufficient(profile):
            profile.turns_since_sufficient = 0
        assert profile.turns_since_sufficient == 0


# ── Run with: pytest tests/test_orchestrator.py -v ──────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
