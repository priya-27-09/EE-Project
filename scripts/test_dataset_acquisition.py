"""
AI Civic Guardian - Step 4C Test Suite: Real Civic Dataset Acquisition, License Audit,
Normalization, Deduplication, and Quality Gate Preparation.

Tests 21 critical requirements:
1. Registry JSON exists and is valid
2. Registry defines canonical 12 classes
3. Registry contains at least 3 distinct open datasets
4. License audit document exists with legal and suitability analysis
5. Permissive open licenses are approved (CC BY 4.0, CC BY-SA 4.0)
6. Commercial/restrictive licenses are flagged as REVIEW_REQUIRED or REJECTED
7. Class mapping JSON exists and is valid
8. Micro-litter classes are explicitly rejected
9. Satellite perspective and general vehicles are rejected as unsuitable
10. Raw sources directories contain valid manifest.json files
11. Raw manifests track provenance, source URL, publisher, license, and SHA-256
12. Dataset preparation pipeline generates data.yaml
13. data.yaml has exactly 12 classes in canonical order
14. All bounding box coordinates are normalized in [0, 1]
15. SHA-256 duplicate detection accurately identifies identical images
16. Deterministic 70/20/10 split with seed=42 is reproducible
17. Zero data leakage across train, val, and test splits
18. Provenance report traces every processed sample to its source and license
19. Class distribution report honestly documents covered vs missing classes
20. Custom data acquisition strategy documents municipal collection guidelines
21. Quality gate passes via Step 4A validator with zero fake training or fake weights
"""

import sys
import os
import json
import shutil
import unittest
from pathlib import Path
from PIL import Image

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.dataset_validator import YOLODatasetValidator, CANONICAL_CLASSES
from scripts.prepare_civic_dataset import CivicDatasetPreparer, compute_sha256, compute_dhash


