from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .config import DATABASE_URL, DB_PATH, DB_SCHEMA

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - required only for hosted PostgreSQL
    psycopg = None
    dict_row = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_schema_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid database schema name: {value!r}")
    return value


_SCHEMA = _validate_schema_name(DB_SCHEMA)
DB_FILE = Path(DB_PATH)
DB_FILE.parent.mkdir(parents=True, exist_ok=True)


class _PostgresConnection:
    """Keep the existing SQLite-style query syntax portable to psycopg."""

    def __init__(self, connection):
        self._connection = connection

    @staticmethod
    def _adapt_sql(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql: str, params=None):
        return self._connection.execute(self._adapt_sql(sql), params or ())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def connect():
    if not DATABASE_URL:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    if psycopg is None:
        raise RuntimeError("psycopg is required when DATABASE_URL is configured")

    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{_SCHEMA}"')
    conn.execute(f'SET search_path TO "{_SCHEMA}"')
    return _PostgresConnection(conn)


@contextmanager
def db() -> Iterator[Any]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        finally:
            conn.close()
        raise
    else:
        conn.close()


def _existing_ai_quality_columns(conn) -> set[str]:
    if DATABASE_URL:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=?",
            (_SCHEMA, "ai_quality_runs"),
        ).fetchall()
        return {row["column_name"] for row in rows}
    rows = conn.execute("PRAGMA table_info(ai_quality_runs)").fetchall()
    return {row[1] for row in rows}


def init_db() -> None:
    """Create the active tables only; never drop legacy tables or stored history."""
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            actor TEXT,
            run_id TEXT,
            payload TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS application_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            project TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            workflow TEXT NOT NULL,
            duration_ms REAL,
            model TEXT,
            request_id TEXT,
            metrics TEXT NOT NULL
        )""")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_events_project_created "
            "ON application_events(project, created_at)"
        )
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_quality_runs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            target TEXT NOT NULL,
            case_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            passed INTEGER NOT NULL,
            score REAL NOT NULL,
            metrics TEXT NOT NULL,
            gate_failures TEXT NOT NULL,
            notes TEXT NOT NULL,
            dataset_version TEXT NOT NULL DEFAULT 'v1',
            prompt_version TEXT NOT NULL DEFAULT 'not-applicable',
            model_version TEXT NOT NULL DEFAULT 'not-applicable',
            config_version TEXT NOT NULL DEFAULT 'v1',
            experiment_id TEXT
        )""")

        # Upgrade older evaluation rows in place. Other legacy tables, if
        # present, are deliberately left intact for safe migration.
        columns = _existing_ai_quality_columns(conn)
        migrations = {
            "batch_id": "ALTER TABLE ai_quality_runs ADD COLUMN batch_id TEXT NOT NULL DEFAULT 'legacy-batch'",
            "dataset_version": "ALTER TABLE ai_quality_runs ADD COLUMN dataset_version TEXT NOT NULL DEFAULT 'v1'",
            "prompt_version": "ALTER TABLE ai_quality_runs ADD COLUMN prompt_version TEXT NOT NULL DEFAULT 'not-applicable'",
            "model_version": "ALTER TABLE ai_quality_runs ADD COLUMN model_version TEXT NOT NULL DEFAULT 'not-applicable'",
            "config_version": "ALTER TABLE ai_quality_runs ADD COLUMN config_version TEXT NOT NULL DEFAULT 'v1'",
            "experiment_id": "ALTER TABLE ai_quality_runs ADD COLUMN experiment_id TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_quality_target_created "
            "ON ai_quality_runs(target, created_at)"
        )


def insert_application_event(
    *,
    event_id: str,
    project: str,
    event_type: str,
    status: str,
    workflow: str,
    duration_ms: float | None,
    model: str | None,
    request_id: str | None,
    metrics: Any,
) -> bool:
    """Persist a bounded project event. Event IDs make retries idempotent."""
    with db() as conn:
        cursor = conn.execute(
            """INSERT INTO application_events
            (id, created_at, project, event_type, status, workflow, duration_ms, model, request_id, metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING""",
            (
                event_id,
                utc_now(),
                project,
                event_type,
                status,
                workflow,
                duration_ms,
                model,
                request_id,
                json.dumps(metrics or {}, allow_nan=False),
            ),
        )
        return getattr(cursor, "rowcount", 0) == 1


