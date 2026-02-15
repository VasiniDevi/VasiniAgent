"""Tests for Event Bus — CloudEvents, outbox, DLQ."""

import pytest
from datetime import datetime, timezone
from vasini.events.envelope import CloudEvent, build_event
from vasini.events.bus import EventBus, EventHandler, InMemoryEventBus
from vasini.events.dlq import DeadLetterQueue, DLQEntry


class TestCloudEvent:
    def test_build_event(self):
        event = build_event(
            event_type="ai.vasini.agent.completed",
            source="/agent-core/runtime",
            data={"task_id": "t-1", "output": "done"},
        )
        assert event.specversion == "1.0"
        assert event.type == "ai.vasini.agent.completed"
        assert event.source == "/agent-core/runtime"
        assert event.id is not None
        assert event.data["task_id"] == "t-1"

    def test_event_has_timestamp(self):
        event = build_event(
            event_type="ai.vasini.test",
            source="/test",
            data={},
        )
        assert event.time is not None

    def test_event_with_subject(self):
        event = build_event(
            event_type="ai.vasini.tool.executed",
            source="/agent-core/sandbox",
            data={"tool_id": "code_exec"},
            subject="agent:python-dev:run-42",
        )
        assert event.subject == "agent:python-dev:run-42"

    def test_event_with_tenant(self):
        event = build_event(
            event_type="ai.vasini.agent.completed",
            source="/test",
            data={},
            tenant_id="t-123",
        )
        assert event.tenant_id == "t-123"


class TestInMemoryEventBus:
    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: CloudEvent) -> None:
            received.append(event)

        bus.subscribe("ai.vasini.agent.completed", handler)
        event = build_event("ai.vasini.agent.completed", "/test", {"done": True})
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].type == "ai.vasini.agent.completed"

    @pytest.mark.asyncio
    async def test_subscribe_filters_by_type(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: CloudEvent) -> None:
            received.append(event)

        bus.subscribe("ai.vasini.agent.completed", handler)
        await bus.publish(build_event("ai.vasini.tool.executed", "/test", {}))
        await bus.publish(build_event("ai.vasini.agent.completed", "/test", {}))

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = InMemoryEventBus()
        received_a = []
        received_b = []

        async def handler_a(event: CloudEvent) -> None:
            received_a.append(event)

        async def handler_b(event: CloudEvent) -> None:
            received_b.append(event)

        bus.subscribe("ai.vasini.test", handler_a)
        bus.subscribe("ai.vasini.test", handler_b)
        await bus.publish(build_event("ai.vasini.test", "/test", {}))

        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_failed_handler_sends_to_dlq(self):
        bus = InMemoryEventBus(max_retries=2)

        async def failing_handler(event: CloudEvent) -> None:
            raise ValueError("Handler error")

        bus.subscribe("ai.vasini.test", failing_handler)
        event = build_event("ai.vasini.test", "/test", {})
        await bus.publish(event)

        assert len(bus.dlq.entries) == 1
        assert bus.dlq.entries[0].retry_count == 2

    @pytest.mark.asyncio
    async def test_idempotent_delivery(self):
        bus = InMemoryEventBus()
        received = []

        async def handler(event: CloudEvent) -> None:
            received.append(event)

        bus.subscribe("ai.vasini.test", handler)
        event = build_event("ai.vasini.test", "/test", {})
        await bus.publish(event)
        await bus.publish(event)  # same event_id

        assert len(received) == 1  # dedup


class TestDeadLetterQueue:
    def test_add_to_dlq(self):
        dlq = DeadLetterQueue()
        event = build_event("ai.vasini.test", "/test", {})
        dlq.add(event, error="Handler failed", retry_count=5)
        assert len(dlq.entries) == 1
        assert dlq.entries[0].error == "Handler failed"

    def test_replay_from_dlq(self):
        dlq = DeadLetterQueue()
        event = build_event("ai.vasini.test", "/test", {})
        dlq.add(event, error="fail", retry_count=5)
        replayed = dlq.replay(event.id)
        assert replayed is not None
        assert replayed.type == "ai.vasini.test"

    def test_replay_removes_from_dlq(self):
        dlq = DeadLetterQueue()
        event = build_event("ai.vasini.test", "/test", {})
        dlq.add(event, error="fail", retry_count=5)
        dlq.replay(event.id)
        assert len(dlq.entries) == 0

    def test_dlq_depth(self):
        dlq = DeadLetterQueue()
        for i in range(5):
            event = build_event("ai.vasini.test", "/test", {"i": i})
            dlq.add(event, error="fail", retry_count=5)
        assert dlq.depth == 5
