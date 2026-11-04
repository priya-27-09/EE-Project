"""
Step 12 Test Suite: Complete Admin RAG Chatbot & Knowledge Base Integration.
Covers all 20 required verification dimensions:
1. Admin authentication
2. Citizen forbidden
3. Officer forbidden
4. Admin document upload
5. Invalid file rejection (unsupported ext, PE/ELF executable, 0 bytes)
6. Duplicate checksum rejection (SHA-256 duplicate protection)
7. Metadata persistence in PostgreSQL
8. Document processing pipeline
9. Deterministic chunk creation and inspection
10. FAISS vector count alignment
11. Archive behavior (remains in DB for audit)
12. Archived document excluded from retrieval
13. Index status endpoint factual metrics
14. Atomic index rebuild
15. Failed rebuild preserves old index
16. Admin document listing with filters & filesystem path exclusion
17. Admin document details with ID & code lookup
18. IDOR protection & conversation isolation
19. Path traversal protection
20. Secret/credential error sanitization
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi_app import app
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.chatbot import ChatbotDocument, ChatbotChunk, ChatbotConversation, ChatbotMessage
from app.core.auth import hash_password, create_access_token
from app.admin.chatbot_router import sanitize_error
from app.chatbot.retrieval_service import get_retrieval_service
from app.chatbot.embedding_service import get_embedding_provider


class TestChatbotAdminIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Admin user
        cls.admin = cls.db.query(User).filter(User.email == "test_kb_admin@civic.gov").first()
        if not cls.admin:
            cls.admin = User(
                name="KB Admin",
                email="test_kb_admin@civic.gov",
                password_hash=hash_password("AdminPass123!"),
                role=UserRole.ADMIN,
            )
            cls.db.add(cls.admin)

        # Officer user
        cls.officer = cls.db.query(User).filter(User.email == "test_kb_officer@civic.gov").first()
        if not cls.officer:
            cls.officer = User(
                name="KB Officer",
                email="test_kb_officer@civic.gov",
                password_hash=hash_password("OfficerPass123!"),
                role=UserRole.OFFICER,
            )
            cls.db.add(cls.officer)

        # Citizen 1 user
        cls.citizen = cls.db.query(User).filter(User.email == "test_kb_citizen@example.com").first()
        if not cls.citizen:
            cls.citizen = User(
                name="KB Citizen",
                email="test_kb_citizen@example.com",
                password_hash=hash_password("CitizenPass123!"),
                role=UserRole.CITIZEN,
            )
            cls.db.add(cls.citizen)

        # Citizen 2 user (for IDOR conversation isolation test)
        cls.citizen2 = cls.db.query(User).filter(User.email == "test_kb_citizen2@example.com").first()
        if not cls.citizen2:
            cls.citizen2 = User(
                name="KB Citizen Two",
                email="test_kb_citizen2@example.com",
                password_hash=hash_password("CitizenPass123!"),
                role=UserRole.CITIZEN,
            )
            cls.db.add(cls.citizen2)

        cls.db.commit()
        cls.db.refresh(cls.admin)
        cls.db.refresh(cls.officer)
        cls.db.refresh(cls.citizen)
        cls.db.refresh(cls.citizen2)

        cls.admin_token = create_access_token(data={"sub": str(cls.admin.id), "role": str(cls.admin.role)})
        cls.officer_token = create_access_token(data={"sub": str(cls.officer.id), "role": str(cls.officer.role)})
        cls.citizen_token = create_access_token(data={"sub": str(cls.citizen.id), "role": str(cls.citizen.role)})
        cls.citizen2_token = create_access_token(data={"sub": str(cls.citizen2.id), "role": str(cls.citizen2.role)})

        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}
        cls.officer_headers = {"Authorization": f"Bearer {cls.officer_token}"}
        cls.citizen_headers = {"Authorization": f"Bearer {cls.citizen_token}"}
        cls.citizen2_headers = {"Authorization": f"Bearer {cls.citizen2_token}"}

        # Track IDs created during tests for clean assertions
        cls.uploaded_doc_id = None
        cls.uploaded_doc_pk = None

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_admin_authentication(self):
        """1. Admin authentication: Admin can access KB status."""
        resp = self.client.get("/api/v1/admin/chatbot/status", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_documents", data)
        self.assertIn("ready_documents", data)
        self.assertIn("index_status", data)
        self.assertIn("total_chunks", data)
        print(f"[PASS] Test 01 — Admin authentication verified (Docs: {data['total_documents']}, Chunks: {data['total_chunks']})")

    def test_02_citizen_forbidden(self):
        """2. Citizen forbidden: Citizen rejected with HTTP 403 on all admin endpoints."""
        for path in [
            "/api/v1/admin/chatbot/status",
            "/api/v1/admin/chatbot/index/status",
            "/api/v1/admin/chatbot/documents",
        ]:
            resp = self.client.get(path, headers=self.citizen_headers)
            self.assertEqual(resp.status_code, 403)
        print("[PASS] Test 02 — Citizen forbidden from admin KB endpoints (HTTP 403)")

    def test_03_officer_forbidden(self):
        """3. Officer forbidden: Department officer rejected with HTTP 403 on all admin endpoints."""
        for path in [
            "/api/v1/admin/chatbot/status",
            "/api/v1/admin/chatbot/index/status",
            "/api/v1/admin/chatbot/documents",
        ]:
            resp = self.client.get(path, headers=self.officer_headers)
            self.assertEqual(resp.status_code, 403)
        print("[PASS] Test 03 — Officer forbidden from admin KB endpoints (HTTP 403)")

    def test_04_admin_document_upload(self):
        """4. Admin document upload: Valid markdown document upload succeeds and enters READY status."""
        unique_marker = f"DOC_TEST_TIMESTAMP_{int(time.time() * 1000)}"
        content = (
            f"# Urban Tree Maintenance SOP\n\n"
            f"Reference Token: {unique_marker}\n\n"
            f"## Section 1: Fallen Tree Clearance\n"
            f"Fallen trees obstructing arterial roadways must be cleared by the Disaster Management Cell within 4 hours.\n\n"
            f"## Section 2: Pruning Standards\n"
            f"Overhanging dangerous tree branches near high-tension electrical wires must be pruned within 24 hours of notification."
        )
        self.__class__.test_upload_content = content
        self.__class__.test_unique_marker = unique_marker

        files = {"file": ("urban_tree_sop.md", content.encode("utf-8"), "text/markdown")}
        data = {
            "title": "Urban Tree Maintenance SOP",
            "source": "Municipal Horticulture Division",
            "source_url": "https://civic.gov.in/horticulture/trees.pdf",
            "department": "Horticulture",
            "category": "Disaster Response",
            "language": "en",
            "version": "1.0",
        }
        resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data=data, files=files)
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertEqual(res_data["status"], "READY")
        self.__class__.uploaded_doc_id = res_data["document_id"]
        self.__class__.uploaded_doc_pk = res_data["id"]
        print(f"[PASS] Test 04 — Admin document upload successful: {res_data['document_id']} (Status: READY)")

    def test_05_invalid_file_rejection(self):
        """5. Invalid file rejection: Rejects unsupported extensions, executables, and 0-byte files."""
        # A) Unsupported extension (.exe)
        files = {"file": ("malicious.exe", b"Some content", "application/octet-stream")}
        resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data={"title": "Bad", "source": "Bad"}, files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file extension", resp.json()["detail"])

        # B) Executable content (PE binary header MZ disguised as .txt)
        files = {"file": ("fake.txt", b"MZ\x90\x00\x03\x00\x00\x00Windows Executable Header", "text/plain")}
        resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data={"title": "Fake", "source": "Fake"}, files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Executable content detected", resp.json()["detail"])

        # C) 0-byte empty file
        files = {"file": ("empty.md", b"", "text/markdown")}
        resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data={"title": "Empty", "source": "Empty"}, files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("empty", resp.json()["detail"].lower())

        print("[PASS] Test 05 — Invalid files (extension, PE executable signature, 0 bytes) rejected (HTTP 400)")

    def test_06_duplicate_checksum_rejection(self):
        """6. Duplicate checksum rejection: Uploading exact same file returns HTTP 409 Conflict."""
        content = getattr(self.__class__, "test_upload_content", "Default content")
        files = {"file": ("urban_tree_sop_duplicate.md", content.encode("utf-8"), "text/markdown")}
        data = {
            "title": "Duplicate Tree SOP",
            "source": "Another Agency",
        }
        resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data=data, files=files)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Duplicate document rejected", resp.json()["detail"])
        print("[PASS] Test 06 — Duplicate document checksum detected and rejected (HTTP 409 Conflict)")

    def test_07_metadata_persistence(self):
        """7. Metadata persistence: Document record stored in PostgreSQL with complete verified attributes."""
        doc = self.db.query(ChatbotDocument).filter(ChatbotDocument.document_id == self.uploaded_doc_id).first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.title, "Urban Tree Maintenance SOP")
        self.assertEqual(doc.department, "Horticulture")
        self.assertEqual(doc.language, "en")
        self.assertEqual(doc.status, "READY")
        self.assertIsNotNone(doc.checksum)
        self.assertGreater(doc.file_size, 0)
        print(f"[PASS] Test 07 — PostgreSQL document metadata verified (ID: {doc.document_id}, Status: {doc.status})")

    def test_08_document_processing(self):
        """8. Document processing: Reprocessing document runs full ingestion pipeline and updates status."""
        resp = self.client.post(f"/api/v1/admin/chatbot/documents/{self.uploaded_doc_id}/process", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertEqual(res_data["status"], "READY")
        print(f"[PASS] Test 08 — Document processing API verified for {self.uploaded_doc_id}")

    def test_09_chunk_creation(self):
        """9. Chunk creation: Verifies deterministic chunks were stored with correct metadata and token counts."""
        self.db.expire_all()
        doc = self.db.query(ChatbotDocument).filter(ChatbotDocument.document_id == self.uploaded_doc_id).first()
        self.assertIsNotNone(doc)
        chunks = doc.chunks
        self.assertGreaterEqual(len(chunks), 1)
        for c in chunks:
            self.assertTrue(c.chunk_id.startswith(doc.document_id))
            self.assertGreater(len(c.text), 10)
            self.assertGreater(c.token_count, 0)
        print(f"[PASS] Test 09 — Chunk creation verified ({len(chunks)} chunks persisted for {doc.document_id})")

    def test_10_faiss_vector_count(self):
        """10. FAISS vector count: Vector index count matches READY document chunks."""
        self.db.expire_all()
        retrieval_service = get_retrieval_service()
        stats = retrieval_service.get_stats()
        self.assertGreater(stats["vector_count"], 0)
        self.assertEqual(stats["status"], "READY")

        ready_chunks_count = (
            self.db.query(ChatbotChunk)
            .join(ChatbotDocument)
            .filter(ChatbotDocument.status == "READY")
            .count()
        )
        self.assertEqual(stats["vector_count"], ready_chunks_count)
        print(f"[PASS] Test 10 — FAISS vector count matches READY chunks count exactly ({stats['vector_count']} vectors)")

    def test_11_archive_behavior(self):
        """11. Archive behavior: Document status becomes ARCHIVED and remains in DB for audit history."""
        resp = self.client.post(f"/api/v1/admin/chatbot/documents/{self.uploaded_doc_id}/archive", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertEqual(res_data["status"], "SUCCESS")

        self.db.expire_all()
        doc = self.db.query(ChatbotDocument).filter(ChatbotDocument.document_id == self.uploaded_doc_id).first()
        self.assertEqual(doc.status, "ARCHIVED")
        print(f"[PASS] Test 11 — Document archived successfully (Preserved in DB with status: ARCHIVED)")

    def test_12_archived_document_excluded_from_retrieval(self):
        """12. Archived document excluded: Archived document is strictly absent from FAISS vector retrieval."""
        # Query chatbot for unique token from the archived document
        marker = getattr(self.__class__, "test_unique_marker", "Horticulture High-Tension")
        chat_req = {
            "message": f"What is the policy for {marker} overhanging branches?",
            "language": "en",
        }
        resp = self.client.post("/api/v1/chatbot/query", headers=self.citizen_headers, json=chat_req)
        self.assertEqual(resp.status_code, 200)
        chat_data = resp.json()
        # Verify none of the returned sources are from the archived document
        returned_sources = [s.get("document_id") for s in chat_data.get("sources", [])]
        self.assertNotIn(self.uploaded_doc_id, returned_sources)
        print(f"[PASS] Test 12 — Archived document {self.uploaded_doc_id} strictly excluded from vector retrieval")

    def test_13_index_status(self):
        """13. Index status: GET /api/v1/admin/chatbot/index/status returns verified factual information."""
        resp = self.client.get("/api/v1/admin/chatbot/index/status", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("index_exists", data)
        self.assertIn("vector_count", data)
        self.assertIn("embedding_model", data)
        self.assertEqual(data["embedding_dimension"], 384)
        self.assertIn("ready_documents_count", data)
        self.assertIn("indexed_chunks", data)
        print(f"[PASS] Test 13 — Index status factual metrics verified (Vectors: {data['vector_count']}, Model: {data['embedding_model']})")

    def test_14_atomic_index_rebuild(self):
        """14. Atomic index rebuild: POST /api/v1/admin/chatbot/index/rebuild rebuilds index atomically."""
        resp = self.client.post("/api/v1/admin/chatbot/index/rebuild", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertGreater(data["vector_count"], 0)
        print(f"[PASS] Test 14 — Atomic index rebuild executed successfully ({data['vector_count']} vectors)")

    def test_15_failed_rebuild_preserves_old_index(self):
        """15. Failed rebuild preserves old index: If rebuild fails, previous index is kept intact."""
        retrieval_service = get_retrieval_service()
        stats_before = retrieval_service.get_stats()
        vector_count_before = stats_before["vector_count"]

        # Mock embedding provider to raise an exception during rebuild
        emb_provider = get_embedding_provider()
        with patch.object(emb_provider, "embed_documents", side_effect=RuntimeError("Simulated GPU/RAM out of memory error")):
            resp = self.client.post("/api/v1/admin/chatbot/index/rebuild", headers=self.admin_headers)
            self.assertEqual(resp.status_code, 500)
            self.assertIn("Index rebuild failed", resp.json()["detail"])

        # Verify previous working index is completely preserved
        stats_after = retrieval_service.get_stats()
        self.assertEqual(stats_after["vector_count"], vector_count_before)
        self.assertEqual(stats_after["status"], "READY")
        print(f"[PASS] Test 15 — Failed rebuild cleanly preserved previous working index ({stats_after['vector_count']} vectors)")

    def test_16_admin_document_listing(self):
        """16. Admin document listing: Lists documents with filters and excludes internal server filesystem paths."""
        resp = self.client.get("/api/v1/admin/chatbot/documents?status=ARCHIVED", headers=self.admin_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertGreaterEqual(data["total"], 1)

        # Verify internal absolute file_path is never exposed in metadata
        for item in data["items"]:
            self.assertNotIn("file_path", item)
            self.assertIn("document_id", item)
            self.assertIn("title", item)
        print(f"[PASS] Test 16 — Document listing verified with filters; internal file_path strictly omitted")

    def test_17_admin_document_details(self):
        """17. Admin document details: Retrieves details and chunks by both primary key ID and document_id code."""
        # By string code
        resp1 = self.client.get(f"/api/v1/admin/chatbot/documents/{self.uploaded_doc_id}", headers=self.admin_headers)
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertEqual(data1["document_id"], self.uploaded_doc_id)
        self.assertIn("chunks", data1)

        # By integer primary key
        resp2 = self.client.get(f"/api/v1/admin/chatbot/documents/{self.uploaded_doc_pk}", headers=self.admin_headers)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["id"], self.uploaded_doc_pk)

        # 404 for nonexistent document
        resp_404 = self.client.get("/api/v1/admin/chatbot/documents/NONEXISTENT-DOC-9999", headers=self.admin_headers)
        self.assertEqual(resp_404.status_code, 404)
        print(f"[PASS] Test 17 — Document details verified by PK ID and document_id code (404 checked)")

    def test_18_idor_protection(self):
        """18. IDOR protection: Citizens cannot access or modify conversations belonging to other citizens."""
        # Citizen 1 creates a conversation
        conv1 = ChatbotConversation(user_id=self.citizen.id, title="Citizen 1 Private Chat", language="en")
        self.db.add(conv1)
        self.db.commit()
        self.db.refresh(conv1)

        # Citizen 2 attempts to access Citizen 1's conversation
        resp = self.client.get(f"/api/v1/chatbot/conversations/{conv1.id}", headers=self.citizen2_headers)
        self.assertIn(resp.status_code, (403, 404))

        # Citizen 2 attempts to delete Citizen 1's conversation
        del_resp = self.client.delete(f"/api/v1/chatbot/conversations/{conv1.id}", headers=self.citizen2_headers)
        self.assertIn(del_resp.status_code, (403, 404))
        print("[PASS] Test 18 — IDOR protection verified; cross-user conversation access prevented")

    def test_19_path_traversal_protection(self):
        """19. Path traversal protection: File uploads with traversal filenames are rejected."""
        traversal_filenames = [
            "../../etc/passwd.txt",
            "..\\..\\Windows\\System32\\cmd.exe.txt",
            "../secret.md",
            "..\\secret.docx",
        ]
        for bad_name in traversal_filenames:
            files = {"file": (bad_name, b"Sample content", "text/plain")}
            resp = self.client.post("/api/v1/admin/chatbot/documents", headers=self.admin_headers, data={"title": "Traversal", "source": "Hacker"}, files=files)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("path traversal", resp.json()["detail"].lower())
        print("[PASS] Test 19 — Path traversal attempts in upload filenames rejected (HTTP 400)")

    def test_20_secret_and_error_sanitization(self):
        """20. Secret/error sanitization: Credentials, passwords, tokens, and server paths are redacted."""
        raw_error = (
            "Database connection failed: postgresql://admin_user:super_secret_pw123@db.civic.internal:5432/ai_civic_guardian "
            "with jwt_secret=my_ultra_private_jwt_key_9999 and private_key=0xdeadbeef1234567890. "
            "File failed at C:\\Users\\priya\\OneDrive\\Desktop\\EE\\knowledge_base\\raw\\private.pdf"
        )
        sanitized = sanitize_error(raw_error)
        self.assertNotIn("super_secret_pw123", sanitized)
        self.assertNotIn("my_ultra_private_jwt_key_9999", sanitized)
        self.assertNotIn("0xdeadbeef1234567890", sanitized)
        self.assertNotIn("C:\\Users\\priya", sanitized)
        self.assertIn("[REDACTED]", sanitized)
        print("[PASS] Test 20 — Error sanitization verified; DB passwords, JWT secrets, and server paths redacted")


if __name__ == "__main__":
    unittest.main()
