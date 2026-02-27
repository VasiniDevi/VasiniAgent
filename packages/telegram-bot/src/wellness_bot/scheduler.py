"""Proactive check-in scheduler with context-aware LLM-generated messages."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from wellness_bot.coaching.knowledge_base import KnowledgeBaseCompiler
from wellness_bot.session_store import SessionStore

logger = logging.getLogger(__name__)


class CheckInScheduler:
    """Manages proactive check-ins for all users.

    When an LLM provider is available, generates context-aware check-in
    messages based on the user's recent conversation history. Falls back
    to rotating generic messages when no LLM or no conversation context.
    """

    # Rotating check-in messages (fallback when no LLM or no context)
    MOOD_CHECKINS = [
        "Как ты сейчас? (1-5)",
        "Как самочувствие? Одним словом",
        "Какой уровень энергии прямо сейчас? (1-5)",
        "Как спал(а) сегодня?",
        "Что занимает голову прямо сейчас?",
        "По сравнению со вчера — лучше, так же или хуже?",
    ]

    def __init__(
        self,
        bot: Bot,
        store: SessionStore,
        default_interval_hours: float = 2.5,
        quiet_start: int = 23,
        quiet_end: int = 8,
        llm_provider: object | None = None,
        practices_dir: Path | str | None = None,
    ) -> None:
        self.bot = bot
        self.store = store
        self.default_interval = default_interval_hours
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end
        self._llm = llm_provider
        self._scheduler = AsyncIOScheduler()
        self._checkin_counter: dict[int, int] = {}  # user_id → rotation index
        self._kb: KnowledgeBaseCompiler | None = None
        if practices_dir:
            self._kb = KnowledgeBaseCompiler(practices_dir)

    def _is_quiet_hour(self) -> bool:
        """Check if current time is within quiet hours."""
        hour = datetime.now().hour
        if self.quiet_start > self.quiet_end:  # wraps midnight (e.g., 23-08)
            return hour >= self.quiet_start or hour < self.quiet_end
        return self.quiet_start <= hour < self.quiet_end

    def _next_checkin_message(self, user_id: int) -> str:
        """Get next rotating check-in message for user."""
        idx = self._checkin_counter.get(user_id, 0)
        msg = self.MOOD_CHECKINS[idx % len(self.MOOD_CHECKINS)]
        self._checkin_counter[user_id] = idx + 1
        return msg

    async def _get_conversation_summary(self, user_id: int) -> str | None:
        """Get recent conversation context for LLM-generated check-in."""
        try:
            messages = await self.store.get_recent_messages(user_id, limit=10)
        except Exception:
            return None
        if not messages:
            return None
        lines = []
        for m in messages[-5:]:
            role = m.get("role", "?")
            content = str(m.get("content", ""))[:150]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def _generate_contextual_checkin(self, summary: str) -> str | None:
        """Generate a context-aware check-in message using the LLM."""
        if self._llm is None or self._kb is None:
            return None
        system = self._kb.compile_checkin_prompt()
        prompt = (
            f"Based on this recent conversation, generate a short (1-2 sentences) "
            f"check-in message in the same language as the conversation. "
            f"Be warm, direct, sometimes humorous. Not pushy.\n\n"
            f"Recent context:\n{summary}\n\n"
            f"Generate ONLY the check-in message, nothing else."
        )
        try:
            response = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                model="claude-haiku-4-5-20251001",
            )
            return response.content
        except Exception:
            logger.exception("LLM check-in generation failed, falling back to generic")
            return None

    async def _run_checkin(self, user_id: int) -> None:
        """Execute a single check-in for one user."""
        if self._is_quiet_hour():
            logger.debug(f"Quiet hours — skipping check-in for {user_id}")
            return

        state = await self.store.get_user_state(user_id)

        # 3-strike rule
        if state["missed_checkins"] >= 3:
            logger.info(f"User {user_id} missed 3+ check-ins, backing off")
            await self.bot.send_message(
                user_id,
                "Я буду реже писать. Но я здесь — напиши когда будешь готов.",
            )
            await self.store.update_user_state(user_id, missed_checkins=0, checkin_interval=24.0)
            return

        # Try context-aware LLM check-in first
        msg = None
        summary = await self._get_conversation_summary(user_id)
        if summary:
            msg = await self._generate_contextual_checkin(summary)

        # Fallback to rotating generic message
        if msg is None:
            msg = self._next_checkin_message(user_id)

        try:
            await self.bot.send_message(user_id, msg)
            await self.store.increment_missed_checkins(user_id)
        except Exception as e:
            logger.error(f"Failed to send check-in to {user_id}: {e}")

    def schedule_user(self, user_id: int, interval_hours: float | None = None) -> None:
        """Schedule recurring check-ins for a user."""
        interval = interval_hours or self.default_interval
        job_id = f"checkin_{user_id}"

        # Remove existing job if any
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        self._scheduler.add_job(
            self._run_checkin,
            "interval",
            hours=interval,
            args=[user_id],
            id=job_id,
            replace_existing=True,
        )
        logger.info(f"Scheduled check-in for user {user_id} every {interval}h")

    def unschedule_user(self, user_id: int) -> None:
        """Remove check-ins for a user."""
        job_id = f"checkin_{user_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
