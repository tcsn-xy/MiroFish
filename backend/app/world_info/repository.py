from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger
from .exceptions import WorldInfoDependencyError, WorldInfoStorageError
from .types import WorldInfoChunk, WorldInfoItem
from .utils import load_metadata, serialize_metadata

logger = get_logger("mirofish.world_info.repository")


class WorldInfoRepository:
    def __init__(self) -> None:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ModuleNotFoundError as exc:
            raise WorldInfoDependencyError("pymysql is not installed") from exc

        self._pymysql = pymysql
        self._dict_cursor = DictCursor

    def _connect(self):
        kwargs = Config.get_mysql_config()
        kwargs["cursorclass"] = self._dict_cursor
        return self._pymysql.connect(**kwargs)

    @contextmanager
    def session(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_tables_exist(self, conn) -> None:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM world_info_items LIMIT 1")
                cursor.execute("SELECT 1 FROM world_info_chunks LIMIT 1")
        except Exception as exc:
            raise WorldInfoStorageError(
                "world info tables are missing. Execute backend/sql/world_info_schema.sql first."
            ) from exc

    def _row_to_item(self, row: Dict[str, Any]) -> WorldInfoItem:
        return WorldInfoItem(
            id=row["id"],
            project_id=row["project_id"],
            title=row.get("title"),
            source=row.get("source"),
            source_type=row.get("source_type"),
            raw_content=row["raw_content"],
            summary=row["summary"],
            published_at=row.get("published_at"),
            content_hash=row["content_hash"],
            metadata_json=load_metadata(row.get("metadata_json")),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _row_to_chunk(self, row: Dict[str, Any]) -> WorldInfoChunk:
        return WorldInfoChunk(
            id=row["id"],
            item_id=row["item_id"],
            project_id=row["project_id"],
            chunk_index=row["chunk_index"],
            chunk_text=row["chunk_text"],
            chunk_summary=row["chunk_summary"],
            chroma_doc_id=row["chroma_doc_id"],
            created_at=row.get("created_at"),
        )

    def get_item_by_hash(self, conn, project_id: str, content_hash: str) -> Optional[WorldInfoItem]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM world_info_items
                WHERE project_id=%s AND content_hash=%s
                LIMIT 1
                """,
                (project_id, content_hash),
            )
            row = cursor.fetchone()
            return self._row_to_item(row) if row else None

    def update_existing_item_metadata(
        self,
        conn,
        item_id: int,
        title: Optional[str],
        source: Optional[str],
        source_type: Optional[str],
        published_at: Optional[datetime],
        metadata: Dict[str, Any],
    ) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE world_info_items
                SET title=%s,
                    source=%s,
                    source_type=%s,
                    published_at=%s,
                    metadata_json=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (title, source, source_type, published_at, serialize_metadata(metadata), item_id),
            )

    def create_item(
        self,
        conn,
        project_id: str,
        title: Optional[str],
        source: Optional[str],
        source_type: Optional[str],
        raw_content: str,
        summary: str,
        published_at: Optional[datetime],
        content_hash: str,
        metadata: Dict[str, Any],
    ) -> int:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO world_info_items
                (project_id, title, source, source_type, raw_content, summary, published_at, content_hash, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    title,
                    source,
                    source_type,
                    raw_content,
                    summary,
                    published_at,
                    content_hash,
                    serialize_metadata(metadata),
                ),
            )
            return int(cursor.lastrowid)

    def create_chunks(self, conn, item_id: int, project_id: str, chunks: List[Dict[str, Any]]) -> List[int]:
        chunk_ids: List[int] = []
        with conn.cursor() as cursor:
            for chunk in chunks:
                cursor.execute(
                    """
                    INSERT INTO world_info_chunks
                    (item_id, project_id, chunk_index, chunk_text, chunk_summary, chroma_doc_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        item_id,
                        project_id,
                        chunk["chunk_index"],
                        chunk["chunk_text"],
                        chunk["chunk_summary"],
                        chunk["chroma_doc_id"],
                    ),
                )
                chunk_ids.append(int(cursor.lastrowid))
        return chunk_ids

    def delete_chunks_by_item(self, conn, item_id: int) -> None:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM world_info_chunks WHERE item_id=%s", (item_id,))

    def delete_item(self, conn, item_id: int) -> None:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM world_info_items WHERE id=%s", (item_id,))

    def get_item(self, conn, item_id: int) -> Optional[WorldInfoItem]:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM world_info_items WHERE id=%s LIMIT 1", (item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = self._row_to_item(row)
            item.chunks = self.get_chunks_by_item(conn, item_id)
            return item

    def get_chunks_by_item(self, conn, item_id: int) -> List[WorldInfoChunk]:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM world_info_chunks WHERE item_id=%s ORDER BY chunk_index ASC",
                (item_id,),
            )
            return [self._row_to_chunk(row) for row in cursor.fetchall()]

    def list_items(self, conn, project_id: str, page: int, page_size: int) -> Tuple[List[WorldInfoItem], int]:
        self._ensure_tables_exist(conn)
        offset = max(page - 1, 0) * page_size
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM world_info_items WHERE project_id=%s",
                (project_id,),
            )
            total = int(cursor.fetchone()["total"])
            cursor.execute(
                """
                SELECT *
                FROM world_info_items
                WHERE project_id=%s
                ORDER BY updated_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (project_id, page_size, offset),
            )
            items = [self._row_to_item(row) for row in cursor.fetchall()]
            return items, total

    def get_stats(self, conn, project_id: str) -> Dict[str, Any]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS items_count, MAX(updated_at) AS last_updated_at
                FROM world_info_items
                WHERE project_id=%s
                """,
                (project_id,),
            )
            item_stats = cursor.fetchone()
            cursor.execute(
                """
                SELECT COUNT(*) AS chunks_count
                FROM world_info_chunks
                WHERE project_id=%s
                """,
                (project_id,),
            )
            chunk_stats = cursor.fetchone()
        return {
            "project_id": project_id,
            "items_count": int(item_stats["items_count"]),
            "chunks_count": int(chunk_stats["chunks_count"]),
            "last_updated_at": (
                item_stats["last_updated_at"].isoformat() if item_stats["last_updated_at"] else None
            ),
        }

    def get_chunks_by_ids(self, conn, chunk_ids: List[int]) -> Dict[int, WorldInfoChunk]:
        if not chunk_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(chunk_ids))
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.*, i.title, i.source, i.published_at, i.metadata_json
                FROM world_info_chunks c
                JOIN world_info_items i ON i.id = c.item_id
                WHERE c.id IN ({placeholders})
                """,
                chunk_ids,
            )
            rows = cursor.fetchall()
        result: Dict[int, WorldInfoChunk] = {}
        for row in rows:
            chunk = self._row_to_chunk(row)
            chunk.title = row.get("title")
            chunk.source = row.get("source")
            chunk.published_at = row.get("published_at")
            chunk.metadata = load_metadata(row.get("metadata_json"))
            result[chunk.id] = chunk
        return result

    def get_chunks_by_chroma_doc_ids(self, conn, chroma_doc_ids: List[str]) -> Dict[str, WorldInfoChunk]:
        if not chroma_doc_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(chroma_doc_ids))
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT c.*, i.title, i.source, i.published_at, i.metadata_json
                FROM world_info_chunks c
                JOIN world_info_items i ON i.id = c.item_id
                WHERE c.chroma_doc_id IN ({placeholders})
                """,
                chroma_doc_ids,
            )
            rows = cursor.fetchall()
        result: Dict[str, WorldInfoChunk] = {}
        for row in rows:
            chunk = self._row_to_chunk(row)
            chunk.title = row.get("title")
            chunk.source = row.get("source")
            chunk.published_at = row.get("published_at")
            chunk.metadata = load_metadata(row.get("metadata_json"))
            result[chunk.chroma_doc_id] = chunk
        return result
