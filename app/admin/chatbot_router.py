import re
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.auth.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.chatbot import ChatbotDocument, ChatbotChunk, ChatbotConversation, ChatbotMessage
from app.chatbot.schemas import (
    DocumentUploadResponse,
    DocumentDetail,
    IndexStatusResponse,
    KBStatusResponse,
)
from app.chatbot.ingestion_service import get_ingestion_service
from app.chatbot.retrieval_service import get_retrieval_service
from app.chatbot.embedding_service import get_embedding_provider
from app.core.config import settings

router = APIRouter(prefix="/api/v1/admin/chatbot", tags=["Admin Knowledge Base Management"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}

EXECUTABLE_SIGNATURES = [
    (b"MZ", "Windows PE executable"),
    (b"\x7fELF", "Linux ELF binary"),
    (b"\xca\xfe\xba\xbe", "Java bytecode / Mach-O universal"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"\xfe\xed\xfa\xcf", "Mach-O executable"),
    (b"\xce\xfa\xed\xfe", "Mach-O executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
]

VALID_STATUS_TRANSITIONS = {
    "UPLOADED": {"PROCESSING", "FAILED", "ARCHIVED"},
    "PROCESSING": {"READY", "FAILED"},
    "READY": {"PROCESSING", "ARCHIVED"},
    "FAILED": {"PROCESSING", "ARCHIVED"},
    "ARCHIVED": {"PROCESSING"},  # May be reprocessed to become READY
}


def sanitize_error(err_str: str) -> str:
    """Sanitizes error messages to strip DB URLs, passwords, secrets, and internal server paths."""
    from app.core.config import settings
    sanitized = re.sub(r'postgres(?:ql)?://[^\s]+', '[REDACTED_DB_URL]', err_str)
    sanitized = re.sub(r'(jwt_secret|private_key|db_password|password|api_key|secret)=[^\s&]+', r'\1=[REDACTED]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'[A-Za-z]:\\[^:\s<>"\',|?*]+', r'[SERVER_PATH]', sanitized)
    sanitized = re.sub(r'/(?:home|usr|etc|var|tmp|app)[^\s:]+', r'[PATH]', sanitized)
    if settings.JWT_SECRET_KEY and settings.JWT_SECRET_KEY in sanitized:
        sanitized = sanitized.replace(settings.JWT_SECRET_KEY, "[REDACTED_JWT_SECRET]")
    if settings.DB_PASSWORD and settings.DB_PASSWORD in sanitized:
        sanitized = sanitized.replace(settings.DB_PASSWORD, "[REDACTED_DB_PASSWORD]")
    return sanitized[:1000]


def validate_status_transition(current_status: str, target_status: str):
    """Enforces valid document status transitions."""
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document status transition from '{current_status}' to '{target_status}'.",
        )


def find_document_by_id_or_code(db: Session, doc_identifier: str) -> ChatbotDocument:
    """Finds document by primary key ID (if numeric) or string document_id code."""
    doc = None
    if str(doc_identifier).isdigit():
        doc = db.query(ChatbotDocument).filter(ChatbotDocument.id == int(doc_identifier)).first()
    if not doc:
        doc = db.query(ChatbotDocument).filter(ChatbotDocument.document_id == str(doc_identifier)).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_identifier}' not found in knowledge base.",
        )
    return doc


@router.post("/documents", response_model=DocumentUploadResponse, summary="Upload and ingest a civic knowledge base document")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(...),
    source_url: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    language: str = Form("en"),
    version: str = Form("1.0"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Admin-only upload endpoint for official civic guideline documents.
    Validates JWT, ADMIN role, file extension, MIME type, file size, filename,
    path traversal, executable content, and SHA-256 duplicate checksum.
    Stores files strictly under knowledge_base/raw/ and processes via existing RAG pipeline.
    """
    raw_filename = file.filename or ""
    # Filename and path traversal validation
    if not raw_filename or ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename or raw_filename.startswith("."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename or path traversal detected in filename.",
        )

    clean_filename = Path(raw_filename).name
    ext = Path(clean_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # MIME type validation
    mime_type = (file.content_type or "").lower().strip()
    if mime_type and mime_type not in ALLOWED_MIME_TYPES.get(ext, set()) and mime_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{mime_type}' for file with extension '{ext}'.",
        )

    # Read and validate content size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of 25MB.",
        )

    # Executable content check
    for sig, desc in EXECUTABLE_SIGNATURES:
        if content.startswith(sig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Executable content detected ({desc}). Executable files are strictly forbidden.",
            )

    # SHA-256 duplicate protection
    checksum = hashlib.sha256(content).hexdigest()
    existing = db.query(ChatbotDocument).filter(ChatbotDocument.checksum == checksum).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document rejected. A document with identical checksum already exists (Document ID: {existing.document_id}, Title: '{existing.title}').",
        )

    # Save securely strictly under knowledge_base/raw/
    raw_dir = Path(settings.KNOWLEDGE_BASE_DIR) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    base_count = db.query(ChatbotDocument).count() + 1
    doc_id_candidate = f"DOC-2026-{base_count:06d}"
    while db.query(ChatbotDocument).filter(ChatbotDocument.document_id == doc_id_candidate).first():
        base_count += 1
        doc_id_candidate = f"DOC-2026-{base_count:06d}"

    target_path = raw_dir / f"{doc_id_candidate}_{clean_filename}"
    if not target_path.resolve().is_relative_to(raw_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal attempt detected in target destination.",
        )

    target_path.write_bytes(content)

    # Ingest document using real ingestion pipeline
    try:
        ingestion_service = get_ingestion_service()
        result = ingestion_service.ingest_file(
            db=db,
            file_path=target_path,
            title=title.strip(),
            source=source.strip(),
            source_url=source_url.strip() if source_url else None,
            department=department.strip() if department else None,
            category=category.strip() if category else None,
            language=language.strip(),
            version=version.strip(),
            custom_document_id=doc_id_candidate,
        )

        return DocumentUploadResponse(
            id=result["id"],
            document_id=result["document_id"],
            title=title.strip(),
            status=result["status"],
            message=result["message"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        sanitized = sanitize_error(str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest document: {sanitized}",
        )


@router.get("/documents", summary="List knowledge base documents")
def list_documents(
    status_filter: Optional[str] = Query(None, alias="status"),
    department: Optional[str] = None,
    category: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Returns filtered, paginated list of knowledge base documents with chunk counts.
    Returns metadata only. Internal absolute filesystem paths are strictly excluded.
    """
    query = db.query(ChatbotDocument)
    if status_filter:
        query = query.filter(ChatbotDocument.status == status_filter.upper())
    if department:
        query = query.filter(ChatbotDocument.department.ilike(f"%{department}%"))
    if category:
        query = query.filter(ChatbotDocument.category.ilike(f"%{category}%"))
    if language:
        query = query.filter(ChatbotDocument.language == language.lower())

    total = query.count()
    docs = query.order_by(ChatbotDocument.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [d.to_dict() for d in docs],
    }


@router.get("/documents/{document_id}", response_model=DocumentDetail, summary="Get document details and chunks")
def get_document_detail(
    document_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Retrieves full details for a document including chunk list and processing diagnostics.
    Omits secrets and server filesystem paths.
    """
    doc = find_document_by_id_or_code(db, document_id)
    chunks_data = [c.to_dict() for c in doc.chunks]
    doc_dict = doc.to_dict()
    # Ensure error message is sanitized if present
    if doc_dict.get("error_message"):
        doc_dict["error_message"] = sanitize_error(doc_dict["error_message"])
    doc_dict["chunks"] = chunks_data
    return DocumentDetail(**doc_dict)


@router.post("/documents/{document_id}/process", summary="Process or reprocess document")
def process_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Reprocesses an existing document from its raw stored file using the real ingestion pipeline.
    Validates status transition to PROCESSING.
    """
    doc = find_document_by_id_or_code(db, document_id)
    validate_status_transition(doc.status, "PROCESSING")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source document file is missing on storage.",
        )

    # Remove existing chunks for this document in PostgreSQL
    db.query(ChatbotChunk).filter(ChatbotChunk.document_id == doc.id).delete()
    doc.status = "PROCESSING"
    db.commit()

    ingestion_service = get_ingestion_service()
    result = ingestion_service.ingest_file(
        db=db,
        file_path=file_path,
        title=doc.title,
        source=doc.source,
        source_url=doc.source_url,
        department=doc.department,
        category=doc.category,
        language=doc.language,
        version=doc.version,
        custom_document_id=doc.document_id,
        reprocess=True,
    )
    return result


@router.post("/documents/{document_id}/archive", summary="Archive document and exclude from retrieval")
def archive_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Marks a document as ARCHIVED and triggers an atomic rebuild of the FAISS index
    so its chunks are immediately excluded from live vector retrieval.
    """
    doc = find_document_by_id_or_code(db, document_id)
    validate_status_transition(doc.status, "ARCHIVED")

    doc.status = "ARCHIVED"
    db.commit()

    # Rebuild index without archived document
    retrieval_service = get_retrieval_service()
    rebuild_result = retrieval_service.rebuild_index(db)

    return {
        "status": "SUCCESS",
        "message": f"Document '{doc.title}' ({doc.document_id}) archived and excluded from vector index.",
        "document_id": doc.document_id,
        "rebuild": rebuild_result,
    }


@router.post("/index/rebuild", summary="Atomic FAISS vector index rebuild")
@router.post("/rebuild-index", summary="Atomic FAISS vector index rebuild (compatibility alias)")
def rebuild_vector_index(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Rebuilds the FAISS vector index from scratch using all READY documents in PostgreSQL.
    Employs atomic replacement: if rebuild fails, the existing working index is preserved.
    """
    retrieval_service = get_retrieval_service()
    try:
        result = retrieval_service.rebuild_index(db)
        return result
    except Exception as exc:
        sanitized = sanitize_error(str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Index rebuild failed: {sanitized}",
        )


@router.get("/index/status", response_model=IndexStatusResponse, summary="Get FAISS vector index status")
def get_index_status(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Returns factual operational diagnostics about the active FAISS vector index.
    """
    retrieval_service = get_retrieval_service()
    index_stats = retrieval_service.get_stats()
    emb_provider = get_embedding_provider()
    emb_status = emb_provider.status()

    ready_docs = db.query(ChatbotDocument).filter(ChatbotDocument.status == "READY").count()
    indexed_chunks = (
        db.query(ChatbotChunk)
        .join(ChatbotDocument)
        .filter(ChatbotDocument.status == "READY")
        .count()
    )

    return IndexStatusResponse(
        index_exists=bool(index_stats.get("status") == "READY" or index_stats.get("vector_count", 0) > 0),
        status=index_stats.get("status", "EMPTY"),
        vector_count=index_stats.get("vector_count", 0),
        embedding_model=emb_status.get("model_name", settings.EMBEDDING_MODEL_NAME),
        embedding_dimension=emb_status.get("dimension", settings.EMBEDDING_DIMENSION),
        last_rebuild=index_stats.get("last_modified"),
        ready_documents_count=ready_docs,
        indexed_chunks=indexed_chunks,
    )


@router.get("/status", response_model=KBStatusResponse, summary="Get Knowledge Base and Index Status")
def get_kb_status(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
):
    """
    Returns real operational diagnostics about documents, chunks, vector index,
    embedding provider, and chatbot usage analytics.
    Zero fake statistics.
    """
    total_docs = db.query(ChatbotDocument).count()
    ready_docs = db.query(ChatbotDocument).filter(ChatbotDocument.status == "READY").count()
    processing_docs = db.query(ChatbotDocument).filter(ChatbotDocument.status == "PROCESSING").count()
    failed_docs = db.query(ChatbotDocument).filter(ChatbotDocument.status == "FAILED").count()
    archived_docs = db.query(ChatbotDocument).filter(ChatbotDocument.status == "ARCHIVED").count()

    chunk_count = db.query(ChatbotChunk).count()

    retrieval_service = get_retrieval_service()
    index_stats = retrieval_service.get_stats()

    embedding_provider = get_embedding_provider()
    emb_status = embedding_provider.status()

    # Real usage analytics from PostgreSQL
    total_convs = db.query(ChatbotConversation).count()
    total_questions = db.query(ChatbotMessage).filter(ChatbotMessage.role == "user").count()

    lang_counts = (
        db.query(ChatbotMessage.language, func.count(ChatbotMessage.id))
        .filter(ChatbotMessage.role == "user")
        .group_by(ChatbotMessage.language)
        .all()
    )
    lang_dist = {l: count for l, count in lang_counts}

    success_retrievals = (
        db.query(ChatbotMessage)
        .filter(ChatbotMessage.role == "assistant", ChatbotMessage.retrieval_status == "SUCCESS")
        .count()
    )
    failed_retrievals = (
        db.query(ChatbotMessage)
        .filter(ChatbotMessage.role == "assistant", ChatbotMessage.retrieval_status != "SUCCESS")
        .count()
    )

    return KBStatusResponse(
        status="READY" if index_stats["status"] == "READY" else "INITIALIZING",
        total_documents=total_docs,
        ready_documents=ready_docs,
        processing_documents=processing_docs,
        failed_documents=failed_docs,
        archived_documents=archived_docs,
        total_chunks=chunk_count,
        faiss_vector_count=index_stats["vector_count"],
        embedding_model=emb_status["model_name"],
        embedding_dimension=emb_status["dimension"],
        last_successful_index_rebuild=index_stats.get("last_modified"),
        index_status=index_stats["status"],
        # Backward compatibility
        document_count=total_docs,
        ready_count=ready_docs,
        processing_count=processing_docs,
        failed_count=failed_docs,
        archived_count=archived_docs,
        chunk_count=chunk_count,
        index_size=index_stats["vector_count"],
        last_indexed_at=index_stats.get("last_modified"),
        last_successful_rebuild=index_stats.get("last_modified"),
        failed_ingestion_count=failed_docs,
        active_documents_count=ready_docs,
        analytics={
            "total_conversations": total_convs,
            "total_questions": total_questions,
            "questions_by_language": lang_dist,
            "successful_retrievals": success_retrievals,
            "retrieval_failures": failed_retrievals,
        },
    )
