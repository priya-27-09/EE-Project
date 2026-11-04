from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.auth.dependencies import get_current_user
from app.complaints.schemas import (
    ComplaintCreateRequest,
    ComplaintResponse,
    ComplaintListResponse,
    EvidenceResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    LocationValidationRequest,
    LocationValidationResponse,
    LocationSearchResult,
    LocationSearchResponse,
    TextClassificationRequest,
    TextClassificationResponse,
)
from app.complaints.constants import VALID_ISSUE_TYPES, ISSUE_DISPLAY_NAMES
from app.services.complaint_service import (
    create_new_complaint,
    build_complaint_response,
)
from app.services.evidence_service import save_evidence_file
from app.services.duplicate_service import DuplicateService
from app.services.boundary_service import CoimbatoreBoundaryService
from app.services.geocoding_service import GeocodingService
from app.services.routing_service import classify_issue_from_description, get_routing_for_issue

router = APIRouter(prefix="/api/v1/complaints", tags=["Complaints"])


@router.post(
    "/classify-text",
    response_model=TextClassificationResponse,
    summary="Classify civic issue category from complaint description and determine assigned department",
)
def classify_complaint_text(
    req: TextClassificationRequest,
    db: Session = Depends(get_db),
):
    """
    Intelligently determines the civic issue category and responsible municipal department
    from citizen text description using multi-lingual NLP keyword & phrase analysis.
    Supports English, Tamil, and Tanglish.
    """
    clean_desc = (req.description or "").strip()
    detected_issue, conf, matched_kw = classify_issue_from_description(clean_desc, req.language)

    if detected_issue:
        routing_info = get_routing_for_issue(detected_issue)
        return TextClassificationResponse(
            success=True,
            detected_issue=detected_issue,
            detected_issue_display=ISSUE_DISPLAY_NAMES.get(detected_issue, detected_issue),
            confidence=conf,
            department_id=routing_info["department_id"],
            department_name=routing_info["department_name"],
            matched_keywords=matched_kw,
            is_uncertain=False,
            routing_message=f"Automatically classified as '{routing_info['class_name']}' and routed to {routing_info['department_name']} ({int(conf * 100)}% match).",
        )
    else:
        # Uncertain classification -> routed for manual review
        return TextClassificationResponse(
            success=False,
            detected_issue=None,
            detected_issue_display="Uncertain (Manual Review Required)",
            confidence=0.0,
            department_id=2,
            department_name="Urban Planning & Municipal Services",
            matched_keywords=[],
            is_uncertain=True,
            routing_message="Category is uncertain from description. Complaint will be routed to Urban Planning & Municipal Services for supervisory human review.",
        )



@router.get(
    "/boundary",
    summary="Get official Coimbatore Municipal Corporation service boundary metadata",
)
def get_service_boundary() -> Dict[str, Any]:
    """
    Returns official Coimbatore City Municipal Corporation (CCMC) bounding box,
    polygon coordinates, center point, and key localities for map display.
    """
    return CoimbatoreBoundaryService.get_service_boundary_info()


@router.post(
    "/validate-location",
    response_model=LocationValidationResponse,
    summary="Validate coordinates against Coimbatore Municipal Corporation boundary",
)
def validate_location(req: LocationValidationRequest) -> LocationValidationResponse:
    """
    Validates if coordinates (lat, lon) lie within Coimbatore City Municipal Corporation service area.
    Returns nearest Coimbatore locality and distance.
    """
    is_valid, err_msg = CoimbatoreBoundaryService.validate_coordinates(req.latitude, req.longitude)
    nearest_name, nearest_dist = CoimbatoreBoundaryService.find_nearest_locality_with_dist(req.latitude, req.longitude)
    return LocationValidationResponse(
        is_valid=is_valid,
        message=err_msg or "Location is within Coimbatore City Municipal Corporation service area.",
        city="Coimbatore",
        nearest_locality=nearest_name,
        distance_meters=round(nearest_dist, 1),
    )


