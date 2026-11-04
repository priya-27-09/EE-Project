"""
Automated Integration and Regression Tests for:
FEATURE UPDATE: LOCATION SEARCH BY PLACE NAME

Tests:
1. Location search for 'Gandhipuram, Coimbatore' returns valid candidates with verified coordinates.
2. Coordinate bounds checking: latitude in [-90, 90], longitude in [-180, 180].
3. Multiple matches behavior: multiple candidates returned for ambiguous place names.
4. Nonexistent place search returns clear message without substituting fake or default coordinates.
5. Reverse geocoding converts coordinates to human-readable address.
6. Complaint submission with place name, address, latitude, and longitude.
7. Verification that place name and address are persisted in PostgreSQL.
8. Verification that place name and address appear in Citizen, Officer, and Admin API responses.
9. Backward compatibility: existing complaints with only lat/lon continue to work.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.core.auth import create_access_token, hash_password
from app.services.geocoding_service import GeocodingService


class TestLocationSearchFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db: Session = SessionLocal()

        # Ensure active departments exist
        dept = cls.db.query(Department).filter(Department.name == "Roads & Highways").first()
        if not dept:
            dept = Department(name="Roads & Highways", description="Road Maintenance", active=True)
            cls.db.add(dept)
            cls.db.commit()
            cls.db.refresh(dept)
        cls.department = dept

        # 1. Setup Test Citizen
        citizen = cls.db.query(User).filter(User.email == "test_citizen_loc@example.com").first()
        if not citizen:
            citizen = User(
                name="Test Citizen Loc",
                email="test_citizen_loc@example.com",
                password_hash=hash_password("Password123!"),
                role=UserRole.CITIZEN,
                preferred_language="en",
            )
            cls.db.add(citizen)
            cls.db.commit()
            cls.db.refresh(citizen)
        cls.citizen = citizen
        cls.citizen_token = create_access_token({"sub": str(citizen.id), "role": citizen.role, "user_id": citizen.id})

        # 2. Setup Test Officer
        officer = cls.db.query(User).filter(User.email == "test_officer_loc@example.com").first()
        if not officer:
            officer = User(
                name="Test Officer Loc",
                email="test_officer_loc@example.com",
                password_hash=hash_password("Password123!"),
                role=UserRole.OFFICER,
                department_id=cls.department.id,
                preferred_language="en",
            )
            cls.db.add(officer)
            cls.db.commit()
            cls.db.refresh(officer)
        else:
            officer.department_id = cls.department.id
            cls.db.commit()
        cls.officer = officer
        cls.officer_token = create_access_token({"sub": str(officer.id), "role": officer.role, "user_id": officer.id})

        # 3. Setup Test Admin
        admin = cls.db.query(User).filter(User.email == "test_admin_loc@example.com").first()
        if not admin:
            admin = User(
                name="Test Admin Loc",
                email="test_admin_loc@example.com",
                password_hash=hash_password("Password123!"),
                role=UserRole.ADMIN,
                preferred_language="en",
            )
            cls.db.add(admin)
            cls.db.commit()
            cls.db.refresh(admin)
        cls.admin = admin
        cls.admin_token = create_access_token({"sub": str(admin.id), "role": admin.role, "user_id": admin.id})

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_search_gandhipuram_returns_valid_candidates(self):
        """Test searching 'Gandhipuram, Coimbatore' returns multiple candidates with verified coordinates."""
        results = GeocodingService.search_location("Gandhipuram, Coimbatore")
        self.assertTrue(len(results) >= 2, f"Expected multiple matching locations, got {len(results)}")

        for res in results:
            self.assertIn("place_name", res)
            self.assertIn("display_name", res)
            self.assertIn("latitude", res)
            self.assertIn("longitude", res)
            self.assertGreaterEqual(res["latitude"], -90.0)
            self.assertLessEqual(res["latitude"], 90.0)
            self.assertGreaterEqual(res["longitude"], -180.0)
            self.assertLessEqual(res["longitude"], 180.0)
            # Verify coordinates are around Coimbatore (~11.0, ~76.9)
            self.assertAlmostEqual(res["latitude"], 11.018, delta=0.5)
            self.assertAlmostEqual(res["longitude"], 76.964, delta=0.5)

    def test_02_api_search_location_endpoint(self):
        """Test GET /api/v1/complaints/search-location endpoint."""
        resp = self.client.get("/api/v1/complaints/search-location", params={"q": "Gandhipuram, Coimbatore"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), data["count"])

        # Check candidate structure
        first = data["results"][0]
        self.assertIn("Gandhipuram", first["place_name"])
        self.assertIsInstance(first["latitude"], float)
        self.assertIsInstance(first["longitude"], float)

    def test_03_nonexistent_search_returns_clear_message(self):
        """Test search for nonexistent place does not substitute a random/default location."""
        resp = self.client.get("/api/v1/complaints/search-location", params={"q": "xyznonexistentplace98765"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["results"]), 0)
        self.assertIsNotNone(data["message"])
        self.assertIn("No locations found", data["message"])

    def test_04_short_query_validation(self):
        """Test query with less than 2 characters gives clear prompt."""
        resp = self.client.get("/api/v1/complaints/search-location", params={"q": "a"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["count"], 0)
        self.assertIn("at least 2 characters", data["message"])

    def test_05_reverse_geocode_valid_and_invalid(self):
        """Test reverse geocoding with coordinates."""
        # Valid coordinates near Gandhipuram
        resp = self.client.get("/api/v1/complaints/reverse-geocode", params={"latitude": 11.0183, "longitude": 76.9644})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("place_name", data)
        self.assertIn("display_name", data)

        # Invalid coordinates out of range
        resp_invalid = self.client.get("/api/v1/complaints/reverse-geocode", params={"latitude": 120.0, "longitude": 76.9644})
        self.assertEqual(resp_invalid.status_code, 422)

    def test_06_submit_complaint_with_place_name_and_verify_storage(self):
        """
        Complete flow:
        - Enter 'Gandhipuram, Coimbatore'
        - Select result with coordinates
        - Submit complaint
        - Confirm place_name, address, latitude, and longitude stored in PostgreSQL
        - Verify they appear in citizen, officer, and admin endpoints
        """
        payload = {
            "issue_type": "pothole",
            "description": "Large pothole on Cross Cut Road near power house junction.",
            "original_language": "en",
            "place_name": "Cross Cut Road, Gandhipuram",
            "address": "Cross Cut Road, Gandhipuram, Coimbatore, Tamil Nadu, 641012, India",
            "latitude": 11.0195,
            "longitude": 76.9658,
        }

        # 1. Citizen submits complaint
        resp = self.client.post(
            "/api/v1/complaints",
            json=payload,
            headers={"Authorization": f"Bearer {self.citizen_token}"},
        )
        self.assertIn(resp.status_code, (200, 201), resp.text)
        created = resp.json()
        complaint_id = created["complaint_id"]
        self.assertTrue(complaint_id.startswith("CG-"))
        self.assertEqual(created["place_name"], payload["place_name"])
        self.assertEqual(created["address"], payload["address"])
        self.assertAlmostEqual(created["latitude"], payload["latitude"], places=4)
        self.assertAlmostEqual(created["longitude"], payload["longitude"], places=4)

        # 2. Verify directly in PostgreSQL via Session
        db_complaint = self.db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        self.assertIsNotNone(db_complaint)
        self.assertEqual(db_complaint.place_name, payload["place_name"])
        self.assertEqual(db_complaint.address, payload["address"])
        self.assertAlmostEqual(float(db_complaint.latitude), payload["latitude"], places=4)
        self.assertAlmostEqual(float(db_complaint.longitude), payload["longitude"], places=4)

        # 3. Verify Citizen Detail Endpoint
        cit_resp = self.client.get(
            f"/api/v1/complaints/{complaint_id}",
            headers={"Authorization": f"Bearer {self.citizen_token}"},
        )
        self.assertEqual(cit_resp.status_code, 200)
        cit_data = cit_resp.json()
        self.assertEqual(cit_data["place_name"], payload["place_name"])
        self.assertEqual(cit_data["address"], payload["address"])
        self.assertAlmostEqual(cit_data["latitude"], payload["latitude"], places=4)
        self.assertAlmostEqual(cit_data["longitude"], payload["longitude"], places=4)

        # 4. Verify Officer Detail Endpoint
        off_resp = self.client.get(
            f"/api/v1/officer/complaints/{complaint_id}",
            headers={"Authorization": f"Bearer {self.officer_token}"},
        )
        self.assertEqual(off_resp.status_code, 200)
        off_data = off_resp.json()
        self.assertEqual(off_data["place_name"], payload["place_name"])
        self.assertEqual(off_data["address"], payload["address"])
        self.assertAlmostEqual(off_data["latitude"], payload["latitude"], places=4)
        self.assertAlmostEqual(off_data["longitude"], payload["longitude"], places=4)

        # 5. Verify Officer List Endpoint
        off_list_resp = self.client.get(
            "/api/v1/officer/complaints",
            params={"search": complaint_id},
            headers={"Authorization": f"Bearer {self.officer_token}"},
        )
        self.assertEqual(off_list_resp.status_code, 200)
        off_list = off_list_resp.json()
        found_officer_item = next((item for item in off_list["items"] if item["complaint_id"] == complaint_id), None)
        self.assertIsNotNone(found_officer_item)
        self.assertEqual(found_officer_item["place_name"], payload["place_name"])
        self.assertEqual(found_officer_item["address"], payload["address"])

        # 6. Verify Admin List Endpoint
        admin_resp = self.client.get(
            "/api/v1/admin/complaints",
            params={"limit": 20},
            headers={"Authorization": f"Bearer {self.admin_token}"},
        )
        self.assertEqual(admin_resp.status_code, 200)
        admin_data = admin_resp.json()
        found_admin_item = next((item for item in admin_data["items"] if item["complaint_id"] == complaint_id), None)
        self.assertIsNotNone(found_admin_item)
        self.assertEqual(found_admin_item["place_name"], payload["place_name"])
        self.assertEqual(found_admin_item["address"], payload["address"])

    def test_07_backward_compatibility_coordinates_only_complaint(self):
        """Test existing latitude/longitude-based complaints without place name still work seamlessly."""
        payload = {
            "issue_type": "damaged_road",
            "description": "Road surface cracking near DB Road.",
            "original_language": "en",
            "latitude": 11.0125,
            "longitude": 76.9480,
            # No place_name or address provided
        }

        resp = self.client.post(
            "/api/v1/complaints",
            json=payload,
            headers={"Authorization": f"Bearer {self.citizen_token}"},
        )
        self.assertIn(resp.status_code, (200, 201), resp.text)
        created = resp.json()
        complaint_id = created["complaint_id"]

        # Coordinates must be preserved
        self.assertAlmostEqual(created["latitude"], payload["latitude"], places=4)
        self.assertAlmostEqual(created["longitude"], payload["longitude"], places=4)
        # Address and place name should be automatically resolved from nearest locality
        self.assertIsNotNone(created["address"])
        self.assertIsNotNone(created["place_name"])
        self.assertIn("Coimbatore", created["address"])


if __name__ == "__main__":
    unittest.main()
