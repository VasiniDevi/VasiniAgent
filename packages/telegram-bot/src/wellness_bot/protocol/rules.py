"""Deterministic rule engine for practice selection.

Redesigned: no blocking gates. All practices are always eligible
subject to time and readiness constraints. Distress level provides
soft guidance (stabilization boost) but never blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from wellness_bot.protocol.types import (
    MaintainingCycle, Readiness, CautionLevel,
)

# Practice catalog v2 — all 30 practices
_CATALOG: list[dict] = [
    # Monitoring
    {"id": "M1", "cat": "monitoring", "dur_min": 5, "dur_max": 10, "rank": 8, "cycles": [],
     "min_readiness": "contemplation"},
    {"id": "M2", "cat": "monitoring", "dur_min": 2, "dur_max": 5, "rank": 10, "cycles": ["rumination", "worry"],
     "min_readiness": "contemplation"},
    {"id": "M3", "cat": "monitoring", "dur_min": 1, "dur_max": 1, "rank": 5, "cycles": [],
     "min_readiness": "precontemplation"},
    {"id": "M4", "cat": "monitoring", "dur_min": 1, "dur_max": 2, "rank": 3, "cycles": [],
     "min_readiness": "contemplation"},
    # Attention
    {"id": "A1", "cat": "attention", "dur_min": 10, "dur_max": 12, "rank": 20, "cycles": ["rumination", "worry", "symptom_fixation"],
     "min_readiness": "action"},
    {"id": "A2", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 15, "cycles": ["rumination", "worry"],
     "min_readiness": "contemplation"},
    {"id": "A3", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 16, "cycles": ["rumination", "worry", "self_criticism"],
     "min_readiness": "contemplation"},
    {"id": "A4", "cat": "attention", "dur_min": 2, "dur_max": 3, "rank": 17, "cycles": ["self_criticism", "rumination"],
     "min_readiness": "contemplation"},
    {"id": "A5", "cat": "attention", "dur_min": 2, "dur_max": 5, "rank": 18, "cycles": ["self_criticism", "rumination"],
     "min_readiness": "action"},
    {"id": "A6", "cat": "attention", "dur_min": 2, "dur_max": 3, "rank": 25, "cycles": ["symptom_fixation", "avoidance"],
     "min_readiness": "action"},
    # Cognitive
    {"id": "C1", "cat": "cognitive", "dur_min": 5, "dur_max": 10, "rank": 30, "cycles": ["avoidance", "perfectionism"],
     "min_readiness": "action"},
    {"id": "C2", "cat": "cognitive", "dur_min": 5, "dur_max": 7, "rank": 31, "cycles": ["worry"],
     "min_readiness": "action"},
    {"id": "C3", "cat": "cognitive", "dur_min": 10, "dur_max": 20, "rank": 35, "cycles": ["avoidance", "worry", "perfectionism"],
     "min_readiness": "action"},
    {"id": "C4", "cat": "cognitive", "dur_min": 5, "dur_max": 10, "rank": 29, "cycles": ["perfectionism", "self_criticism"],
     "min_readiness": "action"},
    {"id": "C5", "cat": "cognitive", "dur_min": 3, "dur_max": 5, "rank": 28, "cycles": ["self_criticism", "perfectionism"],
     "min_readiness": "contemplation"},
    {"id": "C6", "cat": "cognitive", "dur_min": 5, "dur_max": 7, "rank": 32, "cycles": ["self_criticism"],
     "min_readiness": "action"},
    # Behavioral
    {"id": "B1", "cat": "behavioral", "dur_min": 5, "dur_max": 10, "rank": 22, "cycles": ["avoidance", "rumination"],
     "min_readiness": "action"},
    {"id": "B2", "cat": "behavioral", "dur_min": 10, "dur_max": 20, "rank": 23, "cycles": ["avoidance"],
     "min_readiness": "action"},
    {"id": "B3", "cat": "behavioral", "dur_min": 10, "dur_max": 15, "rank": 24, "cycles": ["rumination"],
     "min_readiness": "action"},
    {"id": "B4", "cat": "behavioral", "dur_min": 5, "dur_max": 10, "rank": 26, "cycles": ["avoidance", "symptom_fixation"],
     "min_readiness": "action"},
    {"id": "B5", "cat": "behavioral", "dur_min": 5, "dur_max": 10, "rank": 27, "cycles": ["insomnia"],
     "min_readiness": "contemplation"},
    # Relapse prevention
    {"id": "R1", "cat": "relapse_prevention", "dur_min": 15, "dur_max": 20, "rank": 36, "cycles": [],
     "min_readiness": "maintenance"},
    {"id": "R2", "cat": "relapse_prevention", "dur_min": 10, "dur_max": 10, "rank": 37, "cycles": ["rumination", "worry"],
     "min_readiness": "maintenance"},
    {"id": "R3", "cat": "relapse_prevention", "dur_min": 10, "dur_max": 15, "rank": 38, "cycles": [],
     "min_readiness": "maintenance"},
    # Micro
    {"id": "U1", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 2, "cycles": [],
     "min_readiness": "precontemplation"},
    {"id": "U2", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 1, "cycles": [],
     "min_readiness": "precontemplation"},
    {"id": "U3", "cat": "micro", "dur_min": 1, "dur_max": 2, "rank": 4, "cycles": ["rumination", "worry"],
     "min_readiness": "precontemplation"},
    {"id": "U4", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 6, "cycles": ["rumination"],
     "min_readiness": "precontemplation"},
    {"id": "U5", "cat": "micro", "dur_min": 1, "dur_max": 1, "rank": 7, "cycles": ["self_criticism"],
     "min_readiness": "precontemplation"},
    {"id": "U6", "cat": "micro", "dur_min": 1, "dur_max": 2, "rank": 9, "cycles": ["avoidance", "rumination"],
     "min_readiness": "precontemplation"},
]

# Updated first-line mappings (per design doc Section 2.1)
_FIRST_LINE: dict[str, list[str]] = {
    "rumination": ["A2", "A3", "M2"],
    "worry": ["A2", "A3", "C2"],
    "avoidance": ["C3", "B1", "B2", "B4"],
    "perfectionism": ["C4", "C5", "C3"],
    "self_criticism": ["C5", "A3", "A4"],
    "symptom_fixation": ["A6", "A1", "A3"],
    "insomnia": ["B5", "A2"],
}

_SECOND_LINE: dict[str, list[str]] = {
    "rumination": ["A1", "B1", "B3", "A4", "A5"],
    "worry": ["A1", "C3", "U3"],
    "avoidance": ["C1", "A6"],
    "perfectionism": ["M1", "M2"],
    "self_criticism": ["C1", "A5", "C6"],
    "symptom_fixation": ["C2", "B4"],
    "insomnia": ["A3", "C2"],
}

_READINESS_ORDER = ["precontemplation", "contemplation", "action", "maintenance"]

# Universal practices (always appropriate)
_UNIVERSAL = {"M3", "M4", "U1", "U2"}

# Stabilization practices (boosted at high distress)
_STABILIZATION = {"U1", "U2", "U3", "U4", "U5", "U6", "A3", "A2"}


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
        caution: CautionLevel = CautionLevel.NONE,
    ) -> list[dict]:
        """Filter practices by time and readiness only. No blocking gates."""
        readiness_idx = _READINESS_ORDER.index(readiness.value)
        eligible = []
        for p in _CATALOG:
            # Time gate (only hard filter remaining)
            if p["dur_min"] > time_budget:
                continue
            # Readiness gate
            p_readiness_idx = _READINESS_ORDER.index(p["min_readiness"])
            if readiness_idx < p_readiness_idx:
                continue
            # Precontemplation: only universal and micro practices
            if readiness == Readiness.PRECONTEMPLATION and p["id"] not in _UNIVERSAL:
                if p["cat"] != "micro":
                    continue
            eligible.append(p)
        return eligible

    def select(
        self,
        distress: int,
        cycle: MaintainingCycle,
        time_budget: int,
        readiness: Readiness,
        caution: CautionLevel = CautionLevel.NONE,
        technique_history: dict | None = None,
    ) -> SelectionResult:
        """Full selection pipeline — no blocking, soft guidance only."""
        technique_history = technique_history or {}

        # Step 1: filter by time and readiness
        eligible = self.get_eligible(distress, cycle, time_budget, readiness, caution)

        first_line = _FIRST_LINE.get(cycle.value, [])
        second_line = _SECOND_LINE.get(cycle.value, [])

        scored: list[PracticeCandidate] = []
        for p in eligible:
            pid = p["id"]
            # Cycle match scoring
            if pid in first_line:
                cycle_match = 1.0
            elif pid in second_line:
                cycle_match = 0.5
            elif not p["cycles"] or pid in _UNIVERSAL:  # universal
                cycle_match = 0.3
            else:
                cycle_match = 0.0

            # History-based scoring
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

            # Soft guidance: stabilization boost at high distress
            if distress >= 8 and pid in _STABILIZATION:
                raw += 0.3

            score = max(0.0, min(1.0, raw))

            scored.append(PracticeCandidate(
                practice_id=pid,
                score=score,
                priority_rank=p["rank"],
            ))

        # Sort by score desc, then priority_rank asc (tiebreaker)
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
