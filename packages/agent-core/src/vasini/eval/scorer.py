"""Quality scorer — computes match scores between actual and expected outputs.

Scoring:
  - Exact match (case-insensitive): 1.0
  - Fuzzy match: word overlap ratio (Jaccard similarity)
  - Error result: 0.0
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScoreResult:
    score: float
    exact_match: bool


class QualityScorer:
    """Scores actual vs expected output."""

    def score(self, actual: str, expected: str) -> ScoreResult:
        if not expected:
            return ScoreResult(score=0.0, exact_match=False)

        # Case-insensitive exact match
        if actual.strip().lower() == expected.strip().lower():
            return ScoreResult(score=1.0, exact_match=True)

        # Fuzzy: word overlap (Jaccard similarity)
        actual_words = set(actual.strip().lower().split())
        expected_words = set(expected.strip().lower().split())

        if not actual_words and not expected_words:
            return ScoreResult(score=0.0, exact_match=False)

        intersection = actual_words & expected_words
        union = actual_words | expected_words
        jaccard = len(intersection) / len(union) if union else 0.0

        return ScoreResult(score=jaccard, exact_match=False)

    def aggregate(self, results: list[ScoreResult]) -> float:
        if not results:
            return 0.0
        return sum(r.score for r in results) / len(results)
