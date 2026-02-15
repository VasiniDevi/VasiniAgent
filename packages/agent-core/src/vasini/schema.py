"""Pack schema validation using JSON Schema."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml


SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"

LAYER_SCHEMA_MAP = {
    "soul": "soul.schema.json",
    "role": "role.schema.json",
    "tools": "tools.schema.json",
    "guardrails": "guardrails.schema.json",
    "memory": "memory.schema.json",
    "workflow": "workflow.schema.json",
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def _load_schema(schema_name: str) -> dict:
    schema_path = SCHEMAS_DIR / schema_name
    with open(schema_path) as f:
        return json.load(f)


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def validate_pack(pack_dir: Path) -> ValidationResult:
    """Validate a profession pack directory against JSON Schemas."""
    errors: list[str] = []

    pack_file = pack_dir / "profession-pack.yaml"
    if not pack_file.exists():
        return ValidationResult(valid=False, errors=["profession-pack.yaml not found"])

    pack_data = _load_yaml(pack_file)

    # Validate pack manifest
    pack_schema = _load_schema("profession-pack.schema.json")
    try:
        jsonschema.validate(instance=pack_data, schema=pack_schema)
    except jsonschema.ValidationError as e:
        errors.append(f"profession-pack.yaml: {e.json_path}: {e.message}")

    # Validate each referenced layer file
    for layer_name, schema_file in LAYER_SCHEMA_MAP.items():
        layer_ref = pack_data.get(layer_name)
        if not layer_ref:
            continue

        layer_file = layer_ref.get("file") if isinstance(layer_ref, dict) else None
        if not layer_file:
            continue

        layer_path = pack_dir / layer_file
        if not layer_path.exists():
            errors.append(f"{layer_name}: file {layer_file} not found")
            continue

        layer_data = _load_yaml(layer_path)
        layer_schema = _load_schema(schema_file)
        try:
            jsonschema.validate(instance=layer_data, schema=layer_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{layer_name} ({layer_file}): {e.json_path}: {e.message}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
