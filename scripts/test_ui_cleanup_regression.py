"""
Regression test suite for UI Cleanup:
1. Zero blockchain UI visible across citizen, officer, and admin pages.
2. Technical AI warning hidden in Complaint Wizard:
   - Safe message: "Image uploaded successfully. Please confirm the issue category to continue."
   - Manual selector for all 12 canonical issue classes intact.
   - Server-side image validation intact.
   - Complaint submission with evidence, routing, severity, and backend audit record intact.
"""

import os
import sys
import io
import re
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.complaint import Complaint
from app.models.evidence import ComplaintEvidence
from app.models.blockchain_record import BlockchainRecord
from app.core.auth import create_access_token, hash_password

class TestUICleanupRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        cls.test_email = "citizen_cleanup_reg@test.com"
        cls.test_password = "Password@123"
        cls.created_complaint_ids = []
        cls.created_user_ids = []

        # Find or create test citizen
        user = cls.db.query(User).filter(User.email == cls.test_email).first()
        if not user:
            user = User(
                email=cls.test_email,
                name="Citizen UI Cleanup",
                password_hash=hash_password(cls.test_password),
                role=UserRole.CITIZEN,
                preferred_language="en",
            )
            cls.db.add(user)
            cls.db.commit()
            cls.db.refresh(user)
        cls.citizen = user
        cls.created_user_ids.append(user.id)
        cls.token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        for cid in cls.created_complaint_ids:
            cls.db.query(BlockchainRecord).filter(BlockchainRecord.complaint_id == cid).delete(synchronize_session=False)
            cls.db.query(ComplaintEvidence).filter(ComplaintEvidence.complaint_id == cid).delete(synchronize_session=False)
            cls.db.query(Complaint).filter(Complaint.id == cid).delete(synchronize_session=False)
        for uid in cls.created_user_ids:
            cls.db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_01_base_navbar_no_visible_blockchain_link(self):
        """Verify templates/base.html does not render any visible blockchain navigation link."""
        with open("templates/base.html", "r", encoding="utf-8") as f:
            base_html = f.read()
        self.assertNotIn('href="/admin/blockchain"', base_html, "Visible /admin/blockchain link found in navbar")
        self.assertNotIn("Blockchain Audit", base_html, "Blockchain Audit text found in navbar")

    def test_02_admin_dashboard_no_visible_blockchain_link(self):
        """Verify templates/admin_dashboard.html does not render any visible blockchain link."""
        with open("templates/admin_dashboard.html", "r", encoding="utf-8") as f:
            admin_html = f.read()
        self.assertNotIn('href="/admin/blockchain"', admin_html, "Visible /admin/blockchain link found in admin dashboard")

    def test_03_officer_pages_hidden_blockchain(self):
        """Verify officer dashboard and officer detail page have blockchain sections hidden."""
        with open("templates/officer_dashboard.html", "r", encoding="utf-8") as f:
            dash_html = f.read()
        self.assertIn('id="modal-blockchain-card" style="display: none !important;"', dash_html)

        with open("templates/officer_complaint_detail.html", "r", encoding="utf-8") as f:
            detail_html = f.read()
        self.assertIn('id="blockchain-audit-card" style="display: none !important;"', detail_html)

    def test_04_citizen_complaint_detail_hidden_blockchain(self):
        """Verify citizen complaint detail page hides blockchain integrity card."""
        with open("templates/complaint_detail.html", "r", encoding="utf-8") as f:
            c_html = f.read()
        self.assertIn('id="citizen-blockchain-card" style="display: none !important;"', c_html)

    def test_05_admin_blockchain_cleaned_terminology(self):
        """Verify admin_blockchain.html has clean Cryptographic Audit terminology."""
        with open("templates/admin_blockchain.html", "r", encoding="utf-8") as f:
            ab_html = f.read()
        self.assertNotIn(">Transaction Hash<", ab_html)
        self.assertNotIn(">Block<", ab_html)
        self.assertNotIn("Querying smart contract on Ganache...", ab_html)
        self.assertNotIn("On-chain Data Hash", ab_html)
        self.assertIn("Cryptographic Hash (SHA-256)", ab_html)
        self.assertIn("Record Scope", ab_html)
        self.assertIn("Verifying cryptographic hash integrity...", ab_html)

    def test_06_wizard_template_safe_messages_and_canonical_classes(self):
        """Verify templates/wizard.html contains citizen-friendly text and all 12 canonical classes."""
        with open("templates/wizard.html", "r", encoding="utf-8") as f:
            w_html = f.read()

        # No technical model messages
        self.assertNotIn("No trained AI model is currently active", w_html)
        self.assertNotIn("complete dataset preparation", w_html)
        self.assertNotIn("AI Model Unavailable — Development Fallback Active", w_html)

        # Expected citizen notice
        self.assertIn("Image uploaded successfully. Please confirm the issue category to continue.", w_html)

        # Demo trigger box hidden
        self.assertIn('id="demo-inference-trigger-box" style="display: none !important;"', w_html)

        # All 12 canonical issue classes present in manual selector
        canonical_classes = [
            "pothole", "damaged_road", "garbage_overflow", "illegal_dumping",
            "water_leakage", "sewage_overflow", "broken_street_light", "drainage_problem",
            "traffic_issue", "building_damage", "park_damage", "environmental_pollution"
        ]
        for c in canonical_classes:
            self.assertIn(f'data-issue="{c}"', w_html, f"Canonical class {c} missing from wizard grid")

    def test_07_wizard_js_clean_behavior(self):
        """Verify static/js/wizard.js displays safe message and hides demo button."""
        with open("static/js/wizard.js", "r", encoding="utf-8") as f:
            w_js = f.read()

        self.assertNotIn('res.message || "No trained AI model is currently active', w_js)
        self.assertIn('Image uploaded successfully. Please confirm the issue category to continue.', w_js)
        self.assertIn('demoTrigger.style.display = "none"', w_js)

    def test_08_server_side_upload_validation(self):
        """Verify server-side upload validation rejects invalid or corrupt files."""
        # 1. Invalid extension
        files = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")}
        resp = self.client.post("/api/v1/ai/inference", headers=self.headers, files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported image extension", resp.json()["detail"])

        # 2. Corrupt raster
        files = {"file": ("corrupt.jpg", b"fake_corrupt_data_not_jpeg_magic_bytes", "image/jpeg")}
        resp = self.client.post("/api/v1/ai/inference", headers=self.headers, files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("corrupted or not a valid image", resp.json()["detail"])

    def test_09_production_ai_unavailable_returns_safe_error_code(self):
        """Verify valid image upload succeeds but returns AI_MODEL_NOT_AVAILABLE code for frontend transformation."""
        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        files = {"file": ("evidence.jpg", buf, "image/jpeg")}
        resp = self.client.post("/api/v1/ai/inference", headers=self.headers, files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["success"])
        self.assertIn(data["error_code"], ["AI_MODEL_NOT_AVAILABLE", "AI_NO_DETECTION"])
        self.assertIsNone(data.get("issue"))
        self.assertEqual(data.get("detections", []), [])

    def test_10_complaint_submission_with_manual_category_and_backend_audit(self):
        """Verify complaint submission without AI prediction creates complaint, routes department, and writes SHA-256 audit record."""
        # Submit complaint with manual category 'pothole'
        payload = {
            "title": "Road Surface Pothole on 5th Cross",
            "description": "Deep depression on the main road",
            "issue_type": "pothole",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "language": "en"
        }
        resp = self.client.post("/api/v1/complaints/", headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        complaint_public_id = data["complaint_id"]
        
        # Look up raw DB complaint
        complaint_db = self.db.query(Complaint).filter(Complaint.complaint_id == complaint_public_id).first()
        self.assertIsNotNone(complaint_db)
        raw_db_id = complaint_db.id
        self.created_complaint_ids.append(raw_db_id)

        self.assertEqual(data["status"], "SUBMITTED")
        self.assertEqual(data["department"]["name"], "Roads & Highways")
        self.assertEqual(data["severity"], "MEDIUM")

        # Verify backend blockchain audit record was generated with deterministic SHA-256 hash
        audit_rec = self.db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == raw_db_id,
            BlockchainRecord.event_type == "COMPLAINT_CREATED"
        ).first()
        self.assertIsNotNone(audit_rec, "Backend blockchain record was not created")
        self.assertTrue(audit_rec.data_hash.startswith("0x"), "Data hash missing 0x prefix")
        self.assertEqual(len(audit_rec.data_hash), 66, "Data hash is not 64-char hex SHA-256")

        # Verify verification API returns correct record ID and reason
        v_resp = self.client.get(f"/api/v1/blockchain/records/{audit_rec.id}/verify")
        self.assertEqual(v_resp.status_code, 200)
        v_data = v_resp.json()
        self.assertEqual(v_data["record_id"], audit_rec.id)
        self.assertIn("BLOCKCHAIN_NOT_CONFIGURED", v_data.get("reason", ""))

        # Re-compute payload hash to verify deterministic SHA-256 calculation
        from app.services.blockchain_service import BlockchainService
        recalculated_hex, _ = BlockchainService.hash_payload(audit_rec.canonical_payload)
        self.assertEqual(recalculated_hex.lower(), audit_rec.data_hash.lower())

if __name__ == "__main__":
    unittest.main()
