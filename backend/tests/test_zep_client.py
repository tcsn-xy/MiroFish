import importlib
import sys
from unittest.mock import patch


def _reload_modules(monkeypatch, overrides=None):
    overrides = overrides or {}
    for key in [
        "LLM_API_KEY",
        "ZEP_API_KEY",
        "ZEP_TRUST_ENV",
        "ZEP_TIMEOUT_SECONDS",
        "FLASK_DEBUG",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    for mod in [
        "app.config",
        "app.utils.zep_client",
        "app.services.graph_builder",
    ]:
        sys.modules.pop(mod, None)

    config_module = importlib.import_module("app.config")
    zep_client_module = importlib.import_module("app.utils.zep_client")
    graph_builder_module = importlib.import_module("app.services.graph_builder")
    return config_module, zep_client_module, graph_builder_module


def test_build_zep_client_disables_env_proxy_by_default(monkeypatch):
    _, zep_client_module, _ = _reload_modules(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
        },
    )

    captured = {}

    def fake_httpx_client(*args, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    with patch.object(zep_client_module.httpx, "Client", side_effect=fake_httpx_client):
        with patch.object(zep_client_module, "Zep", return_value="zep-client"):
            client = zep_client_module.build_zep_client()

    assert client == "zep-client"
    assert captured["kwargs"]["trust_env"] is False
    assert captured["kwargs"]["timeout"] == 60.0


def test_build_zep_client_respects_trust_env_override(monkeypatch):
    _, zep_client_module, _ = _reload_modules(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
            "ZEP_TRUST_ENV": "true",
            "ZEP_TIMEOUT_SECONDS": "15",
        },
    )

    captured = {}

    def fake_httpx_client(*args, **kwargs):
        captured["kwargs"] = kwargs
        return object()

    with patch.object(zep_client_module.httpx, "Client", side_effect=fake_httpx_client):
        with patch.object(zep_client_module, "Zep", return_value="zep-client"):
            client = zep_client_module.build_zep_client()

    assert client == "zep-client"
    assert captured["kwargs"]["trust_env"] is True
    assert captured["kwargs"]["timeout"] == 15.0


def test_graph_builder_uses_shared_zep_client_factory(monkeypatch):
    _, _, graph_builder_module = _reload_modules(
        monkeypatch,
        {
            "LLM_API_KEY": "test-key",
            "ZEP_API_KEY": "test-zep",
        },
    )

    with patch.object(graph_builder_module, "build_zep_client", return_value=object()) as mocked_factory:
        service = graph_builder_module.GraphBuilderService(api_key="explicit-key")

    assert service.client is not None
    mocked_factory.assert_called_once_with(api_key="explicit-key")
