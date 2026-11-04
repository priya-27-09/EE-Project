"""
AI Civic Guardian — Service Level Agreement (SLA) & Escalation Service

Calculates municipal SLA resolution deadlines, overdue status, and triggers
formal escalation audit logs for grievances exceeding citizen charter standards.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.models.audit_log import AuditLog
from app.services.audit_service import record_audit_log

# Configurable Municipal SLA Policies (in hours)
SLA_HOURS_BY_SEVERITY: Dict[str, int] = {
    "CRITICAL": 24,    # Major pipeline ruptures, high-voltage street light collapse
    "HIGH": 48,        # Water leakage, major sewage overflow, active road hazard
    "MEDIUM": 72,      # Potholes, broken street lights, garbage accumulation
    "LOW": 120,        # Minor park maintenance, graffiti, building facade notice
}

# Category overrides if specific public health risks apply
CATEGORY_SLA_OVERRIDE_HOURS: Dict[str, int] = {
    "sewage_overflow": 24,
    "water_leakage": 48,
    "damaged_road": 48,
}


class SLAManagementService:
    @classmethod
    def get_configured_sla_hours(cls, severity: Optional[str], issue_type: Optional[str]) -> int:
        sev = (severity or "MEDIUM").upper()
        base_hours = SLA_HOURS_BY_SEVERITY.get(sev, 72)
        issue = (issue_type or "").lower()
        if issue in CATEGORY_SLA_OVERRIDE_HOURS:
            base_hours = min(base_hours, CATEGORY_SLA_OVERRIDE_HOURS[issue])
        return base_hours

    @classmethod
    def calculate_deadline(cls, created_at: datetime, severity: Optional[str], issue_type: Optional[str]) -> datetime:
        sla_hours = cls.get_configured_sla_hours(severity, issue_type)
        return created_at + timedelta(hours=sla_hours)

    @classmethod
    def evaluate_complaint_sla(cls, complaint: Complaint) -> Dict[str, Any]:
        """
        Evaluates SLA metrics for a complaint:
        - SLA hours allocated
        - Projected deadline
        - Elapsed hours since registration
        - Remaining hours or overdue duration
        - Overdue status
        """
        created = complaint.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        sla_hours = cls.get_configured_sla_hours(complaint.severity, complaint.issue_type)
        deadline = created + timedelta(hours=sla_hours)
        now = datetime.now(timezone.utc)

        is_resolved = (complaint.status or "").upper() == "RESOLVED"
        
        if is_resolved and getattr(complaint, "resolved_at", None):
            res_time = complaint.resolved_at
            if res_time.tzinfo is None:
                res_time = res_time.replace(tzinfo=timezone.utc)
            elapsed_seconds = (res_time - created).total_seconds()
            is_overdue = res_time > deadline
            remaining_seconds = (deadline - res_time).total_seconds()
        else:
            elapsed_seconds = (now - created).total_seconds()
            is_overdue = now > deadline and not is_resolved
            remaining_seconds = (deadline - now).total_seconds()

        elapsed_hours = round(max(0.0, elapsed_seconds / 3600.0), 1)
        remaining_hours = round(remaining_seconds / 3600.0, 1)

        if is_resolved:
            escalation_state = "COMPLIED_RESOLVED"
        elif is_overdue:
            escalation_state = "OVERDUE_ESCALATED"
        elif remaining_hours <= 12:
            escalation_state = "WARNING_EXPIRING_SOON"
        else:
            escalation_state = "WITHIN_SLA"

        return {
            "sla_hours_allocated": sla_hours,
            "created_at": created.isoformat(),
            "deadline": deadline.isoformat(),
            "deadline_formatted": deadline.strftime("%d %b %Y, %I:%M %p"),
            "elapsed_hours": elapsed_hours,
            "remaining_hours": remaining_hours,
            "is_overdue": is_overdue,
            "escalation_state": escalation_state,
        }

    calculate_sla_status = evaluate_complaint_sla

    @classmethod
    def check_and_record_escalation(cls, complaint: Complaint, db: Session) -> bool:
        """
        Checks if complaint is overdue. If overdue, logs an SLA_ESCALATED event in audit_logs
        strictly once, preventing duplicate repeated spam alerts.
        """
        if (complaint.status or "").upper() == "RESOLVED":
            return False

        sla_info = cls.evaluate_complaint_sla(complaint)
        if not sla_info["is_overdue"]:
            return False

        # Check if already escalated to prevent duplicate alerts
        existing_log = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "Complaint",
                AuditLog.entity_id == complaint.complaint_id,
                AuditLog.action == "SLA_ESCALATED",
            )
            .first()
        )
        if existing_log:
            return False

        try:
            record_audit_log(
                action="SLA_ESCALATED",
                entity_type="Complaint",
                entity_id=complaint.complaint_id,
                user_id=complaint.user_id,
                db=db,
                metadata={
                    "complaint_id": complaint.complaint_id,
                    "department_id": complaint.department_id,
                    "severity": complaint.severity,
                    "sla_hours": sla_info["sla_hours_allocated"],
                    "elapsed_hours": sla_info["elapsed_hours"],
                    "deadline": sla_info["deadline"],
                },
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
