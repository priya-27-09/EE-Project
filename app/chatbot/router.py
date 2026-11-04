import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.chatbot import ChatbotConversation, ChatbotMessage
from app.chatbot.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    ConversationDetail,
    MessageDetail,
)
from app.chatbot.chatbot_service import get_chatbot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chatbot", tags=["Civic AI Chatbot"])


@router.post("/chat", response_model=ChatResponse, summary="Send a question to the Civic Assistant")
@router.post("/query", response_model=ChatResponse, summary="Send a question to the Civic Assistant (alias)")
def chat_with_assistant(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submits a civic inquiry to the multilingual RAG engine.
    Embeds question, performs FAISS vector search, synthesizes grounded answer,
    and returns official source references.
    """
    service = get_chatbot_service()
    try:
        response = service.process_chat(
            db=db,
            user_id=current_user.id,
            message=payload.message,
            language=payload.language,
            conversation_id=payload.conversation_id,
        )
        return response
    except Exception as exc:
        logger.error("Chatbot processing error for user %d: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chatbot failed to process message: {str(exc)}",
        )


@router.get("/conversations", response_model=List[ConversationSummary], summary="List user's conversations")
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns paginated list of conversations belonging strictly to the current user.
    """
    convs = (
        db.query(ChatbotConversation)
        .filter(ChatbotConversation.user_id == current_user.id)
        .order_by(ChatbotConversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            language=c.language,
            message_count=len(c.messages),
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail, summary="Get conversation messages")
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves full message history for a specific conversation.
    Enforces strict user ownership to prevent IDOR attacks.
    """
    conv = (
        db.query(ChatbotConversation)
        .filter(ChatbotConversation.id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.user_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot view conversations belonging to another citizen.",
        )

    messages_detail = []
    for m in conv.messages:
        m_dict = m.to_dict()
        messages_detail.append(
            MessageDetail(
                id=m.id,
                role=m.role,
                original_text=m.original_text,
                response_text=m.response_text,
                language=m.language,
                sources=m_dict.get("sources", []),
                retrieval_status=m.retrieval_status,
                created_at=m_dict.get("created_at"),
            )
        )

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        language=conv.language,
        messages=messages_detail,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
    )


@router.delete("/conversations/{conversation_id}", summary="Delete conversation thread")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes conversation and associated messages.
    Enforces user ownership.
    """
    conv = (
        db.query(ChatbotConversation)
        .filter(ChatbotConversation.id == conversation_id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.user_id != current_user.id and current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You cannot delete conversations belonging to another citizen.",
        )

    db.delete(conv)
    db.commit()
    return {"status": "SUCCESS", "message": f"Conversation #{conversation_id} deleted successfully."}