@router.get(
    "/search-location",
    response_model=LocationSearchResponse,
    summary="Search for place name, landmark or area in Coimbatore",
)
def search_location(
    q: str,
) -> LocationSearchResponse:
    """
    Search for a familiar place name, area, or landmark (e.g., 'Gandhipuram, Coimbatore').
    Returns matching location candidates with verified coordinates and formatted addresses.
    Never silently substitutes a default location.
    """
    query_str = (q or "").strip()
    if not query_str or len(query_str) < 2:
        return LocationSearchResponse(
            success=False,
            query=query_str,
            count=0,
            results=[],
            message="Please enter a location, area or landmark with at least 2 characters.",
        )

    results_data = GeocodingService.search_location(query_str)
    results = [LocationSearchResult(**r) for r in results_data]

    msg = None
    if not results:
        msg = f"No locations found for '{query_str}'. Please check the place name or pick directly on the map."

    return LocationSearchResponse(
        success=bool(results),
        query=query_str,
        count=len(results),
        results=results,
        message=msg,
    )


@router.get(
    "/reverse-geocode",
    summary="Reverse geocode coordinates to readable place name and address",
)
def reverse_geocode(
    latitude: float,
    longitude: float,
) -> Dict[str, Any]:
    """
    Converts GPS latitude/longitude into a human-readable place name, landmark, and formatted address.
    """
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Latitude must be between -90 and 90, and longitude between -180 and 180.",
        )
    return GeocodingService.reverse_geocode(latitude, longitude)




