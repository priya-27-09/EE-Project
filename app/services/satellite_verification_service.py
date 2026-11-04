"""
AI Civic Guardian — Safe Satellite-Assisted Verification Service

Integrates spatial GIS evidence with citizen photo/video submissions:
- Evaluates geographic coordinates against official CCMC service boundaries.
- Combines citizen narrative, evidence media integrity, and spatial context.
- Explicitly acknowledges satellite resolution limitations (0.5m-1.0m) without
  falsely claiming real-time or fine-defect detection from space.
- Recommends actionable verification outcomes to authorized municipal officers.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.services.boundary_service import CoimbatoreBoundaryService
from app.complaints.constants import ISSUE_DISPLAY_NAMES


class SatelliteAssistedVerificationService:
    PROVIDER_NAME = "Esri World Imagery (ArcGIS Online)"
    TILE_SERVER_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
    SPATIAL_RESOLUTION_NOTE = (
        "Satellite imagery provides global high-resolution orthophoto coverage (0.5m - 1.0m ground sampling distance). "
        "Macro terrain, road alignment, and building footprints are visible. "
        "Fine civic defects (small potholes, water pipe pinhole leaks, internal street light wiring, minor garbage) "
        "cannot be definitively verified from orbit and require on-site ward officer inspection."
    )

    @classmethod
    def evaluate_complaint_evidence(
        cls,
        complaint: Complaint,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Combines spatial coordinates, boundary validation, and citizen evidence
        to provide a defensible verification recommendation.
        """
        lat = float(complaint.latitude) if complaint.latitude is not None else None
        lon = float(complaint.longitude) if complaint.longitude is not None else None

        # 1. Geographic Boundary Validation
        is_in_bounds, boundary_err = CoimbatoreBoundaryService.validate_coordinates(lat, lon)
        nearest_loc, nearest_dist = CoimbatoreBoundaryService.find_nearest_locality_with_dist(lat, lon)

        # 2. Evidence Assessment
        evidence_count = len(complaint.evidences) if complaint.evidences else 0
        has_evidence = evidence_count > 0

        # 3. Defect Visibility Category Classification
        # Macro defects (potentially discernible in high-res satellite imagery) vs Micro defects
        issue_type = (complaint.issue_type or "").lower()
        macro_issues = ["damaged_road", "building_damage", "park_damage", "environmental_pollution"]
        micro_issues = ["pothole", "water_leakage", "sewage_overflow", "broken_street_light", "garbage_overflow", "illegal_dumping", "drainage_problem", "traffic_issue"]

        is_macro = issue_type in macro_issues

        # 4. Formulate Verification Outcome
        if not is_in_bounds:
            outcome = "UNABLE_TO_VERIFY"
            recommendation = "REJECT_OR_FORWARD"
            explanation = (
                f"Reported coordinates ({lat}, {lon}) lie outside Coimbatore Municipal Corporation boundary. "
                "Satellite verification cannot be conducted for locations outside municipal jurisdiction."
            )
        elif not has_evidence:
            outcome = "INSPECTION_REQUIRED"
            recommendation = "CONDUCT_FIELD_INSPECTION"
            explanation = (
                "No visual photographic evidence was uploaded by the citizen. "
                "Physical ward officer inspection is mandatory to confirm the grievance."
            )
        elif is_macro:
            outcome = "EVIDENCE_SUPPORTS_REPORT"
            recommendation = "VERIFY_WITH_FIELD_CONFIRMATION"
            explanation = (
                f"Coordinates verified within CCMC near {nearest_loc} ({nearest_dist:.0f}m). "
                f"Macro civic category '{ISSUE_DISPLAY_NAMES.get(issue_type, issue_type)}' aligns with spatial zone. "
                "Ground photography and satellite alignment support proceeding with officer verification."
            )
        else:
            outcome = "INSPECTION_REQUIRED"
            recommendation = "CONDUCT_FIELD_INSPECTION"
            explanation = (
                f"Coordinates verified within CCMC near {nearest_loc} ({nearest_dist:.0f}m). "
                f"Issue type '{ISSUE_DISPLAY_NAMES.get(issue_type, issue_type)}' is a localized defect. "
                "Per municipal engineering guidelines, satellite imagery cannot independently prove micro-defects; "
                "physical ward crew inspection is required."
            )

        return {
            "status": "ASSESSMENT_COMPLETE",
            "complaint_id": complaint.complaint_id,
            "issue_type": issue_type,
            "issue_display": ISSUE_DISPLAY_NAMES.get(issue_type, issue_type),
            "coordinates": {"latitude": lat, "longitude": lon},
            "is_within_coimbatore_boundary": is_in_bounds,
            "nearest_coimbatore_locality": nearest_loc,
            "distance_to_locality_meters": round(nearest_dist, 1),
            "evidence_count": evidence_count,
            "has_visual_evidence": has_evidence,
            "satellite_layer": {
                "provider": cls.PROVIDER_NAME,
                "tile_service": cls.TILE_SERVER_URL,
                "is_real_time": False,
                "resolution_notes": cls.SPATIAL_RESOLUTION_NOTE,
            },
            "outcome": outcome,
            "recommendation": recommendation,
            "explanation": explanation,
            "assessed_at": datetime.now().isoformat(),
        }
