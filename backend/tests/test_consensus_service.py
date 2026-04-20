from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from app.consensus.default_catalog import (
    DEFAULT_CONSENSUS_PROJECT_ID,
    DEFAULT_CONSENSUS_SIMULATION_ID,
    get_default_consensus_personas,
)
from app.consensus.service import ConsensusService


class DummyContext:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self.repo

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeRepository:
    def __init__(self):
        self.tasks = []
        self.judgments = []
        self._task_id = 1

    def session(self):
        return DummyContext(self)

    def ensure_ready(self):
        return None

    def has_running_task(self, conn, simulation_id):
        return any(
            task["simulation_id"] == simulation_id and task["status"] == "running"
            for task in self.tasks
        )

    def create_task(
        self,
        conn,
        *,
        task_uid,
        project_id,
        simulation_id,
        question_text,
        threshold_percent,
        poll_interval_seconds,
        total_agents,
        next_run_at,
    ):
        task = {
            "id": self._task_id,
            "task_uid": task_uid,
            "project_id": project_id,
            "simulation_id": simulation_id,
            "question_text": question_text,
            "persona_platform": "reddit",
            "threshold_percent": threshold_percent,
            "poll_interval_seconds": poll_interval_seconds,
            "total_agents": total_agents,
            "current_round_index": 0,
            "last_answerable_agents": 0,
            "last_yes_agents": 0,
            "last_no_agents": 0,
            "final_answer": None,
            "final_answerable_agents": None,
            "final_yes_agents": None,
            "final_no_agents": None,
            "completed_round_index": None,
            "final_reason_short": None,
            "status": "running",
            "last_polled_at": None,
            "next_run_at": next_run_at.isoformat() if hasattr(next_run_at, "isoformat") else next_run_at,
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "end_reason": None,
            "error_text": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.tasks.append(task)
        self._task_id += 1
        return task["id"]

    def get_task_by_uid(self, conn, task_uid):
        for task in self.tasks:
            if task["task_uid"] == task_uid:
                return deepcopy(task)
        return None

    def get_current_or_latest_task(self, conn, simulation_id):
        filtered = [task for task in self.tasks if task["simulation_id"] == simulation_id]
        if not filtered:
            return None
        running = [task for task in filtered if task["status"] == "running"]
        selected = running[-1] if running else filtered[-1]
        return deepcopy(selected)

    def list_tasks(self, conn, simulation_id):
        return [deepcopy(task) for task in self.tasks if task["simulation_id"] == simulation_id]

    def list_due_running_tasks(self, conn, now):
        due = []
        for task in self.tasks:
            if task["status"] == "running":
                due.append(deepcopy(task))
        return due

    def create_round_judgments(self, conn, judgments):
        for judgment in judgments:
            self.judgments.append(deepcopy(judgment))

    def update_task_after_round(
        self,
        conn,
        *,
        task_id,
        round_index,
        answerable_count,
        yes_count,
        no_count,
        polled_at,
        next_run_at,
        status,
        final_answer=None,
        final_reason_short=None,
        end_reason=None,
        ended_at=None,
        error_text=None,
    ):
        task = next(task for task in self.tasks if task["id"] == task_id)
        task["current_round_index"] = round_index
        task["last_answerable_agents"] = answerable_count
        task["last_yes_agents"] = yes_count
        task["last_no_agents"] = no_count
        task["last_polled_at"] = polled_at.isoformat()
        task["next_run_at"] = next_run_at.isoformat() if next_run_at else None
        task["status"] = status
        task["final_answer"] = final_answer
        task["final_answerable_agents"] = answerable_count if final_answer else None
        task["final_yes_agents"] = yes_count if final_answer else None
        task["final_no_agents"] = no_count if final_answer else None
        task["completed_round_index"] = round_index if final_answer else None
        task["final_reason_short"] = final_reason_short
        task["ended_at"] = ended_at.isoformat() if ended_at else None
        task["end_reason"] = end_reason
        task["error_text"] = error_text

    def update_task_error(self, conn, task_id, error_text):
        task = next(task for task in self.tasks if task["id"] == task_id)
        task["error_text"] = error_text

    def stop_task(self, conn, task_id, end_reason, ended_at):
        task = next(task for task in self.tasks if task["id"] == task_id)
        if task["status"] == "running":
            task["status"] = "stopped"
            task["ended_at"] = ended_at.isoformat()
            task["end_reason"] = end_reason
            task["next_run_at"] = None

    def interrupt_running_tasks(self, conn, ended_at):
        count = 0
        for task in self.tasks:
            if task["status"] == "running":
                task["status"] = "interrupted"
                task["ended_at"] = ended_at.isoformat()
                task["end_reason"] = "service_restart"
                task["next_run_at"] = None
                count += 1
        return count

    def list_judgments(self, conn, task_id):
        rows = [row for row in self.judgments if row["task_id"] == task_id]
        rows.sort(key=lambda item: (item["agent_source_id"], -int(item["round_index"])))
        return deepcopy(rows)


def build_service(monkeypatch, personas=None, round_judgments=None):
    personas = personas or [
        {"user_id": "u1", "name": "Alice"},
        {"user_id": "u2", "name": "Bob"},
    ]
    round_judgments = round_judgments or [
        {
            "agent_source_id": "u1",
            "agent_name": "Alice",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
        {
            "agent_source_id": "u2",
            "agent_name": "Bob",
            "candidate_answer": "no",
            "is_answerable": 1,
            "content_short": "no",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "no"},
        },
    ]

    service = ConsensusService()
    fake_repo = FakeRepository()
    service.repository = fake_repo

    class FakeState:
        project_id = "proj_1"

    service.simulation_manager = type(
        "Manager",
        (),
        {
            "get_simulation": lambda self, simulation_id: FakeState(),
            "_get_simulation_dir": lambda self, simulation_id: "ignored",
        },
    )()

    monkeypatch.setattr(
        service,
        "_load_reddit_personas",
        lambda simulation_id: {"project_id": "proj_1", "personas": personas},
    )
    monkeypatch.setattr(
        service,
        "_judge_personas_for_round",
        lambda **kwargs: deepcopy(round_judgments),
    )
    return service, fake_repo


def test_start_task_rejects_invalid_threshold(monkeypatch):
    service, _ = build_service(monkeypatch)
    with pytest.raises(ValueError, match="threshold_percent must be between 1 and 100"):
        service.start_task(
            simulation_id="sim_1",
            question_text="Will X happen?",
            threshold_percent=0,
        )


def test_start_task_uses_custom_poll_interval_seconds(monkeypatch):
    service, _ = build_service(monkeypatch)

    task = service.start_task(
        simulation_id="sim_1",
        question_text="Will X happen?",
        threshold_percent=60,
        poll_interval_seconds=3600,
    )

    assert task["poll_interval_seconds"] == 3600


def test_start_task_uses_default_poll_interval_when_missing(monkeypatch):
    service, _ = build_service(monkeypatch)
    monkeypatch.setattr("app.consensus.service.Config.CONSENSUS_POLL_INTERVAL_SECONDS", 45)

    task = service.start_task(
        simulation_id="sim_1",
        question_text="Will X happen?",
        threshold_percent=60,
    )

    assert task["poll_interval_seconds"] == 45


@pytest.mark.parametrize("poll_interval_seconds", [29, 30 * 24 * 60 * 60 + 1, "invalid"])
def test_start_task_rejects_invalid_poll_interval(monkeypatch, poll_interval_seconds):
    service, _ = build_service(monkeypatch)

    with pytest.raises(ValueError, match="poll_interval_seconds"):
        service.start_task(
            simulation_id="sim_1",
            question_text="Will X happen?",
            threshold_percent=60,
            poll_interval_seconds=poll_interval_seconds,
        )


def test_start_task_falls_back_to_default_personas_when_profiles_missing(monkeypatch):
    service, _ = build_service(monkeypatch)
    monkeypatch.setattr(
        "app.consensus.service.load_profiles",
        lambda simulation_dir, platform: [],
    )
    monkeypatch.setattr(
        service,
        "_load_reddit_personas",
        lambda simulation_id: {
            "project_id": "proj_1",
            "personas": get_default_consensus_personas(),
        },
    )
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Will X happen?",
        threshold_percent=60,
    )
    assert task["simulation_id"] == "sim_1"
    assert task["total_agents"] == 10


