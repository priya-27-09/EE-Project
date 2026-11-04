from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version = Column(String(50), nullable=False)
    detected_class = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    bounding_boxes = Column(JSONB, nullable=True)  # Structured detection coordinates/boxes
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    complaint = relationship("Complaint", back_populates="ai_predictions")

    def __repr__(self) -> str:
        return (
            f"<AIPrediction id={self.id} complaint_id={self.complaint_id} "
            f"class={self.detected_class} conf={self.confidence}>"
        )
