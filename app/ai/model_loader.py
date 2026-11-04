import threading
from pathlib import Path
from typing import Optional, Tuple, Any
from sqlalchemy.orm import Session

from app.models.model_version import ModelVersion, TrainingStatus
from app.ai.ai_exceptions import AIModelNotAvailableException, InferenceFailedException


class ModelLoader:
    """
    Thread-safe model loader that discovers and caches the active YOLO model from PostgreSQL.
    Ensures only verified, non-archived models are loaded and automatically invalidates cache
    when the active model version changes.
    """

    _cached_model: Optional[Any] = None
    _cached_model_version: Optional[str] = None
    _cached_weights_path: Optional[str] = None
    _lock = threading.Lock()

    @classmethod
    def get_active_model(cls, db: Session) -> Tuple[ModelVersion, Any]:
        """
        Retrieve the currently ACTIVE ModelVersion from PostgreSQL and returns
        the database record alongside the cached Ultralytics YOLO model instance.

        Raises:
            AIModelNotAvailableException: If no model is active, weights file is missing,
                                         or model is experimental/not approved for production.
            InferenceFailedException: If model weights cannot be loaded by Ultralytics.
        """
        # 1. Query PostgreSQL for single active model
        active_record = (
            db.query(ModelVersion)
            .filter(ModelVersion.is_active.is_(True))
            .first()
        )

        if not active_record:
            cls.clear_cache()
            raise AIModelNotAvailableException(
                "Image uploaded successfully. Please confirm the issue category to continue. (No trained AI model is currently active.)"
            )

        # 2. Strict constraint: MODEL-2026-000001 is experimental baseline and must remain inactive
        if active_record.model_version == "MODEL-2026-000001":
            cls.clear_cache()
            raise AIModelNotAvailableException(
                "Image uploaded successfully. Please confirm the issue category to continue. (No trained AI model is currently active.)"
            )

        # 3. Strict status check - never load inactive or archived model
        if active_record.training_status != TrainingStatus.ACTIVE:
            cls.clear_cache()
            raise AIModelNotAvailableException(
                f"Model '{active_record.model_version}' is marked active but its training status is '{active_record.training_status}'."
            )

        # 4. Locate best.pt on disk
        weights_path_str = active_record.best_weights_path or active_record.weights_path
        if not weights_path_str:
            cls.clear_cache()
            raise AIModelNotAvailableException(
                f"Active model '{active_record.model_version}' has no weights path recorded."
            )

        weights_path = Path(weights_path_str).resolve()
        if not weights_path.exists() or not weights_path.is_file():
            cls.clear_cache()
            raise AIModelNotAvailableException(
                f"Active model weights file not found on disk at: {weights_path}"
            )

        # 5. Thread-safe retrieval / reload
        with cls._lock:
            if (
                cls._cached_model is not None
                and cls._cached_model_version == active_record.model_version
                and cls._cached_weights_path == str(weights_path)
            ):
                return active_record, cls._cached_model

            # Active model has changed or is not yet loaded: load with Ultralytics
            try:
                from ultralytics import YOLO
            except ImportError:
                cls.clear_cache()
                raise AIModelNotAvailableException(
                    "Image uploaded successfully. Please confirm the issue category to continue."
                )

            try:
                loaded = YOLO(str(weights_path))
                if loaded is None:
                    raise RuntimeError("Ultralytics YOLO initialization returned None.")

                cls._cached_model = loaded
                cls._cached_model_version = active_record.model_version
                cls._cached_weights_path = str(weights_path)
                return active_record, cls._cached_model
            except Exception as exc:
                cls.clear_cache()
                raise AIModelNotAvailableException(
                    f"Active model '{active_record.model_version}' is unavailable: {str(exc)}"
                )

    @classmethod
    def get_cached_version(cls) -> Optional[str]:
        """Returns the version string of the currently cached model, if any."""
        with cls._lock:
            return cls._cached_model_version

    @classmethod
    def clear_cache(cls) -> None:
        """Evict the currently cached model from memory."""
        with cls._lock:
            cls._cached_model = None
            cls._cached_model_version = None
            cls._cached_weights_path = None
