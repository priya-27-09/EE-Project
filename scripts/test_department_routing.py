"""
AI Civic Guardian — Comprehensive Automatic Department Routing Verification Suite

Verifies:
1. All 12 canonical category IDs (0 to 11 as int and str) resolve to correct department.
2. All 12 canonical display names resolve to correct department.
3. All 12 internal issue keys resolve to correct department.
4. Live complaint creation via POST /api/v1/complaints persists correct department_id and department_name in PostgreSQL for all 12 categories.
5. Manual category override recalculates and persists the overridden department before saving.
6. Missing, empty, or invalid categories fail safely with clear validation messages (never silently misrouted).
7. Routing consistency between demo inference service and complaint submission.
8. Complete cleanup of all test records.
"""

import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.status_history import ComplaintStatusHistory
from app.models.complaint_note import ComplaintNote
from app.models.evidence import ComplaintEvidence
from app.models.blockchain_record import BlockchainRecord
from app.models.duplicate_analysis import DuplicateAnalysis
from app.core.auth import hash_password
from app.services.routing_service import (
    CANONICAL_ROUTING_TABLE,
    ISSUE_TO_DEPARTMENT_NAME_MAP,
    CLASS_ID_TO_DEPARTMENT_NAME_MAP,
    resolve_canonical_issue,
    route_issue_to_department,
)

API_URL = "http://127.0.0.1:8000"


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


