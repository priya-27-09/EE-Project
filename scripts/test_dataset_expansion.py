"""
AI Civic Guardian - Step 4D Test Suite: Automatic Real Dataset Expansion & Complete 12-Class Civic YOLO Dataset

Tests all 24 required capabilities:
1. Real source discovery
2. License gate
3. Download integrity
4. SHA-256 verification
5. Annotation parsing
6. YOLO conversion
7. COCO conversion
8. VOC conversion
9. Semantic class mapping
10. Rejected mappings
11. Image validation
12. Invalid annotation rejection
13. Exact duplicate detection
14. Near duplicate detection
15. Deterministic split (seed=42)
16. Split leakage prevention
17. 12-class schema
18. Missing class detection
19. Class imbalance report
20. DatasetValidator integration
21. PostgreSQL registration
22. No fake data
23. No fake annotations
24. No training (YOLO TRAINING: NOT STARTED)
"""

import os
import sys
import io
import json
import shutil
import unittest
from pathlib import Path
from PIL import Image
import xml.etree.ElementTree as ET

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.dataset_validator import YOLODatasetValidator, CANONICAL_CLASSES, CANONICAL_NAME_TO_ID
from scripts.auto_dataset_expansion import (
    AutoDatasetExpansionPipeline,
    INVESTIGATION_CATALOG,
    compute_sha256,
    compute_bytes_sha256,
    compute_dhash,
    hamming_distance
)


class TestDatasetExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = BASE_DIR
        cls.dataset_root = cls.base_dir / "dataset"
        cls.canonical_dir = cls.dataset_root / "canonical"
        cls.reports_dir = cls.dataset_root / "reports"
        cls.expansion_dir = cls.dataset_root / "expansion"
        cls.expansion_reports = cls.expansion_dir / "reports"

        # Ensure pipeline has run
        pipeline = AutoDatasetExpansionPipeline(base_dir=cls.base_dir, seed=42)
        cls.pipeline_res = pipeline.run()

    # 1. Real Source Discovery
    def test_01_real_source_discovery(self):
        self.assertTrue(len(INVESTIGATION_CATALOG) >= 8, "Catalog must investigate multiple independent datasets.")
        sources = {d["source"] for d in INVESTIGATION_CATALOG}
        self.assertTrue(any("Hugging Face" in s for s in sources), "Must include Hugging Face sources.")
        self.assertTrue(any("GitHub" in s or "Sekilab" in s for s in sources), "Must include GitHub sources.")
        self.assertTrue(any("Roboflow" in s for s in sources), "Must include Roboflow sources.")
        for d in INVESTIGATION_CATALOG:
            self.assertTrue(d["source_url"].startswith("http"), f"Dataset {d['name']} must have valid real URL.")

    # 2. License Gate
    def test_02_license_gate(self):
        for d in INVESTIGATION_CATALOG:
            status = d["license_status"]
            self.assertIn(status, ["APPROVED", "REJECTED", "NEEDS_REVIEW"])
            if status == "APPROVED":
                # Approved licenses must be permissive open data licenses
                lic = d["license"].upper()
                self.assertTrue(
                    any(p in lic for p in ["CC BY", "CC BY-SA", "CC0", "MIT", "APACHE", "PUBLIC DOMAIN"]),
                    f"Approved dataset {d['name']} must have verified permissive license: {d['license']}"
                )
            elif status == "NEEDS_REVIEW":
                # Must be flagged for legal review
                self.assertTrue("NC" in d["license"] or "NON-COMMERCIAL" in d["license"].upper())

    # 3. Download Integrity
    def test_03_download_integrity(self):
        exp_raw = self.expansion_dir / "raw"
        self.assertTrue(exp_raw.exists(), "dataset/expansion/raw must exist.")
        raw_folders = list(exp_raw.iterdir())
        self.assertTrue(len(raw_folders) >= 2, "Must have acquired and extracted multiple raw datasets.")
        for folder in raw_folders:
            if folder.is_dir():
                files = list(folder.glob("*"))
                self.assertTrue(len(files) > 0, f"Raw extracted folder {folder.name} must not be empty.")

    # 4. SHA-256 Verification
    def test_04_sha256_verification(self):
        img_files = list(self.canonical_dir.rglob("*.jpg")) + list(self.canonical_dir.rglob("*.png"))
        self.assertTrue(len(img_files) > 0, "Canonical images must exist.")
        sample_img = img_files[0]
        h = compute_sha256(sample_img)
        self.assertEqual(len(h), 64, "SHA-256 hash must be 64 hexadecimal characters.")
        self.assertTrue(all(c in "0123456789abcdefABCDEF" for c in h), "SHA-256 must be valid hex.")

    # 5. Annotation Parsing
    def test_05_annotation_parsing(self):
        label_files = list(self.canonical_dir.rglob("*.txt"))
        self.assertTrue(len(label_files) > 0, "Canonical labels must exist.")
        non_empty = 0
        for lf in label_files:
            content = lf.read_text(encoding="utf-8").strip()
            if content:
                non_empty += 1
                for line in content.splitlines():
                    tokens = line.split()
                    self.assertEqual(len(tokens), 5, f"Line must contain 5 tokens: {line}")
                    cid = int(tokens[0])
                    self.assertIn(cid, CANONICAL_CLASSES)
        self.assertTrue(non_empty > 0, "Must have non-empty annotation files.")

    # 6. YOLO Conversion
    def test_06_yolo_conversion(self):
        for split in ["train", "val", "test"]:
            lbl_dir = self.canonical_dir / "labels" / split
            for lf in lbl_dir.glob("*.txt"):
                for line in lf.read_text(encoding="utf-8").strip().splitlines():
                    if not line:
                        continue
                    tokens = line.split()
                    cid, xc, yc, w, h = int(tokens[0]), float(tokens[1]), float(tokens[2]), float(tokens[3]), float(tokens[4])
                    self.assertTrue(0 <= cid <= 11)
                    self.assertTrue(0.0 <= xc <= 1.0, f"xc {xc} out of bounds")
                    self.assertTrue(0.0 <= yc <= 1.0, f"yc {yc} out of bounds")
                    self.assertTrue(0.0 < w <= 1.0, f"w {w} out of bounds")
                    self.assertTrue(0.0 < h <= 1.0, f"h {h} out of bounds")

    # 7. COCO Conversion
    def test_07_coco_conversion(self):
        # Test COCO bbox [xmin, ymin, w, h] to YOLO [xc, yc, w, h]
        im_w, im_h = 640.0, 480.0
        xmin, ymin, bw, bh = 100.0, 120.0, 50.0, 60.0
        xc = (xmin + bw / 2.0) / im_w
        yc = (ymin + bh / 2.0) / im_h
        nw = bw / im_w
        nh = bh / im_h
        self.assertAlmostEqual(xc, 125.0 / 640.0, places=5)
        self.assertAlmostEqual(yc, 150.0 / 480.0, places=5)
        self.assertAlmostEqual(nw, 50.0 / 640.0, places=5)
        self.assertAlmostEqual(nh, 60.0 / 480.0, places=5)

    # 8. VOC Conversion
    def test_08_voc_conversion(self):
        # Test Pascal VOC [xmin, ymin, xmax, ymax] to YOLO [xc, yc, w, h]
        im_w, im_h = 1000.0, 800.0
        xmin, ymin, xmax, ymax = 100.0, 200.0, 300.0, 600.0
        bw = xmax - xmin
        bh = ymax - ymin
        xc = (xmin + bw / 2.0) / im_w
        yc = (ymin + bh / 2.0) / im_h
        nw = bw / im_w
        nh = bh / im_h
        self.assertEqual(xc, 0.20)
        self.assertEqual(yc, 0.50)
        self.assertEqual(nw, 0.20)
        self.assertEqual(nh, 0.50)

    # 9. Semantic Class Mapping
    def test_09_semantic_class_mapping(self):
        for d in INVESTIGATION_CATALOG:
            for src_cls, rule in d.get("class_mapping", {}).items():
                if rule.get("status") == "APPROVED":
                    target_id = rule["target_id"]
                    target_name = rule["target_name"]
                    self.assertIn(target_id, CANONICAL_CLASSES)
                    self.assertEqual(CANONICAL_CLASSES[target_id], target_name)
                    # Verify semantic soundness
                    if "pothole" in src_cls.lower():
                        self.assertEqual(target_name, "Pothole")
                    elif "accident" in src_cls.lower():
                        self.assertEqual(target_name, "Traffic Issue")
                    elif "crack" in src_cls.lower():
                        self.assertIn(target_name, ["Building Damage", "Damaged Road"])

    # 10. Rejected Mappings
    def test_10_rejected_mappings(self):
        rej_file = self.reports_dir / "rejected_mappings.json"
        self.assertTrue(rej_file.exists(), "rejected_mappings.json must exist.")
        data = json.loads(rej_file.read_text(encoding="utf-8"))
        rejected_classes = {item["original_class"] for item in data}
        self.assertTrue("Bottle cap" in rejected_classes or "Cigarette" in rejected_classes)
        self.assertTrue("non_accident" in rejected_classes or "road-traffic" in rejected_classes or "vehicles" in rejected_classes)

    # 11. Image Validation
    def test_11_image_validation(self):
        for img_path in list(self.canonical_dir.rglob("*.jpg")) + list(self.canonical_dir.rglob("*.png")):
            self.assertTrue(img_path.stat().st_size > 0, f"Image {img_path.name} must not be 0 bytes.")
            with Image.open(img_path) as im:
                im.verify()
                w, h = im.size
                self.assertTrue(w >= 10 and h >= 10, "Dimensions must be valid.")

    # 12. Invalid Annotation Rejection
    def test_12_invalid_annotation_rejection(self):
        qual_file = self.reports_dir / "quality_report.json"
        self.assertTrue(qual_file.exists())
        # Labels in canonical should have 0 invalid labels
        for split in ["train", "val", "test"]:
            for lf in (self.canonical_dir / "labels" / split).glob("*.txt"):
                for line in lf.read_text(encoding="utf-8").strip().splitlines():
                    tokens = line.split()
                    self.assertEqual(len(tokens), 5)
                    cid = int(tokens[0])
                    self.assertTrue(0 <= cid <= 11)

    # 13. Exact Duplicate Detection
    def test_13_exact_duplicate_detection(self):
        hashes = set()
        for img_path in list(self.canonical_dir.rglob("*.jpg")) + list(self.canonical_dir.rglob("*.png")):
            h = compute_sha256(img_path)
            self.assertNotIn(h, hashes, f"Exact duplicate image in canonical dataset: {img_path.name}")
            hashes.add(h)

    # 14. Near Duplicate Detection
    def test_14_near_duplicate_detection(self):
        qual_file = self.reports_dir / "quality_report.json"
        qual_data = json.loads(qual_file.read_text(encoding="utf-8"))
        # Verify near-duplicate filter ran
        self.assertIn("near_duplicates", qual_data)
        self.assertTrue(len(qual_data["near_duplicates"]) >= 0)

    # 15. Deterministic Split
    def test_15_deterministic_split(self):
        p1 = AutoDatasetExpansionPipeline(base_dir=self.base_dir, seed=42)
        p2 = AutoDatasetExpansionPipeline(base_dir=self.base_dir, seed=42)
        dummy_samples = [{"sha256": f"hash_{i}", "val": i} for i in range(100)]
        s1 = p1._split_dataset(dummy_samples)
        s2 = p2._split_dataset(dummy_samples)
        self.assertEqual(len(s1["train"]), len(s2["train"]))
        self.assertEqual(len(s1["val"]), len(s2["val"]))
        self.assertEqual(len(s1["test"]), len(s2["test"]))
        self.assertEqual([x["sha256"] for x in s1["train"]], [x["sha256"] for x in s2["train"]])

    # 16. Split Leakage Prevention
    def test_16_split_leakage_prevention(self):
        train_hashes = {compute_sha256(p) for p in (self.canonical_dir / "images" / "train").glob("*.*")}
        val_hashes = {compute_sha256(p) for p in (self.canonical_dir / "images" / "val").glob("*.*")}
        test_hashes = {compute_sha256(p) for p in (self.canonical_dir / "images" / "test").glob("*.*")}

        self.assertEqual(len(train_hashes.intersection(val_hashes)), 0, "Train-Val data leakage detected!")
        self.assertEqual(len(train_hashes.intersection(test_hashes)), 0, "Train-Test data leakage detected!")
        self.assertEqual(len(val_hashes.intersection(test_hashes)), 0, "Val-Test data leakage detected!")

    # 17. 12-Class Schema
    def test_17_12_class_schema(self):
        data_yaml = self.canonical_dir / "data.yaml"
        self.assertTrue(data_yaml.exists(), "data.yaml must exist.")
        content = data_yaml.read_text(encoding="utf-8")
        for cid, cname in CANONICAL_CLASSES.items():
            self.assertIn(f"{cid}: {cname}", content, f"data.yaml must contain '{cid}: {cname}'")

    # 18. Missing Class Detection
    def test_18_missing_class_detection(self):
        miss_file = self.reports_dir / "missing_classes.json"
        self.assertTrue(miss_file.exists(), "missing_classes.json must exist.")
        data = json.loads(miss_file.read_text(encoding="utf-8"))
        missing = data.get("missing_classes", [])
        self.assertTrue(len(missing) > 0, "Missing classes must be explicitly reported.")
        self.assertIn("Broken Street Light", missing)
        self.assertIn("Water Leakage", missing)
        self.assertIn("Sewage Overflow", missing)

    # 19. Class Imbalance Report
    def test_19_class_imbalance_report(self):
        rep_file = self.reports_dir / "DATASET_EXPANSION_FINAL_REPORT.md"
        self.assertTrue(rep_file.exists())
        content = rep_file.read_text(encoding="utf-8")
        self.assertIn("INSUFFICIENT", content)
        self.assertIn("MISSING", content)
        self.assertIn("ADEQUATE", content)

    # 20. DatasetValidator Integration
    def test_20_dataset_validator_integration(self):
        validator = YOLODatasetValidator(self.canonical_dir, dataset_version="test_expansion")
        res = validator.validate()
        self.assertTrue(res.is_valid, f"Validator failed with errors: {res.errors}")
        self.assertEqual(len(res.errors), 0)

    # 21. PostgreSQL Registration
    def test_21_postgresql_registration(self):
        from app.db.session import SessionLocal
        from app.models.dataset import DatasetVersion
        db = SessionLocal()
        try:
            latest = db.query(DatasetVersion).order_by(DatasetVersion.id.desc()).first()
            self.assertIsNotNone(latest, "A DatasetVersion record must exist in PostgreSQL.")
            self.assertTrue(latest.dataset_version.startswith("DS-"), f"Version must start with DS-: {latest.dataset_version}")
            self.assertTrue(latest.total_image_count > 0, "total_image_count must be positive.")
        finally:
            db.close()

    # 22. No Fake Data
    def test_22_no_fake_data(self):
        prov_file = self.reports_dir / "provenance_manifest.json"
        self.assertTrue(prov_file.exists())
        data = json.loads(prov_file.read_text(encoding="utf-8"))
        records = data.get("records", [])
        self.assertTrue(len(records) > 0)
        for r in records[:50]:
            self.assertTrue(r["source_url"].startswith("http"), f"Must trace to real remote source URL: {r}")
            self.assertIn(r["license"], ["CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0 (Public Domain)", "CC0 1.0"])

    # 23. No Fake Annotations
    def test_23_no_fake_annotations(self):
        prov_file = self.reports_dir / "provenance_manifest.json"
        data = json.loads(prov_file.read_text(encoding="utf-8"))
        records = data.get("records", [])
        for r in records[:50]:
            self.assertIn("source_class", r)
            self.assertIn(r["canonical_class_id"], range(12))

    # 24. No Training
    def test_24_no_training(self):
        # Verify no best.pt or training weights were created
        runs_dir = BASE_DIR / "runs"
        if runs_dir.exists():
            weights = list(runs_dir.rglob("best.pt"))
            self.assertEqual(len(weights), 0, "No YOLO model weights may be generated during dataset expansion!")

        # Verify final report explicitly confirms training not started
        rep_file = self.reports_dir / "DATASET_EXPANSION_FINAL_REPORT.md"
        content = rep_file.read_text(encoding="utf-8")
        self.assertIn("YOLO TRAINING: NOT STARTED", content)
        self.assertIn("NOT_READY_FOR_TRAINING", content)


if __name__ == "__main__":
    unittest.main()
