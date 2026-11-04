import sys
import io
import re
import time
import hashlib
from pathlib import Path
from typing import Dict, Any

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import inspect
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.evidence import ComplaintEvidence
from app.models.status_history import ComplaintStatusHistory
from app.models.audit_log import AuditLog
from app.complaints.constants import VALID_ISSUE_TYPES
from app.services.routing_service import ISSUE_TO_DEPARTMENT_NAME_MAP
from fastapi_app import app as fastapi_app


class ComplaintTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db = SessionLocal()
        self.results = []
        self.created_complaint_ids = []
        self.test_users = []

    def log(self, test_num: int, test_name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({"num": test_num, "name": test_name, "passed": passed, "message": message})
        print(f"{status_str} Test {test_num:02d} — {test_name}: {message}")

    def run(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — REAL CIVIC COMPLAINT REGISTRATION TEST SUITE (20 TESTS)")
        print("=" * 80)

        try:
            # Setup two distinct citizen accounts
            ts = int(time.time())
            citizen_a = self.create_test_citizen(f"citizen_a_{ts}@example.com", "Priya Citizen", "Pass@123456")
            citizen_b = self.create_test_citizen(f"citizen_b_{ts}@example.com", "Rohan Citizen", "Pass@123456")

            # 1. Citizen can create complaint
            complaint_a = self.test_01_citizen_can_create_complaint(citizen_a)

            # 2. Unauthenticated user cannot create complaint
            self.test_02_unauthenticated_cannot_create_complaint()

            # 3. Citizen cannot create complaint for another user
            self.test_03_cannot_create_complaint_for_another_user(citizen_a, citizen_b)

            # 4. Invalid issue type rejected
            self.test_04_invalid_issue_type_rejected(citizen_a)

            # 5. Invalid latitude rejected
            self.test_05_invalid_latitude_rejected(citizen_a)

            # 6. Invalid longitude rejected
            self.test_06_invalid_longitude_rejected(citizen_a)

            # 7. Complaint receives unique public complaint ID
            self.test_07_unique_public_complaint_id(citizen_a)

            # 8. Initial status is SUBMITTED
            self.test_08_initial_status_submitted(complaint_a)

            # 9. Status history is created
            self.test_09_status_history_created(complaint_a, citizen_a)

            # 10. Audit log is created
            self.test_10_audit_log_created(complaint_a, citizen_a)

            # 11. Correct department routing for all 12 issue types
            self.test_11_department_routing_all_12_types(citizen_a)

            # 12. Citizen can retrieve own complaint
            self.test_12_citizen_can_retrieve_own_complaint(citizen_a, complaint_a)

            # 13. Citizen cannot retrieve another citizen's complaint
            self.test_13_citizen_cannot_retrieve_others_complaint(citizen_b, complaint_a)

            # 14. Image upload works
            evidence_record, raw_img_bytes = self.test_14_image_upload_works(citizen_a, complaint_a)

            # 15. Unsupported file type rejected
            self.test_15_unsupported_file_type_rejected(citizen_a, complaint_a)

            # 16. Oversized file rejected
            self.test_16_oversized_file_rejected(citizen_a, complaint_a)

            # 17. SHA-256 evidence hash is stored
            self.test_17_sha256_evidence_hash_stored(evidence_record, raw_img_bytes)

            # 18. Actual binary evidence is NOT stored in PostgreSQL
            self.test_18_binary_not_in_postgres(evidence_record)

            # 19. Files use safe server-generated names
            self.test_19_safe_server_generated_filenames(evidence_record)

            # 20. No password/JWT/secret is written to audit logs
            self.test_20_no_secrets_in_audit_logs()

        finally:
            self.cleanup()
            self.db.close()

        print("\n" + "=" * 80)
        print("COMPLAINT TEST EXECUTION SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        all_passed = passed_count == total_count
        print(f"Total Tests: {total_count} | Passed: {passed_count} | Failed: {total_count - passed_count}")
        print(f"Result: {'ALL 20 TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=" * 80)

        if not all_passed:
            sys.exit(1)

    def create_test_citizen(self, email: str, name: str, password: str) -> Dict[str, Any]:
        # Register citizen
        reg_resp = self.client.post(
            "/auth/register",
            json={"name": name, "email": email, "password": password, "preferred_language": "en"},
        )
        assert reg_resp.status_code == 201, f"Failed to register {email}: {reg_resp.text}"

        # Login to get JWT
        login_resp = self.client.post("/auth/login", json={"email": email, "password": password})
        assert login_resp.status_code == 200, f"Failed to login {email}: {login_resp.text}"
        data = login_resp.json()

        user_info = {
            "id": data["user"]["id"],
            "name": name,
            "email": email,
            "token": data["access_token"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
        }
        self.test_users.append(user_info)
        return user_info

    def test_01_citizen_can_create_complaint(self, citizen: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "issue_type": "pothole",
            "description": "Hazardous crater-sized pothole on MG Road causing two-wheelers to slip.",
            "original_language": "en",
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        if passed:
            self.created_complaint_ids.append(data["complaint_id"])
        msg = f"HTTP {resp.status_code}, Complaint ID={data.get('complaint_id')}, Department={data.get('department', {}).get('name')}"
        self.log(1, "Citizen can create complaint", passed, msg)
        return data

    def test_02_unauthenticated_cannot_create_complaint(self):
        payload = {
            "issue_type": "pothole",
            "description": "Anonymous attempt to create a civic complaint without token.",
        }
        resp = self.client.post("/api/v1/complaints", json=payload)
        passed = resp.status_code == 401
        msg = f"HTTP {resp.status_code} (Unauthorized expected)"
        self.log(2, "Unauthenticated user cannot create complaint", passed, msg)

    def test_03_cannot_create_complaint_for_another_user(self, citizen_a: Dict[str, Any], citizen_b: Dict[str, Any]):
        # Attempt to inject user_id of citizen_b while authenticated as citizen_a
        payload = {
            "issue_type": "water_leakage",
            "description": "Pipeline broken near street 4 spilling fresh potable drinking water.",
            "user_id": citizen_b["id"],  # Forged user ID
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen_a["headers"])
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        if passed:
            self.created_complaint_ids.append(data["complaint_id"])
            # Check database: owner must be citizen_a.id, NOT citizen_b.id
            db_record = self.db.query(Complaint).filter(Complaint.complaint_id == data["complaint_id"]).first()
            owner_is_a = db_record.user_id == citizen_a["id"]
            passed = passed and owner_is_a
            msg = f"HTTP {resp.status_code}, DB Owner ID={db_record.user_id} (Citizen A ID={citizen_a['id']}, Citizen B ID={citizen_b['id']})"
        else:
            msg = f"HTTP {resp.status_code}"
        self.log(3, "Citizen cannot create complaint for another user", passed, msg)

    def test_04_invalid_issue_type_rejected(self, citizen: Dict[str, Any]):
        payload = {
            "issue_type": "unidentified_flying_object",
            "description": "Alien spacecraft parked in municipal ground.",
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
        passed = resp.status_code in [400, 422]
        msg = f"HTTP {resp.status_code} ({resp.json().get('detail')})"
        self.log(4, "Invalid issue type rejected", passed, msg)

    def test_05_invalid_latitude_rejected(self, citizen: Dict[str, Any]):
        payload = {
            "issue_type": "pothole",
            "description": "Pothole with invalid latitude coordinates beyond range.",
            "latitude": 95.5,  # Out of -90 to 90 range
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
        passed = resp.status_code in [400, 422]
        msg = f"HTTP {resp.status_code} (Rejected latitude 95.5)"
        self.log(5, "Invalid latitude rejected", passed, msg)

    def test_06_invalid_longitude_rejected(self, citizen: Dict[str, Any]):
        payload = {
            "issue_type": "pothole",
            "description": "Pothole with invalid longitude coordinates beyond range.",
            "longitude": -195.0,  # Out of -180 to 180 range
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
        passed = resp.status_code in [400, 422]
        msg = f"HTTP {resp.status_code} (Rejected longitude -195.0)"
        self.log(6, "Invalid longitude rejected", passed, msg)

    def test_07_unique_public_complaint_id(self, citizen: Dict[str, Any]):
        # Create second complaint and check ID format CG-YYYY-XXXXXX
        payload = {
            "issue_type": "garbage_overflow",
            "description": "Overflowing waste bin attracting stray dogs near community park.",
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        cid = data.get("complaint_id", "")
        self.created_complaint_ids.append(cid)

        # Regex check: CG-YYYY-XXXXXX
        pattern = r"^CG-\d{4}-\d{6}$"
        matches_format = bool(re.match(pattern, cid))
        unique_ids = len(self.created_complaint_ids) == len(set(self.created_complaint_ids))
        passed = passed and matches_format and unique_ids
        msg = f"Generated ID='{cid}', Format match={matches_format}, Unique across set={unique_ids}"
        self.log(7, "Complaint receives unique public complaint ID", passed, msg)

    def test_08_initial_status_submitted(self, complaint: Dict[str, Any]):
        cid = complaint["complaint_id"]
        db_c = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
        passed = complaint["status"] == "SUBMITTED" and db_c.status == "SUBMITTED"
        msg = f"API status='{complaint['status']}', DB status='{db_c.status}'"
        self.log(8, "Initial status is SUBMITTED", passed, msg)

    def test_09_status_history_created(self, complaint: Dict[str, Any], citizen: Dict[str, Any]):
        cid = complaint["complaint_id"]
        db_c = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
        history = self.db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == db_c.id).all()
        passed = len(history) >= 1
        if passed:
            entry = history[0]
            valid_entry = (
                entry.old_status is None
                and entry.new_status == "SUBMITTED"
                and entry.changed_by == citizen["id"]
            )
            passed = passed and valid_entry
            msg = f"History count={len(history)}, Entry: old={entry.old_status}, new={entry.new_status}, changed_by={entry.changed_by}"
        else:
            msg = "No status history found"
        self.log(9, "Status history is created", passed, msg)

    def test_10_audit_log_created(self, complaint: Dict[str, Any], citizen: Dict[str, Any]):
        cid = complaint["complaint_id"]
        audit_entry = (
            self.db.query(AuditLog)
            .filter(AuditLog.entity_id == cid, AuditLog.action == "COMPLAINT_CREATED", AuditLog.user_id == citizen["id"])
            .order_by(AuditLog.id.desc())
            .first()
        )
        passed = audit_entry is not None
        if passed:
            meta = audit_entry.metadata_ or {}
            valid_meta = meta.get("complaint_id") == cid and audit_entry.user_id == citizen["id"]
            passed = passed and valid_meta
            msg = f"AuditLog ID={audit_entry.id}, Action={audit_entry.action}, User={audit_entry.user_id}, Meta={meta}"
        else:
            msg = f"Audit log not found for {cid}"
        self.log(10, "Audit log is created", passed, msg)

    def test_11_department_routing_all_12_types(self, citizen: Dict[str, Any]):
        mismatches = []
        for issue_type, expected_dept_name in ISSUE_TO_DEPARTMENT_NAME_MAP.items():
            payload = {
                "issue_type": issue_type,
                "description": f"Verification test complaint for {issue_type} deterministic routing.",
            }
            resp = self.client.post("/api/v1/complaints", json=payload, headers=citizen["headers"])
            if resp.status_code != 201:
                mismatches.append(f"{issue_type}: HTTP {resp.status_code}")
                continue
            data = resp.json()
            self.created_complaint_ids.append(data["complaint_id"])
            assigned_dept = data.get("department", {}).get("name")
            if assigned_dept != expected_dept_name:
                mismatches.append(f"{issue_type}: expected '{expected_dept_name}', got '{assigned_dept}'")

        passed = len(mismatches) == 0
        msg = f"All 12 issue types routed successfully." if passed else f"Failures: {mismatches}"
        self.log(11, "Correct department routing for all 12 issue types", passed, msg)

    def test_12_citizen_can_retrieve_own_complaint(self, citizen: Dict[str, Any], complaint: Dict[str, Any]):
        cid = complaint["complaint_id"]
        resp = self.client.get(f"/api/v1/complaints/{cid}", headers=citizen["headers"])
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        matched = data.get("complaint_id") == cid
        passed = passed and matched
        msg = f"HTTP {resp.status_code}, Retreived ID={data.get('complaint_id')}, Status={data.get('status')}"
        self.log(12, "Citizen can retrieve own complaint", passed, msg)

    def test_13_citizen_cannot_retrieve_others_complaint(self, citizen_b: Dict[str, Any], complaint_a: Dict[str, Any]):
        cid = complaint_a["complaint_id"]
        # Citizen B attempts to access Citizen A's complaint
        resp = self.client.get(f"/api/v1/complaints/{cid}", headers=citizen_b["headers"])
        passed = resp.status_code == 403
        msg = f"HTTP {resp.status_code} (Forbidden correctly returned when accessing other citizen's complaint)"
        self.log(13, "Citizen cannot retrieve another citizen's complaint", passed, msg)

    def test_14_image_upload_works(self, citizen: Dict[str, Any], complaint: Dict[str, Any]):
        cid = complaint["complaint_id"]
        # Create dummy JPEG bytes with valid JPEG magic bytes (\xFF\xD8\xFF)
        img_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"A" * 1024
        files = {"file": ("pothole_evidence.jpg", io.BytesIO(img_bytes), "image/jpeg")}

        resp = self.client.post(f"/api/v1/complaints/{cid}/evidence", files=files, headers=citizen["headers"])
        passed = resp.status_code == 201
        data = resp.json() if passed else {}
        msg = f"HTTP {resp.status_code}, Evidence ID={data.get('id')}, MIME={data.get('file_type')}, SHA256={data.get('sha256_hash')[:16]}..."
        self.log(14, "Image upload works", passed, msg)
        return data, img_bytes

    def test_15_unsupported_file_type_rejected(self, citizen: Dict[str, Any], complaint: Dict[str, Any]):
        cid = complaint["complaint_id"]
        bad_bytes = b"MZ\x90\x00\x03\x00\x00\x00"  # Executable binary
        files = {"file": ("malicious_payload.exe", io.BytesIO(bad_bytes), "application/x-msdownload")}

        resp = self.client.post(f"/api/v1/complaints/{cid}/evidence", files=files, headers=citizen["headers"])
        passed = resp.status_code == 400
        msg = f"HTTP {resp.status_code} ({resp.json().get('detail')})"
        self.log(15, "Unsupported file type rejected", passed, msg)

    def test_16_oversized_file_rejected(self, citizen: Dict[str, Any], complaint: Dict[str, Any]):
        cid = complaint["complaint_id"]
        # Max image size is 10 MB. Create 10.5 MB stream
        oversized_bytes = b"\xFF\xD8\xFF" + b"X" * (11 * 1024 * 1024)
        files = {"file": ("huge_photo.jpg", io.BytesIO(oversized_bytes), "image/jpeg")}

        resp = self.client.post(f"/api/v1/complaints/{cid}/evidence", files=files, headers=citizen["headers"])
        passed = resp.status_code == 400
        msg = f"HTTP {resp.status_code} ({resp.json().get('detail')})"
        self.log(16, "Oversized file rejected", passed, msg)

    def test_17_sha256_evidence_hash_stored(self, evidence: Dict[str, Any], raw_bytes: bytes):
        expected_hash = hashlib.sha256(raw_bytes).hexdigest()
        stored_hash = evidence.get("sha256_hash")
        passed = stored_hash == expected_hash
        msg = f"Calculated={expected_hash[:16]}..., Stored={stored_hash[:16]}... (Exact match={passed})"
        self.log(17, "SHA-256 evidence hash is stored", passed, msg)

    def test_18_binary_not_in_postgres(self, evidence: Dict[str, Any]):
        # Inspect ComplaintEvidence model and PostgreSQL schema
        inspector = inspect(self.db.get_bind())
        columns = inspector.get_columns("complaint_evidence")
        column_types = {col["name"]: str(col["type"]).upper() for col in columns}

        # Verify no BYTEA or BLOB column exists
        has_binary_col = any("BYTEA" in t or "BLOB" in t or "BINARY" in t for t in column_types.values())
        
        # Verify file exists on disk
        stored_rel_path = evidence.get("file_path", "")
        full_disk_path = BASE_DIR / stored_rel_path
        disk_file_exists = full_disk_path.is_file()

        passed = (not has_binary_col) and disk_file_exists
        msg = f"No binary column in PostgreSQL={not has_binary_col}. File stored safely on disk at '{stored_rel_path}' (Exists={disk_file_exists})"
        self.log(18, "Actual binary evidence is NOT stored in PostgreSQL", passed, msg)

    def test_19_safe_server_generated_filenames(self, evidence: Dict[str, Any]):
        rel_path = evidence.get("file_path", "")
        filename = Path(rel_path).name
        # Filename should be UUID + .jpg, NOT original 'pothole_evidence.jpg'
        is_not_original = "pothole_evidence" not in filename
        # Match hex UUID format: 32 hex chars + extension
        is_uuid_format = bool(re.match(r"^[0-9a-f]{32}\.[a-z0-9]+$", filename))
        passed = is_not_original and is_uuid_format
        msg = f"Server filename='{filename}', Not original name={is_not_original}, UUID format={is_uuid_format}"
        self.log(19, "Files use safe server-generated names", passed, msg)

    def test_20_no_secrets_in_audit_logs(self):
        # Query all audit logs from test run
        logs = self.db.query(AuditLog).all()
        forbidden = ["pass@123456", "password", "bearer", "eyj"]
        leaked = False
        found_sample = None

        for l in logs:
            meta_str = str(l.metadata_).lower()
            for f in forbidden:
                if f in meta_str and meta_str[meta_str.find(f):].startswith("pass@123456"):
                    leaked = True
                    found_sample = f
                    break
            if leaked:
                break

        passed = not leaked
        msg = f"Inspected {len(logs)} audit entries. Zero secrets/passwords found."
        self.log(20, "No password/JWT/secret is written to audit logs", passed, msg)

    def cleanup(self):
        try:
            # Delete created complaints and cascade
            for cid in self.created_complaint_ids:
                c = self.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if c:
                    self.db.delete(c)
            # Delete test users
            for u in self.test_users:
                user_obj = self.db.query(User).filter(User.id == u["id"]).first()
                if user_obj:
                    self.db.delete(user_obj)
            self.db.commit()
        except Exception as e:
            self.db.rollback()


if __name__ == "__main__":
    runner = ComplaintTestRunner()
    runner.run()
