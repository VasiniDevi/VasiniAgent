"""Tests for deterministic multilingual safety gate."""

import pytest

from wellness_bot.coaching.safety_gate import SafetyGate, SafetyGateResult


@pytest.fixture
def gate() -> SafetyGate:
    return SafetyGate()


class TestSafetyGateResult:
    """SafetyGateResult dataclass tests."""

    def test_result_has_detector_field(self, gate: SafetyGate) -> None:
        result = gate.check("hello")
        assert result.detector == "keyword_regex"

    def test_result_default_signals_empty(self) -> None:
        result = SafetyGateResult(
            risk_level="safe",
            safety_action="pass",
        )
        assert result.signals == []
        assert result.detector == "keyword_regex"


class TestSafeRussianMessage:
    """Safe Russian messages should pass through."""

    def test_safe_russian_greeting(self, gate: SafetyGate) -> None:
        result = gate.check("Привет, как дела?")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"
        assert result.signals == []

    def test_safe_russian_daily(self, gate: SafetyGate) -> None:
        result = gate.check("Сегодня хороший день, я гулял в парке")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"


class TestCrisisRussianSelfHarm:
    """Russian self-harm phrases must trigger crisis."""

    def test_pokonchit_s_soboj(self, gate: SafetyGate) -> None:
        result = gate.check("хочу покончить с собой")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "self_harm_ru" in result.signals

    def test_suicid(self, gate: SafetyGate) -> None:
        result = gate.check("думаю о суициде")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "suicide_ru" in result.signals

    def test_hochu_umeret(self, gate: SafetyGate) -> None:
        result = gate.check("я хочу умереть")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_ru" in result.signals

    def test_hotela_ne_zhit(self, gate: SafetyGate) -> None:
        result = gate.check("я хотела не жить")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_ru" in result.signals

    def test_povesitsya(self, gate: SafetyGate) -> None:
        result = gate.check("хочу повеситься")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "method_ru" in result.signals

    def test_porezat_veny(self, gate: SafetyGate) -> None:
        result = gate.check("порезать вены")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "method_ru" in result.signals

    def test_ubit_sebya(self, gate: SafetyGate) -> None:
        result = gate.check("хочу убить себя")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "self_harm_direct_ru" in result.signals

    def test_hopelessness_ru(self, gate: SafetyGate) -> None:
        result = gate.check("не вижу смысла жить")
        assert result.risk_level == "high"
        assert result.safety_action == "flag_review"
        assert "hopelessness_ru" in result.signals


class TestCrisisEnglishSelfHarm:
    """English self-harm phrases must trigger crisis."""

    def test_kill_myself(self, gate: SafetyGate) -> None:
        result = gate.check("I want to kill myself")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "self_harm_en" in result.signals

    def test_want_to_die(self, gate: SafetyGate) -> None:
        result = gate.check("I want to die")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_en" in result.signals

    def test_going_to_end_it(self, gate: SafetyGate) -> None:
        result = gate.check("I'm going to end it")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_en" in result.signals

    def test_going_to_end_my_life(self, gate: SafetyGate) -> None:
        result = gate.check("I'm going to end my life")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_en" in result.signals

    def test_suicidal(self, gate: SafetyGate) -> None:
        result = gate.check("I feel suicidal")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "suicide_en" in result.signals

    def test_suicide(self, gate: SafetyGate) -> None:
        result = gate.check("thinking about suicide")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "suicide_en" in result.signals

    def test_method_en(self, gate: SafetyGate) -> None:
        result = gate.check("I want to hang myself")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "method_en" in result.signals

    def test_hopelessness_en(self, gate: SafetyGate) -> None:
        result = gate.check("there is no reason to live")
        assert result.risk_level == "high"
        assert result.safety_action == "flag_review"
        assert "hopelessness_en" in result.signals


class TestCrisisSpanish:
    """Spanish crisis phrases must trigger crisis."""

    def test_suicidarme(self, gate: SafetyGate) -> None:
        result = gate.check("quiero suicidarme")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "suicide_es" in result.signals

    def test_quiero_morir(self, gate: SafetyGate) -> None:
        result = gate.check("quiero morir")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_es" in result.signals

    def test_quiero_morirme(self, gate: SafetyGate) -> None:
        result = gate.check("quiero morirme")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "death_wish_es" in result.signals

    def test_matarme(self, gate: SafetyGate) -> None:
        result = gate.check("voy a matarme")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "self_harm_es" in result.signals


class TestViolenceDetected:
    """Violence towards others must trigger crisis."""

    def test_violence_ru(self, gate: SafetyGate) -> None:
        result = gate.check("хочу убить его")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "violence_ru" in result.signals

    def test_violence_en(self, gate: SafetyGate) -> None:
        result = gate.check("I want to kill someone")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "violence_en" in result.signals

    def test_violence_en_harm(self, gate: SafetyGate) -> None:
        result = gate.check("I want to hurt them")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert "violence_en" in result.signals


class TestSafeEnglishMessage:
    """Safe English messages should pass through."""

    def test_safe_english_greeting(self, gate: SafetyGate) -> None:
        result = gate.check("Hello, how are you?")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"
        assert result.signals == []

    def test_safe_english_daily(self, gate: SafetyGate) -> None:
        result = gate.check("I had a great day at work today")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"


class TestSafeMixedLanguage:
    """Mixed safe language should pass through."""

    def test_safe_mixed(self, gate: SafetyGate) -> None:
        result = gate.check("Привет! Today was a good day, muy bueno!")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"
        assert result.signals == []


class TestEmptyMessage:
    """Empty messages should be safe."""

    def test_empty_string(self, gate: SafetyGate) -> None:
        result = gate.check("")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"
        assert result.signals == []

    def test_whitespace_only(self, gate: SafetyGate) -> None:
        result = gate.check("   ")
        assert result.risk_level == "safe"
        assert result.safety_action == "pass"


class TestMultipleSignals:
    """Messages with multiple signals should aggregate correctly."""

    def test_multiple_crisis_signals(self, gate: SafetyGate) -> None:
        result = gate.check("думаю о суициде, хочу покончить с собой")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
        assert len(result.signals) >= 2

    def test_crisis_overrides_high(self, gate: SafetyGate) -> None:
        """If both crisis and high signals exist, crisis wins."""
        result = gate.check("не вижу смысла жить, хочу покончить с собой")
        assert result.risk_level == "crisis"
        assert result.safety_action == "crisis_protocol"
