"""Tests for scenario protocol definitions and matcher."""

from wellness_bot.coaching.scenarios import (
    SCENARIOS,
    ScenarioMatcher,
    ScenarioProtocol,
)


class TestScenarioDefinitions:
    def test_all_six_scenarios_defined(self):
        assert set(SCENARIOS.keys()) == {
            "GAD", "RUMINATION", "PROCRASTINATION",
            "SOCIAL_ANXIETY", "LOW_MOOD", "INSOMNIA",
        }

    def test_each_scenario_has_three_phases(self):
        for sid, s in SCENARIOS.items():
            assert len(s.phases) == 3, f"{sid} should have 3 phases"

    def test_phases_are_stabilization_skill_consolidation(self):
        for sid, s in SCENARIOS.items():
            names = [p.name for p in s.phases]
            assert names == ["stabilization", "skill_building", "consolidation"], (
                f"{sid} phases should be stabilization → skill_building → consolidation"
            )

    def test_each_scenario_has_maintaining_cycles(self):
        for sid, s in SCENARIOS.items():
            assert len(s.maintaining_cycles) >= 1, f"{sid} needs at least one cycle"

    def test_consolidation_includes_relapse_prevention(self):
        for sid, s in SCENARIOS.items():
            consolidation = s.phases[2]
            all_practices = consolidation.primary_practices + consolidation.secondary_practices
            has_relapse = any(p.startswith("R") for p in all_practices)
            assert has_relapse, f"{sid} consolidation should include relapse prevention"

    def test_stall_threshold_positive(self):
        for sid, s in SCENARIOS.items():
            assert s.stall_threshold > 0, f"{sid} stall_threshold must be positive"


class TestScenarioMatcher:
    def test_worry_maps_to_gad(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["worry"])
        assert result is not None
        assert result.id == "GAD"

    def test_rumination_maps_to_rumination(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["rumination"])
        assert result is not None
        assert result.id == "RUMINATION"

    def test_avoidance_maps_to_procrastination(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["avoidance"])
        assert result is not None
        assert result.id == "PROCRASTINATION"

    def test_insomnia_maps_to_insomnia(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["insomnia"])
        assert result is not None
        assert result.id == "INSOMNIA"

    def test_first_cycle_wins(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["worry", "rumination"])
        assert result is not None
        assert result.id == "GAD"

    def test_low_mood_fallback(self):
        matcher = ScenarioMatcher()
        result = matcher.match(mood=2.0)
        assert result is not None
        assert result.id == "LOW_MOOD"

    def test_high_anxiety_fallback(self):
        matcher = ScenarioMatcher()
        result = matcher.match(anxiety=0.8)
        assert result is not None
        assert result.id == "GAD"

    def test_no_match_returns_none(self):
        matcher = ScenarioMatcher()
        result = matcher.match()
        assert result is None

    def test_cycles_take_priority_over_mood(self):
        matcher = ScenarioMatcher()
        result = matcher.match(dominant_cycles=["insomnia"], mood=2.0)
        assert result is not None
        assert result.id == "INSOMNIA"
