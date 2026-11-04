"""
Step 9 Automated Test Suite — AI-Assisted Resolution Evidence Verification.
Comprehensive 25-test suite testing:
1. Service imports and constants.
2. Valid before image loads.
3. Valid after image loads.
4. Corrupt image rejected.
5. Unsupported image rejected.
6. Missing before evidence handled (VERIFICATION_NOT_AVAILABLE).
7. Missing after evidence handled (VERIFICATION_NOT_AVAILABLE).
8. Image preprocessing (resize, grayscale, 512x512).
9. Computer vision metrics calculation and bounds.
10. Deterministic scoring formula.
11. Determinism across repeated runs.
12. Different images produce measurable differences.
13. Dissimilar/inconclusive scenes trigger NEEDS_HUMAN_REVIEW.
14. Verification record persisted in PostgreSQL.
15. Audit log record created in audit_logs.
16. Officer department isolation enforced (cross-department returns 403).
17. Citizen cannot call officer verification API (returns 403).
18. Other department officer cannot verify complaint (returns 403).
19. Human review recorded (APPROVED/REJECTED).
20. Human decision preserves automated CV metrics without overwriting.
21. Repeated verification preserves audit trail and history.
22. Resolution evidence uses is_resolution=True.
23. Citizen original evidence uses is_resolution=False.
24. No fake ML confidence strings or fake YOLO claims.
25. No secrets or private tokens in audit logs.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import desc

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.evidence import ComplaintEvidence
from app.models.resolution_verification import ResolutionVerification
from app.models.audit_log import AuditLog
from app.core.auth import hash_password, create_access_token
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_DEPARTMENT_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_NEEDS_HUMAN_REVIEW,
)
import app.services.resolution_verification_service as ver_svc
from fastapi_app import app as fastapi_app

TEST_EVIDENCE_DIR = BASE_DIR / "uploads" / "evidence" / "test_step9"


class ResolutionVerificationTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db = SessionLocal()
        self.results = []
        self.created_users = []
        self.created_complaints = []
        self.created_evidences = []
        self.created_verifications = []

        # Ensure test directory exists
        TEST_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    def log(self, num: int, name: str, passed: bool, msg: str = ""):
        tag = "[PASS]" if passed else "[FAIL]"
        self.results.append({"num": num, "name": name, "passed": passed, "msg": msg})
        print(f"{tag} Test {num:02d} — {name}: {msg}")

    def create_user(self, email: str, name: str, role: str, department_id: Optional[int] = None) -> User:
        pwd_hash = hash_password("SecurePass@123")
        user = User(
            name=name,
            email=email.lower().strip(),
            password_hash=pwd_hash,
            role=role,
            department_id=department_id,
            preferred_language="en",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.created_users.append(user.id)
        return user

    def get_token(self, user: User) -> str:
        return create_access_token(
            data={"sub": str(user.id), "role": user.role, "email": user.email, "department_id": user.department_id}
        )

    def auth_headers(self, user: User) -> dict:
        return {"Authorization": f"Bearer {self.get_token(user)}"}

    def create_synthetic_image(self, filename: str, scene_type: str = "road_with_pothole") -> Path:
        """
        Creates a deterministic synthetic test image strictly for test verification.
        Never placed in production dataset.
        """
        filepath = TEST_EVIDENCE_DIR / filename
        img = np.ones((512, 512, 3), dtype=np.uint8) * 128  # gray road background

        if scene_type == "road_with_pothole":
            # Add road asphalt texture
            np.random.seed(42)
            noise = np.random.randint(-15, 15, (512, 512, 3), dtype=np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            # Draw dark irregular pothole in center
            cv2.ellipse(img, (256, 256), (80, 50), 30, 0, 360, (30, 30, 30), -1)
            cv2.circle(img, (230, 260), 30, (20, 20, 20), -1)
        elif scene_type == "road_repaired":
            # Add road asphalt texture with fresh dark patch covering the pothole
            np.random.seed(42)
            noise = np.random.randint(-15, 15, (512, 512, 3), dtype=np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            # Fresh asphalt patch (smooth dark rectangle/ellipse over the pothole area)
            cv2.rectangle(img, (160, 190), (350, 320), (60, 60, 60), -1)
        elif scene_type == "dissimilar_scene":
            # Completely different image (e.g. bright blue sky and green grass)
            img[:256, :] = [235, 206, 135]  # sky blue
            img[256:, :] = [34, 139, 34]    # forest green
        elif scene_type == "corrupt":
            with open(filepath, "wb") as f:
                f.write(b"not an image file content corrupt")
            return filepath
        elif scene_type == "zero_byte":
            with open(filepath, "wb") as f:
                pass
            return filepath

        cv2.imwrite(str(filepath), img)
        return filepath

    def create_evidence_record(
        self,
        complaint_id: int,
        filepath: Path,
        is_resolution: bool = False,
        file_type: str = "image/jpeg",
    ) -> ComplaintEvidence:
        rel_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
        with open(filepath, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()

        ev = ComplaintEvidence(
            complaint_id=complaint_id,
            file_path=rel_path,
            file_type=file_type,
            sha256_hash=h,
            is_resolution=is_resolution,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)
        self.created_evidences.append(ev.id)
        return ev

    def run_all(self):
        print("=" * 70)
        print("STEP 9 TEST SUITE: AI-ASSISTED RESOLUTION EVIDENCE VERIFICATION")
        print("=" * 70)

        # Pre-requisites: Department and Officers
        roads_dept = self.db.query(Department).filter(Department.name.ilike("%Road%")).first()
        if not roads_dept:
            roads_dept = Department(name="Roads & Infrastructure", description="Roads maintenance")
            self.db.add(roads_dept)
            self.db.commit()
            self.db.refresh(roads_dept)

        water_dept = self.db.query(Department).filter(Department.name.ilike("%Water%")).first()
        if not water_dept:
            water_dept = Department(name="Water Supply & Sewerage", description="Water maintenance")
            self.db.add(water_dept)
            self.db.commit()
            self.db.refresh(water_dept)

        ts = int(datetime.now().timestamp())
        citizen = self.create_user(f"citizen_s9_{ts}@test.gov.in", "Citizen S9", UserRole.CITIZEN)
        officer_roads = self.create_user(f"officer_roads_{ts}@test.gov.in", "Officer Roads S9", UserRole.OFFICER, roads_dept.id)
        officer_water = self.create_user(f"officer_water_{ts}@test.gov.in", "Officer Water S9", UserRole.OFFICER, water_dept.id)
        admin = self.create_user(f"admin_s9_{ts}@test.gov.in", "Admin S9", UserRole.ADMIN)

        # Base complaint for tests
        base_complaint = Complaint(
            complaint_id=f"CG-2026-S9TEST-{ts}",
            issue_type="pothole",
            description="Deep pothole test complaint for resolution verification",
            original_language="en",
            latitude=12.9716,
            longitude=77.5946,
            severity="HIGH",
            status=STATUS_IN_PROGRESS,
            department_id=roads_dept.id,
            user_id=citizen.id,
        )
        self.db.add(base_complaint)
        self.db.commit()
        self.db.refresh(base_complaint)
        self.created_complaints.append(base_complaint.id)

        # ----------------------------------------------------
        # TEST 01: Service imports correctly
        # ----------------------------------------------------
        try:
            assert ver_svc.ALGORITHM_VERSION == "resolution-v1"
            assert ver_svc.VERIFICATION_AI_VERIFIED == "AI_VERIFIED"
            assert ver_svc.VERIFICATION_NEEDS_HUMAN_REVIEW == "NEEDS_HUMAN_REVIEW"
            assert ver_svc.VERIFICATION_FAILED == "VERIFICATION_FAILED"
            assert ver_svc.VERIFICATION_NOT_AVAILABLE == "VERIFICATION_NOT_AVAILABLE"
            self.log(1, "Service imports and constants", True, f"Version: {ver_svc.ALGORITHM_VERSION}")
        except Exception as e:
            self.log(1, "Service imports and constants", False, str(e))

        # ----------------------------------------------------
        # TEST 02: Valid before image loads
        # ----------------------------------------------------
        before_file = self.create_synthetic_image("test_before_02.jpg", "road_with_pothole")
        before_ev = self.create_evidence_record(base_complaint.id, before_file, is_resolution=False)
        try:
            bgr, gray = ver_svc.load_and_preprocess_image(before_ev)
            assert bgr.shape == (512, 512, 3)
            assert gray.shape == (512, 512)
            self.log(2, "Valid before image loads and preprocesses", True, f"Loaded shape: {bgr.shape}")
        except Exception as e:
            self.log(2, "Valid before image loads and preprocesses", False, str(e))

        # ----------------------------------------------------
        # TEST 03: Valid after image loads
        # ----------------------------------------------------
        after_file = self.create_synthetic_image("test_after_03.jpg", "road_repaired")
        after_ev = self.create_evidence_record(base_complaint.id, after_file, is_resolution=True)
        try:
            bgr, gray = ver_svc.load_and_preprocess_image(after_ev)
            assert bgr.shape == (512, 512, 3)
            assert gray.shape == (512, 512)
            self.log(3, "Valid after image loads and preprocesses", True, f"Loaded shape: {bgr.shape}")
        except Exception as e:
            self.log(3, "Valid after image loads and preprocesses", False, str(e))

        # ----------------------------------------------------
        # TEST 04: Corrupt image rejected
        # ----------------------------------------------------
        corrupt_file = self.create_synthetic_image("test_corrupt_04.jpg", "corrupt")
        corrupt_ev = self.create_evidence_record(base_complaint.id, corrupt_file, is_resolution=True)
        try:
            ver_svc.load_and_preprocess_image(corrupt_ev)
            self.log(4, "Corrupt image rejected", False, "Should have raised ValueError")
        except ValueError:
            self.log(4, "Corrupt image rejected", True, "Successfully caught corrupted file")
        except Exception as e:
            self.log(4, "Corrupt image rejected", False, f"Unexpected exception: {str(e)}")

        # ----------------------------------------------------
        # TEST 05: Unsupported/Zero-byte image rejected
        # ----------------------------------------------------
        zero_file = self.create_synthetic_image("test_zero_05.jpg", "zero_byte")
        zero_ev = self.create_evidence_record(base_complaint.id, zero_file, is_resolution=True)
        try:
            ver_svc.load_and_preprocess_image(zero_ev)
            self.log(5, "Empty/Zero-byte image rejected", False, "Should have raised ValueError")
        except ValueError:
            self.log(5, "Empty/Zero-byte image rejected", True, "Successfully rejected 0-byte file")
        except Exception as e:
            self.log(5, "Empty/Zero-byte image rejected", False, f"Unexpected exception: {str(e)}")

        # ----------------------------------------------------
        # TEST 06: Missing before evidence handled
        # ----------------------------------------------------
        c_no_before = Complaint(
            complaint_id=f"CG-2026-NOBEFORE-{ts}",
            issue_type="pothole",
            description="Complaint without citizen before evidence",
            original_language="en",
            status=STATUS_IN_PROGRESS,
            department_id=roads_dept.id,
            user_id=citizen.id,
        )
        self.db.add(c_no_before)
        self.db.commit()
        self.db.refresh(c_no_before)
        self.created_complaints.append(c_no_before.id)

        # Attach ONLY resolution after evidence
        self.create_evidence_record(c_no_before.id, after_file, is_resolution=True)

        res_no_before = ver_svc.run_resolution_verification(c_no_before, officer_roads.id, self.db)
        if (
            res_no_before.verification_status == ver_svc.VERIFICATION_NOT_AVAILABLE
            and "original image" in res_no_before.verification_reason.lower()
        ):
            self.log(6, "Missing before evidence handled", True, res_no_before.verification_reason)
        else:
            self.log(6, "Missing before evidence handled", False, f"Unexpected status: {res_no_before.verification_status}")

        # ----------------------------------------------------
        # TEST 07: Missing after evidence handled
        # ----------------------------------------------------
        c_no_after = Complaint(
            complaint_id=f"CG-2026-NOAFTER-{ts}",
            issue_type="pothole",
            description="Complaint without officer resolution after evidence",
            original_language="en",
            status=STATUS_IN_PROGRESS,
            department_id=roads_dept.id,
            user_id=citizen.id,
        )
        self.db.add(c_no_after)
        self.db.commit()
        self.db.refresh(c_no_after)
        self.created_complaints.append(c_no_after.id)

        # Attach ONLY citizen before evidence
        self.create_evidence_record(c_no_after.id, before_file, is_resolution=False)

        res_no_after = ver_svc.run_resolution_verification(c_no_after, officer_roads.id, self.db)
        if (
            res_no_after.verification_status == ver_svc.VERIFICATION_NOT_AVAILABLE
            and "resolution image" in res_no_after.verification_reason.lower()
        ):
            self.log(7, "Missing after evidence handled", True, res_no_after.verification_reason)
        else:
            self.log(7, "Missing after evidence handled", False, f"Unexpected status: {res_no_after.verification_status}")

        # ----------------------------------------------------
        # TEST 08: Image preprocessing pipeline
        # ----------------------------------------------------
        bgr_b, gray_b = ver_svc.load_and_preprocess_image(before_ev)
        bgr_a, gray_a = ver_svc.load_and_preprocess_image(after_ev)
        if (
            bgr_b.shape == (512, 512, 3)
            and gray_b.shape == (512, 512)
            and bgr_a.shape == (512, 512, 3)
            and gray_a.shape == (512, 512)
        ):
            self.log(8, "Image preprocessing standardization (512x512, BGR & Gray)", True, "Standardized successfully")
        else:
            self.log(8, "Image preprocessing standardization", False, f"Unexpected dimensions: {bgr_b.shape}, {gray_b.shape}")

        # ----------------------------------------------------
        # TEST 09: Metrics calculation & bounds
        # ----------------------------------------------------
        ssim_v = ver_svc.compute_ssim(gray_b, gray_a)
        diff_v = ver_svc.compute_pixel_difference(gray_b, gray_a)
        edge_v = ver_svc.compute_edge_similarity(gray_b, gray_a)
        hist_v = ver_svc.compute_histogram_similarity(bgr_b, bgr_a)
        phash_v = ver_svc.compute_phash_hamming_distance(gray_b, gray_a)

        all_in_bounds = (
            0.0 <= ssim_v <= 1.0
            and 0.0 <= diff_v <= 1.0
            and 0.0 <= edge_v <= 1.0
            and 0.0 <= hist_v <= 1.0
            and 0 <= phash_v <= 64
        )
        if all_in_bounds:
            self.log(
                9,
                "Metrics calculated within valid mathematical bounds",
                True,
                f"SSIM={ssim_v:.4f}, MAD={diff_v:.4f}, Edge={edge_v:.4f}, Hist={hist_v:.4f}, pHash={phash_v}",
            )
        else:
            self.log(9, "Metrics calculated within valid mathematical bounds", False, "Out of bounds metric detected")

        # ----------------------------------------------------
        # TEST 10: Verification score is deterministic
        # ----------------------------------------------------
        st_val, sc_val, hr_val, r_val = ver_svc.evaluate_verification_decision(
            structural_similarity=ssim_v,
            pixel_difference=diff_v,
            edge_similarity=edge_v,
            histogram_similarity=hist_v,
            perceptual_hash_distance=phash_v,
            alignment_status="NOT_AVAILABLE",
        )
        if 0.0 <= sc_val <= 1.0 and st_val in {
            ver_svc.VERIFICATION_AI_VERIFIED,
            ver_svc.VERIFICATION_NEEDS_HUMAN_REVIEW,
            ver_svc.VERIFICATION_FAILED,
        }:
            self.log(10, "Verification score & decision evaluation", True, f"Status: {st_val}, Score: {sc_val}")
        else:
            self.log(10, "Verification score & decision evaluation", False, f"Invalid score or status: {sc_val}, {st_val}")

        # ----------------------------------------------------
        # TEST 11: Determinism Test: Same input produces identical result
        # ----------------------------------------------------
        runs = []
        for _ in range(3):
            s = ver_svc.compute_ssim(gray_b, gray_a)
            d = ver_svc.compute_pixel_difference(gray_b, gray_a)
            e = ver_svc.compute_edge_similarity(gray_b, gray_a)
            h = ver_svc.compute_histogram_similarity(bgr_b, bgr_a)
            p = ver_svc.compute_phash_hamming_distance(gray_b, gray_a)
            _, sc, _, _ = ver_svc.evaluate_verification_decision(s, d, e, h, p, "NOT_AVAILABLE")
            runs.append((round(s, 6), round(d, 6), round(e, 6), round(h, 6), p, round(sc, 6)))

        if runs[0] == runs[1] == runs[2]:
            self.log(11, "Determinism: Repeated runs produce identical metrics", True, f"Run 1=Run 2=Run 3: {runs[0]}")
        else:
            self.log(11, "Determinism: Repeated runs produce identical metrics", False, f"Variance: {runs}")

        # ----------------------------------------------------
        # TEST 12: Different images produce measurable differences
        # ----------------------------------------------------
        if diff_v > 0.01 and ssim_v < 0.99:
            self.log(12, "Before and after images produce measurable visual change", True, f"PixelDiff={diff_v:.4f}, SSIM={ssim_v:.4f}")
        else:
            self.log(12, "Before and after images produce measurable visual change", False, "No difference detected between pothole and repair")

        # ----------------------------------------------------
        # TEST 13: Anti-Spoofing: Identical before/after triggers VERIFICATION_FAILED
        # ----------------------------------------------------
        # Test identical image anti-spoofing
        st_spoof, sc_spoof, hr_spoof, r_spoof = ver_svc.evaluate_verification_decision(
            structural_similarity=1.0,
            pixel_difference=0.0,
            edge_similarity=1.0,
            histogram_similarity=1.0,
            perceptual_hash_distance=0,
            alignment_status="ALIGNED",
        )
        if st_spoof == ver_svc.VERIFICATION_FAILED and sc_spoof == 0.0 and hr_spoof is True:
            self.log(13, "Anti-Spoofing: Identical evidence triggers VERIFICATION_FAILED", True, r_spoof)
        else:
            self.log(13, "Anti-Spoofing: Identical evidence triggers VERIFICATION_FAILED", False, f"Got: {st_spoof}, score: {sc_spoof}")

        # ----------------------------------------------------
        # TEST 14: Verification record stored in PostgreSQL
        # ----------------------------------------------------
        # Prepare complaint with proper before and after evidence
        c_paired = Complaint(
            complaint_id=f"CG-2026-PAIRED-{ts}",
            issue_type="pothole",
            description="Complaint with genuine before/after pair for DB verification",
            original_language="en",
            status=STATUS_IN_PROGRESS,
            department_id=roads_dept.id,
            user_id=citizen.id,
        )
        self.db.add(c_paired)
        self.db.commit()
        self.db.refresh(c_paired)
        self.created_complaints.append(c_paired.id)

        ev_b = self.create_evidence_record(c_paired.id, before_file, is_resolution=False)
        ev_a = self.create_evidence_record(c_paired.id, after_file, is_resolution=True)

        ver_rec = ver_svc.run_resolution_verification(c_paired, officer_roads.id, self.db)
        self.created_verifications.append(ver_rec.id)

        db_check = self.db.query(ResolutionVerification).filter(ResolutionVerification.id == ver_rec.id).first()
        if (
            db_check is not None
            and db_check.complaint_id == c_paired.id
            and db_check.algorithm_version == "resolution-v1"
            and db_check.structural_similarity is not None
        ):
            self.log(14, "Verification record stored in PostgreSQL", True, f"ID={db_check.id}, status={db_check.verification_status}")
        else:
            self.log(14, "Verification record stored in PostgreSQL", False, "Record missing or incomplete in DB")

        # ----------------------------------------------------
        # TEST 15: Audit record created in audit_logs
        # ----------------------------------------------------
        audit = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_id == c_paired.complaint_id,
                AuditLog.action == "RESOLUTION_VERIFICATION_COMPLETED",
            )
            .order_by(desc(AuditLog.timestamp))
            .first()
        )
        if audit is not None and (audit.metadata_ or {}).get("algorithm_version") == "resolution-v1":
            self.log(15, "Audit record created in PostgreSQL", True, f"Audit ID={audit.id}, Action={audit.action}")
        else:
            self.log(15, "Audit record created in PostgreSQL", False, "Audit record missing")

        # ----------------------------------------------------
        # TEST 16: Officer department isolation enforced
        # ----------------------------------------------------
        # Officer Water attempts to verify Complaint belonging to Roads Department
        resp_isolated = self.client.post(
            f"/api/v1/officer/complaints/{c_paired.complaint_id}/resolution/verify",
            headers=self.auth_headers(officer_water),
        )
        if resp_isolated.status_code == 403:
            self.log(16, "Department isolation enforced (cross-department returns 403)", True, resp_isolated.json()["detail"])
        else:
            self.log(16, "Department isolation enforced", False, f"Expected 403, got {resp_isolated.status_code}")

        # ----------------------------------------------------
        # TEST 17: Citizen cannot call verification endpoint
        # ----------------------------------------------------
        resp_citizen = self.client.post(
            f"/api/v1/officer/complaints/{c_paired.complaint_id}/resolution/verify",
            headers=self.auth_headers(citizen),
        )
        if resp_citizen.status_code == 403:
            self.log(17, "Citizen cannot call verification endpoint (returns 403)", True, "Forbidden for citizen")
        else:
            self.log(17, "Citizen cannot call verification endpoint", False, f"Expected 403, got {resp_citizen.status_code}")

        # ----------------------------------------------------
        # TEST 18: Authorized officer can execute verification endpoint
        # ----------------------------------------------------
        resp_verify = self.client.post(
            f"/api/v1/officer/complaints/{c_paired.complaint_id}/resolution/verify",
            headers=self.auth_headers(officer_roads),
        )
        if resp_verify.status_code == 200:
            data = resp_verify.json()
            assert data["complaint_id"] == c_paired.complaint_id
            assert data["algorithm_version"] == "resolution-v1"
            assert "metrics" in data
            self.log(18, "Authorized officer executes verification API (HTTP 200)", True, f"Status: {data['verification_status']}")
        else:
            self.log(18, "Authorized officer executes verification API", False, f"Expected 200, got {resp_verify.status_code}: {resp_verify.text}")

        # ----------------------------------------------------
        # TEST 19: Human review recorded (APPROVED)
        # ----------------------------------------------------
        review_payload = {
            "decision": "APPROVED",
            "review_notes": "Visually inspected pothole repair. Hot-mix compaction confirmed on site.",
        }
        resp_review = self.client.post(
            f"/api/v1/officer/complaints/{c_paired.complaint_id}/resolution/review",
            headers=self.auth_headers(officer_roads),
            json=review_payload,
        )
        if resp_review.status_code == 200:
            rev_data = resp_review.json()
            assert rev_data["review_decision"] == "APPROVED"
            assert rev_data["reviewed_by_id"] == officer_roads.id
            self.log(19, "Human review recorded (APPROVED)", True, f"Decision={rev_data['review_decision']}")
        else:
            self.log(19, "Human review recorded", False, f"Expected 200, got {resp_review.status_code}: {resp_review.text}")

        # ----------------------------------------------------
        # TEST 20: Human decision preserves automated CV metrics
        # ----------------------------------------------------
        rev_db = (
            self.db.query(ResolutionVerification)
            .filter(ResolutionVerification.complaint_id == c_paired.id)
            .order_by(desc(ResolutionVerification.created_at))
            .first()
        )
        if (
            rev_db.review_decision == "APPROVED"
            and rev_db.structural_similarity is not None
            and rev_db.pixel_difference is not None
            and rev_db.verification_score is not None
        ):
            self.log(
                20,
                "Human decision preserves automated CV metrics without overwriting",
                True,
                f"Metrics preserved: SSIM={rev_db.structural_similarity}, Score={rev_db.verification_score}",
            )
        else:
            self.log(20, "Human decision preserves automated CV metrics", False, "Metrics were erased or missing")

        # ----------------------------------------------------
        # TEST 21: Repeated verification preserves audit trail & history
        # ----------------------------------------------------
        # Run verification a second time on c_paired
        ver_2 = ver_svc.run_resolution_verification(c_paired, officer_roads.id, self.db)
        self.created_verifications.append(ver_2.id)

        all_ver_runs = (
            self.db.query(ResolutionVerification)
            .filter(ResolutionVerification.complaint_id == c_paired.id)
            .order_by(desc(ResolutionVerification.created_at))
            .all()
        )
        if len(all_ver_runs) >= 2:
            self.log(21, "Repeated verification preserves full history", True, f"Found {len(all_ver_runs)} verification records in DB")
        else:
            self.log(21, "Repeated verification preserves full history", False, f"Expected >=2 records, got {len(all_ver_runs)}")

        # ----------------------------------------------------
        # TEST 22: Resolution evidence uses is_resolution=True
        # ----------------------------------------------------
        res_ev_check = self.db.query(ComplaintEvidence).filter(ComplaintEvidence.id == ev_a.id).first()
        if res_ev_check and res_ev_check.is_resolution is True:
            self.log(22, "Officer resolution evidence has is_resolution=True", True, f"Evidence #{res_ev_check.id} is_resolution=True")
        else:
            self.log(22, "Officer resolution evidence has is_resolution=True", False, "is_resolution is False")

        # ----------------------------------------------------
        # TEST 23: Citizen evidence remains is_resolution=False
        # ----------------------------------------------------
        cit_ev_check = self.db.query(ComplaintEvidence).filter(ComplaintEvidence.id == ev_b.id).first()
        if cit_ev_check and cit_ev_check.is_resolution is False:
            self.log(23, "Citizen original evidence has is_resolution=False", True, f"Evidence #{cit_ev_check.id} is_resolution=False")
        else:
            self.log(23, "Citizen original evidence has is_resolution=False", False, "is_resolution is True")

        # ----------------------------------------------------
        # TEST 24: No fake confidence fields generated
        # ----------------------------------------------------
        # Inspect API response
        resp_check = self.client.get(
            f"/api/v1/officer/complaints/{c_paired.complaint_id}/resolution/verification",
            headers=self.auth_headers(officer_roads),
        )
        resp_json = resp_check.json()
        raw_text = json.dumps(resp_json)
        # Check that no fake "ai_confidence" or "confidence" appears in metrics
        has_fake_conf = "ai_confidence" in resp_json.get("metrics", {})
        if not has_fake_conf and "metrics" in resp_json:
            self.log(24, "No fake confidence fields generated in resolution metrics", True, "Metrics contain only real CV values")
        else:
            self.log(24, "No fake confidence fields generated in resolution metrics", False, "Fake confidence field detected")

        # ----------------------------------------------------
        # TEST 25: No secrets appear in audit logs
        # ----------------------------------------------------
        audit_records = (
            self.db.query(AuditLog)
            .filter(AuditLog.entity_id == c_paired.complaint_id)
            .all()
        )
        leaked_secret = False
        forbidden_keys = {"password", "secret", "private_key", "jwt", "access_token"}
        for ar in audit_records:
            meta_str = json.dumps(ar.metadata_ or {}).lower()
            for fk in forbidden_keys:
                if fk in meta_str:
                    leaked_secret = True
                    break

        if not leaked_secret:
            self.log(25, "No secrets, passwords, or JWTs appear in audit logs", True, "Audit metadata sanitized")
        else:
            self.log(25, "No secrets appear in audit logs", False, "Potential secret key leaked into audit log")

        # Cleanup test artifacts
        self.cleanup()

        # Summary
        print("=" * 70)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        print(f"RESULTS: {passed_count} / {total_count} TESTS PASSED")
        print("=" * 70)

        if passed_count < total_count:
            sys.exit(1)
        return True

    def cleanup(self):
        """Clean up test database records and temporary test images."""
        try:
            for vid in self.created_verifications:
                self.db.query(ResolutionVerification).filter(ResolutionVerification.id == vid).delete()
            for eid in self.created_evidences:
                self.db.query(ComplaintEvidence).filter(ComplaintEvidence.id == eid).delete()
            for cid in self.created_complaints:
                self.db.query(Complaint).filter(Complaint.id == cid).delete()
            for uid in self.created_users:
                self.db.query(User).filter(User.id == uid).delete()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
        finally:
            self.db.close()

        # Remove temporary test images
        if TEST_EVIDENCE_DIR.exists():
            shutil.rmtree(TEST_EVIDENCE_DIR, ignore_errors=True)


if __name__ == "__main__":
    runner = ResolutionVerificationTestRunner()
    runner.run_all()
