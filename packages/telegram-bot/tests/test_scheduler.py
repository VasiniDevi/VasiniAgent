"""Tests for proactive check-in scheduler."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from wellness_bot.scheduler import CheckInScheduler


class TestCheckInScheduler:

    @pytest.fixture
    def scheduler(self):
        bot = AsyncMock()
        store = AsyncMock()
        store.get_user_state.return_value = {
            "status": "stable",
            "checkin_interval": 4.0,
            "missed_checkins": 0,
            "quiet_start": 23,
            "quiet_end": 8,
        }
        return CheckInScheduler(bot=bot, store=store)

    def test_create_scheduler(self, scheduler):
        assert scheduler.default_interval == 4.0

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
