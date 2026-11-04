from typing import Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from PIL import Image

from app.models.user import User
from app.services.routing_service import route_issue_to_department
from app.services.severity_service import calculate_issue_severity
from app.services.audit_service import record_audit_log
from app.ai.model_loader import ModelLoader
from app.ai.detection_service import DetectionService
from app.ai.ai_exceptions import (
    AIModelNotAvailableException,
    AINoDetectionException,
    InvalidImageException,
    CorruptedImageException,
    InferenceFailedException,
)
from app.ai.schemas import (
    AIInferenceSuccessResponse,
    AIInferenceErrorResponse,
    IssueDetection,
    SeverityInfo,
    DepartmentInfo,
)


class AIInferenceService:
    @classmethod
    async def execute_inference(
        cls,
        image_bytes: bytes,
        filename: Optional[str],
        content_type: Optional[str],
        current_user: User,
        db: Session,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        img_size: int = 640,
    ) -> Union[AIInferenceSuccessResponse, AIInferenceErrorResponse]:
        """
        Execute full end-to-end AI detection workflow asynchronously.
        Returns AIInferenceSuccessResponse when an active model detects a civic issue,
        or structured AIInferenceErrorResponse if the model is unavailable or no issue is detected.
        Raises InvalidImageException or CorruptedImageException on invalid image input.
        """
        import asyncio, time, logging
        # 1. Validate and decode image before inference
        pil_image = DetectionService.validate_and_open_image(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )

        # 2. Check active model availability
        try:
            model_record, model_instance = ModelLoader.get_active_model(db)
        except AIModelNotAvailableException as exc:
            record_audit_log(
                action="AI_INFERENCE_REQUESTED",
                entity_type="AIModel",
                entity_id="NONE",
                user_id=current_user.id if current_user else None,
                db=db,
                metadata={
                    "status": "AI_MODEL_NOT_AVAILABLE",
                    "reason": str(exc),
                    "filename": filename,
                },
            )
            db.commit()
            return AIInferenceErrorResponse(
                success=False,
                error_code="AI_MODEL_NOT_AVAILABLE",
                message=str(exc) or "Image uploaded successfully. Please confirm the issue category to continue.",
            )
        except Exception as exc:
            record_audit_log(
                action="AI_INFERENCE_REQUESTED",
                entity_type="AIModel",
                entity_id="NONE",
                user_id=current_user.id if current_user else None,
                db=db,
                metadata={
                    "status": "AI_MODEL_NOT_AVAILABLE",
                    "reason": str(exc),
                    "filename": filename,
                },
            )
            db.commit()
            return AIInferenceErrorResponse(
                success=False,
                error_code="AI_MODEL_NOT_AVAILABLE",
                message="Image uploaded successfully. Please confirm the issue category to continue. (No trained AI model is currently active.)",
            )

        # 3. Run real YOLO inference in a thread with timeout
        start_time = time.time()
        try:
            detections = await asyncio.wait_for(
                asyncio.to_thread(
                    DetectionService.run_inference,
                    model=model_instance,
                    image=pil_image,
                    conf_threshold=conf_threshold,
                    iou_threshold=iou_threshold,
                    img_size=model_record.image_size or img_size,
                ),
                timeout=15,
            )
        except asyncio.TimeoutError:
            logging.error(f"AI inference timed out after 15 seconds for model {model_record.model_version}")
            raise InferenceFailedException("AI inference timed out. Please try again later.")
        except Exception as exc:
            logging.exception("Unexpected error during AI inference")
            raise InferenceFailedException(str(exc))
        finally:
            elapsed = time.time() - start_time
            logging.info(f"AI inference completed in {elapsed:.2f}s for model {model_record.model_version}")

        # 4. Resolve primary civic issue from detections
        try:
            primary_issue = DetectionService.resolve_primary_issue(
                detections=detections,
                model_version=model_record.model_version,
            )
        except AINoDetectionException as exc:
            record_audit_log(
                action="AI_INFERENCE_EXECUTED",
                entity_type="ModelVersion",
                entity_id=model_record.model_version,
                user_id=current_user.id if current_user else None,
                db=db,
                metadata={
                    "model_version": model_record.model_version,
                    "result_status": "NO_DETECTION",
                    "issue_class": None,
                    "confidence": None,
                    "raw_detections_count": len(detections),
                },
            )
            db.commit()
            return AIInferenceErrorResponse(
                success=False,
                error_code="AI_NO_DETECTION",
                message=str(exc),
                model_version=model_record.model_version,
                detections=detections,
            )

        # 5. Deterministic Severity Assessment
        sev = calculate_issue_severity(
            issue_type=primary_issue.issue_type,
            confidence=primary_issue.confidence,
        )

        # 6. Automatic Department Routing
        department = route_issue_to_department(primary_issue.issue_type, db)

        # 7. Immutable Audit Logging
        record_audit_log(
            action="AI_INFERENCE_EXECUTED",
            entity_type="ModelVersion",
            entity_id=model_record.model_version,
            user_id=current_user.id if current_user else None,
            db=db,
            metadata={
                "model_version": model_record.model_version,
                "result_status": "SUCCESS",
                "issue_class": primary_issue.class_name,
                "confidence": primary_issue.confidence,
                "department_id": department.id,
                "department_name": department.name,
                "severity_level": sev["level"],
                "total_detections": len(detections),
            },
        )
        db.commit()

        # 8. Return structured result
        return AIInferenceSuccessResponse(
            success=True,
            model_version=model_record.model_version,
            issue=primary_issue,
            severity=SeverityInfo(
                level=sev["level"],
                score=sev["score"],
                reason=sev["reason"],
            ),
            department=DepartmentInfo(
                id=department.id,
                name=department.name,
            ),
            detections=detections,
        )

