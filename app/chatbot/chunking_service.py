import re
from typing import List, Dict, Any, Optional
from app.core.config import settings


class DocumentChunker:
    """
    Deterministic document chunking engine preserving section context,
    page numbers, and boundary awareness.
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP

    def chunk_document(
        self,
        document_id: str,
        text: str,
        page_number: int = 1,
        default_section: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Splits text into deterministic, overlapping chunks respecting paragraphs and headings.
        """
        if not text or not text.strip():
            return []

        # Detect section headings if present (Markdown # or ##, or numbered lines)
        sections = self._split_by_sections(text, default_section)

        all_chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        for section_title, section_text in sections:
            paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
            if not paragraphs:
                continue

            current_chunk_text = ""
            for para in paragraphs:
                if len(para) > self.chunk_size:
                    # Break large paragraph into sentence-level chunks
                    sub_sentences = re.split(r"(?<=[.!?\n])\s+", para)
                    for sent in sub_sentences:
                        if not sent.strip():
                            continue
                        if len(current_chunk_text) + len(sent) + 1 <= self.chunk_size:
                            current_chunk_text = f"{current_chunk_text} {sent}".strip()
                        else:
                            if current_chunk_text:
                                all_chunks.append({
                                    "chunk_id": f"{document_id}_chunk_{chunk_idx}",
                                    "chunk_index": chunk_idx,
                                    "page_number": page_number,
                                    "section": section_title,
                                    "text": current_chunk_text,
                                    "token_count": len(current_chunk_text.split()),
                                })
                                chunk_idx += 1
                                # Overlap: carry tail
                                overlap_len = min(self.chunk_overlap, len(current_chunk_text))
                                current_chunk_text = current_chunk_text[-overlap_len:] + " " + sent
                            else:
                                current_chunk_text = sent
                else:
                    if len(current_chunk_text) + len(para) + 2 <= self.chunk_size:
                        current_chunk_text = f"{current_chunk_text}\n\n{para}".strip()
                    else:
                        if current_chunk_text:
                            all_chunks.append({
                                "chunk_id": f"{document_id}_chunk_{chunk_idx}",
                                "chunk_index": chunk_idx,
                                "page_number": page_number,
                                "section": section_title,
                                "text": current_chunk_text,
                                "token_count": len(current_chunk_text.split()),
                            })
                            chunk_idx += 1
                            overlap_len = min(self.chunk_overlap, len(current_chunk_text))
                            current_chunk_text = current_chunk_text[-overlap_len:] + "\n\n" + para
                        else:
                            current_chunk_text = para

            if current_chunk_text.strip():
                all_chunks.append({
                    "chunk_id": f"{document_id}_chunk_{chunk_idx}",
                    "chunk_index": chunk_idx,
                    "page_number": page_number,
                    "section": section_title,
                    "text": current_chunk_text.strip(),
                    "token_count": len(current_chunk_text.split()),
                })
                chunk_idx += 1

        return all_chunks

    def _split_by_sections(self, text: str, default_section: Optional[str]) -> List[tuple]:
        """
        Parses text for section titles like '# Section', '## Section', 'Section X:', or numbers.
        """
        lines = text.splitlines()
        sections = []
        current_title = default_section or "General"
        current_body = []

        header_pattern = re.compile(r"^(?:#{1,3}\s+(.+)|([0-9]+\.\s+[A-Z0-9\s—–-]+)|Section\s+[0-9]+:?\s*(.*))$", re.IGNORECASE)

        for line in lines:
            stripped = line.strip()
            match = header_pattern.match(stripped)
            if match and len(stripped) < 120:
                if current_body:
                    sections.append((current_title, "\n".join(current_body)))
                    current_body = []
                extracted_title = match.group(1) or match.group(2) or match.group(3) or stripped
                current_title = extracted_title.strip()
            else:
                current_body.append(line)

        if current_body:
            sections.append((current_title, "\n".join(current_body)))

        return sections if sections else [(default_section or "General", text)]
