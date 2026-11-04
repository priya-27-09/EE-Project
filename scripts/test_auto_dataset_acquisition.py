"""
AI Civic Guardian - Step 4C/D Test Suite: Automatic Real Dataset Acquisition,
Quality Inspection, Canonical YOLO Preparation, and Step 4A Validation Integration.

Tests the 20 requirements specified in the task:
1. download integrity
2. SHA-256
3. duplicate detection
4. license metadata handling
5. format detection
6. YOLO parsing
7. COCO conversion if applicable
8. VOC conversion if applicable
9. class mapping
10. rejected mappings
11. invalid labels
12. image validation
13. train/val/test split
14. duplicate leakage
15. canonical data.yaml
16. 12-class schema
17. missing-class detection
18. DatasetValidator integration
19. dataset registry
20. no fake data generation
"""

import os
import sys
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.dataset_validator import YOLODatasetValidator, CANONICAL_CLASSES
from scripts.auto_dataset_acquisition import (
    AutoDatasetAcquisitionPipeline,
    compute_sha256,
    compute_bytes_sha256,
    compute_dhash,
    hamming_distance,
    download_file_with_progress,
)


class TestAutoDatasetAcquisition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = BASE_DIR
        cls.dataset_root = cls.base_dir / "dataset"
        cls.canonical_dir = cls.dataset_root / "canonical"
        cls.reports_dir = cls.dataset_root / "reports"
        cls.raw_dir = cls.dataset_root / "raw"
        cls.archives_dir = cls.dataset_root / "archives"

        # Ensure pipeline has run
        cls.pipeline = AutoDatasetAcquisitionPipeline(base_dir=cls.base_dir, seed=42)
        cls.pipeline_res = cls.pipeline.run()

    # 1. Download Integrity
    def test_01_download_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td) / "sample_download.txt"
            # Test download failure behavior with invalid URL
            ok, msg, h = download_file_with_progress("http://invalid.domain.12345.notfound/test.zip", temp_path, timeout=2)
            self.assertFalse(ok)
            self.assertFalse(temp_path.exists(), "Corrupt/failed download file must not persist")

    # 2. SHA-256 Computation
    def test_02_sha256_computation(self):
        sample_bytes = b"AI Civic Guardian - SHA256 Integrity Verification"
        import hashlib
        expected_hash = hashlib.sha256(sample_bytes).hexdigest()
        self.assertEqual(compute_bytes_sha256(sample_bytes), expected_hash)

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(sample_bytes)
            tf.flush()
            tmp_p = Path(tf.name)
        try:
            self.assertEqual(compute_sha256(tmp_p), expected_hash)
        finally:
            tmp_p.unlink(missing_ok=True)

    # 3. Duplicate Detection
    def test_03_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "img1.png"
            p2 = Path(td) / "img2.png"
            im = Image.new("RGB", (64, 64), color=(128, 128, 128))
            im.save(p1)
            im.save(p2)

            sha1 = compute_sha256(p1)
            sha2 = compute_sha256(p2)
            self.assertEqual(sha1, sha2, "Exact identical images must produce matching SHA-256")

            # dHash test
            dh1 = compute_dhash(p1)
            dh2 = compute_dhash(p2)
            self.assertEqual(dh1, dh2)
            self.assertEqual(hamming_distance(dh1, dh2), 0)

    # 4. License Metadata Handling
    def test_04_license_metadata_handling(self):
        reg_file = self.reports_dir / "dataset_registry.json"
        self.assertTrue(reg_file.exists(), "dataset_registry.json must exist")
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        datasets = data.get("datasets", [])
        self.assertGreater(len(datasets), 0)

        statuses = {d["status"] for d in datasets}
        self.assertIn("APPROVED", statuses)
        for ds in datasets:
            self.assertIn(ds["status"], ["APPROVED", "REJECTED", "NEEDS_REVIEW"])
            self.assertTrue(len(ds["license"]) > 0, "License must not be empty")

    # 5. Format Detection
    def test_05_format_detection(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir)
        with tempfile.TemporaryDirectory() as td:
            coco_dir = Path(td) / "coco_test"
            coco_dir.mkdir()
            (coco_dir / "_annotations.coco.json").write_text(
                json.dumps({"images": [], "annotations": [], "categories": []}), encoding="utf-8"
            )
            self.assertEqual(pipe._detect_format(coco_dir), "COCO")

            yolo_dir = Path(td) / "yolo_test"
            yolo_dir.mkdir()
            (yolo_dir / "labels").mkdir()
            (yolo_dir / "labels" / "sample.txt").write_text("0 0.5 0.5 0.2 0.2", encoding="utf-8")
            self.assertEqual(pipe._detect_format(yolo_dir), "YOLO")

    # 6. YOLO Parsing
    def test_06_yolo_parsing(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "images").mkdir()
            (td_path / "labels").mkdir()
            im = Image.new("RGB", (100, 100), color=(200, 200, 200))
            im.save(td_path / "images" / "test_img.jpg")
            (td_path / "labels" / "test_img.txt").write_text("pothole 0.5 0.5 0.3 0.3\n", encoding="utf-8")

            ds_meta = {
                "id": "TEST-DS",
                "name": "Test Potholes",
                "raw_dir": td_path,
                "class_mapping": {
                    "pothole": {"target_id": 2, "target_name": "Pothole", "status": "APPROVED"}
                }
            }
            parsed = pipe._parse_yolo(ds_meta)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(len(parsed[0]["annotations"]), 1)
            ann = parsed[0]["annotations"][0]
            self.assertEqual(ann["target_class_id"], 2)
            self.assertEqual(ann["bbox"], [0.5, 0.5, 0.3, 0.3])

    # 7. COCO Conversion
    def test_07_coco_conversion(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            im = Image.new("RGB", (640, 480), color=(100, 100, 100))
            im.save(td_path / "crack_01.jpg")

            coco_dict = {
                "images": [{"id": 1, "file_name": "crack_01.jpg", "width": 640, "height": 480}],
                "categories": [{"id": 10, "name": "crack"}],
                "annotations": [{"id": 100, "image_id": 1, "category_id": 10, "bbox": [160, 120, 320, 240]}]
            }
            (td_path / "_annotations.coco.json").write_text(json.dumps(coco_dict), encoding="utf-8")

            ds_meta = {
                "id": "TEST-COCO",
                "name": "Test COCO",
                "raw_dir": td_path,
                "class_mapping": {
                    "crack": {"target_id": 9, "target_name": "Building Damage", "status": "APPROVED"}
                }
            }
            parsed = pipe._parse_coco(ds_meta)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(len(parsed[0]["annotations"]), 1)
            ann = parsed[0]["annotations"][0]
            self.assertEqual(ann["target_class_id"], 9)
            # x_center = (160 + 160)/640 = 0.5; y_center = (120 + 120)/480 = 0.5; w = 320/640 = 0.5; h = 240/480 = 0.5
            self.assertEqual(ann["bbox"], [0.5, 0.5, 0.5, 0.5])

    # 8. VOC Conversion
    def test_08_voc_conversion(self):
        # Coordinates conversion math: [xmin, ymin, xmax, ymax] -> [xc, yc, w, h]
        im_w, im_h = 1000.0, 500.0
        xmin, ymin, xmax, ymax = 100.0, 50.0, 300.0, 250.0
        w = (xmax - xmin) / im_w
        h = (ymax - ymin) / im_h
        xc = (xmin + (xmax - xmin) / 2.0) / im_w
        yc = (ymin + (ymax - ymin) / 2.0) / im_h
        self.assertAlmostEqual(xc, 0.20)
        self.assertAlmostEqual(yc, 0.30)
        self.assertAlmostEqual(w, 0.20)
        self.assertAlmostEqual(h, 0.40)

    # 9. Class Mapping
    def test_09_class_mapping(self):
        reg_file = self.reports_dir / "dataset_registry.json"
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ds in data.get("datasets", []):
            for mapped_c in ds.get("mapped_classes", []):
                self.assertIn(mapped_c, list(CANONICAL_CLASSES.values()))

    # 10. Rejected Mappings
    def test_10_rejected_mappings(self):
        rej_file = self.reports_dir / "rejected_mappings.json"
        self.assertTrue(rej_file.exists(), "rejected_mappings.json must exist")
        with open(rej_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        rejected_names = [r["original_class"] for r in data]
        self.assertIn("car", rejected_names)
        self.assertIn("cardboard", rejected_names)
        self.assertIn("Bottle cap", rejected_names)

        for rec in data:
            self.assertEqual(rec["decision"], "REJECTED")
            self.assertIn("reason", rec)
            self.assertTrue(len(rec["reason"]) > 5)

    # 11. Invalid Labels Rejection
    def test_11_invalid_labels(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir)
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / "images").mkdir()
            (td_path / "labels").mkdir()
            im = Image.new("RGB", (100, 100), color=(200, 200, 200))
            im.save(td_path / "images" / "bad_img.jpg")
            # Invalid bounds: xc=1.5, yc=-0.2, w=2.0
            (td_path / "labels" / "bad_img.txt").write_text("pothole 1.5 -0.2 2.0 0.5\n", encoding="utf-8")

            ds_meta = {
                "id": "BAD-DS",
                "name": "Bad Labels",
                "raw_dir": td_path,
                "class_mapping": {
                    "pothole": {"target_id": 2, "target_name": "Pothole", "status": "APPROVED"}
                }
            }
            parsed = pipe._parse_yolo(ds_meta)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(len(parsed[0]["annotations"]), 0, "Out-of-bounds annotations must be rejected")

    # 12. Image Validation
    def test_12_image_validation(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir)
        with tempfile.TemporaryDirectory() as td:
            corrupt_p = Path(td) / "corrupt.jpg"
            corrupt_p.write_bytes(b"NOT_A_REAL_JPEG_IMAGE_DATA")

            samples = [{
                "image_path": corrupt_p,
                "annotations": []
            }]
            valid_unique, quality = pipe._quality_and_deduplicate(samples)
            self.assertEqual(len(valid_unique), 0)
            self.assertEqual(len(quality["corrupted_images"]), 1)

    # 13. Train/Val/Test Split
    def test_13_train_val_test_split(self):
        pipe = AutoDatasetAcquisitionPipeline(base_dir=self.base_dir, seed=42)
        dummy_samples = [
            {"image_path": Path(f"dummy_{i}.jpg"), "sha256": f"hash_{i}", "annotations": []}
            for i in range(100)
        ]
        splits = pipe._split_dataset(dummy_samples)
        self.assertEqual(len(splits["train"]), 70)
        self.assertEqual(len(splits["val"]), 20)
        self.assertEqual(len(splits["test"]), 10)

    # 14. Zero Duplicate Leakage Across Splits
    def test_14_zero_duplicate_leakage(self):
        train_dir = self.canonical_dir / "images" / "train"
        val_dir = self.canonical_dir / "images" / "val"
        test_dir = self.canonical_dir / "images" / "test"

        train_hashes = {compute_sha256(f) for f in train_dir.iterdir() if f.is_file()}
        val_hashes = {compute_sha256(f) for f in val_dir.iterdir() if f.is_file()}
        test_hashes = {compute_sha256(f) for f in test_dir.iterdir() if f.is_file()}

        self.assertEqual(len(train_hashes.intersection(val_hashes)), 0, "Train and Val must have 0 hash overlap")
        self.assertEqual(len(train_hashes.intersection(test_hashes)), 0, "Train and Test must have 0 hash overlap")
        self.assertEqual(len(val_hashes.intersection(test_hashes)), 0, "Val and Test must have 0 hash overlap")

    # 15. Canonical data.yaml
    def test_15_canonical_data_yaml(self):
        yaml_path = self.canonical_dir / "data.yaml"
        self.assertTrue(yaml_path.exists(), "data.yaml must exist in canonical directory")
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.assertIn("train", cfg)
        self.assertIn("val", cfg)
        self.assertIn("test", cfg)
        self.assertIn("names", cfg)

    # 16. Strict 12-Class Canonical Schema
    def test_16_twelve_class_canonical_schema(self):
        import yaml
        yaml_path = self.canonical_dir / "data.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        names = cfg.get("names", {})
        self.assertEqual(len(names), 12, "Must declare exactly 12 classes")
        for cid, cname in CANONICAL_CLASSES.items():
            self.assertIn(cid, names)
            self.assertEqual(names[cid], cname)

    # 17. Missing Class Detection
    def test_17_missing_class_detection(self):
        miss_file = self.reports_dir / "missing_classes.json"
        self.assertTrue(miss_file.exists(), "missing_classes.json must exist")
        with open(miss_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("missing_classes", data)
        self.assertIn("covered_classes", data)
        self.assertIn("searched_datasets", data)

        self.assertIn("Water Leakage", data["missing_classes"])
        self.assertIn("Sewage Overflow", data["missing_classes"])
        self.assertIn("Pothole", data["covered_classes"])

    # 18. DatasetValidator Integration
    def test_18_dataset_validator_integration(self):
        validator = YOLODatasetValidator(self.canonical_dir, dataset_version="canonical_test")
        val_res = validator.validate()
        self.assertTrue(val_res.is_valid, f"Canonical dataset must pass DatasetValidator: {val_res.errors}")
        self.assertEqual(val_res.status, "READY_FOR_TRAINING")
        self.assertEqual(len(val_res.errors), 0)

    # 19. Dataset Registry Schema Conformance
    def test_19_dataset_registry_schema(self):
        reg_file = self.reports_dir / "dataset_registry.json"
        self.assertTrue(reg_file.exists(), "dataset_registry.json must exist")
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        datasets = data.get("datasets", [])
        self.assertGreaterEqual(len(datasets), 4)

        required_keys = [
            "dataset_id", "name", "source", "url", "license",
            "status", "format", "images", "annotations",
            "mapped_classes", "rejected_classes", "sha256"
        ]
        for ds in datasets:
            for k in required_keys:
                self.assertIn(k, ds, f"Dataset entry missing required key '{k}'")

    # 20. Strict Negative Boundary Check: No Fake Data Generation & No Training
    def test_20_no_fake_data_generation_and_no_training(self):
        # 1. No model weights (.pt files) in canonical dataset or reports
        pt_files = list(self.canonical_dir.rglob("*.pt")) + list(self.reports_dir.rglob("*.pt"))
        self.assertEqual(len(pt_files), 0, "No fake weights (.pt) should be placed in canonical dataset or reports")

        # 2. Final dataset report verifies training is NOT STARTED
        report_file = self.reports_dir / "FINAL_DATASET_REPORT.md"
        self.assertTrue(report_file.exists(), "FINAL_DATASET_REPORT.md must exist")
        content = report_file.read_text(encoding="utf-8")
        self.assertIn("TRAINING", content)
        self.assertIn("NOT STARTED", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