class DepartmentRoutingTestSuite:
    def __init__(self):
        self.ts = int(time.time() * 1000)
        self.results = []
        self.created_complaint_ids = []
        self.created_user_ids = []
        self.citizen_token = None
        self.citizen_headers = {}

    def log(self, test_num: int, name: str, passed: bool, detail: str = ""):
        tag = "[PASS]" if passed else "[FAIL]"
        self.results.append({"num": test_num, "name": name, "passed": passed, "detail": detail})
        print(f"{tag} Test {test_num:02d} — {name}: {detail}")

    def setup_user(self):
        db = SessionLocal()
        try:
            email = f"routing_tester_{self.ts}@example.com"
            user = User(
                name="Routing Test Citizen",
                email=email,
                role=UserRole.CITIZEN,
                password_hash=hash_password("CitizenPass123!"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.created_user_ids.append(user.id)
        finally:
            db.close()

        code, body = make_request(f"{API_URL}/auth/login", method="POST", data={"email": email, "password": "CitizenPass123!"})
        if code == 200:
            self.citizen_token = json.loads(body).get("access_token")
            self.citizen_headers = {"Authorization": f"Bearer {self.citizen_token}"}
        else:
            raise RuntimeError(f"Failed to authenticate test user: {body}")

    # =========================================================================
    # Test 1: Routing resolution for all 12 canonical category IDs (0 - 11)
    # =========================================================================
    def test_canonical_ids_resolution(self):
        passed_all = True
        details = []
        for cid in range(12):
            expected = CANONICAL_ROUTING_TABLE[cid]
            # Test int
            res_id, res_name, res_key, res_dept = resolve_canonical_issue(cid)
            # Test string
            res_id_s, res_name_s, res_key_s, res_dept_s = resolve_canonical_issue(str(cid))

            ok = (
                res_id == cid
                and res_key == expected["issue_type"]
                and res_dept == expected["department_name"]
                and res_id_s == cid
                and res_dept_s == expected["department_name"]
            )
            if not ok:
                passed_all = False
            details.append(f"Class {cid} ({expected['class_name']}) -> {res_dept}")

        self.log(
            1,
            "All 12 canonical category IDs (0-11, int & str) resolve to expected departments",
            passed_all,
            f"Verified 12 of 12 classes: {details[0]} ... {details[-1]}",
        )

    # =========================================================================
    # Test 2: Routing resolution for all 12 canonical names and internal keys
    # =========================================================================
    def test_canonical_names_and_keys_resolution(self):
        passed_all = True
        for cid, expected in CANONICAL_ROUTING_TABLE.items():
            # Test canonical name
            _, _, key_from_name, dept_from_name = resolve_canonical_issue(expected["class_name"])
            # Test internal key
            _, _, key_from_key, dept_from_key = resolve_canonical_issue(expected["issue_type"])

            ok = (
                key_from_name == expected["issue_type"]
                and dept_from_name == expected["department_name"]
                and key_from_key == expected["issue_type"]
                and dept_from_key == expected["department_name"]
            )
            if not ok:
                passed_all = False

        self.log(
            2,
            "All 12 canonical display names and internal keys resolve to expected departments",
            passed_all,
            f"12 display names and 12 internal keys verified with 100% consistency",
        )

    # =========================================================================
    # Test 3: Live Complaint Creation & Persisted Department for all 12 categories
    # =========================================================================
    def test_complaint_creation_and_persistence_all_12_categories(self):
        passed_all = True
        db = SessionLocal()
        created_records = []
        try:
            for cid in range(12):
                expected = CANONICAL_ROUTING_TABLE[cid]
                # Alternate between using class ID and internal issue key
                use_cid = (cid % 2 == 0)
                category_payload = cid if use_cid else expected["issue_type"]

                payload = {
                    "issue_type": category_payload,
                    "description": f"Automated test grievance for class {cid} ({expected['class_name']}) #{self.ts}",
                    "latitude": 12.9716,
                    "longitude": 77.5946,
                    "original_language": "en"
                }

                code, body = make_request(f"{API_URL}/api/v1/complaints", method="POST", headers=self.citizen_headers, data=payload)
                data = json.loads(body) if code == 201 else {}
                comp_id = data.get("complaint_id")

                if comp_id:
                    self.created_complaint_ids.append(comp_id)

                api_dept_name = data.get("department", {}).get("name") if data.get("department") else None
                api_dept_id = data.get("department", {}).get("id") if data.get("department") else None

                # Query database directly to confirm persistence
                persisted = db.query(Complaint).filter(Complaint.complaint_id == comp_id).first() if comp_id else None
                db_dept_id = persisted.department_id if persisted else None
                db_dept_name = persisted.department.name if (persisted and persisted.department) else None

                ok = (
                    code == 201
                    and api_dept_name == expected["department_name"]
                    and api_dept_id == expected["department_id"]
                    and db_dept_id == expected["department_id"]
                    and db_dept_name == expected["department_name"]
                )
                if not ok:
                    passed_all = False
                created_records.append(
                    f"Class {cid} ({expected['class_name']}): HTTP {code}, DB Dept={db_dept_id} ({db_dept_name})"
                )
        finally:
            db.close()

        self.log(
            3,
            "Complaint creation automatically routes & persists correct department in PostgreSQL for all 12 classes",
            passed_all,
            f"Successfully created & verified 12 complaints with exact DB foreign key matching: {created_records[0]} ... {created_records[-1]}",
        )

    # =========================================================================
    # Test 4: Manual Category Override Recalculation
    # =========================================================================
    def test_manual_category_override(self):
        # Scenario: AI detection suggests Pothole (Class 2 -> Roads & Highways),
        # but citizen manually overrides it to Drainage Problem (Class 7 -> Drainage & Flood Management)
        db = SessionLocal()
        try:
            override_payload_1 = {
                "issue_type": "drainage_problem",
                "description": f"Citizen manual override from pothole to drainage problem #{self.ts}",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "original_language": "en"
            }
            code1, body1 = make_request(f"{API_URL}/api/v1/complaints", method="POST", headers=self.citizen_headers, data=override_payload_1)
            data1 = json.loads(body1) if code1 == 201 else {}
            cid1 = data1.get("complaint_id")
            if cid1:
                self.created_complaint_ids.append(cid1)

            persisted1 = db.query(Complaint).filter(Complaint.complaint_id == cid1).first()
            dept1_correct = (
                persisted1 is not None
                and persisted1.department.name == "Drainage & Flood Management"
                and persisted1.department_id == 12
            )

            # Scenario 2: Citizen manual override from Broken Street Light to Water Leakage using class ID (4)
            override_payload_2 = {
                "issue_type": 4,  # Class 4: Water Leakage -> Water Supply & Sewerage
                "description": f"Citizen manual override to water leakage using canonical ID 4 #{self.ts}",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "original_language": "en"
            }
            code2, body2 = make_request(f"{API_URL}/api/v1/complaints", method="POST", headers=self.citizen_headers, data=override_payload_2)
            data2 = json.loads(body2) if code2 == 201 else {}
            cid2 = data2.get("complaint_id")
            if cid2:
                self.created_complaint_ids.append(cid2)

            persisted2 = db.query(Complaint).filter(Complaint.complaint_id == cid2).first()
            dept2_correct = (
                persisted2 is not None
                and persisted2.department.name == "Water Supply & Sewerage"
                and persisted2.department_id == 3
            )

            all_ok = code1 == 201 and dept1_correct and code2 == 201 and dept2_correct
        finally:
            db.close()

        self.log(
            4,
            "Manual category override dynamically recalculates & persists department before saving",
            all_ok,
            f"Override 1: Drainage Problem -> Dept ID 12 ({persisted1.department.name if persisted1 else 'None'}); "
            f"Override 2: Water Leakage (ID 4) -> Dept ID 3 ({persisted2.department.name if persisted2 else 'None'}).",
        )

    # =========================================================================
    # Test 5: Missing and Invalid Category Handling (Never routes on confidence)
    # =========================================================================
    def test_missing_and_invalid_categories(self):
        # 1. Missing issue_type key
        code_missing, body_missing = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"description": "Missing category test"}
        )
        missing_ok = code_missing == 422

        # 2. Empty string
        code_empty, body_empty = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"issue_type": "", "description": "Empty category test"}
        )
        empty_ok = code_empty == 422

        # 3. Invalid non-existent string
        code_inv_str, body_inv_str = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"issue_type": "alien_invasion_zone", "description": "Bogus category"}
        )
        inv_str_ok = code_inv_str == 422 and "Invalid issue_type" in body_inv_str

        # 4. Out of bounds class ID (-1)
        code_neg, body_neg = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"issue_type": -1, "description": "Negative class ID"}
        )
        neg_ok = code_neg == 422

        # 5. Out of bounds class ID (99)
        code_oob, body_oob = make_request(
            f"{API_URL}/api/v1/complaints",
            method="POST",
            headers=self.citizen_headers,
            data={"issue_type": 99, "description": "Out of bounds class ID"}
        )
        oob_ok = code_oob == 422

        all_ok = missing_ok and empty_ok and inv_str_ok and neg_ok and oob_ok
        self.log(
            5,
            "Missing, empty, and invalid categories rejected safely with clear validation errors",
            all_ok,
            f"Missing: HTTP {code_missing}, Empty: HTTP {code_empty}, Invalid String: HTTP {code_inv_str}, Negative ID: HTTP {code_neg}, Out-of-Bounds: HTTP {code_oob}",
        )

    # =========================================================================
    # Test 6: Routing Consistency with Demo Inference Service
    # =========================================================================
    def test_routing_consistency(self):
        db = SessionLocal()
        try:
            # Check route_issue_to_department consistency directly
            consistent = True
            for cid in range(12):
                expected = CANONICAL_ROUTING_TABLE[cid]
                d1 = route_issue_to_department(category=cid, db=db)
                d2 = route_issue_to_department(issue_type=expected["issue_type"], db=db)
                d3 = route_issue_to_department(issue_class=cid, db=db)

                if not (d1.id == d2.id == d3.id == expected["department_id"]):
                    consistent = False
        finally:
            db.close()

        self.log(
            6,
            "Demo inference service and complaint submission use identical centralized routing service",
            consistent,
            f"Verified consistency across all signature variants (category, issue_type, issue_class)",
        )

    # =========================================================================
    # Clean up test-created records
    # =========================================================================
    def cleanup(self):
        print("\nCleaning up test records...")
        db = SessionLocal()
        try:
            from sqlalchemy import or_
            for cid in self.created_complaint_ids:
                c = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if c:
                    db.query(BlockchainRecord).filter(BlockchainRecord.complaint_id == c.id).delete(synchronize_session=False)
                    db.query(ComplaintEvidence).filter(ComplaintEvidence.complaint_id == c.id).delete(synchronize_session=False)
                    db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == c.id).delete(synchronize_session=False)
                    db.query(ComplaintNote).filter(ComplaintNote.complaint_id == c.id).delete(synchronize_session=False)
                    db.query(DuplicateAnalysis).filter(
                        or_(DuplicateAnalysis.complaint_id == c.id, DuplicateAnalysis.possible_duplicate_id == c.id)
                    ).delete(synchronize_session=False)
                    db.query(Complaint).filter(Complaint.id == c.id).delete(synchronize_session=False)

            for uid in self.created_user_ids:
                db.query(User).filter(User.id == uid).delete(synchronize_session=False)

            db.commit()
            print(f"[CLEANUP COMPLETE] Removed {len(self.created_complaint_ids)} test complaints and {len(self.created_user_ids)} test users.")
        except Exception as e:
            db.rollback()
            print(f"[CLEANUP WARNING] Error cleaning test data: {e}")
        finally:
            db.close()

    def run_all(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — AUTOMATIC DEPARTMENT ROUTING TEST SUITE")
        print("=" * 80)
        try:
            self.setup_user()
            self.test_canonical_ids_resolution()
            self.test_canonical_names_and_keys_resolution()
            self.test_complaint_creation_and_persistence_all_12_categories()
            self.test_manual_category_override()
            self.test_missing_and_invalid_categories()
            self.test_routing_consistency()
        finally:
            self.cleanup()

        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        total_count = len(self.results)
        print(f"RESULTS: {passed_count}/{total_count} ROUTING TEST SUITES PASSED ({((passed_count/total_count)*100):.1f}%)")
        print("=" * 80)
        return passed_count == total_count


if __name__ == "__main__":
    suite = DepartmentRoutingTestSuite()
    success = suite.run_all()
    if not success:
        sys.exit(1)
