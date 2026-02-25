"""Language resolver with session caching.

Step 2 of the coaching pipeline. Detects the user's language from
message text using Unicode script ranges, caches the result per user,
and supports explicit language overrides.
"""

from __future__ import annotations

import re


# ── Unicode script ranges ────────────────────────────────────────────────
_SCRIPT_RANGES: list[tuple[str, re.Pattern[str]]] = [
    ("ru", re.compile(r"[\u0400-\u04FF]")),
    ("ar", re.compile(r"[\u0600-\u06FF]")),
    ("zh", re.compile(r"[\u4E00-\u9FFF]")),
    ("ja", re.compile(r"[\u3040-\u30FF]")),
    ("ko", re.compile(r"[\uAC00-\uD7AF]")),
    ("he", re.compile(r"[\u0590-\u05FF]")),
    ("en", re.compile(r"[A-Za-z]")),
]

# ── Hint words for Latin-script languages ────────────────────────────────
_HINT_WORDS: dict[str, list[str]] = {
    "es": ["hola", "cómo", "estás", "gracias", "quiero", "puedo", "tengo", "bueno"],
    "fr": ["bonjour", "comment", "merci", "je suis", "oui", "non", "très"],
    "de": ["hallo", "danke", "ich bin", "wie", "bitte", "guten"],
    "pt": ["olá", "obrigado", "obrigada", "como", "estou", "bom", "muito"],
}


class LanguageResolver:
    """Detects language from user text, caches per session, supports overrides."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def detect(self, text: str) -> str:
        """Detect language from text using Unicode script ranges.

        Args:
            text: User message text.

        Returns:
            ISO 639-1 language code.
        """
        if not text or not text.strip():
            return "en"

        # Count characters per script.
        counts: dict[str, int] = {}
        for lang, pattern in _SCRIPT_RANGES:
            count = len(pattern.findall(text))
            if count > 0:
                counts[lang] = count

        if not counts:
            return "en"

        dominant = max(counts, key=lambda k: counts[k])

        # If Latin-dominant, try hint words for specific languages.
        if dominant == "en":
            text_lower = text.lower()
            best_lang = "en"
            best_hits = 0
            for lang, words in _HINT_WORDS.items():
                hits = sum(1 for w in words if w in text_lower)
                if hits > best_hits:
                    best_hits = hits
                    best_lang = lang
            return best_lang

        return dominant

    def resolve(self, user_id: str, text: str) -> str:
        """Detect language, cache, and return.

        For short texts (< 4 chars) or empty texts, returns the cached
        language or 'en' as default.

        Args:
            user_id: Unique user identifier.
            text: User message text.

        Returns:
            ISO 639-1 language code.
        """
        if not text or not text.strip() or len(text.strip()) < 4:
            return self._cache.get(user_id, "en")

        lang = self.detect(text)
        self._cache[user_id] = lang
        return lang

    def get_cached(self, user_id: str) -> str | None:
        """Return cached language for user, or None if not cached.

        Args:
            user_id: Unique user identifier.

        Returns:
            Cached ISO 639-1 code or None.
        """
        return self._cache.get(user_id)

    def set_language(self, user_id: str, language: str) -> None:
        """Explicitly set language for user, overriding detection.

        Args:
            user_id: Unique user identifier.
            language: ISO 639-1 language code to set.
        """
        self._cache[user_id] = language
