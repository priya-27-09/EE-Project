"""
Pydantic schemas for Step 9: AI-Assisted Resolution Evidence Verification.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ResolutionMetricsResponse(BaseModel):
    structural_similarity: Optional[float] = Field(None, description="SSIM score [0.0 - 1.0]")
    pixel_difference: Optional[float] = Field(None, description="Mean absolute pixel difference [0.0 - 1.0]")
    edge_similarity: Optional[float] = Field(None, description="Canny edge Dice overlap [0.0 - 1.0]")
    histogram_similarity: Optional[float] = Field(None, description="3D BGR color histogram correlation [0.0 - 1.0]")
    perceptual_hash_distance: Optional[int] = Field(None, description="64-bit DCT pHash Hamming distance [0 - 64]")


class ResolutionVerificationResponse(BaseModel):
    id: int
    complaint_id: str
    before_evidence_id: Optional[int] = None
    after_evidence_id: Optional[int] = None
    before_evidence_path: Optional[str] = None
    after_evidence_path: Optional[str] = None
    verification_status: str
    verification_score: Optional[float] = None
    human_review_required: bool = True
    verification_reason: Optional[str] = None
    metrics: Optional[ResolutionMetricsResponse] = None
    alignment_status: str = "NOT_AVAILABLE"
    algorithm_version: str = "resolution-v1"
    created_at: datetime
    reviewed_by_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_decision: Optional[str] = None
    review_notes: Optional[str] = None

    class Config:
        from_attributes = True


class ResolutionReviewRequest(BaseModel):
    decision: str = Field(..., description="Review decision: APPROVED or REJECTED", example="APPROVED")
    review_notes: str = Field(..., min_length=5, description="Mandatory detailed officer review remarks", example="Before and after images were visually inspected and road repair is verified.")
