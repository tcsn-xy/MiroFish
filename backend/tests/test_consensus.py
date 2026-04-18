import importlib
import sys
from datetime import datetime
from types import SimpleNamespace


def _reload_consensus(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("ZEP_API_KEY", "test-zep")
    monkeypatch.setenv("CONSENSUS_ENABLED", "true")
    monkeypatch.setenv("CONSENSUS_AGENT_COUNT", "10")
    monkeypatch.setenv("CONSENSUS_ROUND_INTERVAL_SECONDS", "86400")
    monkeypatch.setenv("CONSENSUS_NATIVE_SEARCH_EXTRA_BODY", "{\"search\":true}")
    monkeypatch.setenv("FLASK_DEBUG", "false")

    for mod in [
        "app.config",
        "app.__init__",
        "app.api",
        "app.api.consensus",
        "app.consensus",
        "app.consensus.repository",
        "app.consensus.service",
        "app.consensus.scheduler",
        "app.consensus.utils",
    ]:
        sys.modules.pop(mod, None)

    config_module = importlib.import_module("app.config")
    utils_module = importlib.import_module("app.consensus.utils")
    service_module = importlib.import_module("app.consensus.service")
    app_module = importlib.import_module("app")
    return config_module, utils_module, service_module, app_module


def test_consensus_utils_cleaning_and_threshold():
    utils = importlib.import_module("app.consensus.utils")

    assert utils.required_ready_count(10, 95) == 10
    assert utils.required_ready_count(10, 0) == 0
    assert utils.clean_evidence_url("https://example.com/a") == "https://example.com/a"
    assert utils.clean_evidence_url("ftp://example.com/a") is None
    assert utils.clean_content_short("```json\nhello\n```  world") == "hello world"

    payload = utils.sanitize_agent_payload(
        "记者",
        {
            "content_short": "  第一行\n第二行  ",
            "is_ready_to_answer": True,
            "candidate_answer": "答案",
            "evidence_title": "标题",
            "evidence_url": "notaurl",
            "evidence_time": "2026-04-18",
        },
    )
    assert payload["content_short"] == "第一行 第二行"
    assert payload["evidence_url"] is None
    assert utils.has_valid_evidence(payload) is False


def test_consensus_service_current_agents_builds_fixed_roster(monkeypatch):
    _, _, service_module, _ = _reload_consensus(monkeypatch)

    class Repo:
        def ensure_tables_exist(self):
            return None

        class _Session:
            def __enter__(self_inner):
                return object()

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        def session(self):
            return self._Session()

        def get_current_task(self, conn):
            return {
                "id": 1,
                "question": "问题",
                "status": "running",
                "current_round": 1,
                "threshold_percent": 80,
                "required_ready_count": 8,
                "latest_ready_count": 2,
                "total_agents": 10,
                "accepted_ratio": 20.0,
                "final_answer": None,
                "final_evidence_text": None,
                "updated_at": datetime(2026, 4, 18, 10, 0, 0),
            }

        def get_logs_for_task(self, conn, task_id):
            return [
                {
                    "task_id": 1,
                    "round_no": 1,
                    "agent_id": "programmer",
                    "agent_name": "程序员",
                    "content_short": "可以答",
                    "is_ready_to_answer": 1,
                    "candidate_answer": "答",
                    "evidence_title": "证据",
                    "evidence_url": "https://example.com",
                    "evidence_time": "2026-04-18",
                    "error_text": None,
                    "created_at": datetime(2026, 4, 18, 10, 0, 5),
                }
            ]

    service = service_module.ConsensusService(repository=Repo(), llm_client=None)
    payload = service.get_current_agents_view()

    assert payload["task"]["task_id"] == 1
    assert len(payload["agents"]) == 10
    programmer = next(item for item in payload["agents"] if item["agent_name"] == "程序员")
    skeptic = next(item for item in payload["agents"] if item["agent_name"] == "谨慎怀疑者")
    assert programmer["latest"]["content_short"] == "可以答"
    assert skeptic["latest"]["content_short"] == "等待首轮结果"


def test_consensus_service_runs_answered_round_only_with_valid_evidence(monkeypatch):
    _, _, service_module, _ = _reload_consensus(monkeypatch)

    class Repo:
        def __init__(self):
            self.answer_called = False
            self.running_called = False
            self.failed_called = False
            self.current_status = "running"
            self.current_row = {
                "id": 1,
                "question": "问题",
                "status": "running",
                "current_round": 0,
                "threshold_percent": 0,
                "required_ready_count": 0,
                "latest_ready_count": 0,
                "total_agents": 10,
                "accepted_ratio": 0.0,
                "consecutive_error_rounds": 0,
            }

        def ensure_tables_exist(self):
            return None

        class _Session:
            def __init__(self, owner):
                self.owner = owner

            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        def session(self):
            return self._Session(self)

        def get_due_running_task_for_update(self, conn):
            if self.current_status != "running":
                return None
            return {
                "id": 1,
                "question": "问题",
                "current_round": 0,
                "required_ready_count": 0,
                "consecutive_error_rounds": 0,
            }

        def mark_round_started(self, conn, task_id, round_no):
            self.current_row["current_round"] = round_no

        def insert_agent_log(self, conn, task_id, round_no, agent_id, payload):
            return None

        def get_task_by_id(self, conn, task_id):
            return {**self.current_row, "status": self.current_status}

        def mark_answered(self, conn, task_id, ready_count, accepted_ratio, final_answer, final_evidence_text):
            self.answer_called = True

        def finish_round_running(self, conn, task_id, ready_count, accepted_ratio, next_round_at_expression, consecutive_error_rounds, error_text):
            self.running_called = True

        def mark_failed(self, conn, task_id, error_text):
            self.failed_called = True

    service = service_module.ConsensusService(repository=Repo(), llm_client=None)
    service._execute_round = lambda task_id, question, round_no: (
        [
            {
                "agent_id": f"agent-{i}",
                "agent_name": f"agent-{i}",
                "content_short": "可答",
                "is_ready_to_answer": True,
                "candidate_answer": "answer",
                "evidence_title": "title",
                "evidence_url": "https://example.com/1" if i == 0 else None,
                "evidence_time": "2026-04-18",
                "error_text": None,
            }
            for i in range(10)
        ],
        None,
    )
    service._synthesize_final_answer = lambda question, logs: ("final", "evidence")

    did_work = service.run_due_round()
    assert did_work is True
    assert service.repository.answer_called is True
    assert service.repository.running_called is False
    assert service.repository.failed_called is False


def test_consensus_service_does_not_answer_without_valid_evidence(monkeypatch):
    _, _, service_module, _ = _reload_consensus(monkeypatch)

    class Repo:
        def __init__(self):
            self.answer_called = False
            self.running_called = False
            self.current_row = {
                "id": 1,
                "question": "问题",
                "status": "running",
                "current_round": 0,
                "threshold_percent": 0,
                "required_ready_count": 0,
                "latest_ready_count": 0,
                "total_agents": 10,
                "accepted_ratio": 0.0,
                "consecutive_error_rounds": 0,
            }

        def ensure_tables_exist(self):
            return None

        class _Session:
            def __enter__(self):
                return object()

            def __exit__(self, exc_type, exc, tb):
                return False

        def session(self):
            return self._Session()

        def get_due_running_task_for_update(self, conn):
            return {
                "id": 1,
                "question": "问题",
                "current_round": 0,
                "required_ready_count": 0,
                "consecutive_error_rounds": 0,
            }

        def mark_round_started(self, conn, task_id, round_no):
            return None

        def insert_agent_log(self, conn, task_id, round_no, agent_id, payload):
            return None

        def get_task_by_id(self, conn, task_id):
            return self.current_row

        def mark_answered(self, conn, task_id, ready_count, accepted_ratio, final_answer, final_evidence_text):
            self.answer_called = True

        def finish_round_running(self, conn, task_id, ready_count, accepted_ratio, next_round_at_expression, consecutive_error_rounds, error_text):
            self.running_called = True

        def mark_failed(self, conn, task_id, error_text):
            raise AssertionError("should not fail")

    service = service_module.ConsensusService(repository=Repo(), llm_client=None)
    service._execute_round = lambda task_id, question, round_no: (
        [
            {
                "agent_id": f"agent-{i}",
                "agent_name": f"agent-{i}",
                "content_short": "可答",
                "is_ready_to_answer": True,
                "candidate_answer": "answer",
                "evidence_title": "title",
                "evidence_url": None,
                "evidence_time": "2026-04-18",
                "error_text": None,
            }
            for i in range(10)
        ],
        None,
    )

    did_work = service.run_due_round()
    assert did_work is True
    assert service.repository.answer_called is False
    assert service.repository.running_called is True


def test_consensus_api_endpoints(monkeypatch):
    _, _, _, app_module = _reload_consensus(monkeypatch)

    class FakeService:
        def __init__(self):
            self.started = False
            self.stopped = False

        def start_task(self, question, threshold_percent):
            self.started = True
            return {"task_id": 1, "status": "running", "required_ready_count": 8}

        def get_current_task(self):
            return None

        def get_current_agents_view(self):
            return {"task": None, "agents": []}

        def stop_current_task(self):
            self.stopped = True

    fake_service = FakeService()
    fake_scheduler = SimpleNamespace(start=lambda: None, wake=lambda: None)

    monkeypatch.setattr("app.api.consensus.get_consensus_service", lambda: fake_service)
    monkeypatch.setattr("app.api.consensus.get_consensus_scheduler", lambda: fake_scheduler)
    monkeypatch.setattr("app.consensus.get_consensus_scheduler", lambda: fake_scheduler)

    app = app_module.create_app()
    client = app.test_client()

    res = client.get("/api/consensus/task/current")
    assert res.status_code == 200
    assert res.get_json()["data"] is None

    res = client.post("/api/consensus/task/start", json={"question": "test", "threshold_percent": 80})
    assert res.status_code == 200
    assert res.get_json()["data"]["task_id"] == 1

    res = client.post("/api/consensus/task/stop", json={})
    assert res.status_code == 200
    assert res.get_json()["data"]["status"] == "stopped"