@router.post(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
    summary="Check for possible duplicate civic complaints",
)
def check_duplicate_complaint(
    req: DuplicateCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluate potential duplicate civic complaints using:
    - TF-IDF Cosine Similarity on normalized description
    - Haversine geographic distance in meters
    - Canonical issue type matching
    - Deterministic duplicate score

    Does NOT create, update, or reject any complaint.
    Strictly preserves citizen privacy (no emails, passwords, tokens, or phone numbers).
    """
    clean_issue = (req.issue_type or "").strip().lower()
    if clean_issue not in VALID_ISSUE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid issue type '{req.issue_type}'. Must be one of: {sorted(list(VALID_ISSUE_TYPES))}",
        )

    result = DuplicateService.check_for_duplicates(
        db=db,
        issue_type=clean_issue,
        description=req.description,
        latitude=req.latitude,
        longitude=req.longitude,
        exclude_complaint_id=req.exclude_complaint_id,
    )

    return DuplicateCheckResponse(
        has_possible_duplicate=result["has_possible_duplicate"],
        candidates=result["candidates"],
    )


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new civic complaint (Citizens only)",
)
def register_complaint(
    req: ComplaintCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Register a new civic complaint.
    - Requires valid JWT issued by FastAPI authentication.
    - Authenticated user ID is strictly extracted from JWT.
    - Deterministically routes to appropriate Department based on confirmed issue type.
    - Sets initial status to SUBMITTED and logs status history & audit trail.
    """
    import time, logging
    log = logging.getLogger("app.complaints.route")
    t0 = time.perf_counter()
    log.info(f"[ROUTE] POST /api/v1/complaints received: user={current_user.email} (id={current_user.id}), issue_type={req.issue_type}")

    complaint = create_new_complaint(req=req, current_user=current_user, db=db)

    t_service = time.perf_counter()
    response = build_complaint_response(complaint)
    t_end = time.perf_counter()
    log.info(f"[ROUTE] POST /api/v1/complaints completed in {round((t_end - t0)*1000, 2)}ms (service: {round((t_service - t0)*1000, 2)}ms, response: {round((t_end - t_service)*1000, 2)}ms) -> {complaint.complaint_id}")

    return response


@router.post(
    "/{complaint_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload image, video, or audio evidence for a complaint",
)
def upload_complaint_evidence(
    complaint_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Securely attach photographic, video, or audio evidence to a complaint.
    - Validates file type, extension, and file size limits.
    - Stores file on disk using a safe server-generated filename.
    - Strictly avoids storing raw binary blobs in PostgreSQL.
    - Computes and stores SHA-256 integrity hash.
    """
    # Verify complaint exists and belongs to the current user
    complaint = (
        db.query(Complaint)
        .filter(Complaint.complaint_id == complaint_id.strip())
        .first()
    )
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found.",
        )

    # Authorization check: only complaint owner can upload evidence
    if complaint.user_id != current_user.id and current_user.role.upper() != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you are not authorized to modify this complaint.",
        )

    evidence = save_evidence_file(
        file=file,
        complaint_id=complaint.id,
        uploaded_by=current_user.id,
        db=db,
    )

    return EvidenceResponse(
        id=evidence.id,
        file_type=evidence.file_type,
        sha256_hash=evidence.sha256_hash,
        file_path=evidence.file_path,
        created_at=evidence.created_at,
    )


@router.get(
    "",
    response_model=ComplaintListResponse,
    summary="List complaints for current citizen",
)
def list_my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all complaints lodged by the authenticated citizen.
    Citizens can ONLY view their own complaints.
    """
    query = (
        db.query(Complaint)
        .filter(Complaint.user_id == current_user.id)
        .order_by(Complaint.created_at.desc())
    )
    complaints = query.all()
    items = [build_complaint_response(c) for c in complaints]

    return ComplaintListResponse(
        total=len(items),
        items=items,
    )


def _authorize_complaint_access(complaint: Complaint, current_user: User):
    if current_user.role.upper() == UserRole.ADMIN:
        return
    if current_user.role.upper() == UserRole.CITIZEN:
        if complaint.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: you do not have permission to view this complaint.",
            )
        return
    if current_user.role.upper() == UserRole.OFFICER:
        if complaint.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Complaint '{complaint.complaint_id}' belongs to another department.",
            )
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden.")


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="Retrieve single complaint by ID",
)
def get_complaint_by_id(
    complaint_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve full complaint details including status history and evidence metadata.
    Enforces strict access control: citizens can only access their own complaints,
    and officers can only access complaints belonging to their assigned department.
    """
    complaint = (
        db.query(Complaint)
        .filter(Complaint.complaint_id == complaint_id.strip())
        .first()
    )
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _authorize_complaint_access(complaint, current_user)
    return build_complaint_response(complaint)


@router.get(
    "/{complaint_id}/letter",
    summary="Get official complaint grievance letter (JSON & Text)",
)
def get_complaint_letter(
    complaint_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns official municipal complaint letter data and formatted text.
    Enforces strict citizen and department officer authorization.
    """
    complaint = (
        db.query(Complaint)
        .filter(Complaint.complaint_id == complaint_id.strip())
        .first()
    )
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _authorize_complaint_access(complaint, current_user)
    from app.services.letter_service import ComplaintLetterService

    return {
        "status": "success",
        "complaint_id": complaint.complaint_id,
        "letter": ComplaintLetterService.generate_letter_dict(complaint),
        "formatted_text": ComplaintLetterService.generate_letter_text(complaint),
    }


@router.get(
    "/{complaint_id}/letter/pdf",
    summary="Download official complaint grievance letter as PDF",
)
def download_complaint_letter_pdf(
    complaint_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates and returns an official Coimbatore Municipal Corporation (CCMC)
    grievance intimation letter as a downloadable PDF.
    Enforces strict citizen ownership and officer department authorization.
    """
    complaint = (
        db.query(Complaint)
        .filter(Complaint.complaint_id == complaint_id.strip())
        .first()
    )
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _authorize_complaint_access(complaint, current_user)
    from app.services.letter_service import ComplaintLetterService

    pdf_bytes = ComplaintLetterService.generate_letter_pdf(complaint)
    filename = f"CCMC_Grievance_Letter_{complaint.complaint_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
