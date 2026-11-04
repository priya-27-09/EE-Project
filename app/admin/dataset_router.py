import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.dataset import DatasetVersion, DatasetStatus
from app.auth.dependencies import get_current_user, require_roles
from app.services.dataset_service import DatasetService

router = APIRouter(
    prefix="/api/v1/admin/datasets",
    tags=["Admin - Dataset Management"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Upload new YOLO dataset archive (ADMIN only)")
async def upload_dataset(
    file: UploadFile = File(..., description="Zipped YOLO dataset archive (.zip)"),
    dataset_name: str = Form(..., min_length=2, max_length=200, description="Descriptive dataset name"),
    description: Optional[str] = Form(None, description="Optional description of dataset content/source"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a YOLO dataset ZIP archive.
    Extracts safely, prevents path traversal, rejects executables, calculates SHA-256,
    stores files under dataset/versions/<version>/, records metadata in PostgreSQL,
    and runs structural/label validation.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        dataset_record, validation_data = DatasetService.create_dataset_from_upload(
            db=db,
            archive_bytes=content,
            archive_filename=file.filename,
            dataset_name=dataset_name.strip(),
            description=description.strip() if description else None,
            user_id=current_user.id,
            auto_validate=True,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process dataset archive: {str(exc)}",
        )

    return {
        "status": "success",
        "message": f"Dataset {dataset_record.dataset_version} uploaded and validated successfully.",
        "dataset": {
            "id": dataset_record.id,
            "dataset_version": dataset_record.dataset_version,
            "dataset_name": dataset_record.dataset_name,
            "description": dataset_record.description,
            "status": dataset_record.status,
            "dataset_sha256": dataset_record.dataset_sha256,
            "train_image_count": dataset_record.train_image_count,
            "val_image_count": dataset_record.val_image_count,
            "test_image_count": dataset_record.test_image_count,
            "total_image_count": dataset_record.total_image_count,
            "total_object_count": dataset_record.total_object_count,
            "class_count": dataset_record.class_count,
            "uploaded_by": dataset_record.uploaded_by,
            "uploaded_at": dataset_record.uploaded_at.isoformat() if dataset_record.uploaded_at else None,
        },
        "validation": validation_data,
    }


@router.get("", summary="List all dataset versions (ADMIN only)")
def list_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Optional filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all dataset versions in chronological descending order."""
    query = db.query(DatasetVersion)
    if status_filter:
        query = query.filter(DatasetVersion.status == status_filter.upper())

    total = query.count()
    records = query.order_by(desc(DatasetVersion.id)).offset(skip).limit(limit).all()

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "dataset_version": r.dataset_version,
            "dataset_name": r.dataset_name,
            "description": r.description,
            "status": r.status,
            "dataset_sha256": r.dataset_sha256,
            "train_image_count": r.train_image_count,
            "val_image_count": r.val_image_count,
            "test_image_count": r.test_image_count,
            "total_image_count": r.total_image_count,
            "total_object_count": r.total_object_count,
            "class_count": r.class_count,
            "uploaded_by": r.uploaded_by,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "status": "success",
        "total": total,
        "skip": skip,
        "limit": limit,
        "datasets": items,
    }


@router.get("/{dataset_version}", summary="Get dataset version details (ADMIN only)")
def get_dataset(
    dataset_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve metadata and summary statistics for a specific dataset version."""
    record = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version '{dataset_version}' not found.",
        )

    return {
        "status": "success",
        "dataset": {
            "id": record.id,
            "dataset_version": record.dataset_version,
            "dataset_name": record.dataset_name,
            "description": record.description,
            "status": record.status,
            "storage_path": record.storage_path,
            "dataset_sha256": record.dataset_sha256,
            "train_image_count": record.train_image_count,
            "val_image_count": record.val_image_count,
            "test_image_count": record.test_image_count,
            "total_image_count": record.total_image_count,
            "total_object_count": record.total_object_count,
            "class_count": record.class_count,
            "uploaded_by": record.uploaded_by,
            "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
            "validation_summary": record.validation_summary,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }
    }


@router.post("/{dataset_version}/validate", summary="Trigger dataset validation (ADMIN only)")
def validate_dataset_endpoint(
    dataset_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger YOLO dataset validation.
    If validation passes, status transitions to READY_FOR_TRAINING.
    If critical errors exist, status transitions to INVALID.
    """
    record = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version '{dataset_version}' not found.",
        )

    try:
        report = DatasetService.validate_dataset(db, dataset_version)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed due to internal error: {str(exc)}",
        )

    # Refresh record
    db.refresh(record)

    return {
        "status": "success",
        "dataset_version": dataset_version,
        "dataset_status": record.status,
        "validation": report,
    }


@router.get("/{dataset_version}/report", summary="Get validation report (ADMIN only)")
def get_validation_report(
    dataset_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch the full validation_report.json for a dataset version."""
    record = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset version '{dataset_version}' not found.",
        )

    report = DatasetService.get_validation_report(db, dataset_version)
    return {
        "status": "success",
        "dataset_version": dataset_version,
        "report": report,
    }


# -------------------------------------------------------------
# Civic Dataset Sources & Acquisition Router
# -------------------------------------------------------------

sources_router = APIRouter(
    prefix="/api/v1/admin/dataset-sources",
    tags=["Admin - Dataset Sources"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@sources_router.get("", summary="Get civic dataset sources registry and preparation report (ADMIN only)")
@router.get("/sources/overview", summary="Get civic dataset sources overview alias (ADMIN only)")
def get_dataset_sources_overview(
    current_user: User = Depends(get_current_user),
):
    """
    Returns public dataset sources registry, license audit status, class mappings,
    duplicate analysis, class distribution, and Step 4A quality gate validation results.
    """
    base_dir = Path(__file__).resolve().parent.parent.parent
    sources_dir = base_dir / "data" / "sources"
    reports_dir = base_dir / "data" / "reports"

    registry = {}
    reg_file = sources_dir / "dataset_registry.json"
    if reg_file.exists():
        with open(reg_file, "r", encoding="utf-8") as f:
            registry = json.load(f)

    class_mappings = {}
    cm_file = sources_dir / "class_mapping.json"
    if cm_file.exists():
        with open(cm_file, "r", encoding="utf-8") as f:
            class_mappings = json.load(f)

    duplicates = {}
    dup_file = reports_dir / "duplicates.json"
    if dup_file.exists():
        with open(dup_file, "r", encoding="utf-8") as f:
            duplicates = json.load(f)

    distribution = {}
    dist_file = reports_dir / "class_distribution.json"
    if dist_file.exists():
        with open(dist_file, "r", encoding="utf-8") as f:
            distribution = json.load(f)

    quality = {}
    qual_file = reports_dir / "data_quality_report.json"
    if qual_file.exists():
        with open(qual_file, "r", encoding="utf-8") as f:
            quality = json.load(f)

    license_audit_md = ""
    lic_file = sources_dir / "license_audit.md"
    if lic_file.exists():
        with open(lic_file, "r", encoding="utf-8") as f:
            license_audit_md = f.read()

    custom_data_md = ""
    cust_file = reports_dir / "custom_data_required.md"
    if cust_file.exists():
        with open(cust_file, "r", encoding="utf-8") as f:
            custom_data_md = f.read()

    return {
        "status": "success",
        "registry": registry,
        "class_mappings": class_mappings,
        "duplicates": duplicates,
        "distribution": distribution,
        "quality_gate": quality,
        "license_audit_md": license_audit_md,
        "custom_data_required_md": custom_data_md,
    }

