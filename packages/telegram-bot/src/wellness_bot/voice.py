"""Voice pipeline: Whisper STT + ElevenLabs TTS."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx


class VoicePipeline:
    """Converts voice↔text using Whisper (STT) and ElevenLabs (TTS)."""

    WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
    ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(
        self,
        openai_api_key: str,
        elevenlabs_api_key: str,
        elevenlabs_voice_id: str,
        elevenlabs_model: str = "eleven_multilingual_v2",
    ) -> None:
        self.openai_api_key = openai_api_key
        self.elevenlabs_api_key = elevenlabs_api_key
        self.elevenlabs_voice_id = elevenlabs_voice_id
        self.elevenlabs_model = elevenlabs_model
        self._http = httpx.AsyncClient(timeout=30.0)

    def _temp_path(self, prefix: str, suffix: str) -> Path:
        """Create a temp file path."""
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        os.close(fd)
        return Path(path)

    async def speech_to_text(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Transcribe audio bytes via Whisper API."""
        resp = await self._http.post(
            self.WHISPER_URL,
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            files={"file": (filename, audio_bytes, "audio/ogg")},
            data={"model": "whisper-1"},
        )
        resp.raise_for_status()
        return resp.json()["text"]

    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech via ElevenLabs API. Returns MP3 bytes."""
        url = f"{self.ELEVENLABS_URL}/{self.elevenlabs_voice_id}"
        resp = await self._http.post(
            url,
            headers={
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": self.elevenlabs_model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        )
        resp.raise_for_status()
        return resp.content

    async def close(self) -> None:
        await self._http.aclose()
