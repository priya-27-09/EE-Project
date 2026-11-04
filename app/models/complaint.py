from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Numeric,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.db.session import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    original_language = Column(String(10), nullable=False, default="en")
    original_text = Column(Text, nullable=True)
    processed_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    address = Column(String(500), nullable=True)
    place_name = Column(String(255), nullable=True)
    severity = Column(String(20), nullable=False, default="MEDIUM", index=True)
    severity_score = Column(Float, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="SUBMITTED", index=True)
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
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="complaints")
    department = relationship("Department", back_populates="complaints")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    ai_predictions = relationship("AIPrediction", back_populates="complaint", cascade="all, delete-orphan")
    evidences = relationship("ComplaintEvidence", back_populates="complaint", cascade="all, delete-orphan")
    status_history = relationship(
        "ComplaintStatusHistory",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintStatusHistory.created_at",
    )
    notes = relationship(
        "ComplaintNote",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintNote.created_at",
    )
    duplicate_analyses = relationship(
        "DuplicateAnalysis",
        foreign_keys="[DuplicateAnalysis.complaint_id]",
        back_populates="complaint",
        cascade="all, delete-orphan",
    )
    duplicate_references = relationship(
        "DuplicateAnalysis",
        foreign_keys="[DuplicateAnalysis.possible_duplicate_id]",
        back_populates="possible_duplicate",
        cascade="all, delete-orphan",
    )
    resolution_verifications = relationship(
        "ResolutionVerification",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="desc(ResolutionVerification.created_at)",
    )
    blockchain_records = relationship(
        "BlockchainRecord",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="desc(BlockchainRecord.created_at)",
    )

    __table_args__ = (

        Index("ix_complaints_dept_status", "department_id", "status"),
        Index("ix_complaints_created_severity", "created_at", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Complaint id={self.id} complaint_id={self.complaint_id} status={self.status}>"
