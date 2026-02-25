"""Telegram bot message handlers."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message as TgMessage

from vasini.composer import Composer
from vasini.llm.anthropic_provider import AnthropicProvider
from vasini.llm.providers import Message
from vasini.llm.router import LLMRouter, LLMRouterConfig, ModelTier
from vasini.runtime.agent import AgentRuntime

from wellness_bot.config import BotConfig
from wellness_bot.session_store import SessionStore
from wellness_bot.voice import VoicePipeline

logger = logging.getLogger(__name__)
router = Router()


class WellnessBot:
    """Central bot controller wiring all components."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.store: SessionStore | None = None
        self.voice: VoicePipeline | None = None
        self.agent_runtime: AgentRuntime | None = None
        self.provider: AnthropicProvider | None = None

    async def setup(self) -> None:
        """Initialize all subsystems."""
        # Session store
        self.store = SessionStore(self.config.db_path)
        await self.store.init()

        # Voice pipeline
        self.voice = VoicePipeline(
            openai_api_key=self.config.openai_api_key,
            elevenlabs_api_key=self.config.elevenlabs_api_key,
            elevenlabs_voice_id=self.config.elevenlabs_voice_id,
            elevenlabs_model=self.config.elevenlabs_model,
        )

        # LLM provider
        self.provider = AnthropicProvider(
            api_key=self.config.anthropic_api_key,
            default_model=self.config.claude_model,
        )

        # Load pack and build runtime
        pack_dir = Path(self.config.pack_dir)
        composer = Composer()
        agent_config = composer.load(pack_dir)

        llm_config = LLMRouterConfig(
            tier_mapping={
                ModelTier.TIER_1: "claude-opus-4-6",
                ModelTier.TIER_2: self.config.claude_model,
            },
            default_tier=ModelTier.TIER_2,
            fallback_chain=[ModelTier.TIER_2, ModelTier.TIER_1],
        )
        llm_router = LLMRouter(config=llm_config)
        self.agent_runtime = AgentRuntime(config=agent_config, llm_router=llm_router)

    def _require_setup(self) -> tuple[SessionStore, AnthropicProvider, AgentRuntime, VoicePipeline]:
        """Assert all subsystems are initialized and return them."""
        assert self.store is not None, "Bot not initialized — call setup() first"
        assert self.provider is not None, "Bot not initialized — call setup() first"
        assert self.agent_runtime is not None, "Bot not initialized — call setup() first"
        assert self.voice is not None, "Bot not initialized — call setup() first"
        return self.store, self.provider, self.agent_runtime, self.voice

    async def process_text(self, user_id: int, text: str) -> str:
        """Process a text message and return response."""
        store, provider, runtime, _ = self._require_setup()

        # Save user message
        await store.save_message(user_id, "user", text)

        # Load conversation history
        history = await store.get_messages(user_id, limit=20)
        moods = await store.get_moods(user_id, limit=5)

        # Build context for LLM
        system_prompt = runtime._build_system_prompt()

        # Add mood context if available
        if moods:
            mood_ctx = "\n".join(
                f"- Mood {m['score']}/10 ({m['note']})" for m in moods[:3]
            )
            system_prompt += f"\n\nRecent mood history:\n{mood_ctx}"

        # Build messages
        messages = [Message(role=m["role"], content=m["content"]) for m in history]

        # Call Claude
        response = await provider.chat(messages=messages, system=system_prompt)
        reply = response.content

        # Track token usage
        usage = response.usage
        if usage:
            await store.save_token_usage(
                user_id=user_id,
                model=response.model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            )

        # Save assistant response
        await store.save_message(user_id, "assistant", reply)

        # Reset missed check-ins counter (user is active)
        await store.reset_missed_checkins(user_id)

        return reply

    async def shutdown(self) -> None:
        if self.store:
            await self.store.close()
        if self.voice:
            await self.voice.close()
        if self.provider:
            await self.provider.close()


# Global bot instance (set during app startup)
_bot_instance: WellnessBot | None = None


def set_bot_instance(bot: WellnessBot) -> None:
    global _bot_instance
    _bot_instance = bot


def get_bot() -> WellnessBot:
    assert _bot_instance is not None, "Bot not initialized"
    return _bot_instance


@router.message(CommandStart())
async def cmd_start(message: TgMessage) -> None:
    """Handle /start — onboarding."""
    bot = get_bot()
    assert message.from_user is not None
    user_id = message.from_user.id
    store, _, _, _ = bot._require_setup()
    await store.update_user_state(user_id, status="onboarding")

    welcome = (
        "Привет! Я — wellness-ассистент, работаю на основе когнитивно-поведенческой "
        "терапии и метакогниции.\n\n"
        "Я не врач и не заменяю терапевта. Но могу помочь разобраться в мыслях, "
        "эмоциях и научить конкретным техникам.\n\n"
        "Можешь писать текстом или голосовыми — я отвечу так же.\n\n"
        "Как ты себя сейчас чувствуешь? Оцени от 1 до 10."
    )
    await message.answer(welcome)
    await store.save_message(user_id, "assistant", welcome)


@router.message(F.voice)
async def handle_voice(message: TgMessage, bot: Bot) -> None:
    """Handle voice message: STT → process → TTS → voice reply."""
    wellness = get_bot()
    assert message.from_user is not None
    user_id = message.from_user.id
    _, _, _, voice = wellness._require_setup()

    try:
        # Download voice file
        assert message.voice is not None
        file = await bot.get_file(message.voice.file_id)
        assert file.file_path is not None
        voice_data = io.BytesIO()
        await bot.download_file(file.file_path, voice_data)
        audio_bytes = voice_data.getvalue()

        # STT
        text = await voice.speech_to_text(audio_bytes)
        if not text.strip():
            await message.answer("Не удалось распознать голосовое сообщение. Попробуй ещё раз?")
            return

        # Process as text
        reply = await wellness.process_text(user_id, text)

        # TTS — respond with voice
        try:
            audio_reply = await voice.text_to_speech(reply)
            await message.answer_voice(voice=BufferedInputFile(audio_reply, filename="reply.mp3"))
        except Exception as e:
            logger.exception(f"TTS failed for {user_id}, falling back to text")
            await message.answer(reply)
    except Exception as e:
        logger.exception(f"Error processing voice from {user_id}")
        await message.answer("Не удалось обработать голосовое. Попробуй текстом или ещё раз через минуту.")


@router.message(F.text)
async def handle_text(message: TgMessage) -> None:
    """Handle text message."""
    wellness = get_bot()
    assert message.from_user is not None
    assert message.text is not None
    user_id = message.from_user.id
    try:
        reply = await wellness.process_text(user_id, message.text)
        await message.answer(reply)
    except Exception as e:
        logger.exception(f"Error processing message from {user_id}")
        await message.answer("Произошла ошибка. Попробуй ещё раз через минуту.")
