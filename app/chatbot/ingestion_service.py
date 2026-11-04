import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chatbot import ChatbotDocument, ChatbotChunk
from app.chatbot.chunking_service import DocumentChunker
from app.chatbot.embedding_service import get_embedding_provider
from app.chatbot.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """
    Ingestion pipeline supporting PDF, TXT, MD, and DOCX files.
    Calculates SHA-256 checksums, prevents identical duplicates, extracts text,
    creates deterministic chunks, embeds via multilingual model, and updates FAISS.
    """

    def __init__(self):
        self.chunker = DocumentChunker()
        self.kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
        self.raw_dir = self.kb_dir / "raw"
        self.processed_dir = self.kb_dir / "processed"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def compute_checksum(self, file_bytes: bytes) -> str:
        """Returns standard hex SHA-256 of file contents."""
        return hashlib.sha256(file_bytes).hexdigest()

    def extract_text_and_pages(self, file_path: Path, file_type: str) -> List[Tuple[int, str]]:
        """
        Extracts list of (page_number, text) tuples from the document.
        """
        ext = file_type.lower().strip(".")
        pages_text: List[Tuple[int, str]] = []

        if ext == "pdf":
            import pymupdf
            doc = pymupdf.open(str(file_path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text and text.strip():
                    pages_text.append((page_num + 1, text))
            doc.close()
            if not pages_text:
                pages_text.append((1, ""))

        elif ext in ("txt", "md"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            pages_text.append((1, content))

        elif ext in ("docx", "doc"):
            import docx
            doc = docx.Document(str(file_path))
            paras = []
            for p in doc.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                style_name = (p.style.name or "").lower() if p.style else ""
                if "heading 1" in style_name:
                    paras.append(f"# {txt}")
                elif "heading 2" in style_name or "heading 3" in style_name:
                    paras.append(f"## {txt}")
                else:
                    paras.append(txt)
            content = "\n\n".join(paras)
            pages_text.append((1, content))

        else:
            raise ValueError(f"Unsupported file format: .{ext}. Supported formats: PDF, TXT, MD, DOCX.")

        return pages_text

    def ingest_file(
        self,
        db: Session,
        file_path: Path,
        title: str,
        source: str,
        source_url: Optional[str] = None,
        department: Optional[str] = None,
        category: Optional[str] = None,
        language: str = "en",
        version: str = "1.0",
        custom_document_id: Optional[str] = None,
        reprocess: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingests a document file into PostgreSQL and FAISS.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Source file not found at: {file_path}")

        file_bytes = file_path.read_bytes()
        file_size = len(file_bytes)
        checksum = self.compute_checksum(file_bytes)
        file_type = file_path.suffix.lower().strip(".")

        # Check for exact duplicate checksum in PostgreSQL
        existing = db.query(ChatbotDocument).filter(ChatbotDocument.checksum == checksum).first()
        if existing and not reprocess:
            logger.info("Duplicate document detected with checksum %s (ID: %s)", checksum, existing.document_id)
            return {
                "status": "DUPLICATE",
                "message": f"Document with identical content already exists (Document ID: {existing.document_id}).",
                "document_id": existing.document_id,
                "id": existing.id,
            }

        # Generate unique document ID if not supplied
        if not custom_document_id:
            base_count = db.query(ChatbotDocument).count() + 1
            candidate = f"DOC-2026-{base_count:06d}"
            while db.query(ChatbotDocument).filter(ChatbotDocument.document_id == candidate).first():
                base_count += 1
                candidate = f"DOC-2026-{base_count:06d}"
            document_id = candidate
        else:
            document_id = custom_document_id

        # Copy raw file to knowledge_base/raw if not already there
        target_raw_path = self.raw_dir / f"{document_id}_{file_path.name}"
        if file_path.resolve() != target_raw_path.resolve():
            target_raw_path.write_bytes(file_bytes)
            final_file_path = str(target_raw_path)
        else:
            final_file_path = str(file_path)

        # Retrieve or create record in PROCESSING status
        doc_record = db.query(ChatbotDocument).filter(ChatbotDocument.document_id == document_id).first()
        if not doc_record:
            doc_record = ChatbotDocument(
                document_id=document_id,
                title=title,
                source=source,
                source_url=source_url,
                department=department,
                category=category,
                language=language,
                version=version,
                checksum=checksum,
                file_path=final_file_path,
                file_type=file_type,
                file_size=file_size,
                page_count=1,
                status="PROCESSING",
            )
            db.add(doc_record)
        else:
            doc_record.title = title
            doc_record.source = source
            doc_record.source_url = source_url
            doc_record.department = department
            doc_record.category = category
            doc_record.language = language
            doc_record.version = version
            doc_record.checksum = checksum
            doc_record.file_path = final_file_path
            doc_record.file_type = file_type
            doc_record.file_size = file_size
            doc_record.status = "PROCESSING"

        db.commit()
        db.refresh(doc_record)

        try:
            # Extract text
            pages = self.extract_text_and_pages(Path(final_file_path), file_type)
            doc_record.page_count = len(pages)

            # Chunk document across all pages
            all_chunks_data: List[Dict[str, Any]] = []
            for page_num, page_text in pages:
                page_chunks = self.chunker.chunk_document(
                    document_id=document_id,
                    text=page_text,
                    page_number=page_num,
                    default_section=title,
                )
                all_chunks_data.extend(page_chunks)

            if not all_chunks_data:
                raise ValueError("Document yielded zero text chunks. File may be empty or unreadable.")

            # Remove any existing chunks for this document if re-ingesting or reprocessing
            db.query(ChatbotChunk).filter(ChatbotChunk.document_id == doc_record.id).delete()
            db.flush()

            # Save chunks to PostgreSQL
            chunk_models = []
            chunk_texts = []
            chunk_metas = []

            for c_data in all_chunks_data:
                chunk_obj = ChatbotChunk(
                    document_id=doc_record.id,
                    chunk_id=c_data["chunk_id"],
                    chunk_index=c_data["chunk_index"],
                    page_number=c_data["page_number"],
                    section=c_data["section"],
                    text=c_data["text"],
                    token_count=c_data.get("token_count", len(c_data["text"].split())),
                )
                db.add(chunk_obj)
                chunk_models.append(chunk_obj)
                chunk_texts.append(c_data["text"])
                chunk_metas.append({
                    "chunk_id": c_data["chunk_id"],
                    "document_id": document_id,
                    "title": title,
                    "source": source,
                    "source_url": source_url,
                    "department": department,
                    "page": c_data["page_number"],
                    "section": c_data["section"],
                    "text": c_data["text"],
                })

            db.commit()

            # Embed chunks
            embedding_provider = get_embedding_provider()
            if not embedding_provider.is_available:
                raise RuntimeError("Multilingual embedding provider is unavailable; cannot index document.")

            vectors = embedding_provider.embed_documents(chunk_texts)

            # Update status to READY
            doc_record.status = "READY"
            doc_record.error_message = None
            db.commit()
            db.refresh(doc_record)

            # Rebuild FAISS index atomically so vector count aligns with all READY chunks
            retrieval_service = get_retrieval_service()
            retrieval_service.rebuild_index(db)

            logger.info("Successfully ingested document %s (%d chunks)", document_id, len(chunk_models))
            return {
                "status": "READY",
                "message": f"Successfully ingested {len(chunk_models)} chunks into knowledge base.",
                "document_id": document_id,
                "id": doc_record.id,
                "chunk_count": len(chunk_models),
                "page_count": doc_record.page_count,
            }

        except Exception as exc:
            db.rollback()
            logger.error("Ingestion failed for %s: %s", document_id, exc)
            raw_err = str(exc)
            sanitized_err = re.sub(r'postgres(?:ql)?://[^\s]+', '[REDACTED_DB_URL]', raw_err)
            sanitized_err = re.sub(r'(jwt_secret|private_key|db_password|password)=[^\s&]+', r'\1=[REDACTED]', sanitized_err)
            sanitized_err = re.sub(r'[A-Za-z]:\\[^:\s<>"\',|?*]+', r'[SERVER_PATH]', sanitized_err)
            try:
                failed_doc = db.query(ChatbotDocument).filter(ChatbotDocument.document_id == document_id).first()
                if failed_doc:
                    failed_doc.status = "FAILED"
                    failed_doc.error_message = sanitized_err[:1000]
                    db.commit()
            except Exception:
                db.rollback()
            return {
                "status": "FAILED",
                "message": f"Ingestion failed: {sanitized_err}",
                "document_id": document_id,
                "id": doc_record.id if doc_record else None,
            }


_ingestion_service = None

def get_ingestion_service() -> DocumentIngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = DocumentIngestionService()
    return _ingestion_service
