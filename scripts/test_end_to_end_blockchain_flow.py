import os
import sys
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error
from PIL import Image

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.complaint import Complaint
from app.models.blockchain_record import BlockchainRecord


def create_test_jpeg(color: tuple, size=(256, 256)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def run_e2e_flow():
    print("=" * 70)
    print("AI CIVIC GUARDIAN — STEP 10: FULL END-TO-END BLOCKCHAIN INTEGRITY FLOW")
    print("=" * 70)

    db = SessionLocal()
    fastapi_base = "http://127.0.0.1:8000"

    try:
        # Step 1: Ensure citizen and officer test accounts
        print("\n[STEP 1] Setting up authenticated actors...")
        citizen = db.query(User).filter(User.role == UserRole.CITIZEN).first()
        dept = db.query(Department).filter(Department.name == "Roads & Traffic Infrastructure").first()
        if not dept:
            dept = db.query(Department).first()

        officer = db.query(User).filter(User.role == UserRole.OFFICER, User.department_id == dept.id).first()
        if not officer:
            officer = db.query(User).filter(User.role == UserRole.OFFICER).first()

        from app.core.auth import create_access_token
        citizen_token = create_access_token({"sub": str(citizen.id), "email": citizen.email, "role": UserRole.CITIZEN})
        officer_token = create_access_token({"sub": str(officer.id), "email": officer.email, "role": UserRole.OFFICER})

        print(f" -> Citizen: {citizen.email} (ID #{citizen.id})")
        print(f" -> Officer: {officer.email} (ID #{officer.id}, Dept #{officer.department_id})")

        # Step 2: Citizen creates complaint
        print("\n[STEP 2] Citizen submitting new civic complaint...")
        create_payload = json.dumps({
            "issue_type": "pothole",
            "description": "Hazardous road pothole near junction requiring immediate civic repair.",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "original_language": "en",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{fastapi_base}/api/v1/complaints",
            data=create_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {citizen_token}",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req)
        assert resp.status == 201, f"Failed to create complaint: {resp.status}"
        c_data = json.loads(resp.read().decode("utf-8"))
        public_id = c_data["complaint_id"]
        print(f" -> Complaint Registered: {public_id}, Status: {c_data['status']}")

        # Upload initial before evidence so Step 9 verification has an evidence pair
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        before_bytes = create_test_jpeg((120, 80, 50))
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="citizen_before.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + before_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        ev_req = urllib.request.Request(
            f"{fastapi_base}/api/v1/complaints/{public_id}/evidence",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {citizen_token}",
            },
            method="POST",
        )
        ev_resp = urllib.request.urlopen(ev_req)
        assert ev_resp.status == 201
        print(" -> Citizen Before-Evidence Uploaded")

        # Step 3: Verify COMPLAINT_CREATED on Blockchain
        print("\n[STEP 3] Verifying COMPLAINT_CREATED anchored on blockchain...")
        c_record = db.query(Complaint).filter(Complaint.complaint_id == public_id).first()
        b_records = db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == c_record.id,
            BlockchainRecord.event_type == "COMPLAINT_CREATED",
        ).all()
        assert len(b_records) >= 1, "COMPLAINT_CREATED record not found in PostgreSQL"
        rec_created = b_records[0]
        print(f" -> Status: {rec_created.status}, Block: #{rec_created.block_number}, Tx: {rec_created.transaction_hash}")
        assert rec_created.status == "CONFIRMED", f"Record status is {rec_created.status}"
        assert rec_created.transaction_hash.startswith("0x")

        # Step 4: Officer changes status
        print("\n[STEP 4] Officer advancing status to DEPARTMENT_ASSIGNED & IN_PROGRESS...")
        for next_st in ["DEPARTMENT_ASSIGNED", "IN_PROGRESS"]:
            patch_body = json.dumps({"status": next_st, "remarks": f"Transitioned to {next_st}"}).encode("utf-8")
            st_req = urllib.request.Request(
                f"{fastapi_base}/api/v1/officer/complaints/{public_id}/status",
                data=patch_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {officer_token}",
                },
                method="PATCH",
            )
            st_resp = urllib.request.urlopen(st_req)
            assert st_resp.status == 200
            print(f" -> Transitioned to {next_st}")

        # Step 5: Verify COMPLAINT_STATUS_CHANGED on Blockchain
        print("\n[STEP 5] Verifying COMPLAINT_STATUS_CHANGED on blockchain...")
        st_records = db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == c_record.id,
            BlockchainRecord.event_type == "COMPLAINT_STATUS_CHANGED",
        ).all()
        assert len(st_records) >= 2, "COMPLAINT_STATUS_CHANGED records not found"
        print(f" -> Found {len(st_records)} status change anchors on-chain. Latest Block: #{st_records[-1].block_number}")

        # Step 6: Officer uploads resolution evidence
        print("\n[STEP 6] Officer uploading resolution repair evidence...")
        after_bytes = create_test_jpeg((125, 85, 55))
        res_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="officer_after.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + after_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        res_ev_req = urllib.request.Request(
            f"{fastapi_base}/api/v1/officer/complaints/{public_id}/resolution-evidence",
            data=res_body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {officer_token}",
            },
            method="POST",
        )
        res_ev_resp = urllib.request.urlopen(res_ev_req)
        assert res_ev_resp.status == 201
        print(" -> Officer Resolution Evidence Uploaded")

        # Step 7: Verify RESOLUTION_EVIDENCE_ADDED on Blockchain
        print("\n[STEP 7] Verifying RESOLUTION_EVIDENCE_ADDED on blockchain...")
        ev_records = db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == c_record.id,
            BlockchainRecord.event_type == "RESOLUTION_EVIDENCE_ADDED",
        ).all()
        assert len(ev_records) >= 1, "RESOLUTION_EVIDENCE_ADDED not found"
        print(f" -> Status: {ev_records[0].status}, Block: #{ev_records[0].block_number}, Tx: {ev_records[0].transaction_hash}")

        # Step 8: Run Step 9 Resolution Verification
        print("\n[STEP 8] Officer running AI resolution verification...")
        v_req = urllib.request.Request(
            f"{fastapi_base}/api/v1/officer/complaints/{public_id}/resolution/verify",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {officer_token}",
            },
            method="POST",
        )
        v_resp = urllib.request.urlopen(v_req)
        assert v_resp.status == 200
        v_data = json.loads(v_resp.read().decode("utf-8"))
        print(f" -> Verification Status: {v_data['verification_status']}, Score: {v_data['verification_score']}")

        # Step 9: Verify RESOLUTION_VERIFICATION on Blockchain
        print("\n[STEP 9] Verifying RESOLUTION_VERIFICATION on blockchain...")
        verif_records = db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == c_record.id,
            BlockchainRecord.event_type == "RESOLUTION_VERIFICATION",
        ).all()
        assert len(verif_records) >= 1, "RESOLUTION_VERIFICATION not found"
        print(f" -> Status: {verif_records[0].status}, Block: #{verif_records[0].block_number}, Tx: {verif_records[0].transaction_hash}")

        # Step 10: Human Review
        print("\n[STEP 10] Officer recording human resolution review...")
        hr_body = json.dumps({
            "decision": "APPROVED",
            "review_notes": "Officer inspected asphalt hot-mix patch and verified road is safe for vehicular traffic.",
        }).encode("utf-8")
        hr_req = urllib.request.Request(
            f"{fastapi_base}/api/v1/officer/complaints/{public_id}/resolution/review",
            data=hr_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {officer_token}",
            },
            method="POST",
        )
        hr_resp = urllib.request.urlopen(hr_req)
        assert hr_resp.status == 200
        print(" -> Officer Human Review Decision Recorded: APPROVED")

        # Step 11: Verify HUMAN_RESOLUTION_REVIEW on Blockchain
        print("\n[STEP 11] Verifying HUMAN_RESOLUTION_REVIEW on blockchain...")
        hr_records = db.query(BlockchainRecord).filter(
            BlockchainRecord.complaint_id == c_record.id,
            BlockchainRecord.event_type == "HUMAN_RESOLUTION_REVIEW",
        ).all()
        assert len(hr_records) >= 1, "HUMAN_RESOLUTION_REVIEW not found"
        print(f" -> Status: {hr_records[0].status}, Block: #{hr_records[0].block_number}, Tx: {hr_records[0].transaction_hash}")

        # Step 12: Public Audit Trail Endpoint
        print("\n[STEP 12] Querying public /api/v1/blockchain/complaints/{public_id}...")
        pub_req = urllib.request.Request(f"{fastapi_base}/api/v1/blockchain/complaints/{public_id}")
        pub_resp = urllib.request.urlopen(pub_req)
        assert pub_resp.status == 200
        pub_data = json.loads(pub_resp.read().decode("utf-8"))
        trail_records = pub_data["records"]
        print(f" -> Total Anchors Returned: {len(trail_records)}")

        event_types_found = {r["event_type"] for r in trail_records}
        required_milestones = {
            "COMPLAINT_CREATED",
            "COMPLAINT_STATUS_CHANGED",
            "RESOLUTION_EVIDENCE_ADDED",
            "RESOLUTION_VERIFICATION",
            "HUMAN_RESOLUTION_REVIEW",
        }
        assert required_milestones.issubset(event_types_found), f"Missing milestones: {required_milestones - event_types_found}"
        print(f" -> All 5 required milestones confirmed present on blockchain trail!")

        # Step 13: Cryptographic On-Chain Verification of Each Milestone
        print("\n[STEP 13] Performing cryptographic verification for each record...")
        for r in trail_records:
            v_check_req = urllib.request.Request(f"{fastapi_base}/api/v1/blockchain/records/{r['id']}/verify")
            v_check_resp = urllib.request.urlopen(v_check_req)
            assert v_check_resp.status == 200
            v_check_data = json.loads(v_check_resp.read().decode("utf-8"))
            print(f" -> Record #{r['id']} ({r['event_type']}): Verified={v_check_data['verified']}, Block=#{v_check_data.get('block_number')}")
            assert v_check_data["verified"] is True, f"Verification failed for Record #{r['id']}"

        print("\n" + "=" * 70)
        print(">>> FULL END-TO-END BLOCKCHAIN INTEGRITY FLOW: 100% SUCCESS <<<")
        print("=" * 70)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    ok = run_e2e_flow()
    sys.exit(0 if ok else 1)
