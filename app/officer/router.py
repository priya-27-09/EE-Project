from datetime import datetime, timezone
import math
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.status_history import ComplaintStatusHistory
from app.models.complaint_note import ComplaintNote
from app.models.evidence import ComplaintEvidence
from app.models.resolution_verification import ResolutionVerification
from app.auth.dependencies import get_current_user, require_roles
from app.officer.verification_schemas import (
    ResolutionMetricsResponse,
    ResolutionVerificationResponse,
    ResolutionReviewRequest,
)
from app.services.resolution_verification_service import (
    run_resolution_verification,
    record_human_review as record_resolution_human_review,
)
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_AI_VERIFIED,
    STATUS_DEPARTMENT_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_NEEDS_HUMAN_REVIEW,
    STATUS_REJECTED,
    ISSUE_DISPLAY_NAMES,
)
from app.complaints.schemas import (
    DepartmentBriefResponse,
    EvidenceResponse,
    StatusHistoryResponse,
    DuplicateCandidateResponse,
)
from app.officer.schemas import (
    OfficerDashboardSummary,
    OfficerComplaintBrief,
    OfficerComplaintListResponse,
    OfficerComplaintDetailResponse,
    OfficerStatusUpdateRequest,
    OfficerNoteCreateRequest,
    OfficerNoteResponse,
    OfficerResolutionRequest,
)
from app.services.status_service import transition_complaint_status
from app.services.audit_service import record_audit_log
from app.services.evidence_service import save_evidence_file

router = APIRouter(prefix="/api/v1/officer", tags=["Officer"])


def _find_complaint(complaint_id: str, db: Session) -> Optional[Complaint]:
    """Look up a complaint by canonical complaint_id or fallback integer id."""
    cid = complaint_id.strip()
    complaint = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
    if not complaint and cid.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(cid)).first()
    return complaint


def _verify_officer_department(current_user: User, complaint: Optional[Complaint] = None) -> Optional[int]:
    """
    Enforce strict Department Isolation.
    - If user is OFFICER, verify they have an assigned department.
    - If complaint is provided, verify complaint belongs to officer's assigned department.
    - ADMIN users bypass department isolation for administrative supervision.
    Raises HTTPException(403) on violation.
    """
    if current_user.role.upper() == UserRole.ADMIN:
        return current_user.department_id

    if current_user.role.upper() != UserRole.OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: This resource is restricted to authorized municipal officers.",
        )

    if not current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Officer account is not assigned to any municipal department.",
        )

    if complaint is not None:
        if complaint.department_id != current_user.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Complaint '{complaint.complaint_id}' belongs to another department.",
            )

    return current_user.department_id


def _build_verification_response(ver: ResolutionVerification, complaint: Complaint) -> ResolutionVerificationResponse:
    """Build response for a single ResolutionVerification record."""
    metrics = None
    if ver.structural_similarity is not None or ver.pixel_difference is not None:
        metrics = ResolutionMetricsResponse(
            structural_similarity=ver.structural_similarity,
            pixel_difference=ver.pixel_difference,
            edge_similarity=ver.edge_similarity,
            histogram_similarity=ver.histogram_similarity,
            perceptual_hash_distance=ver.perceptual_hash_distance,
        )

    before_path = ver.before_evidence.file_path if ver.before_evidence else None
    after_path = ver.after_evidence.file_path if ver.after_evidence else None
    reviewer_name = ver.reviewer.name if ver.reviewer else None

    return ResolutionVerificationResponse(
        id=ver.id,
        complaint_id=complaint.complaint_id,
        before_evidence_id=ver.before_evidence_id,
        after_evidence_id=ver.after_evidence_id,
        before_evidence_path=before_path,
        after_evidence_path=after_path,
        verification_status=ver.verification_status,
        verification_score=ver.verification_score,
        human_review_required=ver.human_review_required,
        verification_reason=ver.verification_reason,
        metrics=metrics,
        alignment_status=ver.alignment_status,
        algorithm_version=ver.algorithm_version,
        created_at=ver.created_at,
        reviewed_by_id=ver.reviewed_by_id,
        reviewer_name=reviewer_name,
        reviewed_at=ver.reviewed_at,
        review_decision=ver.review_decision,
        review_notes=ver.review_notes,
    )


