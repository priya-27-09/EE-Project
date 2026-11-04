import time
from typing import Dict, Any
from sqlalchemy import text
from app.db.session import engine
from app.core.config import settings


def check_db_health() -> Dict[str, Any]:
    """
    Perform deep health check on PostgreSQL database connection.
    Verifies dialect, connectivity, query response latency, and database metadata.
    """
    # Reject SQLite
    if "sqlite" in settings.DATABASE_URL.lower():
        return {
            "status": "unhealthy",
            "error": "SQLite dialect detected. PostgreSQL is strictly required.",
            "dialect": "sqlite",
        }

    start_time = time.perf_counter()
    try:
        with engine.connect() as connection:
            # Query version and current database
            result = connection.execute(
                text("SELECT 1 AS alive, current_database() AS db_name, version() AS pg_version, NOW() AS server_time;")
            ).mappings().first()

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "status": "healthy",
                "database_name": result["db_name"],
                "dialect": engine.dialect.name,
                "driver": engine.dialect.driver,
                "server_version": result["pg_version"].split(" on ")[0],
                "server_time": str(result["server_time"]),
                "latency_ms": elapsed_ms,
                "pool_status": {
                    "pool_size": engine.pool.size(),
                    "checked_in": engine.pool.checkedin(),
                    "checked_out": engine.pool.checkedout(),
                    "overflow": engine.pool.overflow(),
                },
            }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "unhealthy",
            "error": str(exc),
            "latency_ms": elapsed_ms,
            "database_url": settings.SAFE_DATABASE_URL,
        }


if __name__ == "__main__":
    import json
    health = check_db_health()
    print(json.dumps(health, indent=2))
