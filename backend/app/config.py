"""
Central configuration.

Loads repository-root .env first, then derives application settings from
environment variables with in-code defaults as the fallback.
"""

from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv


APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
REPO_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
ENV_PATH = os.path.join(REPO_ROOT, ".env")


if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH, override=False)
else:
    load_dotenv(override=False)


DEFAULT_APP_CONFIG: Dict[str, Any] = {
    "llm": {
        "model_name": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_max_tokens": 4096,
    },
    "datasource": {
        "url": (
            "jdbc:mysql://127.0.0.1:3306/mirofish"
            "?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai"
        ),
        "username": "root",
        "password": "123456",
    },
    "storage": {
        "chroma": {
            "mode": "persistent",
            "persist_directory": "backend/uploads/chroma",
            "host": "127.0.0.1",
            "port": 8000,
            "collection_name": "world_info",
        }
    },
    "embedding": {
        "provider": "sentence_transformers",
        "model_name": "BAAI/bge-small-zh-v1.5",
        "batch_size": 16,
    },
    "world_info": {
        "enabled": True,
        "chunk_size": 1200,
        "chunk_overlap": 200,
        "search_top_k": 8,
        "simulation_context_budget_chars": 50000,
        "report_context_budget_chars": 20000,
        "world_info_injection_chars": 12000,
    },
}


def _coerce_env_value(raw: str, sample: Any) -> Any:
    if isinstance(sample, bool):
        return raw.lower() in {"1", "true", "yes", "on"}
    if isinstance(sample, int) and not isinstance(sample, bool):
        return int(raw)
    if isinstance(sample, float):
        return float(raw)
    return raw


def _set_nested(config: Dict[str, Any], dotted_path: str, value: Any) -> None:
    node = config
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _get_nested(config: Dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    node: Any = config
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


ENV_TO_CONFIG = {
    "LLM_BASE_URL": "llm.base_url",
    "LLM_MODEL_NAME": "llm.model_name",
    "LLM_DEFAULT_MAX_TOKENS": "llm.default_max_tokens",
    "DATASOURCE_URL": "datasource.url",
    "DATASOURCE_USERNAME": "datasource.username",
    "DATASOURCE_PASSWORD": "datasource.password",
    "CHROMA_MODE": "storage.chroma.mode",
    "CHROMA_PERSIST_DIRECTORY": "storage.chroma.persist_directory",
    "CHROMA_HOST": "storage.chroma.host",
    "CHROMA_PORT": "storage.chroma.port",
    "CHROMA_COLLECTION_NAME": "storage.chroma.collection_name",
    "EMBEDDING_PROVIDER": "embedding.provider",
    "EMBEDDING_MODEL_NAME": "embedding.model_name",
    "EMBEDDING_BATCH_SIZE": "embedding.batch_size",
    "WORLD_INFO_ENABLED": "world_info.enabled",
    "WORLD_INFO_CHUNK_SIZE": "world_info.chunk_size",
    "WORLD_INFO_CHUNK_OVERLAP": "world_info.chunk_overlap",
    "WORLD_INFO_SEARCH_TOP_K": "world_info.search_top_k",
    "SIMULATION_CONTEXT_BUDGET_CHARS": "world_info.simulation_context_budget_chars",
    "REPORT_CONTEXT_BUDGET_CHARS": "world_info.report_context_budget_chars",
    "WORLD_INFO_INJECTION_CHARS": "world_info.world_info_injection_chars",
}


def _load_application_config() -> Dict[str, Any]:
    config = {
        "llm": dict(DEFAULT_APP_CONFIG["llm"]),
        "datasource": dict(DEFAULT_APP_CONFIG["datasource"]),
        "storage": {
            "chroma": dict(DEFAULT_APP_CONFIG["storage"]["chroma"]),
        },
        "embedding": dict(DEFAULT_APP_CONFIG["embedding"]),
        "world_info": dict(DEFAULT_APP_CONFIG["world_info"]),
    }
    for env_name, dotted_path in ENV_TO_CONFIG.items():
        if env_name in os.environ:
            current = _get_nested(config, dotted_path)
            _set_nested(config, dotted_path, _coerce_env_value(os.environ[env_name], current))
    return config


APPLICATION_CONFIG = _load_application_config()


def resolve_repo_path(path_value: str) -> str:
    if os.path.isabs(path_value):
        return os.path.abspath(path_value)
    return os.path.abspath(os.path.join(REPO_ROOT, path_value))


def parse_jdbc_mysql_url(jdbc_url: str) -> Dict[str, Any]:
    """Convert a jdbc:mysql:// URL to PyMySQL connection keyword args."""
    raw_url = jdbc_url
    if raw_url.startswith("jdbc:"):
        raw_url = raw_url[len("jdbc:") :]
    parsed = urlparse(raw_url)
    if parsed.scheme != "mysql":
        raise ValueError(f"Unsupported datasource URL scheme: {parsed.scheme}")
    query = parse_qs(parsed.query)
    charset = query.get("characterEncoding", query.get("charset", ["utf8mb4"]))[0]
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "database": parsed.path.lstrip("/"),
        "charset": charset or "utf8mb4",
    }


