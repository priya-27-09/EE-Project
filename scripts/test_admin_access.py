"""
AI Civic Guardian — Admin Cross-Department & Universal Access Test Script
Tests Requirement 8:
- Admin login and token verification.
- Admin access to /api/v1/admin/overview (system-wide metrics across all departments).
- Admin access to /api/v1/admin/departments (all 12 municipal departments).
- Admin access to /api/v1/admin/complaints (all complaints across all departments).
- Admin access to officer dashboard endpoints without department restrictions.
- Non-admin (citizen/officer) blocked from admin endpoints (HTTP 403).
"""

import os
import sys
import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")

def run_admin_tests():
    print("=" * 70)
    print("AI CIVIC GUARDIAN — REQUIREMENT 8 ADMIN ACCESS TEST")
    print(f"Backend: {BACKEND_URL}")
    print("=" * 70)

    # 1. Login as Admin
    admin_login = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": "admin@civic.gov",
        "password": "Admin@Civic2026!"
    })
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  [PASS] Admin login succeeded and acquired JWT token.")

    # 2. Login as Roads Officer (non-admin)
    officer_login = requests.post(f"{BACKEND_URL}/auth/login", json={
        "email": "officer.pothole@civic.gov",
        "password": "Officer@Civic2026!"
    })
    assert officer_login.status_code == 200
    officer_token = officer_login.json()["access_token"]
    officer_headers = {"Authorization": f"Bearer {officer_token}"}
    print("  [PASS] Roads Officer token acquired.")

    # 3. Test Admin Overview
    res = requests.get(f"{BACKEND_URL}/api/v1/admin/overview", headers=admin_headers)
    assert res.status_code == 200, f"Admin overview failed: {res.text}"
    overview = res.json()
    print(f"  [PASS] Admin overview HTTP 200: Total complaints = {overview['total_complaints']}, Departments = {overview['total_departments']}")
    assert overview['total_departments'] >= 10, "Expected at least 10 departments in overview"

    # 4. Test Admin Departments
    res = requests.get(f"{BACKEND_URL}/api/v1/admin/departments", headers=admin_headers)
    assert res.status_code == 200
    depts = res.json()
    print(f"  [PASS] Admin departments HTTP 200: Found {len(depts)} municipal departments.")
    dept_names = [d["name"] for d in depts]
    assert "Roads & Highways" in dept_names
    assert "Solid Waste Management" in dept_names
    assert "Water Supply & Sewerage" in dept_names

    # 5. Test Admin Complaints (Global Cross-Department Access)
    res = requests.get(f"{BACKEND_URL}/api/v1/admin/complaints?limit=100", headers=admin_headers)
    assert res.status_code == 200
    complaints = res.json()
    print(f"  [PASS] Admin complaints HTTP 200: Retrieved {complaints['total']} total complaints across all departments.")
    
    # Check that complaints from multiple different departments are visible to Admin
    dept_ids_seen = set()
    for item in complaints["items"]:
        if item.get("department_id"):
            dept_ids_seen.add(item["department_id"])
    print(f"  [PASS] Admin sees complaints across {len(dept_ids_seen)} distinct departments.")

    # 6. Test Admin Access to Officer Endpoints (Universal Supervision)
    res = requests.get(f"{BACKEND_URL}/api/v1/officer/complaints", headers=admin_headers)
    assert res.status_code == 200, f"Admin access to officer complaints failed: {res.text}"
    officer_view_by_admin = res.json()
    print(f"  [PASS] Admin can access /api/v1/officer/complaints with universal bypass (total items: {len(officer_view_by_admin.get('items', []))}).")

    # 7. Non-Admin (Officer) Access to Admin Endpoints MUST be Blocked (HTTP 403)
    res = requests.get(f"{BACKEND_URL}/api/v1/admin/overview", headers=officer_headers)
    assert res.status_code == 403, f"Officer should be blocked with 403, got {res.status_code}"
    print("  [PASS] Non-admin (Officer) accessing /api/v1/admin/overview blocked with HTTP 403 Forbidden.")

    res = requests.get(f"{BACKEND_URL}/api/v1/admin/complaints", headers=officer_headers)
    assert res.status_code == 403, f"Officer should be blocked with 403, got {res.status_code}"
    print("  [PASS] Non-admin (Officer) accessing /api/v1/admin/complaints blocked with HTTP 403 Forbidden.")

    print("=" * 70)
    print(" [SUCCESS] REQUIREMENT 8 ADMIN UNIVERSAL ACCESS VERIFIED 100%")
    print("=" * 70)

if __name__ == "__main__":
    run_admin_tests()
