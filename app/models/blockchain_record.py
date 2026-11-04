from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base

# Canonical Blockchain Record Statuses
STATUS_PENDING = "PENDING"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_FAILED = "FAILED"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"

# Canonical Blockchain Event Types
EVENT_COMPLAINT_CREATED = "COMPLAINT_CREATED"
EVENT_COMPLAINT_STATUS_CHANGED = "COMPLAINT_STATUS_CHANGED"
EVENT_RESOLUTION_EVIDENCE_ADDED = "RESOLUTION_EVIDENCE_ADDED"
EVENT_RESOLUTION_VERIFICATION = "RESOLUTION_VERIFICATION"
EVENT_HUMAN_RESOLUTION_REVIEW = "HUMAN_RESOLUTION_REVIEW"


class BlockchainRecord(Base):
    """
    PostgreSQL persistence for blockchain integrity and audit anchors.
    PostgreSQL remains the primary source of truth; this record anchors cryptographic
    proofs (SHA-256 canonical payload hash) onto the Ethereum/Ganache blockchain.
    """
    __tablename__ = "blockchain_records"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)
    event_hash = Column(String(66), nullable=False, index=True)
    data_hash = Column(String(66), nullable=False)
    canonical_payload = Column(JSON, nullable=True)
    blockchain_network = Column(String(64), nullable=False, default="Ganache")
    chain_id = Column(Integer, nullable=True)
    contract_address = Column(String(64), nullable=True)
    transaction_hash = Column(String(66), nullable=True, index=True)
    block_number = Column(BigInteger, nullable=True)
    blockchain_timestamp = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default=STATUS_PENDING, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    complaint = relationship("Complaint", back_populates="blockchain_records")

    def __repr__(self) -> str:
        return (
            f"<BlockchainRecord id={self.id} complaint_id={self.complaint_id} "
            f"event_type='{self.event_type}' status='{self.status}' "
            f"tx_hash={self.transaction_hash[:10] if self.transaction_hash else None}>"
        )
