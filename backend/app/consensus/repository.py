from __future__ import annotations

import os
import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from ..config import Config, resolve_repo_path
from ..utils.logger import get_logger
from .exceptions import ConsensusConfigurationError, ConsensusStorageError

logger = get_logger("mirofish.consensus.repository")


class ConsensusRepository:
    REQUIRED_TASK_COLUMNS = {
        "id",
        "task_uid",
        "project_id",
        "simulation_id",
        "question_text",
        "persona_platform",
        "threshold_percent",
        "poll_interval_seconds",
        "total_agents",
        "current_round_index",
        "last_answerable_agents",
        "last_yes_agents",
        "last_no_agents",
        "final_answer",
        "final_answerable_agents",
        "final_yes_agents",
        "final_no_agents",
        "completed_round_index",
        "final_reason_short",
        "status",
        "last_polled_at",
        "next_run_at",
        "started_at",
        "ended_at",
        "end_reason",
        "error_text",
        "created_at",
        "updated_at",
    }
    REQUIRED_JUDGMENT_COLUMNS = {
        "id",
        "task_id",
        "round_index",
        "agent_source_id",
        "agent_name",
        "candidate_answer",
        "is_answerable",
        "content_short",
        "evidence_title",
        "evidence_url",
        "evidence_time",
        "status",
        "error_text",
        "raw_response_json",
        "polled_at",
        "created_at",
    }

    def __init__(self) -> None:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ModuleNotFoundError as exc:
            raise ConsensusConfigurationError("pymysql is not installed") from exc

        self._pymysql = pymysql
        self._dict_cursor = DictCursor

    def _connect(self):
        kwargs = Config.get_mysql_config()
        kwargs["cursorclass"] = self._dict_cursor
        return self._pymysql.connect(**kwargs)

    def _schema_path(self) -> str:
        return resolve_repo_path("backend/sql/consensus_schema.sql")

    def _bootstrap_schema(self, conn) -> None:
        self._bootstrap_schema_tables(conn, {"consensus_tasks", "consensus_agent_judgments"})

    def _bootstrap_schema_tables(self, conn, tables: set[str]) -> None:
        schema_path = self._schema_path()
        if not os.path.exists(schema_path):
            raise ConsensusConfigurationError(
                f"consensus schema file is missing: {schema_path}"
            )

        with open(schema_path, "r", encoding="utf-8") as f:
            statements = [stmt.strip() for stmt in f.read().split(";") if stmt.strip()]

        with conn.cursor() as cursor:
            for statement in statements:
                normalized = " ".join(statement.lower().split())
                if "consensus_tasks" in tables and normalized.startswith(
                    "create table if not exists consensus_tasks"
                ):
                    cursor.execute(statement)
                elif "consensus_agent_judgments" in tables and normalized.startswith(
                    "create table if not exists consensus_agent_judgments"
                ):
                    cursor.execute(statement)

    def _list_columns(self, conn, table_name: str) -> set[str]:
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            rows = cursor.fetchall()
        return {row["Field"] for row in rows}

    def _list_column_defs(self, conn, table_name: str) -> Dict[str, Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            rows = cursor.fetchall()
        return {row["Field"]: row for row in rows}

    def _table_exists(self, conn, table_name: str) -> bool:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            return cursor.fetchone() is not None

    def _is_poll_interval_column_current(self, conn) -> bool:
        task_columns = self._list_column_defs(conn, "consensus_tasks")
        poll_interval = task_columns.get("poll_interval_seconds")
        if not poll_interval:
            return False
        column_type = str(poll_interval.get("Type", "")).lower()
        return column_type.startswith("int") and "unsigned" in column_type

    def _is_current_schema(self, conn) -> bool:
        if not self._table_exists(conn, "consensus_tasks"):
            return False
        if not self._table_exists(conn, "consensus_agent_judgments"):
            return False
        task_columns = self._list_columns(conn, "consensus_tasks")
        judgment_columns = self._list_columns(conn, "consensus_agent_judgments")
        return (
            self.REQUIRED_TASK_COLUMNS.issubset(task_columns)
            and self.REQUIRED_JUDGMENT_COLUMNS.issubset(judgment_columns)
            and self._is_poll_interval_column_current(conn)
        )

    def _migrate_poll_interval_column(self, conn) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE consensus_tasks
                MODIFY poll_interval_seconds INT UNSIGNED NOT NULL DEFAULT 30
                """
            )

    def _archive_tables(self, conn, table_names: List[str]) -> None:
        existing = [name for name in table_names if self._table_exists(conn, name)]
        if not existing:
            return

        suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
        rename_pairs = [
            (name, f"{name}_legacy_{suffix}")
            for name in existing
        ]

        with conn.cursor() as cursor:
            cursor.execute(
                "RENAME TABLE "
                + ", ".join(
                    f"`{source}` TO `{target}`"
                    for source, target in rename_pairs
                )
            )

        logger.warning(
            "Archived legacy consensus tables: "
            + ", ".join(f"{source}->{target}" for source, target in rename_pairs)
        )

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

    def ensure_ready(self) -> None:
        with self.session() as conn:
            self._ensure_tables_exist(conn)

    def _ensure_tables_exist(self, conn) -> None:
        try:
            task_exists = self._table_exists(conn, "consensus_tasks")
            task_current = task_exists and self.REQUIRED_TASK_COLUMNS.issubset(
                self._list_columns(conn, "consensus_tasks")
            )
            judgment_exists = self._table_exists(conn, "consensus_agent_judgments")
            judgment_current = judgment_exists and self.REQUIRED_JUDGMENT_COLUMNS.issubset(
                self._list_columns(conn, "consensus_agent_judgments")
            )

            if task_current and not self._is_poll_interval_column_current(conn):
                self._migrate_poll_interval_column(conn)
                task_current = self.REQUIRED_TASK_COLUMNS.issubset(
                    self._list_columns(conn, "consensus_tasks")
                ) and self._is_poll_interval_column_current(conn)

            if task_current and judgment_current:
                return

            if task_current and not judgment_current:
                if judgment_exists:
                    self._archive_tables(conn, ["consensus_agent_judgments"])
                self._bootstrap_schema_tables(conn, {"consensus_agent_judgments"})
                if self._is_current_schema(conn):
                    return

            self._archive_tables(
                conn,
                [
                    "consensus_agent_logs",
                    "consensus_agent_judgments",
                    "consensus_tasks",
                ],
            )
            self._bootstrap_schema(conn)
            if self._is_current_schema(conn):
                return
            raise ConsensusStorageError("consensus schema bootstrap did not produce expected tables.")
        except Exception as exc:
            try:
                if not self._is_current_schema(conn):
                    self._archive_tables(
                        conn,
                        [
                            "consensus_agent_logs",
                            "consensus_agent_judgments",
                            "consensus_tasks",
                        ],
                    )
                    self._bootstrap_schema(conn)
                if self._is_current_schema(conn):
                    return
            except Exception as bootstrap_exc:
                raise ConsensusStorageError(
                    "consensus tables are missing and auto-bootstrap failed."
                ) from bootstrap_exc

    def _serialize_json(self, payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _deserialize_json(self, payload: Any) -> Optional[Dict[str, Any]]:
        if payload in (None, ""):
            return None
        if isinstance(payload, dict):
            return payload
        try:
            return json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return None

    def _prepare_task_row(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        prepared = dict(row)
        for key in [
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
            "last_polled_at",
            "next_run_at",
        ]:
            value = prepared.get(key)
            prepared[key] = value.isoformat() if isinstance(value, datetime) else value
        return prepared

    def _prepare_judgment_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        prepared = dict(row)
        prepared["raw_response_json"] = self._deserialize_json(prepared.get("raw_response_json"))
        for key in ["polled_at", "created_at"]:
            value = prepared.get(key)
            prepared[key] = value.isoformat() if isinstance(value, datetime) else value
        return prepared

    def has_running_task(self, conn, simulation_id: str) -> bool:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM consensus_tasks
                WHERE simulation_id=%s AND status='running'
                LIMIT 1
                """,
                (simulation_id,),
            )
            return cursor.fetchone() is not None

    def create_task(
        self,
        conn,
        *,
        task_uid: str,
        project_id: str,
        simulation_id: str,
        question_text: str,
        threshold_percent: int,
        poll_interval_seconds: int,
        total_agents: int,
        next_run_at: datetime,
    ) -> int:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO consensus_tasks (
                    task_uid,
                    project_id,
                    simulation_id,
                    question_text,
                    persona_platform,
                    threshold_percent,
                    poll_interval_seconds,
                    total_agents,
                    status,
                    next_run_at
                )
                VALUES (%s, %s, %s, %s, 'reddit', %s, %s, %s, 'running', %s)
                """,
                (
                    task_uid,
                    project_id,
                    simulation_id,
                    question_text,
                    threshold_percent,
                    poll_interval_seconds,
                    total_agents,
                    next_run_at,
                ),
            )
            return int(cursor.lastrowid)

    def get_task_by_uid(self, conn, task_uid: str) -> Optional[Dict[str, Any]]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM consensus_tasks WHERE task_uid=%s LIMIT 1",
                (task_uid,),
            )
            return self._prepare_task_row(cursor.fetchone())

    def get_task_by_id(self, conn, task_id: int) -> Optional[Dict[str, Any]]:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM consensus_tasks WHERE id=%s LIMIT 1",
                (task_id,),
            )
            return self._prepare_task_row(cursor.fetchone())

    def get_current_or_latest_task(self, conn, simulation_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM consensus_tasks
                WHERE simulation_id=%s AND status='running'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (simulation_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._prepare_task_row(row)
            cursor.execute(
                """
                SELECT *
                FROM consensus_tasks
                WHERE simulation_id=%s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (simulation_id,),
            )
            return self._prepare_task_row(cursor.fetchone())

    def list_tasks(self, conn, simulation_id: str) -> List[Dict[str, Any]]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM consensus_tasks
                WHERE simulation_id=%s
                ORDER BY created_at DESC, id DESC
                """,
                (simulation_id,),
            )
            return [self._prepare_task_row(row) for row in cursor.fetchall()]

    def list_due_running_tasks(self, conn, now: datetime) -> List[Dict[str, Any]]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM consensus_tasks
                WHERE status='running'
                  AND next_run_at IS NOT NULL
                  AND next_run_at<=%s
                ORDER BY next_run_at ASC, id ASC
                """,
                (now,),
            )
            return [self._prepare_task_row(row) for row in cursor.fetchall()]

    def create_round_judgments(
        self,
        conn,
        judgments: List[Dict[str, Any]],
    ) -> None:
        if not judgments:
            return
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO consensus_agent_judgments (
                    task_id,
                    round_index,
                    agent_source_id,
                    agent_name,
                    candidate_answer,
                    is_answerable,
                    content_short,
                    evidence_title,
                    evidence_url,
                    evidence_time,
                    status,
                    error_text,
                    raw_response_json,
                    polled_at
                )
                VALUES (
                    %(task_id)s,
                    %(round_index)s,
                    %(agent_source_id)s,
                    %(agent_name)s,
                    %(candidate_answer)s,
                    %(is_answerable)s,
                    %(content_short)s,
                    %(evidence_title)s,
                    %(evidence_url)s,
                    %(evidence_time)s,
                    %(status)s,
                    %(error_text)s,
                    %(raw_response_json)s,
                    %(polled_at)s
                )
                """,
                [
                    {
                        **judgment,
                        "raw_response_json": self._serialize_json(
                            judgment.get("raw_response_json")
                        ),
                    }
                    for judgment in judgments
                ],
            )

    def update_task_after_round(
        self,
        conn,
        *,
        task_id: int,
        round_index: int,
        answerable_count: int,
        yes_count: int,
        no_count: int,
        polled_at: datetime,
        next_run_at: Optional[datetime],
        status: str,
        final_answer: Optional[str] = None,
        final_reason_short: Optional[str] = None,
        end_reason: Optional[str] = None,
        ended_at: Optional[datetime] = None,
        error_text: Optional[str] = None,
    ) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET current_round_index=%s,
                    last_answerable_agents=%s,
                    last_yes_agents=%s,
                    last_no_agents=%s,
                    last_polled_at=%s,
                    next_run_at=%s,
                    status=%s,
                    final_answer=%s,
                    final_answerable_agents=%s,
                    final_yes_agents=%s,
                    final_no_agents=%s,
                    completed_round_index=%s,
                    final_reason_short=%s,
                    ended_at=%s,
                    end_reason=%s,
                    error_text=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (
                    round_index,
                    answerable_count,
                    yes_count,
                    no_count,
                    polled_at,
                    next_run_at,
                    status,
                    final_answer,
                    answerable_count if final_answer else None,
                    yes_count if final_answer else None,
                    no_count if final_answer else None,
                    round_index if final_answer else None,
                    final_reason_short,
                    ended_at,
                    end_reason,
                    error_text,
                    task_id,
                ),
            )

    def update_task_error(self, conn, task_id: int, error_text: str) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET error_text=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (error_text, task_id),
            )

    def stop_task(self, conn, task_id: int, end_reason: str, ended_at: datetime) -> None:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET status='stopped',
                    ended_at=%s,
                    end_reason=%s,
                    next_run_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                  AND status='running'
                """,
                (ended_at, end_reason, task_id),
            )

    def interrupt_running_tasks(self, conn, ended_at: datetime) -> int:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE consensus_tasks
                SET status='interrupted',
                    ended_at=%s,
                    end_reason='service_restart',
                    next_run_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE status='running'
                """,
                (ended_at,),
            )
            return int(cursor.rowcount)

    def list_judgments(self, conn, task_id: int) -> List[Dict[str, Any]]:
        self._ensure_tables_exist(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM consensus_agent_judgments
                WHERE task_id=%s
                ORDER BY agent_source_id ASC, round_index DESC, polled_at DESC, id DESC
                """,
                (task_id,),
            )
            return [self._prepare_judgment_row(row) for row in cursor.fetchall()]
