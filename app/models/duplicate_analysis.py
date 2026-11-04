from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.session import Base


class DuplicateAnalysis(Base):
    __tablename__ = "duplicate_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    possible_duplicate_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    complaint = relationship(
        "Complaint",
        foreign_keys=[complaint_id],
        back_populates="duplicate_analyses",
    )
    possible_duplicate = relationship(
        "Complaint",
        foreign_keys=[possible_duplicate_id],
        back_populates="duplicate_references",
    )

    __table_args__ = (
        Index("ix_duplicate_pair", "complaint_id", "possible_duplicate_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DuplicateAnalysis id={self.id} complaint_id={self.complaint_id} "
            f"duplicate_of={self.possible_duplicate_id} score={self.similarity_score}>"
        )
