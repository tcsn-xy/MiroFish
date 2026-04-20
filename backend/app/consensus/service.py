from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import Any, Dict, List, Optional

from ..config import Config
from ..models.project import ProjectManager
from ..services.simulation_files import load_profiles
from ..services.simulation_manager import SimulationManager
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.locale import get_language_instruction
from .default_catalog import (
    DEFAULT_CONSENSUS_PROJECT_ID,
    DEFAULT_CONSENSUS_SIMULATION_ID,
    get_default_consensus_catalog,
    get_default_consensus_personas,
    is_default_consensus_simulation_id,
    resolve_consensus_simulation_id,
)
from .exceptions import ConsensusConfigurationError
from .repository import ConsensusRepository
from .utils import (
    generate_task_uid,
    get_persona_name,
    get_persona_profession,
    get_persona_source_id,
    normalize_candidate_answer,
    sanitize_agent_payload,
    truncate_text,
    utcnow,
)

logger = get_logger("mirofish.consensus.service")


MIN_CONSENSUS_POLL_INTERVAL_SECONDS = 30
MAX_CONSENSUS_POLL_INTERVAL_SECONDS = 30 * 24 * 60 * 60


CONSENSUS_SYSTEM_PROMPT = """
You are simulating one social-media persona making a yes/no judgment.
You are not required to be factually correct. You should search the web and then give your own judgment.
Return JSON only with these keys:
- candidate_answer: "yes", "no", or null
- is_answerable: boolean
- content_short: short one-sentence judgment under 255 chars
- evidence_title: short title or null
- evidence_url: url string or null
- evidence_time: short time string or null
If you cannot decide, set candidate_answer to null and is_answerable to false.
""".strip()


