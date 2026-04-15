from __future__ import annotations

from typing import Any, Dict, List

from ..config import Config
from .exceptions import WorldInfoDependencyError


class ChromaWorldInfoStore:
    _client = None
    _collection = None

    @classmethod
    def _get_collection(cls):
        if cls._collection is not None:
            return cls._collection
        try:
            import chromadb
            from chromadb.config import Settings
        except ModuleNotFoundError as exc:
            raise WorldInfoDependencyError("chromadb is not installed") from exc

        if Config.CHROMA_MODE == "persistent":
            cls._client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIRECTORY)
        else:
            cls._client = chromadb.HttpClient(host=Config.CHROMA_HOST, port=Config.CHROMA_PORT)
        cls._collection = cls._client.get_or_create_collection(name=Config.CHROMA_COLLECTION_NAME)
        return cls._collection

    def upsert_chunks(
        self,
        ids: List[str],
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        collection = self._get_collection()
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def delete_by_ids(self, ids: List[str]) -> None:
        if not ids:
            return
        collection = self._get_collection()
        collection.delete(ids=ids)

    def search(
        self,
        query_embedding: List[float],
        project_id: str,
        top_k: int,
    ) -> Dict[str, List[Any]]:
        collection = self._get_collection()
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"project_id": project_id},
        )
