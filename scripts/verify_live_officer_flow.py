import requests

BASE_FASTAPI = "http://127.0.0.1:8000"
BASE_FLASK = "http://127.0.0.1:5000"

s = requests.Session()

# 1. Login as Officer
login_res = s.post(f"{BASE_FASTAPI}/auth/login", json={"email": "officer_roads_demo@civic.gov", "password": "Pass@123456"})
assert login_res.status_code == 200, f"Officer login failed: {login_res.text}"
officer_token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {officer_token}"}
print("[OK] 1. Officer Login successful via live FastAPI.")

# 2. Get Officer Dashboard
dash_res = s.get(f"{BASE_FASTAPI}/api/v1/officer/dashboard", headers=headers)
assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
dash_data = dash_res.json()
print(f"[OK] 2. Officer Dashboard loaded. Total Assigned: {dash_data['total_assigned']}, Dept: {dash_data['department_name']}")

# 3. List Officer Complaints
list_res = s.get(f"{BASE_FASTAPI}/api/v1/officer/complaints", headers=headers)
assert list_res.status_code == 200, f"Complaints list failed: {list_res.text}"
items = list_res.json()["items"]
assert len(items) > 0, "No complaints in officer list"
target_comp_id = items[0]["complaint_id"]
print(f"[OK] 3. Officer Complaints listed. Target Complaint: {target_comp_id}")

# 4. View Complaint Detail
detail_res = s.get(f"{BASE_FASTAPI}/api/v1/officer/complaints/{target_comp_id}", headers=headers)
assert detail_res.status_code == 200, f"Detail failed: {detail_res.text}"
print(f"[OK] 4. Complaint Detail retrieved. Initial Status: {detail_res.json()['status']}")

# 5. Transition status if SUBMITTED
curr_status = detail_res.json()["status"]
if curr_status == "SUBMITTED":
    p1 = s.patch(f"{BASE_FASTAPI}/api/v1/officer/complaints/{target_comp_id}/status", headers=headers, json={"status": "DEPARTMENT_ASSIGNED", "note": "Acknowledged by Roads team."})
    assert p1.status_code == 200
    print(f"[OK] 5. Status updated to DEPARTMENT_ASSIGNED: {p1.json()['status']}")
    curr_status = "DEPARTMENT_ASSIGNED"

if curr_status == "DEPARTMENT_ASSIGNED":
    p2 = s.patch(f"{BASE_FASTAPI}/api/v1/officer/complaints/{target_comp_id}/status", headers=headers, json={"status": "IN_PROGRESS", "note": "Maintenance crew dispatched."})
    assert p2.status_code == 200
    print(f"[OK] 6. Status updated to IN_PROGRESS: {p2.json()['status']}")
    curr_status = "IN_PROGRESS"

# 7. Add Officer Note
note_res = s.post(f"{BASE_FASTAPI}/api/v1/officer/complaints/{target_comp_id}/notes", headers=headers, json={"note": "Crew is on site with asphalt roller."})
assert note_res.status_code == 201
print(f"[OK] 7. Officer note added successfully: {note_res.json()['note']}")

# 8. Resolve Complaint
if curr_status == "IN_PROGRESS":
    res_res = s.post(f"{BASE_FASTAPI}/api/v1/officer/complaints/{target_comp_id}/resolution", headers=headers, json={"resolution_note": "Pothole filled with hot-mix asphalt and compacted."})
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
    print(f"[OK] 8. Grievance resolved: {res_res.json()['status']}, Notes: {res_res.json()['resolution']['resolution_notes']}")

# 9. Verify Citizen View
cit_login = s.post(f"{BASE_FASTAPI}/auth/login", json={"email": "citizen_browser@example.com", "password": "Pass@123456"})
cit_token = cit_login.json()["access_token"]
cit_headers = {"Authorization": f"Bearer {cit_token}"}
cit_comp = s.get(f"{BASE_FASTAPI}/api/v1/complaints/{target_comp_id}", headers=cit_headers)
assert cit_comp.status_code == 200
assert cit_comp.json()["status"] == "RESOLVED"
print(f"[OK] 9. Citizen tracking view verified from PostgreSQL. Citizen sees status: {cit_comp.json()['status']}")

# 10. Verify Flask HTML template pages
dash_page = s.get(f"{BASE_FLASK}/officer/dashboard")
assert dash_page.status_code == 200 and "Officer Dashboard" in dash_page.text
comp_page = s.get(f"{BASE_FLASK}/officer/complaints/{target_comp_id}")
assert comp_page.status_code == 200 and "Officer Complaint Management" in comp_page.text
print("[OK] 10. Flask web pages /officer/dashboard and /officer/complaints/<id> render HTTP 200.")

print("\n>>> ALL 10 LIVE SERVER VERIFICATION STEPS PASSED SUCCESSFULLY! <<<")
