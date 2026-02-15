"""Tests for SQLite session store."""

import pytest

from wellness_bot.session_store import SessionStore


class TestSessionStore:

    @pytest.fixture
    async def store(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        s = SessionStore(db_path)
        await s.init()
        yield s
        await s.close()

    async def test_save_and_get_message(self, store):
        await store.save_message(user_id=123, role="user", content="Hello")
        msgs = await store.get_messages(user_id=123, limit=10)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"

    async def test_get_messages_ordered(self, store):
        await store.save_message(user_id=123, role="user", content="First")
        await store.save_message(user_id=123, role="assistant", content="Second")
        msgs = await store.get_messages(user_id=123, limit=10)
        assert len(msgs) == 2
        assert msgs[0]["content"] == "First"
        assert msgs[1]["content"] == "Second"

    async def test_user_isolation(self, store):
        await store.save_message(user_id=111, role="user", content="User A")
        await store.save_message(user_id=222, role="user", content="User B")
        msgs_a = await store.get_messages(user_id=111, limit=10)
        msgs_b = await store.get_messages(user_id=222, limit=10)
        assert len(msgs_a) == 1
        assert len(msgs_b) == 1

    async def test_save_mood(self, store):
        await store.save_mood(user_id=123, score=7, note="feeling good")
        moods = await store.get_moods(user_id=123, limit=5)
        assert len(moods) == 1
        assert moods[0]["score"] == 7

    async def test_get_user_state(self, store):
        state = await store.get_user_state(user_id=123)
        assert state["status"] == "onboarding"

    async def test_update_user_state(self, store):
        await store.update_user_state(user_id=123, status="stable", checkin_interval=4.0)
        state = await store.get_user_state(user_id=123)
        assert state["status"] == "stable"
        assert state["checkin_interval"] == 4.0

    async def test_missed_checkins_counter(self, store):
        await store.increment_missed_checkins(user_id=123)
        await store.increment_missed_checkins(user_id=123)
        state = await store.get_user_state(user_id=123)
        assert state["missed_checkins"] == 2

    async def test_reset_missed_checkins(self, store):
        await store.increment_missed_checkins(user_id=123)
        await store.reset_missed_checkins(user_id=123)
        state = await store.get_user_state(user_id=123)
        assert state["missed_checkins"] == 0

    async def test_save_and_get_token_usage(self, store):
        await store.save_token_usage(user_id=123, model="claude-sonnet", input_tokens=100, output_tokens=50)
        usage = await store.get_token_usage(days=1)
        assert len(usage) == 1
        assert usage[0]["input_tokens"] == 100
        assert usage[0]["output_tokens"] == 50

    async def test_token_summary(self, store):
        await store.save_token_usage(user_id=123, model="claude-sonnet", input_tokens=100, output_tokens=50)
        summary = await store.get_token_summary()
        assert summary["today"]["input_tokens"] == 100
        assert summary["today"]["output_tokens"] == 50

    async def test_get_all_users(self, store):
        await store.save_message(user_id=111, role="user", content="Hello")
        await store.save_message(user_id=222, role="user", content="Hi")
        users = await store.get_all_users()
        assert len(users) == 2

    async def test_get_recent_messages(self, store):
        await store.save_message(user_id=111, role="user", content="Msg 1")
        await store.save_message(user_id=111, role="assistant", content="Reply 1")
        recent = await store.get_recent_messages(limit=5)
        assert len(recent) == 2
