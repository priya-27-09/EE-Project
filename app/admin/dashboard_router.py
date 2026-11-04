"""
AI Civic Guardian — Admin Dashboard & Management Router
Provides comprehensive supervision, complaint inspection, department overview,
officer account management, status history, and system audit logs.
All endpoints require ADMIN role (HTTP 401 unauthenticated, HTTP 403 unauthorized).
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.status_history import ComplaintStatusHistory
from app.models.audit_log import AuditLog
from app.auth.dependencies import require_roles
from app.complaints.constants import ISSUE_DISPLAY_NAMES
from app.core.auth import hash_password
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Dashboard"])


# --- Schemas ---

class AdminOverviewResponse(BaseModel):
    total_complaints: int
    pending_complaints: int
    resolved_complaints: int
    rejected_complaints: int
    total_departments: int
    total_officers: int
    total_citizens: int
    status_breakdown: Dict[str, int]
    severity_breakdown: Dict[str, int]
    department_breakdown: List[Dict[str, Any]]


class AdminComplaintItem(BaseModel):
    id: int
    complaint_id: str
    issue_type: str
    issue_type_display: str
    description: Optional[str] = None
    severity: str
    severity_score: Optional[float] = None
    status: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_name: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdminComplaintListResponse(BaseModel):
    total: int
    items: List[AdminComplaintItem]


class AdminDepartmentItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    active: bool
    complaint_count: int
    officer_count: int


class AdminOfficerItem(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    created_at: datetime


class AdminOfficerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    department_id: Optional[int] = None


class AdminOfficerDepartmentUpdate(BaseModel):
    department_id: Optional[int] = None


class AdminStatusHistoryItem(BaseModel):
    id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by_id: Optional[int] = None
    changed_by_name: Optional[str] = None
    remarks: Optional[str] = None
    created_at: datetime


class AdminAuditLogItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class AdminAuditLogListResponse(BaseModel):
    total: int
    items: List[AdminAuditLogItem]


# --- Endpoints ---

@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Admin high-level system metrics overview",
)
def get_admin_overview(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve full system metrics across all complaints, departments, and users."""
    total_complaints = db.query(func.count(Complaint.id)).scalar() or 0
    resolved_complaints = db.query(func.count(Complaint.id)).filter(Complaint.status == "RESOLVED").scalar() or 0
    rejected_complaints = db.query(func.count(Complaint.id)).filter(Complaint.status == "REJECTED").scalar() or 0
    pending_complaints = total_complaints - resolved_complaints - rejected_complaints

    total_departments = db.query(func.count(Department.id)).scalar() or 0
    total_officers = db.query(func.count(User.id)).filter(User.role == UserRole.OFFICER).scalar() or 0
    total_citizens = db.query(func.count(User.id)).filter(User.role == UserRole.CITIZEN).scalar() or 0

    # Status breakdown
    status_q = db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
    status_breakdown = {s: c for s, c in status_q}

    # Severity breakdown
    sev_q = db.query(Complaint.severity, func.count(Complaint.id)).group_by(Complaint.severity).all()
    severity_breakdown = {s: c for s, c in sev_q}

    # Department breakdown
    dept_q = (
        db.query(
            Department.id,
            Department.name,
            func.count(Complaint.id).label("complaint_count"),
        )
        .outerjoin(Complaint, Department.id == Complaint.department_id)
        .group_by(Department.id, Department.name)
        .order_by(Department.id)
        .all()
    )
    department_breakdown = [
        {"department_id": d[0], "department_name": d[1], "complaint_count": d[2]}
        for d in dept_q
    ]

    return AdminOverviewResponse(
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        resolved_complaints=resolved_complaints,
        rejected_complaints=rejected_complaints,
        total_departments=total_departments,
        total_officers=total_officers,
        total_citizens=total_citizens,
        status_breakdown=status_breakdown,
        severity_breakdown=severity_breakdown,
        department_breakdown=department_breakdown,
    )


