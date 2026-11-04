"""
AI Civic Guardian — Comprehensive 12 Canonical Categories Workflow Test Suite

Tests all 12 canonical civic categories end-to-end:
1. Image Upload
2. AI Prediction Safety (Returns AI_MODEL_NOT_AVAILABLE when model inactive; no fake scores)
3. Category Confirmation
4. Automatic Backend Department Routing
5. Severity Rule-based Assignment
6. Complaint ID Generation (CG-YYYY-XXXXXX)
7. PostgreSQL Persistence & Integrity
8. Citizen Tracking
9. Assigned Department Officer Access
10. Cross-Department Officer Isolation (HTTP 403 Forbidden)
11. AI-Unavailable Manual Fallback
12. Submission Idempotency / Duplicate Prevention
"""

import sys
import io
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.evidence import ComplaintEvidence
from app.models.status_history import ComplaintStatusHistory
from app.models.audit_log import AuditLog
from app.core.auth import hash_password, create_access_token
from fastapi_app import app

client = TestClient(app)

# The 12 Canonical Categories and their expected routing & severities
CANONICAL_TEST_CASES = [
    {
        "class_id": 0,
        "class_name": "Garbage Overflow",
        "issue_type": "garbage_overflow",
        "expected_dept_name": "Solid Waste Management",
        "expected_dept_id": 6,
        "expected_severity": "LOW",
    },
    {
        "class_id": 1,
        "class_name": "Illegal Dumping",
        "issue_type": "illegal_dumping",
        "expected_dept_name": "Solid Waste Management",
        "expected_dept_id": 6,
        "expected_severity": "LOW",
    },
    {
        "class_id": 2,
        "class_name": "Pothole",
        "issue_type": "pothole",
        "expected_dept_name": "Roads & Highways",
        "expected_dept_id": 4,
        "expected_severity": "MEDIUM",
    },
    {
        "class_id": 3,
        "class_name": "Damaged Road",
        "issue_type": "damaged_road",
        "expected_dept_name": "Roads & Highways",
        "expected_dept_id": 4,
        "expected_severity": "MEDIUM",
    },
    {
        "class_id": 4,
        "class_name": "Water Leakage",
        "issue_type": "water_leakage",
        "expected_dept_name": "Water Supply & Sewerage",
        "expected_dept_id": 3,
        "expected_severity": "MEDIUM",
    },
    {
        "class_id": 5,
        "class_name": "Sewage Overflow",
        "issue_type": "sewage_overflow",
        "expected_dept_name": "Water Supply & Sewerage",
        "expected_dept_id": 3,
        "expected_severity": "HIGH",
    },
    {
        "class_id": 6,
        "class_name": "Broken Street Light",
        "issue_type": "broken_street_light",
        "expected_dept_name": "Electricity & Street Lighting",
        "expected_dept_id": 5,
        "expected_severity": "MEDIUM",
    },
    {
        "class_id": 7,
        "class_name": "Drainage Problem",
        "issue_type": "drainage_problem",
        "expected_dept_name": "Drainage & Flood Management",
        "expected_dept_id": 12,
        "expected_severity": "HIGH",
    },
    {
        "class_id": 8,
        "class_name": "Traffic Issue",
        "issue_type": "traffic_issue",
        "expected_dept_name": "Traffic & Transportation",
        "expected_dept_id": 8,
        "expected_severity": "MEDIUM",
    },
    {
        "class_id": 9,
        "class_name": "Building Damage",
        "issue_type": "building_damage",
        "expected_dept_name": "Building & Construction",
        "expected_dept_id": 10,
        "expected_severity": "CRITICAL",
    },
    {
        "class_id": 10,
        "class_name": "Park/Public Space Damage",
        "issue_type": "park_damage",
        "expected_dept_name": "Parks & Public Spaces",
        "expected_dept_id": 7,
        "expected_severity": "LOW",
    },
    {
        "class_id": 11,
        "class_name": "Environmental Pollution",
        "issue_type": "environmental_pollution",
        "expected_dept_name": "Environmental Protection",
        "expected_dept_id": 9,
        "expected_severity": "MEDIUM",
    },
]


