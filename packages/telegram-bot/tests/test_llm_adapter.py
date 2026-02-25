# tests/test_llm_adapter.py
"""Tests for LLMAdapter — contract-bound generation with validation."""
import pytest
from dataclasses import dataclass, field
from unittest.mock import AsyncMock

from wellness_bot.protocol.types import LLMContract, RiskLevel
from wellness_bot.protocol.llm_adapter import (
    LLMAdapter,
    ResponseValidator,
    CircuitBreaker,
    STATE_FALLBACKS,
    DEFAULT_FALLBACK,
)
from wellness_bot.protocol.style_validator import (
    StyleValidationInput,
    validate_style,
    CheckResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class MockLLMResponse:
    content: str
    model: str = "claude-sonnet"
    usage: dict = field(default_factory=dict)


def _make_contract(**overrides) -> LLMContract:
    defaults = dict(
        dialogue_state="PRACTICE",
        generation_task="Guide the user through a breathing exercise.",
        instruction="Keep it short and warm.",
        persona_summary="Warm CBT coach.",
        user_summary="User feels anxious today.",
        recent_messages=[],
        max_messages=2,
        max_chars_per_message=500,
        language="ru",
        must_include=[],
        must_not=[],
        ui_mode="text",
    )
    defaults.update(overrides)
    return LLMContract(**defaults)


# A "good" Russian response that passes both contract and style validation.
GOOD_RESPONSE = (
    "\u041f\u043e\u043d\u0438\u043c\u0430\u044e, \u0447\u0442\u043e \u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u043f\u0440\u043e\u0441\u0442\u043e. "
    "\u0414\u0430\u0432\u0430\u0439\u0442\u0435 \u0441\u0434\u0435\u043b\u0430\u0435\u043c \u043f\u0440\u043e\u0441\u0442\u043e\u0435 \u0443\u043f\u0440\u0430\u0436\u043d\u0435\u043d\u0438\u0435: \u0441\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0433\u043b\u0443\u0431\u043e\u043a\u0438\u0439 \u0432\u0434\u043e\u0445 \u043d\u0430 4 \u0441\u0447\u0451\u0442\u0430. "
    "\u0413\u043e\u0442\u043e\u0432\u044b \u043f\u043e\u043f\u0440\u043e\u0431\u043e\u0432\u0430\u0442\u044c?"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def adapter(mock_llm):
    return LLMAdapter(llm_provider=mock_llm, max_repeat_count=2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeneratesValidResponse:
    async def test_generates_valid_response(self, adapter, mock_llm):
        """When LLM returns a well-formed response, it passes through."""
        mock_llm.chat.return_value = MockLLMResponse(content=GOOD_RESPONSE)
        contract = _make_contract()

        result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)

        assert result == GOOD_RESPONSE
        mock_llm.chat.assert_called_once()


class TestCircuitBreakerTriggers:
    async def test_circuit_breaker_triggers(self, mock_llm):
        """After 3 failures within window, adapter returns state fallback."""
        adapter = LLMAdapter(llm_provider=mock_llm, max_repeat_count=2)
        mock_llm.chat.side_effect = RuntimeError("LLM down")
        contract = _make_contract(dialogue_state="INTAKE")

        # Each generate call will fail both attempts -> record failures
        # We need 3 failures to trip the breaker.
        # First call: 2 attempts = 2 failures recorded
        result1 = await adapter.generate(contract, risk_level=RiskLevel.SAFE)
        assert result1 == STATE_FALLBACKS["INTAKE"]

        # Second call: 2 more attempts would push to 4, but breaker opens at 3
        result2 = await adapter.generate(contract, risk_level=RiskLevel.SAFE)
        assert result2 == STATE_FALLBACKS["INTAKE"]

        # Third call: breaker is open, no LLM call made
        mock_llm.chat.reset_mock()
        result3 = await adapter.generate(contract, risk_level=RiskLevel.SAFE)
        assert result3 == STATE_FALLBACKS["INTAKE"]
        # LLM should NOT have been called because breaker is open
        mock_llm.chat.assert_not_called()


class TestMustIncludeValidationFails:
    async def test_must_include_validation_fails(self, adapter, mock_llm):
        """Response missing required phrase → retry → fallback."""
        # Response is good style-wise but missing required phrase
        missing_phrase_response = GOOD_RESPONSE
        mock_llm.chat.return_value = MockLLMResponse(content=missing_phrase_response)

        contract = _make_contract(must_include=["\u0434\u044b\u0445\u0430\u043d\u0438\u0435"])

        result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)

        # Must have been called twice (original + retry), then fallback
        assert mock_llm.chat.call_count == 2
        assert result == STATE_FALLBACKS["PRACTICE"]


class TestBannedContentUsesFallbackNoRetry:
    async def test_banned_content_uses_fallback_no_retry(self, adapter, mock_llm):
        """Critical failure (banned content) → immediate fallback, no retry."""
        banned_response = (
            "\u041f\u043e\u043d\u0438\u043c\u0430\u044e. \u0423 \u0432\u0430\u0441 \u0434\u0435\u043f\u0440\u0435\u0441\u0441\u0438\u044f, \u044d\u0442\u043e \u0442\u044f\u0436\u0435\u043b\u043e. "
            "\u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0433\u043b\u0443\u0431\u043e\u043a\u0438\u0439 \u0432\u0434\u043e\u0445. \u0413\u043e\u0442\u043e\u0432\u044b?"
        )
        mock_llm.chat.return_value = MockLLMResponse(content=banned_response)
        contract = _make_contract()

        result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)

        # Only one LLM call — no retry on critical failure
        assert mock_llm.chat.call_count == 1
        assert result == STATE_FALLBACKS["PRACTICE"]


