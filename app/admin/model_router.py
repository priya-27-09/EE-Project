from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.model_version import ModelVersion, TrainingStatus
from app.auth.dependencies import get_current_user, require_roles
from app.services.model_service import ModelService, detect_hardware, SUPPORTED_BASE_MODELS

router = APIRouter(
    prefix="/api/v1/admin/models",
    tags=["Admin - YOLO Model Management"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


class TrainModelRequest(BaseModel):
    dataset_version: str = Field(..., description="Version of validated dataset (must be READY_FOR_TRAINING)")
    model_name: Optional[str] = Field(None, description="Descriptive model name")
    base_model: Optional[str] = Field("yolo11n.pt", description="Pretrained YOLO base checkpoint")
    epochs: Optional[int] = Field(50, ge=1, le=500, description="Number of training epochs")
    image_size: Optional[int] = Field(640, ge=128, le=1280, description="Image resolution (multiple of 32)")
    batch_size: Optional[int] = Field(8, ge=1, le=128, description="Batch size")
    device: Optional[str] = Field("cpu", description="Hardware device: 'cpu' or '0'")


def serialize_model_version(m: ModelVersion) -> Dict[str, Any]:
    return {
        "id": m.id,
        "model_version": m.model_version,
        "model_name": m.model_name,
        "dataset_version": m.dataset_version,
        "base_model": m.base_model,
        "ultralytics_version": m.ultralytics_version,
        "task": m.task,
        "class_count": m.class_count,
        "class_names": m.class_names,
        "weights_path": m.weights_path,
        "best_weights_path": m.best_weights_path,
        "last_weights_path": m.last_weights_path,
        "training_status": m.training_status,
        "is_active": m.is_active,
        "epochs": m.epochs,
        "image_size": m.image_size,
        "batch_size": m.batch_size,
        "device": m.device,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        "training_duration_seconds": m.training_duration_seconds,
        "precision": m.precision,
        "recall": m.recall,
        "map50": m.map50,
        "map50_95": m.map50_95,
        "training_metrics": m.training_metrics,
        "validation_metrics": m.validation_metrics,
        "error_message": m.error_message,
        "created_by": m.created_by,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


@router.get("/hardware", summary="Detect local compute hardware (ADMIN only)")
def get_hardware_info(current_user: User = Depends(get_current_user)):
    """Return CPU/GPU capabilities and recommended device for training."""
    return {
        "status": "success",
        "hardware": detect_hardware(),
        "supported_base_models": SUPPORTED_BASE_MODELS,
    }


@router.post("/train", status_code=status.HTTP_202_ACCEPTED, summary="Initiate YOLO model training (ADMIN only)")
def start_model_training(
    payload: TrainModelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Queue and start an Ultralytics YOLO training job in a non-blocking background thread.
    Validates that target dataset has status READY_FOR_TRAINING.
    Returns immediately with model_version and initial QUEUED status.
    """
    model_name = payload.model_name or f"Civic YOLO ({payload.base_model}) on {payload.dataset_version}"

    try:
        model_record = ModelService.create_training_job(
            db=db,
            model_name=model_name,
            dataset_version=payload.dataset_version,
            base_model=payload.base_model,
            epochs=payload.epochs,
            image_size=payload.image_size,
            batch_size=payload.batch_size,
            device=payload.device,
            user_id=current_user.id,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule training job: {str(exc)}",
        )

    return {
        "status": "accepted",
        "message": f"Training job scheduled successfully for model version {model_record.model_version}.",
        "model_version": model_record.model_version,
        "training_status": model_record.training_status,
        "details": serialize_model_version(model_record),
    }


@router.get("", summary="List all model versions (ADMIN only)")
def list_models(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, description="Filter by training status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all model versions in chronological descending order."""
    query = db.query(ModelVersion)
    if status_filter:
        query = query.filter(ModelVersion.training_status == status_filter.upper())

    total = query.count()
    records = query.order_by(desc(ModelVersion.id)).offset(skip).limit(limit).all()

    return {
        "status": "success",
        "total": total,
        "skip": skip,
        "limit": limit,
        "models": [serialize_model_version(m) for m in records],
    }


@router.get("/active", summary="Get currently active detection model (ADMIN only)")
def get_active_model(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return currently active model metadata or clear state if none exists."""
    active = ModelService.get_active_model(db)
    if not active:
        return {
            "status": "AI_MODEL_NOT_AVAILABLE",
            "message": "AI model not trained yet. No active model currently available.",
            "active_model": None,
        }

    return {
        "status": "success",
        "active_model": serialize_model_version(active),
    }


@router.get("/{model_version}", summary="Get model version details (ADMIN only)")
def get_model(
    model_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve metadata and real metrics for a specific model version."""
    record = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model version '{model_version}' not found.",
        )

    return {
        "status": "success",
        "model": serialize_model_version(record),
    }


@router.get("/{model_version}/status", summary="Poll model training status (ADMIN only)")
def get_model_status(
    model_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight polling endpoint to inspect training status and elapsed time."""
    record = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model version '{model_version}' not found.",
        )

    return {
        "model_version": record.model_version,
        "status": record.training_status,
        "is_active": record.is_active,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "training_duration_seconds": record.training_duration_seconds,
        "error_message": record.error_message,
    }


@router.get("/{model_version}/metrics", summary="Get model validation metrics (ADMIN only)")
def get_model_metrics(
    model_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve real precision, recall, and mAP metrics obtained from Ultralytics."""
    record = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model version '{model_version}' not found.",
        )

    return {
        "status": "success",
        "model_version": record.model_version,
        "training_status": record.training_status,
        "precision": record.precision,
        "recall": record.recall,
        "map50": record.map50,
        "map50_95": record.map50_95,
        "training_metrics": record.training_metrics,
        "validation_metrics": record.validation_metrics,
    }


@router.post("/{model_version}/activate", summary="Activate model for civic issue detection (ADMIN only)")
def activate_model_endpoint(
    model_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Activate a COMPLETED model.
    Transitions previously ACTIVE model to ARCHIVED.
    Verifies weights file existence and integrity before activation.
    """
    try:
        activated = ModelService.activate_model(db, model_version)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model activation failed: {str(exc)}",
        )

    return {
        "status": "success",
        "message": f"Model {model_version} is now the ACTIVE detection model.",
        "active_model": serialize_model_version(activated),
    }


@router.post("/{model_version}/deactivate", summary="Deactivate model from production civic detection (ADMIN only)")
def deactivate_model_endpoint(
    model_version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Safely deactivate an active model without promoting a replacement.
    Transitions active model to COMPLETED and sets is_active=False.
    Records audit log in PostgreSQL.
    """
    try:
        deactivated = ModelService.deactivate_model(db, model_version, user_id=current_user.id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model deactivation failed: {str(exc)}",
        )

    return {
        "status": "success",
        "message": f"Model {model_version} has been safely deactivated from production.",
        "model": serialize_model_version(deactivated),
    }


@router.post("/{model_version}/inference", summary="Run sample inference on a test image (ADMIN only)")
async def run_sample_inference(
    model_version: str,
    file: UploadFile = File(..., description="Real test image file"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run real inference on an uploaded image using the specified model checkpoint."""
    temp_path = None
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No real inference image supplied.")

        suffix = Path(file.filename).suffix if file.filename else ".jpg"
        temp_dir = settings.BASE_DIR / "uploads" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"test_{int(time.time()*1000)}{suffix}"
        temp_path.write_bytes(content)

        results = ModelService.run_inference(db, model_version, temp_path)
        return {
            "status": "success",
            "inference": results,
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(exc)}",
        )
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
