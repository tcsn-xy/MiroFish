from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional


CONTENT_SHORT_LIMIT = 160
DISPLAY_SHORT_TARGET = 50
FAILURE_CONTENT = "本轮未找到可靠新信息，暂不可答"


BUILTIN_AGENTS: List[Dict[str, str]] = [
    {"id": "programmer", "name": "程序员", "persona": "你从工程实现、系统机制、可验证来源角度判断问题是否已可回答。"},
    {"id": "product_manager", "name": "产品经理", "persona": "你从用户需求、产品定义、官方口径和使用场景角度判断问题是否已可回答。"},
    {"id": "journalist", "name": "记者", "persona": "你从新闻价值、来源可信度、发布时间和交叉印证角度判断问题是否已可回答。"},
    {"id": "researcher", "name": "研究员", "persona": "你从研究证据、方法质量、样本局限和可重复性角度判断问题是否已可回答。"},
    {"id": "industry_analyst", "name": "行业分析师", "persona": "你从行业结构、商业现实、市场动态和主流机构信息角度判断问题是否已可回答。"},
    {"id": "general_user", "name": "普通用户", "persona": "你从普通人是否能据此做出判断、信息是否直观可靠角度判断问题是否已可回答。"},
    {"id": "investor", "name": "投资人", "persona": "你从风险收益、市场预期、企业动作和外部变量角度判断问题是否已可回答。"},
    {"id": "scholar", "name": "学者", "persona": "你从概念边界、论证完整性和证据严谨性角度判断问题是否已可回答。"},
    {"id": "community_observer", "name": "社区观察者", "persona": "你从社区讨论、舆论倾向和群体感知角度判断问题是否已可回答。"},
    {"id": "skeptic", "name": "谨慎怀疑者", "persona": "你默认保持怀疑，只有当证据足够具体、近期且可信时才认为问题可回答。"},
]


def required_ready_count(total_agents: int, threshold_percent: int) -> int:
    return int(math.ceil(total_agents * threshold_percent / 100.0))


def load_extra_body(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"CONSENSUS_NATIVE_SEARCH_EXTRA_BODY 不是合法 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("CONSENSUS_NATIVE_SEARCH_EXTRA_BODY 必须是 JSON object")
    return parsed


def clean_content_short(value: Optional[str]) -> str:
    text = value or ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"[*_>#-]+", " ", text)
    text = re.sub(r"\s+", " ", text.replace("\n", " ").replace("\r", " ")).strip()
    if not text:
        text = FAILURE_CONTENT
    if len(text) > CONTENT_SHORT_LIMIT:
        text = text[:CONTENT_SHORT_LIMIT].rstrip()
    return text


def clean_optional_text(value: Optional[str], limit: int) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text.replace("\n", " ").replace("\r", " ")).strip()
    if len(text) > limit:
        text = text[:limit].rstrip()
    return text


def clean_evidence_url(value: Optional[str]) -> Optional[str]:
    text = clean_optional_text(value, 500)
    if not text:
        return None
    if not text.lower().startswith(("http://", "https://")):
        return None
    return text


def sanitize_agent_payload(agent_name: str, payload: Optional[Dict[str, Any]], error_text: Optional[str] = None) -> Dict[str, Any]:
    payload = payload or {}
    return {
        "agent_name": agent_name,
        "content_short": clean_content_short(payload.get("content_short")),
        "is_ready_to_answer": bool(payload.get("is_ready_to_answer")),
        "candidate_answer": clean_optional_text(payload.get("candidate_answer"), 4000),
        "evidence_title": clean_optional_text(payload.get("evidence_title"), 255),
        "evidence_url": clean_evidence_url(payload.get("evidence_url")),
        "evidence_time": clean_optional_text(payload.get("evidence_time"), 64),
        "error_text": clean_optional_text(error_text or payload.get("error_text"), 255),
    }


def has_valid_evidence(log: Dict[str, Any]) -> bool:
    return bool(log.get("is_ready_to_answer") and clean_evidence_url(log.get("evidence_url")))


def scheduler_should_start(debug: bool) -> bool:
    return (not debug) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
