"""YAML practice loader with fail-fast validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


_VALID_CATEGORIES = {"monitoring", "attention", "cognitive", "behavioral", "micro", "relapse_prevention"}
_VALID_UI_MODES = {"text", "buttons", "timer", "text_input"}
_VALID_BUTTON_ACTIONS = {"next", "fallback", "branch_extended", "branch_help", "backup_practice", "end"}
_REQUIRED_FALLBACK_KEYS = {"user_confused", "cannot_now", "too_hard"}


class PracticeValidationError(Exception):
    pass


@dataclass
class PracticeStep:
    index: int
    instruction_ru: str
    ui_mode: str
    checkpoint: bool
    fallback: dict[str, str]
    buttons: list[dict] | None = None


@dataclass
class Practice:
    id: str
    version: str
    step_schema_hash: str
    name_ru: str
    name_en: str
    category: str
    goal: str
    duration_min: int
    duration_max: int
    priority_rank: int
    prerequisites: dict
    safety_overrides: dict
    maintaining_cycles: list[str]
    steps: list[PracticeStep]
    outcome: dict
    resume_compatibility: dict


class PracticeLoader:
    def __init__(self, practices_dir: Path | str) -> None:
        self._dir = Path(practices_dir)

    def load_all(self) -> dict[str, Practice]:
        practices: dict[str, Practice] = {}
        for path in sorted(self._dir.glob("*.yaml")):
            practice = self._load_one(path)
            practices[practice.id] = practice
        return practices

    def _load_one(self, path: Path) -> Practice:
        with open(path) as f:
            data = yaml.safe_load(f)

        pid = data["id"]

        # Validate category
        if data.get("category") not in _VALID_CATEGORIES:
            raise PracticeValidationError(f"{pid}: invalid category '{data.get('category')}'")

        # Validate and build steps
        steps = []
        raw_steps = data.get("steps", [])
        expected_index = 1
        for s in raw_steps:
            idx = s["index"]
            if idx != expected_index:
                raise PracticeValidationError(
                    f"{pid}: step index continuity broken — expected {expected_index}, got {idx}"
                )
            expected_index += 1

            # Validate ui_mode
            if s.get("ui_mode") not in _VALID_UI_MODES:
                raise PracticeValidationError(f"{pid} step {idx}: invalid ui_mode '{s.get('ui_mode')}'")

            # Validate fallback keys
            fallback = s.get("fallback", {})
            missing = _REQUIRED_FALLBACK_KEYS - set(fallback.keys())
            if missing:
                raise PracticeValidationError(
                    f"{pid} step {idx}: missing fallback keys: {missing}"
                )

            # Validate button actions
            buttons = s.get("buttons")
            if buttons:
                for btn in buttons:
                    if btn.get("action") not in _VALID_BUTTON_ACTIONS:
                        raise PracticeValidationError(
                            f"{pid} step {idx}: invalid button action '{btn.get('action')}'"
                        )

            steps.append(PracticeStep(
                index=idx,
                instruction_ru=s["instruction_ru"],
                ui_mode=s["ui_mode"],
                checkpoint=s.get("checkpoint", False),
                fallback=fallback,
                buttons=buttons,
            ))

        return Practice(
            id=pid,
            version=data["version"],
            step_schema_hash=data.get("step_schema_hash", ""),
            name_ru=data["name_ru"],
            name_en=data.get("name_en", ""),
            category=data["category"],
            goal=data["goal"],
            duration_min=data["duration_min"],
            duration_max=data["duration_max"],
            priority_rank=data["priority_rank"],
            prerequisites=data.get("prerequisites", {}),
            safety_overrides=data.get("safety_overrides", {}),
            maintaining_cycles=data.get("maintaining_cycles", []),
            steps=steps,
            outcome=data.get("outcome", {}),
            resume_compatibility=data.get("resume_compatibility", {}),
        )
