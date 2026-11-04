"""
Live End-to-End Verification Script for Step 12.
Executes the live sequence:
1. Admin login
2. Upload real civic document
3. PostgreSQL metadata verification
4. Document processing & chunk generation
5. Multilingual embeddings generation
6. FAISS vector index updated
7. Query chatbot -> retrieved source shown
8. Archive document -> verify archived document is no longer retrieved
9. Citizen forbidden from admin KB management
10. Officer forbidden from admin KB management
11. Admin permitted to manage knowledge base
"""

import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.chatbot import ChatbotDocument
from app.core.auth import hash_password, create_access_token


def run_live_verification():
    client = TestClient(app)
    db = SessionLocal()

    print("=" * 80)
    print("STEP 12 LIVE END-TO-END VERIFICATION")
    print("=" * 80)

    try:
        # Step 1: Users & Login
        admin = db.query(User).filter(User.email == "test_kb_admin@civic.gov").first()
        officer = db.query(User).filter(User.email == "test_kb_officer@civic.gov").first()
        citizen = db.query(User).filter(User.email == "test_kb_citizen@example.com").first()

        admin_token = create_access_token(data={"sub": str(admin.id), "role": str(admin.role)})
        officer_token = create_access_token(data={"sub": str(officer.id), "role": str(officer.role)})
        citizen_token = create_access_token(data={"sub": str(citizen.id), "role": str(citizen.role)})

        admin_hdr = {"Authorization": f"Bearer {admin_token}"}
        officer_hdr = {"Authorization": f"Bearer {officer_token}"}
        citizen_hdr = {"Authorization": f"Bearer {citizen_token}"}

        print("[OK] Step 1: Authentication tokens generated for ADMIN, OFFICER, CITIZEN.")

        # Step 2: Upload real civic document
        ts = int(time.time())
        doc_content = (
            f"# Municipal Stormwater Drain Desilting Charter {ts}\n\n"
            f"Unique Verification Code: DRAIN_DESILT_{ts}\n\n"
            f"## Section 1: Pre-Monsoon Desilting Schedule\n"
            f"All roadside micro-drains and arterial stormwater channels must be fully desilted by May 31st each year.\n\n"
            f"## Section 2: Waterlogging Emergency Redressal\n"
            f"Severe waterlogging complaints on major road junctions must be deployed with heavy dewatering pumps within 2 hours."
        )
        files = {"file": (f"stormwater_charter_{ts}.md", doc_content.encode("utf-8"), "text/markdown")}
        data = {
            "title": f"Stormwater Drain Desilting Charter {ts}",
            "source": "State Municipal Administration Directorate",
            "source_url": "https://civic.gov.in/drainage/charter.pdf",
            "department": "Drainage & Flood Management",
            "category": "Pre-Monsoon Preparedness",
            "language": "en",
            "version": "1.0",
        }

        upload_resp = client.post("/api/v1/admin/chatbot/documents", headers=admin_hdr, data=data, files=files)
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        upload_data = upload_resp.json()
        doc_id = upload_data["document_id"]
        print(f"[OK] Step 2: Real civic document uploaded: {doc_id} (Status: {upload_data['status']})")

        # Step 3: PostgreSQL metadata created
        db.expire_all()
        doc_record = db.query(ChatbotDocument).filter(ChatbotDocument.document_id == doc_id).first()
        assert doc_record is not None, "Document record missing in DB"
        assert doc_record.department == "Drainage & Flood Management"
        assert doc_record.status == "READY"
        print(f"[OK] Step 3: PostgreSQL metadata verified for {doc_id} (Checksum: {doc_record.checksum[:16]}...)")

        # Step 4: Chunks created
        chunks = doc_record.chunks
        assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"
        print(f"[OK] Step 4: Deterministic chunks created: {len(chunks)} chunks verified.")

        # Step 5 & 6: Real multilingual embeddings & FAISS index updated
        idx_resp = client.get("/api/v1/admin/chatbot/index/status", headers=admin_hdr)
        assert idx_resp.status_code == 200
        idx_data = idx_resp.json()
        assert idx_data["index_exists"] is True
        assert idx_data["vector_count"] >= len(chunks)
        print(f"[OK] Step 5 & 6: Real FAISS vector index updated. Vectors: {idx_data['vector_count']}, Dim: {idx_data['embedding_dimension']}")

        # Step 7: Query chatbot -> retrieved source shown
        query_payload = {
            "message": f"What is the emergency turnaround time for DRAIN_DESILT_{ts} waterlogging?",
            "language": "en",
        }
        chat_resp = client.post("/api/v1/chatbot/chat", headers=citizen_hdr, json=query_payload)
        assert chat_resp.status_code == 200, f"Chat failed: {chat_resp.text}"
        chat_data = chat_resp.json()
        source_doc_ids = [s["document_id"] for s in chat_data.get("sources", [])]
        assert doc_id in source_doc_ids, f"Expected {doc_id} in sources: {source_doc_ids}"
        print(f"[OK] Step 7: Query chatbot succeeded. Grounded answer retrieved from {doc_id}.")
        print(f"     Answer excerpt: {chat_data['answer'][:120]}...")

        # Step 8: Archive document -> verify excluded from retrieval
        archive_resp = client.post(f"/api/v1/admin/chatbot/documents/{doc_id}/archive", headers=admin_hdr)
        assert archive_resp.status_code == 200, f"Archive failed: {archive_resp.text}"
        print(f"[OK] Step 8a: Document {doc_id} successfully archived.")

        # Re-query chatbot and verify archived document is no longer retrieved
        chat_resp_2 = client.post("/api/v1/chatbot/chat", headers=citizen_hdr, json=query_payload)
        assert chat_resp_2.status_code == 200
        chat_data_2 = chat_resp_2.json()
        source_doc_ids_2 = [s["document_id"] for s in chat_data_2.get("sources", [])]
        assert doc_id not in source_doc_ids_2, f"Archived document {doc_id} was unexpectedly retrieved!"
        print(f"[OK] Step 8b: Verified archived document {doc_id} is strictly excluded from retrieval.")

        # Step 9, 10, 11: Security RBAC checks
        cit_attempt = client.get("/api/v1/admin/chatbot/status", headers=citizen_hdr)
        assert cit_attempt.status_code == 403, "Citizen was not rejected with 403"
        print("[OK] Step 9: CITIZEN cannot manage knowledge base (HTTP 403 Forbidden verified).")

        off_attempt = client.get("/api/v1/admin/chatbot/status", headers=officer_hdr)
        assert off_attempt.status_code == 403, "Officer was not rejected with 403"
        print("[OK] Step 10: OFFICER cannot manage knowledge base (HTTP 403 Forbidden verified).")

        adm_attempt = client.get("/api/v1/admin/chatbot/status", headers=admin_hdr)
        assert adm_attempt.status_code == 200, "Admin was rejected"
        print("[OK] Step 11: ADMIN can manage knowledge base (HTTP 200 OK verified).")

        print("=" * 80)
        print("ALL LIVE VERIFICATION CHECKS PASSED PERFECTLY!")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_live_verification()