def _build_officer_complaint_detail(complaint: Complaint) -> OfficerComplaintDetailResponse:
    """Build full response for officer detail page."""
    dept_brief = None
    if complaint.department:
        dept_brief = DepartmentBriefResponse(
            id=complaint.department.id,
            name=complaint.department.name,
            description=complaint.department.description,
        )

    evidences_list = [
        EvidenceResponse(
            id=ev.id,
            file_type=ev.file_type,
            sha256_hash=ev.sha256_hash,
            file_path=ev.file_path,
            is_resolution=getattr(ev, "is_resolution", False),
            created_at=ev.created_at,
        )
        for ev in complaint.evidences
    ]

    history_list = [
        StatusHistoryResponse(
            id=h.id,
            old_status=h.old_status,
            new_status=h.new_status,
            changed_by=h.changed_by,
            remarks=h.remarks,
            created_at=h.created_at,
        )
        for h in complaint.status_history
    ]

    notes_list = [
        OfficerNoteResponse(
            id=n.id,
            complaint_id=complaint.complaint_id,
            user_id=n.user_id,
            author_name=n.author.name if n.author else "Officer",
            note=n.note,
            created_at=n.created_at,
        )
        for n in (complaint.notes or [])
    ]

    latest_ver_resp = None
    if getattr(complaint, "resolution_verifications", None) and len(complaint.resolution_verifications) > 0:
        latest_ver_resp = _build_verification_response(complaint.resolution_verifications[0], complaint)

    resolution_info = None
    if complaint.resolved_at or complaint.resolution_notes:
        ai_ver_status = "AI-assisted evidence verification not conducted yet."
        ai_ver_score = None
        if latest_ver_resp:
            ai_ver_status = latest_ver_resp.verification_status
            ai_ver_score = latest_ver_resp.verification_score
        resolution_info = {
            "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
            "resolved_by_id": complaint.resolved_by_id,
            "resolved_by_name": complaint.resolved_by.name if complaint.resolved_by else None,
            "resolution_notes": complaint.resolution_notes,
            "ai_verification_status": ai_ver_status,
            "ai_verification_score": ai_ver_score,
        }

    duplicates_list = []
    if getattr(complaint, "duplicate_analyses", None):
        for da in complaint.duplicate_analyses:
            cand = getattr(da, "possible_duplicate", None)
            if cand:
                duplicates_list.append(
                    DuplicateCandidateResponse(
                        complaint_id=cand.complaint_id,
                        issue_type=cand.issue_type,
                        issue_type_display=ISSUE_DISPLAY_NAMES.get(cand.issue_type, cand.issue_type),
                        issue_match=(complaint.issue_type.lower() == cand.issue_type.lower()),
                        text_similarity=round(float(da.similarity_score), 4),
                        distance_meters=None,
                        duplicate_score=round(float(da.similarity_score), 4),
                        reason="Recorded as potential duplicate candidate during registration",
                        status=cand.status,
                        created_at=cand.created_at,
                    )
                )

    # Check for AI prediction if present
    ai_detected_issue = None
    if getattr(complaint, "ai_predictions", None) and len(complaint.ai_predictions) > 0:
        pred = complaint.ai_predictions[0]
        ai_detected_issue = pred.detected_class

    return OfficerComplaintDetailResponse(
        complaint_id=complaint.complaint_id,
        issue_type=complaint.issue_type,
        issue_type_display=ISSUE_DISPLAY_NAMES.get(complaint.issue_type, complaint.issue_type),
        description=complaint.description,
        original_language=complaint.original_language,
        original_text=complaint.original_text,
        processed_text=complaint.processed_text,
        translated_text=complaint.translated_text,
        latitude=float(complaint.latitude) if complaint.latitude is not None else None,
        longitude=float(complaint.longitude) if complaint.longitude is not None else None,
        place_name=getattr(complaint, "place_name", None),
        address=getattr(complaint, "address", None),
        severity=complaint.severity,
        severity_score=complaint.severity_score,
        severity_reason=f"Priority assessment for {ISSUE_DISPLAY_NAMES.get(complaint.issue_type, complaint.issue_type)}",
        ai_confidence=complaint.ai_confidence,
        ai_detected_issue=ai_detected_issue,
        status=complaint.status,
        department=dept_brief,
        evidences=evidences_list,
        status_history=history_list,
        notes=notes_list,
        resolution=resolution_info,
        latest_verification=latest_ver_resp,
        possible_duplicates=duplicates_list,
        citizen_id=complaint.user_id,
        citizen_name=complaint.user.name if complaint.user else "Anonymous Citizen",
        citizen_email=complaint.user.email if complaint.user else None,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )


