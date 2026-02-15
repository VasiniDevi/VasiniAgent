"""LLM Router with tier-based model mapping, fallback chain, and circuit breaker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from vasini.llm.providers import LLMResponse, Message, ToolSchema


class ModelTier(Enum):
    """Model capability tiers."""

    TIER_1 = "tier-1"  # Full capability (opus-class)
    TIER_2 = "tier-2"  # Balanced (sonnet-class)
    TIER_3 = "tier-3"  # Fast/cheap (haiku-class)


@dataclass
class CircuitBreakerState:
    """Per-model circuit breaker preventing repeated calls to failing providers."""

    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed | open | half_open
    error_threshold: int = 5
    window_seconds: float = 60.0
    half_open_after: float = 120.0

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        now = time.monotonic()

        # Reset count if outside the rolling window
        if (
            self.last_failure_time > 0
            and (now - self.last_failure_time) > self.window_seconds
        ):
            self.failure_count = 0

        self.failure_count += 1
        self.last_failure_time = now

        if self.failure_count >= self.error_threshold:
            self.state = "open"

    def record_success(self) -> None:
        """Record a success, resetting the breaker to closed."""
        self.failure_count = 0
        self.state = "closed"

    def can_attempt(self) -> bool:
        """Return True if a request is allowed through the breaker."""
        if self.state == "closed":
            return True

        if self.state == "open":
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.half_open_after:
                self.state = "half_open"
                return True
            return False

        # half_open — allow one probe request
        return True


@dataclass
class LLMRouterConfig:
    """Configuration for the LLM Router."""

    tier_mapping: dict[ModelTier, str]  # tier -> model name
    default_tier: ModelTier = ModelTier.TIER_2
    fallback_chain: list[ModelTier] = field(default_factory=list)


class LLMRouter:
    """Routes LLM requests through tiers with fallback and circuit breaking."""

    def __init__(self, config: LLMRouterConfig) -> None:
        self.config = config
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}

    def _get_breaker(self, model: str) -> CircuitBreakerState:
        """Get or create a circuit breaker for the given model."""
        if model not in self._circuit_breakers:
            self._circuit_breakers[model] = CircuitBreakerState()
        return self._circuit_breakers[model]

    def resolve_model(self, tier: ModelTier | None = None) -> str:
        """Map a tier to its configured model string.

        Uses default_tier when tier is None.
        """
        effective_tier = tier if tier is not None else self.config.default_tier
        return self.config.tier_mapping[effective_tier]

    def get_fallback_chain(self, current_tier: ModelTier) -> list[ModelTier]:
        """Return the remaining tiers after *current_tier* in the fallback chain."""
        chain = self.config.fallback_chain
        if current_tier in chain:
            idx = chain.index(current_tier)
            return chain[idx + 1 :]
        return []

    async def chat(
        self,
        messages: list[Message],
        system: str = "",
        tier: ModelTier | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Send a chat request, falling back through the chain on breaker trips."""
        effective_tier = tier if tier is not None else self.config.default_tier
        model = self.resolve_model(effective_tier)
        breaker = self._get_breaker(model)

        if breaker.can_attempt():
            try:
                response = await self._call_provider(model, messages, system, tools)
                breaker.record_success()
                return response
            except Exception:
                breaker.record_failure()

        # Try fallback chain
        for fallback_tier in self.get_fallback_chain(effective_tier):
            fb_model = self.resolve_model(fallback_tier)
            fb_breaker = self._get_breaker(fb_model)
            if fb_breaker.can_attempt():
                try:
                    response = await self._call_provider(
                        fb_model, messages, system, tools
                    )
                    fb_breaker.record_success()
                    return response
                except Exception:
                    fb_breaker.record_failure()

        raise RuntimeError("All models in the fallback chain are unavailable")

    async def _call_provider(
        self,
        model: str,
        messages: list[Message],
        system: str,
        tools: list[ToolSchema] | None,
    ) -> LLMResponse:
        """Dispatch to the appropriate provider. Subclasses override this."""
        raise NotImplementedError("Provider dispatch not yet implemented")
