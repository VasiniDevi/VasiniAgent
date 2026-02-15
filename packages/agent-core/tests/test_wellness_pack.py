"""Tests for wellness-cbt profession pack loading."""

from pathlib import Path

import pytest

from vasini.composer import Composer


PACK_DIR = Path(__file__).resolve().parents[3] / "packs" / "wellness-cbt"


class TestWellnessPack:
    """Verify wellness-cbt pack loads and validates correctly."""

    @pytest.fixture
    def config(self):
        return Composer().load(PACK_DIR)

    def test_pack_loads_without_error(self, config):
        assert config.pack_id == "wellness-cbt"
        assert config.version == "0.1.0"
        assert config.risk_level == "high"

    def test_soul_loaded(self, config):
        assert config.soul is not None
        assert "Vasini Wellness" in config.soul.identity.name
        assert config.soul.personality.proactivity == "proactive"
        assert len(config.soul.principles) >= 5

    def test_role_loaded(self, config):
        assert config.role is not None
        assert config.role.title == "Cognitive Therapy Wellness Specialist"
        assert config.role.seniority == "principal"
        assert len(config.role.competency_graph.skills) >= 9
        assert len(config.role.limitations) >= 4

    def test_role_has_cbt_skills(self, config):
        skill_ids = [s.id for s in config.role.competency_graph.skills]
        assert "cbt-core" in skill_ids
        assert "cognitive-distortions" in skill_ids
        assert "mct-wells" in skill_ids
        assert "metacognition-applied" in skill_ids

    def test_tools_loaded(self, config):
        assert config.tools is not None
        tool_ids = [t.id for t in config.tools.available]
        assert "mood_tracker" in tool_ids
        assert "thought_record" in tool_ids
        assert "assessment" in tool_ids

    def test_guardrails_loaded(self, config):
        assert config.guardrails is not None
        assert config.guardrails.input.jailbreak_detection is True
        assert config.guardrails.input.pii_detection.enabled is True
        assert len(config.guardrails.behavioral.prohibited_actions) >= 5
        assert len(config.guardrails.behavioral.escalation_triggers) >= 3

    def test_memory_loaded(self, config):
        assert config.memory is not None
        assert config.memory.short_term.enabled is True
        assert config.memory.cross_session.enabled is True

    def test_workflow_loaded(self, config):
        assert config.workflow is not None
        sop_ids = [s.id for s in config.workflow.sop]
        assert "user-message" in sop_ids
        assert "proactive-checkin" in sop_ids
        assert "crisis-protocol" in sop_ids
