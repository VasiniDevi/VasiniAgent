"""Tests for voice pipeline (STT + TTS)."""

from wellness_bot.voice import VoicePipeline


class TestVoicePipeline:

    def test_create_pipeline(self):
        pipeline = VoicePipeline(
            openai_api_key="sk-test",
            elevenlabs_api_key="el-test",
            elevenlabs_voice_id="test-voice",
        )
        assert pipeline is not None

    def test_ogg_to_mp3_path(self):
        pipeline = VoicePipeline(
            openai_api_key="sk-test",
            elevenlabs_api_key="el-test",
            elevenlabs_voice_id="test-voice",
        )
        result = pipeline._temp_path("test", ".mp3")
        assert result.suffix == ".mp3"
        assert "test" in result.name
