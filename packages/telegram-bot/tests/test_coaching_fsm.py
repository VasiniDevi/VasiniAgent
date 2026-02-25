"""Tests for 2-level conversation + practice FSM."""

import pytest

from wellness_bot.coaching.fsm import ConversationFSM
from wellness_bot.protocol.types import (
    ConversationState,
    CoachingDecision,
    PracticeState,
)


@pytest.fixture
def fsm() -> ConversationFSM:
    return ConversationFSM()


class TestInitialState:
    """FSM starts in FREE_CHAT with no practice state."""

    def test_initial_conversation_state(self, fsm: ConversationFSM) -> None:
        assert fsm.conversation_state == ConversationState.FREE_CHAT

    def test_initial_practice_state_is_none(self, fsm: ConversationFSM) -> None:
        assert fsm.practice_state is None


class TestExploreTransition:
    """FREE_CHAT -> EXPLORE via EXPLORE decision."""

    def test_free_chat_to_explore(self, fsm: ConversationFSM) -> None:
        result = fsm.transition(CoachingDecision.EXPLORE)
        assert result is True
        assert fsm.conversation_state == ConversationState.EXPLORE

    def test_follow_up_to_explore(self, fsm: ConversationFSM) -> None:
        # Get to FOLLOW_UP: offer -> accept -> complete
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        fsm.complete_practice()
        assert fsm.conversation_state == ConversationState.FOLLOW_UP
        result = fsm.transition(CoachingDecision.EXPLORE)
        assert result is True
        assert fsm.conversation_state == ConversationState.EXPLORE


