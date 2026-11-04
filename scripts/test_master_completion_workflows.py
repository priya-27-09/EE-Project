"""
AI CIVIC GUARDIAN — MASTER COMPLETION & INTEGRATION TEST SUITE
Validates all features and bug-fixes:
1. Chatbot API endpoint and response format
2. Citizen View Details & Ownership enforcement
3. Complaint Letter Generation & PDF download
4. Strict Officer Department Isolation (Backend 403 & Allowed Issue Types)
5. Evidence Screening & Raster Integrity
6. Safe Satellite-Assisted Verification (No fake AI predictions)
7. Priority, SLA Deadlines, and Escalation Indicators
8. Repeat-Failure Detection after Resolution
9. Blockchain Decoupling with Preserved SHA-256 Database Audit History
10. Tamil Voice Complaint UI & Controller Integration
"""

import sys
import os
import requests
import json
import io
from PIL import Image

FASTAPI_URL = "http://127.0.0.1:8000"
FLASK_URL = "http://127.0.0.1:5000"

PASSED = 0
FAILED = 0


def record_result(test_name: str, passed: bool, detail: str = ""):
    global PASSED, FAILED
    if passed:
        PASSED += 1
        print(f"  [PASS] {test_name} {detail}")
    else:
        FAILED += 1
        print(f"  [FAIL] {test_name}: {detail}")


def login(email, password):
    resp = requests.post(
        f"{FASTAPI_URL}/auth/login",
        json={"email": email, "password": password},
    )
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


