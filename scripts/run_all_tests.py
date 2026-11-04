import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.health import check_db_health
from app.models.user import User, UserRole
from app.models.department import Department
from app.core.auth import hash_password, create_access_token
from fastapi_app import app as fastapi_app
from flask_app import app as flask_app

# The exactly required 12 departments
EXPECTED_DEPARTMENTS = [
    "Public Health & Sanitation",
    "Urban Planning & Municipal Services",
    "Water Supply & Sewerage",
    "Roads & Highways",
    "Electricity & Street Lighting",
    "Solid Waste Management",
    "Parks & Public Spaces",
    "Traffic & Transportation",
    "Environmental Protection",
    "Building & Construction",
    "Public Safety",
    "Drainage & Flood Management",
]


class TestRunner:
    def __init__(self):
        self.fastapi_client = TestClient(fastapi_app)
        self.flask_client = flask_app.test_client()
        self.results = []
        self.db = SessionLocal()

    def log(self, test_name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({"test": test_name, "passed": passed, "message": message})
        print(f"{status_str} {test_name}: {message}")

    def run(self):
        print("=" * 75)
        print(f"AI CIVIC GUARDIAN — FOUNDATION & AUTHENTICATION TEST SUITE")
        print(f"Target Database: {settings.DB_NAME}")
        print("=" * 75)

        try:
            self.test_postgres_connection()
            self.test_12_departments()
            self.test_flask_health()
            self.test_fastapi_health()
            
            # Auth tests
            test_ts = int(time.time())
            citizen_email = f"citizen_qa_{test_ts}@example.com"
            officer_email = f"officer_qa_{test_ts}@example.com"
            admin_email = f"admin_qa_{test_ts}@example.com"
            password = "SecurePassword@123"

            self.test_registration(citizen_email, password)
            self.test_role_escalation_guard(f"escalate_{test_ts}@example.com", password)
            self.test_duplicate_registration(citizen_email, password)
            citizen_token = self.test_login_success(citizen_email, password)
            self.test_login_invalid_password(citizen_email)
            self.test_jwt_validation_and_me(citizen_token, citizen_email)
            self.test_protected_without_token()
            self.test_protected_with_invalid_token()
            self.test_protected_with_valid_token(citizen_token)
            
            # Seed officer and admin accounts directly in DB to test RBAC
            officer_token, admin_token = self.setup_and_test_rbac(officer_email, admin_email, password, citizen_token)
            
            # Flask integration with FastAPI JWT
            self.test_flask_jwt_integration(citizen_token, officer_token)

        finally:
            self.cleanup_test_users()
            self.db.close()

        print("\n" + "=" * 75)
        print("TEST EXECUTION SUMMARY")
        print("=" * 75)
        all_passed = all(r["passed"] for r in self.results)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        print(f"Total Tests Run: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_count - passed_count}")
        print(f"Status: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=" * 75)

        if not all_passed:
            sys.exit(1)

    def test_postgres_connection(self):
        health = check_db_health()
        is_healthy = health.get("status") == "healthy"
        db_name = health.get("database_name")
        matches_db = db_name == "ai_civic_guardian"
        passed = is_healthy and matches_db
        msg = f"Connected to '{db_name}', Version: {health.get('server_version')}, Latency: {health.get('latency_ms')}ms"
        self.log("1. PostgreSQL Connection", passed, msg)

    def test_12_departments(self):
        depts = self.db.query(Department).all()
        dept_names = [d.name for d in depts]
        has_12 = len(depts) == 12
        matches_all = sorted(dept_names) == sorted(EXPECTED_DEPARTMENTS)
        passed = has_12 and matches_all
        msg = f"Count={len(depts)}. All 12 required departments exist without duplicates."
        self.log("2. Exactly 12 Departments Verification", passed, msg)

    def test_flask_health(self):
        response = self.flask_client.get("/health")
        passed = response.status_code == 200
        data = response.get_json() or {}
        is_healthy = data.get("status") == "healthy"
        db_healthy = data.get("database", {}).get("status") == "healthy"
        passed = passed and is_healthy and db_healthy
        msg = f"Status={response.status_code}, App status={data.get('status')}, DB={data.get('database', {}).get('database_name')}"
        self.log("3. Flask GET /health", passed, msg)

    def test_fastapi_health(self):
        response = self.fastapi_client.get("/health")
        passed = response.status_code == 200
        data = response.json()
        is_healthy = data.get("status") == "healthy"
        db_healthy = data.get("database", {}).get("status") == "healthy"
        passed = passed and is_healthy and db_healthy
        msg = f"Status={response.status_code}, Service={data.get('service')}, DB={data.get('database', {}).get('database_name')}"
        self.log("4. FastAPI GET /health", passed, msg)

    def test_registration(self, email: str, password: str):
        payload = {
            "name": "Citizen QA Tester",
            "email": email,
            "password": password,
            "preferred_language": "en",
            "role": "CITIZEN",
        }
        response = self.fastapi_client.post("/auth/register", json=payload)
        passed = response.status_code == 201
        data = response.json()
        role_is_citizen = data.get("role") == UserRole.CITIZEN
        user_in_db = self.db.query(User).filter(User.email == email).first()
        passed = passed and role_is_citizen and (user_in_db is not None)
        msg = f"Status={response.status_code}, User ID={data.get('id')}, Role={data.get('role')}"
        self.log("5. User Registration (CITIZEN)", passed, msg)

    def test_role_escalation_guard(self, email: str, password: str):
        # Attempt to register as ADMIN - must be blocked by validation
        payload = {
            "name": "Attacker Trying Admin",
            "email": email,
            "password": password,
            "role": "ADMIN",
        }
        response = self.fastapi_client.post("/auth/register", json=payload)
        # Validation error returns 422 Unprocessable Entity
        passed = response.status_code in [400, 422]
        msg = f"Attempting self-registration as ADMIN rejected with HTTP {response.status_code}."
        self.log("6. Role Escalation Prevention", passed, msg)

    def test_duplicate_registration(self, email: str, password: str):
        payload = {
            "name": "Duplicate User",
            "email": email,
            "password": password,
        }
        response = self.fastapi_client.post("/auth/register", json=payload)
        passed = response.status_code == 400
        msg = f"Duplicate email registration rejected with HTTP {response.status_code} ({response.json().get('detail')})."
        self.log("7. Duplicate Email Rejection", passed, msg)

    def test_login_success(self, email: str, password: str) -> str:
        payload = {"email": email, "password": password}
        response = self.fastapi_client.post("/auth/login", json=payload)
        passed = response.status_code == 200
        data = response.json()
        token = data.get("access_token", "")
        token_type = data.get("token_type")
        has_token = len(token) > 20 and token_type == "bearer"
        passed = passed and has_token
        msg = f"Status={response.status_code}, Token Type={token_type}, Token Length={len(token)}"
        self.log("8. User Login (Valid Credentials -> JWT)", passed, msg)
        return token

    def test_login_invalid_password(self, email: str):
        payload = {"email": email, "password": "WrongPassword!999"}
        response = self.fastapi_client.post("/auth/login", json=payload)
        passed = response.status_code == 401
        msg = f"Invalid password rejected with HTTP {response.status_code} ({response.json().get('detail')})."
        self.log("9. Login with Invalid Password", passed, msg)

    def test_jwt_validation_and_me(self, token: str, expected_email: str):
        headers = {"Authorization": f"Bearer {token}"}
        response = self.fastapi_client.get("/auth/me", headers=headers)
        passed = response.status_code == 200
        data = response.json()
        email_matches = data.get("email") == expected_email
        passed = passed and email_matches
        msg = f"Status={response.status_code}, Authenticated User={data.get('name')}, Email={data.get('email')}"
        self.log("10. JWT Validation via GET /auth/me", passed, msg)

    def test_protected_without_token(self):
        response = self.fastapi_client.get("/auth/protected")
        passed = response.status_code == 401
        msg = f"Unauthenticated request rejected with HTTP {response.status_code}."
        self.log("11. Protected Endpoint without Token", passed, msg)

    def test_protected_with_invalid_token(self):
        headers = {"Authorization": "Bearer invalid_garbage_token_12345"}
        response = self.fastapi_client.get("/auth/protected", headers=headers)
        passed = response.status_code == 401
        msg = f"Invalid token rejected with HTTP {response.status_code}."
        self.log("12. Protected Endpoint with Invalid Token", passed, msg)

    def test_protected_with_valid_token(self, token: str):
        headers = {"Authorization": f"Bearer {token}"}
        response = self.fastapi_client.get("/auth/protected", headers=headers)
        passed = response.status_code == 200
        data = response.json()
        status_ok = data.get("status") == "success"
        passed = passed and status_ok
        msg = f"Status={response.status_code}, Message: {data.get('message')}"
        self.log("13. Protected Endpoint with Valid Token", passed, msg)

    def setup_and_test_rbac(self, officer_email: str, admin_email: str, password: str, citizen_token: str):
        # 1. Create officer & admin in DB securely
        officer = User(
            name="Officer Rajesh Kumar",
            email=officer_email,
            password_hash=hash_password(password),
            role=UserRole.OFFICER,
            preferred_language="en",
        )
        admin = User(
            name="Admin Sunita Sharma",
            email=admin_email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            preferred_language="en",
        )
        self.db.add_all([officer, admin])
        self.db.commit()
        self.db.refresh(officer)
        self.db.refresh(admin)

        # Login as officer and admin
        resp_off = self.fastapi_client.post("/auth/login", json={"email": officer_email, "password": password})
        officer_token = resp_off.json()["access_token"]

        resp_adm = self.fastapi_client.post("/auth/login", json={"email": admin_email, "password": password})
        admin_token = resp_adm.json()["access_token"]

        # Check Citizen trying to access /auth/officer-only -> must be 403 Forbidden
        c_resp = self.fastapi_client.get("/auth/officer-only", headers={"Authorization": f"Bearer {citizen_token}"})
        c_blocked = c_resp.status_code == 403

        # Check Officer accessing /auth/officer-only -> 200 OK
        o_resp = self.fastapi_client.get("/auth/officer-only", headers={"Authorization": f"Bearer {officer_token}"})
        o_allowed = o_resp.status_code == 200

        # Check Officer accessing /auth/admin-only -> 403 Forbidden
        o_admin_blocked = self.fastapi_client.get("/auth/admin-only", headers={"Authorization": f"Bearer {officer_token}"}).status_code == 403

        # Check Admin accessing /auth/admin-only -> 200 OK
        a_resp = self.fastapi_client.get("/auth/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
        a_allowed = a_resp.status_code == 200

        passed = c_blocked and o_allowed and o_admin_blocked and a_allowed
        msg = f"Citizen blocked(403)={c_blocked}, Officer allowed(200)={o_allowed}, Officer admin-blocked(403)={o_admin_blocked}, Admin allowed(200)={a_allowed}"
        self.log("14. Role-Based Access Control (RBAC)", passed, msg)

        return officer_token, admin_token

    def test_flask_jwt_integration(self, citizen_token: str, officer_token: str):
        # 1. Flask protected without token -> 401
        res_no_tok = self.flask_client.get("/api/v1/protected")
        no_tok_ok = res_no_tok.status_code == 401

        # 2. Flask protected with FastAPI citizen token -> 200
        res_tok = self.flask_client.get("/api/v1/protected", headers={"Authorization": f"Bearer {citizen_token}"})
        tok_ok = res_tok.status_code == 200
        tok_data = res_tok.get_json() or {}

        # 3. Flask officer dashboard with citizen token -> 403 Forbidden
        res_cit_dash = self.flask_client.get("/api/v1/officer/dashboard", headers={"Authorization": f"Bearer {citizen_token}"})
        cit_dash_blocked = res_cit_dash.status_code == 403

        # 4. Flask officer dashboard with officer token -> 200 OK
        res_off_dash = self.flask_client.get("/api/v1/officer/dashboard", headers={"Authorization": f"Bearer {officer_token}"})
        off_dash_ok = res_off_dash.status_code == 200

        passed = no_tok_ok and tok_ok and cit_dash_blocked and off_dash_ok
        msg = f"Flask verified FastAPI JWT: NoToken(401)={no_tok_ok}, ValidToken(200)={tok_ok}, CitizenDashboardBlocked(403)={cit_dash_blocked}, OfficerDashboardAllowed(200)={off_dash_ok}"
        self.log("15. Flask & FastAPI Unified JWT Authentication", passed, msg)

    def cleanup_test_users(self):
        try:
            self.db.query(User).filter(User.email.like("%_qa_%@example.com")).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()


if __name__ == "__main__":
    runner = TestRunner()
    runner.run()
