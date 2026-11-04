from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.complaint import Complaint
from app.models.status_history import ComplaintStatusHistory
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_AI_VERIFIED,
    STATUS_VERIFIED,
    STATUS_DEPARTMENT_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_NEEDS_HUMAN_REVIEW,
    STATUS_IN_REVIEW,
    STATUS_ASSIGNED,
    STATUS_REJECTED,
    VALID_STATUSES,
)

# Canonical workflow state transitions:
# SUBMITTED -> VERIFIED/AI_VERIFIED -> DEPARTMENT_ASSIGNED -> IN_PROGRESS -> RESOLVED
# (NEEDS_HUMAN_REVIEW can branch/return where human review is required)
ALLOWED_TRANSITIONS = {
    STATUS_SUBMITTED: {
        STATUS_AI_VERIFIED,
        STATUS_VERIFIED,
        STATUS_DEPARTMENT_ASSIGNED,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_IN_REVIEW,
        STATUS_ASSIGNED,
        STATUS_REJECTED,
    },
    STATUS_AI_VERIFIED: {
        STATUS_VERIFIED,
        STATUS_DEPARTMENT_ASSIGNED,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_IN_PROGRESS,
        STATUS_ASSIGNED,
        STATUS_REJECTED,
    },
    STATUS_VERIFIED: {
        STATUS_DEPARTMENT_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_RESOLVED,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_REJECTED,
    },
    STATUS_DEPARTMENT_ASSIGNED: {
        STATUS_VERIFIED,
        STATUS_IN_PROGRESS,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_REJECTED,
    },
    STATUS_IN_PROGRESS: {
        STATUS_RESOLVED,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_REJECTED,
    },
    STATUS_NEEDS_HUMAN_REVIEW: {
        STATUS_DEPARTMENT_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_RESOLVED,
        STATUS_REJECTED,
    },
    # Backwards compatibility transitions for existing seeded/legacy complaints
    STATUS_IN_REVIEW: {
        STATUS_DEPARTMENT_ASSIGNED,
        STATUS_ASSIGNED,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_REJECTED,
    },
    STATUS_ASSIGNED: {
        STATUS_IN_PROGRESS,
        STATUS_NEEDS_HUMAN_REVIEW,
        STATUS_REJECTED,
    },
    STATUS_RESOLVED: set(),  # Terminal state
    STATUS_REJECTED: set(),  # Terminal state
}


def record_initial_status(
    complaint_id: int,
    user_id: int,
    db: Session,
    remarks: Optional[str] = "Complaint submitted by citizen.",
) -> ComplaintStatusHistory:
    """Record initial SUBMITTED status in ComplaintStatusHistory."""
    history = ComplaintStatusHistory(
        complaint_id=complaint_id,
        old_status=None,
        new_status=STATUS_SUBMITTED,
        changed_by=user_id,
        remarks=remarks,
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)
    return history


def transition_complaint_status(
    complaint: Complaint,
    new_status: str,
    changed_by_user_id: int,
    db: Session,
    remarks: Optional[str] = None,
) -> ComplaintStatusHistory:
    """
    Centralized status transition service.
    Enforces state machine rules and records audit trail in ComplaintStatusHistory.
    Raises:
      - HTTP 422 Unprocessable Entity if status string is not recognized.
      - HTTP 409 Conflict if transition is not permitted by canonical state machine.
    """
    clean_status = (new_status or "").strip().upper()
    if clean_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid complaint status '{new_status}'. Allowed statuses: {sorted(list(VALID_STATUSES))}",
        )

    current_status = complaint.status
    allowed_next = ALLOWED_TRANSITIONS.get(current_status, set())
    if clean_status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition from '{current_status}' to '{clean_status}'. Allowed next transitions: {sorted(list(allowed_next))}",
        )

    # Apply transition
    complaint.status = clean_status
    complaint.updated_at = datetime.now(timezone.utc)

    # Record history
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=current_status,
        new_status=clean_status,
        changed_by=changed_by_user_id,
        remarks=remarks,
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)
    db.commit()
    db.refresh(complaint)
    db.refresh(history)

    # Blockchain Integrity Anchoring (Step 10)
    # Anchors tamper-evident cryptographic hash on Ganache without storing PII
    try:
        from app.services.blockchain_service import BlockchainService
        from app.models.blockchain_record import EVENT_COMPLAINT_STATUS_CHANGED

        status_payload = {
            "complaint_id": complaint.complaint_id,
            "event_type": EVENT_COMPLAINT_STATUS_CHANGED,
            "history_id": history.id,
            "previous_status": current_status,
            "new_status": clean_status,
            "changed_at": history.created_at.isoformat(),
        }

        BlockchainService.anchor_event(
            complaint_id=complaint.id,
            complaint_public_id=complaint.complaint_id,
            event_type=EVENT_COMPLAINT_STATUS_CHANGED,
            payload=status_payload,
            unique_key=f"status_hist_{history.id}",
            db=db,
            user_id=changed_by_user_id,
        )
    except Exception:
        # Resilient design: Blockchain errors must NEVER fail the status transition
        pass

    return history

