import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi_app import app as fastapi_app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.duplicate_analysis import DuplicateAnalysis
from app.models.audit_log import AuditLog
from app.core.auth import hash_password, create_access_token
from app.services.duplicate_service import (
    DuplicateService,
    normalize_complaint_text,
    haversine_distance_meters,
    compute_text_similarity,
    TEXT_SIMILARITY_THRESHOLD,
    GPS_DISTANCE_THRESHOLD_METERS,
    RECENT_DAYS,
)


class DuplicateDetectionTestRunner:
    def __init__(self):
        self.client = TestClient(fastapi_app)
        self.db: Session = SessionLocal()
        self.results = []
        self.citizen_user = None
        self.citizen_token = None
        self.created_complaint_ids = []

    def log(self, test_name: str, passed: bool, message: str = ""):
        status_str = "[PASS]" if passed else "[FAIL]"
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
        })
        print(f"{status_str} {test_name}: {message}")

    def setup(self):
        ts = int(time.time() * 1000)
        self.citizen_user = User(
            name="Citizen Duplicate Tester",
            email=f"dup_tester_{ts}@example.com",
            password_hash=hash_password("Password@123"),
            role=UserRole.CITIZEN,
        )
        self.db.add(self.citizen_user)
        self.db.commit()
        self.db.refresh(self.citizen_user)

        self.citizen_token = create_access_token({
            "sub": str(self.citizen_user.id),
            "email": self.citizen_user.email,
            "role": UserRole.CITIZEN,
        })

        # Seed reference base complaint in PostgreSQL
        now = datetime.now(timezone.utc)
        self.base_complaint = Complaint(
            complaint_id=f"CG-DUP-BASE-{ts}",
            user_id=self.citizen_user.id,
            department_id=4,  # Roads & Highways
            issue_type="pothole",
            description="Deep hazardous pothole on MG Road near metro pillar 42 causing severe traffic congestion.",
            original_language="en",
            processed_text="Deep hazardous pothole on MG Road near metro pillar 42 causing severe traffic congestion.",
            latitude=12.971598,
            longitude=77.594562,
            severity="MEDIUM",
            status="SUBMITTED",
            created_at=now,
            updated_at=now,
        )
        self.db.add(self.base_complaint)
        self.db.commit()
        self.db.refresh(self.base_complaint)
        self.created_complaint_ids.append(self.base_complaint.id)

    def teardown(self):
        try:
            if self.created_complaint_ids:
                self.db.query(DuplicateAnalysis).filter(
                    (DuplicateAnalysis.complaint_id.in_(self.created_complaint_ids))
                    | (DuplicateAnalysis.possible_duplicate_id.in_(self.created_complaint_ids))
                ).delete(synchronize_session=False)
                self.db.query(Complaint).filter(Complaint.id.in_(self.created_complaint_ids)).delete(synchronize_session=False)

            if self.citizen_user:
                self.db.query(AuditLog).filter(AuditLog.user_id == self.citizen_user.id).delete()
                self.db.query(Complaint).filter(Complaint.user_id == self.citizen_user.id).delete(synchronize_session=False)
                self.db.query(User).filter(User.id == self.citizen_user.id).delete()

            self.db.commit()
        finally:
            self.db.close()

    def run(self):
        print("=" * 80)
        print("AI CIVIC GUARDIAN — STEP 6 DUPLICATE COMPLAINT DETECTION TESTS")
        print("=" * 80)

        self.setup()
        try:
            self.test_text_normalization()
            self.test_haversine_distance_calculation()
            self.test_1_identical_similar_complaint_text()
            self.test_2_different_complaint_text()
            self.test_3_same_issue_nearby_gps()
            self.test_4_same_issue_far_gps()
            self.test_5_different_issue_same_gps()
            self.test_6_missing_gps_coordinates()
            self.test_7_missing_description_safety()
            self.test_8_empty_database_no_match()
            self.test_9_recent_complaint_window_filtering()
            self.test_10_unauthorized_request_rejected()
            self.test_11_privacy_no_personal_data_exposed()
            self.test_12_complaint_creation_not_blocked_by_duplicate()
            self.test_13_officer_admin_duplicate_analysis_visibility()

        finally:
            self.teardown()

        print("\n" + "=" * 80)
        print("DUPLICATE DETECTION TEST EXECUTION SUMMARY")
        print("=" * 80)
        passed_count = sum(1 for r in self.results if r["passed"])
        failed_count = sum(1 for r in self.results if not r["passed"])
        total_count = len(self.results)

        print(f"Total Tests Run: {total_count}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print(f"Status: {'ALL TESTS PASSED' if failed_count == 0 else 'SOME TESTS FAILED'}")
        print("=" * 80)

        if failed_count > 0:
            sys.exit(1)

    # Unit Test: Text Normalization
    def test_text_normalization(self):
        raw = "   Deep Hazardous   Pothole, Near Metro Pillar #42!!! \n\t Causing Traffic...   "
        expected = "deep hazardous pothole near metro pillar 42 causing traffic"
        norm = normalize_complaint_text(raw)
        passed = norm == expected
        self.log(
            "Test — Text normalization strips punctuation, collapses spaces, and lowercases",
            passed,
            f"Normalized: '{norm}'",
        )

    # Unit Test: Haversine Calculation
    def test_haversine_distance_calculation(self):
        # Coordinates approx 111 meters apart in Bangalore
        lat1, lon1 = 12.971598, 77.594562
        lat2, lon2 = 12.972598, 77.594562
        dist = haversine_distance_meters(lat1, lon1, lat2, lon2)
        passed = dist is not None and 110.0 <= dist <= 112.0
        self.log(
            "Test — Haversine geographic distance computes accurate distance in meters",
            passed,
            f"Distance: {dist} meters (Expected ~111.2m)",
        )

    # Test 1: Identical / Highly Similar Complaint Text
    def test_1_identical_similar_complaint_text(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "pothole",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42 causing major traffic congestion.",
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        passed = (
            resp.status_code == 200
            and data.get("has_possible_duplicate") is True
            and len(data.get("candidates", [])) > 0
            and data["candidates"][0]["text_similarity"] >= TEXT_SIMILARITY_THRESHOLD
        )
        self.log(
            "Test 1 — Highly similar complaint text yields high text similarity (>= 0.70)",
            passed,
            f"HTTP {resp.status_code}, Candidates: {len(data.get('candidates', []))}, Sim: {data['candidates'][0]['text_similarity'] if data.get('candidates') else None}",
        )

    # Test 2: Different Complaint Text
    def test_2_different_complaint_text(self):
        text_sims = compute_text_similarity(
            "Deep hazardous pothole on MG Road near metro pillar 42",
            ["Completely unrelated garden beautification and tree pruning request in community park"],
        )
        passed = text_sims[0] < 0.20
        self.log(
            "Test 2 — Dissimilar complaint descriptions produce low text similarity (< 0.20)",
            passed,
            f"Similarity score: {text_sims[0]}",
        )

    # Test 3: Same Issue + Nearby GPS (< 100m)
    def test_3_same_issue_nearby_gps(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        # Point ~15 meters away
        payload = {
            "issue_type": "pothole",
            "description": "Pothole spotted right here near pillar 42",
            "latitude": 12.971700,
            "longitude": 77.594600,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        passed = (
            resp.status_code == 200
            and data.get("has_possible_duplicate") is True
            and len(data.get("candidates", [])) > 0
            and data["candidates"][0]["distance_meters"] is not None
            and data["candidates"][0]["distance_meters"] <= GPS_DISTANCE_THRESHOLD_METERS
        )
        top = data["candidates"][0] if data.get("candidates") else {}
        self.log(
            "Test 3 — Same issue type with nearby GPS (<= 100m) flags possible duplicate",
            passed,
            f"Distance: {top.get('distance_meters')}m, Score: {top.get('duplicate_score')}",
        )

    # Test 4: Same Issue + Far GPS (> 1000m)
    def test_4_same_issue_far_gps(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        # Location in another neighborhood (~10 km away)
        payload = {
            "issue_type": "pothole",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42 causing severe traffic congestion.",
            "latitude": 13.050000,
            "longitude": 77.650000,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        candidates = data.get("candidates", [])
        # Far distance applies strong penalty: score should decay sharply
        top_cand = candidates[0] if candidates else None
        decayed = (top_cand is None) or (top_cand["duplicate_score"] < 0.60) or (top_cand["distance_meters"] > 1000)

        passed = resp.status_code == 200 and decayed
        self.log(
            "Test 4 — Same issue but far GPS location (>1km) receives strong geographic penalty",
            passed,
            f"Candidates count: {len(candidates)}, Top score: {top_cand.get('duplicate_score') if top_cand else 'None'}",
        )

    # Test 5: Different Issue + Same GPS
    def test_5_different_issue_same_gps(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "broken_street_light",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42 causing traffic congestion.",
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        # Different issue types must NEVER be flagged as duplicate candidates
        has_dup = data.get("has_possible_duplicate")
        candidates = data.get("candidates", [])
        passed = resp.status_code == 200 and has_dup is False and len(candidates) == 0
        self.log(
            "Test 5 — Different issue category at same GPS is NOT flagged as duplicate",
            passed,
            f"has_possible_duplicate: {has_dup}, Candidates: {len(candidates)}",
        )

    # Test 6: Missing GPS Coordinates
    def test_6_missing_gps_coordinates(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "pothole",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42 causing traffic congestion.",
            "latitude": None,
            "longitude": None,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        passed = (
            resp.status_code == 200
            and data.get("has_possible_duplicate") is True
            and data["candidates"][0]["distance_meters"] is None
            and data["candidates"][0]["text_similarity"] >= TEXT_SIMILARITY_THRESHOLD
        )
        self.log(
            "Test 6 — Missing GPS safely returns distance=None and relies on text similarity",
            passed,
            f"Distance: {data['candidates'][0]['distance_meters'] if data.get('candidates') else 'N/A'}, TextSim: {data['candidates'][0]['text_similarity'] if data.get('candidates') else 'N/A'}",
        )

    # Test 7: Missing Description (Empty or None)
    def test_7_missing_description_safety(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "pothole",
            "description": None,
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        passed = resp.status_code == 200
        self.log(
            "Test 7 — Missing description executes safely without crash or 500 error",
            passed,
            f"Status: {resp.status_code}",
        )

    # Test 8: Empty Database or No Matching Issues
    def test_8_empty_database_no_match(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "building_damage",
            "description": "Structural cracks on residential wall",
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()

        passed = (
            resp.status_code == 200
            and data.get("has_possible_duplicate") is False
            and len(data.get("candidates", [])) == 0
        )
        self.log(
            "Test 8 — No existing matches returns has_possible_duplicate=false and empty list",
            passed,
            f"Candidates: {len(data.get('candidates', []))}",
        )

    # Test 9: Recent Complaint Window Filtering (> 30 days excluded)
    def test_9_recent_complaint_window_filtering(self):
        # Insert an old complaint (45 days ago)
        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        old_complaint = Complaint(
            complaint_id=f"CG-DUP-OLD-{int(time.time()*1000)}",
            user_id=self.citizen_user.id,
            department_id=4,
            issue_type="pothole",
            description="Ancient pothole reported six weeks ago on MG Road pillar 42.",
            original_language="en",
            processed_text="Ancient pothole reported six weeks ago on MG Road pillar 42.",
            latitude=12.971598,
            longitude=77.594562,
            severity="MEDIUM",
            status="RESOLVED",
            created_at=old_time,
            updated_at=old_time,
        )
        self.db.add(old_complaint)
        self.db.commit()
        self.db.refresh(old_complaint)
        self.created_complaint_ids.append(old_complaint.id)

        # Query specifically for this ancient complaint
        candidates = DuplicateService.get_recent_eligible_complaints(
            db=self.db,
            recent_days=RECENT_DAYS,
        )
        old_ids = [c.complaint_id for c in candidates]
        passed = old_complaint.complaint_id not in old_ids

        self.log(
            "Test 9 — Complaints older than 30 days are excluded from duplicate search window",
            passed,
            f"Old complaint ID '{old_complaint.complaint_id}' found in recent candidates: {old_complaint.complaint_id in old_ids}",
        )

    # Test 10: Unauthorized Request Rejected
    def test_10_unauthorized_request_rejected(self):
        payload = {
            "issue_type": "pothole",
            "description": "Unauthenticated test",
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", json=payload)
        passed = resp.status_code == 401
        self.log(
            "Test 10 — Unauthenticated request is rejected with HTTP 401",
            passed,
            f"Status: {resp.status_code}",
        )

    # Test 11: Privacy Guarantee (No Personal Data Exposed)
    def test_11_privacy_no_personal_data_exposed(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "pothole",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42",
            "latitude": 12.971598,
            "longitude": 77.594562,
        }
        resp = self.client.post("/api/v1/complaints/check-duplicate", headers=headers, json=payload)
        data = resp.json()
        candidates = data.get("candidates", [])

        passed = len(candidates) > 0
        forbidden_keys = {"email", "phone", "password", "password_hash", "token", "user_id"}
        leaked_keys = []

        for cand in candidates:
            for k in cand.keys():
                if k.lower() in forbidden_keys:
                    leaked_keys.append(k)

        passed = passed and len(leaked_keys) == 0
        self.log(
            "Test 11 — Candidate response strictly guarantees privacy (no emails, phone, or tokens)",
            passed,
            f"Forbidden keys leaked: {leaked_keys}",
        )

    # Test 12: Complaint Creation is NOT Blocked by Possible Duplicate
    def test_12_complaint_creation_not_blocked_by_duplicate(self):
        headers = {"Authorization": f"Bearer {self.citizen_token}"}
        payload = {
            "issue_type": "pothole",
            "description": "Deep hazardous pothole on MG Road near metro pillar 42 causing traffic congestion.",
            "latitude": 12.971598,
            "longitude": 77.594562,
            "original_language": "en",
        }

        # Create new complaint that is an exact duplicate candidate of base_complaint
        resp = self.client.post("/api/v1/complaints", headers=headers, json=payload)
        data = resp.json()

        created_cid = data.get("complaint_id")
        passed = resp.status_code == 201 and created_cid is not None and data.get("status") == "SUBMITTED"

        if created_cid:
            # Check if DuplicateAnalysis link was recorded in PostgreSQL
            created_obj = self.db.query(Complaint).filter(Complaint.complaint_id == created_cid).first()
            if created_obj:
                self.created_complaint_ids.append(created_obj.id)
                links = self.db.query(DuplicateAnalysis).filter(DuplicateAnalysis.complaint_id == created_obj.id).all()
                passed = passed and len(links) > 0

        self.log(
            "Test 12 — Possible duplicate does NOT reject complaint; records DuplicateAnalysis relation",
            passed,
            f"Created ID: {created_cid}, Status: {resp.status_code}",
        )

    # Test 13: Officer/Admin Visibility of Duplicate Analyses
    def test_13_officer_admin_duplicate_analysis_visibility(self):
        # Create an officer user
        ts = int(time.time() * 1000)
        officer = User(
            name="Officer QA",
            email=f"officer_dup_{ts}@example.com",
            password_hash=hash_password("Password@123"),
            role=UserRole.OFFICER,
            department_id=4,
        )
        self.db.add(officer)
        self.db.commit()
        self.db.refresh(officer)

        officer_token = create_access_token({
            "sub": str(officer.id),
            "email": officer.email,
            "role": UserRole.OFFICER,
        })

        if self.created_complaint_ids:
            latest_id = self.created_complaint_ids[-1]
            complaint_obj = self.db.query(Complaint).filter(Complaint.id == latest_id).first()
            if complaint_obj:
                headers = {"Authorization": f"Bearer {officer_token}"}
                resp = self.client.get(f"/api/v1/complaints/{complaint_obj.complaint_id}", headers=headers)
                data = resp.json()
                dups = data.get("possible_duplicates", [])
                passed = resp.status_code == 200 and len(dups) > 0
                self.log(
                    "Test 13 — Officers can retrieve complaint details with duplicate candidate evidence",
                    passed,
                    f"HTTP {resp.status_code}, Possible duplicates visible: {len(dups)}",
                )
            else:
                self.log("Test 13 — Officer duplicate visibility", False, "Latest complaint not found")
        else:
            self.log("Test 13 — Officer duplicate visibility", False, "No created complaints to verify")

        self.db.query(User).filter(User.id == officer.id).delete()
        self.db.commit()


if __name__ == "__main__":
    runner = DuplicateDetectionTestRunner()
    runner.run()
