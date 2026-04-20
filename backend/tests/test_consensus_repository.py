from __future__ import annotations

from pathlib import Path

from app.consensus.repository import ConsensusRepository


def current_task_columns():
    return {
        column: {"Field": column, "Type": "varchar(255)"}
        for column in ConsensusRepository.REQUIRED_TASK_COLUMNS
    } | {
        "poll_interval_seconds": {
            "Field": "poll_interval_seconds",
            "Type": "int unsigned",
        }
    }


def current_judgment_columns():
    return {
        column: {"Field": column, "Type": "varchar(255)"}
        for column in ConsensusRepository.REQUIRED_JUDGMENT_COLUMNS
    }


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self._rows = []

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        if sql.startswith("SHOW TABLES LIKE"):
            table_name = params[0]
            self._rows = [(table_name,)] if table_name in self.state["tables"] else []
            return
        if sql.startswith("SHOW COLUMNS FROM"):
            table_name = sql.split()[-1]
            columns = self.state["tables"].get(table_name, {})
            if isinstance(columns, dict):
                self._rows = list(columns.values())
            else:
                self._rows = [{"Field": name, "Type": "varchar(255)"} for name in columns]
            return
        if sql.startswith("DROP TABLE IF EXISTS consensus_agent_judgments"):
            self.state["tables"].pop("consensus_agent_judgments", None)
            return
        if sql.startswith("DROP TABLE IF EXISTS consensus_tasks"):
            self.state["tables"].pop("consensus_tasks", None)
            return
        if sql.startswith("RENAME TABLE"):
            parts = sql[len("RENAME TABLE ") :].split(",")
            for part in parts:
                source_part, target_part = part.split(" TO ")
                source = source_part.strip().strip("`")
                target = target_part.strip().strip("`")
                self.state["tables"][target] = self.state["tables"].pop(source)
            return
        if sql.startswith("ALTER TABLE consensus_tasks MODIFY poll_interval_seconds"):
            self.state.setdefault("alters", []).append(sql)
            self.state["tables"]["consensus_tasks"]["poll_interval_seconds"] = {
                "Field": "poll_interval_seconds",
                "Type": "int unsigned",
            }
            return
        if "CREATE TABLE IF NOT EXISTS consensus_tasks" in sql:
            self.state["tables"]["consensus_tasks"] = current_task_columns()
            return
        if "CREATE TABLE IF NOT EXISTS consensus_agent_judgments" in sql:
            self.state["tables"]["consensus_agent_judgments"] = current_judgment_columns()
            return
        raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return FakeCursor(self.state)


def test_ensure_tables_exist_rebuilds_legacy_schema(monkeypatch, tmp_path):
    repo = object.__new__(ConsensusRepository)
    repo.REQUIRED_TASK_COLUMNS = ConsensusRepository.REQUIRED_TASK_COLUMNS
    repo.REQUIRED_JUDGMENT_COLUMNS = ConsensusRepository.REQUIRED_JUDGMENT_COLUMNS

    state = {
        "tables": {
            "consensus_tasks": {
                "id": {"Field": "id", "Type": "bigint unsigned"},
                "question": {"Field": "question", "Type": "text"},
                "status": {"Field": "status", "Type": "varchar(32)"},
            },
        }
    }
    conn = FakeConnection(state)
    schema_path = Path(tmp_path) / "consensus_schema.sql"
    schema_path.write_text(
        """
        CREATE TABLE IF NOT EXISTS consensus_tasks (id BIGINT);
        CREATE TABLE IF NOT EXISTS consensus_agent_judgments (id BIGINT);
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(repo, "_schema_path", lambda: str(schema_path))

    repo._ensure_tables_exist(conn)

    assert "consensus_tasks" in state["tables"]
    assert "consensus_agent_judgments" in state["tables"]
    assert any(name.startswith("consensus_tasks_legacy_") for name in state["tables"])
    assert ConsensusRepository.REQUIRED_TASK_COLUMNS.issubset(state["tables"]["consensus_tasks"])
    assert ConsensusRepository.REQUIRED_JUDGMENT_COLUMNS.issubset(
        state["tables"]["consensus_agent_judgments"]
    )


def test_ensure_tables_exist_migrates_poll_interval_to_int_unsigned(monkeypatch, tmp_path):
    repo = object.__new__(ConsensusRepository)
    repo.REQUIRED_TASK_COLUMNS = ConsensusRepository.REQUIRED_TASK_COLUMNS
    repo.REQUIRED_JUDGMENT_COLUMNS = ConsensusRepository.REQUIRED_JUDGMENT_COLUMNS

    task_columns = current_task_columns()
    task_columns["poll_interval_seconds"] = {
        "Field": "poll_interval_seconds",
        "Type": "smallint unsigned",
    }
    state = {
        "tables": {
            "consensus_tasks": task_columns,
            "consensus_agent_judgments": current_judgment_columns(),
        }
    }
    conn = FakeConnection(state)
    schema_path = Path(tmp_path) / "consensus_schema.sql"
    schema_path.write_text(
        """
        CREATE TABLE IF NOT EXISTS consensus_tasks (id BIGINT);
        CREATE TABLE IF NOT EXISTS consensus_agent_judgments (id BIGINT);
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(repo, "_schema_path", lambda: str(schema_path))

    repo._ensure_tables_exist(conn)

    assert state["tables"]["consensus_tasks"]["poll_interval_seconds"]["Type"] == "int unsigned"
    assert state["alters"] == [
        "ALTER TABLE consensus_tasks MODIFY poll_interval_seconds INT UNSIGNED NOT NULL DEFAULT 30"
    ]
