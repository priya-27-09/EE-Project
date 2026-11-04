"""
AI Civic Guardian — Production Candidate Model Training, Validation & Integration Pipeline
Candidate Model: MODEL-2026-000002
Dataset: DS-2026-000018

Mandatory Requirements:
1. Genuine AI model training using Ultralytics YOLO with PyTorch.
2. 12 Canonical Classes preserved in exact order (0 to 11).
3. Class 7 (Drainage Problem) has 0 verified samples — clearly reported as non-evaluated without fabrication.
4. Model candidate saved in its own versioned directory: models/MODEL-2026-000002.
5. All previous models (including MODEL-2026-000001 and experimental_baseline_v1) strictly preserved.
6. Candidate model registered in PostgreSQL with is_active=False (NO automatic activation).
7. Complete evaluation performed on the separate 152-image test split.
"""

import sys
import os
import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import torch
from ultralytics import YOLO

from app.db.session import SessionLocal
from app.models.dataset import DatasetVersion
from app.models.model_version import ModelVersion, TrainingStatus
from app.models.user import User, UserRole

CANONICAL_CLASSES = {
    0: "Garbage Overflow",
    1: "Illegal Dumping",
    2: "Pothole",
    3: "Damaged Road",
    4: "Water Leakage",
    5: "Sewage Overflow",
    6: "Broken Street Light",
    7: "Drainage Problem",
    8: "Traffic Issue",
    9: "Building Damage",
    10: "Park/Public Space Damage",
    11: "Environmental Pollution"
}

