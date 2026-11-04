from datetime import datetime
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, field_validator

from app.complaints.constants import (
    VALID_ISSUE_TYPES,
    VALID_LANGUAGES,
    ISSUE_DISPLAY_NAMES,
)


class ComplaintCreateRequest(BaseModel):
    issue_type: Union[str, int] = Field(
        ...,
        description="Standard internal issue identifier (e.g., pothole), canonical class ID (0-11), or confirmed category name",
        example="pothole",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Description of the civic problem (optional when evidence is provided)",
        example="Deep pothole near the intersection of 5th cross and Main road.",
    )
    original_language: str = Field(
        default="en",
        description="Language code: en (English), ta (Tamil), or hi (Hindi)",
        example="en",
    )
    language: Optional[str] = Field(
        default=None,
        description="Optional alias for original_language",
        example="en",
    )
    severity_level: Optional[str] = Field(
        default=None,
        description="Optional preferred severity hint",
        example="HIGH",
    )
    latitude: Optional[float] = Field(
        default=None,
        description="Optional GPS latitude (-90 to 90)",
        example=11.0168,
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Optional GPS longitude (-180 to 180)",
        example=76.9558,
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Readable street address or landmark in Coimbatore",
        example="Cross Cut Road, Gandhipuram, Coimbatore, Tamil Nadu, 641012",
    )
    place_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User-entered place name, area or landmark",
        example="Gandhipuram, Coimbatore",
    )
    enforce_boundary: Optional[bool] = Field(
        default=None,
        description="Enforce Coimbatore Municipal Corporation service boundary check",
    )
    ai_confidence: Optional[float] = Field(
        default=None,
        description="Actual AI model prediction confidence if confirmed from AI detection",
    )
    ai_model_version: Optional[str] = Field(
        default=None,
        description="Model version that produced the prediction",
    )
    is_ai_confirmed: Optional[bool] = Field(
        default=None,
        description="Whether category was confirmed from an AI prediction",
    )
    location_source: Optional[str] = Field(
        default=None,
        description="Location acquisition source ('GPS', 'MANUAL_MAP', 'SEARCH')",
    )
    location_accuracy: Optional[float] = Field(
        default=None,
        description="GPS accuracy radius in meters if acquired from Geolocation API",
    )

    @field_validator("issue_type", mode="before")
    def validate_issue_type(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip().lower()
            if not clean or clean in ("auto", "automatic", "none", "null", "undefined"):
                return None
        from app.services.routing_service import resolve_canonical_issue
        try:
            _, _, canonical_key, _ = resolve_canonical_issue(v)
            return canonical_key
        except ValueError as exc:
            raise ValueError(str(exc))


    @field_validator("original_language")
    def validate_language(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in VALID_LANGUAGES:
            raise ValueError(
                f"Invalid language '{v}'. Supported languages are: {sorted(list(VALID_LANGUAGES))}"
            )
        return clean

    @field_validator("latitude")
    def validate_latitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0 degrees.")
        return v

    @field_validator("longitude")
    def validate_longitude(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0 degrees.")
        return v


class EvidenceResponse(BaseModel):
    id: int
    file_type: str
    sha256_hash: str
    file_path: str  # Sanitized relative path (e.g. uploads/evidence/2026/09/xxx.jpg)
    is_resolution: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class StatusHistoryResponse(BaseModel):
    id: int
    old_status: Optional[str]
    new_status: str
    changed_by: Optional[int]
    remarks: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentBriefResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


class DuplicateCandidateResponse(BaseModel):
    complaint_id: str = Field(..., description="Public ID of potential duplicate complaint")
    issue_type: str = Field(..., description="Issue type of candidate")
    issue_type_display: str = Field(..., description="Human-readable issue display name")
    issue_match: bool = Field(..., description="True if canonical issue matches exactly")
    text_similarity: float = Field(..., description="Cosine similarity score [0.0 - 1.0]")
    distance_meters: Optional[float] = Field(default=None, description="Haversine distance in meters")
    duplicate_score: float = Field(..., description="Composite duplicate score [0.0 - 1.0]")
    reason: str = Field(..., description="Explanation for duplicate flag")
    status: str = Field(..., description="Current status of existing complaint")
    created_at: datetime = Field(..., description="Timestamp when existing complaint was registered")


class DuplicateCheckRequest(BaseModel):
    issue_type: str = Field(..., description="Canonical issue category", example="pothole")
    description: Optional[str] = Field(default=None, max_length=2000, description="Description text")
    latitude: Optional[float] = Field(default=None, description="GPS latitude")
    longitude: Optional[float] = Field(default=None, description="GPS longitude")
    exclude_complaint_id: Optional[str] = Field(default=None, description="Exclude self from duplicate search")


class DuplicateCheckResponse(BaseModel):
    has_possible_duplicate: bool
    candidates: List[DuplicateCandidateResponse] = []


class LocationValidationRequest(BaseModel):
    latitude: float = Field(..., description="GPS Latitude (-90 to 90)")
    longitude: float = Field(..., description="GPS Longitude (-180 to 180)")


class LocationValidationResponse(BaseModel):
    is_valid: bool
    message: Optional[str] = None
    city: str = "Coimbatore"
    nearest_locality: Optional[str] = None
    distance_meters: Optional[float] = None


class LocationSearchResult(BaseModel):
    place_name: str
    display_name: str
    latitude: float
    longitude: float
    locality: Optional[str] = None
    city: str = "Coimbatore"
    type: Optional[str] = "landmark"


class LocationSearchResponse(BaseModel):
    success: bool
    query: str
    count: int
    results: List[LocationSearchResult] = []
    message: Optional[str] = None


class ComplaintResponse(BaseModel):
    complaint_id: str
    issue_type: str
    issue_type_display: str
    description: str
    original_language: str
    original_text: Optional[str] = None
    processed_text: Optional[str] = None
    translated_text: Optional[str] = None
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str] = None
    place_name: Optional[str] = None
    severity: str
    severity_score: Optional[float]
    ai_confidence: Optional[float]
    status: str
    department: Optional[DepartmentBriefResponse]
    evidences: List[EvidenceResponse] = []
    status_history: List[StatusHistoryResponse] = []
    possible_duplicates: List[DuplicateCandidateResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplaintListResponse(BaseModel):
    total: int
    items: List[ComplaintResponse]


class TextClassificationRequest(BaseModel):
    description: str = Field(..., max_length=2000, description="Citizen complaint description text")
    language: Optional[str] = Field(default="en", description="Language code (en, ta, hi)")


class TextClassificationResponse(BaseModel):
    success: bool
    detected_issue: Optional[str] = None
    detected_issue_display: Optional[str] = None
    confidence: float = 0.0
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    matched_keywords: List[str] = []
    is_uncertain: bool = True
    routing_message: str = ""