class ConsensusService:
    def __init__(self) -> None:
        self.repository = ConsensusRepository()
        self.simulation_manager = SimulationManager()
        self._round_lock = threading.Lock()

    def ensure_ready(self) -> None:
        self.repository.ensure_ready()

    def _get_simulation_dir(self, simulation_id: str) -> str:
        if is_default_consensus_simulation_id(simulation_id):
            raise ValueError("default consensus catalog does not use a simulation directory")
        state = self.simulation_manager.get_simulation(simulation_id)
        if not state:
            raise ValueError(f"simulation not found: {simulation_id}")
        simulation_dir = self.simulation_manager._get_simulation_dir(simulation_id)
        project = ProjectManager.get_project(state.project_id)
        if not project:
            raise ValueError(f"project not found for simulation: {simulation_id}")
        return simulation_dir

    def _load_reddit_personas(self, simulation_id: str) -> Dict[str, Any]:
        if is_default_consensus_simulation_id(simulation_id):
            return {
                "project_id": DEFAULT_CONSENSUS_PROJECT_ID,
                "personas": get_default_consensus_personas(),
                "catalog": get_default_consensus_catalog(),
            }
        state = self.simulation_manager.get_simulation(simulation_id)
        if not state:
            raise ValueError(f"simulation not found: {simulation_id}")
        simulation_dir = self.simulation_manager._get_simulation_dir(simulation_id)
        personas = load_profiles(simulation_dir, "reddit")
        if not personas:
            personas = get_default_consensus_personas()
        return {
            "project_id": state.project_id,
            "personas": personas,
        }

    def _load_persona_bundle_for_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return self._load_reddit_personas(task["simulation_id"])

    def _normalize_poll_interval_seconds(self, value: Any = None) -> int:
        if value in (None, ""):
            value = Config.CONSENSUS_POLL_INTERVAL_SECONDS
        if isinstance(value, bool):
            raise ValueError("poll_interval_seconds must be an integer")
        if isinstance(value, int):
            interval = value
        elif isinstance(value, str) and value.strip().isdigit():
            interval = int(value.strip())
        else:
            raise ValueError("poll_interval_seconds must be an integer")
        if interval < MIN_CONSENSUS_POLL_INTERVAL_SECONDS:
            raise ValueError(
                f"poll_interval_seconds must be at least {MIN_CONSENSUS_POLL_INTERVAL_SECONDS}"
            )
        if interval > MAX_CONSENSUS_POLL_INTERVAL_SECONDS:
            raise ValueError(
                f"poll_interval_seconds must be at most {MAX_CONSENSUS_POLL_INTERVAL_SECONDS}"
            )
        return interval

    def _build_profession_by_agent_id(
        self,
        personas: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        profession_by_agent_id: Dict[str, str] = {}
        for index, profile in enumerate(personas):
            agent_source_id = get_persona_source_id(profile, index)
            profession_by_agent_id[agent_source_id] = get_persona_profession(profile)
        return profession_by_agent_id

    def start_task(
        self,
        *,
        simulation_id: str,
        question_text: str,
        threshold_percent: int,
        poll_interval_seconds: Any = None,
    ) -> Dict[str, Any]:
        if not question_text or not question_text.strip():
            raise ValueError("question_text is required")
        if threshold_percent < 1 or threshold_percent > 100:
            raise ValueError("threshold_percent must be between 1 and 100")
        normalized_poll_interval_seconds = self._normalize_poll_interval_seconds(
            poll_interval_seconds
        )

        simulation_id = resolve_consensus_simulation_id(simulation_id)
        persona_bundle = self._load_reddit_personas(simulation_id)
        personas = persona_bundle["personas"]
        now = utcnow()
        task_uid = generate_task_uid()

        with self.repository.session() as conn:
            if self.repository.has_running_task(conn, simulation_id):
                raise ValueError(
                    f"simulation {simulation_id} already has a running consensus task"
                )
            self.repository.create_task(
                conn,
                task_uid=task_uid,
                project_id=persona_bundle["project_id"],
                simulation_id=simulation_id,
                question_text=question_text.strip(),
                threshold_percent=threshold_percent,
                poll_interval_seconds=normalized_poll_interval_seconds,
                total_agents=len(personas),
                next_run_at=now,
            )
            task = self.repository.get_task_by_uid(conn, task_uid)
        return task

    def stop_task(self, task_uid: str) -> Optional[Dict[str, Any]]:
        if not task_uid:
            raise ValueError("task_uid is required")
        with self.repository.session() as conn:
            task = self.repository.get_task_by_uid(conn, task_uid)
            if not task:
                return None
            self.repository.stop_task(conn, task["id"], "manual_stop", utcnow())
            return self.repository.get_task_by_uid(conn, task_uid)

    def get_task(self, task_uid: str) -> Optional[Dict[str, Any]]:
        with self.repository.session() as conn:
            return self.repository.get_task_by_uid(conn, task_uid)

    def get_current_task(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        simulation_id = resolve_consensus_simulation_id(simulation_id)
        with self.repository.session() as conn:
            return self.repository.get_current_or_latest_task(conn, simulation_id)

    def list_tasks(self, simulation_id: str) -> List[Dict[str, Any]]:
        simulation_id = resolve_consensus_simulation_id(simulation_id)
        with self.repository.session() as conn:
            return self.repository.list_tasks(conn, simulation_id)

    def get_default_catalog(self) -> Dict[str, Any]:
        return get_default_consensus_catalog()

    def get_agents_view(self, task_uid: str) -> List[Dict[str, Any]]:
        with self.repository.session() as conn:
            task = self.repository.get_task_by_uid(conn, task_uid)
            if not task:
                return []
            judgments = self.repository.list_judgments(conn, task["id"])

        try:
            persona_bundle = self._load_persona_bundle_for_task(task)
            profession_by_agent_id = self._build_profession_by_agent_id(
                persona_bundle.get("personas", [])
            )
        except Exception:
            profession_by_agent_id = {}

        grouped: Dict[str, Dict[str, Any]] = {}
        for item in judgments:
            agent_id = item["agent_source_id"]
            card = grouped.setdefault(
                agent_id,
                {
                    "agent_source_id": agent_id,
                    "agent_name": item["agent_name"],
                    "profession": profession_by_agent_id.get(agent_id, "Persona"),
                    "card_answer": None,
                    "history": [],
                },
            )
            card["history"].append(
                {
                    "round_index": item["round_index"],
                    "candidate_answer": item["candidate_answer"],
                    "is_answerable": bool(item["is_answerable"]),
                    "content_short": item["content_short"],
                    "evidence_title": item["evidence_title"],
                    "evidence_url": item["evidence_url"],
                    "evidence_time": item["evidence_time"],
                    "status": item["status"],
                    "error_text": item["error_text"],
                    "polled_at": item["polled_at"],
                    "raw_response_json": item["raw_response_json"],
                }
            )

        target_round = task.get("completed_round_index") if task.get("status") == "completed" else None
        cards = []
        for card in grouped.values():
            history = sorted(
                card["history"],
                key=lambda row: (
                    int(row["round_index"]),
                    row["polled_at"] or "",
                ),
                reverse=True,
            )
            card_answer = None
            if target_round is not None:
                for row in history:
                    if row["round_index"] == target_round:
                        card_answer = row["candidate_answer"]
                        break
            else:
                card_answer = history[0]["candidate_answer"] if history else None
            cards.append(
                {
                    "agent_source_id": card["agent_source_id"],
                    "agent_name": card["agent_name"],
                    "profession": card["profession"],
                    "card_answer": card_answer,
                    "history": history,
                }
            )

        cards.sort(key=lambda item: (item["profession"], item["agent_source_id"]))
        return cards

    def interrupt_running_tasks(self) -> int:
        with self.repository.session() as conn:
            return self.repository.interrupt_running_tasks(conn, utcnow())

    def _build_messages(
        self,
        *,
        question_text: str,
        profile: Dict[str, Any],
        agent_name: str,
        agent_source_id: str,
    ) -> List[Dict[str, str]]:
        persona_json = str(profile)
        user_prompt = (
            f"{get_language_instruction()}\n"
            f"Question: {question_text}\n"
            f"Persona name: {agent_name}\n"
            f"Persona id: {agent_source_id}\n"
            f"Persona profile: {persona_json}\n"
            "Search the internet, think from this persona's perspective, and return the required JSON."
        )
        return [
            {"role": "system", "content": CONSENSUS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _judge_single_persona(
        self,
        *,
        question_text: str,
        profile: Dict[str, Any],
        agent_name: str,
        agent_source_id: str,
    ) -> Dict[str, Any]:
        client = LLMClient(model=Config.CONSENSUS_MODEL_NAME)
        messages = self._build_messages(
            question_text=question_text,
            profile=profile,
            agent_name=agent_name,
            agent_source_id=agent_source_id,
        )
        response = client.chat_json(
            messages=messages,
            temperature=Config.CONSENSUS_TEMPERATURE,
            max_tokens=Config.CONSENSUS_MAX_TOKENS,
            extra_body=Config.CONSENSUS_NATIVE_SEARCH_EXTRA_BODY,
        )
        response["candidate_answer"] = normalize_candidate_answer(
            response.get("candidate_answer")
        )
        if response.get("candidate_answer") in {"yes", "no"}:
            response["is_answerable"] = True
        return sanitize_agent_payload(response)

    def _judge_personas_for_round(
        self,
        *,
        question_text: str,
        personas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not personas:
            return []

        max_workers = max(1, min(Config.CONSENSUS_MAX_PARALLELISM, len(personas)))
        results: List[Optional[Dict[str, Any]]] = [None] * len(personas)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}
            for index, profile in enumerate(personas):
                agent_source_id = get_persona_source_id(profile, index)
                agent_name = get_persona_name(profile, index)
                future = executor.submit(
                    self._judge_single_persona,
                    question_text=question_text,
                    profile=profile,
                    agent_name=agent_name,
                    agent_source_id=agent_source_id,
                )
                future_map[future] = (index, agent_source_id, agent_name)

            for future in as_completed(future_map):
                index, agent_source_id, agent_name = future_map[future]
                try:
                    payload = future.result()
                except Exception as exc:
                    payload = sanitize_agent_payload(
                        {
                            "error_text": truncate_text(str(exc), limit=255),
                        },
                        status="error",
                    )
                results[index] = {
                    "agent_source_id": agent_source_id,
                    "agent_name": agent_name,
                    **payload,
                }

        return [item for item in results if item is not None]

    def _aggregate_round(self, judgments: List[Dict[str, Any]]) -> Dict[str, int]:
        yes_count = sum(1 for item in judgments if item.get("candidate_answer") == "yes")
        no_count = sum(1 for item in judgments if item.get("candidate_answer") == "no")
        return {
            "answerable_count": yes_count + no_count,
            "yes_count": yes_count,
            "no_count": no_count,
        }

    def run_due_round(self) -> bool:
        with self._round_lock:
            due_task = None
            with self.repository.session() as conn:
                due_tasks = self.repository.list_due_running_tasks(conn, utcnow())
                due_task = due_tasks[0] if due_tasks else None

            if not due_task:
                return False

            task_id = due_task["id"]
            round_index = int(due_task["current_round_index"]) + 1

            try:
                persona_bundle = self._load_persona_bundle_for_task(due_task)
                personas = persona_bundle["personas"]
                judgments = self._judge_personas_for_round(
                    question_text=due_task["question_text"],
                    personas=personas,
                )
                polled_at = utcnow()
                aggregate = self._aggregate_round(judgments)
                ratio = (
                    aggregate["answerable_count"] / float(due_task["total_agents"])
                    if due_task["total_agents"]
                    else 0.0
                )
                reached_threshold = ratio >= (float(due_task["threshold_percent"]) / 100.0)
                final_answer = None
                status = "running"
                final_reason_short = None
                end_reason = None
                ended_at = None
                next_run_at = polled_at + timedelta(
                    seconds=int(due_task["poll_interval_seconds"])
                )

                if reached_threshold:
                    if aggregate["yes_count"] > aggregate["no_count"]:
                        final_answer = "yes"
                    elif aggregate["no_count"] > aggregate["yes_count"]:
                        final_answer = "no"

                if final_answer:
                    status = "completed"
                    end_reason = "completed_threshold"
                    ended_at = polled_at
                    next_run_at = None
                    final_reason_short = truncate_text(
                        (
                            f"第 {round_index} 轮达到阈值，"
                            f"是 {aggregate['yes_count']}，否 {aggregate['no_count']}"
                        ),
                        limit=255,
                    )

                judgment_rows = [
                    {
                        "task_id": task_id,
                        "round_index": round_index,
                        "agent_source_id": item["agent_source_id"],
                        "agent_name": item["agent_name"],
                        "candidate_answer": item["candidate_answer"],
                        "is_answerable": item["is_answerable"],
                        "content_short": item["content_short"],
                        "evidence_title": item["evidence_title"],
                        "evidence_url": item["evidence_url"],
                        "evidence_time": item["evidence_time"],
                        "status": item["status"],
                        "error_text": item["error_text"],
                        "raw_response_json": item["raw_response_json"],
                        "polled_at": polled_at,
                    }
                    for item in judgments
                ]

                with self.repository.session() as conn:
                    self.repository.create_round_judgments(conn, judgment_rows)
                    self.repository.update_task_after_round(
                        conn,
                        task_id=task_id,
                        round_index=round_index,
                        answerable_count=aggregate["answerable_count"],
                        yes_count=aggregate["yes_count"],
                        no_count=aggregate["no_count"],
                        polled_at=polled_at,
                        next_run_at=next_run_at,
                        status=status,
                        final_answer=final_answer,
                        final_reason_short=final_reason_short,
                        end_reason=end_reason,
                        ended_at=ended_at,
                        error_text=None,
                    )
                return True
            except Exception as exc:
                with self.repository.session() as conn:
                    self.repository.update_task_error(
                        conn,
                        task_id,
                        truncate_text(str(exc), limit=255, fallback="round execution failed"),
                    )
                logger.error(f"consensus round failed for task {due_task['task_uid']}: {exc}")
                return False


_consensus_service: Optional[ConsensusService] = None


def get_consensus_service() -> ConsensusService:
    global _consensus_service
    if _consensus_service is None:
        _consensus_service = ConsensusService()
    return _consensus_service
