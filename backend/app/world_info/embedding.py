from __future__ import annotations

from typing import List

from ..config import Config
from .exceptions import WorldInfoDependencyError


class EmbeddingService:
    _model = None

    def __init__(self) -> None:
        self.model_name = Config.EMBEDDING_MODEL_NAME
        self.batch_size = Config.EMBEDDING_BATCH_SIZE

    @classmethod
    def _load_model(cls):
        if cls._model is not None:
            return cls._model
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise WorldInfoDependencyError("sentence-transformers is not installed") from exc
        cls._model = SentenceTransformer(Config.EMBEDDING_MODEL_NAME)
        return cls._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [embedding.tolist() for embedding in embeddings]