def test_start_task_uses_default_catalog_when_simulation_id_missing(monkeypatch):
    service, _ = build_service(monkeypatch)
    monkeypatch.setattr(
        service,
        "_load_reddit_personas",
        lambda simulation_id: {
            "project_id": DEFAULT_CONSENSUS_PROJECT_ID,
            "personas": get_default_consensus_personas(),
        },
    )

    task = service.start_task(
        simulation_id="",
        question_text="Will X happen?",
        threshold_percent=60,
    )

    assert task["simulation_id"] == DEFAULT_CONSENSUS_SIMULATION_ID
    assert task["project_id"] == DEFAULT_CONSENSUS_PROJECT_ID
    assert task["total_agents"] == 10


def test_get_current_task_uses_default_catalog_when_simulation_id_missing(monkeypatch):
    service, _ = build_service(monkeypatch)
    created = service.start_task(
        simulation_id=DEFAULT_CONSENSUS_SIMULATION_ID,
        question_text="Question A",
        threshold_percent=60,
    )

    current = service.get_current_task("")

    assert current is not None
    assert current["task_uid"] == created["task_uid"]


def test_list_tasks_uses_default_catalog_when_simulation_id_missing(monkeypatch):
    service, _ = build_service(monkeypatch)
    created = service.start_task(
        simulation_id=DEFAULT_CONSENSUS_SIMULATION_ID,
        question_text="Question A",
        threshold_percent=60,
    )

    tasks = service.list_tasks("")

    assert len(tasks) == 1
    assert tasks[0]["task_uid"] == created["task_uid"]