class TestCivicDatasetAcquisition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_dir = BASE_DIR
        cls.sources_dir = cls.base_dir / "data" / "sources"
        cls.raw_dir = cls.base_dir / "data" / "raw"
        cls.processed_dir = cls.base_dir / "data" / "processed" / "civic_yolo"
        cls.reports_dir = cls.base_dir / "data" / "reports"

        # Ensure pipeline has run
        preparer = CivicDatasetPreparer(base_dir=cls.base_dir, seed=42)
        cls.pipeline_res = preparer.run(validate_gate=True)

    # Test 1: Registry JSON exists and parses cleanly
    def test_01_registry_json_exists_and_valid(self):
        reg_file = self.sources_dir / "dataset_registry.json"
        self.assertTrue(reg_file.exists(), "dataset_registry.json must exist")
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("registry_version", data)
        self.assertIn("datasets", data)
        self.assertIsInstance(data["datasets"], list)

    # Test 2: Registry defines canonical 12 classes
    def test_02_registry_defines_canonical_12_classes(self):
        reg_file = self.sources_dir / "dataset_registry.json"
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        target_classes = data.get("target_classes", [])
        self.assertEqual(len(target_classes), 12, "Must define exactly 12 target classes")
        for item in target_classes:
            cid = item["id"]
            cname = item["name"]
            self.assertIn(cid, CANONICAL_CLASSES)
            self.assertEqual(cname, CANONICAL_CLASSES[cid])

    # Test 3: Registry contains at least 3 distinct open datasets
    def test_03_registry_contains_at_least_3_open_datasets(self):
        reg_file = self.sources_dir / "dataset_registry.json"
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        datasets = data.get("datasets", [])
        self.assertGreaterEqual(len(datasets), 3, "Registry must contain at least 3 datasets")
        for ds in datasets:
            self.assertTrue(ds["id"].startswith("DATASET-"))
            self.assertTrue(len(ds["name"]) > 5)
            self.assertTrue(ds["source_url"].startswith("http"))
            self.assertIn("license", ds)
            self.assertIn("license_status", ds)

    # Test 4: License audit document exists with legal and suitability analysis
    def test_04_license_audit_document_exists(self):
        audit_file = self.sources_dir / "license_audit.md"
        self.assertTrue(audit_file.exists(), "license_audit.md must exist")
        content = audit_file.read_text(encoding="utf-8")
        self.assertTrue("License" in content and "Audit" in content)
        self.assertIn("APPROVED_WITH_ATTRIBUTION", content)
        self.assertIn("REJECTED", content)
        self.assertIn("Commercial", content)
        self.assertIn("Attribution", content)

    # Test 5: Permissive open licenses are approved (CC BY 4.0, CC BY-SA 4.0)
    def test_05_permissive_licenses_approved(self):
        reg_file = self.sources_dir / "dataset_registry.json"
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        approved = [
            d for d in data["datasets"]
            if d.get("license_status") == "APPROVED_WITH_ATTRIBUTION"
        ]
        self.assertGreaterEqual(len(approved), 3, "Must approve at least 3 open licensed datasets")
        for d in approved:
            self.assertTrue(
                "CC BY" in d["license"] or "CC0" in d["license"],
                f"Approved dataset {d['id']} must have open CC license, got {d['license']}",
            )

    # Test 6: Commercial/restrictive licenses are flagged as REVIEW_REQUIRED or REJECTED
    def test_06_commercial_restrictive_licenses_flagged(self):
        reg_file = self.sources_dir / "dataset_registry.json"
        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        non_approved = [
            d for d in data["datasets"]
            if d.get("license_status") != "APPROVED_WITH_ATTRIBUTION"
        ]
        self.assertGreaterEqual(len(non_approved), 2, "Must audit non-commercial/incompatible candidates")
        for d in non_approved:
            self.assertIn(d["license_status"], ["REVIEW_REQUIRED", "REJECTED"])

    # Test 7: Class mapping JSON exists and is valid
    def test_07_class_mapping_json_exists_and_valid(self):
        cm_file = self.sources_dir / "class_mapping.json"
        self.assertTrue(cm_file.exists(), "class_mapping.json must exist")
        with open(cm_file, "r", encoding="utf-8") as f:
            mappings = json.load(f).get("mappings", {})
        self.assertIn("DATASET-001", mappings)
        self.assertIn("DATASET-002", mappings)
        self.assertIn("DATASET-003", mappings)

    # Test 8: Micro-litter classes are explicitly rejected
    def test_08_micro_litter_classes_explicitly_rejected(self):
        cm_file = self.sources_dir / "class_mapping.json"
        with open(cm_file, "r", encoding="utf-8") as f:
            mappings = json.load(f).get("mappings", {})
        ds3_rules = mappings.get("DATASET-003", [])
        rejected_classes = [
            r["source_class"].lower() for r in ds3_rules if r.get("review_status") == "REJECTED"
        ]
        self.assertTrue(
            any("bottle cap" in c or "cap" in c for c in rejected_classes),
            "Micro-litter like bottle cap must be explicitly rejected",
        )
        self.assertTrue(
            any("cigarette" in c for c in rejected_classes),
            "Micro-litter like cigarette butt must be explicitly rejected",
        )

    # Test 9: Satellite perspective and general vehicles are rejected as unsuitable
    def test_09_satellite_and_car_classes_rejected(self):
        cm_file = self.sources_dir / "class_mapping.json"
        with open(cm_file, "r", encoding="utf-8") as f:
            mappings = json.load(f).get("mappings", {})
        # xBD Satellite perspective rejected
        ds4_rules = mappings.get("DATASET-004", [])
        self.assertTrue(
            any(r.get("review_status") == "REJECTED" for r in ds4_rules),
            "Satellite damage dataset (xBD) must be rejected for perspective mismatch",
        )
        # Ordinary moving cars in Cityscapes rejected
        ds5_rules = mappings.get("DATASET-005", [])
        self.assertTrue(
            any(r.get("review_status") == "REJECTED" for r in ds5_rules),
            "General moving vehicles must be rejected from Traffic Issue class",
        )

    # Test 10: Raw sources directories contain valid manifest.json files
    def test_10_raw_sources_manifests_exist(self):
        approved_ids = ["DATASET-001", "DATASET-002", "DATASET-003"]
        for ds_id in approved_ids:
            manifest_file = self.raw_dir / ds_id / "manifest.json"
            self.assertTrue(manifest_file.exists(), f"Manifest must exist for {ds_id}")
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["source_dataset_id"], ds_id)
            self.assertGreater(data["image_count"], 0)

    # Test 11: Raw manifests track provenance, source URL, publisher, license, and SHA-256
    def test_11_manifests_track_provenance(self):
        approved_ids = ["DATASET-001", "DATASET-002", "DATASET-003"]
        for ds_id in approved_ids:
            manifest_file = self.raw_dir / ds_id / "manifest.json"
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("source_url", data)
            self.assertIn("publisher", data)
            self.assertIn("license", data)
            self.assertIn("archive_sha256", data)
            self.assertIn("download_date", data)
            self.assertEqual(len(data["archive_sha256"]), 64)

    # Test 12: Dataset preparation pipeline generates data.yaml
    def test_12_preparation_script_generates_data_yaml(self):
        yaml_file = self.processed_dir / "data.yaml"
        self.assertTrue(yaml_file.exists(), "data.yaml must be generated at processed root")
        content = yaml_file.read_text(encoding="utf-8")
        self.assertIn("train: images/train", content)
        self.assertIn("val: images/val", content)
        self.assertIn("test: images/test", content)
        self.assertIn("nc: 12", content)

    # Test 13: data.yaml has exactly 12 classes in canonical order
    def test_13_data_yaml_strictly_12_canonical_classes(self):
        yaml_file = self.processed_dir / "data.yaml"
        content = yaml_file.read_text(encoding="utf-8")
        for cid, cname in CANONICAL_CLASSES.items():
            self.assertIn(f"{cid}: {cname}", content)

    # Test 14: All bounding box coordinates are normalized in [0, 1]
    def test_14_bounding_box_coordinates_strictly_normalized(self):
        labels_dir = self.processed_dir / "labels"
        total_boxes = 0
        for split in ["train", "val", "test"]:
            split_lbl_dir = labels_dir / split
            self.assertTrue(split_lbl_dir.exists())
            for lbl_file in split_lbl_dir.glob("*.txt"):
                lines = lbl_file.read_text(encoding="utf-8").strip().splitlines()
                for line in lines:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    self.assertEqual(len(parts), 5, f"Label in {lbl_file.name} must have 5 tokens")
                    cid = int(parts[0])
                    xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    self.assertIn(cid, range(12))
                    self.assertTrue(0.0 <= xc <= 1.0, f"xc {xc} outside [0, 1] in {lbl_file.name}")
                    self.assertTrue(0.0 <= yc <= 1.0, f"yc {yc} outside [0, 1] in {lbl_file.name}")
                    self.assertTrue(0.0 < w <= 1.0, f"w {w} invalid in {lbl_file.name}")
                    self.assertTrue(0.0 < h <= 1.0, f"h {h} invalid in {lbl_file.name}")
                    total_boxes += 1
        self.assertGreater(total_boxes, 0, "Processed dataset must contain valid bounding boxes")

    # Test 15: SHA-256 duplicate detection accurately identifies identical images
    def test_15_duplicate_detection_logic(self):
        dup_file = self.reports_dir / "duplicates.json"
        self.assertTrue(dup_file.exists(), "duplicates.json report must exist")
        with open(dup_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("total_images_analyzed", data)
        self.assertIn("exact_duplicates_found", data)
        self.assertIn("near_duplicates_found", data)
        self.assertIn("deduplication_policy", data)
        self.assertEqual(data["total_images_analyzed"], 8)

        # Test deduplication on synthetic duplicate pair in temporary directory
        temp_img1 = self.base_dir / "data" / "scratch_dup1.jpg"
        temp_img2 = self.base_dir / "data" / "scratch_dup2.jpg"
        try:
            im = Image.new("RGB", (64, 64), color=(100, 100, 100))
            im.save(temp_img1)
            im.save(temp_img2)
            sha1 = compute_sha256(temp_img1)
            sha2 = compute_sha256(temp_img2)
            self.assertEqual(sha1, sha2, "Identical images must yield matching SHA-256")
        finally:
            if temp_img1.exists():
                temp_img1.unlink()
            if temp_img2.exists():
                temp_img2.unlink()

    # Test 16: Deterministic 70/20/10 split with seed=42 is reproducible
    def test_16_deterministic_split_with_seed(self):
        preparer_a = CivicDatasetPreparer(base_dir=self.base_dir, seed=42)
        preparer_b = CivicDatasetPreparer(base_dir=self.base_dir, seed=42)
        # Running with same seed must yield same split image counts
        res_a = preparer_a.run(validate_gate=False)
        res_b = preparer_b.run(validate_gate=False)
        self.assertEqual(res_a["split_counts"], res_b["split_counts"])
        self.assertEqual(res_a["split_counts"]["train"], 5)
        self.assertEqual(res_a["split_counts"]["val"], 2)
        self.assertEqual(res_a["split_counts"]["test"], 1)

    # Test 17: Zero data leakage across train, val, and test splits
    def test_17_zero_data_leakage_across_splits(self):
        train_imgs = {f.name for f in (self.processed_dir / "images" / "train").glob("*.jpg")}
        val_imgs = {f.name for f in (self.processed_dir / "images" / "val").glob("*.jpg")}
        test_imgs = {f.name for f in (self.processed_dir / "images" / "test").glob("*.jpg")}

        # Ensure non-empty splits
        self.assertGreater(len(train_imgs), 0, "Train split must have images")
        self.assertGreater(len(val_imgs), 0, "Val split must have images")
        self.assertGreater(len(test_imgs), 0, "Test split must have images")

        # Zero leakage assertion
        self.assertEqual(len(train_imgs.intersection(val_imgs)), 0, "Train and Val must not overlap")
        self.assertEqual(len(train_imgs.intersection(test_imgs)), 0, "Train and Test must not overlap")
        self.assertEqual(len(val_imgs.intersection(test_imgs)), 0, "Val and Test must not overlap")

    # Test 18: Provenance report traces every processed sample to its source and license
    def test_18_provenance_report_traces_every_sample(self):
        prov_file = self.reports_dir / "provenance.json"
        self.assertTrue(prov_file.exists(), "provenance.json must exist")
        with open(prov_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data.get("records", [])
        self.assertEqual(len(records), 8, "Must trace all 8 processed images")
        for rec in records:
            self.assertIn("processed_image_name", rec)
            self.assertIn("source_dataset_id", rec)
            self.assertIn("original_filename", rec)
            self.assertIn("license", rec)
            self.assertIn("attribution", rec)
            self.assertIn("sha256", rec)
            self.assertIn("split", rec)
            self.assertIn(rec["split"], ["train", "val", "test"])

    # Test 19: Class distribution report honestly documents covered vs missing classes
    def test_19_class_distribution_report_identifies_gaps(self):
        dist_file = self.reports_dir / "class_distribution.json"
        self.assertTrue(dist_file.exists(), "class_distribution.json must exist")
        with open(dist_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["canonical_class_count"], 12)
        self.assertEqual(data["covered_classes_count"], 3)
        self.assertEqual(data["missing_classes_count"], 9)
        self.assertGreaterEqual(data["imbalance_ratio_among_covered"], 1.0)

        # Check covered classes: 0 (Garbage Overflow), 2 (Pothole), 3 (Damaged Road)
        covered_ids = [c["class_id"] for c in data["classes"] if c["status"] == "COVERED"]
        self.assertEqual(sorted(covered_ids), [0, 2, 3])

    # Test 20: Custom data acquisition strategy documents municipal collection guidelines
    def test_20_custom_data_strategy_documented(self):
        doc_file = self.reports_dir / "custom_data_required.md"
        self.assertTrue(doc_file.exists(), "custom_data_required.md must exist")
        content = doc_file.read_text(encoding="utf-8")
        self.assertIn("Custom Data Acquisition Strategy", content)
        self.assertIn("Water Leakage", content)
        self.assertIn("Sewage Overflow", content)
        self.assertIn("Broken Street Light", content)
        self.assertIn("Drainage Problem", content)
        self.assertIn("Traffic Issue", content)
        self.assertIn("Building Damage", content)
        self.assertIn("Park/Public Space Damage", content)
        self.assertIn("Environmental Pollution", content)
        self.assertIn("Privacy Standards", content)
        self.assertIn("Gaussian blur", content)

    # Test 21: Quality gate passes via Step 4A validator with zero fake training or fake weights
    def test_21_quality_gate_passes_and_no_fake_training(self):
        validator = YOLODatasetValidator(self.processed_dir, dataset_version="civic_yolo_v1")
        res = validator.validate()
        self.assertTrue(res.is_valid, f"Quality gate must pass: {res.errors}")
        self.assertEqual(res.status, "READY_FOR_TRAINING")
        self.assertEqual(len(res.errors), 0)

        # Verify quality report on disk
        qual_file = self.reports_dir / "data_quality_report.json"
        self.assertTrue(qual_file.exists(), "data_quality_report.json must exist")
        with open(qual_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["valid"])
        self.assertEqual(data["status"], "READY_FOR_TRAINING")

        # STRICT NEGATIVE BOUNDARY CHECK:
        # Confirm that no fake weights (.pt files) or fabricated metrics exist in processed directory
        pt_files = list(self.processed_dir.rglob("*.pt"))
        self.assertEqual(
            len(pt_files), 0, "No fake weights (.pt) should be placed in the processed dataset"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
