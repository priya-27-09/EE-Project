import sys
import io
import os
import zipfile
import shutil
import tempfile
import time
from pathlib import Path
from PIL import Image

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.dataset import DatasetVersion, DatasetStatus
from app.core.auth import hash_password, create_access_token
from app.services.dataset_validator import YOLODatasetValidator, CANONICAL_CLASSES
from fastapi_app import app as fastapi_app


def create_zip_bytes(files_dict: dict) -> bytes:
    """Helper to create an in-memory zip archive from {relative_path: content_bytes_or_str}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files_dict.items():
            if isinstance(content, str):
                zf.writestr(path, content.encode("utf-8"))
            else:
                zf.writestr(path, content)
    return buf.getvalue()


def make_dummy_image_bytes(color=(100, 100, 100), fmt="JPEG") -> bytes:
    """Create a valid tiny image in memory."""
    im = Image.new("RGB", (64, 64), color=color)
    b = io.BytesIO()
    im.save(b, format=fmt)
    return b.getvalue()


class DatasetManagementTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db: Session = SessionLocal()
        self.results = []
        self.admin_token = None
        self.citizen_token = None
        self.officer_token = None
        self.admin_user = None
        self.citizen_user = None
        self.officer_user = None
        self.created_dataset_versions = []

    def log(self, test_name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({"test": test_name, "passed": passed, "message": message})
        print(f"{status_str} {test_name}: {message}")

    def setup_users(self):
        ts = int(time.time())
        # 1. Admin
        self.admin_user = User(
            name="Admin DS Tester",
            email=f"admin_ds_{ts}@example.com",
            password_hash=hash_password("AdminPass@123"),
            role=UserRole.ADMIN,
            preferred_language="en",
        )
        # 2. Citizen
        self.citizen_user = User(
            name="Citizen DS Tester",
            email=f"citizen_ds_{ts}@example.com",
            password_hash=hash_password("CitizenPass@123"),
            role=UserRole.CITIZEN,
            preferred_language="en",
        )
        # 3. Officer
        self.officer_user = User(
            name="Officer DS Tester",
            email=f"officer_ds_{ts}@example.com",
            password_hash=hash_password("OfficerPass@123"),
            role=UserRole.OFFICER,
            preferred_language="en",
        )
        self.db.add_all([self.admin_user, self.citizen_user, self.officer_user])
        self.db.commit()
        self.db.refresh(self.admin_user)
        self.db.refresh(self.citizen_user)
        self.db.refresh(self.officer_user)

        self.admin_token = create_access_token({"sub": str(self.admin_user.id), "email": self.admin_user.email, "role": UserRole.ADMIN})
        self.citizen_token = create_access_token({"sub": str(self.citizen_user.id), "email": self.citizen_user.email, "role": UserRole.CITIZEN})
        self.officer_token = create_access_token({"sub": str(self.officer_user.id), "email": self.officer_user.email, "role": UserRole.OFFICER})

    def teardown(self):
        # Cleanup uploaded dataset directories
        for v in self.created_dataset_versions:
            v_dir = settings.BASE_DIR / "dataset" / "versions" / v
            if v_dir.exists():
                shutil.rmtree(v_dir, ignore_errors=True)

        # Cleanup DB
        if self.created_dataset_versions:
            self.db.query(DatasetVersion).filter(DatasetVersion.dataset_version.in_(self.created_dataset_versions)).delete(synchronize_session=False)

        if self.admin_user:
            self.db.query(User).filter(User.id.in_([self.admin_user.id, self.citizen_user.id, self.officer_user.id])).delete(synchronize_session=False)

        self.db.commit()
        self.db.close()

    def build_valid_dataset_files(self) -> dict:
        """Build dictionary of files for a small valid YOLO dataset."""
        img1 = make_dummy_image_bytes(color=(120, 50, 50))
        img2 = make_dummy_image_bytes(color=(50, 120, 50))
        img3 = make_dummy_image_bytes(color=(50, 50, 120))
        img4 = make_dummy_image_bytes(color=(80, 80, 80))

        yaml_content = (
            "path: .\n"
            "train: images/train\n"
            "val: images/val\n"
            "test: images/test\n"
            "names:\n"
            "  0: Garbage Overflow\n"
            "  1: Illegal Dumping\n"
            "  2: Pothole\n"
            "  3: Damaged Road\n"
        )

        return {
            "data.yaml": yaml_content,
            "images/train/train_01.jpg": img1,
            "images/train/train_02.jpg": img2,
            "images/val/val_01.jpg": img3,
            "images/test/test_01.jpg": img4,
            "labels/train/train_01.txt": "2 0.50 0.50 0.30 0.30\n3 0.20 0.20 0.15 0.15\n",
            "labels/train/train_02.txt": "0 0.60 0.40 0.25 0.35\n",
            "labels/val/val_01.txt": "1 0.45 0.55 0.20 0.20\n",
            "labels/test/test_01.txt": "2 0.70 0.30 0.10 0.15\n",
        }

    def run_all_tests(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 4A YOLO DATASET MANAGEMENT & VALIDATION TESTS")
        print("=" * 80)
        self.setup_users()

        try:
            # 1. Admin can upload dataset
            valid_zip = create_zip_bytes(self.build_valid_dataset_files())
            resp1 = self.client.post(
                "/api/v1/admin/datasets",
                files={"file": ("civic_valid.zip", valid_zip, "application/zip")},
                data={"dataset_name": "Civic Valid Dataset V1", "description": "Valid test dataset"},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
            v1_data = resp1.json()
            is_201 = resp1.status_code == 201
            v1_version = v1_data.get("dataset", {}).get("dataset_version") if is_201 else None
            if v1_version:
                self.created_dataset_versions.append(v1_version)
            self.log("Test 01 — Admin can upload dataset", is_201 and v1_version is not None, f"HTTP {resp1.status_code}, Version={v1_version}")

            # 2. Citizen cannot upload dataset
            resp2 = self.client.post(
                "/api/v1/admin/datasets",
                files={"file": ("civic_valid.zip", valid_zip, "application/zip")},
                data={"dataset_name": "Citizen Hack Dataset"},
                headers={"Authorization": f"Bearer {self.citizen_token}"},
            )
            self.log("Test 02 — Citizen cannot upload dataset", resp2.status_code == 403, f"HTTP {resp2.status_code} (Forbidden expected)")

            # 3. Officer cannot upload dataset
            resp3 = self.client.post(
                "/api/v1/admin/datasets",
                files={"file": ("civic_valid.zip", valid_zip, "application/zip")},
                data={"dataset_name": "Officer Dataset"},
                headers={"Authorization": f"Bearer {self.officer_token}"},
            )
            self.log("Test 03 — Officer cannot upload dataset", resp3.status_code == 403, f"HTTP {resp3.status_code} (Forbidden expected)")

            # 4. Dataset version is unique
            resp4 = self.client.post(
                "/api/v1/admin/datasets",
                files={"file": ("civic_valid_2.zip", valid_zip, "application/zip")},
                data={"dataset_name": "Civic Valid Dataset V2"},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
            v2_data = resp4.json()
            v2_version = v2_data.get("dataset", {}).get("dataset_version")
            if v2_version:
                self.created_dataset_versions.append(v2_version)
            is_unique = (v1_version != v2_version) and v2_version.startswith("DS-")
            self.log("Test 04 — Dataset version is unique", is_unique, f"V1={v1_version}, V2={v2_version}")

            # 5. Dataset metadata is saved in PostgreSQL
            db_record = self.db.query(DatasetVersion).filter(DatasetVersion.dataset_version == v1_version).first()
            db_saved = (
                db_record is not None
                and db_record.dataset_name == "Civic Valid Dataset V1"
                and db_record.uploaded_by == self.admin_user.id
                and db_record.total_image_count == 4
                and db_record.total_object_count == 5
                and len(db_record.dataset_sha256) == 64
            )
            self.log("Test 05 — Dataset metadata is saved in PostgreSQL", db_saved, f"DB Record ID={db_record.id if db_record else None}, Images={db_record.total_image_count if db_record else None}")

            # 6. data.yaml is detected
            v1_report = v1_data.get("validation", {})
            has_yaml = "Missing required data.yaml" not in " ".join(v1_report.get("errors", []))
            self.log("Test 06 — data.yaml is detected", has_yaml, f"Classes declared in data.yaml: {v1_report.get('summary', {}).get('class_count')}")

            # 7. Missing data.yaml is detected
            no_yaml_files = self.build_valid_dataset_files()
            del no_yaml_files["data.yaml"]
            with tempfile.TemporaryDirectory() as td:
                for k, v in no_yaml_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-NOYAML").validate()
                missing_yaml_detected = any("Missing required data.yaml" in e for e in val_res.errors) and not val_res.is_valid
            self.log("Test 07 — Missing data.yaml is detected", missing_yaml_detected, f"Errors: {val_res.errors}")

            # 8. Missing train directory is detected
            no_train_files = self.build_valid_dataset_files()
            no_train_files = {k: v for k, v in no_train_files.items() if not k.startswith("images/train")}
            with tempfile.TemporaryDirectory() as td:
                for k, v in no_train_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-NOTRAIN").validate()
                missing_train_detected = any("Missing required image directory: images/train" in e for e in val_res.errors)
            self.log("Test 08 — Missing train directory is detected", missing_train_detected, f"Errors: {val_res.errors}")

            # 9. Missing val directory is detected
            no_val_files = self.build_valid_dataset_files()
            no_val_files = {k: v for k, v in no_val_files.items() if not k.startswith("images/val")}
            with tempfile.TemporaryDirectory() as td:
                for k, v in no_val_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-NOVAL").validate()
                missing_val_detected = any("Missing required image directory: images/val" in e for e in val_res.errors)
            self.log("Test 09 — Missing val directory is detected", missing_val_detected, f"Errors: {val_res.errors}")

            # 10. Missing test directory is detected
            no_test_files = self.build_valid_dataset_files()
            no_test_files = {k: v for k, v in no_test_files.items() if not k.startswith("images/test")}
            with tempfile.TemporaryDirectory() as td:
                for k, v in no_test_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-NOTEST").validate()
                missing_test_detected = any("Missing required image directory: images/test" in e for e in val_res.errors)
            self.log("Test 10 — Missing test directory is detected", missing_test_detected, f"Errors: {val_res.errors}")

            # 11. Valid YOLO label passes
            self.log("Test 11 — Valid YOLO label passes", len(v1_report.get("invalid_labels", [])) == 0 and v1_report.get("valid") is True, f"Valid objects parsed: {v1_report.get('summary', {}).get('total_objects')}")

            # 12. Invalid class ID fails
            bad_cid_files = self.build_valid_dataset_files()
            bad_cid_files["labels/train/train_01.txt"] = "99 0.50 0.50 0.30 0.30\n"
            with tempfile.TemporaryDirectory() as td:
                for k, v in bad_cid_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-BADCID").validate()
                bad_cid_detected = any("Invalid class ID" in e or "class_id 99 is not declared" in e for e in val_res.errors)
            self.log("Test 12 — Invalid class ID fails", bad_cid_detected and not val_res.is_valid, f"Detected error in invalid_labels: {len(val_res.invalid_labels)}")

            # 13. Invalid normalized coordinates fail
            bad_coord_files = self.build_valid_dataset_files()
            bad_coord_files["labels/train/train_01.txt"] = "2 1.50 0.50 0.30 0.30\n"
            with tempfile.TemporaryDirectory() as td:
                for k, v in bad_coord_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-BADCOORD").validate()
                bad_coord_detected = any("Out of bounds coordinates" in e or "outside [0.0, 1.0]" in e for e in val_res.errors)
            self.log("Test 13 — Invalid normalized coordinates fail", bad_coord_detected and not val_res.is_valid, f"Detected out-of-bounds coordinate: {val_res.invalid_labels[0]['error'] if val_res.invalid_labels else None}")

            # 14. Malformed label fails
            malformed_files = self.build_valid_dataset_files()
            malformed_files["labels/train/train_01.txt"] = "2 0.50 0.50\n"  # only 3 tokens
            with tempfile.TemporaryDirectory() as td:
                for k, v in malformed_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-MALFORMED").validate()
                malformed_detected = any("Malformed label" in e or "Expected 5 values" in e for e in val_res.errors)
            self.log("Test 14 — Malformed label fails", malformed_detected and not val_res.is_valid, f"Reported line: {val_res.invalid_labels[0]['line'] if val_res.invalid_labels else None}")

            # 15. Missing label is detected
            missing_lbl_files = self.build_valid_dataset_files()
            del missing_lbl_files["labels/train/train_02.txt"]
            with tempfile.TemporaryDirectory() as td:
                for k, v in missing_lbl_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-MISSLBL").validate()
                missing_lbl_detected = len(val_res.missing_labels) == 1 and val_res.summary["missing_label_count"] == 1
            self.log("Test 15 — Missing label is detected", missing_lbl_detected, f"Missing labels: {val_res.missing_labels}")

            # 16. Orphan label is detected
            orphan_lbl_files = self.build_valid_dataset_files()
            orphan_lbl_files["labels/train/ghost_image.txt"] = "2 0.5 0.5 0.2 0.2\n"
            with tempfile.TemporaryDirectory() as td:
                for k, v in orphan_lbl_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-ORPHAN").validate()
                orphan_detected = len(val_res.orphan_labels) == 1 and val_res.summary["orphan_label_count"] == 1
            self.log("Test 16 — Orphan label is detected", orphan_detected, f"Orphan labels: {val_res.orphan_labels}")

            # 17. Empty label is reported
            empty_lbl_files = self.build_valid_dataset_files()
            empty_lbl_files["labels/train/train_02.txt"] = ""  # empty negative sample
            with tempfile.TemporaryDirectory() as td:
                for k, v in empty_lbl_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-EMPTY").validate()
                empty_reported = val_res.summary["empty_label_count"] == 1 and val_res.is_valid
            self.log("Test 17 — Empty label is reported", empty_reported, f"Empty label count={val_res.summary['empty_label_count']}, Valid={val_res.is_valid}")

            # 18. Corrupted image is detected
            corrupt_files = self.build_valid_dataset_files()
            corrupt_files["images/train/train_01.jpg"] = b"NOT_A_REAL_IMAGE_DATA_CORRUPT"
            with tempfile.TemporaryDirectory() as td:
                for k, v in corrupt_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-CORRUPT").validate()
                corrupt_detected = len(val_res.corrupted_images) == 1 and not val_res.is_valid
            self.log("Test 18 — Corrupted image is detected", corrupt_detected, f"Corrupted image count={len(val_res.corrupted_images)}")

            # 19. Duplicate image hash is detected
            dup_files = self.build_valid_dataset_files()
            dup_files["images/train/train_02.jpg"] = dup_files["images/train/train_01.jpg"]  # exact duplicate
            with tempfile.TemporaryDirectory() as td:
                for k, v in dup_files.items():
                    fp = Path(td) / k
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(v, str):
                        fp.write_text(v)
                    else:
                        fp.write_bytes(v)
                val_res = YOLODatasetValidator(Path(td), "DS-TEST-DUP").validate()
                dup_detected = val_res.summary["duplicate_group_count"] == 1 and val_res.summary["duplicate_image_count"] == 2
            self.log("Test 19 — Duplicate image hash is detected", dup_detected, f"Duplicate groups: {val_res.summary['duplicate_group_count']}")

            # 20. Class statistics are calculated
            stats_classes = v1_report.get("classes", [])
            has_pothole = any(c["class_name"] == "Pothole" and c["objects"] == 2 for c in stats_classes)
            has_dumping = any(c["class_name"] == "Illegal Dumping" and c["objects"] == 1 for c in stats_classes)
            self.log("Test 20 — Class statistics are calculated", has_pothole and has_dumping, f"Classes parsed: {[c['class_name'] + ': ' + str(c['objects']) for c in stats_classes]}")

            # 21. Dataset with subset of classes produces a warning
            subset_warning_found = any("Dataset contains 4 of 12 required civic classes" in w for w in v1_report.get("warnings", []))
            self.log("Test 21 — Dataset with subset of classes produces a warning", subset_warning_found, f"Warnings: {v1_report.get('warnings')}")

            # 22. Dataset with valid structure becomes READY_FOR_TRAINING
            is_ready = v1_data.get("dataset", {}).get("status") == DatasetStatus.READY_FOR_TRAINING
            self.log("Test 22 — Dataset with valid structure becomes READY_FOR_TRAINING", is_ready, f"Status={v1_data.get('dataset', {}).get('status')}")

            # 23. Invalid dataset becomes INVALID
            invalid_zip = create_zip_bytes(bad_cid_files)
            resp_inv = self.client.post(
                "/api/v1/admin/datasets",
                files={"file": ("civic_invalid.zip", invalid_zip, "application/zip")},
                data={"dataset_name": "Invalid Dataset Testing"},
                headers={"Authorization": f"Bearer {self.admin_token}"},
            )
            inv_data = resp_inv.json()
            inv_version = inv_data.get("dataset", {}).get("dataset_version")
            if inv_version:
                self.created_dataset_versions.append(inv_version)
            is_invalid_status = inv_data.get("dataset", {}).get("status") == DatasetStatus.INVALID
            self.log("Test 23 — Invalid dataset becomes INVALID", is_invalid_status, f"Status={inv_data.get('dataset', {}).get('status')}")

            # 24. Citizen cannot access admin dataset API
            res_c1 = self.client.get("/api/v1/admin/datasets", headers={"Authorization": f"Bearer {self.citizen_token}"})
            res_c2 = self.client.get(f"/api/v1/admin/datasets/{v1_version}", headers={"Authorization": f"Bearer {self.citizen_token}"})
            res_c3 = self.client.post(f"/api/v1/admin/datasets/{v1_version}/validate", headers={"Authorization": f"Bearer {self.citizen_token}"})
            res_c4 = self.client.get(f"/api/v1/admin/datasets/{v1_version}/report", headers={"Authorization": f"Bearer {self.citizen_token}"})
            citizen_blocked = all(r.status_code == 403 for r in [res_c1, res_c2, res_c3, res_c4])
            self.log("Test 24 — Citizen cannot access admin dataset API", citizen_blocked, f"HTTP codes: {[r.status_code for r in [res_c1, res_c2, res_c3, res_c4]]}")

            # 25. Officer cannot access admin dataset API
            res_o1 = self.client.get("/api/v1/admin/datasets", headers={"Authorization": f"Bearer {self.officer_token}"})
            res_o2 = self.client.get(f"/api/v1/admin/datasets/{v1_version}", headers={"Authorization": f"Bearer {self.officer_token}"})
            res_o3 = self.client.post(f"/api/v1/admin/datasets/{v1_version}/validate", headers={"Authorization": f"Bearer {self.officer_token}"})
            res_o4 = self.client.get(f"/api/v1/admin/datasets/{v1_version}/report", headers={"Authorization": f"Bearer {self.officer_token}"})
            officer_blocked = all(r.status_code == 403 for r in [res_o1, res_o2, res_o3, res_o4])
            self.log("Test 25 — Officer cannot access admin dataset API", officer_blocked, f"HTTP codes: {[r.status_code for r in [res_o1, res_o2, res_o3, res_o4]]}")

            # 26. Dataset report contains actual values
            report_resp = self.client.get(f"/api/v1/admin/datasets/{v1_version}/report", headers={"Authorization": f"Bearer {self.admin_token}"})
            actual_report = report_resp.json().get("report", {})
            values_match = (
                actual_report.get("summary", {}).get("total_images") == 4
                and actual_report.get("summary", {}).get("train_images") == 2
                and actual_report.get("summary", {}).get("val_images") == 1
                and actual_report.get("summary", {}).get("test_images") == 1
                and actual_report.get("summary", {}).get("total_objects") == 5
            )
            self.log("Test 26 — Dataset report contains actual values", values_match, f"Summary: {actual_report.get('summary')}")

            # 27. No fake metrics are created
            forbidden_keys = ["mAP", "accuracy", "loss", "precision", "recall", "epochs", "weights", "ai_predictions"]
            has_fake = any(k in actual_report for k in forbidden_keys)
            no_fake = not has_fake and "READY_FOR_TRAINING" in actual_report.get("status", "")
            self.log("Test 27 — No fake metrics are created", no_fake, "Confirmed zero AI training metrics or fake model weights exist.")

        finally:
            self.teardown()

        print("=" * 80)
        print("DATASET MANAGEMENT TEST EXECUTION SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        print(f"Total Tests Run: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_count - passed_count}")
        print(f"Status: {'ALL 27 TESTS PASSED' if passed_count == total_count else 'SOME TESTS FAILED'}")
        print("=" * 80)
        if passed_count != total_count:
            sys.exit(1)


if __name__ == "__main__":
    runner = DatasetManagementTestRunner()
    runner.run_all_tests()
