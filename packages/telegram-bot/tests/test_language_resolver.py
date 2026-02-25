"""Tests for language resolver with session caching."""

import pytest

from wellness_bot.coaching.language_resolver import LanguageResolver


@pytest.fixture
def resolver() -> LanguageResolver:
    return LanguageResolver()


class TestDetectRussian:
    """Russian (Cyrillic) text should be detected as 'ru'."""

    def test_russian_greeting(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Привет, как дела?") == "ru"

    def test_russian_sentence(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Сегодня хороший день") == "ru"

    def test_russian_long(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Я хочу записаться на практику медитации") == "ru"


class TestDetectEnglish:
    """English (Latin, no hint words) should be detected as 'en'."""

    def test_english_greeting(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Hello, how are you?") == "en"

    def test_english_sentence(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("I had a great day today") == "en"

    def test_english_long(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Today I want to practice mindfulness meditation") == "en"


class TestDetectSpanish:
    """Spanish hint words in Latin text should be detected as 'es'."""

    def test_spanish_hola(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Hola, cómo estás?") == "es"

    def test_spanish_gracias(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Muchas gracias por tu ayuda") == "es"

    def test_spanish_quiero(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Quiero practicar meditación") == "es"


class TestDetectFrench:
    """French hint words in Latin text should be detected as 'fr'."""

    def test_french_bonjour(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Bonjour, comment allez-vous?") == "fr"

    def test_french_merci(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Merci beaucoup pour votre aide") == "fr"


class TestDetectGerman:
    """German hint words in Latin text should be detected as 'de'."""

    def test_german_hallo(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Hallo, wie geht es Ihnen?") == "de"

    def test_german_danke(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Danke für Ihre Hilfe, bitte") == "de"


class TestDetectPortuguese:
    """Portuguese hint words in Latin text should be detected as 'pt'."""

    def test_portuguese_ola(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Olá, como você está?") == "pt"

    def test_portuguese_obrigado(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("Muito obrigado pela ajuda") == "pt"


class TestDetectOtherScripts:
    """Non-Latin scripts should be detected by Unicode ranges."""

    def test_arabic(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("مرحبا كيف حالك") == "ar"

    def test_chinese(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("你好世界今天天气很好") == "zh"

    def test_japanese(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("こんにちは、お元気ですか") == "ja"

    def test_korean(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("안녕하세요 오늘 기분이 좋아요") == "ko"

    def test_hebrew(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("שלום מה שלומך היום") == "he"


class TestDetectMixed:
    """Mixed-script text should return the dominant script."""

    def test_mostly_russian_with_english(self, resolver: LanguageResolver) -> None:
        result = resolver.detect("Привет, сегодня day хороший")
        assert result == "ru"

    def test_mostly_english_with_russian(self, resolver: LanguageResolver) -> None:
        result = resolver.detect("Hello today is a great day, привет")
        assert result == "en"

    def test_russian_dominates_mixed(self, resolver: LanguageResolver) -> None:
        result = resolver.detect("Я записался на практику meditation")
        assert result == "ru"


class TestDetectEmpty:
    """Empty or whitespace text should return 'en' default."""

    def test_empty_string(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("") == "en"

    def test_whitespace_only(self, resolver: LanguageResolver) -> None:
        assert resolver.detect("   ") == "en"


class TestCacheShortMessages:
    """Short messages (< 4 chars) should return cached language."""

    def test_short_returns_cached(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user1", "Привет, как у тебя дела?")
        assert resolver.resolve("user1", "да") == "ru"

    def test_short_returns_default_when_no_cache(self, resolver: LanguageResolver) -> None:
        assert resolver.resolve("user1", "ok") == "en"

    def test_short_exactly_3_chars(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user2", "Bonjour, comment ça va?")
        assert resolver.resolve("user2", "oui") == "fr"


class TestExplicitLanguageSwitch:
    """set_language should override cached language."""

    def test_override_cached(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user1", "Hello, how are you?")
        assert resolver.get_cached("user1") == "en"

        resolver.set_language("user1", "ru")
        assert resolver.get_cached("user1") == "ru"

    def test_override_persists_for_short_messages(self, resolver: LanguageResolver) -> None:
        resolver.set_language("user1", "es")
        assert resolver.resolve("user1", "si") == "es"


class TestGetCached:
    """get_cached returns None when no cache exists."""

    def test_no_cache(self, resolver: LanguageResolver) -> None:
        assert resolver.get_cached("unknown_user") is None

    def test_cached_after_resolve(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user1", "Привет, как дела?")
        assert resolver.get_cached("user1") == "ru"


class TestEmptyCachedOrDefault:
    """Empty text in resolve should return cached or default."""

    def test_empty_returns_cached(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user1", "Привет мир, как дела?")
        assert resolver.resolve("user1", "") == "ru"

    def test_empty_returns_default_no_cache(self, resolver: LanguageResolver) -> None:
        assert resolver.resolve("user1", "") == "en"


class TestResolveReturnsDetected:
    """resolve should detect, cache, and return the detected language."""

    def test_resolve_russian(self, resolver: LanguageResolver) -> None:
        result = resolver.resolve("user1", "Привет, как дела сегодня?")
        assert result == "ru"
        assert resolver.get_cached("user1") == "ru"

    def test_resolve_english(self, resolver: LanguageResolver) -> None:
        result = resolver.resolve("user2", "Hello, how are you doing today?")
        assert result == "en"
        assert resolver.get_cached("user2") == "en"

    def test_resolve_updates_cache(self, resolver: LanguageResolver) -> None:
        resolver.resolve("user1", "Hello, how are you?")
        assert resolver.get_cached("user1") == "en"

        resolver.resolve("user1", "Привет, как дела сегодня?")
        assert resolver.get_cached("user1") == "ru"

    def test_resolve_spanish(self, resolver: LanguageResolver) -> None:
        result = resolver.resolve("user3", "Hola, cómo estás hoy?")
        assert result == "es"
        assert resolver.get_cached("user3") == "es"
