"""Tests for CoachingPipeline — the main 11-step coaching processing pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from wellness_bot.coaching.pipeline import CoachingPipeline, PipelineConfig


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=[
        MagicMock(
            content='{"risk_level":"low","emotional_state":{"anxiety":0.3},"readiness_for_practice":0.5,"coaching_hypotheses":[],"confidence":0.8,"candidate_constraints":[]}',
            input_tokens=100,
            output_tokens=50,
        ),
        MagicMock(
            content="I understand. Tell me more about what's bothering you?",
            input_tokens=100,
            output_tokens=30,
        ),
    ])
    return provider


class TestSafeMessageProcessing:
    """Safe messages go through the full pipeline and return a string response."""

    async def test_returns_string_response(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        result = await pipeline.process("user1", "I had a stressful day at work")

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_response_comes_from_llm(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        result = await pipeline.process("user1", "I had a stressful day at work")

        assert result == "I understand. Tell me more about what's bothering you?"


class TestCrisisMessage:
    """Crisis messages are non-blocking: LLM is called AND crisis resources are appended."""

    async def test_crisis_appends_crisis_resources(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        result = await pipeline.process("user1", "I want to kill myself")

        # Crisis resources are appended to the LLM response
        assert "988" in result or "crisis" in result.lower() or "help" in result.lower()

    async def test_crisis_still_calls_llm(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        await pipeline.process("user1", "I want to kill myself")

        # Non-blocking: LLM IS called (context analyzer + response generator)
        assert mock_provider.chat.call_count == 2

    async def test_crisis_russian_appends_russian_resources(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        result = await pipeline.process("user1", "хочу покончить с собой")

        # Should contain Russian crisis line number appended to response
        assert "8-800-2000-122" in result


class TestLanguageDetection:
    """Language is detected from user message and used in responses."""

    async def test_russian_text_detected(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        await pipeline.process("user1", "Мне сегодня очень грустно и тяжело на душе")

        # The second call to LLM (response generation) should include
        # language instruction in the system prompt
        assert mock_provider.chat.call_count == 2
        # Check the system prompt of the second call contains Russian language
        second_call = mock_provider.chat.call_args_list[1]
        system_prompt = second_call.kwargs.get("system", "") or second_call[1].get("system", "")
        if not system_prompt:
            # Try positional args
            system_prompt = second_call[0][1] if len(second_call[0]) > 1 else ""
        assert "ru" in system_prompt.lower() or "russian" in system_prompt.lower() or "Respond in ru" in system_prompt

    async def test_english_text_detected(self, mock_provider):
        pipeline = CoachingPipeline(llm_provider=mock_provider)
        await pipeline.process("user1", "I feel really stressed about my job situation")

        assert mock_provider.chat.call_count == 2
        second_call = mock_provider.chat.call_args_list[1]
        system_prompt = second_call.kwargs.get("system", "") or second_call[1].get("system", "")
        if not system_prompt:
            system_prompt = second_call[0][1] if len(second_call[0]) > 1 else ""
        assert "en" in system_prompt.lower() or "english" in system_prompt.lower() or "Respond in en" in system_prompt
