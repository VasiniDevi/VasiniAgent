# tests/test_practice_loader.py
"""Tests for YAML practice loader with validation."""
import pytest
from pathlib import Path
from wellness_bot.protocol.practice_loader import PracticeLoader, Practice, PracticeValidationError


@pytest.fixture
def loader(tmp_path):
    return PracticeLoader(practices_dir=tmp_path)


@pytest.fixture
def valid_yaml(tmp_path):
    content = """
id: U2
version: "1.0"
step_schema_hash: "sha256:test"
name_ru: "3-3-3 заземление"
name_en: "3-3-3 Grounding"
category: micro
goal: "Прервать руминацию через сенсорный якорь"
duration_min: 1
duration_max: 1
priority_rank: 1

prerequisites:
  needs_formulation: false
  min_time_budget: 1
  min_readiness: precontemplation

safety_overrides:
  blocked_in_caution_elevated: false
  blocked_if_distress_gte: null

maintaining_cycles: []

steps:
  - index: 1
    instruction_ru: "Назовите 3 вещи, которые видите."
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "Просто посмотрите вокруг и назовите 3 предмета."
      cannot_now: "Ничего, попробуем позже."
      too_hard: "Начните с одной вещи."
  - index: 2
    instruction_ru: "Назовите 3 звука."
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "Прислушайтесь. Какие звуки слышите?"
      cannot_now: "Хорошо, пропустим."
      too_hard: "Назовите хотя бы один звук."
  - index: 3
    instruction_ru: "Назовите 3 ощущения в теле."
    ui_mode: buttons
    buttons:
      - label: "Готово"
        action: next
    checkpoint: true
    fallback:
      user_confused: "Что чувствуете? Тепло, холод, давление?"
      cannot_now: "Не страшно. Главное — вы попробовали."
      too_hard: "Просто отметьте одно ощущение."

outcome:
  pre_rating: {type: rating, label: "Тревога", scale: "0-10"}
  post_rating: {type: rating, label: "Тревога", scale: "0-10"}
  completed: true
  drop_reason: null
  tracking: null

resume_compatibility:
  practice_id: U2
  version: "1.0"
  step_schema_hash: "sha256:test"
"""
    (tmp_path / "U2-grounding.yaml").write_text(content)
    return tmp_path


class TestPracticeLoader:
    def test_load_valid_practice(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        assert "U2" in practices
        p = practices["U2"]
        assert p.name_ru == "3-3-3 заземление"
        assert len(p.steps) == 3

    def test_step_index_continuity(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        p = practices["U2"]
        indices = [s.index for s in p.steps]
        assert indices == [1, 2, 3]

    def test_all_fallback_keys_present(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        for step in practices["U2"].steps:
            assert "user_confused" in step.fallback
            assert "cannot_now" in step.fallback
            assert "too_hard" in step.fallback

    def test_button_action_enum_validated(self, valid_yaml):
        loader = PracticeLoader(practices_dir=valid_yaml)
        practices = loader.load_all()
        step3 = practices["U2"].steps[2]
        assert step3.buttons[0]["action"] == "next"

    def test_missing_fallback_key_fails(self, tmp_path):
        bad = """
id: BAD
version: "1.0"
step_schema_hash: "sha256:bad"
name_ru: "Bad"
name_en: "Bad"
category: micro
goal: "test"
duration_min: 1
duration_max: 1
priority_rank: 99
prerequisites: {needs_formulation: false, min_time_budget: 1, min_readiness: precontemplation}
safety_overrides: {blocked_in_caution_elevated: false, blocked_if_distress_gte: null}
maintaining_cycles: []
steps:
  - index: 1
    instruction_ru: "Test"
    ui_mode: text
    checkpoint: false
    fallback:
      user_confused: "ok"
outcome: {pre_rating: null, post_rating: null, completed: true, drop_reason: null, tracking: null}
resume_compatibility: {practice_id: BAD, version: "1.0", step_schema_hash: "sha256:bad"}
"""
        (tmp_path / "BAD-test.yaml").write_text(bad)
        loader = PracticeLoader(practices_dir=tmp_path)
        with pytest.raises(PracticeValidationError, match="fallback"):
            loader.load_all()

    def test_step_index_gap_fails(self, tmp_path):
        bad = """
id: GAP
version: "1.0"
step_schema_hash: "sha256:gap"
name_ru: "Gap"
name_en: "Gap"
category: micro
goal: "test"
duration_min: 1
duration_max: 1
priority_rank: 99
prerequisites: {needs_formulation: false, min_time_budget: 1, min_readiness: precontemplation}
safety_overrides: {blocked_in_caution_elevated: false, blocked_if_distress_gte: null}
maintaining_cycles: []
steps:
  - index: 1
    instruction_ru: "Step 1"
    ui_mode: text
    checkpoint: false
    fallback: {user_confused: "a", cannot_now: "b", too_hard: "c"}
  - index: 3
    instruction_ru: "Step 3 (gap!)"
    ui_mode: text
    checkpoint: false
    fallback: {user_confused: "a", cannot_now: "b", too_hard: "c"}
outcome: {pre_rating: null, post_rating: null, completed: true, drop_reason: null, tracking: null}
resume_compatibility: {practice_id: GAP, version: "1.0", step_schema_hash: "sha256:gap"}
"""
        (tmp_path / "GAP-test.yaml").write_text(bad)
        loader = PracticeLoader(practices_dir=tmp_path)
        with pytest.raises(PracticeValidationError, match="continuity"):
            loader.load_all()
