import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch


def _load_simulation_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("ZEP_API_KEY", "test-zep")
    monkeypatch.setenv("FLASK_DEBUG", "false")

    for mod in [
        "app.config",
        "app.api.simulation",
        "app.services.simulation_manager",
        "app.services.simulation_runner",
        "app.services.simulation_files",
    ]:
        sys.modules.pop(mod, None)

    config_module = importlib.import_module("app.config")
    config_module.Config.OASIS_SIMULATION_DATA_DIR = str(tmp_path)
    simulation_api = importlib.import_module("app.api.simulation")
    simulation_manager = importlib.import_module("app.services.simulation_manager")
    simulation_runner = importlib.import_module("app.services.simulation_runner")
    simulation_files = importlib.import_module("app.services.simulation_files")
    return simulation_api, simulation_manager, simulation_runner, simulation_files


def _write_state(sim_dir: Path, **overrides):
    data = {
        "simulation_id": sim_dir.name,
        "project_id": "proj_1",
        "graph_id": "graph_1",
        "enable_twitter": True,
        "enable_reddit": True,
        "status": "ready",
        "entities_count": 2,
        "profiles_count": 2,
        "entity_types": ["person"],
        "config_generated": True,
        "created_at": "2026-04-17T10:00:00",
        "updated_at": "2026-04-17T10:00:00",
        "error": None,
    }
    data.update(overrides)
    (sim_dir / "state.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_config(sim_dir: Path):
    (sim_dir / "simulation_config.json").write_text("{}", encoding="utf-8")


def _write_reddit_profiles(sim_dir: Path):
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps([{"user_id": 1}, {"user_id": 2}], ensure_ascii=False),
        encoding="utf-8",
    )


def _write_twitter_profiles(sim_dir: Path):
    (sim_dir / "twitter_profiles.csv").write_text(
        "user_id,name,username,user_char,description\n"
        "0,Alice,alice,Persona A,Desc A\n"
        "1,Bob,bob,Persona B,Desc B\n",
        encoding="utf-8",
    )


def test_load_twitter_profiles_from_csv(monkeypatch, tmp_path):
    _, simulation_manager, _, _ = _load_simulation_modules(monkeypatch, tmp_path)

    sim_dir = tmp_path / "sim_twitter"
    sim_dir.mkdir()
    _write_state(sim_dir, enable_reddit=False, enable_twitter=True)
    _write_twitter_profiles(sim_dir)

    manager = simulation_manager.SimulationManager()
    profiles = manager.get_profiles("sim_twitter", platform="twitter")

    assert len(profiles) == 2
    assert profiles[0]["username"] == "alice"
    assert profiles[1]["description"] == "Desc B"


def test_check_simulation_prepared_supports_single_platform(monkeypatch, tmp_path):
    simulation_api, _, _, _ = _load_simulation_modules(monkeypatch, tmp_path)

    twitter_only = tmp_path / "sim_twitter_only"
    twitter_only.mkdir()
    _write_state(twitter_only, enable_reddit=False, enable_twitter=True)
    _write_config(twitter_only)
    _write_twitter_profiles(twitter_only)

    ok, info = simulation_api._check_simulation_prepared("sim_twitter_only")
    assert ok is True
    assert info["profiles_count"] == 2

    reddit_only = tmp_path / "sim_reddit_only"
    reddit_only.mkdir()
    _write_state(reddit_only, enable_reddit=True, enable_twitter=False)
    _write_config(reddit_only)
    _write_reddit_profiles(reddit_only)

    ok, info = simulation_api._check_simulation_prepared("sim_reddit_only")
    assert ok is True
    assert info["profiles_count"] == 2

    dual = tmp_path / "sim_dual"
    dual.mkdir()
    _write_state(dual, enable_reddit=True, enable_twitter=True)
    _write_config(dual)
    _write_reddit_profiles(dual)
    _write_twitter_profiles(dual)

    ok, info = simulation_api._check_simulation_prepared("sim_dual")
    assert ok is True
    assert info["profiles_count"] == 2

    missing_enabled_file = tmp_path / "sim_missing"
    missing_enabled_file.mkdir()
    _write_state(missing_enabled_file, enable_reddit=False, enable_twitter=True)
    _write_config(missing_enabled_file)

    ok, info = simulation_api._check_simulation_prepared("sim_missing")
    assert ok is False
    assert info["missing_files"] == ["twitter_profiles.csv"]


def test_start_simulation_closes_log_file_when_popen_fails(monkeypatch, tmp_path):
    _, _, simulation_runner, _ = _load_simulation_modules(monkeypatch, tmp_path)

    sim_dir = tmp_path / "sim_launch_fail"
    sim_dir.mkdir()
    _write_config(sim_dir)

    state_file = sim_dir / "run_state.json"
    captured = {}

    def fake_save_run_state(state):
        state_file.write_text(
            json.dumps(state.to_detail_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    monkeypatch.setattr(simulation_runner.SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(simulation_runner.SimulationRunner, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(simulation_runner.SimulationRunner, "_save_run_state", fake_save_run_state)
    monkeypatch.setattr(simulation_runner.os.path, "exists", lambda path: True)

    real_open = open

    def tracking_open(*args, **kwargs):
        handle = real_open(*args, **kwargs)
        if str(args[0]).endswith("simulation.log"):
            captured["handle"] = handle
        return handle

    with patch("builtins.open", tracking_open):
        with patch.object(simulation_runner.subprocess, "Popen", side_effect=RuntimeError("boom")):
            try:
                simulation_runner.SimulationRunner.start_simulation("sim_launch_fail")
            except RuntimeError as exc:
                assert str(exc) == "boom"
            else:
                raise AssertionError("start_simulation should raise when Popen fails")

    assert captured["handle"].closed is True
