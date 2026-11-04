import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.health import check_db_health


def main():
    print("=" * 60)
    print("PostgreSQL Database Health & Connection Diagnostic")
    print("=" * 60)
    health = check_db_health()
    print(json.dumps(health, indent=2))
    print("=" * 60)

    if health.get("status") == "healthy":
        print("[SUCCESS] Database is healthy and responding.")
        sys.exit(0)
    else:
        print(f"[FAILED] Database check failed: {health.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
