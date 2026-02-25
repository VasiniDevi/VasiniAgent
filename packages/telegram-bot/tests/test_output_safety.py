"""Tests for deterministic output safety check.

Runs AFTER LLM generates a response to catch unsafe content
(diagnosis, medication advice, pressure language) before delivery.
"""

import pytest

from wellness_bot.coaching.output_safety import OutputSafetyCheck, SafetyCheckResult


@pytest.fixture
def checker() -> OutputSafetyCheck:
    return OutputSafetyCheck()


class TestSafetyCheckResultDefaults:
    """SafetyCheckResult dataclass defaults."""

    def test_approved_default(self) -> None:
        result = SafetyCheckResult(approved=True)
        assert result.approved is True
        assert result.reason == ""
        assert result.action == "pass"

    def test_not_approved_with_fields(self) -> None:
        result = SafetyCheckResult(
            approved=False, reason="diagnosis", action="rewrite"
        )
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"


class TestCleanMessagePasses:
    """Clean messages should be approved."""

    def test_clean_russian(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Попробуйте сегодня уделить 10 минут дыхательной практике."
        )
        assert result.approved is True
        assert result.reason == ""
        assert result.action == "pass"

    def test_clean_english(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Try spending 10 minutes on a breathing exercise today."
        )
        assert result.approved is True
        assert result.reason == ""
        assert result.action == "pass"

    def test_empty_string(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("")
        assert result.approved is True


class TestDiagnosisBlockedRussian:
    """Russian diagnosis patterns must be caught."""

    def test_u_vas_depressiya(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("У вас депрессия, вам нужна помощь.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_u_tebya_trevozhnoe(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "У тебя тревожное расстройство, это серьёзно."
        )
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_vash_diagnoz(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Ваш диагноз требует внимания специалиста.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_u_vas_ptsr(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("У вас ПТСР, нужно обратиться к врачу.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"


class TestMedicationBlockedRussian:
    """Russian medication patterns must be caught."""

    def test_antidepressant(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Антидепрессанты помогут вам справиться.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_tranquilizer(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Транквилизаторы снимут напряжение.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_prinyat_tabletki(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Попробуйте принять таблетки перед сном.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_naznachit_lekarstva(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Врач может назначить лекарства.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"


class TestPressureBlockedRussian:
    """Russian pressure patterns must be caught."""

    def test_obyazan_sdelaj(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Ты обязан сделай это прямо сейчас!")
        assert result.approved is False
        assert result.reason == "pressure"
        assert result.action == "rewrite"

    def test_dolzhen_nachni(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Ты должен начни заниматься спортом.")
        assert result.approved is False
        assert result.reason == "pressure"
        assert result.action == "rewrite"


class TestEnglishDiagnosisBlocked:
    """English diagnosis patterns must be caught."""

    def test_you_have_depression(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You have depression and need treatment.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_you_suffer_from_ptsd(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You suffer from PTSD.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_diagnosed_with_anxiety(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "You may be diagnosed with anxiety disorder."
        )
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"

    def test_clinical_depression(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("This looks like clinical depression.")
        assert result.approved is False
        assert result.reason == "diagnosis"
        assert result.action == "rewrite"


class TestEnglishMedicationBlocked:
    """English medication patterns must be caught."""

    def test_antidepressant_en(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("An antidepressant could help you.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_take_medication(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You should take medication for this.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_need_medication(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You need medication to feel better.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"

    def test_prescription(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("Get a prescription from your doctor.")
        assert result.approved is False
        assert result.reason == "medication"
        assert result.action == "rewrite"


class TestEnglishPressureBlocked:
    """English pressure patterns must be caught."""

    def test_you_must_do_this(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You must do this right now.")
        assert result.approved is False
        assert result.reason == "pressure"
        assert result.action == "rewrite"

    def test_you_have_to_start(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate("You have to start exercising.")
        assert result.approved is False
        assert result.reason == "pressure"
        assert result.action == "rewrite"


class TestSafeWellnessLanguagePasses:
    """Wellness-related but safe language should pass."""

    def test_mindfulness_suggestion(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Mindfulness practice can help you feel more grounded."
        )
        assert result.approved is True

    def test_breathing_exercise_ru(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Дыхательные упражнения помогают расслабиться."
        )
        assert result.approved is True

    def test_journaling_suggestion(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Consider journaling about your feelings today."
        )
        assert result.approved is True

    def test_gentle_encouragement(self, checker: OutputSafetyCheck) -> None:
        result = checker.validate(
            "Вы делаете отличную работу, продолжайте в том же духе."
        )
        assert result.approved is True