@router.get(
    "/dashboard",
    response_model=OfficerDashboardSummary,
    summary="Officer Dashboard summary counts from PostgreSQL",
)
def get_officer_dashboard(
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retrieve real database summary statistics for the officer's assigned department.
    Guarantees strict department isolation: counts reflect ONLY the officer's department.
    """
    dept_id = _verify_officer_department(current_user)

    query = db.query(Complaint.status, func.count(Complaint.id))
    if dept_id is not None:
        query = query.filter(Complaint.department_id == dept_id)
    query = query.group_by(Complaint.status)

    status_counts = dict(query.all())

    # Total assigned count
    total_q = db.query(func.count(Complaint.id))
    if dept_id is not None:
        total_q = total_q.filter(Complaint.department_id == dept_id)
    total_assigned = total_q.scalar() or 0

    dept_name = None
    if current_user.department:
        dept_name = current_user.department.name
    elif dept_id:
        dept = db.query(Department).filter(Department.id == dept_id).first()
        dept_name = dept.name if dept else None

    from app.services.routing_service import CANONICAL_ROUTING_TABLE
    allowed_issues = []
    if current_user.role.upper() == UserRole.ADMIN:
        allowed_issues = [{"key": v["issue_type"], "display": v["class_name"]} for v in CANONICAL_ROUTING_TABLE.values()]
    elif dept_name:
        dept_name_lower = dept_name.lower()
        for v in CANONICAL_ROUTING_TABLE.values():
            if v["department_name"].lower() in dept_name_lower or dept_name_lower in v["department_name"].lower():
                allowed_issues.append({"key": v["issue_type"], "display": v["class_name"]})
    else:
        allowed_issues = [{"key": v["issue_type"], "display": v["class_name"]} for v in CANONICAL_ROUTING_TABLE.values()]

    return OfficerDashboardSummary(
        total_assigned=total_assigned,
        submitted=status_counts.get(STATUS_SUBMITTED, 0),
        ai_verified=status_counts.get(STATUS_AI_VERIFIED, 0),
        department_assigned=status_counts.get(STATUS_DEPARTMENT_ASSIGNED, 0) + status_counts.get("ASSIGNED", 0),
        in_progress=status_counts.get(STATUS_IN_PROGRESS, 0),
        resolved=status_counts.get(STATUS_RESOLVED, 0),
        needs_human_review=status_counts.get(STATUS_NEEDS_HUMAN_REVIEW, 0),
        department_id=dept_id,
        department_name=dept_name,
        officer_name=current_user.name,
        officer_role=current_user.role,
        allowed_issue_types=allowed_issues,
    )


@router.get(
    "/complaints",
    response_model=OfficerComplaintListResponse,
    summary="List complaints assigned to officer's department with filtering & pagination",
)
def list_officer_complaints(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    issue_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retrieve complaints assigned to the officer's department.
    Enforces Department Isolation and offers filtering by status, severity, issue type, date, and ID search.
    """
    dept_id = _verify_officer_department(current_user)

    query = db.query(Complaint)
    if dept_id is not None:
        query = query.filter(Complaint.department_id == dept_id)

    # Status filter
    if status_filter:
        clean_status = status_filter.strip().upper()
        if clean_status == "DEPARTMENT_ASSIGNED":
            query = query.filter(Complaint.status.in_([STATUS_DEPARTMENT_ASSIGNED, "ASSIGNED"]))
        else:
            query = query.filter(Complaint.status == clean_status)

    # Severity filter
    if severity:
        query = query.filter(Complaint.severity == severity.strip().upper())

    # Issue type filter with strict department isolation
    if issue_type:
        clean_issue = issue_type.strip().lower()
        if current_user.role.upper() != UserRole.ADMIN and current_user.department:
            from app.services.routing_service import CANONICAL_ROUTING_TABLE
            dept_name_lower = current_user.department.name.lower()
            dept_allowed = [
                v["issue_type"] for v in CANONICAL_ROUTING_TABLE.values()
                if v["department_name"].lower() in dept_name_lower or dept_name_lower in v["department_name"].lower()
            ]
            if dept_allowed and clean_issue not in dept_allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access forbidden: Issue type '{clean_issue}' does not belong to your authorized department ({current_user.department.name}).",
                )
        query = query.filter(Complaint.issue_type == clean_issue)

    # Search filter (Complaint ID or description)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((Complaint.complaint_id.ilike(s)) | (Complaint.description.ilike(s)))

    # Date range filters
    if date_from:
        try:
            df = datetime.fromisoformat(date_from)
            query = query.filter(Complaint.created_at >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            query = query.filter(Complaint.created_at <= dt)
        except ValueError:
            pass

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    complaints = query.order_by(desc(Complaint.created_at)).offset(offset).limit(page_size).all()

    items = []
    for c in complaints:
        has_ev = bool(c.evidences and len(c.evidences) > 0)
        has_dup = bool(getattr(c, "duplicate_analyses", None) and len(c.duplicate_analyses) > 0)
        items.append(
            OfficerComplaintBrief(
                id=c.id,
                complaint_id=c.complaint_id,
                issue_type=c.issue_type,
                issue_type_display=ISSUE_DISPLAY_NAMES.get(c.issue_type, c.issue_type),
                department_id=c.department_id,
                department_name=c.department.name if c.department else None,
                severity=c.severity,
                status=c.status,
                created_at=c.created_at,
                latitude=float(c.latitude) if c.latitude is not None else None,
                longitude=float(c.longitude) if c.longitude is not None else None,
                place_name=getattr(c, "place_name", None),
                address=getattr(c, "address", None),
                ai_confidence=c.ai_confidence,
                has_evidence=has_ev,
                has_duplicate_warning=has_dup,
            )
        )


    dept_name = current_user.department.name if current_user.department else None

    return OfficerComplaintListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        department_name=dept_name,
        items=items,
    )


