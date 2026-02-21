# tests/test_practice_catalog.py
"""Test that all v1 practice YAML files pass validation."""
import pytest
from pathlib import Path
from wellness_bot.protocol.practice_loader import PracticeLoader

PRACTICES_DIR = Path(__file__).parent.parent.parent.parent / "packs" / "wellness-cbt" / "practices"


class TestPracticeCatalog:
    @pytest.fixture
    def loader(self):
        assert PRACTICES_DIR.exists(), f"Practices dir not found: {PRACTICES_DIR}"
        return PracticeLoader(practices_dir=PRACTICES_DIR)

    def test_all_12_practices_load(self, loader):
        practices = loader.load_all()
        expected_ids = {"M2", "M3", "A1", "A2", "A3", "A6", "C1", "C2", "C3", "C5", "B1", "U2"}
        assert set(practices.keys()) == expected_ids

    def test_all_have_steps(self, loader):
        for pid, p in loader.load_all().items():
            assert len(p.steps) >= 1, f"{pid} has no steps"

    def test_all_steps_have_fallbacks(self, loader):
        for pid, p in loader.load_all().items():
            for step in p.steps:
                assert "user_confused" in step.fallback, f"{pid} step {step.index} missing user_confused"
                assert "cannot_now" in step.fallback, f"{pid} step {step.index} missing cannot_now"
                assert "too_hard" in step.fallback, f"{pid} step {step.index} missing too_hard"

    def test_step_indices_continuous(self, loader):
        for pid, p in loader.load_all().items():
            indices = [s.index for s in p.steps]
            assert indices == list(range(1, len(indices) + 1)), f"{pid} has non-continuous indices"

    def test_priority_ranks_unique(self, loader):
        practices = loader.load_all()
        ranks = [p.priority_rank for p in practices.values()]
        assert len(ranks) == len(set(ranks)), "Duplicate priority_rank found"
