"""End-to-end integration tests with mocked external services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wellness_bot.config import BotConfig
from wellness_bot.handlers import WellnessBot


class TestE2EIntegration:

    @pytest.fixture
    def config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
        return BotConfig(
            db_path=str(tmp_path / "test.db"),
            pack_dir="../../packs/wellness-cbt",
        )

    def _mock_agent_config(self):
        mock = MagicMock()
        mock.soul.tone.default = "Be direct"
        mock.soul.principles = ["Be honest"]
        mock.role.title = "Therapist"
        mock.role.domain = "CBT"
        mock.role.goal.primary = "Help"
        mock.role.backstory = "Expert"
        mock.role.limitations = []
        mock.guardrails.behavioral.prohibited_actions = []
        mock.guardrails.behavioral.required_disclaimers = []
        mock.guardrails.behavioral.max_autonomous_steps = 10
        return mock

    async def test_text_message_roundtrip(self, config):
        """User sends text → gets text response."""
        bot = WellnessBot(config)

        with patch("wellness_bot.handlers.Composer") as MockComposer:
            MockComposer.return_value.load.return_value = self._mock_agent_config()
            await bot.setup()

        # Mock Claude response
        mock_response = MagicMock()
        mock_response.content = "Окей. Расскажи что происходит."
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = {"input_tokens": 50, "output_tokens": 25}
        bot.provider.chat = AsyncMock(return_value=mock_response)

        reply = await bot.process_text(user_id=12345, text="Мне плохо")

        assert reply == "Окей. Расскажи что происходит."

        # Verify message was saved
        msgs = await bot.store.get_messages(12345, limit=10)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

        await bot.shutdown()

    async def test_conversation_history_builds(self, config):
        """Multiple messages build context."""
        bot = WellnessBot(config)

        with patch("wellness_bot.handlers.Composer") as MockComposer:
            MockComposer.return_value.load.return_value = self._mock_agent_config()
            await bot.setup()

        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = {"input_tokens": 50, "output_tokens": 25}
        bot.provider.chat = AsyncMock(return_value=mock_response)

        await bot.process_text(12345, "Message 1")
        await bot.process_text(12345, "Message 2")
        await bot.process_text(12345, "Message 3")

        msgs = await bot.store.get_messages(12345, limit=20)
        assert len(msgs) == 6  # 3 user + 3 assistant

        await bot.shutdown()

    async def test_mood_context_included(self, config):
        """Mood history gets included in system prompt."""
        bot = WellnessBot(config)

        with patch("wellness_bot.handlers.Composer") as MockComposer:
            MockComposer.return_value.load.return_value = self._mock_agent_config()
            await bot.setup()

        # Save a mood entry
        await bot.store.save_mood(user_id=12345, score=3, note="anxious")

        mock_response = MagicMock()
        mock_response.content = "I see your mood was low."
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.usage = {"input_tokens": 50, "output_tokens": 25}
        bot.provider.chat = AsyncMock(return_value=mock_response)

        await bot.process_text(12345, "How am I doing?")

        # Verify Claude was called with mood context in system prompt
        call_kwargs = bot.provider.chat.call_args
        system_prompt = call_kwargs.kwargs.get("system", call_kwargs[1].get("system", ""))
        assert "Mood 3/10" in system_prompt

        await bot.shutdown()