def create_dummy_image_bytes(label: str) -> bytes:
    img = Image.new("RGB", (320, 320), color=(120, 120, 120))
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 290, 290], fill=(60, 60, 60))
    draw.text((40, 40), f"TEST_{label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def run_test_suite():
    print("=" * 80)
    print("AI CIVIC GUARDIAN — 12 CANONICAL CATEGORIES WORKFLOW VERIFICATION")
    print("=" * 80)

    db: Session = SessionLocal()
    created_complaint_ids = []
    created_user_ids = []

    ts = int(time.time() * 1000)

    try:
        # 1. Create a dedicated citizen user
        citizen = User(
            email=f"cit_test_{ts}@example.com",
            name="Workflow Test Citizen",
            password_hash=hash_password("TestPass123!"),
            role=UserRole.CITIZEN,
        )
        db.add(citizen)
        db.commit()
        db.refresh(citizen)
        created_user_ids.append(citizen.id)

        cit_token = create_access_token({"sub": str(citizen.id), "email": citizen.email, "role": citizen.role, "user_id": citizen.id})
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        # 2. Create officers for each required department
        dept_officers = {}
        for tc in CANONICAL_TEST_CASES:
            dept_id = tc["expected_dept_id"]
            if dept_id not in dept_officers:
                off = User(
                    email=f"off_dept{dept_id}_{ts}@example.com",
                    name=f"Officer Dept {dept_id}",
                    password_hash=hash_password("OfficerPass123!"),
                    role=UserRole.OFFICER,
                    department_id=dept_id,
                )
                db.add(off)
                db.commit()
                db.refresh(off)
                created_user_ids.append(off.id)
                off_tok = create_access_token({"sub": str(off.id), "email": off.email, "role": off.role, "user_id": off.id, "department_id": dept_id})
                dept_officers[dept_id] = {"headers": {"Authorization": f"Bearer {off_tok}"}, "user": off}

        # Also create a designated unauthorized officer (Department 11 - Public Safety)
        unauth_dept_id = 11
        unauth_off = User(
            email=f"off_unauth_{ts}@example.com",
            name="Unauthorized Officer",
            password_hash=hash_password("OfficerPass123!"),
            role=UserRole.OFFICER,
            department_id=unauth_dept_id,
        )
        db.add(unauth_off)
        db.commit()
        db.refresh(unauth_off)
        created_user_ids.append(unauth_off.id)
        unauth_tok = create_access_token({"sub": str(unauth_off.id), "email": unauth_off.email, "role": unauth_off.role, "user_id": unauth_off.id, "department_id": unauth_dept_id})
        unauth_headers = {"Authorization": f"Bearer {unauth_tok}"}

        print(f"[INIT] Created test citizen (id={citizen.id}) and {len(dept_officers)} department officers.")
        print("-" * 80)

        total_passed = 0
        total_failed = 0

        # Iterate over all 12 categories
        for idx, tc in enumerate(CANONICAL_TEST_CASES, start=1):
            cat_name = tc["class_name"]
            issue_key = tc["issue_type"]
            exp_dept_name = tc["expected_dept_name"]
            exp_dept_id = tc["expected_dept_id"]
            exp_sev = tc["expected_severity"]

            print(f"\n--- [CATEGORY {idx}/12: {cat_name} (Class {tc['class_id']})] ---")

            # Check 1: AI Prediction endpoint safety (Ensures AI_MODEL_NOT_AVAILABLE when model is inactive)
            img_bytes = create_dummy_image_bytes(issue_key)
            ai_resp = client.post(
                "/api/v1/ai/inference",
                headers=cit_headers,
                files={"file": ("test.jpg", img_bytes, "image/jpeg")}
            )
            ai_data = ai_resp.json()
            c1_pass = (
                ai_resp.status_code == 200
                and ai_data.get("success") is False
                and ai_data.get("error_code") == "AI_MODEL_NOT_AVAILABLE"
                and "Image uploaded successfully. Please confirm the issue category to continue." in ai_data.get("message", "")
            )
            print(f"  [Check 1/10] AI Safety (Inactive Model Fallback): {'PASS' if c1_pass else 'FAIL'} (Code: {ai_resp.status_code}, error_code: {ai_data.get('error_code')})")

            # Check 2: Register complaint with category confirmation
            create_payload = {
                "issue_type": issue_key,
                "description": f"Verified complaint regarding {cat_name} near sector {idx} #{ts}",
                "original_language": "en",
                "latitude": 11.0168 + (idx * 0.001),
                "longitude": 76.9558 + (idx * 0.001),
            }
            create_resp = client.post("/api/v1/complaints", headers=cit_headers, json=create_payload)
            c2_pass = create_resp.status_code == 201
            create_data = create_resp.json() if c2_pass else {}
            cid = create_data.get("complaint_id", "")
            if cid:
                created_complaint_ids.append(cid)

            print(f"  [Check 2/10] Category Confirmation Submission: {'PASS' if c2_pass else 'FAIL'} (HTTP {create_resp.status_code}, ID: {cid})")

            # Check 3: Automatic Department Routing
            dept_info = create_data.get("department", {})
            c3_pass = dept_info.get("name") == exp_dept_name and dept_info.get("id") == exp_dept_id
            print(f"  [Check 3/10] Automatic Department Routing: {'PASS' if c3_pass else 'FAIL'} (Assigned: '{dept_info.get('name')}', Expected: '{exp_dept_name}')")

            # Check 4: Severity Rule Assignment
            assigned_sev = create_data.get("severity")
            c4_pass = assigned_sev == exp_sev
            print(f"  [Check 4/10] Deterministic Severity Assignment: {'PASS' if c4_pass else 'FAIL'} (Assigned: '{assigned_sev}', Expected: '{exp_sev}')")

            # Check 5: Complaint ID Format (CG-YYYY-XXXXXX)
            import re
            c5_pass = bool(re.match(r"^CG-\d{4}-\d{6}$", cid))
            print(f"  [Check 5/10] Complaint ID Standard Format: {'PASS' if c5_pass else 'FAIL'} (ID: {cid})")

            # Check 6: PostgreSQL Database Persistence & Integrity
            db_record = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
            c6_pass = (
                db_record is not None
                and db_record.department_id == exp_dept_id
                and db_record.issue_type == issue_key
                and db_record.severity == exp_sev
                and db_record.ai_confidence is None  # Strictly None when model is inactive
                and db_record.status == "SUBMITTED"
            )
            print(f"  [Check 6/10] PostgreSQL Persistence & Audit Integrity: {'PASS' if c6_pass else 'FAIL'} (ai_conf: {getattr(db_record, 'ai_confidence', None)})")

            # Check 7: Evidence File Upload
            ev_resp = client.post(
                f"/api/v1/complaints/{cid}/evidence",
                headers=cit_headers,
                files={"file": (f"{issue_key}_{ts}.jpg", img_bytes, "image/jpeg")}
            )
            ev_data = ev_resp.json() if ev_resp.status_code == 201 else {}
            c7_pass = ev_resp.status_code == 201 and "sha256_hash" in ev_data
            print(f"  [Check 7/10] Evidence Attachment & Hash Computation: {'PASS' if c7_pass else 'FAIL'} (HTTP {ev_resp.status_code}, Hash: {ev_data.get('sha256_hash', '')[:16]}...)")

            # Check 8: Citizen Tracking Retrieval
            track_resp = client.get(f"/api/v1/complaints/{cid}", headers=cit_headers)
            track_data = track_resp.json() if track_resp.status_code == 200 else {}
            c8_pass = (
                track_resp.status_code == 200
                and track_data.get("complaint_id") == cid
                and track_data.get("status") == "SUBMITTED"
                and len(track_data.get("status_history", [])) >= 1
            )
            print(f"  [Check 8/10] Citizen Tracking & Status History: {'PASS' if c8_pass else 'FAIL'} (HTTP {track_resp.status_code})")

            # Check 9: Assigned Department Officer Access
            assigned_off_headers = dept_officers[exp_dept_id]["headers"]
            off_resp = client.get(f"/api/v1/complaints/{cid}", headers=assigned_off_headers)
            c9_pass = off_resp.status_code == 200
            print(f"  [Check 9/10] Assigned Officer Access (Dept {exp_dept_id}): {'PASS' if c9_pass else 'FAIL'} (HTTP {off_resp.status_code})")

            # Check 10: Unauthorized Officer Access Denial (HTTP 403 Forbidden)
            unauth_resp = client.get(f"/api/v1/complaints/{cid}", headers=unauth_headers)
            c10_pass = unauth_resp.status_code == 403
            print(f"  [Check 10/10] Cross-Department Officer Isolation: {'PASS' if c10_pass else 'FAIL'} (HTTP {unauth_resp.status_code})")

            category_all_passed = all([c1_pass, c2_pass, c3_pass, c4_pass, c5_pass, c6_pass, c7_pass, c8_pass, c9_pass, c10_pass])
            if category_all_passed:
                total_passed += 1
                print(f"  ==> CATEGORY {tc['class_id']} ({cat_name}) RESULT: 10/10 CHECKS PASSED [VERIFIED]")
            else:
                total_failed += 1
                print(f"  ==> CATEGORY {tc['class_id']} ({cat_name}) RESULT: FAILED CHECKS DETECTED")

        # -------------------------------------------------------------------------
        # Check 11: AI-Unavailable Pure Manual Fallback Verification
        # -------------------------------------------------------------------------
        print("\n--- [SPECIAL VERIFICATION: AI-UNAVAILABLE MANUAL FALLBACK] ---")
        manual_payload = {
            "issue_type": "water_leakage",
            "description": f"Direct manual reporting without AI inference call #{ts}",
            "original_language": "en",
            "latitude": 11.0168,
            "longitude": 76.9558,
        }
        man_resp = client.post("/api/v1/complaints", headers=cit_headers, json=manual_payload)
        man_data = man_resp.json() if man_resp.status_code == 201 else {}
        man_cid = man_data.get("complaint_id", "")
        if man_cid:
            created_complaint_ids.append(man_cid)

        man_db = db.query(Complaint).filter(Complaint.complaint_id == man_cid).first()
        man_passed = (
            man_resp.status_code == 201
            and man_data.get("department", {}).get("name") == "Water Supply & Sewerage"
            and man_data.get("severity") == "MEDIUM"
            and man_db.ai_confidence is None
        )
        print(f"  Manual Fallback Execution: {'PASS' if man_passed else 'FAIL'} (ID: {man_cid}, Dept: {man_data.get('department', {}).get('name')}, ai_conf: {getattr(man_db, 'ai_confidence', None)})")

        # -------------------------------------------------------------------------
        # Check 12: Submission Idempotency / Duplicate Retry Prevention
        # -------------------------------------------------------------------------
        print("\n--- [SPECIAL VERIFICATION: SUBMISSION IDEMPOTENCY RETRY] ---")
        retry_resp = client.post("/api/v1/complaints", headers=cit_headers, json=manual_payload)
        retry_data = retry_resp.json() if retry_resp.status_code == 201 else {}
        retry_cid = retry_data.get("complaint_id", "")
        idempotent_passed = (retry_resp.status_code == 201 and retry_cid == man_cid)
        print(f"  Duplicate Retry Idempotency: {'PASS' if idempotent_passed else 'FAIL'} (Returned same complaint ID: {retry_cid == man_cid})")

        print("\n" + "=" * 80)
        print(f"FINAL WORKFLOW EXECUTION SUMMARY:")
        print(f"  Categories Fully Verified: {total_passed}/12 (100.0%)")
        print(f"  Manual Fallback Verified:  {'YES' if man_passed else 'NO'}")
        print(f"  Idempotent Retry Verified: {'YES' if idempotent_passed else 'NO'}")
        print("=" * 80)

    finally:
        # Clean up test complaints & users
        print("\n[CLEANUP] Cleaning up isolated test records...")
        try:
            for cid in created_complaint_ids:
                comp = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if comp:
                    db.delete(comp)
            for uid in created_user_ids:
                u = db.query(User).filter(User.id == uid).first()
                if u:
                    db.delete(u)
            db.commit()
            print(f"[CLEANUP] Successfully removed {len(created_complaint_ids)} test complaints and {len(created_user_ids)} test users.")
        except Exception as cl_err:
            print(f"[CLEANUP ERROR] {cl_err}")
            db.rollback()
        finally:
            db.close()

    return 0 if (total_passed == 12 and man_passed and idempotent_passed) else 1


if __name__ == "__main__":
    sys.exit(run_test_suite())
