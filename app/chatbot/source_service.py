from typing import List, Dict, Any
from app.chatbot.schemas import SourceReference


class SourceFormattingService:
    """
    Sanitizes and formats source references for citizen and officer UI display.
    Guarantees internal server filesystem paths and server secrets are never exposed.
    """

    @staticmethod
    def format_sources(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for c in chunks:
            raw_url = c.get("source_url")
            # Only include URL if valid http/https
            valid_url = raw_url if raw_url and (raw_url.startswith("http://") or raw_url.startswith("https://")) else None

            item = {
                "document_id": c.get("document_id", "DOC-CIVIC"),
                "title": c.get("title", "Official Municipal Standard"),
                "page": int(c.get("page", 1)),
                "section": c.get("section") or "General",
                "source": c.get("source", "Municipal Corporation"),
                "url": valid_url,
                "similarity": float(c.get("similarity", 0.0)),
                "department": c.get("department"),
            }
            formatted.append(item)
        return formatted


_source_service = None

def get_source_service() -> SourceFormattingService:
    global _source_service
    if _source_service is None:
        _source_service = SourceFormattingService()
    return _source_service
