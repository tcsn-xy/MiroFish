"""Consensus QA helpers."""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


def utcnow() -> datetime:
    return datetime.now()


def generate_task_uid() -> str:
    return f"cqa_{int(time.time())}_{uuid.uuid4().hex[:12]}"


def scheduler_should_start(debug: bool) -> bool:
    if not debug:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def normalize_candidate_answer(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"yes", "y"}:
        return "yes"
    if text in {"no", "n"}:
        return "no"
    return None


def truncate_text(value: Any, limit: int = 255, fallback: str = "") -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."


def safe_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def parse_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip() or None


def get_persona_source_id(profile: Dict[str, Any], fallback_index: int) -> str:
    for key in ("user_id", "id", "agent_id", "username"):
        value = profile.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"agent_{fallback_index}"


def get_persona_name(profile: Dict[str, Any], fallback_index: int) -> str:
    for key in ("name", "username", "display_name", "user_name", "user_id"):
        value = profile.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"Agent {fallback_index}"


def get_persona_profession(profile: Dict[str, Any]) -> str:
    for key in ("profession", "occupation", "job_title", "role"):
        value = profile.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "Persona"


def sanitize_agent_payload(payload: Dict[str, Any], status: str = "completed") -> Dict[str, Any]:
    payload = safe_json(payload)
    candidate_answer = normalize_candidate_answer(payload.get("candidate_answer"))
    is_answerable = 1 if candidate_answer in {"yes", "no"} else 0
    content_short = truncate_text(
        payload.get("content_short"),
        limit=255,
        fallback="No clear judgment this round",
    )
    if status == "error" and content_short == "No clear judgment this round":
        content_short = "Agent request failed this round"

    return {
        "candidate_answer": candidate_answer,
        "is_answerable": is_answerable,
        "content_short": content_short,
        "evidence_title": truncate_text(payload.get("evidence_title"), limit=255) or None,
        "evidence_url": truncate_text(payload.get("evidence_url"), limit=512) or None,
        "evidence_time": truncate_text(parse_datetime(payload.get("evidence_time")), limit=128)
        or None,
        "status": status,
        "error_text": truncate_text(payload.get("error_text"), limit=255) or None,
        "raw_response_json": payload,
    }
