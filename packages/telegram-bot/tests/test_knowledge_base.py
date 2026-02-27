# tests/test_knowledge_base.py
"""Tests for KnowledgeBaseCompiler."""
from pathlib import Path

from wellness_bot.coaching.knowledge_base import KnowledgeBaseCompiler

_PRACTICES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "packs" / "wellness-cbt" / "practices"


class TestKnowledgeBaseCompiler:
    def test_compile_includes_all_practices(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile()
        assert "M1" in prompt
        assert "R3" in prompt
        assert "U6" in prompt
        assert "30" in prompt  # "Всего: 30 практик"

    def test_compile_includes_personality(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile()
        assert "подлизывания" in prompt or "подлизывание" in prompt
        assert "честно" in prompt.lower() or "Честно" in prompt

    def test_compile_includes_theory(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile()
        assert "CBT" in prompt
        assert "MCT" in prompt
        assert "метакогнитивн" in prompt

    def test_compile_includes_decision_rules(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile()
        assert "Руминация" in prompt
        assert "дистресс" in prompt.lower() or "Дистресс" in prompt

    def test_compile_includes_safety(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile()
        assert "ВСЕГДА помогай" in prompt
        assert "НИКОГДА не отказывай" in prompt

    def test_compile_with_user_context(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile(user_context={
            "last_practice": "A2",
            "current_mode": "exploring",
            "safety_level": "green",
        })
        assert "A2" in prompt
        assert "exploring" in prompt
        assert "green" in prompt

    def test_compile_checkin_prompt(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt = kb.compile_checkin_prompt()
        assert "check-in" in prompt.lower() or "чек-ин" in prompt.lower()
        assert "ВСЕГДА помогай" in prompt

    def test_practices_cached(self):
        kb = KnowledgeBaseCompiler(_PRACTICES_DIR)
        prompt1 = kb.compile()
        prompt2 = kb.compile()
        assert prompt1 == prompt2
