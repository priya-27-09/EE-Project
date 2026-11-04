from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.session import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)

    # Relationships
    complaints = relationship("Complaint", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name} active={self.active}>"
