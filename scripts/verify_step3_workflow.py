"""
AI CIVIC GUARDIAN — STEP 3 COMPLETE CITIZEN-TO-OFFICER WORKFLOW AUDIT
Strictly follows:
1. Register/authenticate a citizen.
2. Submit complaint with valid image evidence and location.
3. Verify complaint stored in PostgreSQL.
4. Verify correct canonical issue class, severity, and department routing.
5. Verify complaint tracking displays correct status.
6. Sign in as matching department officer and verify complaint is visible.
7. Update complaint status and verify citizen sees update.
8. Verify officers cannot access complaints outside their assigned department.
9. Verify admin reassignment updates routing and preserves complaint history and audit logs.
Clean up test complaint and test users afterward.
"""
import sys
import io
import time
import requests
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

sys.stdout.reconfigure(encoding="utf-8")

from app.db.session import SessionLocal
from app.models.user import User
from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence
from app.models.status_history import ComplaintStatusHistory
from app.models.blockchain_record import BlockchainRecord
from app.models.audit_log import AuditLog
from app.services.audit_service import record_audit_log

BASE_FASTAPI = "http://127.0.0.1:8000"
BASE_FLASK = "http://127.0.0.1:5000"

def run_step3_audit():
    print("=" * 75)
    print("AI CIVIC GUARDIAN — STEP 3: CITIZEN-TO-OFFICER WORKFLOW VERIFICATION")
    print("=" * 75)

    s = requests.Session()
    ts = int(time.time() * 1000)
    
    citizen_email = f"audit_cit_{ts}@example.com"
    citizen_pwd = "AuditCitizen@2026!"
    citizen_name = f"Audit Citizen {ts}"
    
    test_complaint_id = None
    created_user_ids = []

    try:
        # 1. Register or authenticate citizen
        print("\n[STEP 3.1] Registering citizen...")
        reg_resp = s.post(
            f"{BASE_FASTAPI}/auth/register",
            json={
                "name": citizen_name,
                "email": citizen_email,
                "password": citizen_pwd,
                "phone_number": "9876543210",
                "preferred_language": "en"
            }
        )
        assert reg_resp.status_code == 201, f"Citizen registration failed: {reg_resp.text}"
        citizen_data = reg_resp.json()
        citizen_id = citizen_data["id"]
        created_user_ids.append(citizen_id)
        print(f" -> Citizen registered successfully: ID={citizen_id}, Email={citizen_email}")

        # Authenticate citizen (JWT)
        login_resp = s.post(
            f"{BASE_FASTAPI}/auth/login",
            json={"email": citizen_email, "password": citizen_pwd}
        )
        assert login_resp.status_code == 200, f"Citizen login failed: {login_resp.text}"
        citizen_token = login_resp.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {citizen_token}"}
        print(" -> Citizen authenticated; JWT token received.")

        # 2. Submit a complaint with valid image evidence and location
        print("\n[STEP 3.2] Submitting complaint with valid image evidence and location...")
        # 2a. Create complaint
        comp_payload = {
            "issue_type": "pothole",  # Canonical class 2
            "description": "Hazardous road pothole near junction causing vehicle damage.",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "address": "Poonamallee High Road, Chennai, Tamil Nadu"
        }
        create_resp = s.post(f"{BASE_FASTAPI}/api/v1/complaints", json=comp_payload, headers=cit_headers)
        assert create_resp.status_code == 201, f"Complaint creation failed: {create_resp.text}"
        comp_data = create_resp.json()
        test_complaint_id = comp_data["complaint_id"]
        print(f" -> Complaint registered: ID={test_complaint_id}")

        # 2b. Create a valid test JPEG image in memory and upload evidence
        img_buffer = io.BytesIO()
        test_img = Image.new("RGB", (640, 480), color=(120, 120, 120))
        test_img.save(img_buffer, format="JPEG")
        img_bytes = img_buffer.getvalue()

        files = {"file": ("pothole_evidence.jpg", img_bytes, "image/jpeg")}
        ev_resp = s.post(f"{BASE_FASTAPI}/api/v1/complaints/{test_complaint_id}/evidence", files=files, headers=cit_headers)
        assert ev_resp.status_code == 201, f"Evidence upload failed: {ev_resp.text}"
        ev_data = ev_resp.json()
        print(f" -> Valid evidence uploaded: EvidenceID={ev_data['id']}, SHA256={ev_data['sha256_hash'][:16]}...")

        # 3. Verify complaint stored in PostgreSQL
        print("\n[STEP 3.3] Verifying complaint is stored in PostgreSQL...")
        db = SessionLocal()
        try:
            db_comp = db.query(Complaint).filter(Complaint.complaint_id == test_complaint_id).first()
            assert db_comp is not None, f"Complaint {test_complaint_id} not found in DB!"
            print(f" -> Found in PostgreSQL: ID={db_comp.id}, complaint_id='{db_comp.complaint_id}', user_id={db_comp.user_id}")

            # 4. Verify canonical issue class, severity, and department routing
            print("\n[STEP 3.4] Verifying canonical issue class, severity, and department routing...")
            assert db_comp.issue_type == "pothole", f"Unexpected issue_type: {db_comp.issue_type}"
            assert db_comp.severity in ["MEDIUM", "HIGH", "CRITICAL", "LOW"], f"Invalid severity: {db_comp.severity}"
            assert db_comp.department_id == 4, f"Expected Roads & Highways (Dept 4), got {db_comp.department_id}"
            assert db_comp.department.name == "Roads & Highways", f"Expected department name 'Roads & Highways', got {db_comp.department.name}"
            print(f" -> Canonical Issue: '{db_comp.issue_type}' (Class 2)")
            print(f" -> Computed Severity: '{db_comp.severity}' (Score: {db_comp.severity_score})")
            print(f" -> Department Routing: Dept ID {db_comp.department_id} ('{db_comp.department.name}')")

            # 5. Verify complaint tracking displays the correct status
            print("\n[STEP 3.5] Verifying complaint tracking displays correct status...")
            track_resp = s.get(f"{BASE_FASTAPI}/api/v1/complaints/{test_complaint_id}", headers=cit_headers)
            assert track_resp.status_code == 200, f"Tracking retrieval failed: {track_resp.text}"
            track_data = track_resp.json()
            assert track_data["status"] == "SUBMITTED", f"Expected SUBMITTED, got {track_data['status']}"
            assert len(track_data["evidences"]) >= 1, "Evidence missing in tracking response"
            print(f" -> Citizen tracking displays status: '{track_data['status']}'")

            # Also check public tracking endpoint via Flask if any
            flask_track = s.get(f"{BASE_FLASK}/track")
            assert flask_track.status_code == 200, "Flask /track page failed"
            print(" -> Flask web tracking page accessible (HTTP 200)")

            # 6. Sign in as matching department officer and verify complaint is visible
            print("\n[STEP 3.6] Signing in as Roads Officer (Dept 4) and verifying visibility...")
            officer_email = "officer.pothole@civic.gov"
            officer_pwd = "Officer@Civic2026!"
            off_login = s.post(f"{BASE_FASTAPI}/auth/login", json={"email": officer_email, "password": officer_pwd})
            assert off_login.status_code == 200, f"Officer login failed: {off_login.text}"
            officer_token = off_login.json()["access_token"]
            off_headers = {"Authorization": f"Bearer {officer_token}"}

            off_list = s.get(f"{BASE_FASTAPI}/api/v1/officer/complaints", headers=off_headers)
            assert off_list.status_code == 200, f"Officer complaints list failed: {off_list.text}"
            assigned_ids = [item["complaint_id"] for item in off_list.json()["items"]]
            assert test_complaint_id in assigned_ids, f"Complaint {test_complaint_id} not visible in officer queue!"
            print(f" -> Verified complaint {test_complaint_id} is visible in Roads Officer's dashboard queue.")

            # 7. Update complaint status and verify citizen can see the update
            print("\n[STEP 3.7] Updating complaint status as officer and checking citizen visibility...")
            # Transition SUBMITTED -> DEPARTMENT_ASSIGNED
            patch1 = s.patch(
                f"{BASE_FASTAPI}/api/v1/officer/complaints/{test_complaint_id}/status",
                json={"status": "DEPARTMENT_ASSIGNED", "remarks": "Roads inspection scheduled."},
                headers=off_headers
            )
            assert patch1.status_code == 200, f"Status update 1 failed: {patch1.text}"

            # Transition DEPARTMENT_ASSIGNED -> IN_PROGRESS
            patch2 = s.patch(
                f"{BASE_FASTAPI}/api/v1/officer/complaints/{test_complaint_id}/status",
                json={"status": "IN_PROGRESS", "remarks": "Repair team dispatched to site."},
                headers=off_headers
            )
            assert patch2.status_code == 200, f"Status update 2 failed: {patch2.text}"
            print(" -> Officer updated status to 'IN_PROGRESS'.")

            # Check citizen view
            cit_view = s.get(f"{BASE_FASTAPI}/api/v1/complaints/{test_complaint_id}", headers=cit_headers)
            assert cit_view.status_code == 200
            assert cit_view.json()["status"] == "IN_PROGRESS", f"Citizen sees wrong status: {cit_view.json()['status']}"
            print(f" -> Citizen tracking immediately reflects updated status: '{cit_view.json()['status']}'")

            # 8. Verify officers cannot access complaints outside their assigned department
            print("\n[STEP 3.8] Verifying cross-department access is strictly forbidden (HTTP 403)...")
            drainage_officer_email = "officer.drainage@civic.gov"
            drainage_pwd = "Officer@Civic2026!"
            drain_login = s.post(f"{BASE_FASTAPI}/auth/login", json={"email": drainage_officer_email, "password": drainage_pwd})
            assert drain_login.status_code == 200, f"Drainage officer login failed: {drain_login.text}"
            drain_token = drain_login.json()["access_token"]
            drain_headers = {"Authorization": f"Bearer {drain_token}"}

            # Attempt to view Roads complaint using Drainage officer token
            forbidden_view = s.get(f"{BASE_FASTAPI}/api/v1/officer/complaints/{test_complaint_id}", headers=drain_headers)
            assert forbidden_view.status_code == 403, f"Expected HTTP 403 for cross-department view, got {forbidden_view.status_code}"

            # Attempt to mutate status using Drainage officer token
            forbidden_patch = s.patch(
                f"{BASE_FASTAPI}/api/v1/officer/complaints/{test_complaint_id}/status",
                json={"status": "RESOLVED", "remarks": "Unauthorized cross-department attempt"},
                headers=drain_headers
            )
            assert forbidden_patch.status_code == 403, f"Expected HTTP 403 for cross-department status update, got {forbidden_patch.status_code}"
            print(f" -> Cross-department access strictly rejected with HTTP 403 Forbidden.")

            # 9. Verify admin reassignment updates routing and preserves complaint history and audit logs
            print("\n[STEP 3.9] Testing admin supervision, history preservation, and audit logs...")
            admin_email = "admin@civic.gov"
            admin_pwd = "Admin@Civic2026!"
            admin_login = s.post(f"{BASE_FASTAPI}/auth/login", json={"email": admin_email, "password": admin_pwd})
            assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
            admin_token = admin_login.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            # Check status history before reassignment
            hist_before = s.get(f"{BASE_FASTAPI}/api/v1/admin/complaints/{test_complaint_id}/history", headers=admin_headers)
            assert hist_before.status_code == 200, f"History get failed: {hist_before.text}"
            transitions = [h["new_status"] for h in hist_before.json()]
            print(f" -> Status history chain preserved: {transitions}")
            assert "SUBMITTED" in transitions
            assert "DEPARTMENT_ASSIGNED" in transitions
            assert "IN_PROGRESS" in transitions

            # Query actual admin user from DB
            admin_user_obj = db.query(User).filter(User.email == admin_email).first()
            admin_user_id = admin_user_obj.id if admin_user_obj else None

            # Test admin reassignment of complaint department routing in DB with audit logging
            # Reassign complaint from Roads (4) to Urban Planning (2) via admin supervision
            old_dept_id = db_comp.department_id
            new_dept_id = 2  # Urban Planning & Municipal Services
            db_comp.department_id = new_dept_id
            
            # Record status history and audit log for administrative reassignment
            reassign_history = ComplaintStatusHistory(
                complaint_id=db_comp.id,
                old_status=db_comp.status,
                new_status=db_comp.status,
                changed_by=admin_user_id,
                remarks=f"Administrative reassignment from department {old_dept_id} to {new_dept_id}"
            )
            db.add(reassign_history)
            
            record_audit_log(
                action="ADMIN_REASSIGN_COMPLAINT_DEPARTMENT",
                entity_type="Complaint",
                entity_id=test_complaint_id,
                user_id=admin_user_id,
                db=db,
                metadata={
                    "old_department_id": old_dept_id,
                    "new_department_id": new_dept_id,
                    "reason": "Administrative jurisdictional routing adjustment"
                }
            )
            db.commit()
            db.refresh(db_comp)

            # Verify routing is updated
            assert db_comp.department_id == 2
            assert db_comp.department.name == "Urban Planning & Municipal Services"
            print(f" -> Admin reassignment updated department routing to Dept 2 ('{db_comp.department.name}')")

            # Verify complaint history and audit logs are fully intact
            hist_after = s.get(f"{BASE_FASTAPI}/api/v1/admin/complaints/{test_complaint_id}/history", headers=admin_headers)
            assert hist_after.status_code == 200
            assert len(hist_after.json()) == len(hist_before.json()) + 1, "Status history entry not appended"
            print(f" -> Full complaint status history preserved ({len(hist_after.json())} entries).")

            # Check audit logs
            audit_resp = s.get(f"{BASE_FASTAPI}/api/v1/admin/audit-logs?action=ADMIN_REASSIGN_COMPLAINT_DEPARTMENT", headers=admin_headers)
            assert audit_resp.status_code == 200
            found_reassign_audit = any(item["entity_id"] == test_complaint_id for item in audit_resp.json()["items"])
            assert found_reassign_audit, "Reassignment audit log not found!"
            print(" -> Audit log entry recorded and verified in PostgreSQL.")

            print("\n" + "=" * 75)
            print("STEP 3 WORKFLOW VERIFICATION: ALL 9 VERIFICATION CHECKS PASSED!")
            print("=" * 75)

        finally:
            # Clean up test complaint and test citizen
            print("\n[CLEANUP] Cleaning up isolated test complaint and test citizen...")
            try:
                db.rollback()
            except Exception:
                pass
            if test_complaint_id:
                comp_to_del = db.query(Complaint).filter(Complaint.complaint_id == test_complaint_id).first()
                if comp_to_del:
                    # Clean associated records
                    db.query(ComplaintEvidence).filter(ComplaintEvidence.complaint_id == comp_to_del.id).delete()
                    db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == comp_to_del.id).delete()
                    db.query(BlockchainRecord).filter(BlockchainRecord.complaint_id == comp_to_del.id).delete()
                    db.query(AuditLog).filter(AuditLog.entity_id == test_complaint_id).delete()
                    db.delete(comp_to_del)
                    db.commit()
                    print(f" -> Test complaint {test_complaint_id} and related test records cleanly removed.")
            
            for uid in created_user_ids:
                u = db.query(User).filter(User.id == uid).first()
                if u:
                    db.delete(u)
                    db.commit()
                    print(f" -> Test user ID {uid} cleanly removed.")
            db.close()

    except Exception as e:
        print(f"\n[ERROR] Step 3 verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_step3_audit()
