"""Tests for LLM-based context analyzer."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from wellness_bot.coaching.context_analyzer import ContextAnalyzer
from wellness_bot.protocol.types import ContextState, EmotionalState


def _make_llm_response(data: dict) -> MagicMock:
    """Build a mock LLM response object with .content, .input_tokens, .output_tokens."""
    resp = MagicMock()
    resp.content = json.dumps(data)
    resp.input_tokens = 100
    resp.output_tokens = 50
    return resp


VALID_JSON = {
    "risk_level": "medium",
    "emotional_state": {
        "anxiety": 0.7,
        "rumination": 0.4,
        "avoidance": 0.2,
        "perfectionism": 0.1,
        "self_criticism": 0.5,
        "symptom_fixation": 0.0,
    },
    "readiness_for_practice": 0.6,
    "coaching_hypotheses": ["user shows moderate anxiety"],
    "confidence": 0.85,
    "candidate_constraints": ["no_breathing"],
}


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.chat = AsyncMock(return_value=_make_llm_response(VALID_JSON))
    return provider


@pytest.fixture
def analyzer(mock_provider: AsyncMock) -> ContextAnalyzer:
    return ContextAnalyzer(llm_provider=mock_provider)


class TestValidJsonResponse:
    """LLM returns well-formed JSON -> ContextState with correct values."""

    @pytest.mark.asyncio
    async def test_returns_context_state(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious today",
            dialogue_window=[{"role": "user", "content": "hello"}],
            mood_history=[{"date": "2026-02-20", "score": 4}],
            practice_history=[],
            user_profile={"name": "Alice"},
            language="en",
        )
        assert isinstance(result, ContextState)

    @pytest.mark.asyncio
    async def test_risk_level_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert result.risk_level == "medium"

    @pytest.mark.asyncio
    async def test_emotional_state_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert isinstance(result.emotional_state, EmotionalState)
        assert result.emotional_state.anxiety == 0.7
        assert result.emotional_state.rumination == 0.4
        assert result.emotional_state.self_criticism == 0.5

    @pytest.mark.asyncio
    async def test_readiness_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert result.readiness_for_practice == 0.6

    @pytest.mark.asyncio
    async def test_coaching_hypotheses_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert result.coaching_hypotheses == ["user shows moderate anxiety"]

    @pytest.mark.asyncio
    async def test_confidence_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_candidate_constraints_parsed(self, analyzer: ContextAnalyzer) -> None:
        result = await analyzer.analyze(
            user_message="I feel anxious",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert result.candidate_constraints == ["no_breathing"]


class TestSystemPromptContainsContext:
    """LLM is called with system prompt containing 'context'."""

    @pytest.mark.asyncio
    async def test_system_prompt_has_context(self, analyzer: ContextAnalyzer, mock_provider: AsyncMock) -> None:
        await analyzer.analyze(
            user_message="hi",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        mock_provider.chat.assert_called_once()
        call_kwargs = mock_provider.chat.call_args
        # system can be positional or keyword
        system_arg = call_kwargs.kwargs.get("system") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("system", "")
        assert "context" in system_arg.lower()


class TestMalformedJsonDefaults:
    """Malformed JSON returns safe defaults with low confidence."""

    @pytest.mark.asyncio
    async def test_malformed_json_returns_defaults(self) -> None:
        provider = AsyncMock()
        bad_resp = MagicMock()
        bad_resp.content = "this is not json {{{{"
        bad_resp.input_tokens = 10
        bad_resp.output_tokens = 5
        provider.chat = AsyncMock(return_value=bad_resp)

        analyzer = ContextAnalyzer(llm_provider=provider)
        result = await analyzer.analyze(
            user_message="test",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert isinstance(result, ContextState)
        assert result.risk_level == "low"
        assert result.confidence == 0.3
        assert result.readiness_for_practice == 0.5
        assert result.coaching_hypotheses == []
        assert result.candidate_constraints == []

    @pytest.mark.asyncio
    async def test_partial_json_returns_defaults(self) -> None:
        """JSON that parses but is missing required fields."""
        provider = AsyncMock()
        partial_resp = MagicMock()
        partial_resp.content = json.dumps({"risk_level": "high"})
        partial_resp.input_tokens = 10
        partial_resp.output_tokens = 5
        provider.chat = AsyncMock(return_value=partial_resp)

        analyzer = ContextAnalyzer(llm_provider=provider)
        result = await analyzer.analyze(
            user_message="test",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        # Should still produce a valid ContextState (with defaults for missing fields)
        assert isinstance(result, ContextState)


class TestMoodHistoryInPrompt:
    """Mood history should be included in the user prompt sent to LLM."""

    @pytest.mark.asyncio
    async def test_mood_history_in_prompt(self, mock_provider: AsyncMock) -> None:
        analyzer = ContextAnalyzer(llm_provider=mock_provider)
        mood_history = [
            {"date": "2026-02-20", "score": 3},
            {"date": "2026-02-21", "score": 5},
        ]
        await analyzer.analyze(
            user_message="I feel better",
            dialogue_window=[],
            mood_history=mood_history,
            practice_history=[],
            user_profile={},
            language="en",
        )
        call_kwargs = mock_provider.chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
        # At least one message should contain mood history data
        all_content = " ".join(m["content"] for m in messages)
        assert "2026-02-20" in all_content
        assert "2026-02-21" in all_content


class TestLlmExceptionDefaults:
    """LLM exception returns safe defaults with confidence 0.2."""

    @pytest.mark.asyncio
    async def test_llm_exception_returns_defaults(self) -> None:
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        analyzer = ContextAnalyzer(llm_provider=provider)
        result = await analyzer.analyze(
            user_message="test",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert isinstance(result, ContextState)
        assert result.risk_level == "low"
        assert result.confidence == 0.2
        assert result.readiness_for_practice == 0.5
        assert result.coaching_hypotheses == []
        assert result.candidate_constraints == []

    @pytest.mark.asyncio
    async def test_llm_exception_never_crashes(self) -> None:
        """Even unexpected exceptions should not propagate."""
        provider = AsyncMock()
        provider.chat = AsyncMock(side_effect=Exception("totally unexpected"))

        analyzer = ContextAnalyzer(llm_provider=provider)
        # Should NOT raise
        result = await analyzer.analyze(
            user_message="test",
            dialogue_window=[],
            mood_history=[],
            practice_history=[],
            user_profile={},
            language="en",
        )
        assert isinstance(result, ContextState)