@router.get(
    "/complaints/{complaint_id}",
    response_model=OfficerComplaintDetailResponse,
    summary="Retrieve single complaint detail with department isolation and audit logging",
)
def get_officer_complaint(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retrieve complaint details for officer.
    Strictly verifies complaint belongs to officer's assigned department.
    Records COMPLAINT_VIEWED audit trail.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    # Record safe audit log
    record_audit_log(
        action="COMPLAINT_VIEWED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "officer_id": current_user.id,
            "department_id": current_user.department_id,
            "complaint_id": complaint.complaint_id,
        },
    )
    db.commit()

    return _build_officer_complaint_detail(complaint)


@router.put(
    "/complaints/{complaint_id}/status",
    response_model=OfficerComplaintDetailResponse,
    summary="Update complaint status using canonical state machine (PUT alias)",
)
@router.patch(
    "/complaints/{complaint_id}/status",
    response_model=OfficerComplaintDetailResponse,
    summary="Update complaint status using canonical state machine",
)
def update_officer_complaint_status(
    complaint_id: str,
    req: OfficerStatusUpdateRequest,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Update complaint status following canonical workflow rules.
    1. Authenticates officer.
    2. Enforces department isolation.
    3. Validates status transition (raises 409 Conflict if invalid).
    4. Records status history and audit log.
    5. Saves officer note if remarks are provided.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    old_status = complaint.status
    clean_target = (req.status or "").strip().upper()

    # Enforce state transition
    transition_complaint_status(
        complaint=complaint,
        new_status=clean_target,
        changed_by_user_id=current_user.id,
        db=db,
        remarks=req.note or f"Status changed from {old_status} to {clean_target} by officer {current_user.name}.",
    )

    # Save note if provided
    if req.note and req.note.strip():
        note_record = ComplaintNote(
            complaint_id=complaint.id,
            user_id=current_user.id,
            note=req.note.strip(),
            created_at=datetime.now(timezone.utc),
        )
        db.add(note_record)

    # Record audit log
    record_audit_log(
        action="STATUS_CHANGED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "officer_id": current_user.id,
            "department_id": current_user.department_id,
            "old_status": old_status,
            "new_status": clean_target,
            "has_note": bool(req.note),
        },
    )

    db.commit()
    db.refresh(complaint)

    return _build_officer_complaint_detail(complaint)


