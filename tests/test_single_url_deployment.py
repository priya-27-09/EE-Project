"""
AI Civic Guardian — Single-URL Deployment Integration & Route Verification Tests
Verifies unified ASGI deployment architecture (Flask at `/`, FastAPI at `/api`, Swagger at `/api/docs`).
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from asgi_app import app as unified_app


class TestSingleUrlDeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(unified_app)

    def test_01_flask_root_page(self):
        """Verify Flask serves public landing page at /"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertTrue(len(resp.content) > 1000)

    def test_02_flask_auth_pages(self):
        """Verify Flask serves /login and /register web pages"""
        r_login = self.client.get("/login")
        self.assertEqual(r_login.status_code, 200)
        self.assertIn("text/html", r_login.headers.get("content-type", ""))

        r_reg = self.client.get("/register")
        self.assertEqual(r_reg.status_code, 200)
        self.assertIn("text/html", r_reg.headers.get("content-type", ""))

    def test_03_fastapi_health_endpoints(self):
        """Verify health check endpoints at /health and /api/health"""
        r_health = self.client.get("/health")
        self.assertEqual(r_health.status_code, 200)
        data = r_health.json()
        self.assertEqual(data.get("status"), "healthy")

        r_api_health = self.client.get("/api/health")
        self.assertEqual(r_api_health.status_code, 200)
        api_data = r_api_health.json()
        self.assertEqual(api_data.get("status"), "healthy")

    def test_04_swagger_and_openapi_docs(self):
        """Verify Swagger UI at /api/docs and OpenAPI schema at /api/openapi.json"""
        # Swagger at /api/docs
        r_api_docs = self.client.get("/api/docs")
        self.assertEqual(r_api_docs.status_code, 200)
        self.assertIn("swagger", r_api_docs.text.lower())

        # Swagger at /docs (backward-compatible)
        r_docs = self.client.get("/docs")
        self.assertEqual(r_docs.status_code, 200)

        # OpenAPI JSON schemas
        r_api_schema = self.client.get("/api/openapi.json")
        self.assertEqual(r_api_schema.status_code, 200)
        self.assertIn("openapi", r_api_schema.json())

        r_schema = self.client.get("/openapi.json")
        self.assertEqual(r_schema.status_code, 200)

    def test_05_fastapi_api_router_dispatch(self):
        """Verify API endpoints under /api/v1/ dispatch to FastAPI"""
        r_boundary = self.client.get("/api/v1/complaints/boundary")
        self.assertEqual(r_boundary.status_code, 200)
        data = r_boundary.json()
        self.assertIn("polygon", data)

    def test_06_flask_wizard_and_track_pages(self):
        """Verify Flask web application routes for complaint wizard and tracking"""
        r_wizard = self.client.get("/complaints/new")
        self.assertEqual(r_wizard.status_code, 200)
        self.assertIn("text/html", r_wizard.headers.get("content-type", ""))

        r_track = self.client.get("/track")
        self.assertEqual(r_track.status_code, 200)
        self.assertIn("text/html", r_track.headers.get("content-type", ""))

    def test_07_database_url_normalization(self):
        """Verify Render legacy postgres:// prefix is safely normalized"""
        from app.core.config import Settings
        import os
        orig = os.environ.get("DATABASE_URL")
        try:
            os.environ["DATABASE_URL"] = "postgres://test_user:test_pass@render-db.com:5432/test_db"
            s = Settings()
            norm = s.DATABASE_URL
            self.assertTrue(norm.startswith("postgresql+psycopg://"))
            self.assertIn("render-db.com", norm)
        finally:
            if orig is not None:
                os.environ["DATABASE_URL"] = orig
            else:
                os.environ.pop("DATABASE_URL", None)


if __name__ == "__main__":
    unittest.main()

