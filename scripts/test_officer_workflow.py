import sys
import io
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.status_history import ComplaintStatusHistory
from app.models.complaint_note import ComplaintNote
from app.models.evidence import ComplaintEvidence
from app.models.audit_log import AuditLog
from app.core.auth import hash_password, create_access_token
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_AI_VERIFIED,
    STATUS_DEPARTMENT_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_NEEDS_HUMAN_REVIEW,
)
from app.i18n.translation_service import TranslationService
from fastapi_app import app as fastapi_app


class OfficerWorkflowTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db = SessionLocal()
        self.results = []
        self.created_users = []
        self.created_complaints = []

    def log(self, num: int, name: str, passed: bool, msg: str = ""):
        tag = "[PASS]" if passed else "[FAIL]"
        self.results.append({"num": num, "name": name, "passed": passed, "msg": msg})
        print(f"{tag} Test {num:02d} — {name}: {msg}")

    def create_user(self, email: str, name: str, role: str, department_id: int = None) -> User:
        pwd_hash = hash_password("OfficerPass@123")
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

    def get_token(self, email: str) -> str:
        resp = self.client.post("/auth/login", json={"email": email, "password": "OfficerPass@123"})
        assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
        return resp.json()["access_token"]

    def run(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 8: REAL OFFICER DASHBOARD & WORKFLOW TEST SUITE (19 TESTS)")
        print("=" * 80)

        ts = int(time.time() * 1000)

        # Retrieve test departments
        dept_roads = self.db.query(Department).filter(Department.name == "Roads & Highways").first()
        dept_water = self.db.query(Department).filter(Department.name == "Water Supply & Sewerage").first()
        assert dept_roads and dept_water, "Core departments must exist in database"

        # 1. Setup Users
        officer_roads = self.create_user(f"officer_roads_{ts}@civic.gov", "Officer Ramesh (Roads)", UserRole.OFFICER, dept_roads.id)
        officer_water = self.create_user(f"officer_water_{ts}@civic.gov", "Officer Suresh (Water)", UserRole.OFFICER, dept_water.id)
        citizen = self.create_user(f"citizen_user_{ts}@example.com", "Ananya Citizen", UserRole.CITIZEN)

        roads_token = self.get_token(officer_roads.email)
        water_token = self.get_token(officer_water.email)
        citizen_token = self.get_token(citizen.email)

        # 2. Setup Complaints
        # Complaint A: Roads & Highways (pothole)
        reg_a = self.client.post(
            "/api/v1/complaints",
            headers={"Authorization": f"Bearer {citizen_token}"},
            json={
                "issue_type": "pothole",
                "description": "Deep dangerous pothole on MG Road near junction.",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "original_language": "en",
            },
        )
        assert reg_a.status_code == 201, f"Failed to register complaint A: {reg_a.text}"
        comp_a_id = reg_a.json()["complaint_id"]
        self.created_complaints.append(comp_a_id)

        # Complaint B: Water Supply & Sewerage (water_leakage)
        reg_b = self.client.post(
            "/api/v1/complaints",
            headers={"Authorization": f"Bearer {citizen_token}"},
            json={
                "issue_type": "water_leakage",
                "description": "Drinking water pipeline burst and leaking clean water.",
                "latitude": 12.9750,
                "longitude": 77.5990,
                "original_language": "en",
            },
        )
        assert reg_b.status_code == 201, f"Failed to register complaint B: {reg_b.text}"
        comp_b_id = reg_b.json()["complaint_id"]
        self.created_complaints.append(comp_b_id)

        try:
            # 1. Officer authentication
            self.test_01_officer_authentication(officer_roads.email)

            # 2. Citizen rejected from officer API
            self.test_02_citizen_rejected_from_officer_api(citizen_token)

            # 3. Officer dashboard loads with real PostgreSQL counts
            self.test_03_officer_dashboard_loads(roads_token, dept_roads.id)

            # 4. Department filtering (only returns complaints belonging to officer's department)
            self.test_04_department_filtering(roads_token, comp_a_id, comp_b_id)

            # 5. Officer can retrieve own department complaint
            self.test_05_officer_can_retrieve_own_complaint(roads_token, comp_a_id)

            # 6. Officer cannot retrieve another department complaint (IDOR protection)
            self.test_06_officer_cannot_retrieve_other_dept_complaint(roads_token, comp_b_id)

            # 7. Officer can update valid status
            self.test_07_officer_can_update_valid_status(roads_token, comp_a_id)

            # 8. Invalid status transition rejected with HTTP 409
            self.test_08_invalid_status_transition_rejected(roads_token, citizen_token)

            # 9. Status history created in PostgreSQL
            self.test_09_status_history_created(comp_a_id, officer_roads.id)

            # 10. Audit record created in PostgreSQL
            self.test_10_audit_record_created(comp_a_id, officer_roads.id)

            # 11. Officer note saved in PostgreSQL
            self.test_11_officer_note_saved(roads_token, comp_a_id, officer_roads.id)

            # 12. Resolution note saved
            self.test_12_resolution_note_saved(roads_token, comp_a_id)

            # 13. RESOLVED timestamp and user stored
            self.test_13_resolved_timestamp_stored(comp_a_id, officer_roads.id)

            # 14. Citizen sees updated status in citizen tracking API
            self.test_14_citizen_sees_updated_status(citizen_token, comp_a_id)

            # 15. Multilingual officer labels work
            self.test_15_multilingual_officer_labels()

            # 16. Unauthorized access rejected (no token -> 401)
            self.test_16_unauthorized_access_rejected()

            # 17. IDOR attempt rejected (Officer Water cannot update or add note to Officer Roads complaint)
            self.test_17_idor_attempt_rejected(water_token, comp_a_id)

            # 18. Pagination & filtering works
            self.test_18_pagination_and_filtering(roads_token)

            # 19. Resolution evidence upload works
            self.test_19_resolution_evidence_upload(roads_token, comp_a_id, officer_roads.id)

        finally:
            self.cleanup()
            self.db.close()

        print("\n" + "=" * 80)
        print("STEP 8 TEST EXECUTION SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        all_passed = passed_count == total_count
        print(f"Total Tests: {total_count} | Passed: {passed_count} | Failed: {total_count - passed_count}")
        print(f"Result: {'ALL 19 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=" * 80)

        if not all_passed:
            sys.exit(1)

    # -------------------------------------------------------------------------
    # TEST IMPLEMENTATIONS
    # -------------------------------------------------------------------------

    def test_01_officer_authentication(self, officer_email: str):
        resp = self.client.post("/auth/login", json={"email": officer_email, "password": "OfficerPass@123"})
        passed = (
            resp.status_code == 200
            and "access_token" in resp.json()
            and resp.json()["user"]["role"] == "OFFICER"
            and resp.json()["user"]["department_id"] is not None
        )
        self.log(1, "Officer authentication", passed, f"Status: {resp.status_code}, User: {resp.json().get('user')}")

    def test_02_citizen_rejected_from_officer_api(self, citizen_token: str):
        resp = self.client.get(
            "/api/v1/officer/dashboard",
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        passed = resp.status_code == 403
        self.log(2, "Citizen rejected from officer API", passed, f"Status: {resp.status_code} (Expected 403 Forbidden)")

    def test_03_officer_dashboard_loads(self, roads_token: str, dept_id: int):
        resp = self.client.get(
            "/api/v1/officer/dashboard",
            headers={"Authorization": f"Bearer {roads_token}"},
        )
        data = resp.json()
        passed = (
            resp.status_code == 200
            and data.get("department_id") == dept_id
            and data.get("total_assigned") >= 1
            and "submitted" in data
            and "in_progress" in data
            and "resolved" in data
        )
        self.log(3, "Officer dashboard loads from PostgreSQL", passed, f"Total Assigned: {data.get('total_assigned')}")

    def test_04_department_filtering(self, roads_token: str, comp_roads_id: str, comp_water_id: str):
        resp = self.client.get(
            "/api/v1/officer/complaints",
            headers={"Authorization": f"Bearer {roads_token}"},
        )
        data = resp.json()
        listed_ids = [item["complaint_id"] for item in data.get("items", [])]

        has_roads = comp_roads_id in listed_ids
        has_water = comp_water_id in listed_ids

        passed = (resp.status_code == 200 and has_roads and not has_water)
        self.log(
            4,
            "Department filtering",
            passed,
            f"Roads complaint present: {has_roads}, Water complaint absent: {not has_water}",
        )

    def test_05_officer_can_retrieve_own_complaint(self, roads_token: str, comp_roads_id: str):
        resp = self.client.get(
            f"/api/v1/officer/complaints/{comp_roads_id}",
            headers={"Authorization": f"Bearer {roads_token}"},
        )
        passed = (
            resp.status_code == 200
            and resp.json().get("complaint_id") == comp_roads_id
            and resp.json().get("department", {}).get("name") == "Roads & Highways"
        )
        self.log(5, "Officer can retrieve own department complaint", passed, f"Status: {resp.status_code}")

    def test_06_officer_cannot_retrieve_other_dept_complaint(self, roads_token: str, comp_water_id: str):
        resp = self.client.get(
            f"/api/v1/officer/complaints/{comp_water_id}",
            headers={"Authorization": f"Bearer {roads_token}"},
        )
        passed = resp.status_code == 403
        self.log(
            6,
            "Officer cannot retrieve another department complaint (IDOR check)",
            passed,
            f"Status: {resp.status_code} (Expected 403 Forbidden)",
        )

    def test_07_officer_can_update_valid_status(self, roads_token: str, comp_id: str):
        # SUBMITTED -> DEPARTMENT_ASSIGNED
        patch1 = self.client.patch(
            f"/api/v1/officer/complaints/{comp_id}/status",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"status": "DEPARTMENT_ASSIGNED", "note": "Acknowledged by Roads dept."},
        )
        ok1 = patch1.status_code == 200 and patch1.json().get("status") == "DEPARTMENT_ASSIGNED"

        # DEPARTMENT_ASSIGNED -> IN_PROGRESS
        patch2 = self.client.patch(
            f"/api/v1/officer/complaints/{comp_id}/status",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"status": "IN_PROGRESS", "note": "Road repair crew assigned."},
        )
        ok2 = patch2.status_code == 200 and patch2.json().get("status") == "IN_PROGRESS"

        passed = ok1 and ok2
        self.log(7, "Officer can update valid status", passed, f"P1: {patch1.status_code}, P2: {patch2.status_code}")

    def test_08_invalid_status_transition_rejected(self, roads_token: str, citizen_token: str):
        # Create fresh complaint in SUBMITTED state
        reg = self.client.post(
            "/api/v1/complaints",
            headers={"Authorization": f"Bearer {citizen_token}"},
            json={
                "issue_type": "damaged_road",
                "description": "Cracked pavement on side street.",
                "original_language": "en",
            },
        )
        fresh_id = reg.json()["complaint_id"]
        self.created_complaints.append(fresh_id)

        # Direct jump SUBMITTED -> RESOLVED must be rejected with 409 Conflict
        patch = self.client.patch(
            f"/api/v1/officer/complaints/{fresh_id}/status",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"status": "RESOLVED", "note": "Attempting illegal direct jump"},
        )
        passed_409 = patch.status_code == 409

        # Invalid random status must be rejected with 422
        patch_bad = self.client.patch(
            f"/api/v1/officer/complaints/{fresh_id}/status",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"status": "ARBITRARY_STATUS"},
        )
        passed_422 = patch_bad.status_code == 422

        passed = passed_409 and passed_422
        self.log(
            8,
            "Invalid status transition rejected",
            passed,
            f"Jump to RESOLVED returned: {patch.status_code} (Expected 409), Bad string returned: {patch_bad.status_code} (Expected 422)",
        )

    def test_09_status_history_created(self, comp_id: str, officer_id: int):
        c = self.db.query(Complaint).filter(Complaint.complaint_id == comp_id).first()
        history = (
            self.db.query(ComplaintStatusHistory)
            .filter(ComplaintStatusHistory.complaint_id == c.id)
            .order_by(ComplaintStatusHistory.created_at.asc())
            .all()
        )
        statuses = [h.new_status for h in history]
        officer_changes = [h for h in history if h.changed_by == officer_id]

        passed = (
            len(history) >= 3
            and "SUBMITTED" in statuses
            and "DEPARTMENT_ASSIGNED" in statuses
            and "IN_PROGRESS" in statuses
            and len(officer_changes) >= 2
        )
        self.log(9, "Status history created in PostgreSQL", passed, f"History transitions: {statuses}")

    def test_10_audit_record_created(self, comp_id: str, officer_id: int):
        logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.entity_id == comp_id, AuditLog.user_id == officer_id)
            .all()
        )
        actions = [l.action for l in logs]
        passed = ("COMPLAINT_VIEWED" in actions or "STATUS_CHANGED" in actions)
        self.log(10, "Audit record created in PostgreSQL", passed, f"Actions logged: {actions}")

    def test_11_officer_note_saved(self, roads_token: str, comp_id: str, officer_id: int):
        resp = self.client.post(
            f"/api/v1/officer/complaints/{comp_id}/notes",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"note": "Field inspection team Alpha dispatched to MG Road."},
        )
        ok_api = resp.status_code == 201

        # Check DB
        c = self.db.query(Complaint).filter(Complaint.complaint_id == comp_id).first()
        notes_db = (
            self.db.query(ComplaintNote)
            .filter(ComplaintNote.complaint_id == c.id, ComplaintNote.user_id == officer_id)
            .all()
        )
        has_alpha = any("Alpha" in n.note for n in notes_db)
        passed = ok_api and len(notes_db) > 0 and has_alpha
        self.log(11, "Officer note saved in PostgreSQL", passed, f"API Status: {resp.status_code}, Total Notes: {len(notes_db)}, Found Alpha: {has_alpha}")

    def test_12_resolution_note_saved(self, roads_token: str, comp_id: str):
        note_text = "Pothole filled with hot asphalt and compacted flat. Surface inspected."
        resp = self.client.post(
            f"/api/v1/officer/complaints/{comp_id}/resolution",
            headers={"Authorization": f"Bearer {roads_token}"},
            json={"resolution_note": note_text},
        )
        ok_api = resp.status_code == 200 and resp.json().get("status") == "RESOLVED"

        c = self.db.query(Complaint).filter(Complaint.complaint_id == comp_id).first()
        passed = ok_api and c.resolution_notes == note_text and c.status == STATUS_RESOLVED
        self.log(12, "Resolution note saved in PostgreSQL", passed, f"Status: {c.status}")

    def test_13_resolved_timestamp_stored(self, comp_id: str, officer_id: int):
        c = self.db.query(Complaint).filter(Complaint.complaint_id == comp_id).first()
        passed = (c.resolved_at is not None and c.resolved_by_id == officer_id)
        self.log(
            13,
            "RESOLVED timestamp & resolver stored",
            passed,
            f"Resolved At: {c.resolved_at}, Resolver User ID: {c.resolved_by_id}",
        )

    def test_14_citizen_sees_updated_status(self, citizen_token: str, comp_id: str):
        resp = self.client.get(
            f"/api/v1/complaints/{comp_id}",
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        data = resp.json()
        passed = (resp.status_code == 200 and data.get("status") == "RESOLVED")
        self.log(14, "Citizen sees updated status from PostgreSQL", passed, f"Citizen retrieved status: {data.get('status')}")

    def test_15_multilingual_officer_labels(self):
        # Test status translations
        t_en = TranslationService.translate_status("DEPARTMENT_ASSIGNED", "en")
        t_ta = TranslationService.translate_status("DEPARTMENT_ASSIGNED", "ta")
        t_hi = TranslationService.translate_status("DEPARTMENT_ASSIGNED", "hi")

        passed = (
            t_en == "Department Assigned"
            and t_ta == "துறை ஒதுக்கப்பட்டது"
            and t_hi == "विभाग आवंटित"
        )
        self.log(15, "Multilingual officer labels work", passed, f"en: '{t_en}', ta: '{t_ta}', hi: '{t_hi}'")

    def test_16_unauthorized_access_rejected(self):
        resp_no_auth = self.client.get("/api/v1/officer/dashboard")
        resp_bad_auth = self.client.get("/api/v1/officer/dashboard", headers={"Authorization": "Bearer bad.token.here"})

        passed = resp_no_auth.status_code == 401 and resp_bad_auth.status_code == 401
        self.log(16, "Unauthorized access rejected", passed, f"No Auth: {resp_no_auth.status_code}, Bad Auth: {resp_bad_auth.status_code}")

    def test_17_idor_attempt_rejected(self, water_token: str, comp_roads_id: str):
        # Water officer attempts status patch on Roads complaint
        patch = self.client.patch(
            f"/api/v1/officer/complaints/{comp_roads_id}/status",
            headers={"Authorization": f"Bearer {water_token}"},
            json={"status": "IN_PROGRESS"},
        )

        # Water officer attempts adding note on Roads complaint
        note = self.client.post(
            f"/api/v1/officer/complaints/{comp_roads_id}/notes",
            headers={"Authorization": f"Bearer {water_token}"},
            json={"note": "Malicious cross-department note attempt"},
        )

        # Water officer attempts resolution on Roads complaint
        res = self.client.post(
            f"/api/v1/officer/complaints/{comp_roads_id}/resolution",
            headers={"Authorization": f"Bearer {water_token}"},
            json={"resolution_note": "Malicious resolution attempt"},
        )

        passed = patch.status_code == 403 and note.status_code == 403 and res.status_code == 403
        self.log(
            17,
            "IDOR attempt rejected across all mutation endpoints",
            passed,
            f"Patch: {patch.status_code}, Note: {note.status_code}, Resolution: {res.status_code} (All 403)",
        )

    def test_18_pagination_and_filtering(self, roads_token: str):
        resp = self.client.get(
            "/api/v1/officer/complaints?status=RESOLVED&page=1&page_size=5",
            headers={"Authorization": f"Bearer {roads_token}"},
        )
        data = resp.json()
        passed = (
            resp.status_code == 200
            and "total" in data
            and "items" in data
            and "page" in data
            and data["page"] == 1
            and data["page_size"] == 5
        )
        self.log(18, "Pagination and filtering works", passed, f"Total: {data.get('total')}, Page size: {data.get('page_size')}")

    def test_19_resolution_evidence_upload(self, roads_token: str, comp_id: str, officer_id: int):
        img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("repair_proof.png", io.BytesIO(img_bytes), "image/png")}

        resp = self.client.post(
            f"/api/v1/officer/complaints/{comp_id}/resolution-evidence",
            headers={"Authorization": f"Bearer {roads_token}"},
            files=files,
        )
        ok_api = resp.status_code == 201 and "sha256_hash" in resp.json()

        # Check DB
        ev = self.db.query(ComplaintEvidence).filter(ComplaintEvidence.id == resp.json().get("id")).first()
        passed = ok_api and ev is not None and ev.is_resolution is True and ev.uploaded_by == officer_id
        self.log(
            19,
            "Resolution evidence upload works with SHA-256 and is_resolution flag",
            passed,
            f"API Status: {resp.status_code}, Hash: {resp.json().get('sha256_hash', '')[:16]}..., is_resolution: {getattr(ev, 'is_resolution', False)}",
        )

    def cleanup(self):
        # Clean test complaints
        for cid in self.created_complaints:
            c = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
            if c:
                self.db.delete(c)

        # Clean test users
        for uid in self.created_users:
            u = self.db.query(User).filter(User.id == uid).first()
            if u:
                self.db.delete(u)

        self.db.commit()


if __name__ == "__main__":
    runner = OfficerWorkflowTestRunner()
    runner.run()
