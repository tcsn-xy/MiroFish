from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .embedding import EmbeddingService
from .repository import WorldInfoRepository
from .types import WorldInfoChunk
from .utils import (
    chunk_preview,
    compute_content_hash,
    normalize_text,
    parse_datetime,
    split_text,
    trim_results_by_budget,
)
from .vector_store import ChromaWorldInfoStore

logger = get_logger("mirofish.world_info.service")


class WorldInfoService:
    def __init__(
        self,
        repository: Optional[WorldInfoRepository] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[ChromaWorldInfoStore] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.repository = repository or WorldInfoRepository()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or ChromaWorldInfoStore()
        self._llm_client = llm_client

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _summarize(self, title: Optional[str], content: str) -> str:
        system_prompt = (
            "你是信息整理助手。请为输入的世界信息生成一段客观、简洁的中文摘要。"
            "只概括事实，不添加外部信息。"
        )
        title_part = f"标题：{title}\n" if title else ""
        prompt = f"{title_part}正文：\n{content[:12000]}"
        summary = self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        if not summary or not summary.strip():
            raise ValueError("LLM summary returned empty content")
        return summary.strip()

    def ingest(
        self,
        project_id: str,
        content: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        source_type: Optional[str] = None,
        published_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not Config.WORLD_INFO_ENABLED:
            raise ValueError("world info is disabled")

        normalized = normalize_text(content or "")
        if not normalized:
            raise ValueError("content is required")

        metadata = metadata or {}
        published_dt = parse_datetime(published_at)
        content_hash = compute_content_hash(normalized)

        with self.repository.session() as conn:
            existing = self.repository.get_item_by_hash(conn, project_id, content_hash)
            if existing:
                self.repository.update_existing_item_metadata(
                    conn=conn,
                    item_id=existing.id,
                    title=title or existing.title,
                    source=source or existing.source,
                    source_type=source_type or existing.source_type,
                    published_at=published_dt or existing.published_at,
                    metadata={**existing.metadata_json, **metadata},
                )
                chunks = self.repository.get_chunks_by_item(conn, existing.id)
                return {
                    "item_id": existing.id,
                    "existed": True,
                    "items_count": 1,
                    "chunks_count": len(chunks),
                    "content_hash": content_hash,
                }

        # Strict policy: summarize before any storage write.
        summary = self._summarize(title, normalized)
        text_chunks = split_text(normalized, Config.WORLD_INFO_CHUNK_SIZE, Config.WORLD_INFO_CHUNK_OVERLAP)
        if not text_chunks:
            raise ValueError("content produced no chunks")

        item_id: Optional[int] = None
        chroma_ids: List[str] = []

        try:
            with self.repository.session() as conn:
                item_id = self.repository.create_item(
                    conn=conn,
                    project_id=project_id,
                    title=title,
                    source=source,
                    source_type=source_type,
                    raw_content=normalized,
                    summary=summary,
                    published_at=published_dt,
                    content_hash=content_hash,
                    metadata=metadata,
                )

                chroma_ids = [f"world_info:{project_id}:{item_id}:{i}" for i in range(len(text_chunks))]
                embeddings = self.embedding_service.embed(text_chunks)
                metadatas = [
                    {
                        "project_id": project_id,
                        "item_id": item_id,
                        "chunk_index": i,
                        "title": title or "",
                        "source": source or "",
                        "published_at": published_at or "",
                    }
                    for i in range(len(text_chunks))
                ]

                self.vector_store.upsert_chunks(
                    ids=chroma_ids,
                    documents=text_chunks,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )

                chunk_rows = [
                    {
                        "chunk_index": i,
                        "chunk_text": chunk,
                        "chunk_summary": chunk_preview(chunk),
                        "chroma_doc_id": chroma_ids[i],
                    }
                    for i, chunk in enumerate(text_chunks)
                ]
                self.repository.create_chunks(conn, item_id, project_id, chunk_rows)

            return {
                "item_id": item_id,
                "existed": False,
                "items_count": 1,
                "chunks_count": len(text_chunks),
                "content_hash": content_hash,
            }
        except Exception:
            logger.exception("world info ingest failed; attempting compensation cleanup")
            try:
                if chroma_ids:
                    self.vector_store.delete_by_ids(chroma_ids)
            except Exception:
                logger.exception("failed to compensate chroma world info records")
            if item_id is not None:
                try:
                    with self.repository.session() as conn:
                        self.repository.delete_item(conn, item_id)
                except Exception:
                    logger.exception("failed to compensate mysql world info records")
            raise

    def search(self, project_id: str, query: str, top_k: Optional[int] = None) -> List[WorldInfoChunk]:
        if not Config.WORLD_INFO_ENABLED:
            return []
        clean_query = normalize_text(query or "")
        if not clean_query:
            return []
        top_k = top_k or Config.WORLD_INFO_SEARCH_TOP_K
        query_embedding = self.embedding_service.embed([clean_query])[0]
        chroma_result = self.vector_store.search(query_embedding, project_id, top_k)

        ids = (chroma_result.get("ids") or [[]])[0]
        distances = (chroma_result.get("distances") or [[]])[0]
        metadatas = (chroma_result.get("metadatas") or [[]])[0]
        if not ids:
            return []

        with self.repository.session() as conn:
            chunks_by_doc_id = self.repository.get_chunks_by_chroma_doc_ids(conn, ids)

        ordered: List[WorldInfoChunk] = []
        for idx, doc_id in enumerate(ids):
            chunk = chunks_by_doc_id.get(doc_id)
            if not chunk:
                continue
            distance = distances[idx] if idx < len(distances) else None
            chunk.score = 1 - float(distance) if distance is not None else 0.0
            chunk.metadata = {**chunk.metadata, **(metadatas[idx] or {})}
            ordered.append(chunk)
        return ordered

    def list_items(self, project_id: str, page: int, page_size: int) -> Dict[str, Any]:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        with self.repository.session() as conn:
            items, total = self.repository.list_items(conn, project_id, page, page_size)
        return {
            "items": [item.to_dict() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def stats(self, project_id: str) -> Dict[str, Any]:
        with self.repository.session() as conn:
            return self.repository.get_stats(conn, project_id)

    def build_context_text(
        self,
        project_id: str,
        query: str,
        top_k: Optional[int] = None,
        budget_chars: Optional[int] = None,
        heading: str = "世界信息记忆",
    ) -> str:
        budget_chars = budget_chars if budget_chars is not None else Config.WORLD_INFO_INJECTION_CHARS
        hits = self.search(project_id, query, top_k=top_k)
        if not hits:
            return ""

        by_item_count = defaultdict(int)
        blocks: List[str] = []
        for hit in hits:
            if by_item_count[hit.item_id] >= 2:
                continue
            by_item_count[hit.item_id] += 1
            source = hit.source or "未知来源"
            title = hit.title or f"World Info #{hit.item_id}"
            published = hit.published_at.isoformat() if hit.published_at else "未知时间"
            score = f"{hit.score:.4f}" if hit.score is not None else "n/a"
            blocks.append(
                "\n".join(
                    [
                        f"- 标题: {title}",
                        f"  来源: {source}",
                        f"  发布时间: {published}",
                        f"  命中分数: {score}",
                        f"  片段: {hit.chunk_text}",
                    ]
                )
            )

        selected = trim_results_by_budget(blocks, max(budget_chars - len(heading) - 10, 0))
        if not selected:
            return ""
        return f"## {heading}\n" + "\n\n".join(selected)


_world_info_service: Optional[WorldInfoService] = None


def get_world_info_service() -> WorldInfoService:
    global _world_info_service
    if _world_info_service is None:
        _world_info_service = WorldInfoService()
    return _world_info_service
