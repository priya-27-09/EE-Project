from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base


class UserRole:
    CITIZEN = "CITIZEN"
    OFFICER = "OFFICER"
    ADMIN = "ADMIN"
    ALL = [CITIZEN, OFFICER, ADMIN]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.CITIZEN, index=True)
    preferred_language = Column(String(10), nullable=False, default="en")
    department_id = Column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    department = relationship("Department", foreign_keys=[department_id])
    complaints = relationship("Complaint", foreign_keys="[Complaint.user_id]", back_populates="user", cascade="all, delete-orphan")
    status_history_changes = relationship("ComplaintStatusHistory", back_populates="actor")
    audit_logs = relationship("AuditLog", back_populates="user")
    uploaded_evidences = relationship("ComplaintEvidence", back_populates="uploader")
    complaint_notes = relationship("ComplaintNote", back_populates="author")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role} dept={self.department_id}>"
