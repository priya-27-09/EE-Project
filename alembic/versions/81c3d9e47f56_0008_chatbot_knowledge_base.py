"""0008_chatbot_knowledge_base

Revision ID: 81c3d9e47f56
Revises: 63a1b7c25d34
Create Date: 2026-09-23 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "81c3d9e47f56"
down_revision: Union[str, None] = "63a1b7c25d34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. chatbot_documents
    op.create_table(
        "chatbot_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("checksum", sa.String(length=66), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="UPLOADED", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chatbot_documents_id"), "chatbot_documents", ["id"], unique=False)
    op.create_index(op.f("ix_chatbot_documents_document_id"), "chatbot_documents", ["document_id"], unique=True)
    op.create_index(op.f("ix_chatbot_documents_checksum"), "chatbot_documents", ["checksum"], unique=False)
    op.create_index(op.f("ix_chatbot_documents_status"), "chatbot_documents", ["status"], unique=False)
    op.create_index(op.f("ix_chatbot_documents_created_at"), "chatbot_documents", ["created_at"], unique=False)

    # 2. chatbot_chunks
    op.create_table(
        "chatbot_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("vector_index_id", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["chatbot_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chatbot_chunks_id"), "chatbot_chunks", ["id"], unique=False)
    op.create_index(op.f("ix_chatbot_chunks_document_id"), "chatbot_chunks", ["document_id"], unique=False)
    op.create_index(op.f("ix_chatbot_chunks_chunk_id"), "chatbot_chunks", ["chunk_id"], unique=True)
    op.create_index(op.f("ix_chatbot_chunks_vector_index_id"), "chatbot_chunks", ["vector_index_id"], unique=False)

    # 3. chatbot_conversations
    op.create_table(
        "chatbot_conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("title", sa.String(length=255), server_default="Civic Inquiry", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chatbot_conversations_id"), "chatbot_conversations", ["id"], unique=False)
    op.create_index(op.f("ix_chatbot_conversations_user_id"), "chatbot_conversations", ["user_id"], unique=False)
    op.create_index(op.f("ix_chatbot_conversations_created_at"), "chatbot_conversations", ["created_at"], unique=False)

    # 4. chatbot_messages
    op.create_table(
        "chatbot_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("retrieved_chunks", sa.Text(), nullable=True),
        sa.Column("retrieval_status", sa.String(length=32), server_default="SUCCESS", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chatbot_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chatbot_messages_id"), "chatbot_messages", ["id"], unique=False)
    op.create_index(op.f("ix_chatbot_messages_conversation_id"), "chatbot_messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_chatbot_messages_created_at"), "chatbot_messages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("chatbot_messages")
    op.drop_table("chatbot_conversations")
    op.drop_table("chatbot_chunks")
    op.drop_table("chatbot_documents")
