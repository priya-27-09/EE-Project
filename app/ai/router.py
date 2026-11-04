from typing import Optional, Union
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
from app.ai.ai_exceptions import (
    InvalidImageException,
    CorruptedImageException,
    InferenceFailedException,
)
from app.ai.inference_service import AIInferenceService
from app.ai.demo_inference_service import DemoInferenceService
from app.ai.schemas import (
    AIInferenceSuccessResponse,
    AIInferenceErrorResponse,
    AIDemoInferenceSuccessResponse,
    AIDemoInferenceErrorResponse,
)

router = APIRouter(prefix="/api/v1/ai", tags=["AI Inference"])


@router.post(
    "/inference",
    response_model=Union[AIInferenceSuccessResponse, AIInferenceErrorResponse],
    summary="Run real YOLO AI inference on an uploaded civic image",
)
async def run_ai_inference(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(
        default=0.25,
        ge=0.01,
        le=1.0,
        description="Minimum confidence threshold for object detection",
    ),
    iou_threshold: float = Query(
        default=0.45,
        ge=0.01,
        le=1.0,
        description="IoU threshold for Non-Maximum Suppression (NMS)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run real YOLO inference using the currently ACTIVE model version in PostgreSQL.
    - Requires authenticated user (JWT Bearer token).
    - Accepts standard image formats (JPEG, PNG, WebP, BMP up to 10MB).
    - If no model is active, returns structured error with code `AI_MODEL_NOT_AVAILABLE`.
    - If no civic issues are detected, returns structured response with code `AI_NO_DETECTION`.
    - If valid civic issue is detected, deterministically assesses severity and routes to department.
    - Does NOT automatically lodge a complaint; allows citizen to review before final confirmation.
    """
    # 1. Read uploaded image binary into memory
    try:
        image_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded image stream: {str(exc)}",
        )

    # 2. Execute inference pipeline
    try:
        result = await AIInferenceService.execute_inference(
            image_bytes=image_bytes,
            filename=file.filename,
            content_type=file.content_type,
            current_user=current_user,
            db=db,
            conf_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
        )
        return result
    except (InvalidImageException, CorruptedImageException) as img_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=img_err.message,
        )
    except InferenceFailedException as inf_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=inf_err.message,
        )


@router.post(
    "/demo-inference",
    response_model=Union[AIDemoInferenceSuccessResponse, AIDemoInferenceErrorResponse],
    summary="Run real YOLO inference in isolated demo mode using experimental baseline checkpoint",
)
async def run_ai_demo_inference(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(
        default=0.25,
        ge=0.01,
        le=1.0,
        description="Minimum confidence threshold for object detection",
    ),
    iou_threshold: float = Query(
        default=0.45,
        ge=0.01,
        le=1.0,
        description="IoU threshold for Non-Maximum Suppression (NMS)",
    ),
    enable_demo: bool = Query(
        default=False,
        description="Explicitly enable demo inference for local testing",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run real YOLO inference using the experimental baseline checkpoint in isolated DEMO mode.
    - Completely separate from production inference pipeline.
    - Never changes active model configuration or database records.
    - Explicitly disabled unless ENABLE_EXPERIMENTAL_DEMO_INFERENCE=true or enable_demo=true.
    - All predictions are flagged with is_demo=True and is_experimental=True.
    - Class 7 (Drainage Problem) is flagged as unvalidated.
    """
    try:
        image_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded image stream: {str(exc)}",
        )

    try:
        result = DemoInferenceService.execute_demo_inference(
            image_bytes=image_bytes,
            filename=file.filename,
            content_type=file.content_type,
            current_user=current_user,
            db=db,
            conf_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            enable_demo=enable_demo,
        )
        return result
    except (InvalidImageException, CorruptedImageException) as img_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=img_err.message,
        )
    except InferenceFailedException as inf_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=inf_err.message,
        )

