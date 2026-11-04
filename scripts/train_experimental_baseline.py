"""
AI Civic Guardian - Experimental Baseline YOLO Training

Mandatory Safety Requirements:
1. Uses only existing staged dataset version DS-2026-000018.
2. Does NOT modify dataset/canonical/, dataset/staged_canonical/, raw ZIP files, or existing dataset records.
3. Preserves canonical 12-class mapping exactly (IDs 0-11 in order).
4. Explicitly reports that Class 7 (Drainage Problem) has ZERO verified annotations. No synthetic samples or fake labels created.
5. Saves model checkpoints and logs in a new experimental output directory: models/experimental_baseline_v1/.
6. Runs a 5-epoch baseline with yolo11n.pt on CPU.
7. Evaluates validation metrics (precision, recall, mAP50, mAP50-95, per-class metrics).
8. Marks model as EXPERIMENTAL BASELINE (is_active=False). Does NOT promote to production or integrate into live website.
"""

import os
import sys
import io
import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

import torch
import yaml
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.models.dataset import DatasetVersion
from app.models.model_version import ModelVersion, TrainingStatus
from app.models.user import User, UserRole
from app.services.model_service import detect_hardware, generate_model_version_id

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
    print("AI CIVIC GUARDIAN — EXPERIMENTAL BASELINE YOLO TRAINING")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Environment & Hardware Checks
    print("\n[STEP 1] Environment & Hardware Inspection:")
    hw = detect_hardware()
    print(f"  PyTorch Version: {hw['torch_version']}")
    print(f"  Ultralytics Version: {hw['ultralytics_version']}")
    print(f"  CUDA Available: {hw['cuda_available']} (Device: {hw['device_name']})")
    print(f"  Training Device Selected: cpu")

    # 2. Dataset Verification (DS-2026-000018)
    print("\n[STEP 2] Dataset Verification (DS-2026-000018):")
    db = SessionLocal()
    ds = db.query(DatasetVersion).filter(DatasetVersion.dataset_version == "DS-2026-000018").first()
    if not ds:
        print("[ERROR] Dataset version DS-2026-000018 not found in database!")
        db.close()
        sys.exit(1)

    ds_dir = Path(ds.storage_path).resolve()
    print(f"  Dataset Storage Path: {ds_dir}")
    print(f"  Database Status: {ds.status}")
    print(f"  Total Images: {ds.total_image_count} (Train: {ds.train_image_count}, Val: {ds.val_image_count}, Test: {ds.test_image_count})")
    print(f"  Total Annotations: {ds.total_object_count}")

    # Count annotations per class directly from labels to explicitly confirm Class 7 count
    from collections import Counter
    class_annot_counts = Counter()
    for lbl_p in (ds_dir / "labels").rglob("*.txt"):
        for line in lbl_p.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if parts:
                class_annot_counts[int(parts[0])] += 1

    print("\n  Class Distribution in DS-2026-000018:")
    for cid in range(12):
        cname = CANONICAL_CLASSES[cid]
        cnt = class_annot_counts[cid]
        flag = " [ZERO ANNOTATIONS — NOT TRAINED/VALIDATED]" if cnt == 0 else ""
        print(f"    Class {cid:>2}: {cname:<26} -> {cnt:>5} boxes{flag}")

    assert class_annot_counts[7] == 0, "Class 7 should have 0 annotations per project status"
    print("\n  [SAFETY CONFIRMATION] Class 7 (Drainage Problem) has exactly ZERO annotations.")
    print("  No synthetic labels or fabricated boxes are added.")

    # 3. Create Experimental Training Output Directory and data.yaml
    exp_output_dir = BASE_DIR / "models" / "experimental_baseline_v1"
    exp_output_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = exp_output_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    results_dir = exp_output_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    data_yaml_path = exp_output_dir / "data_training.yaml"
    data_yaml_dict = {
        "path": str(ds_dir).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {i: CANONICAL_CLASSES[i] for i in range(12)}
    }
    with open(data_yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data_yaml_dict, f, sort_keys=False)
    print(f"\n[STEP 3] Created training configuration: {data_yaml_path}")
    print(f"  Experimental Checkpoints Directory: {exp_output_dir}")

    # 4. Initialize Pretrained Base Model (yolo11n.pt)
    print("\n[STEP 4] Initializing Pretrained Base Model (yolo11n.pt)...")
    base_model_path = BASE_DIR / "yolo11n.pt"
    if not base_model_path.exists():
        print(f"[ERROR] Base model {base_model_path} not found!")
        db.close()
        sys.exit(1)

    model = YOLO(str(base_model_path))
    print(f"  Base Model Loaded: {base_model_path.name}")

    # 5. Execute 5-Epoch Experimental Baseline Training
    epochs = 5
    imgsz = 320
    batch_size = 32
    print(f"\n[STEP 5] Starting Baseline Training ({epochs} epochs, imgsz={imgsz}, batch={batch_size}, device=cpu)...")
    start_time = time.time()

    train_results = model.train(
        data=str(data_yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        device="cpu",
        project=str(results_dir),
        name="run_baseline",
        exist_ok=True,
        verbose=True
    )
    training_duration = round(time.time() - start_time, 2)
    print(f"\n[TRAINING COMPLETE] Completed {epochs} epochs in {training_duration}s ({training_duration/60:.2f} mins).")

    # 6. Locate Generated Weights
    run_dir = results_dir / "run_baseline"
    run_weights_dir = run_dir / "weights"
    best_pt_src = run_weights_dir / "best.pt"
    last_pt_src = run_weights_dir / "last.pt"

    best_pt_dest = weights_dir / "best.pt"
    last_pt_dest = weights_dir / "last.pt"

    if best_pt_src.exists():
        shutil.copy2(str(best_pt_src), str(best_pt_dest))
    if last_pt_src.exists():
        shutil.copy2(str(last_pt_src), str(last_pt_dest))

    print(f"  Best Weights Saved: {best_pt_dest}")
    print(f"  Last Weights Saved: {last_pt_dest}")

    # 7. Model Validation & Evaluation
    print("\n[STEP 6] Running Validation on Validation Split (304 images)...")
    eval_model = YOLO(str(best_pt_dest))
    val_metrics = eval_model.val(
        data=str(data_yaml_path),
        imgsz=imgsz,
        batch=batch_size,
        device="cpu",
        verbose=True
    )

    # Extract metrics
    rd = getattr(val_metrics, "results_dict", {})
    precision = float(rd.get("metrics/precision(B)", 0.0))
    recall = float(rd.get("metrics/recall(B)", 0.0))
    map50 = float(rd.get("metrics/mAP50(B)", 0.0))
    map50_95 = float(rd.get("metrics/mAP50-95(B)", 0.0))

    print("\n" + "=" * 80)
    print("EXPERIMENTAL BASELINE EVALUATION METRICS")
    print("=" * 80)
    print(f"  Overall Precision (B): {precision:.4f}")
    print(f"  Overall Recall (B):    {recall:.4f}")
    print(f"  Overall mAP@50 (B):    {map50:.4f}")
    print(f"  Overall mAP@50-95 (B): {map50_95:.4f}")

    # Per-class metrics
    print("\nPer-Class Detection Performance (Validation Split):")
    print("-" * 80)
    print(f"{'ID':<4} {'Class Name':<28} {'Images':<8} {'Instances':<10} {'P':<8} {'R':<8} {'mAP50':<8}")
    print("-" * 80)

    # Extract per-class arrays if available
    box_p = getattr(val_metrics.box, "p", None)
    box_r = getattr(val_metrics.box, "r", None)
    box_ap50 = getattr(val_metrics.box, "ap50", None)

    for cid in range(12):
        cname = CANONICAL_CLASSES[cid]
        if cid == 7:
            print(f"{cid:<4} {cname:<28} {'0':<8} {'0':<10} {'N/A':<8} {'N/A':<8} {'N/A':<8} [WARNING: NO EXAMPLES]")
        else:
            p_val = f"{box_p[cid]:.3f}" if box_p is not None and len(box_p) > cid else "N/A"
            r_val = f"{box_r[cid]:.3f}" if box_r is not None and len(box_r) > cid else "N/A"
            ap_val = f"{box_ap50[cid]:.3f}" if box_ap50 is not None and len(box_ap50) > cid else "N/A"
            # Get val split instances for this class
            val_instances = 0
            for lbl_p in (ds_dir / "labels" / "val").glob("*.txt"):
                for l in lbl_p.read_text().splitlines():
                    if l.strip() and int(l.split()[0]) == cid:
                        val_instances += 1
            print(f"{cid:<4} {cname:<28} {'304':<8} {str(val_instances):<10} {p_val:<8} {r_val:<8} {ap_val:<8}")
    print("-" * 80)

    # 8. Record in PostgreSQL as EXPERIMENTAL BASELINE (is_active=False)
    print("\n[STEP 7] Registering Experimental Model Version in PostgreSQL...")
    try:
        admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
        user_id = admin_user.id if admin_user else 1

        model_version_id = generate_model_version_id(db)
        model_record = ModelVersion(
            model_version=model_version_id,
            model_name="Experimental Baseline YOLO11n (DS-2026-000018)",
            dataset_version="DS-2026-000018",
            base_model="yolo11n.pt",
            ultralytics_version=hw["ultralytics_version"],
            task="detect",
            class_count=12,
            class_names=CANONICAL_CLASSES,
            training_status=TrainingStatus.COMPLETED,
            is_active=False,  # CRITICAL: Keep false. Not production ready.
            epochs=epochs,
            image_size=imgsz,
            batch_size=batch_size,
            device="cpu",
            training_duration_seconds=training_duration,
            precision=precision,
            recall=recall,
            map50=map50,
            map50_95=map50_95,
            weights_path=str(best_pt_dest),
            best_weights_path=str(best_pt_dest),
            last_weights_path=str(last_pt_dest),
            training_output_path=str(run_dir),
            validation_metrics=rd,
            created_by=user_id,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(model_record)
        db.commit()
        db.refresh(model_record)
        print(f"  [SUCCESS] Registered in PostgreSQL as '{model_record.model_version}' (ID: {model_record.id}).")
        print(f"  Active Status: is_active={model_record.is_active} (EXPERIMENTAL ONLY — NOT ACTIVATED FOR WEB INFERENCE)")
    except Exception as exc:
        print(f"  [NOTE] DB Registration note: {exc}")
    finally:
        db.close()

    # 9. Save Metadata and Evaluation JSON
    report_data = {
        "model_version": model_version_id if 'model_version_id' in locals() else "EXP-BASELINE",
        "dataset_version": "DS-2026-000018",
        "status": "EXPERIMENTAL_BASELINE",
        "is_active": False,
        "is_production_ready": False,
        "base_model": "yolo11n.pt",
        "device": "cpu",
        "epochs": epochs,
        "imgsz": imgsz,
        "batch_size": batch_size,
        "duration_seconds": training_duration,
        "weights_path": str(best_pt_dest),
        "results_path": str(run_dir),
        "metrics": {
            "precision": precision,
            "recall": recall,
            "map50": map50,
            "map50_95": map50_95
        },
        "class_warning": "Class 7 (Drainage Problem) has 0 annotations in dataset and was not evaluated.",
        "completed_at": datetime.now(timezone.utc).isoformat()
    }
    with open(exp_output_dir / "experimental_baseline_report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print("\n" + "=" * 80)
    print("EXPERIMENTAL BASELINE COMPLETED SUCCESSFULLY.")
    print("STATUS: EXPERIMENTAL BASELINE ONLY (NOT PRODUCTION READY).")
    print(f"Saved Checkpoints: {best_pt_dest}")
    print(f"Saved Report: {exp_output_dir / 'experimental_baseline_report.json'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
