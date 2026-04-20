import importlib
import sys
from unittest.mock import patch


def _reload_llm_modules(monkeypatch, overrides=None):
    overrides = overrides or {}
    for key in [
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL_NAME",
        "LLM_TRUST_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    for mod in [
        "app.config",
        "app.utils.llm_client",
    ]:
        sys.modules.pop(mod, None)

    config_module = importlib.import_module("app.config")
    llm_client_module = importlib.import_module("app.utils.llm_client")
    return config_module, llm_client_module


def test_llm_client_disables_env_proxy_by_default(monkeypatch):
    _, llm_client_module = _reload_llm_modules(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
        },
    )

    captured = {}

    def fake_httpx_client(*args, **kwargs):
        captured["httpx_kwargs"] = kwargs
        return object()

    def fake_openai(*args, **kwargs):
        captured["openai_kwargs"] = kwargs
        return object()

    with patch.object(llm_client_module.httpx, "Client", side_effect=fake_httpx_client):
        with patch.object(llm_client_module, "OpenAI", side_effect=fake_openai):
            client = llm_client_module.LLMClient()

    assert client.client is not None
    assert captured["httpx_kwargs"]["trust_env"] is False
    assert captured["httpx_kwargs"]["follow_redirects"] is True
    assert captured["openai_kwargs"]["http_client"] is client.http_client


def test_llm_client_respects_trust_env_override(monkeypatch):
    _, llm_client_module = _reload_llm_modules(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "LLM_TRUST_ENV": "true",
        },
    )

    captured = {}

    def fake_httpx_client(*args, **kwargs):
        captured["httpx_kwargs"] = kwargs
        return object()

    with patch.object(llm_client_module.httpx, "Client", side_effect=fake_httpx_client):
        with patch.object(llm_client_module, "OpenAI", return_value=object()):
            llm_client_module.LLMClient()

    assert captured["httpx_kwargs"]["trust_env"] is True
