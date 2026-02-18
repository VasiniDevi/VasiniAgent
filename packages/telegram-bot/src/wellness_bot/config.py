"""Bot configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class BotConfig(BaseSettings):
    """All configuration loaded from env vars or .env file."""

    # Telegram
    telegram_bot_token: str

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5-20250929"

    # OpenAI (Whisper STT)
    openai_api_key: str

    # ElevenLabs (TTS)
    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # Bella — warm female
    elevenlabs_model: str = "eleven_multilingual_v2"

    # Proactive check-ins
    checkin_interval_hours: float = 4.0
    quiet_hours_start: int = 23  # 23:00
    quiet_hours_end: int = 8    # 08:00

    # Paths
    pack_dir: str = "packs/wellness-cbt"
    db_path: str = "data/wellness.db"

    # Allowed users (telegram user IDs, comma-separated)
    allowed_user_ids: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def allowed_ids(self) -> set[int]:
        if not self.allowed_user_ids:
            return set()
        return {int(x.strip()) for x in self.allowed_user_ids.split(",") if x.strip()}
