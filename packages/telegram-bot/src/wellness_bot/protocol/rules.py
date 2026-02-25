"""Deterministic rule engine for practice selection."""
from __future__ import annotations

from dataclasses import dataclass
from wellness_bot.protocol.types import (
    MaintainingCycle, Readiness, CautionLevel,
)

# Practice catalog v1 — defined in code, mirrors YAML
_CATALOG: list[dict] = [
    {"id": "M2", "cat": "monitoring", "dur_min": 2, "dur_max": 5, "rank": 10, "cycles": ["rumination", "worry"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "M3", "cat": "monitoring", "dur_min": 1, "dur_max": 1, "rank": 5, "cycles": [],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "precontemplation"},
    {"id": "A1", "cat": "attention", "dur_min": 10, "dur_max": 12, "rank": 20, "cycles": ["rumination", "worry", "symptom_fixation"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "A2", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 15, "cycles": ["rumination", "worry"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "A3", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 16, "cycles": ["rumination", "worry", "self_criticism"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "A6", "cat": "attention", "dur_min": 2, "dur_max": 3, "rank": 25, "cycles": ["symptom_fixation", "avoidance"],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "C1", "cat": "cognitive", "dur_min": 5, "dur_max": 10, "rank": 30, "cycles": ["avoidance", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": True, "min_readiness": "action"},
    {"id": "C2", "cat": "cognitive", "dur_min": 5, "dur_max": 7, "rank": 31, "cycles": ["worry"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "C3", "cat": "cognitive", "dur_min": 10, "dur_max": 20, "rank": 35, "cycles": ["avoidance", "worry", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": True, "min_readiness": "action"},
    {"id": "C5", "cat": "cognitive", "dur_min": 3, "dur_max": 5, "rank": 28, "cycles": ["self_criticism", "perfectionism"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "contemplation"},
    {"id": "B1", "cat": "behavioral", "dur_min": 5, "dur_max": 10, "rank": 22, "cycles": ["avoidance", "rumination"],
     "blocked_distress": 8, "blocked_caution_elevated": False, "min_readiness": "action"},
    {"id": "U2", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 1, "cycles": [],
     "blocked_distress": None, "blocked_caution_elevated": False, "min_readiness": "precontemplation"},
]

# First-line mappings
_FIRST_LINE: dict[str, list[str]] = {
    "rumination": ["A2", "A3", "M2"],
    "worry": ["A2", "A3", "C2"],
    "avoidance": ["C3", "B1"],
    "perfectionism": ["C5", "C3"],
    "self_criticism": ["C5", "A3"],
    "symptom_fixation": ["A6", "A1", "A3"],
}

_SECOND_LINE: dict[str, list[str]] = {
    "rumination": ["A1", "B1"],
    "worry": ["A1", "C3"],
    "avoidance": ["C1"],
    "perfectionism": ["M2"],
    "self_criticism": ["C1"],
    "symptom_fixation": ["C2"],
}

_READINESS_ORDER = ["precontemplation", "contemplation", "action", "maintenance"]


@dataclass
class PracticeCandidate:
    practice_id: str
    score: float
    priority_rank: int


@dataclass
class SelectionResult:
    primary: PracticeCandidate
    backup: PracticeCandidate | None


class RuleEngine:
    def get_eligible(
        self,
        distress: int,
        cycle: MaintainingCycle,
        time_budget: int,
        readiness: Readiness,
        caution: CautionLevel,
    ) -> list[dict]:
        """Step 2: Hard filter — return eligible practices."""
        readiness_idx = _READINESS_ORDER.index(readiness.value)
        eligible = []
        for p in _CATALOG:
            # Distress gate
            if p["blocked_distress"] is not None and distress >= p["blocked_distress"]:
                continue
            # Caution gate
            if caution == CautionLevel.ELEVATED and p["blocked_caution_elevated"]:
                continue
            # Time gate
            if p["dur_min"] > time_budget:
                continue
            # Readiness gate
            p_readiness_idx = _READINESS_ORDER.index(p["min_readiness"])
            if readiness_idx < p_readiness_idx:
                continue
            # Precontemplation: only M3 and U2
            if readiness == Readiness.PRECONTEMPLATION and p["id"] not in ("M3", "U2"):
                continue
            eligible.append(p)
        return eligible

    def select(
        self,
        distress: int,
        cycle: MaintainingCycle,
        time_budget: int,
        readiness: Readiness,
        caution: CautionLevel,
        technique_history: dict,
    ) -> SelectionResult:
        """Full 7-step selection pipeline."""
        # Step 2: hard filter
        eligible = self.get_eligible(distress, cycle, time_budget, readiness, caution)

        first_line = _FIRST_LINE.get(cycle.value, [])
        second_line = _SECOND_LINE.get(cycle.value, [])

        scored: list[PracticeCandidate] = []
        for p in eligible:
            pid = p["id"]
            # Step 3: cycle match
            if pid in first_line:
                cycle_match = 1.0
            elif pid in second_line:
                cycle_match = 0.5
            elif not p["cycles"]:  # universal (M3, U2)
                cycle_match = 0.3
            else:
                cycle_match = 0.0

            # Step 4: score
            history = technique_history.get(pid, {})
            times_used = history.get("times_used", 0)
            avg_eff = history.get("avg_effectiveness", 5.0)

            effectiveness = avg_eff / 10.0
            repetition = 1.0 if times_used >= 3 else (0.5 if times_used >= 1 else 0.0)
            novelty = 1.0 if times_used == 0 else (0.5 if times_used < 3 else 0.0)

            raw = (
                cycle_match * 0.4
                + effectiveness * 0.3
                - repetition * 0.2
                + novelty * 0.1
            )
            score = max(0.0, min(1.0, raw))

            scored.append(PracticeCandidate(
                practice_id=pid,
                score=score,
                priority_rank=p["rank"],
            ))

        # Step 5: sort by score desc, then priority_rank asc (tiebreaker)
        scored.sort(key=lambda c: (-c.score, c.priority_rank))

        if not scored:
            # Fallback: U2 is always safe
            return SelectionResult(
                primary=PracticeCandidate("U2", 0.1, 1),
                backup=None,
            )

        primary = scored[0]
        backup = scored[1] if len(scored) > 1 else None

        return SelectionResult(primary=primary, backup=backup)
