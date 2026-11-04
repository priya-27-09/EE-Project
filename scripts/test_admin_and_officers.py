#!/usr/bin/env python3
"""
Automated Test Suite for AI Civic Guardian:
1. Admin Login & Full Supervision Permissions
2. All 12 Department Officer Logins & Canonical Category Department Mappings
3. Strict Department Isolation & IDOR Cross-Department Protection
4. Automatic Routing for All 12 Canonical Categories
5. Manual Category Override Department Recalculation
6. Status Changes & Notes Propagation to Citizen Tracking
7. RBAC & Security Boundary Enforcement (401 / 403)
8. Safe Isolated Test Data Cleanup
"""

import os
import sys
import uuid
import requests
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.complaint import Complaint
from app.models.status_history import ComplaintStatusHistory
from app.models.complaint_note import ComplaintNote
from app.models.audit_log import AuditLog
from app.models.user import User

BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@civic.gov")
ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "Admin@Civic2026!")
OFFICER_PASSWORD = os.getenv("DEMO_OFFICER_PASSWORD", "Officer@Civic2026!")

# Canonical 12 Categories and their target departments
CANONICAL_OFFICERS = [
    {"category": "Garbage Overflow", "email": "officer.garbage@civic.gov", "dept_id": 6, "dept_name": "Solid Waste Management"},
    {"category": "Illegal Dumping", "email": "officer.dumping@civic.gov", "dept_id": 6, "dept_name": "Solid Waste Management"},
    {"category": "Pothole", "email": "officer.pothole@civic.gov", "dept_id": 4, "dept_name": "Roads & Highways"},
    {"category": "Damaged Road", "email": "officer.road@civic.gov", "dept_id": 4, "dept_name": "Roads & Highways"},
    {"category": "Water Leakage", "email": "officer.water@civic.gov", "dept_id": 3, "dept_name": "Water Supply & Sewerage"},
    {"category": "Sewage Overflow", "email": "officer.sewage@civic.gov", "dept_id": 3, "dept_name": "Water Supply & Sewerage"},
    {"category": "Broken Street Light", "email": "officer.light@civic.gov", "dept_id": 5, "dept_name": "Electricity & Street Lighting"},
    {"category": "Drainage Problem", "email": "officer.drainage@civic.gov", "dept_id": 12, "dept_name": "Drainage & Flood Management"},
    {"category": "Traffic Issue", "email": "officer.traffic@civic.gov", "dept_id": 8, "dept_name": "Traffic & Transportation"},
    {"category": "Building Damage", "email": "officer.building@civic.gov", "dept_id": 10, "dept_name": "Building & Construction"},
    {"category": "Park/Public Space Damage", "email": "officer.park@civic.gov", "dept_id": 7, "dept_name": "Parks & Public Spaces"},
    {"category": "Environmental Pollution", "email": "officer.pollution@civic.gov", "dept_id": 9, "dept_name": "Environmental Protection"},
]

created_complaint_ids = []
created_user_ids = []


def cleanup_isolated_data():
    """Clean up only the test complaints and test users created by this suite."""
    if not created_complaint_ids and not created_user_ids:
        return
    db = SessionLocal()
    try:
        print(f"\n[*] Cleaning up {len(created_complaint_ids)} isolated test complaints...")
        for cid in created_complaint_ids:
            complaint = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
            if complaint:
                db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == complaint.id).delete()
                db.query(ComplaintNote).filter(ComplaintNote.complaint_id == complaint.id).delete()
                db.query(AuditLog).filter(AuditLog.entity_id == str(complaint.id)).delete()
                db.delete(complaint)

        for uid in created_user_ids:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                db.delete(user)

        db.commit()
        print("[OK] Test data cleanup complete.")
    except Exception as e:
        db.rollback()
        print(f"[-] Cleanup warning: {e}", file=sys.stderr)
    finally:
        db.close()


