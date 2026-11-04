from typing import Dict, Any, Optional
from app.complaints.constants import (
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    SEVERITY_CRITICAL,
    ISSUE_BUILDING_DAMAGE,
    ISSUE_SEWAGE_OVERFLOW,
    ISSUE_DRAINAGE_PROBLEM,
    ISSUE_POTHOLE,
    ISSUE_DAMAGED_ROAD,
    ISSUE_BROKEN_STREET_LIGHT,
    ISSUE_WATER_LEAKAGE,
    ISSUE_ENVIRONMENTAL_POLLUTION,
    ISSUE_TRAFFIC_ISSUE,
    ISSUE_GARBAGE_OVERFLOW,
    ISSUE_ILLEGAL_DUMPING,
    ISSUE_PARK_DAMAGE,
)

# Deterministic Baseline Severity Classification
# Rule-based municipal risk baseline
BASELINE_SEVERITY_MAP: Dict[str, str] = {
    # Structural or immediate life-safety hazard
    ISSUE_BUILDING_DAMAGE: SEVERITY_CRITICAL,
    # High health / sanitary or flooding hazards
    ISSUE_SEWAGE_OVERFLOW: SEVERITY_HIGH,
    ISSUE_DRAINAGE_PROBLEM: SEVERITY_HIGH,
    # Standard public infrastructure & utility disruptions
    ISSUE_POTHOLE: SEVERITY_MEDIUM,
    ISSUE_DAMAGED_ROAD: SEVERITY_MEDIUM,
    ISSUE_WATER_LEAKAGE: SEVERITY_MEDIUM,
    ISSUE_BROKEN_STREET_LIGHT: SEVERITY_MEDIUM,
    ISSUE_TRAFFIC_ISSUE: SEVERITY_MEDIUM,
    ISSUE_ENVIRONMENTAL_POLLUTION: SEVERITY_MEDIUM,
    # Lower immediate public safety risk
    ISSUE_GARBAGE_OVERFLOW: SEVERITY_LOW,
    ISSUE_ILLEGAL_DUMPING: SEVERITY_LOW,
    ISSUE_PARK_DAMAGE: SEVERITY_LOW,
}

SEVERITY_REASONS: Dict[str, str] = {
    ISSUE_BUILDING_DAMAGE: "Structural or immediate life-safety hazard identified.",
    ISSUE_SEWAGE_OVERFLOW: "High health, sanitary, and biological contamination risk.",
    ISSUE_DRAINAGE_PROBLEM: "Monsoon flooding and stormwater drainage failure risk.",
    ISSUE_POTHOLE: "Road surface defect posing hazard to vehicular traffic and pedestrians.",
    ISSUE_DAMAGED_ROAD: "Public road infrastructure disruption requiring municipal repair.",
    ISSUE_WATER_LEAKAGE: "Treated municipal water supply line rupture and wastage.",
    ISSUE_BROKEN_STREET_LIGHT: "Public thoroughfare illumination failure affecting nocturnal safety.",
    ISSUE_TRAFFIC_ISSUE: "Urban mobility disruption or traffic safety obstruction.",
    ISSUE_ENVIRONMENTAL_POLLUTION: "Civic environmental contamination violating municipal standards.",
    ISSUE_GARBAGE_OVERFLOW: "Uncollected municipal solid waste accumulation.",
    ISSUE_ILLEGAL_DUMPING: "Unauthorized waste disposal in public open space.",
    ISSUE_PARK_DAMAGE: "Recreational municipal park fixture or greenery degradation.",
}


def determine_baseline_severity(category: Any = None, *, issue_type: Optional[str] = None, issue_class: Optional[int] = None) -> str:
    """
    Deterministically determine a baseline severity category based on civic risk rules.
    Accepts internal issue key, canonical class name, or class ID (0-11).
    Returns: LOW, MEDIUM, HIGH, or CRITICAL.
    """
    raw = category if category is not None else (issue_type if issue_type is not None else issue_class)
    try:
        from app.services.routing_service import resolve_canonical_issue
        _, _, clean_issue, _ = resolve_canonical_issue(raw)
    except Exception:
        clean_issue = str(raw or "").strip().lower()
    return BASELINE_SEVERITY_MAP.get(clean_issue, SEVERITY_MEDIUM)


def calculate_issue_severity(
    category: Any = None,
    confidence: Optional[float] = None,
    *,
    issue_type: Optional[str] = None,
    issue_class: Optional[int] = None,
    detections_count: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Structured deterministic severity assessment based on civic risk rules and real detection.
    Does NOT generate arbitrary or fake scores.
    """
    raw = category if category is not None else (issue_type if issue_type is not None else issue_class)
    try:
        from app.services.routing_service import resolve_canonical_issue
        _, _, clean_issue, _ = resolve_canonical_issue(raw)
    except Exception:
        clean_issue = str(raw or "").strip().lower()

    level = BASELINE_SEVERITY_MAP.get(clean_issue, SEVERITY_MEDIUM)
    reason = SEVERITY_REASONS.get(clean_issue, f"Standard {clean_issue} civic issue.")

    return {
        "level": level,
        "score": None,  # Kept strictly None (no fake score)
        "reason": reason,
        "ai_confidence": confidence,
    }
