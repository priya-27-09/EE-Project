"""
Pydantic Schemas for Multilingual Support
"""

from typing import List, Dict
from pydantic import BaseModel, Field


class LanguageItem(BaseModel):
    code: str = Field(..., description="ISO 639-1 language code (e.g., en, ta, hi)")
    name: str = Field(..., description="English name of the language")
    native_name: str = Field(..., description="Native script name of the language")


class LanguageListResponse(BaseModel):
    languages: List[LanguageItem] = Field(..., description="List of officially supported languages")


class TranslationCatalogResponse(BaseModel):
    language: str = Field(..., description="Language code")
    translations: Dict[str, str] = Field(..., description="Key-value translation dictionary")
