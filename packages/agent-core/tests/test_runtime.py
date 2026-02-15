"""Tests for TaskStateMachine and AgentRuntime."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vasini.llm.providers import LLMResponse, Message
from vasini.llm.router import LLMRouter, LLMRouterConfig, ModelTier
from vasini.models import AgentConfig, Role, RoleGoal, Soul, SoulIdentity, SoulTone
from vasini.runtime.state import TERMINAL_STATES, TaskState, TaskStateMachine
from vasini.runtime.agent import AgentResult, AgentRuntime


# ── TaskStateMachine Tests ─────────────────────────────────────────────────


class TestTaskStateMachine:
    def test_initial_state_is_queued(self):
        sm = TaskStateMachine()
        assert sm.state == TaskState.QUEUED

    def test_queued_to_running(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        assert sm.state == TaskState.RUNNING

    def test_running_to_done(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.DONE)
        assert sm.state == TaskState.DONE

    def test_running_to_retry(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.RETRY)
        assert sm.state == TaskState.RETRY
        assert sm.retry_count == 1

    def test_max_retries_to_failed(self):
        sm = TaskStateMachine(max_retries=2)
        sm.transition(TaskState.RUNNING)

        # First retry
        sm.transition(TaskState.RETRY)
        assert sm.state == TaskState.RETRY
        sm.transition(TaskState.RUNNING)

        # Second retry
        sm.transition(TaskState.RETRY)
        assert sm.state == TaskState.RETRY
        sm.transition(TaskState.RUNNING)

        # Third retry exceeds max_retries=2 -> auto FAILED
        sm.transition(TaskState.RETRY)
        assert sm.state == TaskState.FAILED

    def test_running_to_cancelled(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.CANCELLED)
        assert sm.state == TaskState.CANCELLED

    def test_invalid_transition_raises(self):
        sm = TaskStateMachine()
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(TaskState.DONE)

    def test_terminal_states_cannot_transition(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.DONE)
        with pytest.raises(ValueError, match="terminal state"):
            sm.transition(TaskState.RUNNING)

    def test_queued_to_cancelled(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.CANCELLED)
        assert sm.state == TaskState.CANCELLED

    def test_failed_to_dead_letter(self):
        sm = TaskStateMachine()
        sm.transition(TaskState.RUNNING)
        sm.transition(TaskState.FAILED)
        # FAILED is terminal, so this should raise
        with pytest.raises(ValueError, match="terminal state"):
            sm.transition(TaskState.DEAD_LETTER)


# ── AgentRuntime Tests ─────────────────────────────────────────────────────


class TestAgentRuntime:
    def _make_config(self) -> AgentConfig:
        return AgentConfig(
            pack_id="test-agent",
            role=Role(
                title="Test Engineer",
                domain="testing",
                goal=RoleGoal(primary="Help users write tests"),
                backstory="An experienced QA engineer",
                limitations=["Cannot deploy code"],
            ),
            soul=Soul(
                identity=SoulIdentity(name="TestBot"),
                tone=SoulTone(default="friendly"),
                principles=["Be helpful", "Be accurate"],
            ),
        )

    def _make_router(self) -> LLMRouter:
        config = LLMRouterConfig(
            tier_mapping={
                ModelTier.TIER_1: "claude-opus",
                ModelTier.TIER_2: "claude-sonnet",
                ModelTier.TIER_3: "claude-haiku",
            },
        )
        return LLMRouter(config)

    @pytest.mark.asyncio
    async def test_run_returns_response(self):
        config = self._make_config()
        router = self._make_router()
        runtime = AgentRuntime(config, router)

        mock_response = LLMResponse(
            content="Here is your answer.",
            model="claude-sonnet",
            tool_calls=[],
        )

        with patch.object(
            router, "_call_provider", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await runtime.run("Hello")

        assert result.output == "Here is your answer."
        assert result.state == TaskState.DONE
        assert isinstance(result, AgentResult)

    @pytest.mark.asyncio
    async def test_run_respects_max_steps(self):
        config = self._make_config()
        config.guardrails.behavioral.max_autonomous_steps = 2
        router = self._make_router()
        runtime = AgentRuntime(config, router)

        tool_response = LLMResponse(
            content="Calling tool...",
            model="claude-sonnet",
            tool_calls=[{"id": "tc_1", "name": "search", "arguments": "{}"}],
        )
        final_response = LLMResponse(
            content="Final answer.",
            model="claude-sonnet",
            tool_calls=[],
        )

        call_count = 0

        async def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return tool calls for the first 3 calls, then final
            if call_count <= 3:
                return tool_response
            return final_response

        with patch.object(router, "_call_provider", side_effect=mock_call):
            result = await runtime.run("Do something")

        # max_autonomous_steps=2, so the loop runs at most 3 iterations
        # (initial + 2 tool-call steps)
        assert result.steps_taken <= 3

    @pytest.mark.asyncio
    async def test_system_prompt_contains_role(self):
        config = self._make_config()
        runtime = AgentRuntime(config, self._make_router())

        prompt = runtime._build_system_prompt()
        assert "Test Engineer" in prompt
        assert "Help users write tests" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_contains_soul(self):
        config = self._make_config()
        runtime = AgentRuntime(config, self._make_router())

        prompt = runtime._build_system_prompt()
        assert "friendly" in prompt
        assert "Be helpful" in prompt

    @pytest.mark.asyncio
    async def test_system_prompt_contains_limitations(self):
        config = self._make_config()
        runtime = AgentRuntime(config, self._make_router())

        prompt = runtime._build_system_prompt()
        assert "Cannot deploy code" in prompt
