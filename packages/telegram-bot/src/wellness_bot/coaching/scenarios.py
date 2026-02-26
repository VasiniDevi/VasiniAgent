"""Scenario protocol definitions — 6 common clinical presentations.

Each scenario defines phases with primary/secondary practices and
psychoeducation keys. These are used as LLM guidance in the knowledge
base system prompt, not as rigid step-by-step programs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioPhase:
    """A phase within a scenario protocol."""

    name: str
    sessions: tuple[int, int]  # (start, end) session range
    primary_practices: list[str]
    secondary_practices: list[str]
    psychoeducation_key: str | None
    goal: str


@dataclass(frozen=True)
class ScenarioProtocol:
    """A scenario protocol for a common clinical presentation."""

    id: str
    name_ru: str
    maintaining_cycles: list[str]
    phases: list[ScenarioPhase]
    stall_threshold: int  # sessions without progress before switching approach


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, ScenarioProtocol] = {
    "GAD": ScenarioProtocol(
        id="GAD",
        name_ru="Генерализованная тревога",
        maintaining_cycles=["worry", "avoidance"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["A2", "A3", "U2"],
                secondary_practices=["U1", "U3"],
                psychoeducation_key="worry_cycle",
                goal="Стабилизация через внимание и откладывание worry",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 8),
                primary_practices=["A1", "C2", "C3"],
                secondary_practices=["M1", "A4", "A5"],
                psychoeducation_key="metacognitive_model",
                goal="Развитие навыков: ATT, реструктуризация worry, экспозиция",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(9, 12),
                primary_practices=["R1", "R2"],
                secondary_practices=["B2", "R3"],
                psychoeducation_key=None,
                goal="Закрепление навыков и профилактика рецидива",
            ),
        ],
        stall_threshold=4,
    ),
    "RUMINATION": ScenarioProtocol(
        id="RUMINATION",
        name_ru="Руминация / депрессивное мышление",
        maintaining_cycles=["rumination", "self_criticism"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["A2", "A3", "M4"],
                secondary_practices=["U4", "U1"],
                psychoeducation_key="rumination_cycle",
                goal="Замечание руминации и переключение через DM/откладывание",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 8),
                primary_practices=["A1", "M2", "B1"],
                secondary_practices=["A4", "A5", "C5", "B3"],
                psychoeducation_key="process_vs_content",
                goal="ATT, поведенческая активация, децентрация",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(9, 12),
                primary_practices=["R1", "R2"],
                secondary_practices=["R3", "M1"],
                psychoeducation_key=None,
                goal="Закрепление и план на случай возврата руминации",
            ),
        ],
        stall_threshold=4,
    ),
    "PROCRASTINATION": ScenarioProtocol(
        id="PROCRASTINATION",
        name_ru="Прокрастинация / избегание",
        maintaining_cycles=["avoidance", "perfectionism"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["U6", "B1", "C5"],
                secondary_practices=["U1", "A3"],
                psychoeducation_key="avoidance_cycle",
                goal="Микро-действия и разбор перфекционистских ожиданий",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 8),
                primary_practices=["C3", "C4", "B3"],
                secondary_practices=["B2", "M1", "A4"],
                psychoeducation_key="perfectionism_trap",
                goal="Экспозиция к несовершенству, решение проблем, диспут",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(9, 12),
                primary_practices=["R1", "R2"],
                secondary_practices=["R3"],
                psychoeducation_key=None,
                goal="Закрепление нового отношения к неидеальному результату",
            ),
        ],
        stall_threshold=5,
    ),
    "SOCIAL_ANXIETY": ScenarioProtocol(
        id="SOCIAL_ANXIETY",
        name_ru="Социальная тревога",
        maintaining_cycles=["avoidance", "self_criticism", "symptom_fixation"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["A3", "A6", "U2"],
                secondary_practices=["U1", "U5"],
                psychoeducation_key="safety_behaviors",
                goal="Управление вниманием и снижение фиксации на симптомах",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 10),
                primary_practices=["B2", "B4", "C3"],
                secondary_practices=["C1", "A4", "A5"],
                psychoeducation_key="avoidance_maintains_anxiety",
                goal="Экспозиция, отказ от безопасного поведения, эксперименты",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(11, 14),
                primary_practices=["R1", "R2"],
                secondary_practices=["R3", "B2"],
                psychoeducation_key=None,
                goal="Закрепление и расширение экспозиции",
            ),
        ],
        stall_threshold=5,
    ),
    "LOW_MOOD": ScenarioProtocol(
        id="LOW_MOOD",
        name_ru="Сниженное настроение",
        maintaining_cycles=["rumination", "avoidance"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["B1", "U6", "M3"],
                secondary_practices=["U1", "A2"],
                psychoeducation_key="activity_mood_link",
                goal="Поведенческая активация и мониторинг настроения",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 8),
                primary_practices=["M1", "C1", "A1"],
                secondary_practices=["C5", "A4", "B3"],
                psychoeducation_key="cognitive_triad",
                goal="Дневник мыслей, реструктуризация, ATT",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(9, 12),
                primary_practices=["R1", "R2"],
                secondary_practices=["R3"],
                psychoeducation_key=None,
                goal="Закрепление и профилактика рецидива",
            ),
        ],
        stall_threshold=4,
    ),
    "INSOMNIA": ScenarioProtocol(
        id="INSOMNIA",
        name_ru="Бессонница",
        maintaining_cycles=["insomnia", "worry"],
        phases=[
            ScenarioPhase(
                name="stabilization",
                sessions=(1, 3),
                primary_practices=["B5", "A2", "U2"],
                secondary_practices=["U1", "U3"],
                psychoeducation_key="sleep_hygiene_basics",
                goal="CBT-I основы: контроль стимулов, гигиена сна",
            ),
            ScenarioPhase(
                name="skill_building",
                sessions=(4, 8),
                primary_practices=["A3", "C2", "A1"],
                secondary_practices=["M4", "A4"],
                psychoeducation_key="worry_and_sleep",
                goal="Управление worry перед сном, DM, ATT",
            ),
            ScenarioPhase(
                name="consolidation",
                sessions=(9, 12),
                primary_practices=["R1", "R2"],
                secondary_practices=["R3", "B5"],
                psychoeducation_key=None,
                goal="Закрепление режима и навыков",
            ),
        ],
        stall_threshold=4,
    ),
}


class ScenarioMatcher:
    """Finds the best matching scenario based on emotional signals."""

    # Cycle → scenario mapping (primary cycle → scenario)
    _CYCLE_MAP: dict[str, str] = {
        "worry": "GAD",
        "rumination": "RUMINATION",
        "avoidance": "PROCRASTINATION",
        "perfectionism": "PROCRASTINATION",
        "self_criticism": "RUMINATION",
        "symptom_fixation": "SOCIAL_ANXIETY",
        "insomnia": "INSOMNIA",
    }

    def match(
        self,
        *,
        dominant_cycles: list[str] | None = None,
        mood: float | None = None,
        anxiety: float | None = None,
    ) -> ScenarioProtocol | None:
        """Find best matching scenario.

        Parameters
        ----------
        dominant_cycles:
            Maintaining cycles identified in the user, ordered by dominance.
        mood:
            Current mood score (0-10, lower = worse).
        anxiety:
            Current anxiety level (0-1).

        Returns
        -------
        ScenarioProtocol or None
            Best matching scenario, or None if no clear match.
        """
        if dominant_cycles:
            for cycle in dominant_cycles:
                scenario_id = self._CYCLE_MAP.get(cycle)
                if scenario_id:
                    return SCENARIOS[scenario_id]

        # Fallback heuristics
        if mood is not None and mood <= 3.0:
            return SCENARIOS["LOW_MOOD"]
        if anxiety is not None and anxiety >= 0.7:
            return SCENARIOS["GAD"]

        return None
