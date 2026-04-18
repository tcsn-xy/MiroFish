from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from ..config import BACKEND_DIR, Config
from ..utils.logger import get_logger
from .exceptions import ConsensusStorageError

logger = get_logger("mirofish.consensus.repository")


class ConsensusRepository:
    def __init__(self) -> None:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ModuleNotFoundError as exc:
            raise ConsensusStorageError("pymysql is not installed") from exc

        self._pymysql = pymysql
        self._dict_cursor = DictCursor
        self._schema_path = Path(BACKEND_DIR) / "sql" / "consensus_schema.sql"
        self._tables_ensured = False

    def _connect(self):
        kwargs = Config.get_mysql_config()
        kwargs["cursorclass"] = self._dict_cursor
        return self._pymysql.connect(**kwargs)

    @contextmanager
    def session(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_tables_exist(self) -> None:
        if self._tables_ensured:
            return
        if not self._schema_path.exists():
            raise ConsensusStorageError(f"consensus schema file not found: {self._schema_path}")
        ddl = self._schema_path.read_text(encoding="utf-8")
        with self.session() as conn:
            with conn.cursor() as cursor:
                for statement in [part.strip() for part in ddl.split(";") if part.strip()]:
                    cursor.execute(statement)
        self._tables_ensured = True

    def create_task(
        self,
        conn,
        question: str,
        threshold_percent: int,
        total_agents: int,
        required_ready_count: int,
        round_interval_seconds: int,
        model_name: str,
    ) -> int:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO consensus_tasks
                (
                    question, threshold_percent, total_agents, required_ready_count,
                    round_interval_seconds, model_name, status, next_round_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'running', CURRENT_TIMESTAMP)
                """,
                (
                    question,
                    threshold_percent,
                    total_agents,
                    required_ready_count,
                    round_interval_seconds,
                    model_name,
                ),
            )
            return int(cursor.lastrowid)

    def get_running_task(self, conn) -> Optional[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM consensus_tasks
                WHERE status='running'
                ORDER BY id DESC
                LIMIT 1
                """
            )
            return cursor.fetchone()

    def get_latest_task(self, conn) -> Optional[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM consensus_tasks
                ORDER BY
                  CASE WHEN status='running' THEN 0 ELSE 1 END ASC,
                  updated_at DESC,
                  id DESC
                LIMIT 1
                """
            )
            return cursor.fetchone()

    def get_current_task(self, conn) -> Optional[Dict[str, Any]]:
        running = self.get_running_task(conn)
        if running:
            return running
        return self.get_latest_task(conn)

    def get_task_by_id(self, conn, task_id: int) -> Optional[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM consensus_tasks WHERE id=%s LIMIT 1", (task_id,))
            return cursor.fetchone()

    def get_due_running_task_for_update(self, conn) -> Optional[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM consensus_tasks
                WHERE status='running'
                  AND (next_round_at IS NULL OR next_round_at <= CURRENT_TIMESTAMP)
                ORDER BY next_round_at ASC, id ASC
                LIMIT 1
                FOR UPDATE
                """
            )
            return cursor.fetchone()

    def mark_round_started(self, conn, task_id: int, round_no: int) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET current_round=%s,
                    last_round_started_at=CURRENT_TIMESTAMP,
                    error_text=NULL
                WHERE id=%s
                """,
                (round_no, task_id),
            )

    def insert_agent_log(self, conn, task_id: int, round_no: int, agent_id: str, payload: Dict[str, Any]) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO consensus_agent_logs
                (
                    task_id, round_no, agent_id, agent_name, content_short,
                    is_ready_to_answer, candidate_answer, evidence_title,
                    evidence_url, evidence_time, error_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    task_id,
                    round_no,
                    agent_id,
                    payload["agent_name"],
                    payload["content_short"],
                    1 if payload["is_ready_to_answer"] else 0,
                    payload["candidate_answer"],
                    payload["evidence_title"],
                    payload["evidence_url"],
                    payload["evidence_time"],
                    payload["error_text"],
                ),
            )

    def finish_round_running(
        self,
        conn,
        task_id: int,
        ready_count: int,
        accepted_ratio: float,
        next_round_at_expression: str,
        consecutive_error_rounds: int,
        error_text: Optional[str],
    ) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE consensus_tasks
                SET latest_ready_count=%s,
                    accepted_ratio=%s,
                    consecutive_error_rounds=%s,
                    error_text=%s,
                    last_round_finished_at=CURRENT_TIMESTAMP,
                    next_round_at={next_round_at_expression}
                WHERE id=%s
                """,
                (
                    ready_count,
                    accepted_ratio,
                    consecutive_error_rounds,
                    error_text,
                    task_id,
                ),
            )

    def mark_answered(
        self,
        conn,
        task_id: int,
        ready_count: int,
        accepted_ratio: float,
        final_answer: str,
        final_evidence_text: str,
    ) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET status='answered',
                    latest_ready_count=%s,
                    accepted_ratio=%s,
                    final_answer=%s,
                    final_evidence_text=%s,
                    answered_at=CURRENT_TIMESTAMP,
                    last_round_finished_at=CURRENT_TIMESTAMP,
                    next_round_at=NULL,
                    error_text=NULL
                WHERE id=%s
                """,
                (ready_count, accepted_ratio, final_answer, final_evidence_text, task_id),
            )

    def mark_failed(self, conn, task_id: int, error_text: str) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET status='failed',
                    error_text=%s,
                    failed_at=CURRENT_TIMESTAMP,
                    next_round_at=NULL,
                    last_round_finished_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (error_text, task_id),
            )

    def stop_running_task(self, conn) -> int:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET status='stopped',
                    stopped_at=CURRENT_TIMESTAMP,
                    next_round_at=NULL
                WHERE status='running'
                """
            )
            return int(cursor.rowcount)

    def get_logs_for_task(self, conn, task_id: int) -> List[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM consensus_agent_logs
                WHERE task_id=%s
                ORDER BY round_no DESC, created_at DESC, id DESC
                """,
                (task_id,),
            )
            return list(cursor.fetchall())

    def get_logs_for_round(self, conn, task_id: int, round_no: int) -> List[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM consensus_agent_logs
                WHERE task_id=%s AND round_no=%s
                ORDER BY agent_name ASC
                """,
                (task_id, round_no),
            )
            return list(cursor.fetchall())
