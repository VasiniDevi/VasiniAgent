"""Tests for bot handlers (unit tests with mocks)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wellness_bot.config import BotConfig
from wellness_bot.handlers import WellnessBot


class TestWellnessBot:

    @pytest.fixture
    def config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
        return BotConfig(db_path=str(tmp_path / "test.db"))

    def test_create_bot(self, config):
        bot = WellnessBot(config)
        assert bot.config == config
        assert bot.store is None  # not yet initialized

    async def test_setup_initializes_components(self, config):
        bot = WellnessBot(config)
        # Mock Composer to avoid needing actual pack files
        mock_config = MagicMock()
        mock_config.soul.tone.default = "test tone"
        mock_config.soul.principles = ["p1"]
        mock_config.role.title = "Test"
        mock_config.role.domain = "Test"
        mock_config.role.goal.primary = "Test"
        mock_config.role.backstory = "Test"
        mock_config.role.limitations = []
        mock_config.guardrails.behavioral.prohibited_actions = []
        mock_config.guardrails.behavioral.required_disclaimers = []
        mock_config.guardrails.behavioral.max_autonomous_steps = 10

        with patch("wellness_bot.handlers.Composer") as MockComposer:
            MockComposer.return_value.load.return_value = mock_config
            await bot.setup()

        assert bot.store is not None
        assert bot.voice is not None
        assert bot.provider is not None
        await bot.shutdown()

    async def test_process_text_saves_messages(self, config):
        bot = WellnessBot(config)
        mock_config = MagicMock()
        mock_config.soul.tone.default = "Be direct"
        mock_config.soul.principles = ["Be honest"]
        mock_config.role.title = "Therapist"
        mock_config.role.domain = "CBT"
        mock_config.role.goal.primary = "Help"
        mock_config.role.backstory = "Expert"
        mock_config.role.limitations = []
        mock_config.guardrails.behavioral.prohibited_actions = []
        mock_config.guardrails.behavioral.required_disclaimers = []
        mock_config.guardrails.behavioral.max_autonomous_steps = 10

        with patch("wellness_bot.handlers.Composer") as MockComposer:
            MockComposer.return_value.load.return_value = mock_config
            await bot.setup()

        mock_response = MagicMock()
        mock_response.content = "How are you feeling?"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = {"input_tokens": 50, "output_tokens": 25}
        bot.provider.chat = AsyncMock(return_value=mock_response)

        reply = await bot.process_text(user_id=12345, text="Hello")

        assert reply == "How are you feeling?"
        msgs = await bot.store.get_messages(12345, limit=10)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        await bot.shutdown()
