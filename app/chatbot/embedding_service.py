import os
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


def _set_hf_offline_if_cached(model_name: str) -> None:
    """
    Sets HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE env vars if the model is already
    cached locally. This avoids the long HuggingFace Hub connectivity check / timeout
    that blocks model initialization when running without network or with slow HF Hub access.
    """
    try:
        # Determine HF cache directory (default: ~/.cache/huggingface/hub)
        hf_cache = Path(
            os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
        ) / "hub"
        # Convert model_name to hub directory convention (replace / with --)
        hub_dir_name = "models--" + model_name.replace("/", "--")
        cached = (hf_cache / hub_dir_name).exists()
        if cached:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            logger.info(
                "Model '%s' found in local HF cache. Setting HF_HUB_OFFLINE=1 "
                "to skip hub connectivity check.",
                model_name,
            )
        else:
            logger.info(
                "Model '%s' not yet cached; will attempt HuggingFace Hub download.",
                model_name,
            )
    except Exception as exc:
        logger.warning("Could not check HF cache: %s", exc)

_set_hf_offline_if_cached(settings.EMBEDDING_MODEL_NAME)


class BaseEmbeddingProvider:
    """Abstract interface for embedding providers."""

    def embed_query(self, text: str) -> np.ndarray:
        raise NotImplementedError

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:
        raise NotImplementedError


class SentenceTransformerEmbeddingProvider(BaseEmbeddingProvider):
    """
    Real multilingual embedding provider using SentenceTransformers.
    Supports English, Tamil, Hindi, and 50+ other languages.
    Produces 384-dimensional dense vectors normalized to unit length (L2).
    """

    _instance = None
    _lock = threading.RLock()  # RLock to prevent re-entrancy deadlocks

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self.model = None
        self._is_available = False
        self._init_error = None
        self._initialize()

    def _initialize(self):
        try:
            _set_hf_offline_if_cached(self.model_name)
            from sentence_transformers import SentenceTransformer
            logger.info("Loading multilingual embedding model: %s", self.model_name)
            self.model = SentenceTransformer(self.model_name)
            self._is_available = True
            logger.info("Multilingual embedding model loaded successfully. Dimension: %d", self.dimension)
        except Exception as exc:
            self._is_available = False
            self._init_error = str(exc)
            logger.error("Failed to load SentenceTransformer model %s: %s", self.model_name, exc)

    @classmethod
    def get_instance(cls) -> "SentenceTransformerEmbeddingProvider":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_available(self) -> bool:
        return self._is_available and self.model is not None

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embeds a single user query string into a 1D normalized float32 vector (shape: [dimension]).
        """
        if not self.is_available:
            raise RuntimeError(f"Embedding provider unavailable: {self._init_error}")

        raw_vec = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        return raw_vec[0].astype(np.float32)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Embeds a list of document chunk strings into a 2D normalized float32 matrix (shape: [N, dimension]).
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        if not self.is_available:
            raise RuntimeError(f"Embedding provider unavailable: {self._init_error}")

        raw_matrix = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32)
        return raw_matrix.astype(np.float32)

    def status(self) -> Dict[str, Any]:
        return {
            "status": "AVAILABLE" if self.is_available else "UNAVAILABLE",
            "model_name": self.model_name,
            "dimension": self.dimension,
            "error": self._init_error,
        }


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory returning the configured singleton embedding provider."""
    return SentenceTransformerEmbeddingProvider.get_instance()
