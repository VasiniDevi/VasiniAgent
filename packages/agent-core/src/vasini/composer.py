"""Composer — assembles an AgentConfig from a pack directory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Type

import yaml
from pydantic import BaseModel

from vasini.models import (
    AgentConfig,
    Guardrails,
    Memory,
    Role,
    Skill,
    Soul,
    Tools,
    Workflow,
)


class ComposerError(Exception):
    """Raised when pack loading fails."""


# Mapping from pack manifest keys to their Pydantic model class.
_LAYER_MODELS: dict[str, Type[BaseModel]] = {
    "soul": Soul,
    "role": Role,
    "tools": Tools,
    "guardrails": Guardrails,
    "memory": Memory,
    "workflow": Workflow,
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*.

    - Dicts are merged recursively.
    - Lists and scalars from *override* replace those in *base*.
    """
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _parse_skill_markdown(path: Path) -> dict:
    """Parse a skill markdown file with YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        raise ComposerError(f"Skill file {path} has no YAML frontmatter")
    frontmatter = yaml.safe_load(match.group(1)) or {}
    frontmatter["body"] = match.group(2).strip()
    return frontmatter


class Composer:
    """Load and assemble a profession pack into an AgentConfig."""

    def load(self, pack_dir: Path) -> AgentConfig:
        """Read a pack directory and return a fully assembled AgentConfig."""
        pack_dir = Path(pack_dir)
        pack_file = pack_dir / "profession-pack.yaml"

        if not pack_file.exists():
            raise ComposerError(f"profession-pack.yaml not found in {pack_dir}")

        manifest = _load_yaml(pack_file)

        layers: dict[str, Any] = {}
        for layer_name, model_cls in _LAYER_MODELS.items():
            ref = manifest.get(layer_name)
            if ref is None:
                layers[layer_name] = model_cls()
            else:
                layers[layer_name] = self._load_layer(pack_dir, ref, model_cls)

        # Skills are a list of refs, not a single ref.
        skill_refs = manifest.get("skills", [])
        layers["skills"] = self._load_skills(pack_dir, skill_refs)

        return AgentConfig(
            pack_id=manifest["pack_id"],
            version=manifest.get("version", "1.0.0"),
            risk_level=manifest.get("risk_level", "medium"),
            **layers,
        )

    def _load_layer(
        self,
        pack_dir: Path,
        ref: dict | str,
        model_cls: Type[BaseModel],
    ) -> BaseModel:
        """Resolve a layer reference and return the corresponding model."""
        if not isinstance(ref, dict):
            raise ComposerError(f"Layer ref must be a dict, got {type(ref)}")

        if "file" in ref:
            file_path = pack_dir / ref["file"]
            if not file_path.exists():
                raise ComposerError(f"Layer file not found: {file_path}")
            data = _load_yaml(file_path)
            return model_cls.model_validate(data)

        if "extends" in ref:
            base_path = pack_dir / ref["extends"]
            if not base_path.exists():
                raise ComposerError(f"Base layer file not found: {base_path}")
            base_data = _load_yaml(base_path)
            override = ref.get("override", {})
            merged = _deep_merge(base_data, override)
            return model_cls.model_validate(merged)

        # Inline — the ref dict *is* the data.
        return model_cls.model_validate(ref)

    def _load_skills(
        self, pack_dir: Path, skill_refs: list[dict]
    ) -> list[Skill]:
        """Load skill definitions from markdown files or inline dicts."""
        skills: list[Skill] = []
        for ref in skill_refs:
            if isinstance(ref, dict) and "file" in ref:
                file_path = pack_dir / ref["file"]
                if not file_path.exists():
                    raise ComposerError(f"Skill file not found: {file_path}")
                data = _parse_skill_markdown(file_path)
                skills.append(Skill.model_validate(data))
            elif isinstance(ref, dict):
                skills.append(Skill.model_validate(ref))
            else:
                raise ComposerError(f"Invalid skill ref: {ref}")
        return skills
