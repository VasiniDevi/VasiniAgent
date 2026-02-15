"""Task state machine with valid transition enforcement and retry logic."""

from __future__ import annotations

from enum import Enum


class TaskState(Enum):
    """Possible states for an agent task."""

    QUEUED = "queued"
    RUNNING = "running"
    RETRY = "retry"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"


TERMINAL_STATES = {
    TaskState.DONE,
    TaskState.FAILED,
    TaskState.CANCELLED,
    TaskState.DEAD_LETTER,
}

VALID_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.QUEUED: {TaskState.RUNNING, TaskState.CANCELLED},
    TaskState.RUNNING: {
        TaskState.DONE,
        TaskState.RETRY,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.RETRY: {
        TaskState.RUNNING,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.DEAD_LETTER,
    },
    TaskState.DONE: set(),
    TaskState.FAILED: {TaskState.DEAD_LETTER},
    TaskState.CANCELLED: set(),
    TaskState.DEAD_LETTER: set(),
}


class TaskStateMachine:
    """Enforces valid state transitions and tracks retry counts."""

    def __init__(self, max_retries: int = 3) -> None:
        self.state = TaskState.QUEUED
        self.max_retries = max_retries
        self.retry_count = 0

    def transition(self, new_state: TaskState) -> None:
        """Transition to *new_state*, raising ValueError on illegal moves."""
        if self.state in TERMINAL_STATES:
            raise ValueError(
                f"Cannot transition from terminal state {self.state.value}"
            )

        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {new_state.value}"
            )

        # Auto-escalate RETRY when retries are exhausted
        if new_state == TaskState.RETRY:
            self.retry_count += 1
            if self.retry_count > self.max_retries:
                self.state = TaskState.FAILED
                return

        self.state = new_state
