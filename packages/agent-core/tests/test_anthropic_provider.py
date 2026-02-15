"""Tests for Anthropic Claude provider."""

import pytest

from vasini.llm.anthropic_provider import AnthropicProvider
from vasini.llm.providers import LLMResponse, Message


class TestAnthropicProvider:

    def test_create_provider(self):
        provider = AnthropicProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.default_model == "claude-sonnet-4-5-20250929"

    def test_create_with_custom_model(self):
        provider = AnthropicProvider(api_key="test-key", default_model="claude-opus-4-6")
        assert provider.default_model == "claude-opus-4-6"

    def test_format_messages(self):
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        formatted = provider._format_messages(messages)
        assert len(formatted) == 2
        assert formatted[0]["role"] == "user"
        assert formatted[0]["content"] == "Hello"

    def test_format_system_extracted(self):
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        formatted = provider._format_messages(messages)
        assert all(m["role"] != "system" for m in formatted)

    def test_extract_system(self):
        provider = AnthropicProvider(api_key="test-key")
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        system = provider._extract_system(messages)
        assert system == "You are helpful"

    def test_extract_system_none(self):
        provider = AnthropicProvider(api_key="test-key")
        messages = [Message(role="user", content="Hello")]
        assert provider._extract_system(messages) is None

    def test_parse_response(self):
        provider = AnthropicProvider(api_key="test-key")
        raw = {
            "content": [{"type": "text", "text": "Hello!"}],
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }
        response = provider._parse_response(raw)
        assert isinstance(response, LLMResponse)
        assert response.content == "Hello!"
        assert response.model == "claude-sonnet-4-5-20250929"
        assert response.usage["input_tokens"] == 10

    def test_parse_response_multiple_blocks(self):
        provider = AnthropicProvider(api_key="test-key")
        raw = {
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world!"},
            ],
            "model": "claude-sonnet-4-5-20250929",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "stop_reason": "end_turn",
        }
        response = provider._parse_response(raw)
        assert response.content == "Hello world!"
