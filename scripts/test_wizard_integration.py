import sys
import io
import time
import hashlib
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient as FastAPITestClient
from flask_app import app as flask_app
from fastapi_app import app as fastapi_app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence


class WizardIntegrationRunner:
    def __init__(self):
        self.flask_client = flask_app.test_client()
        self.fastapi_client = FastAPITestClient(fastapi_app)
        self.db = SessionLocal()
        self.results = []
        self.test_email = f"wizard_citizen_{int(time.time())}@example.com"
        self.test_password = "Password@123"
        self.created_cid = None
        self.token = None

    def log(self, num: int, name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({"num": num, "name": name, "passed": passed, "message": message})
        print(f"{status_str} Test {num:02d} — {name}: {message}")

    def run(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 3 CITIZEN WIZARD & INTEGRATION TEST SUITE")
        print("=" * 80)

        try:
            self.test_01_home_page_loads()
            self.test_02_registration_page_loads()
            self.test_03_login_page_loads()
            self.test_04_dashboard_page_loads()
            self.test_05_wizard_page_loads()
            self.test_06_static_assets_load()
            self.test_07_citizen_registration_flow()
            self.test_08_citizen_login_flow()
            self.test_09_create_complaint_via_wizard()
            self.test_10_upload_evidence_attachment()
            self.test_11_verify_no_fake_ai_confidence()
            self.test_12_verify_no_fake_blockchain()
            self.test_13_complaint_detail_page_loads()
            self.test_14_user_isolation_enforced()
            self.test_15_multilingual_data_intact()

        finally:
            self.cleanup()
            self.db.close()

        print("\n" + "=" * 80)
        print("WIZARD INTEGRATION TEST SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        print(f"Total: {total} | Passed: {passed_count} | Failed: {total - passed_count}")
        print(f"Result: {'ALL 15 INTEGRATION TESTS PASSED' if passed_count == total else 'SOME FAILED'}")
        print("=" * 80)

        if passed_count != total:
            sys.exit(1)

    def test_01_home_page_loads(self):
        resp = self.flask_client.get("/")
        data_lower = resp.data.lower()
        passed = (
            resp.status_code == 200
            and b"ai civic guardian" in data_lower
            and b"report civic problems quickly and easily" in data_lower
        )
        msg = f"HTTP {resp.status_code}, Found 'AI Civic Guardian' and hero text."
        self.log(1, "Home page loads", passed, msg)

    def test_02_registration_page_loads(self):
        resp = self.flask_client.get("/register")
        passed = resp.status_code == 200 and b"Citizen Registration" in resp.data and b"Full Name" in resp.data
        msg = f"HTTP {resp.status_code}, Form inputs present."
        self.log(2, "Registration page loads", passed, msg)

    def test_03_login_page_loads(self):
        resp = self.flask_client.get("/login")
        passed = resp.status_code == 200 and b"Citizen Login" in resp.data and b"login-email" in resp.data
        msg = f"HTTP {resp.status_code}, Email and password inputs present."
        self.log(3, "Login page loads", passed, msg)

    def test_04_dashboard_page_loads(self):
        resp = self.flask_client.get("/dashboard")
        passed = resp.status_code == 200 and b"My Dashboard" in resp.data and b"REPORT A PROBLEM" in resp.data
        msg = f"HTTP {resp.status_code}, Dashboard structure and report button rendered."
        self.log(4, "Dashboard page loads", passed, msg)

    def test_05_wizard_page_loads(self):
        resp = self.flask_client.get("/complaints/new")
        passed = (
            resp.status_code == 200
            and b"How would you like to report the problem?" in resp.data
            and b"Development fallback" in resp.data
            and b"AI image detection will be available after the AI model is trained" in resp.data
        )
        msg = f"HTTP {resp.status_code}, Wizard steps and dev fallback notices rendered."
        self.log(5, "Complaint wizard page loads", passed, msg)

    def test_06_static_assets_load(self):
        css = self.flask_client.get("/static/css/styles.css")
        api_js = self.flask_client.get("/static/js/api.js")
        i18n_js = self.flask_client.get("/static/js/i18n.js")
        wiz_js = self.flask_client.get("/static/js/wizard.js")
        passed = all(r.status_code == 200 for r in [css, api_js, i18n_js, wiz_js])
        msg = f"styles.css({css.status_code}), api.js({api_js.status_code}), i18n.js({i18n_js.status_code}), wizard.js({wiz_js.status_code})"
        self.log(6, "Static CSS and JS assets load", passed, msg)

    def test_07_citizen_registration_flow(self):
        payload = {
            "name": "Wizard Citizen",
            "email": self.test_email,
            "password": self.test_password,
            "preferred_language": "ta",
            "role": "CITIZEN",
        }
        resp = self.fastapi_client.post("/auth/register", json=payload)
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        passed = passed and data.get("role") == "CITIZEN"
        msg = f"HTTP {resp.status_code}, Registered ID={data.get('id')}, Role={data.get('role')}"
        self.log(7, "Citizen registration flow", passed, msg)

    def test_08_citizen_login_flow(self):
        resp = self.fastapi_client.post("/auth/login", json={"email": self.test_email, "password": self.test_password})
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        self.token = data.get("access_token")
        passed = passed and bool(self.token)
        msg = f"HTTP {resp.status_code}, JWT received, length={len(self.token or '')}"
        self.log(8, "Citizen login flow", passed, msg)

    def test_09_create_complaint_via_wizard(self):
        payload = {
            "issue_type": "drainage_problem",
            "description": "Storm drain completely blocked with silt, causing street waterlogging.",
            "original_language": "ta",
            "latitude": 13.0827,
            "longitude": 80.2707,
        }
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.fastapi_client.post("/api/v1/complaints", json=payload, headers=headers)
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        self.created_cid = data.get("complaint_id")
        # Check that department is Drainage & Flood Management
        dept = data.get("department", {}).get("name")
        passed = passed and dept == "Drainage & Flood Management" and data.get("status") == "SUBMITTED"
        msg = f"HTTP {resp.status_code}, Complaint ID={self.created_cid}, Routed Dept='{dept}', Status='{data.get('status')}'"
        self.log(9, "Create complaint via wizard API", passed, msg)

    def test_10_upload_evidence_attachment(self):
        sample_jpg = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"EVIDENCE_IMAGE_BYTES" * 100
        files = {"file": ("drain_clogged.jpg", io.BytesIO(sample_jpg), "image/jpeg")}
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.fastapi_client.post(f"/api/v1/complaints/{self.created_cid}/evidence", files=files, headers=headers)
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        stored_hash = data.get("sha256_hash")
        expected_hash = hashlib.sha256(sample_jpg).hexdigest()
        passed = passed and stored_hash == expected_hash
        msg = f"HTTP {resp.status_code}, File Type={data.get('file_type')}, SHA-256 Match={passed}"
        self.log(10, "Upload evidence attachment", passed, msg)

    def test_11_verify_no_fake_ai_confidence(self):
        # Inspect created complaint in database & API response
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.fastapi_client.get(f"/api/v1/complaints/{self.created_cid}", headers=headers)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        # severity_score and ai_confidence must strictly be null
        no_fake_score = data.get("severity_score") is None
        no_fake_conf = data.get("ai_confidence") is None
        passed = passed and no_fake_score and no_fake_conf
        msg = f"severity_score={data.get('severity_score')} (None expected), ai_confidence={data.get('ai_confidence')} (None expected)"
        self.log(11, "No fake AI confidence or scores", passed, msg)

    def test_12_verify_no_fake_blockchain(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.fastapi_client.get(f"/api/v1/complaints/{self.created_cid}", headers=headers)
        raw_json_str = resp.text.lower()
        has_blockchain = any(term in raw_json_str for term in ["blockchain", "tx_hash", "smart_contract", "ethereum", "web3"])
        passed = not has_blockchain
        msg = f"Zero blockchain fields found in complaint data: {passed}"
        self.log(12, "No fake blockchain fields present", passed, msg)

    def test_13_complaint_detail_page_loads(self):
        resp = self.flask_client.get(f"/complaints/{self.created_cid}")
        passed = resp.status_code == 200 and b"Complaint Tracking" in resp.data and b"status-timeline" in resp.data
        msg = f"HTTP {resp.status_code}, Detail template rendered with status timeline container."
        self.log(13, "Complaint detail page loads", passed, msg)

    def test_14_user_isolation_enforced(self):
        # Register a second citizen
        other_email = f"other_citizen_{int(time.time())}@example.com"
        self.fastapi_client.post("/auth/register", json={"name": "Other Citizen", "email": other_email, "password": "Password@123"})
        login_resp = self.fastapi_client.post("/auth/login", json={"email": other_email, "password": "Password@123"})
        other_token = login_resp.json()["access_token"]

        # Other citizen attempts to access the first citizen's complaint
        resp = self.fastapi_client.get(f"/api/v1/complaints/{self.created_cid}", headers={"Authorization": f"Bearer {other_token}"})
        passed = resp.status_code == 403
        msg = f"HTTP {resp.status_code} (Forbidden when other citizen attempts access)"
        self.log(14, "Citizen isolation enforced", passed, msg)

        # Cleanup other user
        u = self.db.query(User).filter(User.email == other_email).first()
        if u:
            self.db.delete(u)
            self.db.commit()

    def test_15_multilingual_data_intact(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = self.fastapi_client.get(f"/api/v1/complaints/{self.created_cid}", headers=headers)
        data = resp.json()
        passed = data.get("original_language") == "ta"
        msg = f"Language code stored as '{data.get('original_language')}'"
        self.log(15, "Multilingual language code recorded", passed, msg)

    def cleanup(self):
        try:
            if self.created_cid:
                c = self.db.query(Complaint).filter(Complaint.complaint_id == self.created_cid).first()
                if c:
                    self.db.delete(c)
            u = self.db.query(User).filter(User.email == self.test_email).first()
            if u:
                self.db.delete(u)
            self.db.commit()
        except Exception:
            self.db.rollback()


if __name__ == "__main__":
    runner = WizardIntegrationRunner()
    runner.run()