def main():
    print("=" * 80)
    print("AI CIVIC GUARDIAN — CANDIDATE MODEL TRAINING PIPELINE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    candidate_id = "MODEL-2026-000002"
    dataset_version = "DS-2026-000018"
    candidate_dir = BASE_DIR / "models" / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = candidate_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        # Step 1: Verify Dataset
        print(f"\n[STEP 1] Verifying Dataset {dataset_version}...")
        ds_rec = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == dataset_version).first()
        if not ds_rec:
            raise RuntimeError(f"Dataset {dataset_version} not found in database!")

        ds_path = Path(ds_rec.storage_path).resolve()
        print(f"  Storage Path: {ds_path}")
        print(f"  Total Images: {ds_rec.total_image_count} (Train: {ds_rec.train_image_count}, Val: {ds_rec.val_image_count}, Test: {ds_rec.test_image_count})")

        # Step 2: Prepare YAML config
        yaml_path = candidate_dir / "data_training.yaml"
        yaml_content = (
            f"path: {ds_path.as_posix()}\n"
            f"train: images/train\n"
            f"val: images/val\n"
            f"test: images/test\n"
            f"names:\n"
        )
        for cid in range(12):
            yaml_content += f"  {cid}: {CANONICAL_CLASSES[cid]}\n"
        yaml_path.write_text(yaml_content, encoding="utf-8")
        print(f"  Generated training YAML: {yaml_path}")

        # Save class mapping
        class_mapping_path = candidate_dir / "class_mapping.json"
        class_mapping_path.write_text(json.dumps(CANONICAL_CLASSES, indent=2), encoding="utf-8")

        # Step 3: Base Model Checkpoint
        base_weights = BASE_DIR / "yolo11n.pt"
        if not base_weights.exists():
            raise RuntimeError(f"Base pretrained weights {base_weights} not found!")
        print(f"\n[STEP 2] Loading Base Architecture from: {base_weights}")
        model = YOLO(str(base_weights))

        # Step 4: Real YOLO Training
        epochs = 5
        imgsz = 320
        batch = 32
        device = "cpu"
        seed = 42

        print(f"\n[STEP 3] Starting Real Training for {epochs} epochs on {device}...")
        print(f"  Hyperparameters: imgsz={imgsz}, batch={batch}, seed={seed}, workers=2")
        train_start = time.time()

        train_results = model.train(
            data=str(yaml_path),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            device=device,
            seed=seed,
            project=str(candidate_dir),
            name="candidate_run",
            exist_ok=True,
            verbose=True,
            val=True,
            save=True,
            plots=True,
        )
        train_duration = time.time() - train_start
        print(f"  Training successfully completed in {train_duration:.2f} seconds ({train_duration/60:.2f} minutes).")

        # Copy best and last weights to candidate weights dir
        run_weights_dir = candidate_dir / "candidate_run" / "weights"
        candidate_best = weights_dir / "best.pt"
        candidate_last = weights_dir / "last.pt"

        if (run_weights_dir / "best.pt").exists():
            shutil.copy2(str(run_weights_dir / "best.pt"), str(candidate_best))
            print(f"  Saved best checkpoint: {candidate_best} ({candidate_best.stat().st_size} bytes)")
        if (run_weights_dir / "last.pt").exists():
            shutil.copy2(str(run_weights_dir / "last.pt"), str(candidate_last))
            print(f"  Saved last checkpoint: {candidate_last} ({candidate_last.stat().st_size} bytes)")

        # Step 5: Standalone Test Split Evaluation (152 Test Images)
        print("\n[STEP 4] Evaluating Candidate Model on Separate Test Split (152 images)...")
        eval_model = YOLO(str(candidate_best))
        eval_start = time.time()
        test_results = eval_model.val(
            data=str(yaml_path),
            split="test",
            imgsz=imgsz,
            batch=batch,
            device=device,
            project=str(candidate_dir),
            name="test_evaluation",
            exist_ok=True,
            verbose=False,
            plots=True,
        )
        eval_duration = time.time() - eval_start
        print(f"  Test evaluation completed in {eval_duration:.2f} seconds.")

        # Extract genuine test metrics
        rd = getattr(test_results, "results_dict", {})
        prec = float(rd.get("metrics/precision(B)", 0.0))
        rec = float(rd.get("metrics/recall(B)", 0.0))
        m50 = float(rd.get("metrics/mAP50(B)", 0.0))
        m50_95 = float(rd.get("metrics/mAP50-95(B)", 0.0))

        print(f"\n[STEP 5] Candidate Test Set Evaluation Results:")
        print(f"  Overall Precision (B): {prec:.4f}")
        print(f"  Overall Recall (B):    {rec:.4f}")
        print(f"  Overall mAP@50 (B):    {m50:.4f}")
        print(f"  Overall mAP@50-95 (B): {m50_95:.4f}")

        # Per-class metrics
        class_metrics = {}
        names = test_results.names if hasattr(test_results, "names") else CANONICAL_CLASSES
        maps = test_results.maps if hasattr(test_results, "maps") else []

        print("\n  Per-Class Evaluation Summary:")
        for idx in range(12):
            cname = CANONICAL_CLASSES[idx]
            if idx == 7:
                # Class 7 has zero test annotations
                class_metrics[cname] = {
                    "class_id": 7,
                    "status": "NON_EVALUATED",
                    "reason": "Zero verified test samples available in canonical dataset",
                    "ap50": None,
                    "ap50_95": None,
                }
                print(f"    Class {idx:>2}: {cname:<26} -> NON-EVALUATED (0 test annotations; safe fallback required)")
            else:
                ap = float(maps[idx]) if idx < len(maps) else 0.0
                class_metrics[cname] = {
                    "class_id": idx,
                    "status": "EVALUATED",
                    "mAP50_95": ap,
                }
                print(f"    Class {idx:>2}: {cname:<26} -> mAP50-95: {ap:.4f}")

        # Save evaluation report JSON
        eval_report = {
            "model_version": candidate_id,
            "dataset_version": dataset_version,
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "test_split_image_count": ds_rec.test_image_count,
            "overall_metrics": {
                "precision": prec,
                "recall": rec,
                "mAP50": m50,
                "mAP50_95": m50_95,
            },
            "per_class_metrics": class_metrics,
            "class_7_drainage_problem": {
                "verified_test_samples": 0,
                "evaluated": False,
                "handling": "Safe fallback to municipal supervisory review and manual category confirmation",
            },
            "training_duration_seconds": train_duration,
            "raw_results_dict": {k: float(v) if isinstance(v, (int, float)) else str(v) for k, v in rd.items()},
        }
        report_path = candidate_dir / "evaluation_report.json"
        report_path.write_text(json.dumps(eval_report, indent=2), encoding="utf-8")
        print(f"\n  Saved evaluation report: {report_path}")

        # Save training metadata
        meta = {
            "candidate_id": candidate_id,
            "base_model": "yolo11n.pt",
            "ultralytics_version": getattr(test_results, "version", "8.4.200"),
            "epochs": epochs,
            "imgsz": imgsz,
            "batch_size": batch,
            "device": device,
            "training_duration_seconds": train_duration,
            "dataset_version": dataset_version,
            "train_images": ds_rec.train_image_count,
            "val_images": ds_rec.val_image_count,
            "test_images": ds_rec.test_image_count,
            "weights_best": str(candidate_best),
            "weights_last": str(candidate_last),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = candidate_dir / "training_metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # Step 6: Register in PostgreSQL as INACTIVE Candidate
        print("\n[STEP 6] Registering Candidate Model in PostgreSQL...")
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        admin_id = admin.id if admin else 1

        rec = db.query(ModelVersion).filter(ModelVersion.model_version == candidate_id).first()
        if not rec:
            rec = ModelVersion(
                model_version=candidate_id,
                model_name=f"AI Civic Guardian YOLO11n Production Candidate ({dataset_version})",
                dataset_version=dataset_version,
                base_model="yolo11n.pt",
                ultralytics_version="8.4.200",
                task="detect",
                epochs=epochs,
                image_size=imgsz,
                batch_size=batch,
                device=device,
                class_count=12,
                class_names={str(k): v for k, v in CANONICAL_CLASSES.items()},
                weights_path=str(candidate_best),
                best_weights_path=str(candidate_best),
                last_weights_path=str(candidate_last),
                training_status=TrainingStatus.COMPLETED,
                is_active=False, # STRICT REQUIREMENT: DO NOT ACTIVATE AUTOMATICALLY
                precision=prec,
                recall=rec,
                map50=m50,
                map50_95=m50_95,
                training_duration_seconds=train_duration,
                validation_metrics=eval_report["raw_results_dict"],
                training_output_path=str(candidate_dir / "candidate_run"),
                completed_at=datetime.now(timezone.utc),
                created_by=admin_id,
            )
            db.add(rec)
        else:
            rec.model_name = f"AI Civic Guardian YOLO11n Production Candidate ({dataset_version})"
            rec.weights_path = str(candidate_best)
            rec.best_weights_path = str(candidate_best)
            rec.last_weights_path = str(candidate_last)
            rec.training_status = TrainingStatus.COMPLETED
            rec.is_active = False # STRICT REQUIREMENT: DO NOT ACTIVATE AUTOMATICALLY
            rec.precision = prec
            rec.recall = rec
            rec.map50 = m50
            rec.map50_95 = m50_95
            rec.training_duration_seconds = train_duration
            rec.validation_metrics = eval_report["raw_results_dict"]
            rec.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(rec)
        print(f"  Successfully registered {candidate_id} in database (is_active={rec.is_active}, status={rec.training_status})!")

        # Step 7: Verification of Candidate Weights with sample inference
        print("\n[STEP 7] Verifying Candidate Checkpoint with Sample Inference...")
        test_img_path = BASE_DIR / "tests" / "fixtures" / "yolo_dataset" / "images" / "train" / "pothole_sample01.jpg"
        if not test_img_path.exists():
            test_img_path = ds_path / "images" / "test" / list((ds_path / "images" / "test").glob("*.*"))[0].name
        
        from PIL import Image
        pil_img = Image.open(test_img_path)
        sample_results = eval_model(pil_img, conf=0.15, verbose=False)
        print(f"  Sample inference on {test_img_path.name} produced {len(sample_results[0].boxes)} detection(s):")
        for b in sample_results[0].boxes:
            cid = int(b.cls[0].item())
            conf = float(b.conf[0].item())
            print(f"    -> Detected: Class {cid} ({CANONICAL_CLASSES.get(cid, 'Unknown')}) with confidence {conf:.3f}")

        print("\n" + "=" * 80)
        print("CANDIDATE MODEL TRAINING, EVALUATION & ARTIFACT PERSISTENCE COMPLETE!")
        print(f"Candidate ID: {candidate_id}")
        print(f"Artifacts: {candidate_best}")
        print(f"Active in Production: {rec.is_active} (Maintained False per requirements)")
        print("=" * 80)

    finally:
        db.close()

if __name__ == "__main__":
    main()

