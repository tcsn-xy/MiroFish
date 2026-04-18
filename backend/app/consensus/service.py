from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from pymysql.err import IntegrityError

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .exceptions import ConsensusConfigurationError, ConsensusStorageError
from .repository import ConsensusRepository
from .utils import (
    BUILTIN_AGENTS,
    FAILURE_CONTENT,
    has_valid_evidence,
    load_extra_body,
    required_ready_count,
    sanitize_agent_payload,
)

logger = get_logger("mirofish.consensus.service")

FAILURE_THRESHOLD_ROUNDS = 3

AGENT_JSON_SCHEMA = (
    "你必须只返回一个 JSON object，字段必须完整："
    "content_short, is_ready_to_answer, candidate_answer, evidence_title, evidence_url, evidence_time。"
    "content_short 只能是一句中文短句，不要 Markdown，不要换行，不要长推理。"
)


class ConsensusService:
    def __init__(
        self,
        repository: Optional[ConsensusRepository] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.repository = repository or ConsensusRepository()
        self._llm_client = llm_client
        self._extra_body_cache: Optional[Dict[str, Any]] = None

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient(model=Config.CONSENSUS_MODEL_NAME)
        return self._llm_client

    @property
    def extra_body(self) -> Dict[str, Any]:
        if self._extra_body_cache is None:
            self._extra_body_cache = load_extra_body(Config.CONSENSUS_NATIVE_SEARCH_EXTRA_BODY)
        return self._extra_body_cache

    def ensure_ready(self) -> None:
        if not Config.CONSENSUS_ENABLED:
            raise ConsensusConfigurationError("consensus feature is disabled")
        if Config.CONSENSUS_AGENT_COUNT != len(BUILTIN_AGENTS):
            raise ConsensusConfigurationError("CONSENSUS_AGENT_COUNT must be 10 in V1")
        if Config.CONSENSUS_ROUND_INTERVAL_SECONDS != 86400:
            raise ConsensusConfigurationError("CONSENSUS_ROUND_INTERVAL_SECONDS must be 86400 in V1")
        self.repository.ensure_tables_exist()

    def verify_native_search(self) -> None:
        self.ensure_ready()
        try:
            result = self.llm.consensus_native_search_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你正在执行原生联网能力自检。"
                            "如果可以联网搜索并返回 JSON，请输出 {\"ok\": true, \"message\": \"...\"}。"
                        ),
                    },
                    {"role": "user", "content": "请用联网搜索自检能力，并返回 JSON。"},
                ],
                temperature=0,
                max_tokens=120,
                extra_body=self.extra_body,
            )
        except Exception as exc:
            raise ConsensusConfigurationError(f"consensus native search check failed: {exc}") from exc
        if result.get("ok") is not True:
            raise ConsensusConfigurationError("consensus native search check did not return ok=true")

    def start_task(self, question: str, threshold_percent: int) -> Dict[str, Any]:
        self.verify_native_search()
        question = (question or "").strip()
        if not question:
            raise ValueError("question is required")
        if not isinstance(threshold_percent, int) or threshold_percent < 0 or threshold_percent > 100:
            raise ValueError("threshold_percent must be an integer between 0 and 100")

        required = required_ready_count(Config.CONSENSUS_AGENT_COUNT, threshold_percent)
        try:
            with self.repository.session() as conn:
                task_id = self.repository.create_task(
                    conn=conn,
                    question=question,
                    threshold_percent=threshold_percent,
                    total_agents=Config.CONSENSUS_AGENT_COUNT,
                    required_ready_count=required,
                    round_interval_seconds=Config.CONSENSUS_ROUND_INTERVAL_SECONDS,
                    model_name=Config.CONSENSUS_MODEL_NAME,
                )
        except IntegrityError as exc:
            raise ConsensusStorageError("consensus task already running") from exc

        return {
            "task_id": task_id,
            "status": "running",
            "required_ready_count": required,
        }

    def stop_current_task(self) -> None:
        self.ensure_ready()
        with self.repository.session() as conn:
            updated = self.repository.stop_running_task(conn)
        if updated == 0:
            raise LookupError("当前没有运行中的任务")

    def get_current_task(self) -> Optional[Dict[str, Any]]:
        self.ensure_ready()
        with self.repository.session() as conn:
            row = self.repository.get_current_task(conn)
        if not row:
            return None
        return self._serialize_task(row)

    def get_current_agents_view(self) -> Optional[Dict[str, Any]]:
        self.ensure_ready()
        with self.repository.session() as conn:
            task = self.repository.get_current_task(conn)
            if not task:
                return None
            logs = self.repository.get_logs_for_task(conn, int(task["id"]))
        return self._build_agents_payload(task, logs)

    def run_due_round(self) -> bool:
        self.ensure_ready()
        with self.repository.session() as conn:
            task = self.repository.get_due_running_task_for_update(conn)
            if not task:
                return False
            task_id = int(task["id"])
            round_no = int(task["current_round"]) + 1
            self.repository.mark_round_started(conn, task_id, round_no)

        round_logs, round_error = self._execute_round(task_id=task_id, question=task["question"], round_no=round_no)
        ready_count = sum(1 for log in round_logs if log["is_ready_to_answer"])
        accepted_ratio = round(ready_count * 100.0 / Config.CONSENSUS_AGENT_COUNT, 2)
        evidence_ready_logs = [log for log in round_logs if has_valid_evidence(log)]
        threshold_met = ready_count >= int(task["required_ready_count"])

        with self.repository.session() as conn:
            current = self.repository.get_task_by_id(conn, task_id)
            if not current or current["status"] != "running":
                self.repository.finish_round_running(
                    conn=conn,
                    task_id=task_id,
                    ready_count=ready_count,
                    accepted_ratio=accepted_ratio,
                    next_round_at_expression="NULL",
                    consecutive_error_rounds=int(current["consecutive_error_rounds"]) if current else 0,
                    error_text=round_error,
                )
                return True

            next_error_rounds = int(current["consecutive_error_rounds"])
            if round_error:
                next_error_rounds += 1
            else:
                next_error_rounds = 0

            if next_error_rounds >= FAILURE_THRESHOLD_ROUNDS:
                self.repository.mark_failed(
                    conn=conn,
                    task_id=task_id,
                    error_text=round_error or "consensus round failed too many times",
                )
                return True

            if threshold_met and evidence_ready_logs:
                try:
                    final_answer, final_evidence_text = self._synthesize_final_answer(task["question"], evidence_ready_logs)
                except Exception as exc:
                    self.repository.mark_failed(conn=conn, task_id=task_id, error_text=str(exc))
                    return True

                current = self.repository.get_task_by_id(conn, task_id)
                if current and current["status"] == "running":
                    self.repository.mark_answered(
                        conn=conn,
                        task_id=task_id,
                        ready_count=ready_count,
                        accepted_ratio=accepted_ratio,
                        final_answer=final_answer,
                        final_evidence_text=final_evidence_text,
                    )
                return True

            self.repository.finish_round_running(
                conn=conn,
                task_id=task_id,
                ready_count=ready_count,
                accepted_ratio=accepted_ratio,
                next_round_at_expression="DATE_ADD(CURRENT_TIMESTAMP, INTERVAL round_interval_seconds SECOND)",
                consecutive_error_rounds=next_error_rounds,
                error_text=round_error,
            )
        return True

    def _execute_round(self, task_id: int, question: str, round_no: int) -> tuple[List[Dict[str, Any]], Optional[str]]:
        logs: List[Dict[str, Any]] = []
        failures: List[str] = []

        with ThreadPoolExecutor(max_workers=len(BUILTIN_AGENTS)) as executor:
            futures = {
                executor.submit(self._run_agent, agent, question): agent
                for agent in BUILTIN_AGENTS
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    payload = future.result()
                except Exception as exc:
                    failures.append(f"{agent['name']}: {exc}")
                    payload = sanitize_agent_payload(agent["name"], {"content_short": FAILURE_CONTENT}, error_text=str(exc))
                payload["agent_id"] = agent["id"]
                logs.append(payload)

        logs.sort(key=lambda item: item["agent_id"])
        with self.repository.session() as conn:
            for log in logs:
                self.repository.insert_agent_log(conn, task_id, round_no, log["agent_id"], log)

        return logs, "; ".join(failures) if failures else None

    def _run_agent(self, agent: Dict[str, str], question: str) -> Dict[str, Any]:
        result = self.llm.consensus_native_search_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是“{agent['name']}”人格。{agent['persona']}"
                        "请严格基于你联网搜索到的近期公开信息作答。"
                        "如果证据不足，就明确保持不可答。"
                        + AGENT_JSON_SCHEMA
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n"
                        "请先联网搜索，再按 JSON 返回："
                        "你现在是否认为这个问题已经可以回答、你建议的候选答案、最关键的一条证据标题、链接、时间。"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=900,
            extra_body=self.extra_body,
        )
        return sanitize_agent_payload(agent["name"], result)

    def _synthesize_final_answer(self, question: str, ready_logs: List[Dict[str, Any]]) -> tuple[str, str]:
        evidence_lines = []
        for log in ready_logs:
            evidence_lines.append(
                f"- {log['agent_name']}: 候选答案={log.get('candidate_answer') or '无'}；"
                f"证据={log.get('evidence_title') or '无'}；"
                f"链接={log.get('evidence_url') or '无'}；"
                f"时间={log.get('evidence_time') or '未知'}"
            )
        prompt = (
            f"问题：{question}\n"
            "以下是多个人格 agent 基于联网搜索后给出的可回答结论与证据。\n"
            "请生成一个 JSON object，字段为 final_answer 与 final_evidence_text。\n"
            "要求 final_answer 简洁直接、适合前台展示；final_evidence_text 用 2-5 句总结可展示证据，不要 Markdown 列表。\n"
            + "\n".join(evidence_lines)
        )
        result = self.llm.chat_json(
            messages=[
                {"role": "system", "content": "你是共识问答总结器，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        final_answer = (result.get("final_answer") or "").strip()
        final_evidence_text = (result.get("final_evidence_text") or "").strip()
        if not final_answer or not final_evidence_text:
            raise ConsensusStorageError("final synthesis returned empty answer or evidence")
        return final_answer, final_evidence_text

    def _serialize_task(self, row: Dict[str, Any]) -> Dict[str, Any]:
        ready_count = int(row.get("latest_ready_count") or 0)
        return {
            "task_id": int(row["id"]),
            "question": row["question"],
            "status": row["status"],
            "current_round": int(row["current_round"]),
            "threshold_percent": int(row["threshold_percent"]),
            "required_ready_count": int(row["required_ready_count"]),
            "ready_count": ready_count,
            "total_agents": int(row["total_agents"]),
            "accepted_ratio": float(row.get("accepted_ratio") or 0.0),
            "is_threshold_met": ready_count >= int(row["required_ready_count"]),
            "final_answer": row.get("final_answer"),
            "final_evidence_text": row.get("final_evidence_text"),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        }

    def _build_agents_payload(self, task: Dict[str, Any], logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        latest_by_agent: Dict[str, Dict[str, Any]] = {}
        history_by_agent: Dict[str, List[Dict[str, Any]]] = {agent["id"]: [] for agent in BUILTIN_AGENTS}

        for log in logs:
            history_item = {
                "round_no": int(log["round_no"]),
                "content_short": log["content_short"],
                "is_ready_to_answer": bool(log["is_ready_to_answer"]),
                "candidate_answer": log.get("candidate_answer"),
                "evidence_title": log.get("evidence_title"),
                "evidence_url": log.get("evidence_url"),
                "evidence_time": log.get("evidence_time"),
                "error_text": log.get("error_text"),
                "created_at": log["created_at"].isoformat() if log.get("created_at") else None,
            }
            history_by_agent[log["agent_id"]].append(history_item)
            latest_by_agent.setdefault(log["agent_id"], history_item)

        agents = []
        for agent in BUILTIN_AGENTS:
            latest = latest_by_agent.get(agent["id"])
            agents.append(
                {
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "latest": latest
                    or {
                        "round_no": 0,
                        "content_short": "等待首轮结果",
                        "is_ready_to_answer": False,
                        "candidate_answer": None,
                        "evidence_title": None,
                        "evidence_url": None,
                        "evidence_time": None,
                        "error_text": None,
                        "created_at": None,
                    },
                    "history": history_by_agent[agent["id"]],
                }
            )

        return {
            "task": self._serialize_task(task),
            "agents": agents,
        }


_consensus_service: Optional[ConsensusService] = None


def get_consensus_service() -> ConsensusService:
    global _consensus_service
    if _consensus_service is None:
        _consensus_service = ConsensusService()
    return _consensus_service
