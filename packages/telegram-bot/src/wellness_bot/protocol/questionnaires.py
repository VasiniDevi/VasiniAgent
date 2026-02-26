"""PHQ-2 and GAD-2 screening questionnaires with scoring and interpretation.

These ultra-brief screeners are administered periodically to track symptom
trends. Results inform scenario matching and check-in timing, but NEVER
block practices or refuse help.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class QuestionnaireItem:
    """A single questionnaire item."""

    text_ru: str
    text_en: str
    scale: list[str]  # Display labels for 0..N


@dataclass(frozen=True)
class Questionnaire:
    """A validated screening questionnaire."""

    id: str
    name_ru: str
    name_en: str
    items: list[QuestionnaireItem]
    frequency_days: int
    thresholds: dict[str, int]  # interpretation_label → min_score

    def score(self, answers: list[int]) -> int:
        """Sum up answers. Raises ValueError if wrong number of answers."""
        if len(answers) != len(self.items):
            raise ValueError(
                f"{self.id} expects {len(self.items)} answers, got {len(answers)}"
            )
        for i, a in enumerate(answers):
            max_val = len(self.items[i].scale) - 1
            if not (0 <= a <= max_val):
                raise ValueError(
                    f"Answer {i} out of range: {a} (expected 0-{max_val})"
                )
        return sum(answers)

    def interpret(self, total: int) -> str:
        """Return interpretation label based on total score."""
        # Check thresholds from highest to lowest
        for label in ("suggest_specialist", "monitor"):
            if label in self.thresholds and total >= self.thresholds[label]:
                return label
        return "normal"


# ---------------------------------------------------------------------------
# Scale labels (same for PHQ-2 and GAD-2)
# ---------------------------------------------------------------------------

_LIKERT_4_RU = [
    "Совсем нет (0)",
    "Несколько дней (1)",
    "Более половины дней (2)",
    "Почти каждый день (3)",
]

_LIKERT_4_EN = [
    "Not at all (0)",
    "Several days (1)",
    "More than half the days (2)",
    "Nearly every day (3)",
]

# ---------------------------------------------------------------------------
# PHQ-2 (Patient Health Questionnaire-2)
# ---------------------------------------------------------------------------

PHQ2 = Questionnaire(
    id="PHQ2",
    name_ru="PHQ-2 (Депрессия)",
    name_en="PHQ-2 (Depression)",
    items=[
        QuestionnaireItem(
            text_ru="За последние 2 недели, как часто вас беспокоило: мало интереса или удовольствия от дел?",
            text_en="Over the last 2 weeks, how often have you been bothered by: little interest or pleasure in doing things?",
            scale=_LIKERT_4_RU,
        ),
        QuestionnaireItem(
            text_ru="За последние 2 недели, как часто вас беспокоило: чувство подавленности, депрессии или безнадёжности?",
            text_en="Over the last 2 weeks, how often have you been bothered by: feeling down, depressed, or hopeless?",
            scale=_LIKERT_4_RU,
        ),
    ],
    frequency_days=14,
    thresholds={"monitor": 3, "suggest_specialist": 5},
)

# ---------------------------------------------------------------------------
# GAD-2 (Generalized Anxiety Disorder-2)
# ---------------------------------------------------------------------------

GAD2 = Questionnaire(
    id="GAD2",
    name_ru="GAD-2 (Тревога)",
    name_en="GAD-2 (Anxiety)",
    items=[
        QuestionnaireItem(
            text_ru="За последние 2 недели, как часто вас беспокоило: нервозность, тревожность или ощущение «на грани»?",
            text_en="Over the last 2 weeks, how often have you been bothered by: feeling nervous, anxious, or on edge?",
            scale=_LIKERT_4_RU,
        ),
        QuestionnaireItem(
            text_ru="За последние 2 недели, как часто вас беспокоило: невозможность остановить или контролировать беспокойство?",
            text_en="Over the last 2 weeks, how often have you been bothered by: not being able to stop or control worrying?",
            scale=_LIKERT_4_RU,
        ),
    ],
    frequency_days=14,
    thresholds={"monitor": 3, "suggest_specialist": 5},
)

# Registry for easy lookup
QUESTIONNAIRES: dict[str, Questionnaire] = {
    "PHQ2": PHQ2,
    "GAD2": GAD2,
}


# ---------------------------------------------------------------------------
# Questionnaire result storage
# ---------------------------------------------------------------------------


@dataclass
class QuestionnaireResult:
    """A completed questionnaire result."""

    user_id: str
    questionnaire_id: str
    answers: list[int]
    total_score: int
    interpretation: str
    completed_at: str  # ISO 8601


class QuestionnaireRepository:
    """Lightweight SQLite storage for questionnaire results."""

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS questionnaire_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        questionnaire_id TEXT NOT NULL,
        answers_json TEXT NOT NULL,
        total_score INTEGER NOT NULL,
        interpretation TEXT NOT NULL,
        completed_at TEXT NOT NULL
    )
    """

    CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_qr_user_questionnaire
    ON questionnaire_results (user_id, questionnaire_id, completed_at)
    """

    def __init__(self, db: object) -> None:
        """Initialize with an aiosqlite connection."""
        self._db = db

    async def ensure_table(self) -> None:
        """Create the questionnaire_results table if it doesn't exist."""
        await self._db.execute(self.CREATE_TABLE_SQL)
        await self._db.execute(self.CREATE_INDEX_SQL)
        await self._db.commit()

    async def save_result(
        self,
        user_id: str,
        questionnaire_id: str,
        answers: list[int],
        total_score: int,
        interpretation: str,
    ) -> None:
        """Save a completed questionnaire result."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO questionnaire_results "
            "(user_id, questionnaire_id, answers_json, total_score, interpretation, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, questionnaire_id, json.dumps(answers), total_score, interpretation, now),
        )
        await self._db.commit()

    async def get_latest(
        self, user_id: str, questionnaire_id: str
    ) -> QuestionnaireResult | None:
        """Get the most recent result for a user and questionnaire."""
        cursor = await self._db.execute(
            "SELECT user_id, questionnaire_id, answers_json, total_score, "
            "interpretation, completed_at "
            "FROM questionnaire_results "
            "WHERE user_id = ? AND questionnaire_id = ? "
            "ORDER BY completed_at DESC LIMIT 1",
            (user_id, questionnaire_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return QuestionnaireResult(
            user_id=row[0],
            questionnaire_id=row[1],
            answers=json.loads(row[2]),
            total_score=row[3],
            interpretation=row[4],
            completed_at=row[5],
        )

    async def needs_administration(
        self, user_id: str, questionnaire_id: str, frequency_days: int
    ) -> bool:
        """Check if a questionnaire is due for re-administration."""
        latest = await self.get_latest(user_id, questionnaire_id)
        if latest is None:
            return True
        completed = datetime.fromisoformat(latest.completed_at)
        return datetime.now(timezone.utc) - completed > timedelta(days=frequency_days)
