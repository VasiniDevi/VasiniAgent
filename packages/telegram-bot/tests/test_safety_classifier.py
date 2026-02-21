# tests/test_safety_classifier.py
"""Tests for SafetyClassifier — hard rules layer."""
import pytest
from wellness_bot.protocol.safety import SafetyClassifier, SafetyResult
from wellness_bot.protocol.types import RiskLevel


@pytest.fixture
def classifier():
    return SafetyClassifier(classifier_version="1.0", policy_version="1.0")


class TestHardRules:
    def test_suicide_explicit_ru(self, classifier):
        result = classifier.check_hard_rules("хочу умереть")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS
        assert result.protocol_id == "S1"

    def test_suicide_explicit_en(self, classifier):
        result = classifier.check_hard_rules("I want to kill myself")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS
        assert result.protocol_id == "S1"

    def test_self_harm(self, classifier):
        result = classifier.check_hard_rules("я режу себя каждый вечер")
        assert result is not None
        assert result.protocol_id == "S1"

    def test_violence(self, classifier):
        result = classifier.check_hard_rules("я убью его")
        assert result is not None
        assert result.protocol_id == "S2"

    def test_psychosis(self, classifier):
        result = classifier.check_hard_rules("голоса говорят мне что делать")
        assert result is not None
        assert result.protocol_id == "S3"

    def test_domestic_violence(self, classifier):
        result = classifier.check_hard_rules("муж бьёт меня")
        assert result is not None
        assert result.protocol_id == "S6"

    def test_safe_message(self, classifier):
        result = classifier.check_hard_rules("Сегодня хороший день, настроение 7")
        assert result is None

    def test_safe_with_partial_keyword(self, classifier):
        """'умереть' in context of discussing death abstractly should still trigger."""
        result = classifier.check_hard_rules("Иногда хочу умереть")
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS

    def test_case_insensitive(self, classifier):
        result = classifier.check_hard_rules("ХОЧУ УМЕРЕТЬ")
        assert result is not None


class TestClassify:
    async def test_hard_rules_bypass_llm(self, classifier):
        """Hard rules should return immediately without calling LLM."""
        result = await classifier.classify("хочу покончить с собой", context=[])
        assert result.risk_level == RiskLevel.CRISIS
        assert result.source == "rules"

    async def test_safe_message_without_llm(self, classifier):
        """Without LLM provider, safe messages should return CAUTION_MILD (uncertain)."""
        result = await classifier.classify("привет, как дела", context=[])
        # Without LLM, we can't be certain → CAUTION_MILD
        assert result.risk_level == RiskLevel.CAUTION_MILD
        assert result.source == "heuristic"
