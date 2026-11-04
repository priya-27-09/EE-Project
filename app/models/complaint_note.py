from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.session import Base


class ComplaintNote(Base):
    """
    Officer operational notes recorded during complaint investigation/handling.
    Stored securely in PostgreSQL.
    """
    __tablename__ = "complaint_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    complaint = relationship("Complaint", back_populates="notes")
    author = relationship("User", back_populates="complaint_notes")

    __table_args__ = (
        Index("ix_complaint_notes_complaint_time", "complaint_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ComplaintNote id={self.id} complaint_id={self.complaint_id} user_id={self.user_id}>"
