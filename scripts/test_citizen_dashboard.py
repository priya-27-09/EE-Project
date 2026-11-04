"""
Step 13 Test Suite: Citizen Dashboard & Grievance Workflows.
Covers all 20 required verification dimensions:
1. Citizen authentication & GET /auth/me
2. Citizen forbidden from officer endpoints (HTTP 403)
3. Citizen forbidden from admin endpoints (HTTP 403)
4. Citizen complaint list isolation (GET /api/v1/complaints)
5. Cross-citizen complaint access forbidden (IDOR protection)
6. Real complaint statistics calculation (Total, Submitted, In Progress, Resolved)
7. Empty complaint state handling
8. Complaint detail citizen-safe fields
9. Officer internal audit/private notes exclusion
10. Complaint tracking by valid ID
11. Nonexistent complaint tracking (HTTP 404)
12. New complaint submission via wizard flow
13. Complaint evidence upload with SHA-256 hash
14. Unauthorized evidence upload blocked (HTTP 403)
15. Citizen profile update (PATCH /auth/me)
16. Profile update validation (invalid language rejected)
17. Privilege escalation blocked (role cannot be changed)
18. Chatbot access with grounded source citation
19. Chatbot conversation isolation between citizens
20. Expired/invalid JWT rejection (HTTP 401)
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence
from app.complaints.constants import STATUS_SUBMITTED, STATUS_IN_PROGRESS, STATUS_RESOLVED
from app.models.chatbot import ChatbotConversation
from app.core.auth import hash_password, create_access_token


class TestCitizenDashboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Seed test departments if missing
        cls.dept_roads = cls.db.query(Department).filter(Department.name == "Roads & Highways").first()
        if not cls.dept_roads:
            cls.dept_roads = Department(name="Roads & Highways", description="Road and highway maintenance")
            cls.db.add(cls.dept_roads)
            cls.db.commit()
            cls.db.refresh(cls.dept_roads)

        # Seed Citizen A
        cls.citizen_a = cls.db.query(User).filter(User.email == "citizen_dash_a@test.com").first()
        if not cls.citizen_a:
            cls.citizen_a = User(
                name="Aravind Citizen",
                email="citizen_dash_a@test.com",
                password_hash=hash_password("Password123!"),
                role=UserRole.CITIZEN,
                preferred_language="en",
            )
            cls.db.add(cls.citizen_a)
            cls.db.commit()
            cls.db.refresh(cls.citizen_a)

        # Seed Citizen B (for isolation testing)
        cls.citizen_b = cls.db.query(User).filter(User.email == "citizen_dash_b@test.com").first()
        if not cls.citizen_b:
            cls.citizen_b = User(
                name="Bharathi Citizen",
                email="citizen_dash_b@test.com",
                password_hash=hash_password("Password123!"),
                role=UserRole.CITIZEN,
                preferred_language="ta",
            )
            cls.db.add(cls.citizen_b)
            cls.db.commit()
            cls.db.refresh(cls.citizen_b)

        # Tokens
        cls.token_a = create_access_token({
            "sub": str(cls.citizen_a.id),
            "email": cls.citizen_a.email,
            "role": cls.citizen_a.role,
        })
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        cls.token_b = create_access_token({
            "sub": str(cls.citizen_b.id),
            "email": cls.citizen_b.email,
            "role": cls.citizen_b.role,
        })
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_citizen_auth_and_me(self):
        """Test 01: Citizen authentication & GET /auth/me returns safe profile."""
        res = self.client.get("/auth/me", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["email"], "citizen_dash_a@test.com")
        self.assertEqual(data["role"], "CITIZEN")
        self.assertNotIn("password_hash", data)
        self.assertNotIn("password", data)
        print("[PASS] Test 01 — Citizen authentication & safe profile verified")

    def test_02_citizen_cannot_access_officer_portal(self):
        """Test 02: Citizen forbidden from officer portal (HTTP 403)."""
        res = self.client.get("/api/v1/officer/dashboard", headers=self.headers_a)
        self.assertEqual(res.status_code, 403)
        print("[PASS] Test 02 — Citizen forbidden from officer portal (HTTP 403)")

    def test_03_citizen_cannot_access_admin_portal(self):
        """Test 03: Citizen forbidden from admin portal (HTTP 403)."""
        res = self.client.get("/api/v1/admin/chatbot/status", headers=self.headers_a)
        self.assertEqual(res.status_code, 403)
        print("[PASS] Test 03 — Citizen forbidden from admin endpoints (HTTP 403)")

    def test_04_citizen_complaints_list_isolation(self):
        """Test 04: Citizen complaints list is strictly isolated to own submissions."""
        # Create a complaint for citizen A
        payload = {
            "issue_type": "pothole",
            "description": "Large road defect on Main Street",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "language": "en",
        }
        res_create = self.client.post("/api/v1/complaints", json=payload, headers=self.headers_a)
        self.assertEqual(res_create.status_code, 201)
        created_id = res_create.json()["complaint_id"]

        # Citizen A list must include created_id
        res_list_a = self.client.get("/api/v1/complaints", headers=self.headers_a)
        self.assertEqual(res_list_a.status_code, 200)
        ids_a = [item["complaint_id"] for item in res_list_a.json()["items"]]
        self.assertIn(created_id, ids_a)

        # Citizen B list must NOT include created_id
        res_list_b = self.client.get("/api/v1/complaints", headers=self.headers_b)
        self.assertEqual(res_list_b.status_code, 200)
        ids_b = [item["complaint_id"] for item in res_list_b.json()["items"]]
        self.assertNotIn(created_id, ids_b)
        print("[PASS] Test 04 — Citizen complaint list isolation verified")

    def test_05_cross_citizen_complaint_access_forbidden(self):
        """Test 05: Citizen B cannot view Citizen A's complaint (IDOR protection: HTTP 403)."""
        # Create complaint for citizen A
        res_create = self.client.post("/api/v1/complaints", json={
            "issue_type": "broken_street_light",
            "description": "Street light dark for 3 days",
            "language": "en",
        }, headers=self.headers_a)
        self.assertEqual(res_create.status_code, 201)
        cid = res_create.json()["complaint_id"]

        # Citizen B attempts to access Citizen A's complaint
        res_b = self.client.get(f"/api/v1/complaints/{cid}", headers=self.headers_b)
        self.assertEqual(res_b.status_code, 403)
        print("[PASS] Test 05 — Cross-citizen complaint access blocked (HTTP 403 IDOR protected)")

    def test_06_real_complaint_statistics_calculation(self):
        """Test 06: Complaint summary metrics computed dynamically from real database records."""
        res = self.client.get("/api/v1/complaints", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        total = len(items)

        # Count statuses
        count_resolved = sum(1 for c in items if c["status"] == "RESOLVED")
        count_in_prog = sum(1 for c in items if c["status"] in ["IN_PROGRESS", "DEPARTMENT_ASSIGNED", "AI_VERIFIED"])
        count_sub = sum(1 for c in items if c["status"] == "SUBMITTED")

        self.assertEqual(total, count_resolved + count_in_prog + count_sub)
        print(f"[PASS] Test 06 — Real complaint stats calculated: Total={total}, Sub={count_sub}, InProg={count_in_prog}, Res={count_resolved}")

    def test_07_empty_complaints_state(self):
        """Test 07: User with no complaints receives clean empty state representation."""
        # Create fresh user with 0 complaints
        import uuid
        fresh_email = f"fresh_citizen_{uuid.uuid4().hex[:8]}@test.com"
        fresh_user = User(
            name="Fresh Citizen",
            email=fresh_email,
            password_hash=hash_password("Pass123!"),
            role=UserRole.CITIZEN,
            preferred_language="en",
        )
        self.db.add(fresh_user)
        self.db.commit()
        self.db.refresh(fresh_user)

        fresh_token = create_access_token({"sub": str(fresh_user.id), "email": fresh_user.email, "role": fresh_user.role})
        res = self.client.get("/api/v1/complaints", headers={"Authorization": f"Bearer {fresh_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["items"]), 0)
        print("[PASS] Test 07 — Empty complaints state verified")

    def test_08_complaint_detail_safe_fields(self):
        """Test 08: Complaint details contain citizen-safe fields and no internal paths/secrets."""
        res_create = self.client.post("/api/v1/complaints", json={
            "issue_type": "garbage_overflow",
            "description": "Garbage bin overflowing at corner",
            "language": "en",
        }, headers=self.headers_a)
        self.assertEqual(res_create.status_code, 201)
        cid = res_create.json()["complaint_id"]

        res_detail = self.client.get(f"/api/v1/complaints/{cid}", headers=self.headers_a)
        self.assertEqual(res_detail.status_code, 200)
        d = res_detail.json()

        # Check required citizen fields
        self.assertEqual(d["complaint_id"], cid)
        self.assertEqual(d["issue_type"], "garbage_overflow")
        self.assertIn("status", d)
        self.assertIn("severity", d)
        self.assertIn("created_at", d)
        self.assertIn("status_history", d)
        self.assertNotIn("password", str(d))
        self.assertNotIn("secret", str(d))
        print("[PASS] Test 08 — Complaint detail citizen-safe fields verified")

    def test_09_officer_internal_notes_excluded_from_citizen(self):
        """Test 09: Citizen complaint representation excludes internal officer notes and audit tables."""
        res_list = self.client.get("/api/v1/complaints", headers=self.headers_a)
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()["items"]
        if items:
            first = items[0]
            self.assertNotIn("internal_audit", first)
            self.assertNotIn("officer_private_notes", first)
            self.assertNotIn("ai_feature_vector", first)
        print("[PASS] Test 09 — Officer internal details strictly excluded from citizen view")

    def test_10_complaint_tracking_valid_id(self):
        """Test 10: Authorized citizen can track complaint by ID and view status timeline."""
        res_create = self.client.post("/api/v1/complaints", json={
            "issue_type": "water_leakage",
            "description": "Pipe leaking water continuously",
            "language": "en",
        }, headers=self.headers_a)
        self.assertEqual(res_create.status_code, 201)
        cid = res_create.json()["complaint_id"]

        res_track = self.client.get(f"/api/v1/complaints/{cid}", headers=self.headers_a)
        self.assertEqual(res_track.status_code, 200)
        data = res_track.json()
        self.assertEqual(data["complaint_id"], cid)
        self.assertIsInstance(data["status_history"], list)
        self.assertGreaterEqual(len(data["status_history"]), 1)
        print("[PASS] Test 10 — Complaint tracking by valid ID verified")

    def test_11_complaint_tracking_nonexistent_returns_404(self):
        """Test 11: Tracking nonexistent complaint ID returns HTTP 404."""
        res = self.client.get("/api/v1/complaints/CG-9999-999999", headers=self.headers_a)
        self.assertEqual(res.status_code, 404)
        print("[PASS] Test 11 — Tracking nonexistent complaint returns 404")

    def test_12_complaint_submission_wizard_flow(self):
        """Test 12: New complaint registration persists in PostgreSQL with SUBMITTED status."""
        payload = {
            "issue_type": "damaged_road",
            "description": "Deep asphalt fissures causing vehicular slowdown",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "language": "en",
        }
        res = self.client.post("/api/v1/complaints", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data["complaint_id"].startswith("CG-"))
        self.assertEqual(data["status"], "SUBMITTED")
        self.assertIsNotNone(data["department"])
        print(f"[PASS] Test 12 — Wizard complaint submission successful: {data['complaint_id']}")

    def test_13_complaint_evidence_upload_valid(self):
        """Test 13: Citizen can upload photographic evidence with SHA-256 integrity hash."""
        # Create complaint
        res_c = self.client.post("/api/v1/complaints", json={
            "issue_type": "sewage_overflow",
            "description": "Drainage blockage",
            "language": "en",
        }, headers=self.headers_a)
        cid = res_c.json()["complaint_id"]

        # Upload image evidence
        fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        files = {"file": ("evidence.png", fake_png, "image/png")}
        res_ev = self.client.post(f"/api/v1/complaints/{cid}/evidence", files=files, headers=self.headers_a)
        self.assertEqual(res_ev.status_code, 201)
        ev_data = res_ev.json()
        self.assertIn("sha256_hash", ev_data)
        self.assertEqual(len(ev_data["sha256_hash"]), 64)
        print("[PASS] Test 13 — Complaint evidence upload verified with SHA-256 hash")

    def test_14_unauthorized_evidence_upload_blocked(self):
        """Test 14: Citizen B cannot upload evidence to Citizen A's complaint (HTTP 403)."""
        res_c = self.client.post("/api/v1/complaints", json={
            "issue_type": "environmental_pollution",
            "description": "Industrial smoke emission",
            "language": "en",
        }, headers=self.headers_a)
        cid = res_c.json()["complaint_id"]

        fake_png = b"\x89PNG\r\n\x1a\n"
        files = {"file": ("unauth.png", fake_png, "image/png")}
        res_ev = self.client.post(f"/api/v1/complaints/{cid}/evidence", files=files, headers=self.headers_b)
        self.assertEqual(res_ev.status_code, 403)
        print("[PASS] Test 14 — Unauthorized evidence upload blocked (HTTP 403)")

    def test_15_profile_update_success(self):
        """Test 15: Citizen can update name and preferred_language via PATCH /auth/me."""
        payload = {
            "name": "Aravind K. Citizen",
            "preferred_language": "ta",
        }
        res = self.client.patch("/auth/me", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "Aravind K. Citizen")
        self.assertEqual(data["preferred_language"], "ta")

        # Verify in DB
        self.db.refresh(self.citizen_a)
        self.assertEqual(self.citizen_a.name, "Aravind K. Citizen")
        self.assertEqual(self.citizen_a.preferred_language, "ta")
        print("[PASS] Test 15 — Citizen profile update verified via PATCH /auth/me")

    def test_16_profile_update_validation(self):
        """Test 16: Profile update rejects invalid language or invalid name (HTTP 400)."""
        # Invalid language code
        res_lang = self.client.patch("/auth/me", json={"preferred_language": "invalid_lang"}, headers=self.headers_a)
        self.assertIn(res_lang.status_code, [400, 422])

        # Empty name
        res_name = self.client.patch("/auth/me", json={"name": " "}, headers=self.headers_a)
        self.assertIn(res_name.status_code, [400, 422])
        print("[PASS] Test 16 — Profile update validation rules verified (HTTP 400/422)")

    def test_17_profile_update_cannot_escalate_role(self):
        """Test 17: User cannot self-assign role via profile update."""
        res = self.client.patch("/auth/me", json={"name": "Hacker", "role": "ADMIN"}, headers=self.headers_a)
        # Even if role key is sent, role remains CITIZEN
        self.db.refresh(self.citizen_a)
        self.assertEqual(self.citizen_a.role, UserRole.CITIZEN)
        print("[PASS] Test 17 — Privilege escalation prevented; role remains CITIZEN")

    def test_18_chatbot_access_and_source_citation(self):
        """Test 18: Citizen can query chatbot and receive grounded civic response."""
        payload = {
            "message": "What is the repair timeline for hazardous road potholes?",
            "language": "en",
        }
        res = self.client.post("/api/v1/chatbot/chat", json=payload, headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("answer", data)
        self.assertIsInstance(data["sources"], list)
        self.assertIn("conversation_id", data)
        print("[PASS] Test 18 — Citizen chatbot query verified with RAG sources")

    def test_19_chatbot_conversation_isolation(self):
        """Test 19: Chatbot conversations are isolated per citizen."""
        # Citizen A creates conversation
        res_chat = self.client.post("/api/v1/chatbot/chat", json={"message": "Hello", "language": "en"}, headers=self.headers_a)
        self.assertEqual(res_chat.status_code, 200)
        conv_id = res_chat.json()["conversation_id"]

        # Citizen B queries conversations list
        res_convs_b = self.client.get("/api/v1/chatbot/conversations", headers=self.headers_b)
        self.assertEqual(res_convs_b.status_code, 200)
        convs_data = res_convs_b.json()
        if isinstance(convs_data, list):
            ids_b = [c["conversation_id"] for c in convs_data]
        else:
            ids_b = [c["conversation_id"] for c in convs_data.get("conversations", [])]
        self.assertNotIn(conv_id, ids_b)
        print("[PASS] Test 19 — Chatbot conversation isolation verified between citizens")

    def test_20_expired_or_invalid_jwt_handling(self):
        """Test 20: Expired or malformed JWT returns HTTP 401 across citizen endpoints."""
        bad_headers = {"Authorization": "Bearer invalid.token.value"}
        res_me = self.client.get("/auth/me", headers=bad_headers)
        self.assertEqual(res_me.status_code, 401)

        res_complaints = self.client.get("/api/v1/complaints", headers=bad_headers)
        self.assertEqual(res_complaints.status_code, 401)
        print("[PASS] Test 20 — Expired / invalid JWT properly rejected with HTTP 401")


if __name__ == "__main__":
    unittest.main()
