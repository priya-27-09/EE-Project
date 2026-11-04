from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, field_validator


class SourceReference(BaseModel):
    document_id: str
    title: str
    page: int = 1
    section: Optional[str] = None
    source: str
    url: Optional[str] = None
    similarity: float = 0.0


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Citizen inquiry text")
    language: str = Field(default="en", description="Preferred response language: en, ta, hi")
    conversation_id: Optional[int] = Field(default=None, description="Existing conversation thread ID or null")

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty or only whitespace")
        return cleaned

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        lang = (v or "en").lower().strip()
        if lang not in ("en", "ta", "hi"):
            return "en"
        return lang


class ChatResponse(BaseModel):
    answer: str
    language: str
    conversation_id: int
    sources: List[SourceReference] = []
    retrieval_status: str = "SUCCESS"  # SUCCESS, NO_RELEVANT_CONTEXT, NOT_CONFIGURED, FAILED


class ConversationSummary(BaseModel):
    id: int
    title: str
    language: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MessageDetail(BaseModel):
    id: int
    role: str
    original_text: str
    response_text: Optional[str] = None
    language: str
    sources: List[Dict[str, Any]] = []
    retrieval_status: str
    created_at: Optional[str] = None


class ConversationDetail(BaseModel):
    id: int
    title: str
    language: str
    messages: List[MessageDetail] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    id: int
    document_id: str
    title: str
    status: str
    message: str


class DocumentDetail(BaseModel):
    id: int
    document_id: str
    title: str
    source: str
    source_url: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    language: str
    version: str
    checksum: str
    file_type: str
    file_size: int
    page_count: int
    status: str
    error_message: Optional[str] = None
    chunk_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    chunks: List[Dict[str, Any]] = []


class IndexStatusResponse(BaseModel):
    index_exists: bool
    status: str
    vector_count: int
    embedding_model: str
    embedding_dimension: int
    last_rebuild: Optional[str] = None
    ready_documents_count: int
    indexed_chunks: int


class KBStatusResponse(BaseModel):
    status: str
    total_documents: int
    ready_documents: int
    processing_documents: int
    failed_documents: int
    archived_documents: int
    total_chunks: int
    faiss_vector_count: int
    embedding_model: str
    embedding_dimension: int
    last_successful_index_rebuild: Optional[str] = None
    index_status: str
    # Backward compatibility fields
    document_count: int = 0
    ready_count: int = 0
    processing_count: int = 0
    failed_count: int = 0
    archived_count: int = 0
    chunk_count: int = 0
    index_size: int = 0
    last_indexed_at: Optional[str] = None
    last_successful_rebuild: Optional[str] = None
    failed_ingestion_count: int = 0
    active_documents_count: int = 0
    analytics: Dict[str, Any] = {}
