"""Tests for the Composer — layer loading and merging."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vasini.composer import Composer, ComposerError, _deep_merge
from vasini.models import AgentConfig

EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples"
PACK_DIR = EXAMPLES_DIR / "packs" / "senior-python-dev"


@pytest.fixture()
def composer() -> Composer:
    return Composer()


@pytest.fixture()
def config(composer: Composer) -> AgentConfig:
    return composer.load(PACK_DIR)


class TestComposer:
    def test_load_pack_from_directory(self, config: AgentConfig) -> None:
        assert isinstance(config, AgentConfig)
        assert config.pack_id == "senior-python-dev"
        assert config.version == "1.0.0"
        assert config.risk_level == "medium"

    def test_soul_loaded(self, config: AgentConfig) -> None:
        assert config.soul.identity.name == "Architect"
        assert config.soul.personality.communication_style == "professional"
        assert config.soul.personality.verbosity == "concise"
        assert len(config.soul.principles) == 3

    def test_role_loaded(self, config: AgentConfig) -> None:
        assert config.role.title == "Senior Backend Developer"
        assert config.role.seniority == "senior"
        assert config.role.domain == "Software Engineering"
        assert len(config.role.competency_graph.skills) > 0
        assert config.role.competency_graph.skills[0].id == "python-backend"

    def test_tools_loaded(self, config: AgentConfig) -> None:
        tool_ids = [t.id for t in config.tools.available]
        assert "code_executor" in tool_ids
        assert "git" in tool_ids
        assert "file_manager" in tool_ids
        assert "shell_unrestricted" in config.tools.denied

    def test_skills_loaded(self, config: AgentConfig) -> None:
        assert len(config.skills) == 1
        skill = config.skills[0]
        assert skill.id == "code-review"
        assert skill.name == "Code Review"
        assert "git" in skill.required_tools
        assert skill.body != ""
        assert "# Code Review" in skill.body

    def test_guardrails_loaded(self, config: AgentConfig) -> None:
        assert config.guardrails.behavioral.max_autonomous_steps == 15
        assert config.guardrails.input.jailbreak_detection is True
        assert config.guardrails.compliance.audit_logging is True

    def test_workflow_loaded(self, config: AgentConfig) -> None:
        assert config.workflow.default_process == "adaptive"
        assert len(config.workflow.sop) > 0
        assert config.workflow.sop[0].id == "feature-implementation"
        assert len(config.workflow.sop[0].steps) == 5

    def test_memory_loaded(self, config: AgentConfig) -> None:
        assert config.memory.short_term.enabled is True
        assert config.memory.episodic.retrieval_top_k == 10
        assert config.memory.cross_session.merge_strategy == "highest_confidence"

    def test_extends_merges_layers(
        self, composer: Composer, tmp_path: Path
    ) -> None:
        # Create a shared base soul
        base_soul = {
            "schema_version": "1.0",
            "identity": {"name": "Base", "language": "en"},
            "personality": {
                "communication_style": "casual",
                "verbosity": "verbose",
                "proactivity": "reactive",
                "confidence_expression": "balanced",
            },
            "tone": {"default": "friendly"},
            "principles": ["Be nice"],
        }
        (tmp_path / "base-soul.yaml").write_text(yaml.dump(base_soul))

        # Pack that extends the base with an override
        pack_manifest = {
            "schema_version": "1.0",
            "pack_id": "extends-test",
            "version": "1.0.0",
            "risk_level": "low",
            "soul": {
                "extends": "./base-soul.yaml",
                "override": {
                    "identity": {"name": "Override"},
                    "personality": {"communication_style": "professional"},
                },
            },
        }
        (tmp_path / "profession-pack.yaml").write_text(yaml.dump(pack_manifest))

        cfg = composer.load(tmp_path)
        # Override values applied
        assert cfg.soul.identity.name == "Override"
        assert cfg.soul.personality.communication_style == "professional"
        # Base values preserved where not overridden
        assert cfg.soul.personality.verbosity == "verbose"
        assert cfg.soul.tone.default == "friendly"
        assert cfg.soul.principles == ["Be nice"]

    def test_missing_pack_file_raises(
        self, composer: Composer, tmp_path: Path
    ) -> None:
        with pytest.raises(ComposerError, match="profession-pack.yaml not found"):
            composer.load(tmp_path)

    def test_missing_layer_file_raises(
        self, composer: Composer, tmp_path: Path
    ) -> None:
        manifest = {
            "schema_version": "1.0",
            "pack_id": "missing-layer",
            "version": "1.0.0",
            "risk_level": "low",
            "soul": {"file": "./nonexistent.yaml"},
        }
        (tmp_path / "profession-pack.yaml").write_text(yaml.dump(manifest))
        with pytest.raises(ComposerError, match="Layer file not found"):
            composer.load(tmp_path)

    def test_inline_layer(self, composer: Composer, tmp_path: Path) -> None:
        manifest = {
            "schema_version": "1.0",
            "pack_id": "inline-test",
            "version": "1.0.0",
            "risk_level": "low",
            "soul": {
                "schema_version": "1.0",
                "identity": {"name": "Inline"},
            },
        }
        (tmp_path / "profession-pack.yaml").write_text(yaml.dump(manifest))
        cfg = composer.load(tmp_path)
        assert cfg.soul.identity.name == "Inline"


class TestDeepMerge:
    def test_scalar_override(self) -> None:
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_nested_dict_merge(self) -> None:
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        assert _deep_merge(base, override) == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_list_replaces(self) -> None:
        assert _deep_merge({"a": [1, 2]}, {"a": [3]}) == {"a": [3]}

    def test_new_keys_added(self) -> None:
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
