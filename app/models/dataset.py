from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class DatasetStatus:
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    READY_FOR_TRAINING = "READY_FOR_TRAINING"
    ARCHIVED = "ARCHIVED"

    ALL = [UPLOADED, VALIDATING, VALID, INVALID, READY_FOR_TRAINING, ARCHIVED]


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    dataset_version = Column(String(50), unique=True, index=True, nullable=False)
    dataset_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    storage_path = Column(String(500), nullable=False)
    dataset_sha256 = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False, default=DatasetStatus.UPLOADED, index=True)

    # Dataset file and object statistics
    train_image_count = Column(Integer, nullable=False, default=0)
    val_image_count = Column(Integer, nullable=False, default=0)
    test_image_count = Column(Integer, nullable=False, default=0)
    total_image_count = Column(Integer, nullable=False, default=0)
    total_object_count = Column(Integer, nullable=False, default=0)
    class_count = Column(Integer, nullable=False, default=0)

    # Detailed validation summary cached in PostgreSQL as JSONB
    validation_summary = Column(JSONB, nullable=True)
    validation_report_path = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    uploader = relationship("User", backref="uploaded_datasets")

    def __repr__(self) -> str:
        return f"<DatasetVersion version={self.dataset_version} name={self.dataset_name} status={self.status}>"
