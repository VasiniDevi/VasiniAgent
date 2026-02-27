# tests/test_safety_classifier.py
"""Tests for SafetyClassifier — soft levels, never blocking."""
import pytest
from unittest.mock import AsyncMock
from dataclasses import dataclass, field
from wellness_bot.protocol.safety import SafetyClassifier, SafetyResult
from wellness_bot.protocol.types import RiskLevel, SafetyLevel


@dataclass
class MockLLMResponse:
    content: str
    model: str = "claude-haiku"
    usage: dict = field(default_factory=dict)


@pytest.fixture
def classifier():
    return SafetyClassifier(classifier_version="1.0", policy_version="1.0")


class TestNeverBlocks:
    """Core principle: safety NEVER blocks practice access."""

    def test_safety_never_blocks_practice(self, classifier):
        """Safety should NEVER set block_practice=True."""
        result = classifier.check_hard_rules("У меня диагноз депрессия и мне нужна практика")
        # No hard rule match → None (caller uses GREEN default)
        assert result is None

    def test_diagnosis_mention_stays_green(self, classifier):
        """Mentioning a diagnosis should not trigger any safety level."""
        result = classifier.check_hard_rules("У меня ОКР, помоги с руминацией")
        assert result is None  # No pattern match → GREEN by default

    async def test_classify_diagnosis_stays_green(self, classifier):
        """Full classify: diagnosis mention should be GREEN."""
        result = await classifier.classify("У меня депрессия, помоги с практикой")
        assert result.safety_level == SafetyLevel.GREEN
        assert result.block_practice is False

    def test_red_result_still_does_not_block(self, classifier):
        """Even RED results must have block_practice=False."""
        result = classifier.check_hard_rules("хочу умереть")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED
        assert result.block_practice is False


class TestHardRules:
    def test_suicide_explicit_ru(self, classifier):
        result = classifier.check_hard_rules("хочу умереть")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED
        assert result.protocol_id == "S1"
        assert result.crisis_resources is not None

    def test_suicide_explicit_en(self, classifier):
        result = classifier.check_hard_rules("I want to kill myself")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED
        assert result.protocol_id == "S1"

    def test_self_harm(self, classifier):
        result = classifier.check_hard_rules("я режу себя каждый вечер")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED
        assert result.protocol_id == "S1"

    def test_violence(self, classifier):
        result = classifier.check_hard_rules("я убью его")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED
        assert result.protocol_id == "S2"

    def test_psychosis_is_yellow(self, classifier):
        """Psychosis signals → YELLOW (help + suggest specialist)."""
        result = classifier.check_hard_rules("голоса говорят мне что делать")
        assert result is not None
        assert result.safety_level == SafetyLevel.YELLOW
        assert result.protocol_id == "S3"
        assert result.specialist_suggestion is not None
        assert result.block_practice is False

    def test_domestic_violence_is_yellow(self, classifier):
        """DV signals → YELLOW (help + suggest specialist)."""
        result = classifier.check_hard_rules("муж бьёт меня")
        assert result is not None
        assert result.safety_level == SafetyLevel.YELLOW
        assert result.protocol_id == "S6"
        assert result.block_practice is False

    def test_safe_message(self, classifier):
        result = classifier.check_hard_rules("Сегодня хороший день, настроение 7")
        assert result is None

    def test_case_insensitive(self, classifier):
        result = classifier.check_hard_rules("ХОЧУ УМЕРЕТЬ")
        assert result is not None
        assert result.safety_level == SafetyLevel.RED


class TestClassify:
    async def test_hard_rules_bypass_llm(self, classifier):
        """Hard rules should return immediately without calling LLM."""
        result = await classifier.classify("хочу покончить с собой", context=[])
        assert result.safety_level == SafetyLevel.RED
        assert result.source == "rules"

    async def test_safe_message_without_llm(self, classifier):
        """Without LLM provider, safe messages should return GREEN."""
        result = await classifier.classify("привет, как дела", context=[])
        assert result.safety_level == SafetyLevel.GREEN
        assert result.block_practice is False


class TestLLMClassifier:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def classifier_with_llm(self, mock_llm):
        return SafetyClassifier(llm_provider=mock_llm)

    async def test_llm_red_high_confidence(self, classifier_with_llm, mock_llm):
        mock_llm.chat.return_value = MockLLMResponse(
            content='{"safety_level":"red","protocol":"S1","signals":["suicidal_ideation"],"confidence":0.9}',
        )
        result = await classifier_with_llm.classify("Я больше не могу так жить", context=[])
        assert result.safety_level == SafetyLevel.RED
        assert result.crisis_resources is not None
        assert result.block_practice is False

    async def test_llm_green_high_confidence(self, classifier_with_llm, mock_llm):
        mock_llm.chat.return_value = MockLLMResponse(
            content='{"safety_level":"green","protocol":null,"signals":[],"confidence":0.95}',
        )
        result = await classifier_with_llm.classify("Сегодня хорошо поспал", context=[])
        assert result.safety_level == SafetyLevel.GREEN
        assert result.block_practice is False

    async def test_llm_yellow(self, classifier_with_llm, mock_llm):
        mock_llm.chat.return_value = MockLLMResponse(
            content='{"safety_level":"yellow","protocol":"S3","signals":["psychosis_possible"],"confidence":0.8}',
        )
        result = await classifier_with_llm.classify("иногда слышу голоса", context=[])
        assert result.safety_level == SafetyLevel.YELLOW
        assert result.specialist_suggestion is not None
        assert result.block_practice is False

    async def test_llm_red_low_confidence_still_escalates(self, classifier_with_llm, mock_llm):
        mock_llm.chat.return_value = MockLLMResponse(
            content='{"safety_level":"red","protocol":"S1","signals":["ambiguous"],"confidence":0.3}',
        )
        result = await classifier_with_llm.classify("не вижу смысла", context=[])
        assert result.safety_level == SafetyLevel.RED  # safety > precision
        assert result.block_practice is False

    async def test_llm_timeout_fallback(self, classifier_with_llm, mock_llm):
        mock_llm.chat.side_effect = TimeoutError("LLM timeout")
        result = await classifier_with_llm.classify("что-то случилось", context=[])
        assert result.safety_level == SafetyLevel.GREEN  # fail open, help freely
        assert result.block_practice is False
