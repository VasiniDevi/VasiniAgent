"""2-level conversation + practice finite-state machine.

The FSM tracks two orthogonal layers:
- **Conversation state** – high-level coaching phase (FREE_CHAT, EXPLORE, …).
- **Practice state** – inner practice step (CONSENT, STEP, CHECKPOINT, …),
  only meaningful when conversation_state is PRACTICE_ACTIVE.
"""

from __future__ import annotations

from wellness_bot.protocol.types import (
    ConversationState,
    CoachingDecision,
    PracticeState,
)

# States from which EXPLORE is a valid coaching decision
_EXPLORE_ALLOWED: frozenset[ConversationState] = frozenset(
    {ConversationState.FREE_CHAT, ConversationState.FOLLOW_UP}
)

# States from which SUGGEST is a valid coaching decision
_SUGGEST_ALLOWED: frozenset[ConversationState] = frozenset(
    {
        ConversationState.FREE_CHAT,
        ConversationState.EXPLORE,
        ConversationState.FOLLOW_UP,
    }
)

# Passthrough decisions that never change the conversation state
_PASSTHROUGH: frozenset[CoachingDecision] = frozenset(
    {CoachingDecision.LISTEN, CoachingDecision.ANSWER, CoachingDecision.GUIDE}
)


class ConversationFSM:
    """Two-level finite-state machine for the coaching conversation."""

    def __init__(self) -> None:
        self._conversation_state: ConversationState = ConversationState.FREE_CHAT
        self._practice_state: PracticeState | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def conversation_state(self) -> ConversationState:
        return self._conversation_state

    @property
    def practice_state(self) -> PracticeState | None:
        return self._practice_state

    # ------------------------------------------------------------------
    # Coaching-decision transitions
    # ------------------------------------------------------------------

    def transition(self, decision: CoachingDecision) -> bool:
        """Apply a coaching decision. Returns ``True`` on success."""
        if decision in _PASSTHROUGH:
            return True

        if decision == CoachingDecision.EXPLORE:
            if self._conversation_state in _EXPLORE_ALLOWED:
                self._conversation_state = ConversationState.EXPLORE
                return True
            return False

        if decision == CoachingDecision.SUGGEST:
            if self._conversation_state in _SUGGEST_ALLOWED:
                self._conversation_state = ConversationState.PRACTICE_OFFERED
                return True
            return False

        return False  # pragma: no cover – unknown decision

    # ------------------------------------------------------------------
    # Practice lifecycle
    # ------------------------------------------------------------------

    def accept_practice(self) -> bool:
        """User accepts the offered practice."""
        if self._conversation_state != ConversationState.PRACTICE_OFFERED:
            return False
        self._conversation_state = ConversationState.PRACTICE_ACTIVE
        self._practice_state = PracticeState.CONSENT
        return True

    def decline_practice(self) -> bool:
        """User declines the offered practice."""
        if self._conversation_state != ConversationState.PRACTICE_OFFERED:
            return False
        self._conversation_state = ConversationState.FREE_CHAT
        return True

    def pause_practice(self) -> bool:
        """Pause the active practice."""
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        self._conversation_state = ConversationState.PRACTICE_PAUSED
        return True

    def resume_practice(self) -> bool:
        """Resume a paused practice."""
        if self._conversation_state != ConversationState.PRACTICE_PAUSED:
            return False
        self._conversation_state = ConversationState.PRACTICE_ACTIVE
        return True

    def complete_practice(self) -> bool:
        """Mark the active practice as complete."""
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        self._conversation_state = ConversationState.FOLLOW_UP
        self._practice_state = None
        return True

    def advance_practice_step(self, next_step: str) -> bool:
        """Move to the next inner practice step.

        Returns ``False`` if the FSM is not in PRACTICE_ACTIVE or if
        *next_step* is not a valid ``PracticeState`` member.
        """
        if self._conversation_state != ConversationState.PRACTICE_ACTIVE:
            return False
        try:
            self._practice_state = PracticeState(next_step)
        except ValueError:
            return False
        return True

    # ------------------------------------------------------------------
    # Crisis
    # ------------------------------------------------------------------

    def enter_crisis(self) -> bool:
        """Immediately enter crisis state from any state."""
        self._conversation_state = ConversationState.CRISIS
        self._practice_state = None
        return True

    def stabilize_from_crisis(self) -> bool:
        """Transition out of crisis back to free chat."""
        if self._conversation_state != ConversationState.CRISIS:
            return False
        self._conversation_state = ConversationState.FREE_CHAT
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize both state layers to a plain dict."""
        return {
            "conversation_state": self._conversation_state.value,
            "practice_state": (
                self._practice_state.value if self._practice_state is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationFSM:
        """Restore an FSM from a previously serialized dict."""
        fsm = cls()
        fsm._conversation_state = ConversationState(data["conversation_state"])
        raw_practice = data.get("practice_state")
        fsm._practice_state = (
            PracticeState(raw_practice) if raw_practice is not None else None
        )
        return fsm
