"""Tests for proactive check-in scheduler."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wellness_bot.scheduler import CheckInScheduler


class TestCheckInScheduler:

    @pytest.fixture
    def scheduler(self):
        bot = AsyncMock()
        store = AsyncMock()
        store.get_user_state.return_value = {
            "status": "stable",
            "checkin_interval": 2.5,
            "missed_checkins": 0,
            "quiet_start": 23,
            "quiet_end": 8,
        }
        store.get_recent_messages.return_value = []
        return CheckInScheduler(bot=bot, store=store)

    def test_default_interval_is_2_5h(self, scheduler):
        assert scheduler.default_interval == 2.5

    def test_quiet_hours_detection(self, scheduler):
        with patch("wellness_bot.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 2, 0)  # 2 AM
            assert scheduler._is_quiet_hour() is True

            mock_dt.now.return_value = datetime(2026, 1, 1, 14, 0)  # 2 PM
            assert scheduler._is_quiet_hour() is False

    def test_rotating_messages(self, scheduler):
        msg1 = scheduler._next_checkin_message(user_id=123)
        msg2 = scheduler._next_checkin_message(user_id=123)
        assert msg1 != msg2  # Different messages each time
        assert msg1 in scheduler.MOOD_CHECKINS
        assert msg2 in scheduler.MOOD_CHECKINS

    async def test_checkin_skipped_during_quiet_hours(self, scheduler):
        with patch.object(scheduler, "_is_quiet_hour", return_value=True):
            await scheduler._run_checkin(user_id=123)
            scheduler.bot.send_message.assert_not_called()

    async def test_checkin_sends_message(self, scheduler):
        with patch.object(scheduler, "_is_quiet_hour", return_value=False):
            await scheduler._run_checkin(user_id=123)
            scheduler.bot.send_message.assert_called_once()

    async def test_three_strike_backoff(self, scheduler):
        scheduler.store.get_user_state.return_value["missed_checkins"] = 3
        with patch.object(scheduler, "_is_quiet_hour", return_value=False):
            await scheduler._run_checkin(user_id=123)
            # Should send backoff message, not regular check-in
            call_args = scheduler.bot.send_message.call_args
            assert "реже" in call_args[1].get("text", call_args[0][1])

    def test_schedule_user(self, scheduler):
        scheduler.schedule_user(user_id=123, interval_hours=4.0)
        job = scheduler._scheduler.get_job("checkin_123")
        assert job is not None

    def test_unschedule_user(self, scheduler):
        scheduler.schedule_user(user_id=123)
        scheduler.unschedule_user(user_id=123)
        job = scheduler._scheduler.get_job("checkin_123")
        assert job is None


class TestContextAwareCheckins:
    """Context-aware LLM-generated check-in messages."""

    @pytest.fixture
    def llm_provider(self):
        provider = AsyncMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(content="Как там с руминацией? Замечаешь паттерн?")
        )
        return provider

    @pytest.fixture
    def scheduler_with_llm(self, llm_provider, tmp_path):
        bot = AsyncMock()
        store = AsyncMock()
        store.get_user_state.return_value = {
            "status": "stable",
            "checkin_interval": 2.5,
            "missed_checkins": 0,
            "quiet_start": 23,
            "quiet_end": 8,
        }
        store.get_recent_messages.return_value = [
            {"role": "user", "content": "У меня опять руминация"},
            {"role": "assistant", "content": "Давай попробуем DM"},
        ]
        return CheckInScheduler(
            bot=bot,
            store=store,
            llm_provider=llm_provider,
            practices_dir=tmp_path,  # empty dir is fine — KB won't load practices but won't crash
        )

    async def test_llm_checkin_uses_conversation_context(self, scheduler_with_llm):
        summary = await scheduler_with_llm._get_conversation_summary(user_id=123)
        assert summary is not None
        assert "руминация" in summary

    async def test_generate_contextual_checkin_calls_llm(self, scheduler_with_llm, llm_provider):
        result = await scheduler_with_llm._generate_contextual_checkin("user: привет")
        assert result == "Как там с руминацией? Замечаешь паттерн?"
        llm_provider.chat.assert_called_once()

    async def test_contextual_checkin_sent_when_history_available(self, scheduler_with_llm, llm_provider):
        with patch.object(scheduler_with_llm, "_is_quiet_hour", return_value=False):
            await scheduler_with_llm._run_checkin(user_id=123)
            call_args = scheduler_with_llm.bot.send_message.call_args
            sent_text = call_args[1].get("text", call_args[0][1])
            assert sent_text == "Как там с руминацией? Замечаешь паттерн?"

    async def test_falls_back_to_generic_when_no_history(self, scheduler_with_llm):
        scheduler_with_llm.store.get_recent_messages.return_value = []
        with patch.object(scheduler_with_llm, "_is_quiet_hour", return_value=False):
            await scheduler_with_llm._run_checkin(user_id=123)
            call_args = scheduler_with_llm.bot.send_message.call_args
            sent_text = call_args[1].get("text", call_args[0][1])
            assert sent_text in scheduler_with_llm.MOOD_CHECKINS

    async def test_falls_back_when_llm_fails(self, scheduler_with_llm, llm_provider):
        llm_provider.chat.side_effect = RuntimeError("LLM unavailable")
        with patch.object(scheduler_with_llm, "_is_quiet_hour", return_value=False):
            await scheduler_with_llm._run_checkin(user_id=123)
            call_args = scheduler_with_llm.bot.send_message.call_args
            sent_text = call_args[1].get("text", call_args[0][1])
            assert sent_text in scheduler_with_llm.MOOD_CHECKINS

    async def test_no_llm_uses_generic(self):
        bot = AsyncMock()
        store = AsyncMock()
        store.get_user_state.return_value = {"missed_checkins": 0}
        store.get_recent_messages.return_value = [
            {"role": "user", "content": "test"},
        ]
        scheduler = CheckInScheduler(bot=bot, store=store)  # no llm_provider
        result = await scheduler._generate_contextual_checkin("summary")
        assert result is None