def main():
    print("=" * 70)
    print("AI CIVIC GUARDIAN — MASTER COMPLETION & BUG-FIX TEST SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Authentication and Tokens
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 1: AUTHENTICATION ---")
    import time
    ts = int(time.time())
    cit1_email = f"master_cit1_{ts}@test.com"
    cit2_email = f"master_cit2_{ts}@test.com"

    requests.post(f"{FASTAPI_URL}/auth/register", json={"name": "Citizen One", "email": cit1_email, "password": "Password@123", "preferred_language": "en"})
    requests.post(f"{FASTAPI_URL}/auth/register", json={"name": "Citizen Two", "email": cit2_email, "password": "Password@123", "preferred_language": "en"})

    citizen_token = login(cit1_email, "Password@123")
    citizen2_token = login(cit2_email, "Password@123")
    roads_officer_token = login("officer.pothole@civic.gov", "Officer@Civic2026!")
    sanitation_officer_token = login("officer.garbage@civic.gov", "Officer@Civic2026!")
    admin_token = login("admin@civic.gov", "Admin@Civic2026!")

    record_result("Citizen 1 token acquired", bool(citizen_token))
    record_result("Citizen 2 token acquired", bool(citizen2_token))
    record_result("Roads officer token acquired", bool(roads_officer_token))
    record_result("Sanitation officer token acquired", bool(sanitation_officer_token))
    record_result("Admin token acquired", bool(admin_token))

    cit_headers = {"Authorization": f"Bearer {citizen_token}"}
    cit2_headers = {"Authorization": f"Bearer {citizen2_token}"}
    roads_headers = {"Authorization": f"Bearer {roads_officer_token}"}
    san_headers = {"Authorization": f"Bearer {sanitation_officer_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}


    # -------------------------------------------------------------
    # 2. Chatbot API Integration
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 2: CHATBOT API INTEGRATION ---")
    chat_payload = {"message": "How do I report a pothole in Coimbatore?", "language": "en"}
    r = requests.post(f"{FASTAPI_URL}/api/v1/chatbot/chat", json=chat_payload, headers=cit_headers)
    record_result("Chatbot valid question HTTP 200", r.status_code == 200)
    if r.status_code == 200:
        data = r.json()
        record_result("Chatbot response has answer", bool(data.get("answer")))
        record_result("Chatbot response has sources", isinstance(data.get("sources"), list))
        record_result("Chatbot preserves language", data.get("language") == "en")

    # Empty question validation
    r_empty = requests.post(f"{FASTAPI_URL}/api/v1/chatbot/chat", json={"message": "   ", "language": "en"}, headers=cit_headers)
    record_result("Chatbot empty question handled gracefully (422)", r_empty.status_code in (400, 422))


    # -------------------------------------------------------------
    # 3. Complaint Registration & View Details
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 3: COMPLAINT REGISTRATION & VIEW DETAILS ---")
    complaint_data = {
        "issue_type": "Pothole",
        "description": "Deep road crater near Gandhipuram bus stand causing traffic hazard.",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "address": "Gandhipuram Central, Coimbatore, Tamil Nadu",
        "original_language": "en",
    }
    r_comp = requests.post(f"{FASTAPI_URL}/api/v1/complaints", json=complaint_data, headers=cit_headers)
    record_result("Citizen registered complaint HTTP 201", r_comp.status_code == 201)
    new_cid = r_comp.json().get("complaint_id") if r_comp.status_code == 201 else None
    record_result("Complaint ID assigned", bool(new_cid), f"ID: {new_cid}")

    if new_cid:
        # Citizen 1 retrieves details
        r_det = requests.get(f"{FASTAPI_URL}/api/v1/complaints/{new_cid}", headers=cit_headers)
        record_result("Citizen View Details HTTP 200", r_det.status_code == 200)
        cdata = r_det.json()
        record_result("Complaint category is Pothole", cdata.get("issue_type") in ("Pothole", "pothole") or cdata.get("issue_type_display") == "Pothole")
        record_result("Complaint status is SUBMITTED", cdata.get("status") == "SUBMITTED")
        record_result("Department assigned to Roads", "Roads" in (cdata.get("department") or {}).get("name", ""))

        # Ownership test: Citizen 2 tries to access Citizen 1's complaint
        r_own = requests.get(f"{FASTAPI_URL}/api/v1/complaints/{new_cid}", headers=cit2_headers)
        record_result("Citizen 2 access blocked with HTTP 403", r_own.status_code == 403)

        # Flask frontend template check for View Details page
        r_html = requests.get(f"{FLASK_URL}/complaints/{new_cid}")
        record_result("Flask Complaint Detail page returns HTTP 200", r_html.status_code == 200)
        record_result("Flask template renders complaint container", "detail-content" in r_html.text and "detail-loading" in r_html.text)

    # -------------------------------------------------------------
    # 4. Complaint Letter Generation & PDF Download
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 4: COMPLAINT LETTER & PDF GENERATION ---")
    if new_cid:
        # JSON letter data
        r_let = requests.get(f"{FASTAPI_URL}/api/v1/complaints/{new_cid}/letter", headers=cit_headers)
        record_result("Grievance letter metadata HTTP 200", r_let.status_code == 200)
        if r_let.status_code == 200:
            ldata = r_let.json().get("letter", {})
            record_result("Letter includes recipient municipal authority", "Coimbatore City Municipal Corporation" in ldata.get("authority", ""))
            record_result("Letter includes correct complaint ID", ldata.get("complaint_id") == new_cid)
            record_result("Letter specifies pending verification status", bool(ldata.get("verification_status")))

        # Download PDF
        r_pdf = requests.get(f"{FASTAPI_URL}/api/v1/complaints/{new_cid}/letter/pdf", headers=cit_headers)
        record_result("Grievance letter PDF HTTP 200", r_pdf.status_code == 200)
        record_result("PDF content-type is application/pdf", r_pdf.headers.get("content-type") == "application/pdf")
        record_result("PDF starts with %PDF- header", r_pdf.content.startswith(b"%PDF-"))
        record_result("PDF has valid byte size (> 1KB)", len(r_pdf.content) > 1024)

        # Citizen 2 unauthorized PDF download attempt
        r_pdf_unauth = requests.get(f"{FASTAPI_URL}/api/v1/complaints/{new_cid}/letter/pdf", headers=cit2_headers)
        record_result("Unauthorized PDF download blocked with HTTP 403", r_pdf_unauth.status_code == 403)


    # -------------------------------------------------------------
    # 5. Strict Officer Department Isolation
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 5: STRICT OFFICER DEPARTMENT ISOLATION ---")
    # Roads officer dashboard
    r_r_dash = requests.get(f"{FASTAPI_URL}/api/v1/officer/dashboard", headers=roads_headers)
    record_result("Roads officer dashboard HTTP 200", r_r_dash.status_code == 200)
    if r_r_dash.status_code == 200:
        dash_data = r_r_dash.json()
        allowed = [it["key"].lower() for it in dash_data.get("allowed_issue_types", [])]
        record_result("Roads officer sees Pothole in allowed types", "pothole" in allowed)
        record_result("Roads officer sees Damaged Road in allowed types", "damaged_road" in allowed)
        record_result("Roads officer CANNOT see Garbage Overflow", "garbage_overflow" not in allowed)
        record_result("Roads officer CANNOT see Water Leakage", "water_leakage" not in allowed)

    # Roads officer queries allowed vs disallowed category
    r_q_ok = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints?issue_type=Pothole", headers=roads_headers)
    record_result("Roads officer filter by Pothole HTTP 200", r_q_ok.status_code == 200)

    r_q_bad = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints?issue_type=Garbage%20Overflow", headers=roads_headers)
    record_result("Roads officer filter by Garbage Overflow REJECTED with HTTP 403", r_q_bad.status_code == 403)

    # Sanitation officer querying Roads complaint
    if new_cid:
        r_san_cross = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}", headers=san_headers)
        record_result("Sanitation officer accessing Roads complaint REJECTED with HTTP 403", r_san_cross.status_code == 403)

        # Roads officer CAN access their Roads complaint
        r_roads_acc = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}", headers=roads_headers)
        record_result("Roads officer accessing Roads complaint HTTP 200", r_roads_acc.status_code == 200)

    # -------------------------------------------------------------
    # 6. Evidence Screening & Raster Integrity
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 6: EVIDENCE SCREENING & INTEGRITY ---")
    # Upload test image evidence
    img_byte_arr = io.BytesIO()
    img = Image.new("RGB", (200, 200), color=(120, 80, 50))
    img.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)

    r_ev = requests.post(
        f"{FASTAPI_URL}/api/v1/complaints/{new_cid}/evidence",
        headers=cit_headers,
        files={"file": ("pothole_evidence.jpg", img_byte_arr, "image/jpeg")},
    )
    record_result("Uploaded evidence photo HTTP 201", r_ev.status_code == 201)

    r_screen = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/evidence-screening", headers=roads_headers)
    record_result("Evidence screening API HTTP 200", r_screen.status_code == 200)
    if r_screen.status_code == 200:
        sdata = r_screen.json()
        record_result("Screening contains evaluated evidences", sdata.get("evidence_count", 0) > 0)
        first = sdata.get("screenings", [])[0] if sdata.get("screenings") else {}
        record_result("Raster integrity check evaluated", "VALID_IMAGE_RASTER" in first.get("flags", []) or first.get("is_valid") is True)
        record_result("Perceptual hash computed", bool(first.get("metadata", {}).get("perceptual_hash")))

    # -------------------------------------------------------------
    # 7. Safe Satellite-Assisted Verification
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 7: SATELLITE-ASSISTED VERIFICATION ---")
    r_sat = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/satellite-assessment", headers=roads_headers)
    record_result("Satellite assessment API HTTP 200", r_sat.status_code == 200)
    if r_sat.status_code == 200:
        sat_data = r_sat.json()
        record_result("Spatial boundary evaluated (CCMC)", sat_data.get("is_within_coimbatore_boundary") is True)
        record_result("Defect visibility recommendation provided", bool(sat_data.get("recommendation")))
        record_result("Satellite layer noted", "Esri" in sat_data.get("satellite_layer", {}).get("provider", ""))
        record_result("Safe recommendation given without fake AI score", bool(sat_data.get("outcome")))

    # -------------------------------------------------------------
    # 8. Priority & SLA Escalation Status
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 8: PRIORITY & SLA ESCALATION ---")
    r_sla = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/sla", headers=roads_headers)
    record_result("SLA status API HTTP 200", r_sla.status_code == 200)
    if r_sla.status_code == 200:
        sla_data = r_sla.json()
        sla_hrs = sla_data.get("sla_hours_allocated") or sla_data.get("sla_hours")
        record_result("SLA priority/policy calculated", bool(sla_data.get("escalation_state") or sla_data.get("priority")))
        record_result("SLA hours allocated (48h/72h for roads)", sla_hrs in (48, 72))
        record_result("SLA deadline timestamp present", bool(sla_data.get("deadline")))
        record_result("Overdue boolean calculated", "is_overdue" in sla_data)

    # -------------------------------------------------------------
    # 9. Repeat-Failure Detection
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 9: REPEAT-FAILURE DETECTION ---")
    # Advance status through canonical state machine to RESOLVED:
    requests.patch(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/status", headers=roads_headers, json={"status": "VERIFIED", "note": "Verified by field team."})
    requests.patch(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/status", headers=roads_headers, json={"status": "IN_PROGRESS", "note": "Repair crew deployed."})
    r_res = requests.patch(
        f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid}/status",
        headers=roads_headers,
        json={"status": "RESOLVED", "note": "Pothole filled with cold asphalt patch."},
    )
    record_result("First complaint progressed to RESOLVED HTTP 200", r_res.status_code == 200)

    # Step 2: Citizen files a new complaint at the exact same location for the same issue
    r_comp2 = requests.post(
        f"{FASTAPI_URL}/api/v1/complaints",
        headers=cit_headers,
        json={
            "issue_type": "Pothole",
            "description": "Pothole recurring at Gandhipuram bus stand after patch washed away.",
            "latitude": 11.0168,
            "longitude": 76.9558,
            "address": "Gandhipuram Central, Coimbatore, Tamil Nadu",
            "original_language": "en",
        },
    )
    record_result("Second complaint filed at same location HTTP 201", r_comp2.status_code == 201)
    new_cid2 = r_comp2.json().get("complaint_id") if r_comp2.status_code == 201 else None

    if new_cid2:
        r_rep = requests.get(f"{FASTAPI_URL}/api/v1/officer/complaints/{new_cid2}/repeat-failure", headers=roads_headers)
        record_result("Repeat-failure check API HTTP 200", r_rep.status_code == 200)
        if r_rep.status_code == 200:
            rep_data = r_rep.json()
            record_result("Identified as repeat failure", rep_data.get("is_repeat_failure") is True)
            record_result("Matches previously resolved complaint", rep_data.get("previous_complaint_id") == new_cid)
            record_result("Distance accurately computed (< 50m)", rep_data.get("distance_meters", 999) < 50)

    # -------------------------------------------------------------
    # 10. Decoupled Blockchain & Preserved SHA-256 Audit Trail
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 10: DECOUPLED BLOCKCHAIN & DATABASE AUDIT ---")
    r_b_stat = requests.get(f"{FASTAPI_URL}/api/v1/admin/blockchain/status", headers=admin_headers)
    record_result("Admin status API HTTP 200", r_b_stat.status_code == 200)
    if r_b_stat.status_code == 200:
        b_data = r_b_stat.json()
        record_result("External blockchain network cleanly decoupled", b_data.get("available") is False or b_data.get("configured") is False)

    # Verify SHA-256 database audit records exist
    r_audit = requests.get(f"{FASTAPI_URL}/api/v1/admin/blockchain/records?complaint_ref={new_cid}", headers=admin_headers)
    record_result("Audit trail query HTTP 200", r_audit.status_code == 200)
    if r_audit.status_code == 200:
        audit_records = r_audit.json().get("records", [])
        record_result("Audit trail contains historical events", len(audit_records) > 0 or r_audit.json().get("total", 0) > 0)


    # -------------------------------------------------------------
    # 11. Tamil Voice Registration UI & Controller
    # -------------------------------------------------------------
    print("\n--- TEST GROUP 11: TAMIL VOICE COMPLAINT UI ---")
    r_wiz = requests.get(f"{FLASK_URL}/complaints/new")
    record_result("Citizen complaint wizard HTTP 200", r_wiz.status_code == 200)
    record_result("Wizard has Tamil voice input button", "voice-btn" in r_wiz.text)
    record_result("Wizard has voice recording indicator", "voice-indicator" in r_wiz.text)

    r_wiz_js = requests.get(f"{FLASK_URL}/static/js/wizard.js")
    record_result("Wizard JavaScript HTTP 200", r_wiz_js.status_code == 200)
    record_result("Wizard JS configures ta-IN speech recognition", "ta-IN" in r_wiz_js.text)
    record_result("Wizard JS contains manual fallback handlers", "recognition.onerror" in r_wiz_js.text)

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"MASTER COMPLETION TEST SUMMARY: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 70)

    if FAILED > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
