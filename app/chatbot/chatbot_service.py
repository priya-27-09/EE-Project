import json
import logging
import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chatbot import ChatbotConversation, ChatbotMessage
from app.chatbot.schemas import ChatResponse, SourceReference
from app.chatbot.embedding_service import get_embedding_provider
from app.chatbot.retrieval_service import get_retrieval_service
from app.chatbot.generation_service import get_generation_provider, FALLBACK_MESSAGES
from app.chatbot.source_service import get_source_service

logger = logging.getLogger(__name__)

# Security patterns preventing prompt injection, secret exfiltration, or system inspection
SENSITIVE_PATTERNS = [
    # Catches .env, jwt_secret, private_key, database_url, db_password, system_prompt in any message
    # Use (?<!\w) instead of \b before dot since \b doesn't work before non-word chars like .
    re.compile(r"(?<!\w)\.env\b|(?<!\w)\.env(?!\w)", re.IGNORECASE),
    re.compile(r"\b(jwt_secret|private_key|database_url|db_password|system_prompt)\b", re.IGNORECASE),
    # Catches: "show/reveal/display/dump all keys/secrets/passwords/credentials"
    re.compile(r"\b(show|reveal|display|dump|print)\s+(me\s+)?(all\s+)?(keys|secrets|passwords|credentials|prompts)\b", re.IGNORECASE),
    # Catches: "ignore all previous/prior instructions"
    re.compile(r"\b(ignore)\s+(all\s+)?(previous|prior)\s+(instructions|prompts|rules)\b", re.IGNORECASE),
]


