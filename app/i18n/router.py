"""
FastAPI Router for Multilingual / i18n APIs
"""

from fastapi import APIRouter, HTTPException, status
from app.i18n.schemas import (
    LanguageItem,
    LanguageListResponse,
    TranslationCatalogResponse,
)
from app.i18n.translation_service import TranslationService
from app.i18n.constants import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

router = APIRouter(prefix="/api/v1/i18n", tags=["Multilingual"])


@router.get(
    "/languages",
    response_model=LanguageListResponse,
    summary="List officially supported languages",
)
def get_supported_languages():
    """
    Returns the list of officially supported languages with ISO codes,
    English names, and native script names (English, தமிழ், हिन्दी).
    """
    langs = [
        LanguageItem(
            code=item["code"],
            name=item["name"],
            native_name=item["native_name"],
        )
        for item in TranslationService.get_supported_languages()
    ]
    return LanguageListResponse(languages=langs)


@router.get(
    "/translations/{lang}",
    response_model=TranslationCatalogResponse,
    summary="Get translation catalog for a language",
)
def get_translations_for_language(lang: str):
    """
    Returns the key-value translation dictionary for the requested language code.
    If language is unsupported, gracefully falls back to default language ('en').
    """
    clean_lang = TranslationService.validate_language(lang)
    translations = TranslationService.get_translations(clean_lang)
    return TranslationCatalogResponse(
        language=clean_lang,
        translations=translations,
    )
