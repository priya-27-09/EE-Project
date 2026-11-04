import threading
from pathlib import Path
from typing import Optional, Union, Tuple, Any
from sqlalchemy.orm import Session
from PIL import Image

from app.core.config import settings
from app.models.user import User
from app.models.model_version import ModelVersion
from app.services.routing_service import route_issue_to_department
from app.services.severity_service import calculate_issue_severity
from app.services.audit_service import record_audit_log
from app.ai.detection_service import DetectionService
from app.ai.ai_exceptions import (
    AINoDetectionException,
    InvalidImageException,
    CorruptedImageException,
    InferenceFailedException,
)
from app.ai.schemas import (
    AIDemoInferenceSuccessResponse,
    AIDemoInferenceErrorResponse,
    SeverityInfo,
    DepartmentInfo,
)


class DemoInferenceService:
    """
    Isolated service for executing local demo inference using the experimental
    YOLO11n baseline checkpoint without touching production model activation.

    STRICT CONSTRAINTS:
    - Never modifies ModelVersion.is_active in PostgreSQL.
    - Never replaces production ModelLoader or live inference endpoints.
    - Explicitly disabled unless ENABLE_EXPERIMENTAL_DEMO_INFERENCE=True.
    - Class 7 (Drainage Problem) is marked as completely unvalidated if detected.
    """

    _cached_demo_model: Optional[Any] = None
    _cached_weights_path: Optional[str] = None
    _lock = threading.Lock()

    @classmethod
    def get_demo_model(cls) -> Tuple[str, Any]:
        """
        Thread-safe loader for the experimental baseline YOLO checkpoint.
        Loads directly from disk without altering any database records.
        """
        weights_path = Path(settings.DEMO_MODEL_WEIGHTS_PATH).resolve()
        if not weights_path.exists() or not weights_path.is_file():
            raise FileNotFoundError(
                f"Experimental baseline checkpoint not found at: {weights_path}"
            )

        with cls._lock:
            if cls._cached_demo_model is not None and cls._cached_weights_path == str(weights_path):
                return str(weights_path), cls._cached_demo_model

            from ultralytics import YOLO

            loaded = YOLO(str(weights_path))
            if loaded is None:
                raise RuntimeError("Ultralytics YOLO initialization returned None for demo checkpoint.")

            cls._cached_demo_model = loaded
            cls._cached_weights_path = str(weights_path)
            return str(weights_path), cls._cached_demo_model

    @classmethod
    def clear_cache(cls) -> None:
        """Evict demo model from memory."""
        with cls._lock:
            cls._cached_demo_model = None
            cls._cached_weights_path = None

    @classmethod
    def execute_demo_inference(
        cls,
        image_bytes: bytes,
        filename: Optional[str],
        content_type: Optional[str],
        current_user: User,
        db: Session,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        img_size: int = 320,
        enable_demo: bool = False,
    ) -> Union[AIDemoInferenceSuccessResponse, AIDemoInferenceErrorResponse]:
        """
        Execute isolated demo inference on the provided image evidence.
        """
        # 1. Gate check: Demo mode must be explicitly enabled via setting or parameter
        if not (settings.ENABLE_EXPERIMENTAL_DEMO_INFERENCE or enable_demo):
            return AIDemoInferenceErrorResponse(
                success=False,
                is_demo=True,
                error_code="DEMO_MODE_DISABLED",
                message=(
                    "Experimental baseline demo inference is currently disabled. "
                    "To enable local demo inference, set ENABLE_EXPERIMENTAL_DEMO_INFERENCE=true in your environment, "
                    "or provide enable_demo=true in the request parameters."
                ),
                model_version="MODEL-2026-000001 (DISABLED)",
            )

        # 2. Checkpoint availability check
        try:
            weights_path_str, model_instance = cls.get_demo_model()
        except FileNotFoundError as fnf_err:
            return AIDemoInferenceErrorResponse(
                success=False,
                is_demo=True,
                error_code="CHECKPOINT_NOT_FOUND",
                message=str(fnf_err),
                model_version="MODEL-2026-000001",
            )
        except Exception as exc:
            return AIDemoInferenceErrorResponse(
                success=False,
                is_demo=True,
                error_code="MODEL_LOAD_FAILED",
                message=f"Failed to load experimental baseline model: {str(exc)}",
                model_version="MODEL-2026-000001",
            )

        # 3. Validate image
        pil_image = DetectionService.validate_and_open_image(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )

        # 4. Run real YOLO inference using the experimental model
        detections = DetectionService.run_inference(
            model=model_instance,
            image=pil_image,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            img_size=img_size,
        )

        model_version_label = "MODEL-2026-000001 (EXPERIMENTAL BASELINE)"

        # 5. Resolve primary issue
        try:
            primary_issue = DetectionService.resolve_primary_issue(
                detections=detections,
                model_version=model_version_label,
            )
        except AINoDetectionException as exc:
            # Audit the attempt
            record_audit_log(
                action="EXPERIMENTAL_DEMO_INFERENCE_EXECUTED",
                entity_type="ModelVersion",
                entity_id="MODEL-2026-000001",
                user_id=current_user.id if current_user else None,
                db=db,
                metadata={
                    "is_demo": True,
                    "model_version": model_version_label,
                    "result_status": "NO_DETECTION",
                    "filename": filename,
                },
            )
            db.commit()
            return AIDemoInferenceErrorResponse(
                success=False,
                is_demo=True,
                error_code="AI_NO_DETECTION",
                message=str(exc),
                model_version=model_version_label,
                detections=detections,
            )

        # 6. Specific safety check for Class 7 (Drainage Problem)
        is_unvalidated = False
        class_warning: Optional[str] = None
        if primary_issue.class_id == 7:
            is_unvalidated = True
            class_warning = (
                "Class 7 (Drainage Problem) has zero verified annotations across all splits in dataset DS-2026-000018. "
                "This prediction is completely unvalidated and must not be used without manual citizen confirmation."
            )

        # 7. Compute deterministic severity & route to department
        raw_sev = calculate_issue_severity(
            issue_class=primary_issue.class_id,
            confidence=primary_issue.confidence,
            detections_count=len(detections),
        )
        severity_info = SeverityInfo(
            level=raw_sev["level"],
            score=raw_sev.get("score"),
            reason=raw_sev.get("reason"),
        )

        routed_dept = route_issue_to_department(
            issue_class=primary_issue.class_id,
            db=db,
        )
        department_info = DepartmentInfo(
            id=routed_dept.id,
            name=routed_dept.name,
        )

        # 8. Record audit log
        record_audit_log(
            action="EXPERIMENTAL_DEMO_INFERENCE_EXECUTED",
            entity_type="ModelVersion",
            entity_id="MODEL-2026-000001",
            user_id=current_user.id if current_user else None,
            db=db,
            metadata={
                "is_demo": True,
                "model_version": model_version_label,
                "issue_class": primary_issue.class_name,
                "confidence": primary_issue.confidence,
                "is_unvalidated_class": is_unvalidated,
                "raw_detections_count": len(detections),
            },
        )
        db.commit()

        return AIDemoInferenceSuccessResponse(
            success=True,
            is_demo=True,
            is_experimental=True,
            is_production_ready=False,
            model_version=model_version_label,
            weights_path=weights_path_str,
            issue=primary_issue,
            severity=severity_info,
            department=department_info,
            detections=detections,
            is_unvalidated_class=is_unvalidated,
            warning=class_warning,
            note="Experimental baseline demo inference only. Production status remains NOT READY.",
        )
