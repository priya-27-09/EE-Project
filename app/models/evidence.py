from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base


class ComplaintEvidence(Base):
    """
    Evidence attached to a complaint.
    Stores secure storage file paths and SHA-256 integrity hashes.
    Raw binary image/video data is strictly forbidden from being stored in the database.
    """
    __tablename__ = "complaint_evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    is_resolution = Column(Boolean, nullable=False, default=False, server_default="false")
    uploaded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    complaint = relationship("Complaint", back_populates="evidences")
    uploader = relationship("User", back_populates="uploaded_evidences")

    __table_args__ = (
        Index("ix_evidence_complaint_hash", "complaint_id", "sha256_hash"),
    )

    def __repr__(self) -> str:
        return f"<ComplaintEvidence id={self.id} complaint_id={self.complaint_id} type={self.file_type}>"
