import os
import json
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chatbot import ChatbotDocument, ChatbotChunk
from app.chatbot.embedding_service import get_embedding_provider

logger = logging.getLogger(__name__)


class FAISSRetrievalService:
    """
    Real FAISS vector retrieval service using normalized Inner Product (cosine similarity).
    Maintains persistent index file and metadata mapping JSON.
    Supports atomic rebuilding with rollback preservation.
    """

    _instance = None
    _lock = threading.RLock()  # RLock allows re-entrant acquisition from same thread

    def __init__(self):
        self.kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
        self.indexes_dir = self.kb_dir / "indexes"
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.indexes_dir / "civic_faiss.index"
        self.meta_path = self.indexes_dir / "civic_index_meta.json"
        self.dimension = settings.EMBEDDING_DIMENSION

        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata_map: List[Dict[str, Any]] = []
        self._load_or_create_index()

    @classmethod
    def get_instance(cls) -> "FAISSRetrievalService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _load_or_create_index(self):
        with self._lock:
            if self.index_path.exists() and self.meta_path.exists():
                try:
                    logger.info("Loading existing FAISS index from %s", self.index_path)
                    self.index = faiss.read_index(str(self.index_path))
                    with open(self.meta_path, "r", encoding="utf-8") as f:
                        self.metadata_map = json.load(f)
                    logger.info("Loaded FAISS index with %d vectors", self.index.ntotal)
                    return
                except Exception as exc:
                    logger.error("Failed to load existing FAISS index, reinitializing: %s", exc)

            # Create fresh empty index
            logger.info("Initializing new empty FAISS IndexFlatIP (dim=%d)", self.dimension)
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata_map = []
            self._save_index_unlocked()

    def _save_index_unlocked(self):
        """Saves index and metadata to disk."""
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata_map, f, indent=2, ensure_ascii=False)

    def add_vectors(self, vectors: np.ndarray, metadatas: List[Dict[str, Any]]):
        """
        Adds vectors and their matching metadata to the live index.
        """
        if len(vectors) == 0:
            return

        with self._lock:
            if vectors.shape[1] != self.dimension:
                raise ValueError(f"Vector dimension mismatch: expected {self.dimension}, got {vectors.shape[1]}")

            # Ensure float32 and L2-normalized
            vecs = vectors.astype(np.float32)
            faiss.normalize_L2(vecs)

            start_idx = self.index.ntotal
            self.index.add(vecs)

            for i, meta in enumerate(metadatas):
                meta_copy = dict(meta)
                meta_copy["vector_index_id"] = start_idx + i
                self.metadata_map.append(meta_copy)

            self._save_index_unlocked()
            logger.info("Added %d vectors to FAISS index. Total: %d", len(vectors), self.index.ntotal)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 4,
        min_similarity: float = 0.35,
    ) -> List[Dict[str, Any]]:
        """
        Searches FAISS for most similar chunks using cosine similarity (inner product on normalized vectors).
        Returns deduplicated chunks passing the similarity threshold.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # Ensure 2D float32 normalized vector
        q_vec = query_vector.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(q_vec)

        search_k = min(top_k * 3, self.index.ntotal)
        with self._lock:
            distances, indices = self.index.search(q_vec, search_k)

        results: List[Dict[str, Any]] = []
        seen_texts = set()

        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata_map):
                continue
            sim_score = float(score)
            if sim_score < min_similarity:
                continue

            meta = self.metadata_map[idx]
            text_snippet = meta.get("text", "").strip()
            # Deduplicate nearly identical snippets
            norm_snippet = text_snippet[:100].lower()
            if norm_snippet in seen_texts:
                continue
            seen_texts.add(norm_snippet)

            res = dict(meta)
            res["similarity"] = round(sim_score, 4)
            results.append(res)
            if len(results) >= top_k:
                break

        return results

    def rebuild_index(self, db: Session) -> Dict[str, Any]:
        """
        Rebuilds the FAISS vector index from scratch using all READY documents in PostgreSQL.
        Employs atomic replacement: if rebuild fails, the existing working index is preserved.
        """
        logger.info("Starting atomic FAISS vector index rebuild from PostgreSQL...")
        ready_docs = (
            db.query(ChatbotDocument)
            .filter(ChatbotDocument.status == "READY")
            .all()
        )

        all_chunks: List[ChatbotChunk] = []
        for doc in ready_docs:
            all_chunks.extend(doc.chunks)

        if not all_chunks:
            logger.warning("No READY chunks found in database. Initializing empty index.")
            with self._lock:
                self.index = faiss.IndexFlatIP(self.dimension)
                self.metadata_map = []
                self._save_index_unlocked()
            return {"status": "SUCCESS", "vector_count": 0, "document_count": len(ready_docs)}

        texts = [c.text for c in all_chunks]
        provider = get_embedding_provider()
        if not provider.is_available:
            raise RuntimeError("Embedding provider is unavailable; cannot rebuild vector index.")

        # Embed all chunks
        logger.info("Generating embeddings for %d chunks...", len(texts))
        raw_embeddings = provider.embed_documents(texts)
        if raw_embeddings.shape[0] != len(all_chunks):
            raise RuntimeError(f"Embedding count mismatch: expected {len(all_chunks)}, got {raw_embeddings.shape[0]}")

        # Build fresh temporary index
        temp_index = faiss.IndexFlatIP(self.dimension)
        vecs = raw_embeddings.astype(np.float32)
        faiss.normalize_L2(vecs)
        temp_index.add(vecs)

        new_meta = []
        for i, chunk in enumerate(all_chunks):
            doc = chunk.document
            chunk.vector_index_id = i
            new_meta.append({
                "chunk_id": chunk.chunk_id,
                "document_id": doc.document_id,
                "title": doc.title,
                "source": doc.source,
                "source_url": doc.source_url,
                "department": doc.department,
                "page": chunk.page_number,
                "section": chunk.section,
                "text": chunk.text,
                "vector_index_id": i,
            })

        db.commit()

        # Atomic file write
        temp_idx_path = self.indexes_dir / "civic_faiss.index.tmp"
        temp_meta_path = self.indexes_dir / "civic_index_meta.json.tmp"

        faiss.write_index(temp_index, str(temp_idx_path))
        with open(temp_meta_path, "w", encoding="utf-8") as f:
            json.dump(new_meta, f, indent=2, ensure_ascii=False)

        # Atomic replacement in-memory and on disk
        with self._lock:
            if temp_idx_path.exists():
                temp_idx_path.replace(self.index_path)
            if temp_meta_path.exists():
                temp_meta_path.replace(self.meta_path)
            self.index = temp_index
            self.metadata_map = new_meta

        logger.info("Atomic rebuild complete. Total vectors in index: %d", self.index.ntotal)
        return {
            "status": "SUCCESS",
            "vector_count": self.index.ntotal,
            "document_count": len(ready_docs),
            "chunk_count": len(all_chunks),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Returns live statistics about the FAISS index."""
        ntotal = self.index.ntotal if self.index else 0
        file_size = self.index_path.stat().st_size if self.index_path.exists() else 0
        mtime = self.index_path.stat().st_mtime if self.index_path.exists() else None
        iso_mtime = None
        if mtime:
            from datetime import datetime, timezone
            iso_mtime = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        return {
            "status": "READY" if ntotal > 0 else "EMPTY",
            "vector_count": ntotal,
            "dimension": self.dimension,
            "index_file_size_bytes": file_size,
            "last_modified": iso_mtime,
        }


def get_retrieval_service() -> FAISSRetrievalService:
    return FAISSRetrievalService.get_instance()
