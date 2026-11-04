"""
Verification script for Officer Portal: Complaint Full Details & Blockchain Trail.
Tests:
1. Officer Login & JWT authentication
2. Single complaint details retrieval with citizen details, evidences, history, notes
3. Blockchain trail endpoints on both FastAPI (8000) and Flask (5000)
4. Department isolation: Cross-department access returns 403 Forbidden
5. Non-existent complaint returns 404 Not Found
6. Admin access permissions across departments and blockchain records
7. Template & static JS integrity
"""
import sys
import json
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding='utf-8')

FASTAPI_URL = "http://127.0.0.1:8000"
FLASK_URL = "http://127.0.0.1:5000"

def http_post(url, data_dict, headers=None):
    headers = headers or {}
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=json.dumps(data_dict).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def http_get(url, headers=None):
    headers = headers or {}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if "application/json" in content_type:
                return resp.status, json.loads(data.decode("utf-8"))
            return resp.status, data.decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def login(email, password):
    status, res = http_post(f"{FASTAPI_URL}/auth/login", {"email": email, "password": password})
    if status != 200 or "access_token" not in res:
        raise RuntimeError(f"Login failed for {email}: status={status}, response={res}")
    return res["access_token"]

def main():
    print("=" * 70)
    print("AI CIVIC GUARDIAN: OFFICER PORTAL VERIFICATION SUITE")
    print("=" * 70)

    # 1. Login Roads Department Officer
    roads_officer_email = "officer.pothole@civic.gov"
    print(f"\n[TEST 1] Logging in Roads Officer: {roads_officer_email}")
    roads_token = login(roads_officer_email, "Officer@Civic2026!")
    print("  ✓ Login successful. JWT token received.")
    roads_auth = {"Authorization": f"Bearer {roads_token}"}

    # 2. List complaints for Roads Department
    print("\n[TEST 2] Fetching assigned grievances for Roads Department...")
    st, comp_list = http_get(f"{FASTAPI_URL}/api/v1/officer/complaints?page=1&page_size=10", roads_auth)
    assert st == 200, f"Expected 200, got {st}"
    assert "items" in comp_list, "Missing items in complaint list"
    assert len(comp_list["items"]) > 0, "No complaints found in Roads department"
    sample_complaint = comp_list["items"][0]
    sample_id = sample_complaint["complaint_id"]
    print(f"  ✓ Found {comp_list['total']} complaints assigned. Using sample: {sample_id}")

    # 3. Retrieve full details for the sample complaint
    print(f"\n[TEST 3] Fetching full details for {sample_id} via Officer API...")
    st, detail = http_get(f"{FASTAPI_URL}/api/v1/officer/complaints/{sample_id}", roads_auth)
    assert st == 200, f"Expected 200, got {st}: {detail}"
    print("  ✓ HTTP 200 OK received.")

    # Check required fields
    required_fields = [
        "complaint_id", "issue_type", "severity", "status", "description",
        "created_at", "department", "citizen_id", "citizen_name", "citizen_email",
        "evidences", "status_history", "notes"
    ]
    for rf in required_fields:
        assert rf in detail, f"Missing required field '{rf}' in complaint detail response"
        print(f"    - Field '{rf}': {repr(detail[rf])[:60]}")

    print(f"  ✓ Complainant Citizen Details: Name='{detail['citizen_name']}', Email='{detail['citizen_email']}', ID={detail['citizen_id']}")
    print(f"  ✓ Evidence count: {len(detail['evidences'])}, Status history entries: {len(detail['status_history'])}, Officer notes: {len(detail['notes'])}")

    # 4. Check Blockchain Trail on FastAPI & Flask
    print(f"\n[TEST 4] Testing Blockchain Trail endpoint for {sample_id}...")
    # On FastAPI
    st_fa, bc_fa = http_get(f"{FASTAPI_URL}/api/v1/blockchain/complaints/{sample_id}", roads_auth)
    assert st_fa == 200, f"FastAPI blockchain endpoint returned {st_fa}: {bc_fa}"
    assert "records" in bc_fa, "Missing 'records' key in FastAPI blockchain response"
    print(f"  ✓ FastAPI (port 8000) returned HTTP 200 with {len(bc_fa['records'])} blockchain anchor records.")

    # On Flask fallback route
    st_fl, bc_fl = http_get(f"{FLASK_URL}/api/v1/blockchain/complaints/{sample_id}", roads_auth)
    assert st_fl == 200, f"Flask fallback blockchain endpoint returned {st_fl}: {bc_fl}"
    assert "records" in bc_fl, "Missing 'records' key in Flask blockchain response"
    print(f"  ✓ Flask (port 5000) fallback returned HTTP 200 with {len(bc_fl['records'])} blockchain anchor records.")

    if len(bc_fa["records"]) > 0:
        first_rec = bc_fa["records"][0]
        tx_str = (first_rec.get('transaction_hash') or '')[:20]
        print(f"    - Sample milestone: Event='{first_rec.get('event_type')}', Status='{first_rec.get('status')}', Tx='{tx_str}...'")

    # 5. Test Department Isolation (Cross-department access)
    print("\n[TEST 5] Testing Department Isolation (Solid Waste Officer accessing Roads complaint)...")
    waste_officer_email = "officer.garbage@civic.gov"
    waste_token = login(waste_officer_email, "Officer@Civic2026!")
    waste_auth = {"Authorization": f"Bearer {waste_token}"}

    st_cross, cross_res = http_get(f"{FASTAPI_URL}/api/v1/officer/complaints/{sample_id}", waste_auth)
    print(f"  Cross-department request status: {st_cross}")
    assert st_cross == 403, f"Expected 403 Forbidden for cross-department complaint, got {st_cross}: {cross_res}"
    print(f"  ✓ Department isolation preserved! Backend returned HTTP 403: {cross_res.get('detail')}")

    # 6. Test Non-existent complaint ID
    print("\n[TEST 6] Testing non-existent complaint ID...")
    st_404, res_404 = http_get(f"{FASTAPI_URL}/api/v1/officer/complaints/CG-9999-999999", roads_auth)
    assert st_404 == 404, f"Expected 404 Not Found, got {st_404}: {res_404}"
    print(f"  ✓ Non-existent complaint correctly returned HTTP 404: {res_404.get('detail')}")

    # 7. Test Admin permissions
    print("\n[TEST 7] Testing Admin account access...")
    admin_token = login("admin@civic.gov", "Admin@Civic2026!")
    admin_auth = {"Authorization": f"Bearer {admin_token}"}
    st_adm, adm_detail = http_get(f"{FASTAPI_URL}/api/v1/officer/complaints/{sample_id}", admin_auth)
    assert st_adm == 200, f"Admin expected 200, got {st_adm}: {adm_detail}"
    print(f"  ✓ Admin can inspect complaint across any department (HTTP 200).")
    st_adm_bc, adm_bc = http_get(f"{FASTAPI_URL}/api/v1/blockchain/complaints/{sample_id}", admin_auth)
    assert st_adm_bc == 200, f"Admin expected 200 for blockchain, got {st_adm_bc}: {adm_bc}"
    print(f"  ✓ Admin can retrieve blockchain audit records (HTTP 200).")

    # 8. Test Frontend Templates & JS Assets
    print("\n[TEST 8] Verifying Frontend Templates & Static JS...")
    # Check officer dashboard template renders modal
    st_dash, dash_html = http_get(f"{FLASK_URL}/officer/dashboard")
    assert st_dash == 200, f"Dashboard returned {st_dash}"
    assert "complaint-details-modal" in dash_html, "Dashboard missing #complaint-details-modal"
    assert "openComplaintDetailsModal" in dash_html, "Dashboard missing openComplaintDetailsModal function"
    assert "modal-blockchain-status-pill" in dash_html, "Dashboard missing modal blockchain container"
    print("  ✓ Officer dashboard template contains full details modal & controllers.")

    # Check officer detail template renders
    st_det_page, det_html = http_get(f"{FLASK_URL}/officer/complaints/{sample_id}")
    assert st_det_page == 200, f"Detail page returned {st_det_page}"
    assert "renderBlockchainTrail" in det_html, "Detail page missing renderBlockchainTrail"
    assert "blockchain-status-pill" in det_html, "Detail page missing blockchain-status-pill"
    assert "Complainant (Citizen)" in det_html, "Detail page missing Complainant (Citizen) section"
    print("  ✓ Dedicated officer detail page contains Complainant and Blockchain sections.")

    # Check api.js
    st_js, js_code = http_get(f"{FLASK_URL}/static/js/api.js")
    assert st_js == 200, f"api.js returned {st_js}"
    assert "getBlockchainRecords" in js_code, "api.js missing getBlockchainRecords method"
    print("  ✓ static/js/api.js contains ApiClient.getBlockchainRecords method.")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED SUCCESSFULLY! (8/8)")
    print("=" * 70)

if __name__ == "__main__":
    main()
