import sys
from pathlib import Path
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.db.health import check_db_health
from app.auth.router import router as auth_router
from app.complaints.router import router as complaints_router
from app.admin.dataset_router import router as dataset_router, sources_router
from app.admin.model_router import router as model_router
from app.ai.router import router as ai_router
from app.i18n.router import router as i18n_router
from app.officer.router import router as officer_router
from app.admin.blockchain_router import admin_router as admin_blockchain_router, public_router as public_blockchain_router
from app.chatbot.router import router as chatbot_router
from app.admin.chatbot_router import router as admin_chatbot_router
from app.admin.dashboard_router import router as admin_dashboard_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.core.rate_limit import SecurityHeadersAndRateLimitMiddleware

# Hardened CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|testserver)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security Headers & Rate Limiting Middleware
app.add_middleware(SecurityHeadersAndRateLimitMiddleware)

from fastapi.staticfiles import StaticFiles

# Include Routers
app.include_router(auth_router)
app.include_router(complaints_router)
app.include_router(dataset_router)
app.include_router(sources_router)
app.include_router(model_router)
app.include_router(ai_router)
app.include_router(i18n_router)
app.include_router(officer_router)
app.include_router(admin_blockchain_router)
app.include_router(public_blockchain_router)
app.include_router(chatbot_router)
app.include_router(admin_chatbot_router)
app.include_router(admin_dashboard_router)




# Mount uploads static directory for evidence viewing
uploads_dir = BASE_DIR / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/", summary="Root index")
def read_root():
    return {
        "service": settings.PROJECT_NAME,
        "framework": "FastAPI",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "auth_endpoints": {
            "register": "POST /auth/register",
            "login": "POST /auth/login",
            "profile": "GET /auth/me",
            "protected_test": "GET /auth/protected",
            "officer_test": "GET /auth/officer-only",
            "admin_test": "GET /auth/admin-only",
        },
    }


@app.get("/api/docs", include_in_schema=False)
def api_docs_swagger():
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title=f"{settings.PROJECT_NAME} - Swagger API Docs")


@app.get("/api/redoc", include_in_schema=False)
def api_redoc_doc():
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/api/openapi.json", title=f"{settings.PROJECT_NAME} - ReDoc")


@app.get("/api/openapi.json", include_in_schema=False)
def api_openapi_schema():
    return app.openapi()


@app.get("/api/health", summary="FastAPI Service Health Check (at /api prefix)")
async def api_health_check():
    return await health_check()


@app.get("/health", summary="FastAPI Service and Database Health Check")
async def health_check():
    """
    Service health check verifying FastAPI runtime and PostgreSQL connectivity.
    Returns 200 if healthy, or 503 if database is unreachable.
    This version runs the DB check in a background thread to avoid blocking the event loop.
    """
    import asyncio, logging
    try:
        # Run the potentially slow DB health check in a thread with a timeout
        db_health = await asyncio.wait_for(asyncio.to_thread(check_db_health), timeout=5)
    except asyncio.TimeoutError:
        logging.error("Health check timed out after 5 seconds")
        db_health = {"status": "unhealthy", "error": "Health check timeout"}
    except Exception as exc:
        logging.exception("Unexpected error during health check")
        db_health = {"status": "unhealthy", "error": str(exc)}

    is_healthy = db_health.get("status") == "healthy"
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "FastAPI Authentication & API Service",
            "project": settings.PROJECT_NAME,
            "database": db_health,
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=settings.FASTAPI_PORT, reload=True)
