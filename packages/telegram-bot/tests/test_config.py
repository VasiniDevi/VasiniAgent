"""Tests for bot configuration."""

from wellness_bot.config import BotConfig


class TestBotConfig:

    def test_create_config(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
        config = BotConfig()
        assert config.telegram_bot_token == "123:ABC"
        assert config.claude_model == "claude-sonnet-4-5-20250929"
        assert config.checkin_interval_hours == 4.0

    def test_allowed_ids_parsing(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
        monkeypatch.setenv("ALLOWED_USER_IDS", "111,222,333")
        config = BotConfig()
        assert config.allowed_ids == {111, 222, 333}

    def test_empty_allowed_ids(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
        config = BotConfig()
        assert config.allowed_ids == set()