class Config:
    """Flask config and application-level settings."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "mirofish-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    JSON_AS_ASCII = False

    APP_CONFIG = APPLICATION_CONFIG

    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or _get_nested(APP_CONFIG, "llm.base_url")
    LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME") or _get_nested(APP_CONFIG, "llm.model_name")
    LLM_DEFAULT_MAX_TOKENS = int(_get_nested(APP_CONFIG, "llm.default_max_tokens", 4096))

    ZEP_API_KEY = os.environ.get("ZEP_API_KEY")
    ZEP_TRUST_ENV = os.environ.get("ZEP_TRUST_ENV", "false").lower() in {"1", "true", "yes", "on"}
    ZEP_TIMEOUT_SECONDS = float(os.environ.get("ZEP_TIMEOUT_SECONDS", "60"))

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BACKEND_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "md", "txt", "markdown"}

    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get("OASIS_DEFAULT_MAX_ROUNDS", "10"))
    OASIS_SIMULATION_DATA_DIR = os.path.join(UPLOAD_FOLDER, "simulations")

    OASIS_TWITTER_ACTIONS = [
        "CREATE_POST",
        "LIKE_POST",
        "REPOST",
        "FOLLOW",
        "DO_NOTHING",
        "QUOTE_POST",
    ]
    OASIS_REDDIT_ACTIONS = [
        "LIKE_POST",
        "DISLIKE_POST",
        "CREATE_POST",
        "CREATE_COMMENT",
        "LIKE_COMMENT",
        "DISLIKE_COMMENT",
        "SEARCH_POSTS",
        "SEARCH_USER",
        "TREND",
        "REFRESH",
        "DO_NOTHING",
        "FOLLOW",
        "MUTE",
    ]

    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS", "5"))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get("REPORT_AGENT_MAX_REFLECTION_ROUNDS", "2"))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get("REPORT_AGENT_TEMPERATURE", "0.5"))

    DATASOURCE_URL = _get_nested(APP_CONFIG, "datasource.url")
    DATASOURCE_USERNAME = _get_nested(APP_CONFIG, "datasource.username")
    DATASOURCE_PASSWORD = _get_nested(APP_CONFIG, "datasource.password")

    CHROMA_MODE = _get_nested(APP_CONFIG, "storage.chroma.mode")
    CHROMA_PERSIST_DIRECTORY = resolve_repo_path(
        _get_nested(APP_CONFIG, "storage.chroma.persist_directory")
    )
    CHROMA_HOST = _get_nested(APP_CONFIG, "storage.chroma.host")
    CHROMA_PORT = int(_get_nested(APP_CONFIG, "storage.chroma.port"))
    CHROMA_COLLECTION_NAME = _get_nested(APP_CONFIG, "storage.chroma.collection_name")

    EMBEDDING_PROVIDER = _get_nested(APP_CONFIG, "embedding.provider")
    EMBEDDING_MODEL_NAME = _get_nested(APP_CONFIG, "embedding.model_name")
    EMBEDDING_BATCH_SIZE = int(_get_nested(APP_CONFIG, "embedding.batch_size"))

    WORLD_INFO_ENABLED = bool(_get_nested(APP_CONFIG, "world_info.enabled", True))
    WORLD_INFO_CHUNK_SIZE = int(_get_nested(APP_CONFIG, "world_info.chunk_size", 1200))
    WORLD_INFO_CHUNK_OVERLAP = int(_get_nested(APP_CONFIG, "world_info.chunk_overlap", 200))
    WORLD_INFO_SEARCH_TOP_K = int(_get_nested(APP_CONFIG, "world_info.search_top_k", 8))
    SIMULATION_CONTEXT_BUDGET_CHARS = int(
        _get_nested(APP_CONFIG, "world_info.simulation_context_budget_chars", 50000)
    )
    REPORT_CONTEXT_BUDGET_CHARS = int(
        _get_nested(APP_CONFIG, "world_info.report_context_budget_chars", 20000)
    )
    WORLD_INFO_INJECTION_CHARS = int(
        _get_nested(APP_CONFIG, "world_info.world_info_injection_chars", 12000)
    )

    @classmethod
    def get_mysql_config(cls) -> Dict[str, Any]:
        mysql_config = parse_jdbc_mysql_url(cls.DATASOURCE_URL)
        mysql_config.update(
            {
                "user": cls.DATASOURCE_USERNAME,
                "password": cls.DATASOURCE_PASSWORD,
                "autocommit": False,
                "cursorclass": None,
            }
        )
        return mysql_config

    @classmethod
    def validate(cls):
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        return errors
