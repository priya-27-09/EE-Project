"""
AI Civic Guardian — Centralized Translation Service
Handles translation lookups, language validation, text processing, and translation adapters.
"""

import logging
import unicodedata
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from app.i18n.constants import (
    LANG_EN,
    LANG_TA,
    LANG_HI,
    DEFAULT_LANGUAGE,
    FALLBACK_LANGUAGE,
    SUPPORTED_LANGUAGES,
    LANGUAGE_METADATA,
    TRANSLATIONS,
    ISSUE_TRANSLATIONS,
    DEPARTMENT_TRANSLATIONS,
    STATUS_TRANSLATIONS,
    SEVERITY_TRANSLATIONS,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# Translation Provider Interface (Pluggable Adapter Pattern)
# -------------------------------------------------------------

class BaseTranslationProvider(ABC):
    """Abstract interface for external translation service adapters."""

    @abstractmethod
    def translate_text(
        self, text: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        """
        Translate text from source_lang to target_lang.
        Must return None if provider is unconfigured or unable to translate.
        Must NEVER return fabricated/fake translations.
        """
        pass


class NullTranslationProvider(BaseTranslationProvider):
    """
    Default unconfigured translation provider.
    Strictly returns None to guarantee no fake machine translation is performed.
    """

    def translate_text(
        self, text: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        return None


# -------------------------------------------------------------
# Core Translation Service
# -------------------------------------------------------------

class TranslationService:
    """Centralized translation and multilingual text management service."""

    _provider: BaseTranslationProvider = NullTranslationProvider()

    @classmethod
    def set_provider(cls, provider: BaseTranslationProvider) -> None:
        """Register a translation provider adapter."""
        cls._provider = provider

    @classmethod
    def get_supported_languages(cls) -> List[Dict[str, str]]:
        """Return list of supported languages with code, name, and native script name."""
        return list(LANGUAGE_METADATA)

    @classmethod
    def is_supported(cls, lang_code: Optional[str]) -> bool:
        """Check whether a language code is officially supported."""
        if not lang_code:
            return False
        return lang_code.strip().lower() in SUPPORTED_LANGUAGES

    @classmethod
    def validate_language(cls, lang_code: Optional[str], strict: bool = False) -> str:
        """
        Validate and normalize a language code.
        If unsupported and not strict, gracefully returns DEFAULT_LANGUAGE ('en').
        If strict and unsupported, raises ValueError.
        """
        if not lang_code:
            return DEFAULT_LANGUAGE
        norm = lang_code.strip().lower()
        if norm in SUPPORTED_LANGUAGES:
            return norm
        if strict:
            raise ValueError(
                f"Unsupported language code '{lang_code}'. Supported languages are: {sorted(list(SUPPORTED_LANGUAGES))}"
            )
        logger.warning(
            "Unsupported language '%s' requested. Gracefully falling back to '%s'.",
            lang_code,
            DEFAULT_LANGUAGE,
        )
        return DEFAULT_LANGUAGE

    @classmethod
    def t(cls, key: str, lang: Optional[str] = None) -> str:
        """
        Lookup a translation string by key and language.
        Fallback order:
        1. Requested language dictionary
        2. English fallback dictionary
        3. Raw key string (with dev logger warning)
        """
        target_lang = cls.validate_language(lang)

        # 1. Target language dictionary
        lang_dict = TRANSLATIONS.get(target_lang, {})
        if key in lang_dict:
            return lang_dict[key]

        # 2. English fallback
        if target_lang != FALLBACK_LANGUAGE:
            en_dict = TRANSLATIONS.get(FALLBACK_LANGUAGE, {})
            if key in en_dict:
                return en_dict[key]

        # 3. Safe fallback to key with warning
        logger.warning("Missing translation key '%s' for language '%s'.", key, target_lang)
        return key

    @classmethod
    def get_translations(cls, lang: Optional[str] = None) -> Dict[str, str]:
        """Return the complete translation catalog dictionary for a language."""
        target_lang = cls.validate_language(lang)
        # Merge English baseline with target language overrides
        merged = dict(TRANSLATIONS.get(FALLBACK_LANGUAGE, {}))
        merged.update(TRANSLATIONS.get(target_lang, {}))
        return merged

    @classmethod
    def translate_issue(cls, issue_type: str, lang: Optional[str] = None) -> str:
        """Translate a canonical 12-class civic issue identifier for display."""
        target_lang = cls.validate_language(lang)
        canon = (issue_type or "").strip().lower()
        entry = ISSUE_TRANSLATIONS.get(canon)
        if entry:
            return entry.get(target_lang) or entry.get(FALLBACK_LANGUAGE) or issue_type
        return issue_type

    @classmethod
    def translate_department(cls, dept_name: str, lang: Optional[str] = None) -> str:
        """Translate a municipal department name for display."""
        target_lang = cls.validate_language(lang)
        clean = (dept_name or "").strip()
        entry = DEPARTMENT_TRANSLATIONS.get(clean)
        if entry:
            return entry.get(target_lang) or entry.get(FALLBACK_LANGUAGE) or dept_name
        return dept_name

    @classmethod
    def translate_status(cls, status: str, lang: Optional[str] = None) -> str:
        """Translate a complaint status enum value for display."""
        target_lang = cls.validate_language(lang)
        clean = (status or "").strip().upper()
        entry = STATUS_TRANSLATIONS.get(clean)
        if entry:
            return entry.get(target_lang) or entry.get(FALLBACK_LANGUAGE) or status
        return status

    @classmethod
    def translate_severity(cls, severity: str, lang: Optional[str] = None) -> str:
        """Translate a severity level for display."""
        target_lang = cls.validate_language(lang)
        clean = (severity or "").strip().upper()
        entry = SEVERITY_TRANSLATIONS.get(clean)
        if entry:
            return entry.get(target_lang) or entry.get(FALLBACK_LANGUAGE) or severity
        return severity

    @classmethod
    def prepare_processed_text(
        cls, original_text: Optional[str], lang: Optional[str] = None
    ) -> str:
        """
        Normalize citizen complaint text for downstream search/duplicate detection.
        - Preserves all letters, numbers, and Unicode combining marks (matras / vowels in Tamil and Hindi).
        - Replaces Unicode punctuation and symbols with single spaces.
        - Collapses consecutive whitespace.
        - Lowercases ASCII letters.
        - Strictly leaves original citizen text unaltered in the original_text database field.
        """
        if not original_text:
            return ""

        # Normalize whitespace and lowercase ASCII
        text = original_text.strip().lower()

        # Unicode character filtering: keep letters (L), marks/matras (M), numbers (N), and spaces
        cleaned_chars = []
        for char in text:
            cat = unicodedata.category(char)
            if cat.startswith(("P", "S")):  # Punctuation or Symbols
                cleaned_chars.append(" ")
            else:
                cleaned_chars.append(char)

        cleaned = "".join(cleaned_chars)
        # Collapse multiple spaces to single space
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def generate_translated_text(
        cls, text: str, source_lang: str, target_lang: str = LANG_EN
    ) -> Optional[str]:
        """
        Attempt translation using registered translation provider.
        Returns None if provider is unconfigured. Never generates fake translations.
        """
        if not text or source_lang == target_lang:
            return None
        return cls._provider.translate_text(text, source_lang, target_lang)
