"""Bot .env configuration management endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from admin_api.auth import verify_token
from admin_api.deps import ENV_PATH

router = APIRouter(prefix="/api", tags=["config"])

# Keys that can be read and written through the admin API.
SAFE_KEYS: frozenset[str] = frozenset(
    {
        "CLAUDE_MODEL",
        "CHECKIN_INTERVAL_HOURS",
        "QUIET_HOURS_START",
        "QUIET_HOURS_END",
        "PACK_DIR",
        "DB_PATH",
        "ALLOWED_USER_IDS",
        "ELEVENLABS_VOICE_ID",
        "ELEVENLABS_MODEL",
    }
)

# Keys whose values should be masked in GET responses.
SECRET_KEYS: frozenset[str] = frozenset(
    {
        "TELEGRAM_BOT_TOKEN",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
    }
)


def _read_env() -> dict[str, str]:
    """Read the .env file into a dict."""
    path = ENV_PATH.resolve()
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _write_env(data: dict[str, str]) -> None:
    """Write a dict back to the .env file, preserving order."""
    path = ENV_PATH.resolve()
    lines: list[str] = []
    for key, value in data.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ConfigUpdate(BaseModel):
    """Partial config update -- only SAFE_KEYS allowed."""
    values: dict[str, str]


@router.get("/config", dependencies=[Depends(verify_token)])
async def get_config():
    """Return the bot config with secrets masked."""
    env = _read_env()
    safe_env: dict[str, Any] = {}
    for key, value in env.items():
        if key in SECRET_KEYS:
            # Mask secret values, showing only last 4 characters
            if len(value) > 4:
                safe_env[key] = "*" * (len(value) - 4) + value[-4:]
            else:
                safe_env[key] = "****"
        else:
            safe_env[key] = value
    return {"config": safe_env}


@router.patch("/config", dependencies=[Depends(verify_token)])
async def update_config(body: ConfigUpdate):
    """Update safe configuration keys in the .env file."""
    # Validate all keys are in SAFE_KEYS
    forbidden = set(body.values.keys()) - SAFE_KEYS
    if forbidden:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update protected keys: {', '.join(sorted(forbidden))}",
        )

    env = _read_env()
    env.update(body.values)
    _write_env(env)

    return {"ok": True, "updated": list(body.values.keys())}
