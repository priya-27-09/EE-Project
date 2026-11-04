import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

logger = logging.getLogger("app.complaints")

from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_NEEDS_HUMAN_REVIEW,
    ISSUE_DISPLAY_NAMES,
    ISSUE_UNCLASSIFIED,
)
from app.complaints.schemas import (
    ComplaintCreateRequest,
    ComplaintResponse,
    DepartmentBriefResponse,
    EvidenceResponse,
    StatusHistoryResponse,
    DuplicateCandidateResponse,
)
from app.services.routing_service import (
    route_issue_to_department,
    resolve_canonical_issue,
    classify_issue_from_description,
)
from app.services.severity_service import determine_baseline_severity
from app.services.id_generator import generate_complaint_id
from app.services.status_service import record_initial_status
from app.services.audit_service import record_audit_log
from app.i18n.translation_service import TranslationService


def build_complaint_response(complaint: Complaint) -> ComplaintResponse:
    """Helper to transform a Complaint ORM model into a ComplaintResponse schema."""
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

    return ComplaintResponse(
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
        address=complaint.address,
        place_name=complaint.place_name,
        severity=complaint.severity,
        severity_score=complaint.severity_score,
        ai_confidence=complaint.ai_confidence,
        status=complaint.status,
        department=dept_brief,
        evidences=evidences_list,
        status_history=history_list,
        possible_duplicates=duplicates_list,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )


