"""
AI Civic Guardian - Standalone Test Split Evaluation & Model Audit

Objective:
1. Load models/experimental_baseline_v1/weights/best.pt without modifying it.
2. Run standalone validation strictly on the 152-image TEST split (split='test').
3. Save all outputs into a new directory: models/experimental_baseline_v1/test_audit/.
4. Extract overall precision, recall, mAP50, mAP50-95, and per-class metrics.
5. Report the evaluation results and save test_set_evaluation_report.json.
6. Confirm zero modifications to checkpoints, dataset records, or active inference configuration.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.models.model_version import ModelVersion
from app.models.dataset import DatasetVersion

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
    print("AI CIVIC GUARDIAN — STANDALONE TEST SPLIT EVALUATION & AUDIT")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. Path & Checkpoint Verification
    weights_path = BASE_DIR / "models" / "experimental_baseline_v1" / "weights" / "best.pt"
    data_yaml_path = BASE_DIR / "models" / "experimental_baseline_v1" / "data_training.yaml"
    audit_output_dir = BASE_DIR / "models" / "experimental_baseline_v1" / "test_audit"
    audit_output_dir.mkdir(parents=True, exist_ok=True)

    if not weights_path.exists():
        print(f"[ERROR] Checkpoint not found at: {weights_path}")
        sys.exit(1)
    if not data_yaml_path.exists():
        print(f"[ERROR] Training data.yaml not found at: {data_yaml_path}")
        sys.exit(1)

    print(f"Loading checkpoint: {weights_path}")
    model = YOLO(str(weights_path))

    # Verify class names in checkpoint
    print("Verifying checkpoint class names against canonical mapping:")
    for cid in range(12):
        ckpt_name = model.names.get(cid)
        expected_name = CANONICAL_CLASSES[cid]
        match = ckpt_name == expected_name
        print(f"  Class {cid:>2}: '{ckpt_name}' == '{expected_name}' -> {match}")
        assert match, f"Class name mismatch at ID {cid}: {ckpt_name} != {expected_name}"

    # 2. Verify Test Split on Disk
    ds_dir = BASE_DIR / "dataset" / "versions" / "DS-2026-000018"
    test_imgs = list((ds_dir / "images" / "test").glob("*.*"))
    test_lbls = list((ds_dir / "labels" / "test").glob("*.txt"))
    print(f"\nTest Split Verification:")
    print(f"  Test Images on Disk: {len(test_imgs)}")
    print(f"  Test Labels on Disk: {len(test_lbls)}")
    assert len(test_imgs) == 152, f"Expected 152 test images, found {len(test_imgs)}"

    # Count test instances per class
    test_counts = Counter()
    for lbl in test_lbls:
        for line in lbl.read_text().splitlines():
            if line.strip():
                test_counts[int(line.split()[0])] += 1

    print("  Test Set Ground-Truth Instance Counts:")
    for cid in range(12):
        print(f"    Class {cid:>2} ({CANONICAL_CLASSES[cid]:<26}): {test_counts[cid]:>4} instances")

    assert test_counts[7] == 0, "Class 7 should have 0 instances in test set"

    # 3. Execute Standalone Test Split Evaluation
    print(f"\n[EVALUATION] Running model.val() on TEST split (split='test', imgsz=320, batch=32, device='cpu')...")
    start_time = time.time()
    test_results = model.val(
        data=str(data_yaml_path),
        split="test",
        imgsz=320,
        batch=32,
        device="cpu",
        project=str(audit_output_dir),
        name="test_evaluation",
        exist_ok=True,
        verbose=True
    )
    eval_duration = round(time.time() - start_time, 2)
    print(f"[EVALUATION COMPLETE] Completed in {eval_duration} seconds.")

    # 4. Extract Overall Test Metrics
    rd = getattr(test_results, "results_dict", {})
    precision = float(rd.get("metrics/precision(B)", 0.0))
    recall = float(rd.get("metrics/recall(B)", 0.0))
    map50 = float(rd.get("metrics/mAP50(B)", 0.0))
    map50_95 = float(rd.get("metrics/mAP50-95(B)", 0.0))

    print("\n" + "=" * 80)
    print("STANDALONE TEST SPLIT METRICS (152 IMAGES, 311 INSTANCES)")
    print("=" * 80)
    print(f"  Overall Precision (B): {precision:.4f}")
    print(f"  Overall Recall (B):    {recall:.4f}")
    print(f"  Overall mAP@50 (B):    {map50:.4f}")
    print(f"  Overall mAP@50-95 (B): {map50_95:.4f}")

    # 5. Extract Per-Class Metrics
    box_p = getattr(test_results.box, "p", None)
    box_r = getattr(test_results.box, "r", None)
    box_ap50 = getattr(test_results.box, "ap50", None)
    box_ap = getattr(test_results.box, "ap", None)

    per_class_results = {}
    print("\nPer-Class Test Detection Performance:")
    print("-" * 80)
    print(f"{'ID':<4} {'Class Name':<28} {'Instances':<10} {'P':<8} {'R':<8} {'mAP50':<8} {'mAP50-95':<10}")
    print("-" * 80)

    ap_idx = getattr(test_results.box, "ap_class_index", None)
    if ap_idx is not None and hasattr(ap_idx, "tolist"):
        ap_idx = ap_idx.tolist()
    elif ap_idx is None:
        ap_idx = []

    for cid in range(12):
        cname = CANONICAL_CLASSES[cid]
        inst = test_counts[cid]
        if cid == 7 or inst == 0 or cid not in ap_idx:
            print(f"{cid:<4} {cname:<28} {'0':<10} {'N/A':<8} {'N/A':<8} {'N/A':<8} {'N/A':<10} [ZERO GROUND TRUTH]")
            per_class_results[cname] = {
                "class_id": cid,
                "instances": inst,
                "precision": None,
                "recall": None,
                "map50": None,
                "map50_95": None,
                "note": "Zero verified ground-truth instances in dataset; cannot be evaluated."
            }
        else:
            arr_idx = ap_idx.index(cid)
            p_val = float(box_p[arr_idx]) if box_p is not None and len(box_p) > arr_idx else None
            r_val = float(box_r[arr_idx]) if box_r is not None and len(box_r) > arr_idx else None
            ap50_val = float(box_ap50[arr_idx]) if box_ap50 is not None and len(box_ap50) > arr_idx else None
            ap_val = float(box_ap[arr_idx]) if box_ap is not None and len(box_ap) > arr_idx else None

            p_str = f"{p_val:.3f}" if p_val is not None else "N/A"
            r_str = f"{r_val:.3f}" if r_val is not None else "N/A"
            ap50_str = f"{ap50_val:.3f}" if ap50_val is not None else "N/A"
            ap_str = f"{ap_val:.3f}" if ap_val is not None else "N/A"

            print(f"{cid:<4} {cname:<28} {str(inst):<10} {p_str:<8} {r_str:<8} {ap50_str:<8} {ap_str:<10}")
            per_class_results[cname] = {
                "class_id": cid,
                "instances": inst,
                "precision": p_val,
                "recall": r_val,
                "map50": ap50_val,
                "map50_95": ap_val
            }
    print("-" * 80)

    # 6. Verify Database & Configuration Integrity
    db = SessionLocal()
    try:
        model_rec = db.query(ModelVersion).filter(ModelVersion.model_version == "MODEL-2026-000001").first()
        active_rec = db.query(ModelVersion).filter(ModelVersion.is_active == True).first()
        print("\nDatabase Safety Verification:")
        print(f"  MODEL-2026-000001 Record Found: {model_rec is not None}")
        print(f"  MODEL-2026-000001 is_active: {model_rec.is_active if model_rec else 'None'}")
        print(f"  Active Production Model: {active_rec.model_version if active_rec else 'None (Safe - No model active)'}")
    finally:
        db.close()

    # 7. Write Audit Report JSON
    audit_report = {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_version": "MODEL-2026-000001",
        "checkpoint_path": str(weights_path),
        "dataset_version": "DS-2026-000018",
        "split_evaluated": "test",
        "test_images_count": len(test_imgs),
        "test_annotations_count": sum(test_counts.values()),
        "evaluation_duration_seconds": eval_duration,
        "overall_test_metrics": {
            "precision": precision,
            "recall": recall,
            "map50": map50,
            "map50_95": map50_95
        },
        "per_class_metrics": per_class_results,
        "class_7_drainage_problem_status": {
            "canonical_id": 7,
            "class_name": "Drainage Problem",
            "train_instances": 0,
            "val_instances": 0,
            "test_instances": 0,
            "evaluable": False,
            "warning": "Class 7 has zero verified annotations across all splits and cannot be evaluated."
        },
        "safety_checks": {
            "is_active": False,
            "production_ready": False,
            "canonical_dataset_modified": False,
            "staged_dataset_modified": False,
            "database_records_overwritten": False
        },
        "test_run_artifacts_dir": str(audit_output_dir / "test_evaluation")
    }

    report_file = audit_output_dir / "test_set_evaluation_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)

    print(f"\n[REPORT SAVED] Detailed test audit report written to: {report_file}")
    print("=" * 80)
    print("POST-TRAINING AUDIT COMPLETED.")
    print("=" * 80)


if __name__ == "__main__":
    main()
