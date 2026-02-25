"""Smoke tests for coaching pipeline integration in Telegram handlers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from wellness_bot.coaching.pipeline import CoachingPipeline, PipelineConfig


@pytest.mark.asyncio
async def test_pipeline_integration_smoke():
    """CoachingPipeline.process() returns a non-empty string for a simple greeting."""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=[
        # First call: ContextAnalyzer -> returns JSON context
        MagicMock(
            content='{"risk_level":"low","emotional_state":{},'
                    '"readiness_for_practice":0.5,"coaching_hypotheses":[],'
                    '"confidence":0.8,"candidate_constraints":[]}',
            input_tokens=100,
            output_tokens=50,
        ),
        # Second call: ResponseGenerator -> returns reply text
        MagicMock(
            content="Привет! Как я могу помочь?",
            input_tokens=50,
            output_tokens=20,
        ),
    ])
    pipeline = CoachingPipeline(llm_provider=provider, config=PipelineConfig())
    result = await pipeline.process("test_user", "Привет")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_process_message_falls_back_on_pipeline_failure():
    """WellnessBot.process_message falls back to process_text when pipeline raises."""
    from wellness_bot.handlers import WellnessBot

    # Create a minimal bot instance without calling setup()
    config = MagicMock()
    bot = WellnessBot(config)

    # Set up a pipeline that always raises
    mock_pipeline = AsyncMock()
    mock_pipeline.process = AsyncMock(side_effect=RuntimeError("boom"))
    bot.pipeline = mock_pipeline

    # Mock process_text as the fallback
    bot.process_text = AsyncMock(return_value="fallback reply")

    result = await bot.process_message(user_id=123, text="hello")

    assert result == "fallback reply"
    mock_pipeline.process.assert_awaited_once_with("123", "hello")
    bot.process_text.assert_awaited_once_with(123, "hello")


@pytest.mark.asyncio
async def test_process_message_uses_pipeline_when_available():
    """WellnessBot.process_message uses pipeline when it succeeds."""
    from wellness_bot.handlers import WellnessBot

    config = MagicMock()
    bot = WellnessBot(config)

    mock_pipeline = AsyncMock()
    mock_pipeline.process = AsyncMock(return_value="pipeline reply")
    bot.pipeline = mock_pipeline

    bot.process_text = AsyncMock(return_value="fallback reply")

    result = await bot.process_message(user_id=456, text="test")

    assert result == "pipeline reply"
    mock_pipeline.process.assert_awaited_once_with("456", "test")
    bot.process_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_uses_legacy_when_no_pipeline():
    """WellnessBot.process_message uses process_text when pipeline is None."""
    from wellness_bot.handlers import WellnessBot

    config = MagicMock()
    bot = WellnessBot(config)
    assert bot.pipeline is None  # not set up

    bot.process_text = AsyncMock(return_value="legacy reply")

    result = await bot.process_message(user_id=789, text="hi")

    assert result == "legacy reply"
    bot.process_text.assert_awaited_once_with(789, "hi")
