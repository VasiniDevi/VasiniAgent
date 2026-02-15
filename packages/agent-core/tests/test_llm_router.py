"""Tests for LLM Router with tier-based routing and circuit breaker."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from vasini.llm.providers import LLMResponse, Message
from vasini.llm.router import (
    CircuitBreakerState,
    LLMRouter,
    LLMRouterConfig,
    ModelTier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tier_mapping() -> dict[ModelTier, str]:
    return {
        ModelTier.TIER_1: "claude-opus-4-20250514",
        ModelTier.TIER_2: "claude-sonnet-4-20250514",
        ModelTier.TIER_3: "claude-haiku-3",
    }


@pytest.fixture
def router_config(tier_mapping: dict[ModelTier, str]) -> LLMRouterConfig:
    return LLMRouterConfig(
        tier_mapping=tier_mapping,
        default_tier=ModelTier.TIER_2,
        fallback_chain=[ModelTier.TIER_1, ModelTier.TIER_2, ModelTier.TIER_3],
    )


@pytest.fixture
def router(router_config: LLMRouterConfig) -> LLMRouter:
    return LLMRouter(config=router_config)


# ---------------------------------------------------------------------------
# TestLLMRouter
# ---------------------------------------------------------------------------

class TestLLMRouter:
    def test_create_router_with_config(
        self, router: LLMRouter, router_config: LLMRouterConfig
    ) -> None:
        assert router.config is router_config
        assert isinstance(router, LLMRouter)

    def test_resolve_model_by_tier(
        self, router: LLMRouter, tier_mapping: dict[ModelTier, str]
    ) -> None:
        for tier, expected_model in tier_mapping.items():
            assert router.resolve_model(tier) == expected_model

    def test_default_tier_used_when_none_specified(self, router: LLMRouter) -> None:
        model = router.resolve_model()
        assert model == "claude-sonnet-4-20250514"

    def test_fallback_chain(self, router: LLMRouter) -> None:
        chain = router.get_fallback_chain(ModelTier.TIER_1)
        assert chain == [ModelTier.TIER_2, ModelTier.TIER_3]

        chain = router.get_fallback_chain(ModelTier.TIER_2)
        assert chain == [ModelTier.TIER_3]

        chain = router.get_fallback_chain(ModelTier.TIER_3)
        assert chain == []

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, router: LLMRouter) -> None:
        expected = LLMResponse(content="Hello!", model="claude-sonnet-4-20250514")
        router._call_provider = AsyncMock(return_value=expected)

        messages = [Message(role="user", content="Hi")]
        response = await router.chat(messages)

        assert response.content == "Hello!"
        assert response.model == "claude-sonnet-4-20250514"
        router._call_provider.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_falls_back_on_circuit_open(self, router: LLMRouter) -> None:
        """When the primary model's breaker is open, chat falls back."""
        primary_model = router.resolve_model(ModelTier.TIER_2)
        breaker = router._get_breaker(primary_model)
        # Force breaker open
        breaker.state = "open"
        breaker.last_failure_time = time.monotonic()

        fallback_response = LLMResponse(content="Fallback", model="claude-haiku-3")
        router._call_provider = AsyncMock(return_value=fallback_response)

        messages = [Message(role="user", content="Hi")]
        response = await router.chat(messages, tier=ModelTier.TIER_2)

        assert response.content == "Fallback"

    @pytest.mark.asyncio
    async def test_chat_raises_when_all_unavailable(self, router: LLMRouter) -> None:
        """When all models fail, a RuntimeError is raised."""
        router._call_provider = AsyncMock(side_effect=RuntimeError("provider down"))

        # Open all breakers so they fail immediately
        for tier in [ModelTier.TIER_1, ModelTier.TIER_2, ModelTier.TIER_3]:
            model = router.resolve_model(tier)
            breaker = router._get_breaker(model)
            breaker.state = "open"
            breaker.last_failure_time = time.monotonic()

        messages = [Message(role="user", content="Hi")]
        with pytest.raises(RuntimeError, match="All models"):
            await router.chat(messages, tier=ModelTier.TIER_1)


# ---------------------------------------------------------------------------
# TestCircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_closed(self) -> None:
        cb = CircuitBreakerState()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreakerState(error_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert not cb.can_attempt()

    def test_success_resets(self) -> None:
        cb = CircuitBreakerState(error_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_half_open_after_timeout(self) -> None:
        cb = CircuitBreakerState(error_threshold=1, half_open_after=0.0)
        cb.record_failure()
        assert cb.state == "open"
        # With half_open_after=0.0, can_attempt should transition to half_open
        assert cb.can_attempt()
        assert cb.state == "half_open"

    def test_closed_can_attempt(self) -> None:
        cb = CircuitBreakerState()
        assert cb.can_attempt()
