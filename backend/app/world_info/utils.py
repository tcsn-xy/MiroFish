from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def normalize_text(text: str) -> str:
    normalized = text.replace("\ufeff", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be between 0 and chunk_size - 1")
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - chunk_overlap
    return chunks


def chunk_preview(text: str, max_chars: int = 180) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max_chars - 3].rstrip() + "..."


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"Invalid datetime value: {value}")


def serialize_metadata(metadata: Optional[Dict[str, Any]]) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False)


def load_metadata(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        return json.loads(raw)
    return dict(raw)


def trim_results_by_budget(items: Iterable[str], budget_chars: int, separator: str = "\n\n") -> List[str]:
    if budget_chars <= 0:
        return []
    selected: List[str] = []
    total = 0
    for item in items:
        item_len = len(item)
        extra = item_len if not selected else len(separator) + item_len
        if total + extra > budget_chars:
            if not selected:
                selected.append(item[:budget_chars])
            break
        selected.append(item)
        total += extra
    return selected


def format_world_info_hits_text(
    hits: Iterable[Dict[str, Any]],
    heading: str = "世界信息补充",
    budget_chars: Optional[int] = None,
) -> str:
    blocks: List[str] = []
    for index, hit in enumerate(hits, 1):
        title = hit.get("title") or f"World Info #{hit.get('item_id') or index}"
        source = hit.get("source") or "未知来源"
        published_at = hit.get("published_at") or "未知时间"
        score = hit.get("score")
        try:
            score_text = f"{float(score):.4f}" if score is not None else "n/a"
        except (TypeError, ValueError):
            score_text = "n/a"
        snippet = hit.get("chunk_text") or hit.get("chunk_summary") or ""
        blocks.append(
            "\n".join(
                [
                    f"- 标题: {title}",
                    f"  来源: {source}",
                    f"  发布时间: {published_at}",
                    f"  命中分数: {score_text}",
                    f"  片段: {snippet}",
                ]
            )
        )

    if not blocks:
        return ""

    if budget_chars is not None:
        blocks = trim_results_by_budget(blocks, max(budget_chars - len(heading) - 10, 0))
        if not blocks:
            return ""

    return f"\n### {heading}\n" + "\n\n".join(blocks)