def test_start_task_rejects_second_running_task(monkeypatch):
    service, _ = build_service(monkeypatch)
    service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    with pytest.raises(ValueError, match="already has a running consensus task"):
        service.start_task(
            simulation_id="sim_1",
            question_text="Question B",
            threshold_percent=60,
        )


def test_run_due_round_completes_when_threshold_reached_with_majority(monkeypatch):
    judgments = [
        {
            "agent_source_id": "u1",
            "agent_name": "Alice",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
        {
            "agent_source_id": "u2",
            "agent_name": "Bob",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
    ]
    service, repo = build_service(monkeypatch, round_judgments=judgments)
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    did_work = service.run_due_round()
    assert did_work is True
    updated = repo.get_task_by_uid(repo, task["task_uid"])
    assert updated["status"] == "completed"
    assert updated["final_answer"] == "yes"
    assert updated["completed_round_index"] == 1


def test_run_due_round_keeps_running_on_tie(monkeypatch):
    judgments = [
        {
            "agent_source_id": "u1",
            "agent_name": "Alice",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
        {
            "agent_source_id": "u2",
            "agent_name": "Bob",
            "candidate_answer": "no",
            "is_answerable": 1,
            "content_short": "no",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "no"},
        },
    ]
    service, repo = build_service(monkeypatch, round_judgments=judgments)
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    service.run_due_round()
    updated = repo.get_task_by_uid(repo, task["task_uid"])
    assert updated["status"] == "running"
    assert updated["final_answer"] is None
    assert updated["current_round_index"] == 1


def test_run_due_round_schedules_next_round_with_task_poll_interval(monkeypatch):
    judgments = [
        {
            "agent_source_id": "u1",
            "agent_name": "Alice",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
        {
            "agent_source_id": "u2",
            "agent_name": "Bob",
            "candidate_answer": "no",
            "is_answerable": 1,
            "content_short": "no",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "no"},
        },
    ]
    service, repo = build_service(monkeypatch, round_judgments=judgments)
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
        poll_interval_seconds=7200,
    )

    service.run_due_round()

    updated = repo.get_task_by_uid(repo, task["task_uid"])
    last_polled_at = datetime.fromisoformat(updated["last_polled_at"])
    next_run_at = datetime.fromisoformat(updated["next_run_at"])
    assert (next_run_at - last_polled_at).total_seconds() == 7200


def test_get_agents_view_returns_profession_without_name_fallback(monkeypatch):
    personas = [
        {"user_id": "u1", "name": "Alice", "profession": "AI engineer"},
        {"user_id": "u2", "name": "Bob"},
    ]
    judgments = [
        {
            "agent_source_id": "u1",
            "agent_name": "Alice",
            "candidate_answer": "yes",
            "is_answerable": 1,
            "content_short": "yes",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "yes"},
        },
        {
            "agent_source_id": "u2",
            "agent_name": "Bob",
            "candidate_answer": "no",
            "is_answerable": 1,
            "content_short": "no",
            "evidence_title": None,
            "evidence_url": None,
            "evidence_time": None,
            "status": "completed",
            "error_text": None,
            "raw_response_json": {"candidate_answer": "no"},
        },
    ]
    service, _ = build_service(monkeypatch, personas=personas, round_judgments=judgments)
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    service.run_due_round()

    cards = service.get_agents_view(task["task_uid"])

    assert [card["profession"] for card in cards] == ["AI engineer", "Persona"]


def test_stop_task_marks_task_stopped(monkeypatch):
    service, repo = build_service(monkeypatch)
    task = service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    stopped = service.stop_task(task["task_uid"])
    assert stopped["status"] == "stopped"
    assert stopped["end_reason"] == "manual_stop"
    updated = repo.get_task_by_uid(repo, task["task_uid"])
    assert updated["status"] == "stopped"


def test_interrupt_running_tasks_marks_tasks_interrupted(monkeypatch):
    service, repo = build_service(monkeypatch)
    service.start_task(
        simulation_id="sim_1",
        question_text="Question A",
        threshold_percent=60,
    )
    count = service.interrupt_running_tasks()
    assert count == 1
    assert repo.tasks[0]["status"] == "interrupted"
    assert repo.tasks[0]["end_reason"] == "service_restart"