class ChatbotService:
    """
    Core RAG chatbot orchestrator connecting question normalization,
    vector embedding, FAISS similarity search, answer generation, and persistence.
    """

    def __init__(self):
        self.embedding_provider = get_embedding_provider()
        self.retrieval_service = get_retrieval_service()
        self.generation_provider = get_generation_provider()
        self.source_service = get_source_service()

    def process_chat(
        self,
        db: Session,
        user_id: int,
        message: str,
        language: str = "en",
        conversation_id: Optional[int] = None,
    ) -> ChatResponse:
        """
        Executes end-to-end RAG pipeline for a user message.
        """
        lang = (language or "en").lower().strip()
        if lang not in ("en", "ta", "hi"):
            lang = "en"

        cleaned_msg = message.strip()

        # 1. Security & Prompt Injection Protection
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(cleaned_msg):
                logger.warning("Security alert: Blocked sensitive request pattern from user %d: %s", user_id, cleaned_msg)
                sec_msg = {
                    "en": "For security reasons, queries requesting internal system prompts, configuration parameters, or credential secrets are strictly prohibited.",
                    "ta": "பாதுகாப்பு காரணங்களுக்காக, கணினி அமைப்புகள் அல்லது ரகசியங்களை கோரும் கேள்விகள் கண்டிப்பாக தடைசெய்யப்பட்டுள்ளன.",
                    "hi": "सुरक्षा कारणों से, आंतरिक सिस्टम प्रॉम्प्ट या क्रेडेंशियल मांगने वाले प्रश्न सख्त वर्जित हैं।",
                }.get(lang, "Queries requesting internal system parameters or credentials are prohibited.")

                conv = self._get_or_create_conversation(db, user_id, conversation_id, lang, cleaned_msg)
                # Sanitize the stored query text to avoid persisting sensitive keyword patterns in the DB.
                # We replace the matched sensitive tokens with [REDACTED] so the record is auditable
                # but does not contain the literal credential names.
                sanitized_msg = cleaned_msg
                for pat in SENSITIVE_PATTERNS:
                    sanitized_msg = pat.sub("[REDACTED]", sanitized_msg)
                self._record_message_turn(db, conv.id, sanitized_msg, sec_msg, lang, [], "BLOCKED")
                return ChatResponse(
                    answer=sec_msg,
                    language=lang,
                    conversation_id=conv.id,
                    sources=[],
                    retrieval_status="FAILED",
                )

        # 2. Get or create conversation thread (enforcing IDOR isolation)
        conversation = self._get_or_create_conversation(db, user_id, conversation_id, lang, cleaned_msg)

        # 3. Check embedding provider availability
        if not self.embedding_provider.is_available:
            logger.error("Embedding provider is unavailable during chat execution.")
            unavail_msg = {
                "en": "The civic knowledge base embedding service is currently initializing or unavailable. Please try again shortly or contact your municipal ward office.",
                "ta": "நகராட்சி அறிவுத்தள சேவை தற்போது தொடங்குகிறது அல்லது கிடைக்கவில்லை. சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.",
                "hi": "नागरिक ज्ञानकोश सेवा वर्तमान में उपलब्ध नहीं है। कृपया थोड़ी देर बाद पुनः प्रयास करें।",
            }.get(lang, FALLBACK_MESSAGES["en"])

            self._record_message_turn(db, conversation.id, cleaned_msg, unavail_msg, lang, [], "NOT_CONFIGURED")
            return ChatResponse(
                answer=unavail_msg,
                language=lang,
                conversation_id=conversation.id,
                sources=[],
                retrieval_status="NOT_CONFIGURED",
            )

        # 4. Generate query embedding and retrieve matching chunks from FAISS
        try:
            query_vector = self.embedding_provider.embed_query(cleaned_msg)
            raw_chunks = self.retrieval_service.search(
                query_vector=query_vector,
                top_k=settings.RAG_TOP_K,
                min_similarity=settings.RAG_MIN_SIMILARITY,
            )
        except Exception as exc:
            logger.error("Error during vector search: %s", exc)
            raw_chunks = []

        # 5. Format sources
        formatted_sources = self.source_service.format_sources(raw_chunks)
        retrieval_status = "SUCCESS" if formatted_sources else "NO_RELEVANT_CONTEXT"

        # 6. Generate grounded answer
        answer = self.generation_provider.generate_answer(cleaned_msg, raw_chunks, language=lang)

        # 7. Persist message turn in PostgreSQL
        self._record_message_turn(
            db=db,
            conversation_id=conversation.id,
            user_text=cleaned_msg,
            assistant_text=answer,
            language=lang,
            sources=formatted_sources,
            status=retrieval_status,
        )

        pydantic_sources = [
            SourceReference(
                document_id=s["document_id"],
                title=s["title"],
                page=s["page"],
                section=s.get("section"),
                source=s["source"],
                url=s.get("url"),
                similarity=s["similarity"],
            )
            for s in formatted_sources
        ]

        return ChatResponse(
            answer=answer,
            language=lang,
            conversation_id=conversation.id,
            sources=pydantic_sources,
            retrieval_status=retrieval_status,
        )

    def _get_or_create_conversation(
        self,
        db: Session,
        user_id: int,
        conversation_id: Optional[int],
        language: str,
        first_message: str,
    ) -> ChatbotConversation:
        """
        Retrieves existing conversation belonging strictly to user_id,
        or creates a new conversation thread.
        """
        if conversation_id:
            conv = (
                db.query(ChatbotConversation)
                .filter(ChatbotConversation.id == conversation_id, ChatbotConversation.user_id == user_id)
                .first()
            )
            if conv:
                conv.language = language
                db.commit()
                return conv

        # Generate descriptive title from first 6 words of first message
        words = first_message.split()[:6]
        title = " ".join(words) if words else "Civic Inquiry"
        if len(title) > 60:
            title = title[:57] + "..."

        new_conv = ChatbotConversation(
            user_id=user_id,
            language=language,
            title=title,
        )
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        return new_conv

    def _record_message_turn(
        self,
        db: Session,
        conversation_id: int,
        user_text: str,
        assistant_text: str,
        language: str,
        sources: list,
        status: str,
    ):
        """
        Saves user inquiry and assistant response turn into PostgreSQL.
        """
        # User message
        u_msg = ChatbotMessage(
            conversation_id=conversation_id,
            role="user",
            original_text=user_text,
            language=language,
            retrieval_status=status,
        )
        db.add(u_msg)

        # Assistant response
        a_msg = ChatbotMessage(
            conversation_id=conversation_id,
            role="assistant",
            original_text=user_text,
            response_text=assistant_text,
            language=language,
            retrieved_chunks=json.dumps(sources, ensure_ascii=False) if sources else None,
            retrieval_status=status,
        )
        db.add(a_msg)
        db.commit()


_chatbot_service = None

def get_chatbot_service() -> ChatbotService:
    global _chatbot_service
    if _chatbot_service is None:
        _chatbot_service = ChatbotService()
    return _chatbot_service
