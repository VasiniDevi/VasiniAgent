"""Voice + style validator for LLM-generated responses."""
from __future__ import annotations

from dataclasses import dataclass

from wellness_bot.protocol.types import RiskLevel


@dataclass
class StyleValidationInput:
    text: str
    risk_level: RiskLevel
    user_tone_playful: bool
    long_form_requested: bool
    max_sentences: int = 3
    max_questions: int = 1
    max_chars_short: int = 500
    max_chars_long: int = 1400


@dataclass
class CheckResult:
    passed: bool
    code: str
    reason: str | None = None


BANNED_SAFETY = [
    "у вас депрессия", "у вас биполяр", "прими", "таблетк", "дозировк",
    "как причинить себе", "how to harm yourself"
]

SARCASM_MARKERS = ["ну да, конечно", "гениально", "супер идея", "brilliant", "sure, great"]
EMPATHY_MARKERS = ["понимаю", "это тяжело", "слышу вас", "вижу, что", "you're not alone"]
CTA_MARKERS = ["хотите", "давайте", "готовы", "оцените", "?"]


def validate_style(inp: StyleValidationInput) -> list[CheckResult]:
    t = inp.text.strip().lower()
    results = []

    # 1) Length
    max_chars = inp.max_chars_long if inp.long_form_requested else inp.max_chars_short
    results.append(CheckResult(len(inp.text) <= max_chars, "length"))

    # 2) Sentence count
    sent_count = sum(inp.text.count(x) for x in [".", "!", "?"])
    results.append(CheckResult(sent_count <= inp.max_sentences, "sentence_limit"))

    # 3) Question count
    q_count = inp.text.count("?")
    results.append(CheckResult(q_count <= inp.max_questions, "question_limit"))

    # 4) Empathy present
    has_empathy = any(m in t for m in EMPATHY_MARKERS)
    results.append(CheckResult(has_empathy, "empathy_present"))

    # 5) Clear CTA present
    has_cta = any(m in t for m in CTA_MARKERS)
    results.append(CheckResult(has_cta, "cta_present"))

    # 6) No banned safety content
    banned_hit = next((b for b in BANNED_SAFETY if b in t), None)
    results.append(CheckResult(banned_hit is None, "no_banned_content", banned_hit))

    # 7) Sarcasm gating
    has_sarcasm = any(m in t for m in SARCASM_MARKERS)
    sarcasm_allowed = (inp.risk_level == RiskLevel.SAFE and inp.user_tone_playful)
    results.append(CheckResult((not has_sarcasm) or sarcasm_allowed, "sarcasm_gate"))

    # 8) No playful tone in elevated risk
    if inp.risk_level in {RiskLevel.CAUTION_ELEVATED, RiskLevel.CRISIS}:
        results.append(CheckResult(not has_sarcasm, "no_playful_high_risk"))
    else:
        results.append(CheckResult(True, "no_playful_high_risk"))

    # 9) One-step actionability (simple heuristic)
    action_markers = ["сделайте", "напишите", "оцените", "выберите", "назовите", "tell me", "rate", "choose"]
    action_count = sum(1 for m in action_markers if m in t)
    results.append(CheckResult(action_count >= 1 and action_count <= 2, "actionable_one_step"))

    return results
