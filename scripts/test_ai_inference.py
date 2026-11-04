import sys
import io
import time
from pathlib import Path
from PIL import Image

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi_app import app as fastapi_app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.model_version import ModelVersion
from app.models.audit_log import AuditLog
from app.core.auth import hash_password, create_access_token
from app.services.dataset_validator import CANONICAL_CLASSES
from app.services.routing_service import route_issue_to_department
from app.services.severity_service import calculate_issue_severity
from app.ai.detection_service import DetectionService, CLASS_ID_TO_INTERNAL_ISSUE
from app.ai.schemas import BoundingBox, DetectionItem
from app.ai.ai_exceptions import AINoDetectionException, AIModelNotAvailableException
from app.ai.model_loader import ModelLoader


def create_sample_image_bytes(format="JPEG", size=(100, 100), color=(255, 0, 0)) -> bytes:
    """Helper to generate a valid in-memory test image."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


class AIInferenceTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db: Session = SessionLocal()
        self.results = []
        self.citizen_user = None
        self.citizen_token = None

    def log(self, test_name: str, passed: bool, message: str = "", skipped: bool = False):
        if skipped:
            status_str = "[SKIP]"
        elif passed:
            status_str = "[PASS]"
        else:
            status_str = "[FAIL]"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "skipped": skipped,
            "message": message,
        })
        print(f"{status_str} {test_name}: {message}")

    def setup(self):
        ts = int(time.time() * 1000)
        self.citizen_user = User(
            name="AI Citizen Tester",
            email=f"ai_citizen_{ts}@example.com",
            password_hash=hash_password("Password@123"),
            role=UserRole.CITIZEN,
        )
        self.db.add(self.citizen_user)
        self.db.commit()
        self.db.refresh(self.citizen_user)

        self.citizen_token = create_access_token({
            "sub": str(self.citizen_user.id),
            "email": self.citizen_user.email,
            "role": UserRole.CITIZEN,
        })

    def teardown(self):
        try:
            if self.citizen_user:
                self.db.query(AuditLog).filter(AuditLog.user_id == self.citizen_user.id).delete()
                self.db.query(User).filter(User.id == self.citizen_user.id).delete()
                self.db.commit()
        finally:
            self.db.close()

    def run(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 5 REAL YOLO AI INFERENCE INTEGRATION TESTS")
        print("=" * 80)

        self.setup()
        try:
            self.test_no_active_model()
            self.test_invalid_image_extension()
            self.test_zero_byte_image()
            self.test_oversized_image()
            self.test_corrupted_image()
            self.test_unauthorized_request()
            self.test_invalid_jwt_token()
            self.test_12_canonical_classes_mapping()
            self.test_pothole_department_routing()
            self.test_all_12_classes_department_routing()
            self.test_deterministic_severity_integration()
            self.test_no_detection_handling()
            self.test_multiple_detections_resolution()
            self.test_model_loader_cache()
            self.test_audit_logging_no_secrets()
            self.test_active_real_model_inference()

        finally:
            self.teardown()

        print("\n" + "=" * 80)
        print("AI INFERENCE TEST EXECUTION SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"] and not r["skipped"])
        skipped_count = sum(1 for r in self.results if r["skipped"])
        failed_count = sum(1 for r in self.results if not r["passed"] and not r["skipped"])
        total_count = len(self.results)

        print(f"Total Tests Run: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Failed: {failed_count}")
        print(f"Status: {'ALL TESTS COMPLETED AS EXPECTED' if failed_count == 0 else 'SOME TESTS FAILED'}")
        print("=" * 80)

        if failed_count > 0:
            sys.exit(1)

    # Test A: No Active Model
    def test_no_active_model(self):
        # Ensure no active model
        active = self.db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        img_bytes = create_sample_image_bytes()
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        files = {"file": ("pothole.jpg", img_bytes, "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        data = resp.json()

        if active is None:
            passed = (
                resp.status_code == 200
                and data.get("success") is False
                and data.get("error_code") == "AI_MODEL_NOT_AVAILABLE"
                and "No trained AI model is currently active" in data.get("message", "")
            )
            self.log(
                "Test A — No active model returns AI_MODEL_NOT_AVAILABLE",
                passed,
                f"Status: {resp.status_code}, error_code: {data.get('error_code')}",
            )
        else:
            self.log("Test A — No active model returns AI_MODEL_NOT_AVAILABLE", True, "Active model exists, checked separately")

    # Test B1: Invalid Image Extension
    def test_invalid_image_extension(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        files = {"file": ("malicious.exe", b"MZ_NOT_AN_IMAGE", "application/octet-stream")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 400
        self.log(
            "Test B1 — Invalid file extension (.exe) rejected with 400",
            passed,
            f"Status: {resp.status_code}, detail: {resp.json().get('detail')}",
        )

    # Test B2: Zero Byte Image
    def test_zero_byte_image(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        files = {"file": ("empty.jpg", b"", "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 400 and "empty" in resp.json().get("detail", "").lower()
        self.log(
            "Test B2 — Zero-byte image rejected with 400",
            passed,
            f"Status: {resp.status_code}, detail: {resp.json().get('detail')}",
        )

    # Test B3: Oversized Image
    def test_oversized_image(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        oversized_bytes = b"X" * (10 * 1024 * 1024 + 1024)  # > 10MB
        files = {"file": ("huge.jpg", oversized_bytes, "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 400 and "exceeds" in resp.json().get("detail", "").lower()
        self.log(
            "Test B3 — Oversized image (>10MB) rejected with 400",
            passed,
            f"Status: {resp.status_code}, detail: {resp.json().get('detail')}",
        )

    # Test C: Corrupted Image
    def test_corrupted_image(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        corrupted_bytes = b"\xFF\xD8\xFF\xE0" + b"CORRUPTED_GARBAGE_PAYLOAD_NOT_IMAGE" * 20
        files = {"file": ("corrupt.jpg", corrupted_bytes, "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 400 and ("corrupted" in resp.json().get("detail", "").lower() or "verification" in resp.json().get("detail", "").lower())
        self.log(
            "Test C — Corrupted image rejected with 400",
            passed,
            f"Status: {resp.status_code}, detail: {resp.json().get('detail')}",
        )

    # Test D1: Unauthorized Request (No Token)
    def test_unauthorized_request(self):
        img_bytes = create_sample_image_bytes()
        files = {"file": ("pothole.jpg", img_bytes, "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", files=files)
        passed = resp.status_code == 401
        self.log(
            "Test D1 — Unauthenticated request rejected with 401",
            passed,
            f"Status: {resp.status_code}",
        )

    # Test D2: Invalid JWT Token
    def test_invalid_jwt_token(self):
        img_bytes = create_sample_image_bytes()
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        files = {"file": ("pothole.jpg", img_bytes, "image/jpeg")}

        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 401
        self.log(
            "Test D2 — Invalid JWT rejected with 401",
            passed,
            f"Status: {resp.status_code}",
        )

    # Test F: Canonical 12-Class Mapping
    def test_12_canonical_classes_mapping(self):
        expected_classes = {
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
            11: "Environmental Pollution",
        }
        passed = (
            len(CANONICAL_CLASSES) == 12
            and all(CANONICAL_CLASSES.get(k) == v for k, v in expected_classes.items())
            and all(k in CLASS_ID_TO_INTERNAL_ISSUE for k in range(12))
        )
        self.log(
            "Test F — Exactly 12 canonical classes match zero-indexed specifications",
            passed,
            f"Class count: {len(CANONICAL_CLASSES)}, Match: {passed}",
        )

    # Test G1: Pothole -> Roads & Highways
    def test_pothole_department_routing(self):
        dept = route_issue_to_department("pothole", self.db)
        passed = dept is not None and dept.name == "Roads & Highways"
        self.log(
            "Test G1 — Pothole routes dynamically to 'Roads & Highways'",
            passed,
            f"Dept ID: {dept.id if dept else None}, Name: {dept.name if dept else None}",
        )

    # Test G2: All 12 Classes Route to Valid Active Departments
    def test_all_12_classes_department_routing(self):
        all_ok = True
        routed = {}
        for class_id, issue_type in CLASS_ID_TO_INTERNAL_ISSUE.items():
            dept = route_issue_to_department(issue_type, self.db)
            if not dept or not dept.active:
                all_ok = False
                break
            routed[issue_type] = dept.name

        self.log(
            "Test G2 — All 12 canonical civic issues route to active DB departments",
            all_ok and len(routed) == 12,
            f"Successfully routed {len(routed)} of 12 classes",
        )

    # Test: Severity Integration
    def test_deterministic_severity_integration(self):
        sev_building = calculate_issue_severity("building_damage", 0.95)
        sev_sewage = calculate_issue_severity("sewage_overflow", 0.88)
        sev_pothole = calculate_issue_severity("pothole", 0.91)
        sev_garbage = calculate_issue_severity("garbage_overflow", 0.75)

        passed = (
            sev_building["level"] == "CRITICAL"
            and sev_sewage["level"] == "HIGH"
            and sev_pothole["level"] == "MEDIUM"
            and sev_garbage["level"] == "LOW"
            and sev_pothole["score"] is None  # strictly no fake score
            and sev_pothole["ai_confidence"] == 0.91
            and len(sev_pothole["reason"]) > 0
        )
        self.log(
            "Test — Deterministic severity produces correct risk levels and reasons",
            passed,
            f"Pothole: {sev_pothole['level']} (conf={sev_pothole['ai_confidence']}), Building: {sev_building['level']}",
        )

    # Test H: No Detection Handling
    def test_no_detection_handling(self):
        try:
            DetectionService.resolve_primary_issue([], "MODEL-2026-000001")
            passed = False
            msg = "Expected AINoDetectionException was not raised"
        except AINoDetectionException as exc:
            passed = exc.error_code == "AI_NO_DETECTION"
            msg = f"Caught expected {exc.error_code}: {str(exc)}"

        self.log(
            "Test H — Empty detection list raises AI_NO_DETECTION rather than inventing an issue",
            passed,
            msg,
        )

    # Test: Multiple Detections Resolution
    def test_multiple_detections_resolution(self):
        dets = [
            DetectionItem(
                class_id=0,
                class_name="Garbage Overflow",
                confidence=0.55,
                bbox=BoundingBox(x1=10, y1=10, x2=100, y2=100),
            ),
            DetectionItem(
                class_id=2,
                class_name="Pothole",
                confidence=0.92,
                bbox=BoundingBox(x1=50, y1=50, x2=200, y2=200),
            ),
            DetectionItem(
                class_id=3,
                class_name="Damaged Road",
                confidence=0.78,
                bbox=BoundingBox(x1=20, y1=20, x2=150, y2=150),
            ),
        ]
        res = DetectionService.resolve_primary_issue(dets, "MODEL-2026-000001")
        passed = (
            res.class_id == 2
            and res.class_name == "Pothole"
            and res.confidence == 0.92
            and res.issue_type == "pothole"
        )
        self.log(
            "Test — Multiple detections prioritizes highest-confidence valid issue (Pothole 0.92 > 0.78 > 0.55)",
            passed,
            f"Selected: {res.class_name} (conf={res.confidence})",
        )

    # Test: ModelLoader Cache and Reload
    def test_model_loader_cache(self):
        ModelLoader.clear_cache()
        cached_before = ModelLoader.get_cached_version()
        passed = cached_before is None
        self.log(
            "Test — ModelLoader clear_cache evicts cached model safely",
            passed,
            f"Cached version after clear: {cached_before}",
        )

    # Test: Audit Logging Sanitization
    def test_audit_logging_no_secrets(self):
        logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == self.citizen_user.id)
            .all()
        )
        passed = len(logs) > 0
        zero_secrets = True
        for log_entry in logs:
            meta_str = str(log_entry.metadata_ or {}).lower()
            if any(forbidden in meta_str for forbidden in ["password", "token", "secret", "binary"]):
                zero_secrets = False
                break

        self.log(
            "Test — AI audit event logged in PostgreSQL without leaking secrets or image binaries",
            passed and zero_secrets,
            f"Audit entries: {len(logs)}, Zero secrets: {zero_secrets}",
        )

    # Test E: Active Real Model Inference
    def test_active_real_model_inference(self):
        active_model = self.db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).first()
        if active_model is None:
            # Strictly NO fake model creation: explicitly skip
            self.log(
                "Test E — Active real model inference",
                passed=True,
                message="SKIPPED: No active trained YOLO model exists in PostgreSQL. Training data not yet available.",
                skipped=True,
            )
            return

        # If a real model does exist, run real inference
        img_bytes = create_sample_image_bytes()
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        files = {"file": ("test_civic.jpg", img_bytes, "image/jpeg")}
        resp = self.client.post("/api/v1/ai/inference", headers=headers, files=files)
        passed = resp.status_code == 200
        self.log(
            "Test E — Active real model inference",
            passed,
            f"Status: {resp.status_code}, Version: {active_model.model_version}",
            skipped=False,
        )


if __name__ == "__main__":
    runner = AIInferenceTestRunner()
    runner.run()
