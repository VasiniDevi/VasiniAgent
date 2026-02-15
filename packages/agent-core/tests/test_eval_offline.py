"""Tests for Evaluation Service — Offline quality gates."""

import pytest
from vasini.eval.runner import EvalRunner, EvalCase, EvalResult
from vasini.eval.scorer import QualityScorer, ScoreResult
from vasini.eval.gate import QualityGate, GateResult


class TestEvalCase:
    def test_create_eval_case(self):
        case = EvalCase(
            id="test-1",
            input="What is 2+2?",
            expected_output="4",
        )
        assert case.id == "test-1"
        assert case.input == "What is 2+2?"

    def test_eval_case_with_metadata(self):
        case = EvalCase(
            id="test-2",
            input="Hello",
            expected_output="Hi there",
            tags=["greeting"],
            metadata={"category": "chat"},
        )
        assert "greeting" in case.tags


class TestEvalRunner:
    @pytest.mark.asyncio
    async def test_run_single_case(self):
        async def mock_agent(input_text: str) -> str:
            return "4"

        runner = EvalRunner(agent_fn=mock_agent)
        case = EvalCase(id="t1", input="What is 2+2?", expected_output="4")
        result = await runner.run_case(case)
        assert result.case_id == "t1"
        assert result.actual_output == "4"
        assert result.expected_output == "4"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_dataset(self):
        async def mock_agent(input_text: str) -> str:
            return input_text.upper()

        runner = EvalRunner(agent_fn=mock_agent)
        cases = [
            EvalCase(id="t1", input="hello", expected_output="HELLO"),
            EvalCase(id="t2", input="world", expected_output="WORLD"),
            EvalCase(id="t3", input="test", expected_output="WRONG"),
        ]
        results = await runner.run_dataset(cases)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_run_captures_errors(self):
        async def failing_agent(input_text: str) -> str:
            raise ValueError("Agent error")

        runner = EvalRunner(agent_fn=failing_agent)
        case = EvalCase(id="t1", input="test", expected_output="result")
        result = await runner.run_case(case)
        assert result.error is not None
        assert "Agent error" in result.error


class TestQualityScorer:
    def test_exact_match_scores_1(self):
        scorer = QualityScorer()
        result = scorer.score(actual="hello", expected="hello")
        assert result.exact_match is True
        assert result.score == 1.0

    def test_no_match_scores_0(self):
        scorer = QualityScorer()
        result = scorer.score(actual="completely different", expected="hello")
        assert result.exact_match is False
        assert result.score < 1.0

    def test_partial_match_scores_between(self):
        scorer = QualityScorer()
        result = scorer.score(actual="hello world", expected="hello planet")
        assert 0.0 < result.score < 1.0

    def test_case_insensitive_exact(self):
        scorer = QualityScorer()
        result = scorer.score(actual="Hello", expected="hello")
        assert result.exact_match is True

    def test_empty_expected_edge_case(self):
        scorer = QualityScorer()
        result = scorer.score(actual="something", expected="")
        assert result.score == 0.0

    def test_aggregate_scores(self):
        scorer = QualityScorer()
        results = [
            scorer.score("a", "a"),      # 1.0
            scorer.score("b", "b"),      # 1.0
            scorer.score("c", "wrong"),  # < 1.0
        ]
        avg = scorer.aggregate(results)
        assert 0.5 < avg < 1.0

    def test_aggregate_empty_returns_zero(self):
        scorer = QualityScorer()
        assert scorer.aggregate([]) == 0.0


class TestQualityGate:
    def test_gate_passes_above_threshold(self):
        gate = QualityGate(min_score=0.85)
        result = gate.evaluate(score=0.90, total_cases=10, passed_cases=9)
        assert result.passed
        assert result.score == 0.90

    def test_gate_fails_below_threshold(self):
        gate = QualityGate(min_score=0.85)
        result = gate.evaluate(score=0.70, total_cases=10, passed_cases=7)
        assert not result.passed

    def test_gate_passes_at_exact_threshold(self):
        gate = QualityGate(min_score=0.85)
        result = gate.evaluate(score=0.85, total_cases=10, passed_cases=9)
        assert result.passed

    def test_gate_default_threshold(self):
        gate = QualityGate()
        assert gate.min_score == 0.85

    def test_gate_result_contains_summary(self):
        gate = QualityGate(min_score=0.85)
        result = gate.evaluate(score=0.60, total_cases=5, passed_cases=3)
        assert not result.passed
        assert result.total_cases == 5
        assert result.passed_cases == 3

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """End-to-end: runner → scorer → gate."""
        async def mock_agent(input_text: str) -> str:
            answers = {"What is 2+2?": "4", "Capital of France?": "Paris"}
            return answers.get(input_text, "I don't know")

        runner = EvalRunner(agent_fn=mock_agent)
        scorer = QualityScorer()
        gate = QualityGate(min_score=0.85)

        cases = [
            EvalCase(id="t1", input="What is 2+2?", expected_output="4"),
            EvalCase(id="t2", input="Capital of France?", expected_output="Paris"),
        ]

        results = await runner.run_dataset(cases)
        scores = [scorer.score(r.actual_output, r.expected_output) for r in results]
        avg_score = scorer.aggregate(scores)
        gate_result = gate.evaluate(score=avg_score, total_cases=len(cases), passed_cases=sum(1 for s in scores if s.exact_match))

        assert gate_result.passed
        assert gate_result.score >= 0.85
