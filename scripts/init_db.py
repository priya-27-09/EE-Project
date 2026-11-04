import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings

def ensure_database_exists():
    """
    Connect to PostgreSQL server default 'postgres' database
    and verify/create the target database (settings.DB_NAME).
    """
    target_db = settings.DB_NAME
    admin_url = (
        f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}@"
        f"{settings.DB_HOST}:{settings.DB_PORT}/postgres"
    )

    print(f"[*] Checking if target database '{target_db}' exists on {settings.DB_HOST}:{settings.DB_PORT}...")
    try:
        # Use isolation_level='AUTOCOMMIT' for CREATE DATABASE
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            query = text("SELECT 1 FROM pg_database WHERE datname = :dbname")
            result = conn.execute(query, {"dbname": target_db}).scalar()
            if not result:
                print(f"[+] Database '{target_db}' does not exist. Creating now...")
                conn.execute(text(f'CREATE DATABASE "{target_db}" OWNER "{settings.DB_USER}" ENCODING "UTF8";'))
                print(f"[+] Database '{target_db}' created successfully.")
            else:
                print(f"[OK] Database '{target_db}' already exists.")
        admin_engine.dispose()
    except Exception as e:
        print(f"[-] Failed to verify/create database '{target_db}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    ensure_database_exists()