def run_tests():
    total_checks = 0
    passed_checks = 0

    def assert_check(condition: bool, description: str):
        nonlocal total_checks, passed_checks
        total_checks += 1
        if condition:
            passed_checks += 1
            print(f"  [PASS] {description}")
        else:
            print(f"  [FAIL] {description}", file=sys.stderr)
            raise AssertionError(f"Check failed: {description}")

    try:
        print("=" * 75)
        print("AI Civic Guardian — Comprehensive Admin, 12 Officers & Routing Verification")
        print("=" * 75)

        # -------------------------------------------------------------
        # STEP 1: Admin Authentication & Superuser Permissions
        # -------------------------------------------------------------
        print("\n--- STEP 1: Admin Authentication & Endpoints ---")
        login_res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert_check(login_res.status_code == 200, "Admin login succeeds with HTTP 200")
        admin_data = login_res.json()
        admin_token = admin_data.get("access_token")
        admin_role = admin_data.get("user", {}).get("role")
        assert_check(bool(admin_token), "Admin received valid access_token")
        assert_check(admin_role == "ADMIN", f"Admin user role is ADMIN (got: {admin_role})")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Check /api/v1/admin/overview
        ov_res = requests.get(f"{BASE_URL}/api/v1/admin/overview", headers=admin_headers)
        assert_check(ov_res.status_code == 200, "Admin overview returns HTTP 200")
        ov_data = ov_res.json()
        assert_check(ov_data["total_departments"] == 12, f"Overview reports 12 departments (got {ov_data['total_departments']})")
        assert_check(ov_data["total_officers"] >= 12, f"Overview reports >= 12 officers (got {ov_data['total_officers']})")

        # Check /api/v1/admin/departments
        depts_res = requests.get(f"{BASE_URL}/api/v1/admin/departments", headers=admin_headers)
        assert_check(depts_res.status_code == 200, "Admin departments list returns HTTP 200")
        depts_data = depts_res.json()
        assert_check(len(depts_data) == 12, f"All 12 departments returned (got {len(depts_data)})")

        # Check /api/v1/admin/officers
        officers_res = requests.get(f"{BASE_URL}/api/v1/admin/officers", headers=admin_headers)
        assert_check(officers_res.status_code == 200, "Admin officers list returns HTTP 200")
        officers_data = officers_res.json()
        assert_check(len(officers_data) >= 12, f"Officers count >= 12 (got {len(officers_data)})")

        # -------------------------------------------------------------
        # STEP 2: Authenticate All 12 Department Officers & Verify Identity
        # -------------------------------------------------------------
        print("\n--- STEP 2: Authenticate All 12 Department Officer Accounts ---")
        officer_tokens = {}
        for off in CANONICAL_OFFICERS:
            cat = off["category"]
            email = off["email"]
            expected_dept_id = off["dept_id"]
            expected_dept_name = off["dept_name"]

            res = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": OFFICER_PASSWORD})
            assert_check(res.status_code == 200, f"Officer login for {cat} ({email}) returns HTTP 200")
            data = res.json()
            tok = data.get("access_token")
            user_info = data.get("user", {})

            assert_check(user_info.get("role") == "OFFICER", f"Account {email} has role OFFICER")
            assert_check(user_info.get("department_id") == expected_dept_id, f"Account {email} assigned dept_id {expected_dept_id}")

            # Verify officer dashboard endpoint returns correct department
            dash_res = requests.get(f"{BASE_URL}/api/v1/officer/dashboard", headers={"Authorization": f"Bearer {tok}"})
            assert_check(dash_res.status_code == 200, f"Officer dashboard for {email} returns HTTP 200")
            dash_data = dash_res.json()
            assert_check(dash_data.get("department_id") == expected_dept_id, f"Officer dashboard department_id matches {expected_dept_id}")
            assert_check(dash_data.get("department_name") == expected_dept_name, f"Officer dashboard department_name is '{expected_dept_name}'")

            officer_tokens[email] = tok

        # -------------------------------------------------------------
        # STEP 3: Setup Test Citizen for Complaint Creation
        # -------------------------------------------------------------
        print("\n--- STEP 3: Create Citizen Account for Routing Tests ---")
        run_uid = uuid.uuid4().hex[:8]
        citizen_email = f"test_cit_{run_uid}@example.com"
        citizen_pwd = "TestCitizenPass123!"

        reg_res = requests.post(
            f"{BASE_URL}/auth/register",
            json={"name": "Test Citizen", "email": citizen_email, "password": citizen_pwd, "preferred_language": "en"},
        )
        assert_check(reg_res.status_code == 201, f"Test citizen registration returns HTTP 201 ({citizen_email})")
        citizen_user_id = reg_res.json().get("id")
        created_user_ids.append(citizen_user_id)

        cit_login_res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": citizen_email, "password": citizen_pwd},
        )
        citizen_token = cit_login_res.json().get("access_token")
        citizen_headers = {"Authorization": f"Bearer {citizen_token}"}

        # -------------------------------------------------------------
        # STEP 4: Automatic Routing for All 12 Canonical Categories
        # -------------------------------------------------------------
        print("\n--- STEP 4: Automatic Department Routing for All 12 Canonical Categories ---")
        category_complaints = {}

        for off in CANONICAL_OFFICERS:
            cat = off["category"]
            expected_dept_id = off["dept_id"]
            expected_dept_name = off["dept_name"]

            comp_payload = {
                "issue_type": cat,
                "description": f"Automated test complaint for canonical category '{cat}' routing verification.",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "original_language": "en",
            }

            c_res = requests.post(f"{BASE_URL}/api/v1/complaints", json=comp_payload, headers=citizen_headers)
            assert_check(c_res.status_code == 201, f"Complaint creation for '{cat}' returns HTTP 201")
            c_data = c_res.json()
            cid = c_data["complaint_id"]
            created_complaint_ids.append(cid)
            category_complaints[cat] = cid

            assigned_dept = c_data.get("department")
            assert_check(assigned_dept is not None, f"Complaint '{cid}' has an assigned department")
            assert_check(assigned_dept["id"] == expected_dept_id, f"'{cat}' routed to Dept ID {expected_dept_id} (got: {assigned_dept['id']})")
            assert_check(assigned_dept["name"] == expected_dept_name, f"'{cat}' routed to '{expected_dept_name}' (got: {assigned_dept['name']})")

        # -------------------------------------------------------------
        # STEP 5: Manual Category Override Recalculation
        # -------------------------------------------------------------
        print("\n--- STEP 5: Manual Category Override Department Recalculation ---")
        # Submit a complaint that citizen overrides from Garbage (Dept 6) to Broken Street Light (Dept 5)
        override_payload = {
            "issue_type": "Broken Street Light",
            "description": "Citizen manually overrode AI prediction to Broken Street Light.",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "manual_override": True,
            "original_language": "en",
        }
        ov_res = requests.post(f"{BASE_URL}/api/v1/complaints", json=override_payload, headers=citizen_headers)
        assert_check(ov_res.status_code == 201, "Overridden complaint creation returns HTTP 201")
        ov_data = ov_res.json()
        ov_cid = ov_data["complaint_id"]
        created_complaint_ids.append(ov_cid)

        assert_check(ov_data["department"]["id"] == 5, f"Overridden complaint routed to Electricity Dept ID 5 (got {ov_data['department']['id']})")
        assert_check(ov_data["department"]["name"] == "Electricity & Street Lighting", "Overridden complaint department name is Electricity & Street Lighting")

        # -------------------------------------------------------------
        # STEP 6: Department Isolation & IDOR Protection
        # -------------------------------------------------------------
        print("\n--- STEP 6: Department Isolation & IDOR Protection ---")
        pothole_cid = category_complaints["Pothole"]           # Dept 4 (Roads & Highways)
        drainage_cid = category_complaints["Drainage Problem"]   # Dept 12 (Drainage & Flood Management)

        roads_token = officer_tokens["officer.pothole@civic.gov"]
        drainage_token = officer_tokens["officer.drainage@civic.gov"]

        roads_headers = {"Authorization": f"Bearer {roads_token}"}
        drainage_headers = {"Authorization": f"Bearer {drainage_token}"}

        # 6a. Roads officer views Pothole complaint -> Should SUCCEED (200)
        view_ok = requests.get(f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}", headers=roads_headers)
        assert_check(view_ok.status_code == 200, f"Roads officer can view Roads complaint '{pothole_cid}' (HTTP 200)")

        # 6b. Drainage officer views Pothole complaint -> Must FAIL with 403 Forbidden!
        cross_view = requests.get(f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}", headers=drainage_headers)
        assert_check(cross_view.status_code == 403, f"Drainage officer blocked from viewing Roads complaint '{pothole_cid}' (HTTP 403 Forbidden)")

        # 6c. Drainage officer attempts to update status on Pothole complaint -> Must FAIL with 403 Forbidden!
        cross_patch = requests.patch(
            f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}/status",
            json={"status": "IN_PROGRESS", "note": "Unauthorized cross-department change attempt"},
            headers=drainage_headers,
        )
        assert_check(cross_patch.status_code == 403, f"Drainage officer blocked from updating Roads complaint '{pothole_cid}' (HTTP 403 Forbidden)")

        # 6d. Drainage officer attempts to add note on Pothole complaint -> Must FAIL with 403 Forbidden!
        cross_note = requests.post(
            f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}/notes",
            json={"note": "Unauthorized note on other department complaint"},
            headers=drainage_headers,
        )
        assert_check(cross_note.status_code == 403, f"Drainage officer blocked from adding note to Roads complaint '{pothole_cid}' (HTTP 403 Forbidden)")

        # -------------------------------------------------------------
        # STEP 7: Status Transition & Citizen Tracking Visibility
        # -------------------------------------------------------------
        print("\n--- STEP 7: Status Updates & Notes Propagation to Citizen Tracking ---")
        # Authorized Roads officer updates Pothole complaint status to DEPARTMENT_ASSIGNED then IN_PROGRESS
        dept_assign_patch = requests.patch(
            f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}/status",
            json={"status": "DEPARTMENT_ASSIGNED", "note": "Department acknowledged grievance."},
            headers=roads_headers,
        )
        assert_check(dept_assign_patch.status_code == 200, "Authorized officer updates status to DEPARTMENT_ASSIGNED (HTTP 200)")

        status_patch = requests.patch(
            f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}/status",
            json={"status": "IN_PROGRESS", "note": "Field engineer dispatched to fill pothole."},
            headers=roads_headers,
        )
        assert_check(status_patch.status_code == 200, "Authorized officer updates status to IN_PROGRESS (HTTP 200)")

        # Authorized officer adds an official note
        note_post = requests.post(
            f"{BASE_URL}/api/v1/officer/complaints/{pothole_cid}/notes",
            json={"note": "Work order WO-9042 issued. Asphalt batch scheduled."},
            headers=roads_headers,
        )
        assert_check(note_post.status_code == 201, f"Authorized officer adds note (HTTP 201)")

        # Citizen views complaint -> status is IN_PROGRESS and status history contains remarks
        cit_view = requests.get(f"{BASE_URL}/api/v1/complaints/{pothole_cid}", headers=citizen_headers)
        assert_check(cit_view.status_code == 200, f"Citizen views complaint '{pothole_cid}' (HTTP 200)")
        cit_comp = cit_view.json()
        assert_check(cit_comp["status"] == "IN_PROGRESS", f"Citizen sees updated status IN_PROGRESS (got: {cit_comp['status']})")
        history_remarks = [h.get("remarks") for h in cit_comp.get("status_history", []) if h.get("remarks")]
        assert_check(len(history_remarks) >= 2, f"Citizen sees status history transition remarks (count: {len(history_remarks)})")

        # Admin checks complaint history
        hist_res = requests.get(f"{BASE_URL}/api/v1/admin/complaints/{pothole_cid}/history", headers=admin_headers)
        assert_check(hist_res.status_code == 200, "Admin can view complete status history (HTTP 200)")
        hist_items = hist_res.json()
        assert_check(len(hist_items) >= 2, f"Status history recorded transitions (count: {len(hist_items)})")

        # -------------------------------------------------------------
        # STEP 8: Security & RBAC Enforcement (401 / 403)
        # -------------------------------------------------------------
        print("\n--- STEP 8: Security & RBAC Boundary Enforcement ---")
        # 8a. Invalid password -> 401
        bad_login = requests.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPassword123!"})
        assert_check(bad_login.status_code == 401, "Invalid password returns HTTP 401 Unauthorized")

        # 8b. Unauthenticated access to admin overview -> 401
        unauth_admin = requests.get(f"{BASE_URL}/api/v1/admin/overview")
        assert_check(unauth_admin.status_code == 401, "Unauthenticated access to admin endpoint returns HTTP 401")

        # 8c. Unauthenticated access to officer dashboard -> 401
        unauth_officer = requests.get(f"{BASE_URL}/api/v1/officer/dashboard")
        assert_check(unauth_officer.status_code == 401, "Unauthenticated access to officer endpoint returns HTTP 401")

        # 8d. Citizen access to admin overview -> 403
        cit_to_admin = requests.get(f"{BASE_URL}/api/v1/admin/overview", headers=citizen_headers)
        assert_check(cit_to_admin.status_code == 403, "Citizen forbidden from admin endpoint (HTTP 403)")

        # 8e. Citizen access to officer dashboard -> 403
        cit_to_officer = requests.get(f"{BASE_URL}/api/v1/officer/dashboard", headers=citizen_headers)
        assert_check(cit_to_officer.status_code == 403, "Citizen forbidden from officer endpoint (HTTP 403)")

        # 8f. Officer access to admin overview -> 403
        off_to_admin = requests.get(f"{BASE_URL}/api/v1/admin/overview", headers=roads_headers)
        assert_check(off_to_admin.status_code == 403, "Officer forbidden from admin endpoint (HTTP 403)")

        print("\n" + "=" * 75)
        print(f"[SUCCESS] ALL {passed_checks}/{total_checks} CHECKS PASSED PERFECTLY!")
        print("=" * 75)

    finally:
        cleanup_isolated_data()


if __name__ == "__main__":
    run_tests()
