"""
AI Civic Guardian — Unified Single-URL ASGI Deployment Entry Point
Designed for Single-Domain Hosting on Render, Docker, or any ASGI/Uvicorn server.

Routing Architecture:
- Root and UI Web Pages: Served by Flask at `/`
  (e.g., `/`, `/login`, `/register`, `/dashboard`, `/complaints/new`, `/track`, `/admin/...`, `/officer/...`, `/static/...`)
- Backend REST API: Served by FastAPI at `/api`
  (e.g., `/api/v1/auth/...`, `/api/v1/complaints/...`, `/api/v1/ai/...`, `/api/v1/officer/...`, `/api/v1/admin/...`, `/api/v1/chatbot/...`)
- Interactive API Documentation:
  - Swagger UI: `/api/docs` and `/docs`
  - OpenAPI JSON: `/api/openapi.json` and `/openapi.json`
  - ReDoc: `/api/redoc` and `/redoc`
- Health Checks: `/api/health` and `/health`

Strict Preservation:
- `fastapi_app.py` and `flask_app.py` are preserved intact.
- Local dual-server execution (`python run_project.py`) continues working without changes.
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from starlette.middleware.wsgi import WSGIMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

# Import existing application instances (preserved exactly)
from fastapi_app import app as fastapi_app
from flask_app import app as flask_app

# Wrap Flask (WSGI) as an ASGI application
flask_asgi_app = WSGIMiddleware(flask_app)


class UnifiedDeploymentApp:
    """
    Transparent ASGI router dispatching requests to either FastAPI or Flask
    based on URL path, enabling both applications to safely share a single public domain.
    """

    def __init__(self, fastapi_instance: ASGIApp, flask_instance: ASGIApp):
        self.fastapi_app = fastapi_instance
        self.flask_app = flask_instance

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")

            # 1. Route API endpoints, Swagger docs, OpenAPI schemas, and health checks to FastAPI
            if (
                path.startswith("/api")
                or path in ("/docs", "/redoc", "/openapi.json", "/health")
            ):
                await self.fastapi_app(scope, receive, send)
                return

        # 2. All other requests (Citizen portal web pages, officer views, admin panels, static assets) route to Flask
        await self.flask_app(scope, receive, send)


# Standard ASGI application callable for Uvicorn / Gunicorn
app = UnifiedDeploymentApp(fastapi_app, flask_asgi_app)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"[*] Starting AI Civic Guardian Unified Single-URL Deployment on http://{host}:{port}")
    print(f"    - Citizen Web Portal: http://{host}:{port}/")
    print(f"    - FastAPI Backend:    http://{host}:{port}/api/v1/...")
    print(f"    - Swagger API Docs:   http://{host}:{port}/api/docs")
    uvicorn.run("asgi_app:app", host=host, port=port, reload=False)

