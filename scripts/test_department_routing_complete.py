"""
AI Civic Guardian — Complete End-to-End Automatic Department Routing Test Suite

Verifies:
1. Centralized Issue-to-Department Canonical Mappings (all 12 categories)
2. Multi-Lingual Description Classification (English, Tamil, Tanglish)
3. End-to-End Automatic Complaint Submission & Database Persistence (no citizen department selection)
4. Uncertain Complaint Handling (marked NEEDS_HUMAN_REVIEW, no fake AI detection)
5. Strict Officer Department Isolation & Access Restrictions (cross-department HTTP 403)
6. Citizen Tracking & Complaint Details Department Display
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone


from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.complaints.constants import (
    STATUS_SUBMITTED,
    STATUS_NEEDS_HUMAN_REVIEW,
    ISSUE_GARBAGE_OVERFLOW,
    ISSUE_ILLEGAL_DUMPING,
    ISSUE_POTHOLE,
    ISSUE_DAMAGED_ROAD,
    ISSUE_WATER_LEAKAGE,
    ISSUE_SEWAGE_OVERFLOW,
    ISSUE_BROKEN_STREET_LIGHT,
    ISSUE_DRAINAGE_PROBLEM,
    ISSUE_TRAFFIC_ISSUE,
    ISSUE_BUILDING_DAMAGE,
    ISSUE_PARK_DAMAGE,
    ISSUE_ENVIRONMENTAL_POLLUTION,
)
from app.services.routing_service import (
    CANONICAL_ROUTING_TABLE,
    resolve_canonical_issue,
    classify_issue_from_description,
    route_issue_to_department,
    get_routing_for_issue,
)

BASE_URL = "http://127.0.0.1:8000"


def print_step(title):
    print(f"\n{'='*75}\n[*] {title}\n{'='*75}")


def api_post(endpoint, payload, token=None):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed


def api_get(endpoint, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed


# -----------------------------------------------------------------------------
# Test 1: Canonical Issue-to-Department Mappings (All 12 Classes)
# -----------------------------------------------------------------------------
def test_all_12_canonical_mappings():
    print_step("TEST 1: Canonical 12 Issue-to-Department Mappings")
    db = SessionLocal()
    passed = 0
    try:
        for cid, expected in CANONICAL_ROUTING_TABLE.items():
            # 1. Resolve canonical issue by int ID
            class_id, class_name, issue_key, dept_name = resolve_canonical_issue(cid)
            assert class_id == expected["class_id"], f"Class ID mismatch for {cid}"
            assert class_name == expected["class_name"], f"Class name mismatch for {cid}"
            assert issue_key == expected["issue_type"], f"Issue key mismatch for {cid}"
            assert dept_name == expected["department_name"], f"Dept name mismatch for {cid}"

            # 2. Resolve canonical issue by key string
            _, _, resolved_key, _ = resolve_canonical_issue(expected["issue_type"])
            assert resolved_key == expected["issue_type"]

            # 3. Route to live PostgreSQL department record
            dept_record = route_issue_to_department(cid, db)
            assert dept_record is not None, f"Department ORM not found for {cid}"
            assert dept_record.id == expected["department_id"], (
                f"Dept ID mismatch: {dept_record.id} vs {expected['department_id']}"
            )
            assert dept_record.name == expected["department_name"], (
                f"Dept name mismatch: {dept_record.name} vs {expected['department_name']}"
            )

            print(f"  [PASS] Class {cid:02d}: {class_name:<28} -> {dept_record.name} (Dept ID: {dept_record.id})")
            passed += 1

        assert passed == 12, "Not all 12 classes passed mapping test"
        print(f"\n>> All 12 canonical issues correctly and deterministically map to active departments in PostgreSQL.")
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Test 2: Description-Based Classification (English, Tamil, Tanglish)
# -----------------------------------------------------------------------------
def test_description_nlp_classification():
    print_step("TEST 2: Multi-Lingual Description Classification (NLP)")
    test_cases = [
        # English
        ("Large dangerous pothole on Trichy road causing bike accidents", ISSUE_POTHOLE),
        ("Tar road is cracked and broken with bumpy uneven surface", ISSUE_DAMAGED_ROAD),
        ("Municipal garbage bin is overflowing with rotten rubbish and trash", ISSUE_GARBAGE_OVERFLOW),
        ("Truck dumped construction debris and building rubble on roadside illegally", ISSUE_ILLEGAL_DUMPING),
        ("Water pipe burst and clean drinking water is leaking heavily", ISSUE_WATER_LEAKAGE),
        ("Manhole overflowing with foul smell sewage water spilling into street", ISSUE_SEWAGE_OVERFLOW),
        ("Street light not working and entire avenue is completely dark at night", ISSUE_BROKEN_STREET_LIGHT),
        ("Storm drain is blocked causing stagnant rainwater waterlogging", ISSUE_DRAINAGE_PROBLEM),
        ("Heavy traffic jam and gridlock at Gandhipuram signal due to signal failure", ISSUE_TRAFFIC_ISSUE),
        ("Old dilapidated building with cracked wall at risk of structural collapse", ISSUE_BUILDING_DAMAGE),
        ("Public park playground swing is broken and children benches damaged", ISSUE_PARK_DAMAGE),
        ("Industrial chemical factory releasing black toxic smoke causing air pollution", ISSUE_ENVIRONMENTAL_POLLUTION),
        # Tanglish
        ("Big kuzhi on the road near cross cut junction", ISSUE_POTHOLE),
        ("Kuppai thotti is full and smelling bad", ISSUE_GARBAGE_OVERFLOW),
        ("Theruvilakku is not working darkness everywhere", ISSUE_BROKEN_STREET_LIGHT),
        ("Vaadikkaal adaipu rain water not going", ISSUE_DRAINAGE_PROBLEM),
        # Uncertain / Non-civic
        ("Hello, please check this complaint and let me know", None),
        ("Random text with no civic issue keywords at all", None),
    ]

    for desc, expected_issue in test_cases:
        detected_issue, conf, matched = classify_issue_from_description(desc)
        if expected_issue is None:
            assert detected_issue is None, f"Expected None for uncertain text but got {detected_issue}"
            print(f"  [PASS] Uncertain description -> Correctly returned None (conf: {conf})")
        else:
            assert detected_issue == expected_issue, (
                f"Mismatch for '{desc[:40]}...': Expected {expected_issue}, got {detected_issue}"
            )
            assert conf >= 0.50, f"Confidence too low: {conf}"
            print(f"  [PASS] '{desc[:42]}...' -> {detected_issue} ({int(conf*100)}% conf)")

    print("\n>> Multi-lingual description classification passed with high accuracy and safe uncertainty handling.")


# -----------------------------------------------------------------------------
# Test 3: End-to-End Automatic Complaint Submission (No citizen dept selection)
# -----------------------------------------------------------------------------
def test_automatic_complaint_submission():
    print_step("TEST 3: End-to-End Automatic Department Routing via API & PostgreSQL Persistence")
    db = SessionLocal()
    try:
        # Ensure citizen account exists
        api_post("/auth/register", {
            "name": "Routing Test Citizen",
            "email": "routing_test_citizen@civic.gov",
            "password": "Password123!",
            "phone_number": "9123456780",
        })

        # Login to get JWT token
        status_code, login_resp = api_post("/auth/login", {
            "email": "routing_test_citizen@civic.gov",
            "password": "Password123!",
        })
        assert status_code == 200, f"Citizen login failed: {login_resp}"
        citizen_token = login_resp["access_token"]


        submission_cases = [
            {
                "description": "Deep dangerous pothole on Trichy road near flyover causing severe vehicular traffic hazard",
                "lat": 11.0168,
                "lon": 76.9558,
                "expected_category": ISSUE_POTHOLE,
                "expected_dept_id": 4,
                "expected_dept_name": "Roads & Highways",
            },
            {
                "description": "Municipal garbage bin overflowing with rotting food waste and trash attracting stray animals",
                "lat": 11.0180,
                "lon": 76.9600,
                "expected_category": ISSUE_GARBAGE_OVERFLOW,
                "expected_dept_id": 6,
                "expected_dept_name": "Solid Waste Management",
            },
            {
                "description": "Main water pipeline burst and clean drinking water is leaking and flooding the road",
                "lat": 11.0150,
                "lon": 76.9520,
                "expected_category": ISSUE_WATER_LEAKAGE,
                "expected_dept_id": 3,
                "expected_dept_name": "Water Supply & Sewerage",
            },
            {
                "description": "Street light not working and entire street is completely dark for pedestrians at night",
                "lat": 11.0140,
                "lon": 76.9500,
                "expected_category": ISSUE_BROKEN_STREET_LIGHT,
                "expected_dept_id": 5,
                "expected_dept_name": "Electricity & Street Lighting",
            },
            {
                "description": "Storm drain clogged and rainwater stagnant causing severe drainage problem and flooding",
                "lat": 11.0175,
                "lon": 76.9580,
                "expected_category": ISSUE_DRAINAGE_PROBLEM,
                "expected_dept_id": 12,
                "expected_dept_name": "Drainage & Flood Management",
            },
        ]

        created_ids = {}

        for sc in submission_cases:
            # Citizen submits complaint WITHOUT selecting any department or issue category!
            payload = {
                "description": sc["description"],
                "latitude": sc["lat"],
                "longitude": sc["lon"],
                "original_language": "en",
                # Note: issue_type is intentionally omitted!
            }

            status_code, resp = api_post("/api/v1/complaints", payload, token=citizen_token)
            assert status_code == 201, f"Complaint creation failed: {resp}"

            cid = resp["complaint_id"]
            created_ids[sc["expected_category"]] = cid

            # Verify response payload
            assert resp["issue_type"] == sc["expected_category"], (
                f"Expected issue_type {sc['expected_category']}, got {resp['issue_type']}"
            )
            assert resp["department"] is not None, "Department is missing in response"
            assert resp["department"]["id"] == sc["expected_dept_id"], (
                f"Dept ID mismatch: {resp['department']['id']} vs {sc['expected_dept_id']}"
            )
            assert resp["department"]["name"] == sc["expected_dept_name"], (
                f"Dept name mismatch: {resp['department']['name']} vs {sc['expected_dept_name']}"
            )
            assert resp["status"] == STATUS_SUBMITTED

            # Verify directly in PostgreSQL database
            db_record = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
            assert db_record is not None, f"Database record not found for {cid}"
            assert db_record.department_id == sc["expected_dept_id"], (
                f"DB department_id mismatch: {db_record.department_id} vs {sc['expected_dept_id']}"
            )
            assert db_record.issue_type == sc["expected_category"], (
                f"DB issue_type mismatch: {db_record.issue_type} vs {sc['expected_category']}"
            )
            assert db_record.department.name == sc["expected_dept_name"]

            print(f"  [PASS] Submitted: {cid} | Cat: {resp['issue_type']} | Assigned: {resp['department']['name']} (DB Dept ID: {db_record.department_id})")

        print("\n>> All test complaints automatically assigned and persisted in PostgreSQL without citizen department selection.")
        return created_ids
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Test 4: Uncertain Complaint -> Routed for Manual Review (Requirement 7)
# -----------------------------------------------------------------------------
def test_uncertain_complaint_handling():
    print_step("TEST 4: Uncertain Complaint Routing & Manual Review Flag (Requirement 7)")
    status_code, login_resp = api_post("/auth/login", {
        "email": "routing_test_citizen@civic.gov",
        "password": "Password123!",
    })
    token = login_resp["access_token"]

    payload = {
        "description": "General municipal inquiry regarding ward certificates and timings",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "original_language": "en",
    }

    status_code, resp = api_post("/api/v1/complaints", payload, token=token)
    assert status_code == 201, f"Submission failed: {resp}"

    cid = resp["complaint_id"]
    assert resp["status"] == STATUS_NEEDS_HUMAN_REVIEW, f"Expected NEEDS_HUMAN_REVIEW, got {resp['status']}"
    assert resp["ai_confidence"] is None, "AI confidence must be None when no AI model ran"
    assert resp["department"] is not None, "Department must still be assigned for supervisory review"
    assert resp["department"]["id"] == 2, f"Expected Dept 2, got {resp['department']['id']}"

    db = SessionLocal()
    try:
        db_rec = db.query(Complaint).filter(Complaint.complaint_id == cid).first()
        assert db_rec.status == STATUS_NEEDS_HUMAN_REVIEW
        assert db_rec.department_id == 2
        assert db_rec.ai_confidence is None
        print(f"  [PASS] Uncertain complaint {cid} correctly marked {db_rec.status} and assigned to {db_rec.department.name} for human review (ai_confidence: None).")
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Test 5: Officer Department Isolation & Access Restrictions (Requirement 6)
# -----------------------------------------------------------------------------
def test_officer_department_isolation(created_complaints):
    print_step("TEST 5: Officer Department Isolation & Access Restrictions (Requirement 6)")
    # 1. Login as Roads Officer (Dept ID: 4)
    status_code, roads_login = api_post("/auth/login", {
        "email": "officer.pothole@civic.gov",
        "password": "Officer@Civic2026!",
    })
    assert status_code == 200, f"Roads officer login failed: {roads_login}"
    roads_token = roads_login["access_token"]

    # 2. Login as Sanitation Officer (Dept ID: 6)
    status_code, waste_login = api_post("/auth/login", {
        "email": "officer.garbage@civic.gov",
        "password": "Officer@Civic2026!",
    })
    assert status_code == 200, f"Sanitation officer login failed: {waste_login}"
    waste_token = waste_login["access_token"]

    pothole_id = created_complaints[ISSUE_POTHOLE]
    garbage_id = created_complaints[ISSUE_GARBAGE_OVERFLOW]

    # Verify Roads Officer dashboard view
    status_code, roads_dash = api_get("/api/v1/officer/dashboard", token=roads_token)
    assert status_code == 200
    assert roads_dash["department_id"] == 4
    assert roads_dash["department_name"] == "Roads & Highways"
    print(f"  [PASS] Roads Officer Dashboard: Department is {roads_dash['department_name']} (ID: 4)")

    # Verify Roads Officer complaint list contains Roads complaints only
    status_code, roads_list = api_get("/api/v1/officer/complaints?page=1&page_size=50", token=roads_token)
    assert status_code == 200
    roads_cids = [item["complaint_id"] for item in roads_list["items"]]
    assert pothole_id in roads_cids, f"Roads complaint {pothole_id} should be in Roads officer's list"
    assert garbage_id not in roads_cids, f"Sanitation complaint {garbage_id} must NOT be in Roads officer's list"
    print(f"  [PASS] Roads Officer list includes {pothole_id} and excludes {garbage_id}")

    # Verify cross-department single complaint access is blocked (HTTP 403)
    status_code, detail_resp = api_get(f"/api/v1/officer/complaints/{garbage_id}", token=roads_token)
    assert status_code == 403, f"Expected 403 for cross-department access, got {status_code}: {detail_resp}"
    print(f"  [PASS] Roads Officer accessing Sanitation complaint {garbage_id} -> HTTP 403 Forbidden as required")

    # Verify Sanitation Officer list contains Sanitation complaints only
    status_code, waste_list = api_get("/api/v1/officer/complaints?page=1&page_size=50", token=waste_token)
    assert status_code == 200
    waste_cids = [item["complaint_id"] for item in waste_list["items"]]
    assert garbage_id in waste_cids, f"Sanitation complaint {garbage_id} should be in Sanitation officer's list"
    assert pothole_id not in waste_cids, f"Roads complaint {pothole_id} must NOT be in Sanitation officer's list"
    print(f"  [PASS] Sanitation Officer list includes {garbage_id} and excludes {pothole_id}")

    # Verify Sanitation Officer cannot access Roads complaint (HTTP 403)
    status_code, detail_resp2 = api_get(f"/api/v1/officer/complaints/{pothole_id}", token=waste_token)
    assert status_code == 403, f"Expected 403 for cross-department access, got {status_code}: {detail_resp2}"
    print(f"  [PASS] Sanitation Officer accessing Roads complaint {pothole_id} -> HTTP 403 Forbidden as required")


# -----------------------------------------------------------------------------
# Test 6: Citizen Tracking & Details Department Display (Requirement 5)
# -----------------------------------------------------------------------------
def test_citizen_tracking_and_details_display(created_complaints):
    print_step("TEST 6: Citizen Tracking & Complaint Details Department Display (Requirement 5)")
    status_code, login_resp = api_post("/auth/login", {
        "email": "routing_test_citizen@civic.gov",
        "password": "Password123!",
    })
    token = login_resp["access_token"]

    pothole_id = created_complaints[ISSUE_POTHOLE]
    status_code, detail_resp = api_get(f"/api/v1/complaints/{pothole_id}", token=token)
    assert status_code == 200, f"Failed to get complaint detail: {detail_resp}"
    assert detail_resp["complaint_id"] == pothole_id
    assert detail_resp["department"] is not None
    assert detail_resp["department"]["id"] == 4
    assert detail_resp["department"]["name"] == "Roads & Highways"

    print(f"  [PASS] Citizen Tracking API for {pothole_id} returns Department: '{detail_resp['department']['name']}' (ID: 4)")
    print(">> Department is saved in DB and confirmed accessible for citizen tracking and detail views.")


def main():
    print(f"\n===========================================================================")
    print(f" AI CIVIC GUARDIAN — AUTOMATIC DEPARTMENT ROUTING TEST SUITE")
    print(f" Target Backend: {BASE_URL}")
    print(f" Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"===========================================================================")

    try:
        test_all_12_canonical_mappings()
        test_description_nlp_classification()
        created = test_automatic_complaint_submission()
        test_uncertain_complaint_handling()
        test_officer_department_isolation(created)
        test_citizen_tracking_and_details_display(created)

        print("\n" + "="*75)
        print(" [SUCCESS] ALL AUTOMATIC DEPARTMENT ROUTING TESTS PASSED (6/6 SUITES)")
        print("="*75 + "\n")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[FAIL] Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