@router.post(
    "/complaints/{complaint_id}/notes",
    response_model=OfficerNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add operational officer note to complaint",
)
def add_officer_note(
    complaint_id: str,
    req: OfficerNoteCreateRequest,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Save an operational officer note to PostgreSQL.
    Enforces department isolation and records audit trail.
    """
    clean_note = (req.note or "").strip()
    if not clean_note:
        raise HTTPException(
            status_code=422,
            detail="Note content cannot be empty.",
        )

    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    now = datetime.now(timezone.utc)
    note_record = ComplaintNote(
        complaint_id=complaint.id,
        user_id=current_user.id,
        note=clean_note,
        created_at=now,
    )
    db.add(note_record)

    # Record audit log
    record_audit_log(
        action="NOTE_ADDED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "officer_id": current_user.id,
            "department_id": current_user.department_id,
            "note_length": len(clean_note),
        },
    )

    db.commit()
    db.refresh(note_record)

    return OfficerNoteResponse(
        id=note_record.id,
        complaint_id=complaint.complaint_id,
        user_id=current_user.id,
        author_name=current_user.name,
        note=note_record.note,
        created_at=note_record.created_at,
    )


@router.post(
    "/complaints/{complaint_id}/resolve",
    response_model=OfficerComplaintDetailResponse,
    summary="Resolve complaint with resolution note (alias)",
)
@router.post(
    "/complaints/{complaint_id}/resolution",
    response_model=OfficerComplaintDetailResponse,
    summary="Resolve complaint with resolution note, timestamp, and audit trail",
)
def resolve_officer_complaint(
    complaint_id: str,
    req: OfficerResolutionRequest,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Mark complaint as RESOLVED with mandatory resolution notes.
    1. Validates officer department isolation.
    2. Validates status transition (must be IN_PROGRESS or NEEDS_HUMAN_REVIEW).
    3. Saves resolved_at timestamp, resolved_by_id, and resolution_notes.
    4. Creates status history and audit record.
    """
    clean_note = (req.resolution_note or "").strip()
    if len(clean_note) < 3:
        raise HTTPException(
            status_code=422,
            detail="Resolution note must contain at least 3 characters describing the action taken.",
        )

    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    old_status = complaint.status

    # Validate state transition to RESOLVED
    transition_complaint_status(
        complaint=complaint,
        new_status=STATUS_RESOLVED,
        changed_by_user_id=current_user.id,
        db=db,
        remarks=f"Complaint resolved: {clean_note}",
    )

    now = datetime.now(timezone.utc)
    complaint.resolved_at = now
    complaint.resolved_by_id = current_user.id
    complaint.resolution_notes = clean_note

    # Add resolution note to notes table as well
    res_note = ComplaintNote(
        complaint_id=complaint.id,
        user_id=current_user.id,
        note=f"[RESOLUTION] {clean_note}",
        created_at=now,
    )
    db.add(res_note)

    # Record audit log
    record_audit_log(
        action="RESOLUTION_SUBMITTED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "officer_id": current_user.id,
            "department_id": current_user.department_id,
            "old_status": old_status,
            "new_status": STATUS_RESOLVED,
            "resolved_at": now.isoformat(),
        },
    )

    db.commit()
    db.refresh(complaint)

    return _build_officer_complaint_detail(complaint)


@router.post(
    "/complaints/{complaint_id}/resolution-evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload resolution evidence photo/video by officer",
)
def upload_resolution_evidence(
    complaint_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Attach photographic or video proof of resolution.
    Stores safe file path, SHA-256 hash, and marks is_resolution=True.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    evidence = save_evidence_file(
        file=file,
        complaint_id=complaint.id,
        uploaded_by=current_user.id,
        db=db,
    )
    evidence.is_resolution = True

    record_audit_log(
        action="RESOLUTION_EVIDENCE_UPLOADED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "evidence_id": evidence.id,
            "file_type": evidence.file_type,
            "sha256": evidence.sha256_hash,
            "is_resolution": True,
        },
    )

    db.commit()
    db.refresh(evidence)

    # Blockchain Integrity Anchoring (Step 10)
    # Reuses existing evidence SHA-256; NEVER uploads images or files to blockchain
    try:
        from app.services.blockchain_service import BlockchainService
        from app.models.blockchain_record import EVENT_RESOLUTION_EVIDENCE_ADDED

        evidence_payload = {
            "complaint_id": complaint.complaint_id,
            "event_type": EVENT_RESOLUTION_EVIDENCE_ADDED,
            "evidence_id": evidence.id,
            "evidence_sha256": evidence.sha256_hash,
            "timestamp": evidence.created_at.isoformat(),
        }

        BlockchainService.anchor_event(
            complaint_id=complaint.id,
            complaint_public_id=complaint.complaint_id,
            event_type=EVENT_RESOLUTION_EVIDENCE_ADDED,
            payload=evidence_payload,
            unique_key=f"evidence_{evidence.id}",
            db=db,
            user_id=current_user.id,
        )
    except Exception:
        # Resilient design: Blockchain errors must NEVER fail the evidence upload
        pass

    return EvidenceResponse(
        id=evidence.id,
        file_type=evidence.file_type,
        sha256_hash=evidence.sha256_hash,
        file_path=evidence.file_path,
        is_resolution=evidence.is_resolution,
        created_at=evidence.created_at,
    )



