#!/usr/bin/env python3
"""
Seed / Reset Script for AI Civic Guardian Demo Accounts:
- 1 Secure Admin Account (admin@civic.gov)
- 12 Distinct Department Officer Accounts (one for each canonical civic category)

Usage:
    python scripts/seed_demo_accounts.py [--reset-passwords]

Environment variables (optional):
    DEMO_ADMIN_EMAIL (default: admin@civic.gov)
    DEMO_ADMIN_PASSWORD (default: Admin@Civic2026!)
    DEMO_OFFICER_PASSWORD (default: Officer@Civic2026!)
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.department import Department
from app.core.auth import hash_password

# 12 Canonical Issue Categories mapped to their respective Officers & Departments
OFFICER_ACCOUNTS = [
    {
        "category": "Garbage Overflow",
        "email": "officer.garbage@civic.gov",
        "name": "Officer - Garbage Management",
        "dept_id": 6,
        "dept_name": "Solid Waste Management",
    },
    {
        "category": "Illegal Dumping",
        "email": "officer.dumping@civic.gov",
        "name": "Officer - Illegal Dumping",
        "dept_id": 6,
        "dept_name": "Solid Waste Management",
    },
    {
        "category": "Pothole",
        "email": "officer.pothole@civic.gov",
        "name": "Officer - Pothole Repair",
        "dept_id": 4,
        "dept_name": "Roads & Highways",
    },
    {
        "category": "Damaged Road",
        "email": "officer.road@civic.gov",
        "name": "Officer - Road Infrastructure",
        "dept_id": 4,
        "dept_name": "Roads & Highways",
    },
    {
        "category": "Water Leakage",
        "email": "officer.water@civic.gov",
        "name": "Officer - Water Supply & Leakage",
        "dept_id": 3,
        "dept_name": "Water Supply & Sewerage",
    },
    {
        "category": "Sewage Overflow",
        "email": "officer.sewage@civic.gov",
        "name": "Officer - Sewerage & Wastewater",
        "dept_id": 3,
        "dept_name": "Water Supply & Sewerage",
    },
    {
        "category": "Broken Street Light",
        "email": "officer.light@civic.gov",
        "name": "Officer - Street Lighting",
        "dept_id": 5,
        "dept_name": "Electricity & Street Lighting",
    },
    {
        "category": "Drainage Problem",
        "email": "officer.drainage@civic.gov",
        "name": "Officer - Drainage & Flood Relief",
        "dept_id": 12,
        "dept_name": "Drainage & Flood Management",
    },
    {
        "category": "Traffic Issue",
        "email": "officer.traffic@civic.gov",
        "name": "Officer - Traffic Operations",
        "dept_id": 8,
        "dept_name": "Traffic & Transportation",
    },
    {
        "category": "Building Damage",
        "email": "officer.building@civic.gov",
        "name": "Officer - Building & Structural Safety",
        "dept_id": 10,
        "dept_name": "Building & Construction",
    },
    {
        "category": "Park/Public Space Damage",
        "email": "officer.park@civic.gov",
        "name": "Officer - Parks & Public Amenities",
        "dept_id": 7,
        "dept_name": "Parks & Public Spaces",
    },
    {
        "category": "Environmental Pollution",
        "email": "officer.pollution@civic.gov",
        "name": "Officer - Environmental Protection",
        "dept_id": 9,
        "dept_name": "Environmental Protection",
    },
]


def seed_accounts(reset_passwords: bool = True):
    admin_email = os.getenv("DEMO_ADMIN_EMAIL", "admin@civic.gov").strip().lower()
    admin_password = os.getenv("DEMO_ADMIN_PASSWORD", "Admin@Civic2026!")
    officer_password = os.getenv("DEMO_OFFICER_PASSWORD", "Officer@Civic2026!")

    db = SessionLocal()
    try:
        print("=" * 70)
        print("  AI Civic Guardian — Demo Accounts Initialization / Seed Utility")
        print("=" * 70)

        # 1. Verify departments exist in database
        departments = {d.id: d.name for d in db.query(Department).all()}
        print(f"[*] Found {len(departments)} active departments in database.")

        # 2. Seed / Update Admin Account
        admin_user = db.query(User).filter(User.email == admin_email).first()
        admin_hash = hash_password(admin_password)

        if not admin_user:
            admin_user = User(
                name="Chief System Administrator",
                email=admin_email,
                password_hash=admin_hash,
                role=UserRole.ADMIN,
                preferred_language="en",
                department_id=None,
            )
            db.add(admin_user)
            print(f"[+] Created Admin Account: {admin_email} (Role: {UserRole.ADMIN})")
        else:
            admin_user.role = UserRole.ADMIN
            admin_user.name = "Chief System Administrator"
            if reset_passwords:
                admin_user.password_hash = admin_hash
            db.add(admin_user)
            print(f"[OK] Updated Admin Account: {admin_email} (Role: {UserRole.ADMIN})")

        # 3. Seed / Update 12 Department Officer Accounts
        officer_hash = hash_password(officer_password)
        created_count = 0
        updated_count = 0

        for off in OFFICER_ACCOUNTS:
            dept_id = off["dept_id"]
            dept_name = departments.get(dept_id, off["dept_name"])
            email = off["email"].strip().lower()

            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    name=off["name"],
                    email=email,
                    password_hash=officer_hash,
                    role=UserRole.OFFICER,
                    preferred_language="en",
                    department_id=dept_id,
                )
                db.add(user)
                created_count += 1
                status_str = "CREATED"
            else:
                user.name = off["name"]
                user.role = UserRole.OFFICER
                user.department_id = dept_id
                if reset_passwords:
                    user.password_hash = officer_hash
                db.add(user)
                updated_count += 1
                status_str = "UPDATED"

            print(f"  [{status_str}] Category: {off['category']:<26} -> {email:<28} Dept: [{dept_id}] {dept_name}")

        db.commit()

        print("-" * 70)
        print(f"[SUCCESS] Finished seeding accounts:")
        print(f"  - 1 Admin account configured: {admin_email}")
        print(f"  - 12 Department Officer accounts configured ({created_count} created, {updated_count} updated)")
        print(f"  - Passwords set/verified using secure bcrypt hashing.")
        print("-" * 70)
        print("Local Demo Credentials:")
        print(f"  Admin:   {admin_email} / [DEMO_ADMIN_PASSWORD]")
        print(f"  Officer: officer.<category>@civic.gov / [DEMO_OFFICER_PASSWORD]")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"[-] Error seeding demo accounts: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Admin and 12 Department Officer demo accounts.")
    parser.add_argument(
        "--no-reset-passwords",
        dest="reset_passwords",
        action="store_false",
        help="Do not reset password hashes for already existing accounts",
    )
    args = parser.parse_args()
    seed_accounts(reset_passwords=args.reset_passwords)
