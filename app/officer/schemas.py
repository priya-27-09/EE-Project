from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.complaints.schemas import (
    DepartmentBriefResponse,
    EvidenceResponse,
    StatusHistoryResponse,
    DuplicateCandidateResponse,
)


class OfficerDashboardSummary(BaseModel):
    """Real summary statistics from PostgreSQL for officer's assigned department."""
    total_assigned: int = 0
    submitted: int = 0
    ai_verified: int = 0
    department_assigned: int = 0
    in_progress: int = 0
    resolved: int = 0
    needs_human_review: int = 0
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    officer_name: str
    officer_role: str
    allowed_issue_types: List[Dict[str, str]] = []


class OfficerComplaintBrief(BaseModel):
    """Brief metadata for officer complaints data table."""
    id: int
    complaint_id: str
    issue_type: str
    issue_type_display: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    severity: str
    status: str
    created_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_name: Optional[str] = None
    address: Optional[str] = None
    ai_confidence: Optional[float] = None
    has_evidence: bool = False
    has_duplicate_warning: bool = False



class OfficerComplaintListResponse(BaseModel):
    """Paginated complaint list response for officer."""
    total: int
    page: int
    page_size: int
    total_pages: int
    department_name: Optional[str] = None
    items: List[OfficerComplaintBrief]


class OfficerStatusUpdateRequest(BaseModel):
    """Status transition request with optional officer remarks."""
    status: str = Field(..., min_length=2, max_length=50)
    note: Optional[str] = Field(default=None, max_length=5000)


class OfficerNoteCreateRequest(BaseModel):
    """Officer operational note payload."""
    note: str = Field(..., min_length=1, max_length=5000)


class OfficerNoteResponse(BaseModel):
    """Saved officer note item."""
    id: int
    complaint_id: str
    user_id: Optional[int] = None
    author_name: Optional[str] = None
    note: str
    created_at: datetime


class OfficerResolutionRequest(BaseModel):
    """Resolution submission with mandatory explanation."""
    resolution_note: str = Field(..., min_length=3, max_length=5000)


from app.officer.verification_schemas import ResolutionVerificationResponse


class OfficerComplaintDetailResponse(BaseModel):
    """Detailed view for single complaint on officer dashboard."""
    complaint_id: str
    issue_type: str
    issue_type_display: str
    description: str
    original_language: str
    original_text: Optional[str] = None
    processed_text: Optional[str] = None
    translated_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_name: Optional[str] = None
    address: Optional[str] = None
    severity: str
    severity_score: Optional[float] = None
    severity_reason: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_detected_issue: Optional[str] = None
    status: str
    department: Optional[DepartmentBriefResponse] = None
    evidences: List[EvidenceResponse] = []
    status_history: List[StatusHistoryResponse] = []
    notes: List[OfficerNoteResponse] = []
    resolution: Optional[Dict[str, Any]] = None
    latest_verification: Optional[ResolutionVerificationResponse] = None
    possible_duplicates: List[DuplicateCandidateResponse] = []
    citizen_id: Optional[int] = None
    citizen_name: Optional[str] = None
    citizen_email: Optional[str] = None
    created_at: datetime
    updated_at: datetime