def query_application_events(limit: int = 60, project: str | None = None) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit), 1000))
    with db() as conn:
        if project:
            rows = conn.execute(
                "SELECT * FROM application_events WHERE project=? ORDER BY created_at DESC LIMIT ?",
                (project, bounded_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM application_events ORDER BY created_at DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["metrics"] = json.loads(item.get("metrics") or "{}")
        result.append(item)
    return result


def insert_audit(
    event_type: str,
    status: str,
    payload: Dict[str, Any],
    actor: str = "system",
    run_id: Optional[str] = None,
) -> str:
    event_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_events (id, created_at, event_type, status, actor, run_id, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, utc_now(), event_type, status, actor, run_id, json.dumps(payload, default=str)),
        )
    return event_id


def insert_ai_quality(
    *,
    batch_id: str,
    target: str,
    case_id: str,
    mode: str,
    score: float,
    passed: bool,
    metrics: Any,
    gate_failures: Any,
    notes: Any,
    dataset_version: str = "v1",
    prompt_version: str = "not-applicable",
    model_version: str = "not-applicable",
    config_version: str = "v1",
    experiment_id: str | None = None,
) -> str:
    quality_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            """INSERT INTO ai_quality_runs
            (id, created_at, batch_id, target, case_id, mode, passed, score, metrics, gate_failures, notes,
             dataset_version, prompt_version, model_version, config_version, experiment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                quality_id,
                utc_now(),
                batch_id,
                target,
                case_id,
                mode,
                int(passed),
                score,
                json.dumps(metrics, default=str),
                json.dumps(gate_failures, default=str),
                json.dumps(notes, default=str),
                dataset_version,
                prompt_version,
                model_version,
                config_version,
                experiment_id,
            ),
        )
    return quality_id


def quality_metrics(limit: int = 400) -> Dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 2000))
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_quality_runs ORDER BY created_at DESC LIMIT ?",
            (bounded_limit,),
        ).fetchall()

    parsed = []
    for row in rows:
        item = dict(row)
        item["passed"] = bool(item["passed"])
        item["metrics"] = json.loads(item.get("metrics") or "{}")
        item["gate_failures"] = json.loads(item.get("gate_failures") or "[]")
        item["notes"] = json.loads(item.get("notes") or "[]")
        parsed.append(item)

    by_target: dict[str, dict[str, Any]] = {}
    for target in sorted({item["target"] for item in parsed}):
        target_rows = [item for item in parsed if item["target"] == target]
        latest_batch = target_rows[0]["batch_id"]
        latest_rows = [item for item in target_rows if item["batch_id"] == latest_batch]
        previous_batch = next(
            (item["batch_id"] for item in target_rows if item["batch_id"] != latest_batch),
            None,
        )
        previous_rows = (
            [item for item in target_rows if item["batch_id"] == previous_batch]
            if previous_batch
            else []
        )

        metric_names = sorted({key for item in latest_rows for key in item["metrics"]})
        aggregate_metrics = {
            name: round(
                sum(float(item["metrics"].get(name, 0.0)) for item in latest_rows)
                / sum(name in item["metrics"] for item in latest_rows),
                6,
            )
            for name in metric_names
            if any(name in item["metrics"] for item in latest_rows)
        }
        score = (
            round(sum(float(item["score"]) for item in latest_rows) / len(latest_rows), 6)
            if latest_rows
            else 0.0
        )
        previous_score = (
            round(sum(float(item["score"]) for item in previous_rows) / len(previous_rows), 6)
            if previous_rows
            else None
        )
        failures = sorted(
            {failure for item in latest_rows for failure in item["gate_failures"]}
        )
        by_target[target] = {
            "score": score,
            "passed": all(item["passed"] for item in latest_rows) if latest_rows else False,
            "mode": latest_rows[0]["mode"] if latest_rows else "unknown",
            "batch_id": latest_batch,
            "cases": len(latest_rows),
            "case_ids": [item["case_id"] for item in latest_rows],
            "gate_failures": failures,
            "delta_vs_previous": None if previous_score is None else round(score - previous_score, 6),
            "metrics": aggregate_metrics,
            "notes": sorted({note for item in latest_rows for note in item["notes"]}),
            "lineage": {
                "dataset_version": latest_rows[0].get("dataset_version", "v1"),
                "prompt_version": latest_rows[0].get("prompt_version", "not-applicable"),
                "model_version": latest_rows[0].get("model_version", "not-applicable"),
                "config_version": latest_rows[0].get("config_version", "v1"),
                "experiment_id": latest_rows[0].get("experiment_id"),
            },
        }

    scores = [float(item["score"]) for item in by_target.values()]
    return {
        "runs": parsed,
        "targets": by_target,
        "target_count": len(by_target),
        "target_gate_passes": sum(1 for item in by_target.values() if item["passed"]),
        "platform_score": round(sum(scores) / len(scores), 6) if scores else 0.0,
    }
