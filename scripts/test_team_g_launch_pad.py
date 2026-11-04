"""
Test Suite: Removal of Launching Pad & Official Landing Page Verification
Verifies:
1. Homepage completely omits any Launching Pad overlay, script, styles, or replay buttons.
2. Homepage renders the official government civic grievance redressal portal landing page.
3. Authenticated session redirect routes users according to their role (Citizen, Officer, Admin).
4. Core citizen, officer, and admin routes render without regression.
5. Health endpoint /health responds with healthy PostgreSQL status.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from flask_app import app


class TestLandingPageAndEntry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_01_launching_pad_is_completely_removed(self):
        """Test 01: Homepage omits Launching Pad elements, styles, scripts, and buttons."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Launch Pad must be completely gone
        self.assertNotIn('id="team-g-launch-pad"', html)
        self.assertNotIn('id="team-g-skip-btn"', html)
        self.assertNotIn("launch-pad-replay-btn", html)
        self.assertNotIn("/static/css/launch_pad.css", html)
        self.assertNotIn("/static/js/launch_pad.js", html)
        self.assertNotIn("INITIALIZING...", html)

        print("[PASS] Test 01 — Launching Pad overlay, assets, and buttons are completely absent from homepage")

    def test_02_government_landing_page_renders_cleanly(self):
        """Test 02: Homepage renders official government-tech civic portal."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Government Tech Branding and Header
        self.assertIn("AI Civic Guardian", html)
        self.assertIn("Official Municipal Grievance Redressal Portal", html)
        self.assertIn("Lodge a Grievance", html)
        self.assertIn("Track Grievance", html)
        self.assertIn("How Civic Redressal Works", html)
        self.assertIn("Supported Civic Categories", html)
        self.assertIn("Roads & Highways", html)
        self.assertIn("Solid Waste Management", html)
        self.assertIn("Water Supply & Sewerage", html)
        self.assertIn("Electricity & Street Lighting", html)

        print("[PASS] Test 02 — Official government portal landing page renders with complete sections and CTAs")

    def test_03_role_based_session_redirects(self):
        """Test 03: Logged-in users redirect based on their role, while ?public=1 bypasses."""
        with self.client.session_transaction() as sess:
            sess["user"] = {"role": "CITIZEN", "name": "Citizen User", "email": "cit@test.com"}

        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/dashboard"))

        # Officer redirect
        with self.client.session_transaction() as sess:
            sess["user"] = {"role": "OFFICER", "name": "Officer User", "email": "off@test.com"}

        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/officer/dashboard"))

        # Admin redirect
        with self.client.session_transaction() as sess:
            sess["user"] = {"role": "ADMIN", "name": "Admin User", "email": "adm@test.com"}

        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["Location"].endswith("/admin/dashboard"))

        # Bypassing redirect with ?public=1
        res = self.client.get("/?public=1")
        self.assertEqual(res.status_code, 200)
        self.assertIn("AI Civic Guardian", res.get_data(as_text=True))

        # Clean session
        with self.client.session_transaction() as sess:
            sess.clear()

        print("[PASS] Test 03 — Role-based session redirects (Citizen, Officer, Admin) work with no loops")

    def test_04_backend_health_check_endpoint(self):
        """Test 04: /health endpoint responds and provides DB health."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertEqual(data["database"]["status"], "healthy")
        print("[PASS] Test 04 — /health endpoint returns healthy PostgreSQL status")

    def test_05_core_pages_render_without_regression(self):
        """Test 05: Core pages render properly."""
        routes = [
            "/login",
            "/register",
            "/chatbot",
            "/complaints/new",
            "/dashboard",
            "/track",
            "/officer/dashboard",
            "/admin/dashboard",
        ]
        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")
            html = res.get_data(as_text=True)
            self.assertNotIn('id="team-g-launch-pad"', html)
            self.assertNotIn("/static/css/launch_pad.css", html)
        print(f"[PASS] Test 05 — All {len(routes)} core application routes render cleanly without Launch Pad")


if __name__ == "__main__":
    unittest.main()