class TestStyleValidationIntegration:
    async def test_style_validation_integration(self, adapter, mock_llm):
        """Style validator sarcasm gate triggers in elevated risk."""
        sarcastic_response = (
            "\u041d\u0443 \u0434\u0430, \u043a\u043e\u043d\u0435\u0447\u043d\u043e, \u0432\u0441\u0451 \u0443\u0436\u0430\u0441\u043d\u043e. "
            "\u041f\u043e\u043d\u0438\u043c\u0430\u044e, \u044d\u0442\u043e \u0442\u044f\u0436\u0435\u043b\u043e. "
            "\u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u043f\u0430\u0443\u0437\u0443. \u0413\u043e\u0442\u043e\u0432\u044b?"
        )
        mock_llm.chat.return_value = MockLLMResponse(content=sarcastic_response)
        contract = _make_contract()

        # Elevated risk + sarcasm → critical failure "no_playful_high_risk"
        result = await adapter.generate(
            contract,
            risk_level=RiskLevel.CAUTION_ELEVATED,
            user_tone_playful=False,
        )

        assert mock_llm.chat.call_count == 1  # no retry on critical
        assert result == STATE_FALLBACKS["PRACTICE"]


class TestRetryOnNonCriticalFailure:
    async def test_retry_on_non_critical_failure(self, adapter, mock_llm):
        """Non-critical failure on first attempt → retry succeeds."""
        # First response: too long (non-critical)
        too_long = "\u041f\u043e\u043d\u0438\u043c\u0430\u044e. " * 200 + "\u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0432\u0434\u043e\u0445. \u0413\u043e\u0442\u043e\u0432\u044b?"
        mock_llm.chat.side_effect = [
            MockLLMResponse(content=too_long),
            MockLLMResponse(content=GOOD_RESPONSE),
        ]
        contract = _make_contract()

        result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)

        assert mock_llm.chat.call_count == 2
        assert result == GOOD_RESPONSE


class TestFallbackPerState:
    async def test_fallback_per_state(self, mock_llm):
        """Different dialogue states produce different fallback texts."""
        mock_llm.chat.side_effect = RuntimeError("down")
        adapter = LLMAdapter(llm_provider=mock_llm, max_repeat_count=2)

        for state, expected in STATE_FALLBACKS.items():
            # Reset breaker between states
            adapter._breaker.reset()
            contract = _make_contract(dialogue_state=state)
            result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)
            assert result == expected, f"Fallback mismatch for state {state}"

    async def test_unknown_state_uses_default_fallback(self, mock_llm):
        """Unknown dialogue state falls back to DEFAULT_FALLBACK."""
        mock_llm.chat.side_effect = RuntimeError("down")
        adapter = LLMAdapter(llm_provider=mock_llm, max_repeat_count=2)
        contract = _make_contract(dialogue_state="UNKNOWN_STATE")

        result = await adapter.generate(contract, risk_level=RiskLevel.SAFE)
        assert result == DEFAULT_FALLBACK


# ---------------------------------------------------------------------------
# Unit tests for ResponseValidator alone
# ---------------------------------------------------------------------------


