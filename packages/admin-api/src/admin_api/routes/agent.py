"""Agent pack management endpoints -- read / edit / preview YAML layers."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from admin_api.auth import verify_token
from admin_api.deps import PACK_DIR

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Valid layer names (matching profession-pack.yaml references)
LAYER_NAMES = frozenset(
    ["soul", "role", "tools", "guardrails", "memory", "workflow"]
)


def _pack_dir() -> Path:
    """Resolve the pack directory path."""
    return PACK_DIR.resolve()


def _layer_path(layer: str) -> Path:
    """Return the YAML file path for a layer."""
    return _pack_dir() / f"{layer}.yaml"


def _load_layer(layer: str) -> dict[str, Any]:
    """Load a single YAML layer from disk."""
    path = _layer_path(layer)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Layer file not found: {layer}.yaml")
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _get_composer():
    """Import and return a Composer instance, adding agent-core to sys.path if needed."""
    agent_core_src = Path(__file__).resolve().parents[4] / "agent-core" / "src"
    if str(agent_core_src) not in sys.path:
        sys.path.insert(0, str(agent_core_src))
    from vasini.composer import Composer  # type: ignore[import-untyped]
    return Composer()


class LayerUpdate(BaseModel):
    """Request body for updating a pack layer."""
    content: dict[str, Any]


@router.get("/pack", dependencies=[Depends(verify_token)])
async def get_all_layers():
    """Return all pack layers as a dict keyed by layer name."""
    result: dict[str, Any] = {}
    for layer in sorted(LAYER_NAMES):
        path = _layer_path(layer)
        if path.exists():
            result[layer] = _load_layer(layer)
    return result


@router.get("/pack/{layer}", dependencies=[Depends(verify_token)])
async def get_layer(layer: str):
    """Return a single pack layer."""
    if layer not in LAYER_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown layer: {layer}. Must be one of: {', '.join(sorted(LAYER_NAMES))}",
        )
    return _load_layer(layer)


@router.put("/pack/{layer}", dependencies=[Depends(verify_token)])
async def update_layer(layer: str, body: LayerUpdate):
    """Overwrite a pack layer YAML. Validates via Composer before saving; rolls back on failure."""
    if layer not in LAYER_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown layer: {layer}. Must be one of: {', '.join(sorted(LAYER_NAMES))}",
        )

    path = _layer_path(layer)
    pack_dir = _pack_dir()

    # Create a backup of the current file (if it exists)
    backup_path = path.with_suffix(".yaml.bak")
    had_backup = False
    if path.exists():
        shutil.copy2(path, backup_path)
        had_backup = True

    try:
        # Write the new content
        with open(path, "w") as f:
            yaml.dump(body.content, f, default_flow_style=False, allow_unicode=True)

        # Validate the full pack via Composer
        composer = _get_composer()
        composer.load(pack_dir)

    except Exception as exc:
        # Roll back to the backup
        if had_backup:
            shutil.copy2(backup_path, path)
        elif path.exists():
            path.unlink()
        raise HTTPException(
            status_code=422,
            detail=f"Validation failed, changes rolled back: {exc}",
        ) from exc
    finally:
        # Clean up backup
        if backup_path.exists():
            backup_path.unlink()

    return {"ok": True, "layer": layer}


@router.get("/prompt-preview", dependencies=[Depends(verify_token)])
async def prompt_preview():
    """Load the pack and return the assembled system prompt."""
    try:
        composer = _get_composer()
        pack_dir = _pack_dir()
        agent_config = composer.load(pack_dir)

        # Import AgentRuntime to get _build_system_prompt
        from vasini.runtime.agent import AgentRuntime  # type: ignore[import-untyped]
        from vasini.llm.router import LLMRouter, LLMRouterConfig  # type: ignore[import-untyped]

        # Build a minimal runtime just for prompt assembly
        llm_config = LLMRouterConfig()
        llm_router = LLMRouter(config=llm_config)
        runtime = AgentRuntime(config=agent_config, llm_router=llm_router)
        prompt = runtime._build_system_prompt()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build prompt preview: {exc}",
        ) from exc

    return {"system_prompt": prompt}
