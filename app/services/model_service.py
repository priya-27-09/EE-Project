import os
import io
import json
import time
import shutil
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

import torch
import yaml
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.dataset import DatasetVersion, DatasetStatus
from app.models.model_version import ModelVersion, TrainingStatus
from app.services.audit_service import record_audit_log

# Base models storage directory
MODELS_ROOT = settings.BASE_DIR / "models"
MODELS_ROOT.mkdir(parents=True, exist_ok=True)

# Cache Ultralytics version
try:
    import ultralytics
    from ultralytics import YOLO
    ULTRALYTICS_VERSION = ultralytics.__version__
except ImportError:
    ULTRALYTICS_VERSION = "unknown"
    YOLO = None

SUPPORTED_BASE_MODELS = ["yolo11n.pt", "yolo11s.pt", "yolov8n.pt", "yolov8s.pt"]


def detect_hardware() -> Dict[str, Any]:
    """Detect local compute capabilities (CPU vs CUDA GPU)."""
    cuda_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count() if cuda_available else 0
    device_name = torch.cuda.get_device_name(0) if cuda_available and device_count > 0 else "CPU"
    recommended_device = "0" if cuda_available else "cpu"

    return {
        "cuda_available": cuda_available,
        "device_count": device_count,
        "device_name": device_name,
        "recommended_device": recommended_device,
        "torch_version": torch.__version__,
        "ultralytics_version": ULTRALYTICS_VERSION,
    }


def generate_model_version_id(db: Session) -> str:
    """Generate sequential unique model version ID: MODEL-YYYY-XXXXXX."""
    current_year = datetime.now(timezone.utc).year
    prefix = f"MODEL-{current_year}-"

    latest = (
        db.query(ModelVersion)
        .filter(ModelVersion.model_version.like(f"{prefix}%"))
        .order_by(desc(ModelVersion.id))
        .first()
    )

    if latest and latest.model_version.startswith(prefix):
        try:
            current_seq = int(latest.model_version.split("-")[-1])
            new_seq = current_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1

    return f"{prefix}{new_seq:06d}"


