# Import Base and all models for Alembic migrations autogenerate
from app.db.session import Base
from app.models.user import User
from app.models.department import Department
from app.models.complaint import Complaint
from app.models.prediction import AIPrediction
from app.models.evidence import ComplaintEvidence
from app.models.status_history import ComplaintStatusHistory
from app.models.duplicate_analysis import DuplicateAnalysis
from app.models.audit_log import AuditLog
from app.models.dataset import DatasetVersion, DatasetStatus
from app.models.model_version import ModelVersion, TrainingStatus

__all__ = [
    "Base",
    "User",
    "Department",
    "Complaint",
    "AIPrediction",
    "ComplaintEvidence",
    "ComplaintStatusHistory",
    "DuplicateAnalysis",
    "AuditLog",
    "DatasetVersion",
    "DatasetStatus",
    "ModelVersion",
    "TrainingStatus",
]


