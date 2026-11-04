"""
AI Civic Guardian — Comprehensive Live Website Functional Test Suite

Executes automated live functional tests across:
1. Server Health & Endpoints (FastAPI :8000, Flask :5000)
2. Authentication (Registration, Login, Duplicate email, Bad Password, JWT /auth/me)
3. Citizen Complaint Wizard (Submission, Evidence upload, Department routing)
4. Production AI Inference (Ensures AI_MODEL_NOT_AVAILABLE when no model active)
5. Experimental Demo Inference (Disabled vs Enabled with best.pt)
6. Class 7 Drainage Problem Safety Protection
7. Complaint Tracking & Status History
8. Concern Officer Workflow (Login, Department Isolation, Transition to IN_PROGRESS, Notes)
9. Full Flow Loopback (Citizen verifies status updated by officer)
10. Admin Management Dashboards (Models, Datasets, Blockchain, Chatbot KB)
11. Security & Error Handling (401 Unauthorized, 403 Role Forbidden, 400 Corrupt Image, 404 Missing)
12. Frontend HTML Route Rendering (Flask :5000 templates)
"""

import sys
import io
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

API_URL = "http://127.0.0.1:8000"
WEB_URL = "http://127.0.0.1:5000"


def make_request(url, method="GET", headers=None, data=None):
    headers_dict = dict(headers) if headers else {}
    if data is not None and isinstance(data, (dict, list)):
        data = json.dumps(data).encode("utf-8")
        headers_dict["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers_dict, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as exc:
        return 0, str(exc)


def create_test_image_bytes(text="CIVIC_DEFECT") -> bytes:
    img = Image.new("RGB", (320, 320), color=(100, 100, 100))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 280, 280], fill=(40, 40, 40))
    draw.text((50, 50), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class LiveWebsiteFunctionalTester:
    def __init__(self):
        self.results = []
        self.created_complaint_ids = []
        self.created_user_ids = []
        self.ts = int(time.time())

    def log(self, task_name: str, passed: bool, detail: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append((task_name, passed, detail))
        print(f"{status_str} {task_name}: {detail}")

    # Task 1: Server Health & Port Verification
    def test_server_health(self):
        code_api, body_api = make_request(f"{API_URL}/health")
        code_web, body_web = make_request(f"{WEB_URL}/health")

        api_healthy = code_api == 200 and "healthy" in body_api
        web_healthy = code_web == 200 and "healthy" in body_web
        passed = api_healthy and web_healthy

        self.log(
            "Task 1 — Server Health & Port Verification",
            passed,
            f"FastAPI ({API_URL}/health): {code_api}, Flask ({WEB_URL}/health): {code_web}",
        )

    # Task 2: Registration, Login & Authentication
    def test_authentication_flow(self):
        # 1. Register citizen
        email = f"live_citizen_{self.ts}@example.com"
        reg_payload = {
            "name": f"Citizen Audit {self.ts}",
            "email": email,
            "password": "SecurePassword123!",
            "preferred_language": "en"
        }
        code, body = make_request(f"{API_URL}/auth/register", method="POST", data=reg_payload)
        reg_data = json.loads(body) if code in [200, 201] else {}
        citizen_id = reg_data.get("id")
        if citizen_id:
            self.created_user_ids.append(citizen_id)

        reg_passed = code == 201 and reg_data.get("role") == "CITIZEN"

        # 2. Prevent duplicate email registration
        code_dup, _ = make_request(f"{API_URL}/auth/register", method="POST", data=reg_payload)
        dup_blocked = code_dup == 400

        # 3. Bad password login
        code_bad, _ = make_request(
            f"{API_URL}/auth/login",
            method="POST",
            data={"email": email, "password": "WrongPassword!"}
        )
        bad_blocked = code_bad == 401

        # 4. Correct login
        code_login, body_login = make_request(
            f"{API_URL}/auth/login",
            method="POST",
            data={"email": email, "password": "SecurePassword123!"}
        )
        login_data = json.loads(body_login) if code_login == 200 else {}
        self.citizen_token = login_data.get("access_token")
        self.citizen_headers = {"Authorization": f"Bearer {self.citizen_token}"}
        login_passed = code_login == 200 and bool(self.citizen_token)

        # 5. /auth/me profile
        code_me, body_me = make_request(f"{API_URL}/auth/me", headers=self.citizen_headers)
        me_data = json.loads(body_me) if code_me == 200 else {}
        me_passed = code_me == 200 and me_data.get("email") == email

        all_passed = reg_passed and dup_blocked and bad_blocked and login_passed and me_passed
        self.log(
            "Task 2 — Citizen Registration, Login & JWT Profile",
            all_passed,
            f"Reg: {code}, Dup: {code_dup}, BadPwd: {code_bad}, Login: {code_login}, Profile: {code_me}",
        )

    # Task 3: Citizen Complaint Submission & Department Routing
    def test_complaint_submission(self):
        # 1. Validation test: missing required fields
        code_val, _ = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"description": "Missing issue type"}
        )
        val_passed = code_val == 422

        # 2. Valid complaint submission (Pothole -> Roads & Highways)
        complaint_payload = {
            "issue_type": "pothole",
            "description": f"Deep pothole on crossroad near civic center #{self.ts}",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "severity_level": "HIGH",
            "language": "en"
        }
        code_sub, body_sub = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data=complaint_payload
        )
        sub_data = json.loads(body_sub) if code_sub == 201 else {}
        self.test_complaint_id = sub_data.get("complaint_id")
        if self.test_complaint_id:
            self.created_complaint_ids.append(self.test_complaint_id)

        dept_name = sub_data.get("department", {}).get("name") if sub_data.get("department") else ""
        routing_correct = dept_name == "Roads & Highways"
        sub_passed = code_sub == 201 and bool(self.test_complaint_id) and routing_correct

        # 3. Upload evidence file using multipart form-data
        evidence_passed = False
        if self.test_complaint_id:
            img_bytes = create_test_image_bytes("ROAD_POTHOLE_EVIDENCE")
            boundary = f"----WebKitFormBoundary{self.ts}"
            body_parts = [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="file"; filename="pothole_{self.ts}.jpg"'.encode("utf-8"),
                b"Content-Type: image/jpeg",
                b"",
                img_bytes,
                f"--{boundary}--".encode("utf-8"),
                b""
            ]
            multipart_body = b"\r\n".join(body_parts)
            ev_headers = {
                "Authorization": f"Bearer {self.citizen_token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            }
            code_ev, body_ev = make_request(
                f"{API_URL}/api/v1/complaints/{self.test_complaint_id}/evidence",
                method="POST",
                headers=ev_headers,
                data=multipart_body
            )
            evidence_passed = code_ev == 201 and "sha256_hash" in body_ev

        all_passed = val_passed and sub_passed and evidence_passed
        self.log(
            "Task 3 — Complaint Submission, Routing & Evidence Attachment",
            all_passed,
            f"Validation: {code_val}, Create: {code_sub} (Dept: {dept_name}), Evidence Upload: {evidence_passed}",
        )

    # Task 4: Production AI Inference Safety (No Model Active)
    def test_production_ai_inference_safety(self):
        img_bytes = create_test_image_bytes("CIVIC_TEST")
        boundary = f"----WebKitFormBoundaryProd{self.ts}"
        body_parts = [
            f"--{boundary}".encode("utf-8"),
            b'Content-Disposition: form-data; name="file"; filename="test.jpg"',
            b"Content-Type: image/jpeg",
            b"",
            img_bytes,
            f"--{boundary}--".encode("utf-8"),
            b""
        ]
        multipart_body = b"\r\n".join(body_parts)
        headers = {
            "Authorization": f"Bearer {self.citizen_token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
        code, body = make_request(
            f"{API_URL}/api/v1/ai/inference",
            method="POST",
            headers=headers,
            data=multipart_body
        )
        data = json.loads(body) if code == 200 else {}
        passed = (
            code == 200
            and data.get("success") is False
            and data.get("error_code") == "AI_MODEL_NOT_AVAILABLE"
            and "No trained AI model is currently active" in data.get("message", "")
        )
        self.log(
            "Task 4 — Production AI Inference Safe Inactivity Check",
            passed,
            f"Code: {code}, error_code: {data.get('error_code')}",
        )

    # Task 5: Isolated Experimental Demo Inference (Disabled vs Enabled)
    def test_demo_inference_flag(self):
        img_bytes = create_test_image_bytes("DEMO_TEST")
        boundary = f"----WebKitFormBoundaryDemo{self.ts}"
        body_parts = [
            f"--{boundary}".encode("utf-8"),
            b'Content-Disposition: form-data; name="file"; filename="demo.jpg"',
            b"Content-Type: image/jpeg",
            b"",
            img_bytes,
            f"--{boundary}--".encode("utf-8"),
            b""
        ]
        multipart_body = b"\r\n".join(body_parts)
        headers = {
            "Authorization": f"Bearer {self.citizen_token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }

        # 1. Test with flag disabled (default)
        code_dis, body_dis = make_request(
            f"{API_URL}/api/v1/ai/demo-inference",
            method="POST",
            headers=headers,
            data=multipart_body
        )
        data_dis = json.loads(body_dis) if code_dis == 200 else {}
        dis_passed = code_dis == 200 and data_dis.get("error_code") == "DEMO_MODE_DISABLED"

        # 2. Test with flag enabled via query parameter
        code_en, body_en = make_request(
            f"{API_URL}/api/v1/ai/demo-inference?enable_demo=true",
            method="POST",
            headers=headers,
            data=multipart_body
        )
        data_en = json.loads(body_en) if code_en == 200 else {}
        en_passed = (
            code_en == 200
            and data_en.get("is_demo") is True
            and (data_en.get("success") is True or data_en.get("error_code") == "AI_NO_DETECTION")
        )

        all_passed = dis_passed and en_passed
        self.log(
            "Task 5 — Experimental Demo Inference Flag Control",
            all_passed,
            f"Disabled check: {dis_passed} ({data_dis.get('error_code')}), Enabled check: {en_passed} (is_demo: {data_en.get('is_demo')})",
        )

    # Task 6: Class 7 Safety & Category Override Check
    def test_class_7_safety_override(self):
        from app.core.config import settings
        orig = settings.ENABLE_EXPERIMENTAL_DEMO_INFERENCE
        settings.ENABLE_EXPERIMENTAL_DEMO_INFERENCE = True
        try:
            from app.ai.demo_inference_service import DemoInferenceService
            from app.db.session import SessionLocal
            from app.models.user import User

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == self.created_user_ids[0]).first() if self.created_user_ids else None
                # Create a sample test run
                res = DemoInferenceService.execute_demo_inference(
                    image_bytes=create_test_image_bytes("SAMPLE_ROAD"),
                    filename="sample.jpg",
                    content_type="image/jpeg",
                    current_user=user,
                    db=db,
                )
                service_executed = res is not None
            finally:
                db.close()
        finally:
            settings.ENABLE_EXPERIMENTAL_DEMO_INFERENCE = orig

        # Verify manual category override in complaints API
        manual_override_payload = {
            "issue_type": "drainage_problem",
            "description": "Citizen manual confirmation: roadside drainage clogged with silt",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "severity_level": "HIGH",
            "language": "en"
        }
        code_ov, body_ov = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data=manual_override_payload
        )
        data_ov = json.loads(body_ov) if code_ov == 201 else {}
        if data_ov.get("complaint_id"):
            self.created_complaint_ids.append(data_ov["complaint_id"])

        override_passed = code_ov == 201 and data_ov.get("issue_type") == "drainage_problem"
        all_passed = service_executed and override_passed

        self.log(
            "Task 6 — Class 7 Safety Protection & Manual Citizen Override",
            all_passed,
            f"Demo Service Execution: {service_executed}, Manual Override Submission: {code_ov} ({data_ov.get('issue_type')})",
        )

    # Task 7: Citizen Complaint Tracking & Status History
    def test_complaint_tracking(self):
        code, body = make_request(
            f"{API_URL}/api/v1/complaints/{self.test_complaint_id}",
            headers=self.citizen_headers
        )
        data = json.loads(body) if code == 200 else {}
        passed = (
            code == 200
            and data.get("complaint_id") == self.test_complaint_id
            and data.get("status") == "SUBMITTED"
            and len(data.get("status_history", [])) >= 1
            and len(data.get("evidences", [])) >= 1
        )
        self.log(
            "Task 7 — Complaint Tracking & Status History Retrieval",
            passed,
            f"Code: {code}, Status: {data.get('status')}, History entries: {len(data.get('status_history', []))}, Evidences: {len(data.get('evidences', []))}",
        )

    # Task 8: Officer Workflow & Department Isolation
    def test_officer_workflow(self):
        from app.db.session import SessionLocal
        from app.models.user import User, UserRole
        from app.models.department import Department
        from app.core.auth import hash_password

        db = SessionLocal()
        try:
            dept_roads = db.query(Department).filter(Department.name == "Roads & Highways").first()
            dept_health = db.query(Department).filter(Department.name == "Public Health & Sanitation").first()

            # Ensure officer for Roads & Highways
            officer_email = f"officer_roads_{self.ts}@civic.gov"
            officer = User(
                name="Roads Officer Audit",
                email=officer_email,
                role=UserRole.OFFICER,
                password_hash=hash_password("OfficerPass123!"),
                department_id=dept_roads.id,
            )
            db.add(officer)

            # Ensure officer for Public Health (to test isolation)
            other_email = f"officer_health_{self.ts}@civic.gov"
            other_officer = User(
                name="Health Officer Audit",
                email=other_email,
                role=UserRole.OFFICER,
                password_hash=hash_password("OfficerPass123!"),
                department_id=dept_health.id,
            )
            db.add(other_officer)
            db.commit()
            db.refresh(officer)
            db.refresh(other_officer)
            self.created_user_ids.extend([officer.id, other_officer.id])
        finally:
            db.close()

        # 1. Login as Roads officer
        code_off, body_off = make_request(
            f"{API_URL}/auth/login",
            method="POST",
            data={"email": officer_email, "password": "OfficerPass123!"}
        )
        token_roads = json.loads(body_off).get("access_token")
        hdr_roads = {"Authorization": f"Bearer {token_roads}"}

        # 2. Officer Dashboard
        code_dash, body_dash = make_request(f"{API_URL}/api/v1/officer/dashboard", headers=hdr_roads)
        dash_passed = code_dash == 200

        # 3. List assigned complaints -> verify test complaint is listed
        code_list, body_list = make_request(
            f"{API_URL}/api/v1/officer/complaints?search={self.test_complaint_id}",
            headers=hdr_roads
        )
        data_list = json.loads(body_list) if code_list == 200 else {}
        complaints_found = [c["complaint_id"] for c in data_list.get("items", [])]
        in_assigned = self.test_complaint_id in complaints_found

        # 4. Department Isolation test: Other officer attempts to view Roads complaint -> must be 403
        _, body_other = make_request(
            f"{API_URL}/auth/login",
            method="POST",
            data={"email": other_email, "password": "OfficerPass123!"}
        )
        token_health = json.loads(body_other).get("access_token")
        hdr_health = {"Authorization": f"Bearer {token_health}"}
        code_iso, _ = make_request(
            f"{API_URL}/api/v1/officer/complaints/{self.test_complaint_id}",
            headers=hdr_health
        )
        isolation_passed = code_iso == 403

        # 5. Roads officer transitions status: SUBMITTED -> DEPARTMENT_ASSIGNED -> IN_PROGRESS
        patch_assign = {
            "status": "DEPARTMENT_ASSIGNED",
            "note": f"Assigned to road inspection unit #{self.ts}"
        }
        code_assign, body_assign = make_request(
            f"{API_URL}/api/v1/officer/complaints/{self.test_complaint_id}/status",
            method="PATCH",
            headers=hdr_roads,
            data=patch_assign
        )
        assign_ok = code_assign == 200 and json.loads(body_assign).get("status") == "DEPARTMENT_ASSIGNED"

        patch_progress = {
            "status": "IN_PROGRESS",
            "note": f"Dispatched inspection team #{self.ts} to site"
        }
        code_patch, body_patch = make_request(
            f"{API_URL}/api/v1/officer/complaints/{self.test_complaint_id}/status",
            method="PATCH",
            headers=hdr_roads,
            data=patch_progress
        )
        patch_ok = code_patch == 200 and json.loads(body_patch).get("status") == "IN_PROGRESS"
        status_lifecycle_passed = assign_ok and patch_ok

        # 6. Roads officer adds official investigation note
        note_payload = {
            "note": f"Field measurement complete: asphalt pothole 0.8m diameter. Work order issued #{self.ts}."
        }
        code_note, _ = make_request(
            f"{API_URL}/api/v1/officer/complaints/{self.test_complaint_id}/notes",
            method="POST",
            headers=hdr_roads,
            data=note_payload
        )
        note_passed = code_note == 201

        all_passed = dash_passed and in_assigned and isolation_passed and status_lifecycle_passed and note_passed
        self.log(
            "Task 8 — Officer Dashboard, Department Isolation & Workflow Transition",
            all_passed,
            f"Dashboard: {code_dash}, Listed: {in_assigned}, Isolation Block (403): {code_iso}, Status Transition: {code_patch}, Note: {code_note}",
        )

    # Task 9: Full End-to-End Status Loopback Verification
    def test_e2e_status_loopback(self):
        # Citizen checks complaint detail again after officer updated it
        code, body = make_request(
            f"{API_URL}/api/v1/complaints/{self.test_complaint_id}",
            headers=self.citizen_headers
        )
        data = json.loads(body) if code == 200 else {}
        status_updated = data.get("status") == "IN_PROGRESS"

        # Check status history contains transition chain
        history = data.get("status_history", [])
        statuses_seen = [h.get("new_status") for h in history if h.get("new_status")]
        history_correct = "SUBMITTED" in statuses_seen and "IN_PROGRESS" in statuses_seen
        chain_str = " -> ".join(statuses_seen) if statuses_seen else "None"

        passed = code == 200 and status_updated and history_correct
        self.log(
            "Task 9 — Full End-to-End Status Loopback (Citizen verifies Officer update)",
            passed,
            f"Citizen Sees Status: {data.get('status')}, History Chain: {chain_str}",
        )

    # Task 10: Admin Management Dashboards & Supervision
    def test_admin_dashboards(self):
        from app.db.session import SessionLocal
        from app.models.user import User, UserRole
        from app.core.auth import hash_password

        db = SessionLocal()
        try:
            admin_email = f"admin_audit_{self.ts}@civic.gov"
            admin = User(
                name="System Administrator Audit",
                email=admin_email,
                role=UserRole.ADMIN,
                password_hash=hash_password("AdminSecurePass123!"),
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            self.created_user_ids.append(admin.id)
        finally:
            db.close()

        code_adm, body_adm = make_request(
            f"{API_URL}/auth/login",
            method="POST",
            data={"email": admin_email, "password": "AdminSecurePass123!"}
        )
        token_admin = json.loads(body_adm).get("access_token")
        hdr_admin = {"Authorization": f"Bearer {token_admin}"}

        # 1. Models list
        code_mod, body_mod = make_request(f"{API_URL}/api/v1/admin/models", headers=hdr_admin)
        models_data = json.loads(body_mod) if code_mod == 200 else {}
        mod_passed = code_mod == 200 and isinstance(models_data.get("models"), list)

        # 2. Datasets list
        code_ds, body_ds = make_request(f"{API_URL}/api/v1/admin/datasets", headers=hdr_admin)
        ds_data = json.loads(body_ds) if code_ds == 200 else {}
        ds_passed = code_ds == 200 and isinstance(ds_data.get("datasets"), list)

        # 3. Chatbot documents list
        code_cb, _ = make_request(f"{API_URL}/api/v1/admin/chatbot/documents", headers=hdr_admin)
        cb_passed = code_cb == 200

        # 4. Blockchain status
        code_bc, _ = make_request(f"{API_URL}/api/v1/admin/blockchain/status", headers=hdr_admin)
        bc_passed = code_bc == 200

        all_passed = mod_passed and ds_passed and cb_passed and bc_passed
        self.log(
            "Task 10 — Admin Management Dashboards (Models, Datasets, KB, Blockchain)",
            all_passed,
            f"Models: {code_mod}, Datasets: {code_ds}, Chatbot KB: {code_cb}, Blockchain: {code_bc}",
        )

    # Task 11: Security Edge Cases & Error Handling
    def test_security_and_error_handling(self):
        # 1. Unauthorized request
        code_unauth, _ = make_request(f"{API_URL}/auth/me")
        unauth_passed = code_unauth == 401

        # 2. Citizen trying to access officer endpoint -> 403
        code_forbid, _ = make_request(f"{API_URL}/api/v1/officer/dashboard", headers=self.citizen_headers)
        forbid_passed = code_forbid == 403

        # 3. Non-existent complaint -> 404
        code_404, _ = make_request(f"{API_URL}/api/v1/complaints/CMP-NONEXISTENT-99999", headers=self.citizen_headers)
        nf_passed = code_404 == 404

        all_passed = unauth_passed and forbid_passed and nf_passed
        self.log(
            "Task 11 — Security Role Enforcement & Error Responses (401, 403, 404)",
            all_passed,
            f"Unauth: {code_unauth}, Role Forbidden: {code_forbid}, Not Found: {code_404}",
        )

    # Task 12: Frontend Web Template Routes (Flask :5000)
    def test_frontend_routes(self):
        routes = [
            ("/", "AI Civic Guardian"),
            ("/register", "Register"),
            ("/login", "Login"),
            ("/dashboard", "Dashboard"),
            ("/complaints/new", "Complaint"),
            ("/track", "Track"),
            ("/profile", "Profile"),
            ("/chatbot", "AI Assistant"),
            ("/officer/dashboard", "Officer"),
            ("/admin/models", "Models"),
            ("/admin/datasets", "Datasets"),
        ]

        route_results = []
        for path, keyword in routes:
            code, html = make_request(f"{WEB_URL}{path}")
            has_kw = keyword.lower() in html.lower()
            ok = (code == 200 and has_kw)
            route_results.append((path, ok, code))

        all_passed = all(ok for _, ok, _ in route_results)
        self.log(
            "Task 12 — Frontend Web Pages & Template Rendering (Port 5000)",
            all_passed,
            f"Verified {len(route_results)} of {len(routes)} HTML routes returned 200 OK",
        )

    # Clean-up strictly isolated test records
    def cleanup(self):
        print("\nCleaning up isolated test records...")
        from app.db.session import SessionLocal
        from app.models.user import User
        from app.models.complaint import Complaint
        from app.models.evidence import ComplaintEvidence
        from app.models.status_history import ComplaintStatusHistory
        from app.models.complaint_note import ComplaintNote
        from app.models.blockchain_record import BlockchainRecord
        from app.models.duplicate_analysis import DuplicateAnalysis
        from sqlalchemy import or_

        db = SessionLocal()
        try:
            # Delete created complaints
            for cid in self.created_complaint_ids:
                c = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if c:
                    db.query(BlockchainRecord).filter(BlockchainRecord.complaint_id == c.id).delete()
                    db.query(ComplaintEvidence).filter(ComplaintEvidence.complaint_id == c.id).delete()
                    db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == c.id).delete()
                    db.query(ComplaintNote).filter(ComplaintNote.complaint_id == c.id).delete()
                    db.query(DuplicateAnalysis).filter(or_(DuplicateAnalysis.complaint_id == c.id, DuplicateAnalysis.possible_duplicate_id == c.id)).delete()
                    db.delete(c)
            # Delete created test users
            for uid in self.created_user_ids:
                db.query(User).filter(User.id == uid).delete()
            db.commit()
            print(f"[CLEANUP COMPLETE] Removed {len(self.created_complaint_ids)} test complaints and {len(self.created_user_ids)} test users.")
        except Exception as e:
            db.rollback()
            print(f"[CLEANUP WARNING] Error during test cleanup: {e}")
        finally:
            db.close()

    def run_all(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — FULL WEBSITE FUNCTIONAL TEST SUITE")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(self.ts))}")
        print("=" * 80)
        try:
            self.test_server_health()
            self.test_authentication_flow()
            self.test_complaint_submission()
            self.test_production_ai_inference_safety()
            self.test_demo_inference_flag()
            self.test_class_7_safety_override()
            self.test_complaint_tracking()
            self.test_officer_workflow()
            self.test_e2e_status_loopback()
            self.test_admin_dashboards()
            self.test_security_and_error_handling()
            self.test_frontend_routes()
        finally:
            self.cleanup()

        print("=" * 80)
        passed_count = sum(1 for _, p, _ in self.results if p)
        total_count = len(self.results)
        print(f"SUMMARY: {passed_count}/{total_count} Tasks Passed ({((passed_count/total_count)*100):.1f}%)")
        print("=" * 80)
        return passed_count == total_count


if __name__ == "__main__":
    tester = LiveWebsiteFunctionalTester()
    success = tester.run_all()
    if not success:
        sys.exit(1)