class ModelService:
    """
    Service managing Ultralytics YOLO model lifecycle, background training,
    metrics recording, validation, and single-active model activation.
    """

    @staticmethod
    def get_active_model(db: Session) -> Optional[ModelVersion]:
        """Fetch the currently ACTIVE model version from PostgreSQL with verified weights."""
        record = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        if not record:
            return None
        weights_path = record.best_weights_path or record.weights_path
        if not weights_path or not Path(weights_path).exists():
            return None
        return record

    @staticmethod
    def validate_training_prerequisites(
        db: Session,
        dataset_version: str,
        base_model: str,
        epochs: int,
        image_size: int,
        batch_size: int,
    ) -> Tuple[DatasetVersion, Path, Dict[str, Any]]:
        """
        Validate all dataset and hyperparameter constraints before queueing training.
        """
        # 1. Dataset must exist and be READY_FOR_TRAINING
        ds = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
        if not ds:
            raise ValueError(f"Dataset version '{dataset_version}' not found.")

        if ds.status != DatasetStatus.READY_FOR_TRAINING:
            raise ValueError(
                f"Dataset '{dataset_version}' cannot be used for training. "
                f"Current status is '{ds.status}', but must be '{DatasetStatus.READY_FOR_TRAINING}'."
            )

        # 2. Verify dataset directory on disk
        dataset_dir = Path(ds.storage_path).resolve()
        if not dataset_dir.exists():
            raise ValueError(f"Dataset storage path does not exist on disk: {dataset_dir}")

        data_yaml_path = dataset_dir / "data.yaml"
        if not data_yaml_path.exists():
            raise ValueError(f"data.yaml missing in dataset storage: {data_yaml_path}")

        # 3. Read data.yaml configuration
        try:
            with open(data_yaml_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
        except Exception as exc:
            raise ValueError(f"Failed to read dataset data.yaml: {str(exc)}")

        raw_names = yaml_data.get("names", {})
        if isinstance(raw_names, list):
            class_names = {idx: str(name) for idx, name in enumerate(raw_names)}
        elif isinstance(raw_names, dict):
            class_names = {int(k): str(v) for k, v in raw_names.items()}
        else:
            class_names = {}

        if not class_names:
            raise ValueError("Dataset data.yaml declares zero classes.")

        # 4. Hyperparameter bounds validation
        if not (1 <= epochs <= 500):
            raise ValueError(f"Epochs must be between 1 and 500. Received: {epochs}")

        if not (128 <= image_size <= 1280) or (image_size % 32 != 0):
            raise ValueError(f"Image size must be a multiple of 32 between 128 and 1280. Received: {image_size}")

        if not (1 <= batch_size <= 128):
            raise ValueError(f"Batch size must be between 1 and 128. Received: {batch_size}")

        if base_model not in SUPPORTED_BASE_MODELS and not base_model.endswith(".pt"):
            raise ValueError(f"Unsupported base model '{base_model}'. Supported: {SUPPORTED_BASE_MODELS}")

        return ds, data_yaml_path, class_names

    @staticmethod
    def create_training_job(
        db: Session,
        model_name: str,
        dataset_version: str,
        base_model: str,
        epochs: int,
        image_size: int,
        batch_size: int,
        device: str,
        user_id: int,
    ) -> ModelVersion:
        """
        Validate prerequisites, generate model version ID, initialize disk structure,
        create QUEUED ModelVersion database record, and spawn background worker.
        """
        ds, data_yaml_path, class_names = ModelService.validate_training_prerequisites(
            db, dataset_version, base_model, epochs, image_size, batch_size
        )

        model_version = generate_model_version_id(db)
        model_dir = MODELS_ROOT / model_version
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "weights").mkdir(parents=True, exist_ok=True)
        (model_dir / "results").mkdir(parents=True, exist_ok=True)

        # Normalize device: if requested cuda but unavailable, fallback to cpu
        hw = detect_hardware()
        if device != "cpu" and not hw["cuda_available"]:
            device = "cpu"

        # Record initial ModelVersion in PostgreSQL
        model_record = ModelVersion(
            model_version=model_version,
            model_name=model_name.strip(),
            dataset_version=dataset_version,
            base_model=base_model,
            ultralytics_version=ULTRALYTICS_VERSION,
            task="detect",
            class_count=len(class_names),
            class_names=class_names,
            training_status=TrainingStatus.QUEUED,
            is_active=False,
            epochs=epochs,
            image_size=image_size,
            batch_size=batch_size,
            device=device,
            training_output_path=str(model_dir / "results"),
            created_by=user_id,
        )
        db.add(model_record)
        db.commit()
        db.refresh(model_record)

        # Save initial metadata.json
        meta_payload = {
            "model_version": model_version,
            "model_name": model_name,
            "dataset_version": dataset_version,
            "base_model": base_model,
            "ultralytics_version": ULTRALYTICS_VERSION,
            "created_by": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "epochs": epochs,
                "image_size": image_size,
                "batch_size": batch_size,
                "device": device,
            },
            "status": TrainingStatus.QUEUED,
        }
        with open(model_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2)

        # Launch background training worker
        worker_thread = threading.Thread(
            target=ModelService._execute_training_worker,
            args=(model_version, str(data_yaml_path), str(model_dir)),
            daemon=True,
        )
        worker_thread.start()

        return model_record

    @staticmethod
    def _execute_training_worker(model_version: str, data_yaml_str: str, model_dir_str: str):
        """
        Background worker thread executing real Ultralytics training & validation.
        Opens an isolated DB session.
        """
        db = SessionLocal()
        model_dir = Path(model_dir_str)
        data_yaml_path = Path(data_yaml_str)

        model_record = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
        if not model_record:
            db.close()
            return

        start_time = time.time()
        model_record.started_at = datetime.now(timezone.utc)
        model_record.training_status = TrainingStatus.RUNNING
        db.commit()

        try:
            if YOLO is None:
                raise RuntimeError("Ultralytics YOLO package is not installed or available.")

            # 1. Initialize YOLO base model
            model = YOLO(model_record.base_model)

            # 2. Run real Ultralytics training
            results_dir = model_dir / "results"
            train_results = model.train(
                data=str(data_yaml_path),
                epochs=model_record.epochs,
                imgsz=model_record.image_size,
                batch=model_record.batch_size,
                device=model_record.device,
                project=str(results_dir),
                name="run",
                exist_ok=True,
                verbose=True,
            )

            # 3. Locate generated weights
            run_weights_dir = results_dir / "run" / "weights"
            best_pt_src = run_weights_dir / "best.pt"
            last_pt_src = run_weights_dir / "last.pt"

            target_weights_dir = model_dir / "weights"
            best_pt_dest = target_weights_dir / "best.pt"
            last_pt_dest = target_weights_dir / "last.pt"

            if best_pt_src.exists():
                shutil.copy2(str(best_pt_src), str(best_pt_dest))
            if last_pt_src.exists():
                shutil.copy2(str(last_pt_src), str(last_pt_dest))

            if not best_pt_dest.exists():
                raise FileNotFoundError(f"Training completed but 'best.pt' was not generated at {best_pt_src}")

            # 4. Model Loading Test on the newly produced weights
            test_model = YOLO(str(best_pt_dest))

            # 5. Run actual validation on trained model
            val_results = test_model.val(data=str(data_yaml_path), device=model_record.device)

            # Extract metrics from validation results
            precision = None
            recall = None
            map50 = None
            map50_95 = None

            if hasattr(val_results, "results_dict") and isinstance(val_results.results_dict, dict):
                rd = val_results.results_dict
                precision = float(rd.get("metrics/precision(B)", 0.0)) if "metrics/precision(B)" in rd else None
                recall = float(rd.get("metrics/recall(B)", 0.0)) if "metrics/recall(B)" in rd else None
                map50 = float(rd.get("metrics/mAP50(B)", 0.0)) if "metrics/mAP50(B)" in rd else None
                map50_95 = float(rd.get("metrics/mAP50-95(B)", 0.0)) if "metrics/mAP50-95(B)" in rd else None

            end_time = time.time()
            duration = round(end_time - start_time, 2)

            # 6. Update PostgreSQL record with real metrics
            model_record.weights_path = str(best_pt_dest)
            model_record.best_weights_path = str(best_pt_dest)
            model_record.last_weights_path = str(last_pt_dest) if last_pt_dest.exists() else None
            model_record.training_status = TrainingStatus.COMPLETED
            model_record.completed_at = datetime.now(timezone.utc)
            model_record.training_duration_seconds = duration
            model_record.precision = precision
            model_record.recall = recall
            model_record.map50 = map50
            model_record.map50_95 = map50_95
            model_record.validation_metrics = getattr(val_results, "results_dict", {})
            model_record.updated_at = datetime.now(timezone.utc)
            db.commit()

            # 7. Update metadata.json on disk
            meta_path = model_dir / "metadata.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["status"] = TrainingStatus.COMPLETED
                meta["completed_at"] = model_record.completed_at.isoformat()
                meta["duration_seconds"] = duration
                meta["metrics"] = {
                    "precision": precision,
                    "recall": recall,
                    "map50": map50,
                    "map50_95": map50_95,
                }
                meta["best_weights"] = str(best_pt_dest)
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)

        except Exception as exc:
            end_time = time.time()
            model_record.training_status = TrainingStatus.FAILED
            model_record.completed_at = datetime.now(timezone.utc)
            model_record.training_duration_seconds = round(end_time - start_time, 2)
            model_record.error_message = str(exc)
            model_record.updated_at = datetime.now(timezone.utc)
            db.commit()

            # Record failure in metadata.json
            meta_path = model_dir / "metadata.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["status"] = TrainingStatus.FAILED
                    meta["error"] = str(exc)
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                except Exception:
                    pass

        finally:
            db.close()

    @staticmethod
    def activate_model(db: Session, model_version: str) -> ModelVersion:
        """
        Activate a COMPLETED model version.
        Guarantees only ONE active model at a time.
        Transitions previously active model to ARCHIVED.
        """
        target = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
        if not target:
            raise ValueError(f"Model version '{model_version}' not found.")

        if target.training_status not in [TrainingStatus.COMPLETED, TrainingStatus.ARCHIVED]:
            raise ValueError(
                f"Model '{model_version}' cannot be activated. "
                f"Status must be '{TrainingStatus.COMPLETED}' or '{TrainingStatus.ARCHIVED}', but is '{target.training_status}'."
            )

        if not target.best_weights_path:
            raise ValueError(f"Model '{model_version}' does not have a recorded weights path.")

        best_weights_file = Path(target.best_weights_path)
        if not best_weights_file.exists():
            raise ValueError(f"Weights file not found on disk at: {best_weights_file}")

        # Verify weights file can actually be loaded by YOLO
        try:
            if YOLO is None:
                raise RuntimeError("Ultralytics YOLO package is not installed.")
            loaded_model = YOLO(str(best_weights_file))
            if loaded_model is None:
                raise RuntimeError("YOLO returned None upon loading weights.")
        except Exception as exc:
            raise ValueError(f"Weights file failed integrity verification test: {str(exc)}")


        # Archive any currently active model
        active_models = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all()
        for active in active_models:
            if active.id != target.id:
                active.is_active = False
                active.training_status = TrainingStatus.ARCHIVED
                active.updated_at = datetime.now(timezone.utc)

        # Activate target model
        target.is_active = True
        target.training_status = TrainingStatus.ACTIVE
        target.updated_at = datetime.now(timezone.utc)

        record_audit_log(
            action="MODEL_ACTIVATED",
            entity_type="ModelVersion",
            entity_id=model_version,
            user_id=None,
            db=db,
            metadata={
                "model_name": target.model_name,
                "dataset_version": target.dataset_version,
                "map50": target.map50,
            },
        )
        # Clear inference model cache
        from app.ai.model_loader import ModelLoader
        ModelLoader.clear_cache()

        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def deactivate_model(db: Session, model_version: str, user_id: Optional[int] = None) -> ModelVersion:
        """
        Safely deactivate an active model, setting is_active=False and training_status=COMPLETED.
        Records an audit log entry in PostgreSQL.
        """
        target = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
        if not target:
            raise ValueError(f"Model version '{model_version}' not found.")

        prev_status = target.training_status
        prev_active = target.is_active

        target.is_active = False
        if target.training_status == TrainingStatus.ACTIVE:
            target.training_status = TrainingStatus.COMPLETED
        target.updated_at = datetime.now(timezone.utc)

        record_audit_log(
            action="MODEL_DEACTIVATED",
            entity_type="ModelVersion",
            entity_id=model_version,
            user_id=user_id,
            db=db,
            metadata={
                "model_name": target.model_name,
                "previous_status": prev_status,
                "previous_is_active": prev_active,
                "new_status": target.training_status,
                "new_is_active": False,
                "reason": "Model safely deactivated from production",
            },
        )
        # Clear inference model cache
        from app.ai.model_loader import ModelLoader
        ModelLoader.clear_cache()

        db.commit()
        db.refresh(target)
        return target

    @staticmethod
    def run_inference(db: Session, model_version: str, image_path: Path) -> Dict[str, Any]:
        """
        Run actual inference using a verified model on a provided image file.
        Returns real detections or error state.
        """
        model_record = db.query(ModelVersion).filter(ModelVersion.model_version == model_version).first()
        if not model_record:
            raise ValueError(f"Model version '{model_version}' not found.")

        if not model_record.best_weights_path or not Path(model_record.best_weights_path).exists():
            raise ValueError(f"Model weights file does not exist on disk.")

        if not image_path.exists():
            raise ValueError(f"Inference image file not found: {image_path}")

        try:
            model = YOLO(model_record.best_weights_path)
            results = model.predict(source=str(image_path), save=False)

            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    c_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = [float(x) for x in box.xyxy[0].tolist()]
                    c_name = model.names.get(c_id, f"class_{c_id}")
                    detections.append({
                        "class_id": c_id,
                        "class_name": c_name,
                        "confidence": round(conf, 4),
                        "bounding_box": xyxy,
                    })

            return {
                "model_version": model_version,
                "image": image_path.name,
                "detection_count": len(detections),
                "detections": detections,
            }
        except Exception as exc:
            raise RuntimeError(f"Inference execution failed: {str(exc)}")