@router.get(
    "/complaints",
    response_model=AdminComplaintListResponse,
    summary="Admin query of all complaints across departments",
)
def get_admin_complaints(
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """List all complaints with full cross-department supervision and filters."""
    q = db.query(Complaint)
    if department_id is not None:
        q = q.filter(Complaint.department_id == department_id)
    if status_filter:
        q = q.filter(Complaint.status == status_filter.upper())
    if severity:
        q = q.filter(Complaint.severity == severity.upper())

    total = q.count()
    complaints = q.order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()

    items = []
    for c in complaints:
        items.append(
            AdminComplaintItem(
                id=c.id,
                complaint_id=c.complaint_id,
                issue_type=c.issue_type,
                issue_type_display=ISSUE_DISPLAY_NAMES.get(c.issue_type, c.issue_type),
                description=c.description,
                severity=c.severity,
                severity_score=c.severity_score,
                status=c.status,
                department_id=c.department_id,
                department_name=c.department.name if c.department else None,
                user_id=c.user_id,
                user_name=c.user.name if c.user else None,
                user_email=c.user.email if c.user else None,
                latitude=float(c.latitude) if c.latitude is not None else None,
                longitude=float(c.longitude) if c.longitude is not None else None,
                place_name=c.place_name,
                address=c.address,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )

    return AdminComplaintListResponse(total=total, items=items)


@router.get(
    "/departments",
    response_model=List[AdminDepartmentItem],
    summary="Admin list of departments with metrics",
)
def get_admin_departments(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve all municipal departments with complaint and officer metrics."""
    departments = db.query(Department).order_by(Department.id).all()

    # Pre-aggregate complaint counts
    complaint_counts = dict(
        db.query(Complaint.department_id, func.count(Complaint.id))
        .filter(Complaint.department_id.isnot(None))
        .group_by(Complaint.department_id)
        .all()
    )

    # Pre-aggregate officer counts
    officer_counts = dict(
        db.query(User.department_id, func.count(User.id))
        .filter(User.role == UserRole.OFFICER, User.department_id.isnot(None))
        .group_by(User.department_id)
        .all()
    )

    result = []
    for d in departments:
        result.append(
            AdminDepartmentItem(
                id=d.id,
                name=d.name,
                description=d.description,
                active=d.active,
                complaint_count=complaint_counts.get(d.id, 0),
                officer_count=officer_counts.get(d.id, 0),
            )
        )
    return result


@router.get(
    "/officers",
    response_model=List[AdminOfficerItem],
    summary="Admin list of officer accounts and department assignments",
)
def get_admin_officers(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """List all department officer accounts and their current department assignments."""
    officers = (
        db.query(User)
        .filter(User.role == UserRole.OFFICER)
        .order_by(User.department_id, User.name)
        .all()
    )

    result = []
    for o in officers:
        result.append(
            AdminOfficerItem(
                id=o.id,
                name=o.name,
                email=o.email,
                role=o.role,
                department_id=o.department_id,
                department_name=o.department.name if o.department else None,
                created_at=o.created_at,
            )
        )
    return result


@router.post(
    "/officers",
    response_model=AdminOfficerItem,
    status_code=status.HTTP_201_CREATED,
    summary="Admin create a new department officer account",
)
def create_admin_officer(
    req: AdminOfficerCreateRequest,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Create a new officer account and assign them to an authorized department."""
    existing = db.query(User).filter(User.email == req.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{req.email}' already exists.",
        )

    if req.department_id:
        dept = db.query(Department).filter(Department.id == req.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {req.department_id} not found.",
            )

    hashed_pwd = hash_password(req.password)
    new_officer = User(
        name=req.name.strip(),
        email=req.email.lower().strip(),
        password_hash=hashed_pwd,
        role=UserRole.OFFICER,
        department_id=req.department_id,
        preferred_language="en",
    )
    db.add(new_officer)
    db.commit()
    db.refresh(new_officer)

    record_audit_log(
        action="ADMIN_CREATE_OFFICER",
        entity_type="USER",
        entity_id=str(new_officer.id),
        user_id=current_user.id,
        db=db,
        metadata={
            "officer_email": new_officer.email,
            "department_id": new_officer.department_id,
        },
    )

    return AdminOfficerItem(
        id=new_officer.id,
        name=new_officer.name,
        email=new_officer.email,
        role=new_officer.role,
        department_id=new_officer.department_id,
        department_name=new_officer.department.name if new_officer.department else None,
        created_at=new_officer.created_at,
    )


@router.patch(
    "/officers/{user_id}/department",
    response_model=AdminOfficerItem,
    summary="Admin update officer department assignment",
)
def update_officer_department(
    user_id: int,
    req: AdminOfficerDepartmentUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Reassign an existing officer account to a different department."""
    target_user = db.query(User).filter(User.id == user_id, User.role == UserRole.OFFICER).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Officer account with ID {user_id} not found.",
        )

    if req.department_id is not None:
        dept = db.query(Department).filter(Department.id == req.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {req.department_id} not found.",
            )

    old_dept = target_user.department_id
    target_user.department_id = req.department_id
    db.commit()
    db.refresh(target_user)

    record_audit_log(
        action="ADMIN_UPDATE_OFFICER_DEPT",
        entity_type="USER",
        entity_id=str(target_user.id),
        user_id=current_user.id,
        db=db,
        metadata={
            "old_department_id": old_dept,
            "new_department_id": req.department_id,
        },
    )

    return AdminOfficerItem(
        id=target_user.id,
        name=target_user.name,
        email=target_user.email,
        role=target_user.role,
        department_id=target_user.department_id,
        department_name=target_user.department.name if target_user.department else None,
        created_at=target_user.created_at,
    )


@router.get(
    "/complaints/{complaint_id}/history",
    response_model=List[AdminStatusHistoryItem],
    summary="Admin view full status history of any complaint",
)
def get_complaint_history(
    complaint_id: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve complete audit status history for a complaint across all actors."""
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{complaint_id}' not found.",
        )

    history = (
        db.query(ComplaintStatusHistory)
        .filter(ComplaintStatusHistory.complaint_id == complaint.id)
        .order_by(ComplaintStatusHistory.created_at)
        .all()
    )

    result = []
    for h in history:
        result.append(
            AdminStatusHistoryItem(
                id=h.id,
                old_status=h.old_status,
                new_status=h.new_status,
                changed_by_id=h.changed_by,
                changed_by_name=h.actor.name if h.actor else ("System" if not h.changed_by else None),
                remarks=h.remarks,
                created_at=h.created_at,
            )
        )
    return result


@router.get(
    "/audit-logs",
    response_model=AdminAuditLogListResponse,
    summary="Admin view system audit logs",
)
def get_admin_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action name"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Retrieve system audit logs for administrative oversight and compliance tracking."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)

    total = q.count()
    logs = q.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit).all()

    items = []
    for l in logs:
        items.append(
            AdminAuditLogItem(
                id=l.id,
                action=l.action,
                entity_type=l.entity_type,
                entity_id=l.entity_id,
                user_id=l.user_id,
                user_email=l.user.email if l.user else None,
                timestamp=l.timestamp,
                metadata=l.metadata_,
            )
        )

    return AdminAuditLogListResponse(total=total, items=items)
