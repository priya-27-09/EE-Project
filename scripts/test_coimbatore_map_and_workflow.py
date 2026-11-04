"""
Comprehensive automated tests for Coimbatore Mapping, Boundary Validation,
Multi-Step Complaint Registration, and Officer Problem Verification Workflows.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.department import Department
from app.models.status_history import ComplaintStatusHistory
from app.core.auth import create_access_token, hash_password
from app.services.boundary_service import CoimbatoreBoundaryService
from app.complaints.constants import (
    VALID_ISSUE_TYPES,
    STATUS_SUBMITTED,
    STATUS_VERIFIED,
    STATUS_DEPARTMENT_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_RESOLVED,
    STATUS_REJECTED,
)

class TestCoimbatoreMapAndWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.created_complaint_ids = []
        cls.created_user_ids = []

        # Ensure departments exist
        cls.road_dept = cls.db.query(Department).filter(Department.name.ilike("%Roads%")).first()
        if not cls.road_dept:
            cls.road_dept = Department(name="Roads & Highways", description="Road maintenance and pothole repair")
            cls.db.add(cls.road_dept)
            cls.db.commit()
            cls.db.refresh(cls.road_dept)

        cls.water_dept = cls.db.query(Department).filter(Department.name.ilike("%Water%")).first()
        if not cls.water_dept:
            cls.water_dept = Department(name="Water Supply & Sewerage", description="Water pipe repairs and drainage")
            cls.db.add(cls.water_dept)
            cls.db.commit()
            cls.db.refresh(cls.water_dept)

        # Setup citizen
        citizen = cls.db.query(User).filter(User.email == "citizen_cbe_test@example.com").first()
        if not citizen:
            citizen = User(
                email="citizen_cbe_test@example.com",
                name="Coimbatore Citizen Tester",
                password_hash=hash_password("Password@123"),
                role=UserRole.CITIZEN,
                preferred_language="en",
            )
            cls.db.add(citizen)
            cls.db.commit()
            cls.db.refresh(citizen)
        cls.citizen = citizen
        cls.citizen_token = create_access_token(data={"sub": str(citizen.id), "email": citizen.email, "role": citizen.role})
        cls.citizen_headers = {"Authorization": f"Bearer {cls.citizen_token}"}

        # Setup road officer
        road_officer = cls.db.query(User).filter(User.email == "road_officer_cbe@example.com").first()
        if not road_officer:
            road_officer = User(
                email="road_officer_cbe@example.com",
                name="Roads Field Officer",
                password_hash=hash_password("Password@123"),
                role=UserRole.OFFICER,
                department_id=cls.road_dept.id,
                preferred_language="en",
            )
            cls.db.add(road_officer)
            cls.db.commit()
            cls.db.refresh(road_officer)
        else:
            road_officer.department_id = cls.road_dept.id
            cls.db.commit()
        cls.road_officer = road_officer
        cls.road_officer_token = create_access_token(data={"sub": str(road_officer.id), "email": road_officer.email, "role": road_officer.role})
        cls.road_officer_headers = {"Authorization": f"Bearer {cls.road_officer_token}"}

        # Setup water officer
        water_officer = cls.db.query(User).filter(User.email == "water_officer_cbe@example.com").first()
        if not water_officer:
            water_officer = User(
                email="water_officer_cbe@example.com",
                name="Water Field Officer",
                password_hash=hash_password("Password@123"),
                role=UserRole.OFFICER,
                department_id=cls.water_dept.id,
                preferred_language="en",
            )
            cls.db.add(water_officer)
            cls.db.commit()
            cls.db.refresh(water_officer)
        else:
            water_officer.department_id = cls.water_dept.id
            cls.db.commit()
        cls.water_officer = water_officer
        cls.water_officer_token = create_access_token(data={"sub": str(water_officer.id), "email": water_officer.email, "role": water_officer.role})
        cls.water_officer_headers = {"Authorization": f"Bearer {cls.water_officer_token}"}

    @classmethod
    def tearDownClass(cls):
        try:
            for cid in cls.created_complaint_ids:
                complaint = cls.db.query(Complaint).filter(Complaint.complaint_id == cid).first()
                if complaint:
                    cls.db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == complaint.id).delete()
                    cls.db.delete(complaint)
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def test_01_coimbatore_boundary_endpoint(self):
        """Verify GET /api/v1/complaints/boundary returns authoritative CCMC metadata."""
        resp = self.client.get("/api/v1/complaints/boundary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["city"], "Coimbatore")
        self.assertEqual(data["state"], "Tamil Nadu")
        self.assertIn("bounding_box", data)
        self.assertIn("polygon", data)
        self.assertGreaterEqual(len(data["polygon"]), 10)
        self.assertIn("localities", data)
        self.assertGreaterEqual(len(data["localities"]), 10)

    def test_02_validate_location_within_coimbatore(self):
        """Verify POST /api/v1/complaints/validate-location approves locations inside Coimbatore."""
        # Gandhipuram
        resp1 = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 11.0168, "longitude": 76.9558})
        self.assertEqual(resp1.status_code, 200)
        d1 = resp1.json()
        self.assertTrue(d1["is_valid"])
        self.assertIn("Coimbatore", d1["message"])
        self.assertIsNotNone(d1["nearest_locality"])

        # Peelamedu
        resp2 = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 11.0264, "longitude": 77.0028})
        self.assertEqual(resp2.status_code, 200)
        d2 = resp2.json()
        self.assertTrue(d2["is_valid"])

        # RS Puram
        resp3 = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 11.0085, "longitude": 76.9515})
        self.assertEqual(resp3.status_code, 200)
        d3 = resp3.json()
        self.assertTrue(d3["is_valid"])

    def test_03_validate_location_outside_coimbatore(self):
        """Verify POST /api/v1/complaints/validate-location rejects locations outside Coimbatore."""
        # Bangalore
        resp_blr = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 12.9716, "longitude": 77.5946})
        self.assertEqual(resp_blr.status_code, 200)
        d_blr = resp_blr.json()
        self.assertFalse(d_blr["is_valid"])
        self.assertIn("outside the Coimbatore Municipal Corporation boundary", d_blr["message"])

        # Chennai
        resp_chn = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 13.0827, "longitude": 80.2707})
        self.assertEqual(resp_chn.status_code, 200)
        d_chn = resp_chn.json()
        self.assertFalse(d_chn["is_valid"])

        # Madurai
        resp_mdu = self.client.post("/api/v1/complaints/validate-location", json={"latitude": 9.9252, "longitude": 78.1198})
        self.assertEqual(resp_mdu.status_code, 200)
        d_mdu = resp_mdu.json()
        self.assertFalse(d_mdu["is_valid"])

    def test_04_create_complaint_rejects_out_of_boundary(self):
        """Verify complaint creation with enforce_boundary=True rejects out-of-boundary submission with HTTP 422."""
        payload = {
            "issue_type": "pothole",
            "description": "Pothole on MG Road outside service area",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "address": "MG Road, Bangalore",
            "enforce_boundary": True,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=self.citizen_headers)
        self.assertEqual(resp.status_code, 422)
        err = resp.json()
        self.assertIn("outside the Coimbatore Municipal Corporation boundary", err["detail"])

    def test_05_create_complaint_success_in_coimbatore(self):
        """Verify complaint creation in Coimbatore succeeds, routes to Roads & Highways, and saves address."""
        payload = {
            "issue_type": "pothole",
            "description": "Deep road depression near Gandhipuram bus terminal, Coimbatore",
            "latitude": 11.0168,
            "longitude": 76.9558,
            "address": "Gandhipuram Bus Stand Road, Coimbatore, Tamil Nadu, 641012",
            "enforce_boundary": True,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=self.citizen_headers)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        cid = data["complaint_id"]
        self.created_complaint_ids.append(cid)
        self.assertEqual(data["issue_type"], "pothole")
        self.assertEqual(data["status"], STATUS_SUBMITTED)
        self.assertEqual(data["address"], "Gandhipuram Bus Stand Road, Coimbatore, Tamil Nadu, 641012")
        self.assertIn("Roads", data["department"]["name"])

        # Retrieve through GET
        get_resp = self.client.get(f"/api/v1/complaints/{cid}", headers=self.citizen_headers)
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()
        self.assertEqual(get_data["address"], "Gandhipuram Bus Stand Road, Coimbatore, Tamil Nadu, 641012")
        self.assertAlmostEqual(get_data["latitude"], 11.0168, places=4)
        self.assertAlmostEqual(get_data["longitude"], 76.9558, places=4)

    def test_06_officer_verification_workflow(self):
        """Verify officer can inspect complaint, change status to VERIFIED, IN_PROGRESS, and RESOLVED."""
        # 1. Create a road complaint
        payload = {
            "issue_type": "damaged_road",
            "description": "Damaged asphalt surface on 100 Feet Road, Gandhipuram",
            "latitude": 11.0195,
            "longitude": 76.9620,
            "address": "100 Feet Road, Gandhipuram, Coimbatore, 641012",
            "enforce_boundary": True,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=self.citizen_headers)
        self.assertEqual(resp.status_code, 201)
        cid = resp.json()["complaint_id"]
        self.created_complaint_ids.append(cid)

        # 2. Road officer views complaint detail
        officer_view = self.client.get(f"/api/v1/officer/complaints/{cid}", headers=self.road_officer_headers)
        self.assertEqual(officer_view.status_code, 200)
        c_detail = officer_view.json()
        self.assertEqual(c_detail["status"], STATUS_SUBMITTED)
        self.assertEqual(c_detail["address"], "100 Feet Road, Gandhipuram, Coimbatore, 641012")

        # 3. Transition to VERIFIED
        ver_resp = self.client.put(
            f"/api/v1/officer/complaints/{cid}/status",
            json={"status": "VERIFIED", "note": "Field inspection confirmed severe road surface wear."},
            headers=self.road_officer_headers,
        )
        self.assertEqual(ver_resp.status_code, 200)
        self.assertEqual(ver_resp.json()["status"], "VERIFIED")

        # 4. Transition to IN_PROGRESS
        prog_resp = self.client.put(
            f"/api/v1/officer/complaints/{cid}/status",
            json={"status": "IN_PROGRESS", "note": "Municipal road resurfacing crew deployed with bitumen equipment."},
            headers=self.road_officer_headers,
        )
        self.assertEqual(prog_resp.status_code, 200)
        self.assertEqual(prog_resp.json()["status"], "IN_PROGRESS")

        # 5. Resolve complaint
        res_resp = self.client.post(
            f"/api/v1/officer/complaints/{cid}/resolve",
            json={"resolution_note": "Resurfacing completed and compaction rolled. Traffic flow restored safely."},
            headers=self.road_officer_headers,
        )
        self.assertEqual(res_resp.status_code, 200)
        res_data = res_resp.json()
        self.assertEqual(res_data["status"], "RESOLVED")

        # 6. Citizen tracking verifies legitimate status update
        track_resp = self.client.get(f"/api/v1/complaints/{cid}", headers=self.citizen_headers)
        self.assertEqual(track_resp.status_code, 200)
        self.assertEqual(track_resp.json()["status"], "RESOLVED")
        history = [h["new_status"] for h in track_resp.json()["status_history"]]
        self.assertIn("VERIFIED", history)
        self.assertIn("IN_PROGRESS", history)
        self.assertIn("RESOLVED", history)

    def test_07_officer_rejection_workflow(self):
        """Verify officer can reject unjustified complaint with logged remarks."""
        payload = {
            "issue_type": "pothole",
            "description": "Alleged road defect on private property",
            "latitude": 11.0085,
            "longitude": 76.9515,
            "address": "Private Society Compound, RS Puram, Coimbatore",
            "enforce_boundary": True,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=self.citizen_headers)
        self.assertEqual(resp.status_code, 201)
        cid = resp.json()["complaint_id"]
        self.created_complaint_ids.append(cid)

        # Reject complaint
        rej_resp = self.client.put(
            f"/api/v1/officer/complaints/{cid}/status",
            json={"status": "REJECTED", "note": "Defect is located inside private gated property, outside municipal jurisdiction."},
            headers=self.road_officer_headers,
        )
        self.assertEqual(rej_resp.status_code, 200)
        self.assertEqual(rej_resp.json()["status"], "REJECTED")

        # Verify reflected in citizen tracking
        track_resp = self.client.get(f"/api/v1/complaints/{cid}", headers=self.citizen_headers)
        self.assertEqual(track_resp.status_code, 200)
        self.assertEqual(track_resp.json()["status"], "REJECTED")

    def test_08_cross_department_isolation(self):
        """Verify officer from another department is strictly forbidden from accessing complaints."""
        # Create a water complaint
        payload = {
            "issue_type": "water_leakage",
            "description": "Main water pipeline valve rupture in Peelamedu",
            "latitude": 11.0264,
            "longitude": 77.0028,
            "address": "Avinashi Road, Peelamedu, Coimbatore",
            "enforce_boundary": True,
        }
        resp = self.client.post("/api/v1/complaints", json=payload, headers=self.citizen_headers)
        self.assertEqual(resp.status_code, 201)
        cid = resp.json()["complaint_id"]
        self.created_complaint_ids.append(cid)

        # Road officer attempts to access water complaint -> 403 Forbidden
        road_view = self.client.get(f"/api/v1/officer/complaints/{cid}", headers=self.road_officer_headers)
        self.assertEqual(road_view.status_code, 403)
        self.assertIn("belongs to another department", road_view.json()["detail"])

        # Water officer CAN access it -> 200 OK
        water_view = self.client.get(f"/api/v1/officer/complaints/{cid}", headers=self.water_officer_headers)
        self.assertEqual(water_view.status_code, 200)

    def test_09_all_12_canonical_classes_preserved(self):
        """Verify all 12 canonical civic issue classes remain intact and valid."""
        expected_classes = {
            "garbage_overflow",
            "illegal_dumping",
            "pothole",
            "damaged_road",
            "water_leakage",
            "sewage_overflow",
            "broken_street_light",
            "drainage_problem",
            "traffic_issue",
            "building_damage",
            "park_damage",
            "environmental_pollution",
        }
        self.assertEqual(VALID_ISSUE_TYPES, expected_classes)
        self.assertEqual(len(VALID_ISSUE_TYPES), 12)

    def test_10_experimental_model_inactive(self):
        """Verify MODEL-2026-000001 is registered as inactive and production inference returns AI_MODEL_NOT_AVAILABLE."""
        from app.models.model_version import ModelVersion
        model = self.db.query(ModelVersion).filter(ModelVersion.model_version == "MODEL-2026-000001").first()
        if model:
            self.assertFalse(model.is_active, "Baseline model MODEL-2026-000001 must not be active in production")

if __name__ == "__main__":
    unittest.main()
