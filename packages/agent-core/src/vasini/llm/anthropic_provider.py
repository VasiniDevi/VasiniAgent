"""Anthropic Claude provider for LLM Router."""

from __future__ import annotations

import httpx

from vasini.llm.providers import LLMResponse, Message


class AnthropicProvider:
    """Calls Anthropic Messages API."""

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=60.0,
        )

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Format messages for Anthropic API, extracting system messages."""
        return [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

    def _extract_system(self, messages: list[Message]) -> str | None:
        """Extract system message content."""
        for m in messages:
            if m.role == "system":
                return m.content
        return None

    def _parse_response(self, raw: dict) -> LLMResponse:
        """Parse Anthropic API response into LLMResponse."""
        content_blocks = raw.get("content", [])
        text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                text += block.get("text", "")

        return LLMResponse(
            content=text,
            model=raw.get("model", self.default_model),
            usage=raw.get("usage", {}),
            tool_calls=[],
            finish_reason=raw.get("stop_reason", "end_turn"),
        )

    async def chat(
        self,
        messages: list[Message],
        system: str | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Send messages to Claude and return response."""
        system_text = system or self._extract_system(messages)
        formatted = self._format_messages(messages)

        body: dict = {
            "model": model or self.default_model,
            "max_tokens": self.max_tokens,
            "messages": formatted,
        }
        if system_text:
            body["system"] = system_text

        resp = await self._client.post(self.API_URL, json=body)
        resp.raise_for_status()
        return self._parse_response(resp.json())

    async def close(self) -> None:
        await self._client.aclose()
