from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base


class TrainingStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"
    ACTIVE = "ACTIVE"

    ALL = [QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, ARCHIVED, ACTIVE]


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_version = Column(String(50), unique=True, index=True, nullable=False)
    model_name = Column(String(200), nullable=False)
    dataset_version = Column(String(50), nullable=False, index=True)
    base_model = Column(String(100), nullable=False, default="yolo11n.pt")
    ultralytics_version = Column(String(50), nullable=False)
    task = Column(String(50), nullable=False, default="detect")

    class_count = Column(Integer, nullable=False, default=0)
    class_names = Column(JSONB, nullable=True)

    # Disk paths for model weights (never stored as binary in PostgreSQL)
    weights_path = Column(String(500), nullable=True)
    best_weights_path = Column(String(500), nullable=True)
    last_weights_path = Column(String(500), nullable=True)

    training_status = Column(String(30), nullable=False, default=TrainingStatus.QUEUED, index=True)
    is_active = Column(Boolean, nullable=False, default=False, index=True)

    # Training hyperparameter configuration
    epochs = Column(Integer, nullable=False, default=50)
    image_size = Column(Integer, nullable=False, default=640)
    batch_size = Column(Integer, nullable=False, default=8)
    device = Column(String(50), nullable=False, default="cpu")

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    training_duration_seconds = Column(Float, nullable=True)

    # Actual metrics obtained from Ultralytics (null if not produced)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)

    # Detailed metrics and curve logs cached as JSONB
    training_metrics = Column(JSONB, nullable=True)
    validation_metrics = Column(JSONB, nullable=True)
    training_output_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
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

    creator = relationship("User", backref="created_models")

    def __repr__(self) -> str:
        return f"<ModelVersion version={self.model_version} name={self.model_name} status={self.training_status} active={self.is_active}>"
