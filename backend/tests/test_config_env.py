import importlib
import os
import sys
from unittest.mock import patch


def _reload_config(monkeypatch, overrides=None):
    overrides = overrides or {}
    env_keys = [
        "SECRET_KEY",
        "FLASK_DEBUG",
        "FLASK_HOST",
        "FLASK_PORT",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL_NAME",
        "LLM_DEFAULT_MAX_TOKENS",
        "ZEP_API_KEY",
        "ZEP_TRUST_ENV",
        "ZEP_TIMEOUT_SECONDS",
        "DATASOURCE_URL",
        "DATASOURCE_USERNAME",
        "DATASOURCE_PASSWORD",
        "CHROMA_MODE",
        "CHROMA_PERSIST_DIRECTORY",
        "CHROMA_HOST",
        "CHROMA_PORT",
        "CHROMA_COLLECTION_NAME",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL_NAME",
        "EMBEDDING_BATCH_SIZE",
        "WORLD_INFO_ENABLED",
        "WORLD_INFO_CHUNK_SIZE",
        "WORLD_INFO_CHUNK_OVERLAP",
        "WORLD_INFO_SEARCH_TOP_K",
        "SIMULATION_CONTEXT_BUDGET_CHARS",
        "REPORT_CONTEXT_BUDGET_CHARS",
        "WORLD_INFO_INJECTION_CHARS",
        "CONSENSUS_ENABLED",
        "CONSENSUS_MODEL_NAME",
        "CONSENSUS_AGENT_COUNT",
        "CONSENSUS_ROUND_INTERVAL_SECONDS",
        "CONSENSUS_NATIVE_SEARCH_EXTRA_BODY",
        "OASIS_DEFAULT_MAX_ROUNDS",
        "REPORT_AGENT_MAX_TOOL_CALLS",
        "REPORT_AGENT_MAX_REFLECTION_ROUNDS",
        "REPORT_AGENT_TEMPERATURE",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop("app.config", None)
    with patch("dotenv.load_dotenv", return_value=False):
        return importlib.import_module("app.config")


def test_config_uses_env_only_without_application_yml(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
            "DATASOURCE_URL": "jdbc:mysql://10.0.0.8:3307/testdb?characterEncoding=utf8mb4",
            "DATASOURCE_USERNAME": "tester",
            "DATASOURCE_PASSWORD": "secret",
            "CHROMA_MODE": "persistent",
            "CHROMA_PERSIST_DIRECTORY": "custom/chroma",
            "CHROMA_COLLECTION_NAME": "custom_collection",
            "EMBEDDING_MODEL_NAME": "custom-model",
            "EMBEDDING_BATCH_SIZE": "32",
            "WORLD_INFO_ENABLED": "false",
            "WORLD_INFO_SEARCH_TOP_K": "12",
            "WORLD_INFO_INJECTION_CHARS": "18000",
            "CONSENSUS_ENABLED": "true",
            "CONSENSUS_MODEL_NAME": "gpt-consensus",
            "CONSENSUS_NATIVE_SEARCH_EXTRA_BODY": "{\"search\":true}",
        },
    )

    assert not hasattr(config_module, "APPLICATION_YML")
    assert config_module.Config.DATASOURCE_URL == "jdbc:mysql://10.0.0.8:3307/testdb?characterEncoding=utf8mb4"
    assert config_module.Config.DATASOURCE_USERNAME == "tester"
    assert config_module.Config.DATASOURCE_PASSWORD == "secret"
    assert config_module.Config.CHROMA_MODE == "persistent"
    assert config_module.Config.CHROMA_PERSIST_DIRECTORY.endswith(
        os.path.join("custom", "chroma")
    )
    assert config_module.Config.CHROMA_COLLECTION_NAME == "custom_collection"
    assert config_module.Config.EMBEDDING_MODEL_NAME == "custom-model"
    assert config_module.Config.EMBEDDING_BATCH_SIZE == 32
    assert config_module.Config.WORLD_INFO_ENABLED is False
    assert config_module.Config.WORLD_INFO_SEARCH_TOP_K == 12
    assert config_module.Config.WORLD_INFO_INJECTION_CHARS == 18000
    assert config_module.Config.CONSENSUS_ENABLED is True
    assert config_module.Config.CONSENSUS_MODEL_NAME == "gpt-consensus"
    assert config_module.Config.CONSENSUS_NATIVE_SEARCH_EXTRA_BODY == "{\"search\":true}"


def test_config_supports_chroma_http_mode(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
            "CHROMA_MODE": "http",
            "CHROMA_HOST": "192.168.1.10",
            "CHROMA_PORT": "9000",
        },
    )

    assert config_module.Config.CHROMA_MODE == "http"
    assert config_module.Config.CHROMA_HOST == "192.168.1.10"
    assert config_module.Config.CHROMA_PORT == 9000


def test_config_defaults_still_work(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
        },
    )

    assert config_module.Config.LLM_BASE_URL == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config_module.Config.LLM_MODEL_NAME == "qwen-plus"
    assert config_module.Config.CHROMA_MODE == "persistent"
    assert config_module.Config.CHROMA_PERSIST_DIRECTORY.endswith(
        os.path.join("backend", "uploads", "chroma")
    )
    assert config_module.Config.WORLD_INFO_CHUNK_SIZE == 1200
    assert config_module.Config.REPORT_AGENT_TEMPERATURE == 0.5
    assert config_module.Config.ZEP_TRUST_ENV is False
    assert config_module.Config.ZEP_TIMEOUT_SECONDS == 60.0
    assert config_module.Config.CONSENSUS_ENABLED is False
    assert config_module.Config.CONSENSUS_AGENT_COUNT == 10
    assert config_module.Config.CONSENSUS_ROUND_INTERVAL_SECONDS == 86400


def test_config_supports_zep_network_overrides(monkeypatch):
    config_module = _reload_config(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
            "ZEP_TRUST_ENV": "true",
            "ZEP_TIMEOUT_SECONDS": "12.5",
        },
    )

    assert config_module.Config.ZEP_TRUST_ENV is True
    assert config_module.Config.ZEP_TIMEOUT_SECONDS == 12.5
