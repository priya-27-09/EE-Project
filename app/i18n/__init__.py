"""
AI Civic Guardian — Multilingual Package
"""

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
from app.i18n.translation_service import (
    TranslationService,
    BaseTranslationProvider,
    NullTranslationProvider,
)
from app.i18n.schemas import (
    LanguageItem,
    LanguageListResponse,
    TranslationCatalogResponse,
)

t = TranslationService.t
translate_issue = TranslationService.translate_issue
translate_department = TranslationService.translate_department
translate_status = TranslationService.translate_status
translate_severity = TranslationService.translate_severity

__all__ = [
    "LANG_EN",
    "LANG_TA",
    "LANG_HI",
    "DEFAULT_LANGUAGE",
    "FALLBACK_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "LANGUAGE_METADATA",
    "TRANSLATIONS",
    "ISSUE_TRANSLATIONS",
    "DEPARTMENT_TRANSLATIONS",
    "STATUS_TRANSLATIONS",
    "SEVERITY_TRANSLATIONS",
    "TranslationService",
    "BaseTranslationProvider",
    "NullTranslationProvider",
    "LanguageItem",
    "LanguageListResponse",
    "TranslationCatalogResponse",
    "t",
    "translate_issue",
    "translate_department",
    "translate_status",
    "translate_severity",
]
