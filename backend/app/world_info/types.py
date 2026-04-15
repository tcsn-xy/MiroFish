from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WorldInfoChunk:
    id: Optional[int]
    item_id: int
    project_id: str
    chunk_index: int
    chunk_text: str
    chunk_summary: str
    chroma_doc_id: str
    created_at: Optional[datetime] = None
    score: Optional[float] = None
    title: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.id,
            "item_id": self.item_id,
            "project_id": self.project_id,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "chunk_summary": self.chunk_summary,
            "chroma_doc_id": self.chroma_doc_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "score": self.score,
            "title": self.title,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "metadata": self.metadata,
        }


@dataclass
class WorldInfoItem:
    id: int
    project_id: str
    title: Optional[str]
    source: Optional[str]
    source_type: Optional[str]
    raw_content: str
    summary: str
    published_at: Optional[datetime]
    content_hash: str
    metadata_json: Dict[str, Any]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    chunks: List[WorldInfoChunk] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "source": self.source,
            "source_type": self.source_type,
            "raw_content": self.raw_content,
            "summary": self.summary,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "content_hash": self.content_hash,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
        }
