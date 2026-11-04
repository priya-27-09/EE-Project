"""
Step 9 Live End-to-End Verification Script:
Performs real HTTP requests against live running servers:
FastAPI (http://127.0.0.1:8000) and Flask (http://127.0.0.1:5000).

Workflow:
1. Login as real officer via FastAPI (/auth/login).
2. Create or select an existing complaint belonging to officer's department.
3. Attach real citizen before evidence (is_resolution=False).
4. Upload a real resolution image via /resolution-evidence (is_resolution=True).
5. Verify is_resolution=True on resolution evidence.
6. Call POST /api/v1/officer/complaints/{id}/resolution/verify.
7. Receive actual computer vision metrics (SSIM, pixel difference, edge similarity, histogram similarity, pHash distance).
8. Verify persistence in PostgreSQL resolution_verifications table.
9. Confirm audit record in audit_logs.
10. Fetch officer complaint detail via GET /api/v1/officer/complaints/{id} and confirm verification result is present.
11. If status is NEEDS_HUMAN_REVIEW, perform human review via POST /api/v1/officer/complaints/{id}/resolution/review.
12. Confirm human decision (APPROVED) and notes are persisted without erasing automated metrics.
13. Load Flask officer complaint page (GET http://127.0.0.1:5000/officer/complaints/{id}) and confirm HTTP 200.
14. Load Flask citizen complaint page (GET http://127.0.0.1:5000/complaints/{id}) and confirm internal algorithm metrics/paths are NOT exposed.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import requests
import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence
from app.models.resolution_verification import ResolutionVerification
from app.models.audit_log import AuditLog
from app.core.auth import hash_password

FASTAPI_URL = "http://127.0.0.1:8000"
FLASK_URL = "http://127.0.0.1:5000"
LIVE_TEST_DIR = BASE_DIR / "uploads" / "evidence" / "live_test_step9"


def run_live_verification():
    print("=" * 80)
    print("LIVE END-TO-END VERIFICATION: AI-ASSISTED RESOLUTION EVIDENCE VERIFICATION")
    print(f"FastAPI: {FASTAPI_URL} | Flask: {FLASK_URL}")
    print("=" * 80)

    LIVE_TEST_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    try:
        # Pre-requisite: ensure a test department and officer exist
        dept = db.query(Department).filter(Department.name.ilike("%Road%")).first()
        if not dept:
            dept = Department(name="Roads & Highways", description="Roads maintenance")
            db.add(dept)
            db.commit()
            db.refresh(dept)

        ts = int(datetime.now().timestamp())
        officer_email = f"live_officer_{ts}@civic.gov"
        officer_pwd = "LiveOfficerPass@123"

        officer = User(
            name="Officer Rajesh Kumar",
            email=officer_email,
            password_hash=hash_password(officer_pwd),
            role=UserRole.OFFICER,
            department_id=dept.id,
            preferred_language="en",
        )
        db.add(officer)

        citizen = User(
            name="Citizen Anita Sharma",
            email=f"live_citizen_{ts}@example.com",
            password_hash=hash_password("CitizenPass@123"),
            role=UserRole.CITIZEN,
            preferred_language="en",
        )
        db.add(citizen)
        db.commit()
        db.refresh(officer)
        db.refresh(citizen)

        print("[OK] Test officer and citizen created in PostgreSQL.")

        # ----------------------------------------------------
        # 1. Login as officer via FastAPI
        # ----------------------------------------------------
        print("\n--- Step 1: Officer Login ---")
        login_resp = requests.post(
            f"{FASTAPI_URL}/auth/login",
            json={"email": officer_email, "password": officer_pwd},
            timeout=10,
        )
        assert login_resp.status_code == 200, f"Officer login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[PASS] Officer logged in successfully via JWT. Token length={len(token)}")

        # ----------------------------------------------------
        # 2. Citizen creates a complaint with before evidence
        # ----------------------------------------------------
        print("\n--- Step 2: Create Complaint with Citizen Before Evidence ---")
        # Generate synthetic before image (pothole)
        before_img_path = LIVE_TEST_DIR / f"before_pothole_{ts}.jpg"
        img_b = np.ones((512, 512, 3), dtype=np.uint8) * 130
        np.random.seed(101)
        noise = np.random.randint(-15, 15, (512, 512, 3), dtype=np.int16)
        img_b = np.clip(img_b.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        cv2.ellipse(img_b, (256, 256), (90, 55), 20, 0, 360, (25, 25, 25), -1)
        cv2.circle(img_b, (240, 270), 35, (15, 15, 15), -1)
        cv2.imwrite(str(before_img_path), img_b)

        # Login citizen to register complaint
        cit_login = requests.post(
            f"{FASTAPI_URL}/auth/login",
            json={"email": citizen.email, "password": "CitizenPass@123"},
            timeout=10,
        )
        cit_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        comp_payload = {
            "issue_type": "pothole",
            "description": "Hazardous road pothole near junction causing vehicle damage.",
            "original_language": "en",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        create_resp = requests.post(
            f"{FASTAPI_URL}/api/v1/complaints",
            json=comp_payload,
            headers=cit_headers,
            timeout=10,
        )
        assert create_resp.status_code == 201, f"Complaint creation failed: {create_resp.text}"
        comp_data = create_resp.json()
        complaint_id = comp_data["complaint_id"]
        print(f"[PASS] Complaint created: {complaint_id}, Department: {comp_data['department']['name']}")

        # Upload before evidence as citizen
        with open(before_img_path, "rb") as f:
            ev_resp = requests.post(
                f"{FASTAPI_URL}/api/v1/complaints/{complaint_id}/evidence",
                files={"file": ("pothole.jpg", f, "image/jpeg")},
                headers=cit_headers,
                timeout=10,
            )
        assert ev_resp.status_code == 201, f"Evidence upload failed: {ev_resp.text}"
        before_ev_data = ev_resp.json()
        print(f"[PASS] Original citizen before-evidence uploaded: ID={before_ev_data['id']}, is_resolution={before_ev_data['is_resolution']}")
        assert before_ev_data["is_resolution"] is False

        # Officer advances complaint status to IN_PROGRESS
        requests.patch(
            f"{FASTAPI_URL}/api/v1/officer/complaints/{complaint_id}/status",
            json={"status": "IN_PROGRESS", "note": "Dispatching road maintenance crew."},
            headers=headers,
            timeout=10,
        )

        # ----------------------------------------------------
        # 3. Officer uploads resolution after-evidence
        # ----------------------------------------------------
        print("\n--- Step 3: Officer Uploads Resolution After-Evidence ---")
        after_img_path = LIVE_TEST_DIR / f"after_repair_{ts}.jpg"
        img_a = np.ones((512, 512, 3), dtype=np.uint8) * 130
        np.random.seed(101)
        noise = np.random.randint(-15, 15, (512, 512, 3), dtype=np.int16)
        img_a = np.clip(img_a.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        # Fresh asphalt rectangular patch covering the pothole
        cv2.rectangle(img_a, (150, 180), (370, 330), (55, 55, 55), -1)
        cv2.imwrite(str(after_img_path), img_a)

        with open(after_img_path, "rb") as f:
            res_ev_resp = requests.post(
                f"{FASTAPI_URL}/api/v1/officer/complaints/{complaint_id}/resolution-evidence",
                files={"file": ("repaired_road.jpg", f, "image/jpeg")},
                headers=headers,
                timeout=10,
            )
        assert res_ev_resp.status_code == 201, f"Resolution evidence upload failed: {res_ev_resp.text}"
        after_ev_data = res_ev_resp.json()
        print(f"[PASS] Resolution evidence uploaded: ID={after_ev_data['id']}, is_resolution={after_ev_data['is_resolution']}")
        assert after_ev_data["is_resolution"] is True

        # ----------------------------------------------------
        # 4. Run AI-Assisted Resolution Evidence Verification
        # ----------------------------------------------------
        print("\n--- Step 4: Run AI-Assisted Resolution Evidence Verification ---")
        verify_resp = requests.post(
            f"{FASTAPI_URL}/api/v1/officer/complaints/{complaint_id}/resolution/verify",
            headers=headers,
            timeout=15,
        )
        assert verify_resp.status_code == 200, f"Verification execution failed: {verify_resp.text}"
        ver_data = verify_resp.json()
        print("[PASS] Verification executed successfully!")
        print(f"       Status: {ver_data['verification_status']}")
        print(f"       Score: {ver_data['verification_score']}")
        print(f"       Human Review Required: {ver_data['human_review_required']}")
        print(f"       Alignment: {ver_data['alignment_status']}")
        print(f"       Algorithm Version: {ver_data['algorithm_version']}")
        print(f"       Reason: {ver_data['verification_reason']}")
        print(f"       Metrics: {json.dumps(ver_data['metrics'], indent=2)}")

        assert ver_data["algorithm_version"] == "resolution-v1"
        assert ver_data["metrics"] is not None
        assert ver_data["metrics"]["structural_similarity"] is not None
        assert ver_data["metrics"]["pixel_difference"] is not None

        # ----------------------------------------------------
        # 5. Confirm Persistence & Audit Record in PostgreSQL
        # ----------------------------------------------------
        print("\n--- Step 5: Confirm PostgreSQL Database Persistence & Audit Record ---")
        comp_db = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        ver_db = (
            db.query(ResolutionVerification)
            .filter(ResolutionVerification.complaint_id == comp_db.id)
            .order_by(ResolutionVerification.created_at.desc())
            .first()
        )
        assert ver_db is not None
        print(f"[PASS] ResolutionVerification row confirmed in PostgreSQL: ID={ver_db.id}, Score={ver_db.verification_score}")

        audit_db = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_id == complaint_id,
                AuditLog.action == "RESOLUTION_VERIFICATION_COMPLETED",
            )
            .first()
        )
        assert audit_db is not None
        print(f"[PASS] Tamper-evident AuditLog confirmed in PostgreSQL: Action={audit_db.action}, User ID={audit_db.user_id}")

        # ----------------------------------------------------
        # 6. Fetch Officer Complaint Detail
        # ----------------------------------------------------
        print("\n--- Step 6: Fetch Officer Complaint Detail & Verify Presentation ---")
        detail_resp = requests.get(
            f"{FASTAPI_URL}/api/v1/officer/complaints/{complaint_id}",
            headers=headers,
            timeout=10,
        )
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["latest_verification"] is not None
        print(f"[PASS] Officer detail presents latest verification: {detail_data['latest_verification']['verification_status']}")

        # ----------------------------------------------------
        # 7. Record Human Review (if applicable)
        # ----------------------------------------------------
        if ver_data["verification_status"] == "NEEDS_HUMAN_REVIEW" or ver_data["human_review_required"]:
            print("\n--- Step 7: Record Officer Human Review ---")
            review_resp = requests.post(
                f"{FASTAPI_URL}/api/v1/officer/complaints/{complaint_id}/resolution/review",
                json={
                    "decision": "APPROVED",
                    "review_notes": "Officer visually confirmed hot-mix asphalt filling on site. Pothole completely sealed.",
                },
                headers=headers,
                timeout=10,
            )
            assert review_resp.status_code == 200, f"Review failed: {review_resp.text}"
            rev_res = review_resp.json()
            assert rev_res["review_decision"] == "APPROVED"
            assert rev_res["reviewed_by_id"] == officer.id
            print(f"[PASS] Human review recorded: Decision={rev_res['review_decision']}, Reviewer ID={rev_res['reviewed_by_id']}")

            # Verify automated CV metrics are still preserved intact
            assert rev_res["metrics"]["structural_similarity"] == ver_data["metrics"]["structural_similarity"]
            print("[PASS] Automated computer vision metrics preserved intact after human review.")

        # ----------------------------------------------------
        # 8. Test Flask Officer UI Page
        # ----------------------------------------------------
        print("\n--- Step 8: Test Flask Officer Complaint Detail UI ---")
        flask_officer_page = requests.get(
            f"{FLASK_URL}/officer/complaints/{complaint_id}",
            timeout=10,
        )
        assert flask_officer_page.status_code == 200
        assert "Resolution Evidence Verification" in flask_officer_page.text
        assert "resolution-v1" in flask_officer_page.text
        print("[PASS] Flask officer detail template rendered HTTP 200 with Resolution Verification UI.")

        # ----------------------------------------------------
        # 9. Test Flask Citizen Public Tracking Page (Privacy & Security)
        # ----------------------------------------------------
        print("\n--- Step 9: Test Flask Citizen Public Tracking Page ---")
        flask_citizen_page = requests.get(
            f"{FLASK_URL}/complaints/{complaint_id}",
            timeout=10,
        )
        assert flask_citizen_page.status_code == 200
        # Ensure internal metrics (e.g., SSIM, pHash, raw formulas) are NOT leaked to public page
        assert "pHash Hamming" not in flask_citizen_page.text
        assert "Pixel Diff (MAD)" not in flask_citizen_page.text
        print("[PASS] Citizen tracking page rendered HTTP 200 without leaking internal CV diagnostic metrics.")

        print("\n" + "=" * 80)
        print("ALL LIVE VERIFICATION CHECKS PASSED SUCCESSFULLY (100%)")
        print("=" * 80)
        return True

    finally:
        db.close()
        # Clean up temporary test files
        if LIVE_TEST_DIR.exists():
            import shutil
            shutil.rmtree(LIVE_TEST_DIR, ignore_errors=True)


if __name__ == "__main__":
    success = run_live_verification()
    if not success:
        sys.exit(1)