@router.post(
    "/complaints/{complaint_id}/resolution/verify",
    response_model=ResolutionVerificationResponse,
    summary="Run AI-assisted resolution evidence verification using computer vision",
)
def verify_complaint_resolution(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Execute deterministic visual verification comparing citizen before-evidence
    with officer after-evidence using classical computer vision.
    Enforces department isolation and logs audit event.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    verification = run_resolution_verification(
        complaint=complaint,
        officer_user_id=current_user.id,
        db=db,
    )
    return _build_verification_response(verification, complaint)


@router.get(
    "/complaints/{complaint_id}/resolution/verification",
    response_model=Optional[ResolutionVerificationResponse],
    summary="Get latest AI-assisted resolution verification result",
)
def get_complaint_resolution_verification(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Retrieve latest resolution verification record for a complaint.
    Enforces department isolation.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    latest_ver = (
        db.query(ResolutionVerification)
        .filter(ResolutionVerification.complaint_id == complaint.id)
        .order_by(desc(ResolutionVerification.created_at))
        .first()
    )
    if not latest_ver:
        return None

    return _build_verification_response(latest_ver, complaint)


@router.post(
    "/complaints/{complaint_id}/resolution/review",
    response_model=ResolutionVerificationResponse,
    summary="Record officer human review decision on resolution evidence",
)
def review_complaint_resolution(
    complaint_id: str,
    req: ResolutionReviewRequest,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Record officer human review (APPROVED or REJECTED) with mandatory explanation.
    Preserves all automated computer vision metrics and logs audit event.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )

    _verify_officer_department(current_user, complaint)

    try:
        updated_ver = record_resolution_human_review(
            complaint=complaint,
            officer_user_id=current_user.id,
            decision=req.decision,
            notes=req.review_notes,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return _build_verification_response(updated_ver, complaint)


@router.get(
    "/complaints/{complaint_id}/satellite-assessment",
    summary="Get defensible spatial and satellite-assisted evidence evaluation",
)
def get_satellite_assessment(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Combines spatial location within Coimbatore corporation, citizen evidence,
    and satellite imagery resolution metadata to provide a verification recommendation.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )
    _verify_officer_department(current_user, complaint)

    from app.services.satellite_verification_service import SatelliteAssistedVerificationService
    return SatelliteAssistedVerificationService.evaluate_complaint_evidence(complaint, db)


@router.get(
    "/complaints/{complaint_id}/evidence-screening",
    summary="Get explainable evidence integrity screening and duplicate analysis",
)
def get_evidence_screening(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Screens all evidence files attached to this complaint for raster corruption,
    perceptual duplicates, and editing signatures.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )
    _verify_officer_department(current_user, complaint)

    from app.services.evidence_screening_service import EvidenceScreeningService
    results = []
    for ev in (complaint.evidences or []):
        r = EvidenceScreeningService.screen_evidence_file(ev.file_path, db, complaint, ev.id)
        r["evidence_id"] = ev.id
        r["file_path"] = ev.file_path
        results.append(r)

    return {
        "status": "success",
        "complaint_id": complaint.complaint_id,
        "evidence_count": len(results),
        "screenings": results,
    }


@router.get(
    "/complaints/{complaint_id}/sla",
    summary="Get priority and SLA deadline status with escalation indicators",
)
def get_sla_status(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Computes SLA deadline, hours remaining, and overdue status based on configurable civic issue tiers.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )
    _verify_officer_department(current_user, complaint)

    from app.services.sla_service import SLAManagementService
    return SLAManagementService.calculate_sla_status(complaint)


@router.get(
    "/complaints/{complaint_id}/repeat-failure",
    summary="Detect if this complaint reports a recurrent failure after recent resolution",
)
def get_repeat_failure(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Checks if a previously resolved complaint of the same type within 250 meters exists.
    """
    complaint = _find_complaint(complaint_id, db)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' was not found.",
        )
    _verify_officer_department(current_user, complaint)

    from app.services.repeat_failure_service import RepeatFailureService
    return RepeatFailureService.check_for_repeat_failure(complaint, db)



