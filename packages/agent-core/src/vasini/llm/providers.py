"""Provider abstractions for LLM backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # system | user | assistant | tool
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ToolSchema:
    """Schema describing a tool the model can invoke."""

    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class LLMResponse:
    """Response returned from an LLM provider."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"


class ProviderType(Enum):
    """Supported LLM provider backends."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