def create_new_complaint(
    req: ComplaintCreateRequest,
    current_user: User,
    db: Session,
) -> Complaint:
    """
    Core complaint creation logic:
    - Verifies user is a CITIZEN.
    - Generates unique complaint ID (CG-YYYY-XXXXXX).
    - Routes issue to department deterministically.
    - Determines baseline severity.
    - Preserves exact citizen original_text and original_language without modification.
    - Prepares processed_text for search/duplicate analysis.
    - Persists Complaint, ComplaintStatusHistory, DuplicateAnalysis, and AuditLog in PostgreSQL.
    """
    t_start = time.perf_counter()
    logger.info(f"[TIMING] Complaint registration request started for user_id={current_user.id}, issue_type={req.issue_type}")

    if current_user.role.upper() != UserRole.CITIZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered CITIZEN accounts are authorized to lodge civic complaints.",
        )

    # 1. Location & Coimbatore Boundary validation
    from app.core.config import settings
    from app.services.boundary_service import CoimbatoreBoundaryService

    should_enforce = req.enforce_boundary
    if should_enforce is None:
        should_enforce = getattr(settings, "COIMBATORE_SERVICE_BOUNDARY_ENFORCED", False)

    if should_enforce and req.latitude is not None and req.longitude is not None:
        is_valid, err_msg = CoimbatoreBoundaryService.validate_coordinates(req.latitude, req.longitude)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=err_msg,
            )

    # Resolve address and place_name
    user_place_name = (req.place_name or "").strip() or None
    resolved_address = (req.address or "").strip() or None
    if not resolved_address and user_place_name:
        resolved_address = user_place_name
    if not resolved_address and req.latitude is not None and req.longitude is not None:
        if CoimbatoreBoundaryService.is_within_bounding_box(req.latitude, req.longitude):
            loc_name, _ = CoimbatoreBoundaryService.find_nearest_locality_with_dist(req.latitude, req.longitude)
            resolved_address = f"{loc_name}, Coimbatore, Tamil Nadu"
    if not user_place_name and resolved_address:
        user_place_name = resolved_address.split(",")[0].strip()

    t_loc = time.perf_counter()
    logger.info(f"[TIMING] Location and boundary check completed in {round((t_loc - t_start)*1000, 2)}ms")

    clean_desc = (req.description or "").strip()
    norm_lang = TranslationService.validate_language(req.original_language)

    # 2. Determine civic issue category and perform automatic department routing
    assigned_issue_type: str = ""
    assigned_status: str = STATUS_SUBMITTED
    assigned_status_remarks: str = ""
    assigned_department = None
    classification_source: str = "MANUAL_CITIZEN_CONFIRMATION"
    verified_ai_conf: Optional[float] = None
    verified_model_ver: Optional[str] = None

    if req.issue_type:
        # Category confirmed or explicitly supplied
        _, class_name, issue_key, _ = resolve_canonical_issue(req.issue_type)
        assigned_issue_type = issue_key
        assigned_department = route_issue_to_department(assigned_issue_type, db)
        assigned_status = STATUS_SUBMITTED

        # Verify whether category originated from an approved active AI model prediction
        if getattr(req, "ai_confidence", None) is not None and getattr(req, "ai_model_version", None):
            from app.models.model_version import ModelVersion
            active_model = (
                db.query(ModelVersion)
                .filter(
                    ModelVersion.model_version == req.ai_model_version,
                    ModelVersion.is_active.is_(True),
                )
                .first()
            )
            if active_model and 0.0 <= float(req.ai_confidence) <= 1.0:
                verified_ai_conf = round(float(req.ai_confidence), 4)
                verified_model_ver = active_model.model_version

        if verified_ai_conf is not None:
            classification_source = "AI_PREDICTION_CONFIRMED"
            assigned_status_remarks = (
                f"Complaint registered with category '{class_name}' (AI prediction with {round(verified_ai_conf * 100, 1)}% confidence confirmed by citizen) and automatically routed to {assigned_department.name}."
            )
        else:
            classification_source = "MANUAL_CITIZEN_CONFIRMATION"
            assigned_status_remarks = (
                f"Complaint registered by citizen with confirmed category '{class_name}' and routed to {assigned_department.name}."
            )
    else:
        # Category NOT supplied -> Automatic description-based classification & department routing
        detected_issue, conf, matched_kw = classify_issue_from_description(clean_desc, norm_lang)

        if detected_issue and conf >= 0.40:
            assigned_issue_type = detected_issue
            assigned_department = route_issue_to_department(assigned_issue_type, db)
            assigned_status = STATUS_SUBMITTED
            classification_source = "NLP_DESCRIPTION_CLASSIFICATION"
            cat_display = ISSUE_DISPLAY_NAMES.get(assigned_issue_type, assigned_issue_type)
            assigned_status_remarks = (
                f"Complaint automatically categorized as '{cat_display}' (confidence: {int(conf * 100)}%) from description and routed to {assigned_department.name}."
            )
        else:
            # Classification uncertain -> Requirement 7:
            # "If image AI is unavailable or confidence is low, use description-based classification where possible.
            # If classification is uncertain, mark the complaint for manual review rather than falsely claiming AI detection."
            assigned_issue_type = ISSUE_UNCLASSIFIED
            assigned_status = STATUS_NEEDS_HUMAN_REVIEW
            classification_source = "UNCERTAIN_NEEDS_REVIEW"
            # Assign to General Grievance / Municipal Services department (id: 2) or default active department
            assigned_department = (
                db.query(Department).filter(Department.id == 2, Department.active.is_(True)).first()
                or db.query(Department).filter(Department.active.is_(True)).first()
            )
            assigned_status_remarks = (
                f"Civic issue category uncertain from citizen description and evidence; automatically routed to {assigned_department.name} for manual supervisory review."
            )

    department = assigned_department
    t_route = time.perf_counter()
    logger.info(f"[TIMING] Department routing completed in {round((t_route - t_loc)*1000, 2)}ms: {department.name}")

    if not clean_desc:
        clean_desc = f"Reported {ISSUE_DISPLAY_NAMES.get(assigned_issue_type, assigned_issue_type)}"

    # 2b. Safe Idempotency Check: prevent rapid duplicates from network retries
    recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
    existing_identical = (
        db.query(Complaint)
        .filter(
            Complaint.user_id == current_user.id,
            Complaint.issue_type == assigned_issue_type,
            Complaint.description == clean_desc,
            Complaint.created_at >= recent_cutoff,
        )
        .order_by(Complaint.created_at.desc())
        .first()
    )
    if existing_identical:
        logger.info(f"[IDEMPOTENCY] Found existing complaint {existing_identical.complaint_id} created within 60s, returning existing record.")
        return existing_identical

    # 3. Baseline severity determination
    baseline_severity = determine_baseline_severity(assigned_issue_type)

    # 4. Generate human-readable unique complaint ID
    public_id = generate_complaint_id(db)
    t_id = time.perf_counter()
    logger.info(f"[TIMING] Unique ID {public_id} generated in {round((t_id - t_route)*1000, 2)}ms")

    # 5. Create Complaint record
    now = datetime.now(timezone.utc)
    processed_repr = TranslationService.prepare_processed_text(clean_desc, norm_lang)

    complaint = Complaint(
        complaint_id=public_id,
        user_id=current_user.id,  # Strictly from authenticated JWT
        department_id=assigned_department.id,
        issue_type=assigned_issue_type,
        description=clean_desc,  # Preserved citizen text
        original_language=norm_lang,
        original_text=clean_desc,  # Exact citizen-provided text
        processed_text=processed_repr,  # Normalized representation for downstream search/duplicate analysis
        translated_text=None,  # No fake translation; stays NULL unless real provider configured
        latitude=req.latitude,
        longitude=req.longitude,
        address=resolved_address,
        place_name=user_place_name,
        severity=baseline_severity,
        severity_score=None,
        ai_confidence=verified_ai_conf,  # Only populated if verified from an active approved production model
        status=assigned_status,
        created_at=now,
        updated_at=now,
    )
    db.add(complaint)
    db.flush()  # Obtain complaint.id for foreign key references

    # If verified active AI prediction was confirmed, record AIPrediction relation
    if verified_ai_conf is not None and verified_model_ver:
        from app.models.prediction import AIPrediction
        pred_rec = AIPrediction(
            complaint_id=complaint.id,
            model_version=verified_model_ver,
            detected_class=class_name,
            confidence=verified_ai_conf,
            bounding_boxes=None,
            created_at=now,
        )
        db.add(pred_rec)

    # 5. Record Initial Status History
    record_initial_status(
        complaint_id=complaint.id,
        user_id=current_user.id,
        db=db,
        remarks=assigned_status_remarks,
    )
    t_insert = time.perf_counter()
    logger.info(f"[TIMING] Complaint record inserted & flushed in {round((t_insert - t_id)*1000, 2)}ms (id={complaint.id})")


    # 6. Run Duplicate Analysis & Link Candidates (Never blocks submission)
    from app.models.duplicate_analysis import DuplicateAnalysis
    from app.services.duplicate_service import DuplicateService, DUPLICATE_FLAG_SCORE_THRESHOLD

    dup_result = DuplicateService.check_for_duplicates(
        db=db,
        issue_type=complaint.issue_type,
        description=complaint.description,
        latitude=float(complaint.latitude) if complaint.latitude is not None else None,
        longitude=float(complaint.longitude) if complaint.longitude is not None else None,
        exclude_db_id=complaint.id,
    )

    if dup_result.get("has_possible_duplicate"):
        for item in dup_result.get("raw_candidates_with_db_id", []):
            if item.get("duplicate_score", 0.0) >= DUPLICATE_FLAG_SCORE_THRESHOLD:
                dup_record = DuplicateAnalysis(
                    complaint_id=complaint.id,
                    possible_duplicate_id=item["db_id"],
                    similarity_score=item["duplicate_score"],
                    created_at=now,
                )
                db.add(dup_record)

    t_dup = time.perf_counter()
    logger.info(f"[TIMING] Duplicate analysis completed in {round((t_dup - t_insert)*1000, 2)}ms")

    # 6b. Repeat Failure Detection (Recurrent issue at same location after resolution)
    repeat_info = {"is_repeat_failure": False}
    try:
        from app.services.repeat_failure_service import RepeatFailureService
        repeat_info = RepeatFailureService.check_for_repeat_failure(complaint, db)
    except Exception:
        pass

    # 6c. SLA & Priority Assessment
    sla_info = {}
    try:
        from app.services.sla_service import SLAManagementService
        sla_info = SLAManagementService.calculate_sla_status(complaint)
    except Exception:
        pass

    # 7. Record Audit Log (strictly sanitized, no credentials)
    record_audit_log(
        action="COMPLAINT_CREATED",
        entity_type="Complaint",
        entity_id=complaint.complaint_id,
        user_id=current_user.id,
        db=db,
        metadata={
            "complaint_id": complaint.complaint_id,
            "issue_type": complaint.issue_type,
            "classification_source": classification_source,
            "ai_confidence": verified_ai_conf,
            "department_id": department.id,
            "department_name": department.name,
            "has_gps": bool(req.latitude is not None and req.longitude is not None),
            "location_source": getattr(req, "location_source", None),
            "location_accuracy": getattr(req, "location_accuracy", None),
            "latitude": req.latitude,
            "longitude": req.longitude,
            "possible_duplicates_found": len(dup_result.get("candidates", [])),
            "is_repeat_failure": repeat_info.get("is_repeat_failure", False),
            "sla_priority": sla_info.get("policy", {}).get("priority") if sla_info else None,
            "sla_hours": sla_info.get("policy", {}).get("sla_hours") if sla_info else None,
        },
    )

    t_audit = time.perf_counter()
    logger.info(f"[TIMING] Repeat failure, SLA, and audit log completed in {round((t_audit - t_dup)*1000, 2)}ms")

    db.commit()
    db.refresh(complaint)

    t_commit = time.perf_counter()
    logger.info(f"[TIMING] DB commit & refresh completed in {round((t_commit - t_audit)*1000, 2)}ms (total DB elapsed: {round((t_commit - t_start)*1000, 2)}ms)")

    # 8. Blockchain Integrity Anchoring (Non-blocking, with hard timeout)
    # Only attempted when blockchain is fully configured; never blocks complaint creation.
    try:
        from app.core.config import settings as _bc_settings
        if _bc_settings.BLOCKCHAIN_ENABLED and _bc_settings.BLOCKCHAIN_CONTRACT_ADDRESS and _bc_settings.BLOCKCHAIN_PRIVATE_KEY:
            import logging as _bc_logging
            import concurrent.futures
            from app.services.blockchain_service import BlockchainService
            from app.models.blockchain_record import EVENT_COMPLAINT_CREATED

            complaint_payload = {
                "complaint_id": complaint.complaint_id,
                "event_type": EVENT_COMPLAINT_CREATED,
                "issue_type": complaint.issue_type,
                "department_id": complaint.department_id,
                "severity": complaint.severity,
                "created_at": complaint.created_at.isoformat(),
            }

            def _anchor_blockchain():
                BlockchainService.anchor_event(
                    complaint_id=complaint.id,
                    complaint_public_id=complaint.complaint_id,
                    event_type=EVENT_COMPLAINT_CREATED,
                    payload=complaint_payload,
                    unique_key=f"created_{complaint.created_at.isoformat()}",
                    db=db,
                    user_id=current_user.id,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_anchor_blockchain)
                try:
                    future.result(timeout=8)  # Hard 8-second cap
                except concurrent.futures.TimeoutError:
                    _bc_logging.warning(
                        "Blockchain anchor timed out for complaint %s; "
                        "record will remain PENDING and can be retried by admin.",
                        complaint.complaint_id,
                    )
                except Exception as bc_err:
                    _bc_logging.warning(
                        "Blockchain anchor failed for %s: %s",
                        complaint.complaint_id, bc_err,
                    )
        else:
            pass  # Blockchain not configured — skip entirely, no imports or DB writes
    except Exception:
        # Resilient design: Blockchain errors must NEVER fail the primary complaint creation
        pass

    return complaint