class TestSuggestTransition:
    """FREE_CHAT -> PRACTICE_OFFERED via SUGGEST decision."""

    def test_free_chat_to_practice_offered(self, fsm: ConversationFSM) -> None:
        result = fsm.transition(CoachingDecision.SUGGEST)
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_OFFERED

    def test_explore_to_practice_offered(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.EXPLORE)
        result = fsm.transition(CoachingDecision.SUGGEST)
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_OFFERED

    def test_follow_up_to_practice_offered(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        fsm.complete_practice()
        assert fsm.conversation_state == ConversationState.FOLLOW_UP
        result = fsm.transition(CoachingDecision.SUGGEST)
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_OFFERED


class TestPassthroughDecisions:
    """LISTEN, ANSWER, GUIDE don't change state but return True."""

    @pytest.mark.parametrize(
        "decision",
        [CoachingDecision.LISTEN, CoachingDecision.ANSWER, CoachingDecision.GUIDE],
    )
    def test_passthrough_keeps_state(
        self, fsm: ConversationFSM, decision: CoachingDecision
    ) -> None:
        result = fsm.transition(decision)
        assert result is True
        assert fsm.conversation_state == ConversationState.FREE_CHAT

    @pytest.mark.parametrize(
        "decision",
        [CoachingDecision.LISTEN, CoachingDecision.ANSWER, CoachingDecision.GUIDE],
    )
    def test_passthrough_from_explore(
        self, fsm: ConversationFSM, decision: CoachingDecision
    ) -> None:
        fsm.transition(CoachingDecision.EXPLORE)
        result = fsm.transition(decision)
        assert result is True
        assert fsm.conversation_state == ConversationState.EXPLORE


class TestAcceptPractice:
    """PRACTICE_OFFERED -> PRACTICE_ACTIVE with CONSENT practice state."""

    def test_accept_practice_transitions(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        result = fsm.accept_practice()
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE
        assert fsm.practice_state == PracticeState.CONSENT

    def test_accept_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.accept_practice()
        assert result is False
        assert fsm.conversation_state == ConversationState.FREE_CHAT


class TestDeclinePractice:
    """PRACTICE_OFFERED -> FREE_CHAT on decline."""

    def test_decline_practice_returns_to_free_chat(
        self, fsm: ConversationFSM
    ) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        result = fsm.decline_practice()
        assert result is True
        assert fsm.conversation_state == ConversationState.FREE_CHAT

    def test_decline_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.decline_practice()
        assert result is False


class TestPausedResumed:
    """PRACTICE_ACTIVE <-> PRACTICE_PAUSED."""

    def test_pause_practice(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.pause_practice()
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_PAUSED

    def test_resume_practice(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        fsm.pause_practice()
        result = fsm.resume_practice()
        assert result is True
        assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE

    def test_pause_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.pause_practice()
        assert result is False

    def test_resume_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.resume_practice()
        assert result is False


class TestCrisis:
    """Crisis from any state, stabilize back to FREE_CHAT."""

    def test_crisis_from_free_chat(self, fsm: ConversationFSM) -> None:
        result = fsm.enter_crisis()
        assert result is True
        assert fsm.conversation_state == ConversationState.CRISIS
        assert fsm.practice_state is None

    def test_crisis_from_practice_active(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        fsm.advance_practice_step("STEP")
        result = fsm.enter_crisis()
        assert result is True
        assert fsm.conversation_state == ConversationState.CRISIS
        assert fsm.practice_state is None

    def test_crisis_from_explore(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.EXPLORE)
        result = fsm.enter_crisis()
        assert result is True
        assert fsm.conversation_state == ConversationState.CRISIS

    def test_stabilize_from_crisis(self, fsm: ConversationFSM) -> None:
        fsm.enter_crisis()
        result = fsm.stabilize_from_crisis()
        assert result is True
        assert fsm.conversation_state == ConversationState.FREE_CHAT

    def test_stabilize_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.stabilize_from_crisis()
        assert result is False


class TestPracticeStepAdvance:
    """advance_practice_step sets practice_state when active."""

    def test_advance_step(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.advance_practice_step("STEP")
        assert result is True
        assert fsm.practice_state == PracticeState.STEP

    def test_advance_to_checkpoint(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.advance_practice_step("CHECKPOINT")
        assert result is True
        assert fsm.practice_state == PracticeState.CHECKPOINT

    def test_advance_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.advance_practice_step("STEP")
        assert result is False

    def test_advance_with_invalid_step_fails(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.advance_practice_step("INVALID_STEP_NAME")
        assert result is False


class TestPracticeCompletion:
    """PRACTICE_ACTIVE -> FOLLOW_UP on completion."""

    def test_complete_practice(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.complete_practice()
        assert result is True
        assert fsm.conversation_state == ConversationState.FOLLOW_UP
        assert fsm.practice_state is None

    def test_complete_from_wrong_state_fails(self, fsm: ConversationFSM) -> None:
        result = fsm.complete_practice()
        assert result is False


class TestInvalidTransitions:
    """Invalid transitions return False without changing state."""

    def test_suggest_from_practice_active(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.transition(CoachingDecision.SUGGEST)
        assert result is False
        assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE

    def test_explore_from_practice_active(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        result = fsm.transition(CoachingDecision.EXPLORE)
        assert result is False
        assert fsm.conversation_state == ConversationState.PRACTICE_ACTIVE

    def test_suggest_from_crisis(self, fsm: ConversationFSM) -> None:
        fsm.enter_crisis()
        result = fsm.transition(CoachingDecision.SUGGEST)
        assert result is False
        assert fsm.conversation_state == ConversationState.CRISIS

    def test_explore_from_crisis(self, fsm: ConversationFSM) -> None:
        fsm.enter_crisis()
        result = fsm.transition(CoachingDecision.EXPLORE)
        assert result is False
        assert fsm.conversation_state == ConversationState.CRISIS


class TestSerialization:
    """to_dict / from_dict round-trip."""

    def test_round_trip_free_chat(self, fsm: ConversationFSM) -> None:
        data = fsm.to_dict()
        restored = ConversationFSM.from_dict(data)
        assert restored.conversation_state == ConversationState.FREE_CHAT
        assert restored.practice_state is None

    def test_round_trip_practice_active(self, fsm: ConversationFSM) -> None:
        fsm.transition(CoachingDecision.SUGGEST)
        fsm.accept_practice()
        fsm.advance_practice_step("STEP")
        data = fsm.to_dict()
        restored = ConversationFSM.from_dict(data)
        assert restored.conversation_state == ConversationState.PRACTICE_ACTIVE
        assert restored.practice_state == PracticeState.STEP

    def test_to_dict_keys(self, fsm: ConversationFSM) -> None:
        data = fsm.to_dict()
        assert "conversation_state" in data
        assert "practice_state" in data
