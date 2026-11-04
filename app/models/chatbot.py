import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ChatbotDocument(Base):
    """
    Knowledge base document registry tracking official civic guidelines,
    SOPs, charters, and regulations ingested for RAG retrieval.
    """
    __tablename__ = "chatbot_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    source = Column(String(255), nullable=False)
    source_url = Column(String(512), nullable=True)
    department = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    language = Column(String(10), default="en", nullable=False)
    version = Column(String(32), default="1.0", nullable=False)
    checksum = Column(String(66), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(16), nullable=False)  # pdf, txt, md, docx
    file_size = Column(Integer, nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    status = Column(String(32), default="UPLOADED", index=True, nullable=False)  # UPLOADED, PROCESSING, READY, FAILED, ARCHIVED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    chunks = relationship("ChatbotChunk", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "source_url": self.source_url,
            "department": self.department,
            "category": self.category,
            "language": self.language,
            "version": self.version,
            "checksum": self.checksum,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "status": self.status,
            "error_message": self.error_message,
            "chunk_count": len(self.chunks) if self.chunks else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatbotChunk(Base):
    """
    Deterministic chunk of an ingested document used for FAISS vector indexing
    and contextual retrieval.
    """
    __tablename__ = "chatbot_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("chatbot_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(128), unique=True, index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, default=1, nullable=False)
    section = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    vector_index_id = Column(Integer, nullable=True, index=True)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("ChatbotDocument", back_populates="chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section,
            "text": self.text,
            "vector_index_id": self.vector_index_id,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChatbotConversation(Base):
    """
    Citizen or officer multi-turn conversation thread.
    Isolated by user_id to enforce RBAC and prevent IDOR.
    """
    __tablename__ = "chatbot_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    language = Column(String(10), default="en", nullable=False)
    title = Column(String(255), default="Civic Inquiry", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")
    messages = relationship("ChatbotMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatbotMessage.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "language": self.language,
            "title": self.title,
            "message_count": len(self.messages) if self.messages else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatbotMessage(Base):
    """
    Single message turn in a conversation storing question, response,
    retrieved chunk references, and retrieval status.
    """
    __tablename__ = "chatbot_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chatbot_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    original_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    language = Column(String(10), default="en", nullable=False)
    retrieved_chunks = Column(Text, nullable=True)  # JSON-encoded array of chunk metadata
    retrieval_status = Column(String(32), default="SUCCESS", nullable=False)  # SUCCESS, NO_RELEVANT_CONTEXT, NOT_CONFIGURED, FAILED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    conversation = relationship("ChatbotConversation", back_populates="messages")

    def to_dict(self):
        sources = []
        if self.retrieved_chunks:
            try:
                sources = json.loads(self.retrieved_chunks)
            except Exception:
                sources = []
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "original_text": self.original_text,
            "response_text": self.response_text,
            "language": self.language,
            "sources": sources,
            "retrieval_status": self.retrieval_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
