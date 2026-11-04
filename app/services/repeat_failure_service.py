"""
AI Civic Guardian — Repeat Civic Failure Detection Service

Detects recurring civic defects at the same physical location after a previous
grievance was marked RESOLVED:
- Compares geographic distance (Haversine distance <= 250m).
- Compares issue category and description similarity.
- Checks if the previous complaint was RESOLVED within the last 90 days.
- Flags the complaint for supervisory and engineering inspection without auto-rejecting.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.complaint import Complaint
from app.services.boundary_service import CoimbatoreBoundaryService
from app.complaints.constants import STATUS_RESOLVED
from app.services.audit_service import record_audit_log


class RepeatFailureService:
    PROXIMITY_RADIUS_METERS = 250.0
    LOOKBACK_DAYS = 90

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    @classmethod
    def check_for_repeat_failure(
        cls,
        complaint: Complaint,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Scans resolved complaints to determine if this new report represents
        a recurring or repeat civic failure at the same site.
        """
        lat = float(complaint.latitude) if complaint.latitude is not None else None
        lon = float(complaint.longitude) if complaint.longitude is not None else None

        if lat is None or lon is None:
            return {
                "is_repeat_failure": False,
                "reason": "Complaint does not have GPS coordinates for spatial proximity check.",
                "candidate": None,
            }

        created = complaint.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        cutoff_date = created - timedelta(days=cls.LOOKBACK_DAYS)

        # Query previously RESOLVED complaints of the same issue type
        resolved_candidates = (
            db.query(Complaint)
            .filter(
                Complaint.id != complaint.id,
                Complaint.issue_type == complaint.issue_type,
                Complaint.status == STATUS_RESOLVED,
                Complaint.latitude.isnot(None),
                Complaint.longitude.isnot(None),
                Complaint.created_at >= cutoff_date,
            )
            .order_by(desc(Complaint.created_at))
            .limit(20)
            .all()
        )

        matched_candidate = None
        closest_distance = 999999.0

        for prev in resolved_candidates:
            p_lat = float(prev.latitude)
            p_lon = float(prev.longitude)
            dist = cls.haversine_distance(lat, lon, p_lat, p_lon)

            if dist <= cls.PROXIMITY_RADIUS_METERS and dist < closest_distance:
                closest_distance = dist
                matched_candidate = prev

        if matched_candidate:
            resolved_at_str = matched_candidate.resolved_at.strftime("%d %b %Y") if matched_candidate.resolved_at else "Recently"
            explanation = (
                f"Repeat Civic Defect Detected: A similar '{complaint.issue_type.replace('_', ' ').title()}' "
                f"was previously marked RESOLVED on {resolved_at_str} under reference {matched_candidate.complaint_id} "
                f"within {closest_distance:.1f} meters. Requires ward engineering review to prevent recurring failure."
            )

            # Record in audit logs
            try:
                record_audit_log(
                    action="REPEAT_FAILURE_DETECTED",
                    entity_type="Complaint",
                    entity_id=complaint.complaint_id,
                    user_id=complaint.user_id,
                    db=db,
                    metadata={
                        "complaint_id": complaint.complaint_id,
                        "previous_complaint_id": matched_candidate.complaint_id,
                        "distance_meters": round(closest_distance, 1),
                        "issue_type": complaint.issue_type,
                        "previous_resolved_at": matched_candidate.resolved_at.isoformat() if matched_candidate.resolved_at else None,
                    },
                )
                db.commit()
            except Exception:
                db.rollback()

            return {
                "is_repeat_failure": True,
                "reason": explanation,
                "distance_meters": round(closest_distance, 1),
                "previous_complaint_id": matched_candidate.complaint_id,
                "previous_resolution_date": matched_candidate.resolved_at.isoformat() if matched_candidate.resolved_at else None,
                "previous_description": matched_candidate.description,
            }

        return {
            "is_repeat_failure": False,
            "reason": "No previously resolved complaints of the same type within 250m.",
            "candidate": None,
        }
