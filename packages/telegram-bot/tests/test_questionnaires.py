"""Tests for PHQ-2 and GAD-2 questionnaires."""

import pytest
import aiosqlite

from wellness_bot.protocol.questionnaires import (
    GAD2,
    PHQ2,
    QUESTIONNAIRES,
    QuestionnaireRepository,
)


class TestPHQ2:
    def test_has_two_items(self):
        assert len(PHQ2.items) == 2

    def test_score_zeros(self):
        assert PHQ2.score([0, 0]) == 0

    def test_score_max(self):
        assert PHQ2.score([3, 3]) == 6

    def test_score_mixed(self):
        assert PHQ2.score([1, 2]) == 3

    def test_interpret_normal(self):
        assert PHQ2.interpret(0) == "normal"
        assert PHQ2.interpret(2) == "normal"

    def test_interpret_monitor(self):
        assert PHQ2.interpret(3) == "monitor"
        assert PHQ2.interpret(4) == "monitor"

    def test_interpret_suggest_specialist(self):
        assert PHQ2.interpret(5) == "suggest_specialist"
        assert PHQ2.interpret(6) == "suggest_specialist"

    def test_wrong_answer_count_raises(self):
        with pytest.raises(ValueError, match="expects 2 answers"):
            PHQ2.score([1, 2, 3])

    def test_out_of_range_answer_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            PHQ2.score([0, 4])

    def test_frequency_is_14_days(self):
        assert PHQ2.frequency_days == 14


class TestGAD2:
    def test_has_two_items(self):
        assert len(GAD2.items) == 2

    def test_score_zeros(self):
        assert GAD2.score([0, 0]) == 0

    def test_score_max(self):
        assert GAD2.score([3, 3]) == 6

    def test_interpret_normal(self):
        assert GAD2.interpret(2) == "normal"

    def test_interpret_monitor(self):
        assert GAD2.interpret(3) == "monitor"

    def test_interpret_suggest_specialist(self):
        assert GAD2.interpret(5) == "suggest_specialist"


class TestQuestionnaireRegistry:
    def test_both_questionnaires_registered(self):
        assert set(QUESTIONNAIRES.keys()) == {"PHQ2", "GAD2"}

    def test_registry_returns_same_objects(self):
        assert QUESTIONNAIRES["PHQ2"] is PHQ2
        assert QUESTIONNAIRES["GAD2"] is GAD2


class TestQuestionnaireRepository:
    @pytest.fixture
    async def db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        async with aiosqlite.connect(db_path) as db:
            repo = QuestionnaireRepository(db)
            await repo.ensure_table()
            yield db

    async def test_save_and_get_latest(self, db):
        repo = QuestionnaireRepository(db)
        await repo.save_result("user1", "PHQ2", [1, 2], 3, "monitor")

        result = await repo.get_latest("user1", "PHQ2")
        assert result is not None
        assert result.user_id == "user1"
        assert result.questionnaire_id == "PHQ2"
        assert result.answers == [1, 2]
        assert result.total_score == 3
        assert result.interpretation == "monitor"

    async def test_get_latest_returns_none_when_empty(self, db):
        repo = QuestionnaireRepository(db)
        result = await repo.get_latest("user1", "PHQ2")
        assert result is None

    async def test_needs_administration_when_never_taken(self, db):
        repo = QuestionnaireRepository(db)
        assert await repo.needs_administration("user1", "PHQ2", 14) is True

    async def test_needs_administration_after_save(self, db):
        repo = QuestionnaireRepository(db)
        await repo.save_result("user1", "PHQ2", [0, 0], 0, "normal")
        # Just saved — should NOT need re-administration
        assert await repo.needs_administration("user1", "PHQ2", 14) is False

    async def test_user_isolation(self, db):
        repo = QuestionnaireRepository(db)
        await repo.save_result("user1", "PHQ2", [1, 1], 2, "normal")
        result = await repo.get_latest("user2", "PHQ2")
        assert result is None