class TestResponseValidator:
    def test_all_checks_pass(self):
        validator = ResponseValidator()
        contract = _make_contract()
        results = validator.validate(GOOD_RESPONSE, contract)
        assert all(r.passed for r in results), [r for r in results if not r.passed]

    def test_length_check_fails(self):
        validator = ResponseValidator()
        contract = _make_contract(max_chars_per_message=10)
        results = validator.validate(GOOD_RESPONSE, contract)
        length_result = next(r for r in results if r.code == "length")
        assert not length_result.passed

    def test_must_include_check_fails(self):
        validator = ResponseValidator()
        contract = _make_contract(must_include=["\u043d\u0435\u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0435_\u0441\u043b\u043e\u0432\u043e"])
        results = validator.validate(GOOD_RESPONSE, contract)
        mi_result = next(r for r in results if r.code == "must_include")
        assert not mi_result.passed

    def test_must_not_check_fails(self):
        validator = ResponseValidator()
        contract = _make_contract(must_not=["\u043f\u043e\u043d\u0438\u043c\u0430\u044e"])
        results = validator.validate(GOOD_RESPONSE, contract)
        mn_result = next(r for r in results if r.code == "must_not")
        assert not mn_result.passed

    def test_no_diagnosis_flags_diagnostic_language(self):
        validator = ResponseValidator()
        contract = _make_contract()
        text = "\u0423 \u0432\u0430\u0441 \u0434\u0435\u043f\u0440\u0435\u0441\u0441\u0438\u044f, \u043d\u043e \u044d\u0442\u043e \u043b\u0435\u0447\u0438\u0442\u0441\u044f."
        results = validator.validate(text, contract)
        diag = next(r for r in results if r.code == "no_diagnosis")
        assert not diag.passed
        assert diag.critical

    def test_safety_lexicon_flags_harmful(self):
        validator = ResponseValidator()
        contract = _make_contract()
        text = "\u0412\u043e\u0442 \u043a\u0430\u043a \u043f\u0440\u0438\u0447\u0438\u043d\u0438\u0442\u044c \u0441\u0435\u0431\u0435 \u0432\u0440\u0435\u0434."
        results = validator.validate(text, contract)
        sl = next(r for r in results if r.code == "safety_lexicon")
        assert not sl.passed
        assert sl.critical

    def test_language_match_english_in_ru_contract(self):
        validator = ResponseValidator()
        contract = _make_contract(language="ru")
        text = "This is entirely in English, no Cyrillic at all."
        results = validator.validate(text, contract)
        lang = next(r for r in results if r.code == "language_match")
        assert not lang.passed


# ---------------------------------------------------------------------------
# Unit tests for CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(threshold=3, window_seconds=60.0)
        assert not cb.is_open()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(threshold=3, window_seconds=60.0)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open()
        cb.record_failure()
        assert cb.is_open()

    def test_reset_closes(self):
        cb = CircuitBreaker(threshold=3, window_seconds=60.0)
        for _ in range(5):
            cb.record_failure()
        assert cb.is_open()
        cb.reset()
        assert not cb.is_open()


# ---------------------------------------------------------------------------
# Unit tests for StyleValidator
# ---------------------------------------------------------------------------


class TestStyleValidator:
    def test_good_response_passes(self):
        inp = StyleValidationInput(
            text=GOOD_RESPONSE,
            risk_level=RiskLevel.SAFE,
            user_tone_playful=False,
            long_form_requested=False,
        )
        results = validate_style(inp)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0, failed

    def test_banned_content_detected(self):
        inp = StyleValidationInput(
            text="\u041f\u043e\u043d\u0438\u043c\u0430\u044e. \u0423 \u0432\u0430\u0441 \u0434\u0435\u043f\u0440\u0435\u0441\u0441\u0438\u044f. \u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u0432\u0434\u043e\u0445. \u0413\u043e\u0442\u043e\u0432\u044b?",
            risk_level=RiskLevel.SAFE,
            user_tone_playful=False,
            long_form_requested=False,
        )
        results = validate_style(inp)
        banned = next(r for r in results if r.code == "no_banned_content")
        assert not banned.passed

    def test_sarcasm_blocked_in_crisis(self):
        inp = StyleValidationInput(
            text="\u041d\u0443 \u0434\u0430, \u043a\u043e\u043d\u0435\u0447\u043d\u043e, \u0432\u0441\u0451 \u043f\u043b\u043e\u0445\u043e. \u041f\u043e\u043d\u0438\u043c\u0430\u044e. \u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u043f\u0430\u0443\u0437\u0443. \u0413\u043e\u0442\u043e\u0432\u044b?",
            risk_level=RiskLevel.CRISIS,
            user_tone_playful=False,
            long_form_requested=False,
        )
        results = validate_style(inp)
        playful = next(r for r in results if r.code == "no_playful_high_risk")
        assert not playful.passed

    def test_sarcasm_allowed_when_safe_and_playful(self):
        inp = StyleValidationInput(
            text="\u041d\u0443 \u0434\u0430, \u043a\u043e\u043d\u0435\u0447\u043d\u043e, \u0436\u0438\u0437\u043d\u044c \u043f\u0440\u0435\u043a\u0440\u0430\u0441\u043d\u0430! \u041f\u043e\u043d\u0438\u043c\u0430\u044e. \u0421\u0434\u0435\u043b\u0430\u0439\u0442\u0435 \u043f\u0430\u0443\u0437\u0443. \u0413\u043e\u0442\u043e\u0432\u044b?",
            risk_level=RiskLevel.SAFE,
            user_tone_playful=True,
            long_form_requested=False,
        )
        results = validate_style(inp)
        sarcasm = next(r for r in results if r.code == "sarcasm_gate")
        assert sarcasm.passed
