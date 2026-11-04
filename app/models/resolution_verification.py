from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, Boolean, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.session import Base


class ResolutionVerification(Base):
    """
    Measurable, deterministic visual verification results comparing citizen original
    before-evidence with officer resolution after-evidence using computer vision.
    Separates automated CV analysis from human review decisions.
    """
    __tablename__ = "resolution_verifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    before_evidence_id = Column(
        Integer,
        ForeignKey("complaint_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    after_evidence_id = Column(
        Integer,
        ForeignKey("complaint_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    verification_status = Column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )  # VERIFICATION_NOT_AVAILABLE, PENDING, AI_VERIFIED, NEEDS_HUMAN_REVIEW, VERIFICATION_FAILED
    verification_score = Column(Float, nullable=True)
    human_review_required = Column(Boolean, default=True, nullable=False)
    verification_reason = Column(Text, nullable=True)

    # Measurable classical computer vision metrics
    structural_similarity = Column(Float, nullable=True)  # SSIM score [0.0, 1.0]
    pixel_difference = Column(Float, nullable=True)       # Mean absolute difference [0.0, 1.0]
    edge_similarity = Column(Float, nullable=True)        # Canny edge Dice overlap [0.0, 1.0]
    histogram_similarity = Column(Float, nullable=True)   # Histogram correlation [0.0, 1.0]
    perceptual_hash_distance = Column(Integer, nullable=True)  # DCT pHash Hamming distance [0, 64]

    alignment_status = Column(String(50), default="NOT_AVAILABLE", nullable=False)
    algorithm_version = Column(String(50), default="resolution-v1", nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Human Review Fields (preserves automated algorithm metrics without overwriting)
    reviewed_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_decision = Column(String(50), nullable=True)  # APPROVED, REJECTED
    review_notes = Column(Text, nullable=True)

    # Relationships
    complaint = relationship("Complaint", back_populates="resolution_verifications")
    before_evidence = relationship("ComplaintEvidence", foreign_keys=[before_evidence_id])
    after_evidence = relationship("ComplaintEvidence", foreign_keys=[after_evidence_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        Index("ix_resolution_verifications_complaint_status", "complaint_id", "verification_status"),
        Index("ix_resolution_verifications_complaint_time", "complaint_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ResolutionVerification id={self.id} complaint_id={self.complaint_id} "
            f"status={self.verification_status} score={self.verification_score}>"
        )
