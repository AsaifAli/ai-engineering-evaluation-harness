from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


DB_FILE = Path(DB_PATH)
DB_FILE.parent.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
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
        conn.execute("""CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            workflow TEXT NOT NULL,
            summary TEXT NOT NULL,
            payload TEXT NOT NULL,
            decided_at TEXT,
            decided_by TEXT,
            decision_note TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS llm_runs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            run_id TEXT NOT NULL,
            workflow TEXT NOT NULL,
            operation TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            status TEXT NOT NULL,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_usd REAL,
            guardrail_status TEXT NOT NULL,
            error TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS evaluation_runs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            eval_suite TEXT NOT NULL,
            workflow TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            passed INTEGER NOT NULL,
            total INTEGER NOT NULL,
            score REAL NOT NULL,
            details TEXT NOT NULL
        )""")
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_quality_runs)").fetchall()}
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
        conn.execute("""CREATE TABLE IF NOT EXISTS traces (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, run_id TEXT NOT NULL, target TEXT, workflow TEXT NOT NULL,
            status TEXT NOT NULL, duration_ms REAL NOT NULL, steps TEXT NOT NULL, metadata TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS config_registry (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, component TEXT NOT NULL, version TEXT NOT NULL,
            config TEXT NOT NULL, notes TEXT, active INTEGER NOT NULL DEFAULT 1
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS experiment_comparisons (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, experiment_id TEXT NOT NULL, target TEXT NOT NULL,
            baseline_batch_id TEXT NOT NULL, candidate_batch_id TEXT NOT NULL, status TEXT NOT NULL, passed INTEGER NOT NULL,
            score_delta REAL NOT NULL, metrics TEXT NOT NULL, regressions TEXT NOT NULL, improvements TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS judge_runs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, target TEXT NOT NULL, case_id TEXT NOT NULL,
            quality_id TEXT, status TEXT NOT NULL, provider TEXT, model TEXT, prompt_version TEXT NOT NULL,
            score REAL, criteria TEXT NOT NULL, rationale TEXT NOT NULL, metadata TEXT NOT NULL
        )""")


def insert_audit(event_type: str, status: str, payload: Dict[str, Any], actor: str = "system", run_id: Optional[str] = None) -> str:
    event_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_events (id, created_at, event_type, status, actor, run_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, utc_now(), event_type, status, actor, run_id, json.dumps(payload, default=str)),
        )
    return event_id


def insert_llm_run(*, run_id: str, workflow: str, operation: str, provider: str, model: str,
                   prompt_version: str, latency_ms: float, status: str, fallback_used: bool,
                   input_tokens: Optional[int], output_tokens: Optional[int], total_tokens: Optional[int],
                   estimated_cost_usd: Optional[float], guardrail_status: str, error: Optional[str] = None) -> str:
    run_record_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            """INSERT INTO llm_runs
            (id, created_at, run_id, workflow, operation, provider, model, prompt_version, latency_ms,
             status, fallback_used, input_tokens, output_tokens, total_tokens, estimated_cost_usd,
             guardrail_status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_record_id, utc_now(), run_id, workflow, operation, provider, model, prompt_version,
             latency_ms, status, int(fallback_used), input_tokens, output_tokens, total_tokens,
             estimated_cost_usd, guardrail_status, error),
        )
    return run_record_id


def insert_evaluation(*, eval_suite: str, workflow: str, provider: str, model: str,
                      passed: int, total: int, score: float, details: Any) -> str:
    evaluation_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (evaluation_id, utc_now(), eval_suite, workflow, provider, model,
             passed, total, score, json.dumps(details, default=str)),
        )
    return evaluation_id


def insert_ai_quality(*, batch_id: str, target: str, case_id: str, mode: str, score: float, passed: bool,
                     metrics: Any, gate_failures: Any, notes: Any, dataset_version: str = "v1",
                     prompt_version: str = "not-applicable", model_version: str = "not-applicable",
                     config_version: str = "v1", experiment_id: str | None = None) -> str:
    quality_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            """INSERT INTO ai_quality_runs
            (id, created_at, batch_id, target, case_id, mode, passed, score, metrics, gate_failures, notes,
             dataset_version, prompt_version, model_version, config_version, experiment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (quality_id, utc_now(), batch_id, target, case_id, mode, int(passed), score,
             json.dumps(metrics, default=str), json.dumps(gate_failures, default=str), json.dumps(notes, default=str),
             dataset_version, prompt_version, model_version, config_version, experiment_id),
        )
    return quality_id


def quality_metrics(limit: int = 400) -> Dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_quality_runs ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 2000)),),
        ).fetchall()

    parsed = []
    for row in rows:
        item = dict(row)
        item["passed"] = bool(item["passed"])
        item["metrics"] = json.loads(item["metrics"] or "{}")
        item["gate_failures"] = json.loads(item["gate_failures"] or "[]")
        item["notes"] = json.loads(item["notes"] or "[]")
        parsed.append(item)

    by_target: dict[str, dict[str, Any]] = {}
    for target in sorted({item["target"] for item in parsed}):
        target_rows = [item for item in parsed if item["target"] == target]
        latest_batch = target_rows[0]["batch_id"]
        latest_rows = [item for item in target_rows if item["batch_id"] == latest_batch]
        previous_batch = next((item["batch_id"] for item in target_rows if item["batch_id"] != latest_batch), None)
        previous_rows = [item for item in target_rows if item["batch_id"] == previous_batch] if previous_batch else []

        metric_names = sorted({key for item in latest_rows for key in item["metrics"]})
        aggregate_metrics = {
            name: round(sum(float(item["metrics"].get(name, 0.0)) for item in latest_rows) / sum(name in item["metrics"] for item in latest_rows), 6)
            for name in metric_names
            if any(name in item["metrics"] for item in latest_rows)
        }
        score = round(sum(float(item["score"]) for item in latest_rows) / len(latest_rows), 6) if latest_rows else 0.0
        previous_score = round(sum(float(item["score"]) for item in previous_rows) / len(previous_rows), 6) if previous_rows else None
        failures = sorted({failure for item in latest_rows for failure in item["gate_failures"]})
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



def get_quality_batch(target: str, batch_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM ai_quality_runs WHERE target=? AND batch_id=? ORDER BY created_at ASC", (target, batch_id)).fetchall()
    parsed: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["passed"] = bool(item["passed"])
        item["metrics"] = json.loads(item["metrics"] or "{}")
        item["gate_failures"] = json.loads(item["gate_failures"] or "[]")
        item["notes"] = json.loads(item["notes"] or "[]")
        parsed.append(item)
    return parsed


def insert_trace(*, run_id: str, target: str | None, workflow: str, status: str, duration_ms: float, steps: Any, metadata: Any) -> str:
    trace_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO traces (id, created_at, run_id, target, workflow, status, duration_ms, steps, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trace_id, utc_now(), run_id, target, workflow, status, duration_ms, json.dumps(steps, default=str), json.dumps(metadata, default=str)),
        )
    return trace_id


def insert_config(*, component: str, version: str, config: Any, notes: str = "", active: bool = True) -> str:
    config_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute("INSERT INTO config_registry (id, created_at, component, version, config, notes, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (config_id, utc_now(), component, version, json.dumps(config, default=str), notes, int(active)))
    return config_id


def query_configs(limit: int = 200) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM config_registry ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["active"] = bool(item["active"])
        item["config"] = json.loads(item["config"] or "{}")
        result.append(item)
    return result


def insert_experiment_comparison(*, experiment_id: str, target: str, baseline_batch_id: str, candidate_batch_id: str, comparison: dict[str, Any]) -> str:
    comparison_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO experiment_comparisons (id, created_at, experiment_id, target, baseline_batch_id, candidate_batch_id, status, passed, score_delta, metrics, regressions, improvements) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (comparison_id, utc_now(), experiment_id, target, baseline_batch_id, candidate_batch_id, comparison["status"], int(comparison["passed"]), comparison["score_delta"],
             json.dumps(comparison["metrics"], default=str), json.dumps(comparison["regressions"], default=str), json.dumps(comparison["improvements"], default=str)),
        )
    return comparison_id


def query_experiments(limit: int = 100) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM experiment_comparisons ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["passed"] = bool(item["passed"])
        item["metrics"] = json.loads(item["metrics"] or "{}")
        item["regressions"] = json.loads(item["regressions"] or "[]")
        item["improvements"] = json.loads(item["improvements"] or "[]")
        result.append(item)
    return result


def insert_judge_run(*, target: str, case_id: str, quality_id: str | None, status: str, provider: str | None, model: str | None, prompt_version: str, score: float | None, criteria: Any, rationale: str, metadata: Any | None = None, **_: Any) -> str:
    judge_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO judge_runs (id, created_at, target, case_id, quality_id, status, provider, model, prompt_version, score, criteria, rationale, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (judge_id, utc_now(), target, case_id, quality_id, status, provider, model, prompt_version, score, json.dumps(criteria, default=str), rationale, json.dumps(metadata or {}, default=str)),
        )
    return judge_id


def query_judges(limit: int = 100) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM judge_runs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["criteria"] = json.loads(item["criteria"] or "{}")
        item["metadata"] = json.loads(item["metadata"] or "{}")
        result.append(item)
    return result


def query_traces(limit: int = 100, run_id: str | None = None) -> list[dict[str, Any]]:
    with db() as conn:
        if run_id:
            rows = conn.execute("SELECT * FROM traces WHERE run_id=? ORDER BY created_at DESC LIMIT ?", (run_id, max(1, min(limit, 200)))).fetchall()
        else:
            rows = conn.execute("SELECT * FROM traces ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["steps"] = json.loads(item["steps"] or "[]")
        item["metadata"] = json.loads(item["metadata"] or "{}")
        result.append(item)
    return result

def create_approval(workflow: str, summary: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    approval_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO approvals (id, created_at, status, workflow, summary, payload, decided_at, decided_by, decision_note) VALUES (?, ?, 'pending', ?, ?, ?, NULL, NULL, NULL)",
            (approval_id, utc_now(), workflow, summary, json.dumps(payload, default=str)),
        )
    return {"approval_id": approval_id, "status": "pending"}


def decide_approval(approval_id: str, status: str, decided_by: str, decision_note: str) -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise KeyError("approval not found")
        conn.execute(
            "UPDATE approvals SET status=?, decided_at=?, decided_by=?, decision_note=? WHERE id=?",
            (status, utc_now(), decided_by, decision_note, approval_id),
        )
    return {"approval_id": approval_id, "status": status, "decided_by": decided_by, "decision_note": decision_note}


def query_rows(table: str, limit: int = 50):
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    return [dict(row) for row in rows]


def metrics() -> Dict[str, Any]:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM llm_runs").fetchone()["c"]
        success = conn.execute("SELECT COUNT(*) c FROM llm_runs WHERE status='success'").fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) c FROM llm_runs WHERE status='failed'").fetchone()["c"]
        fallback = conn.execute("SELECT COUNT(*) c FROM llm_runs WHERE fallback_used=1").fetchone()["c"]
        avg_latency = conn.execute("SELECT AVG(latency_ms) v FROM llm_runs").fetchone()["v"]
        total_tokens = conn.execute("SELECT SUM(total_tokens) v FROM llm_runs").fetchone()["v"] or 0
        cost = conn.execute("SELECT SUM(estimated_cost_usd) v FROM llm_runs").fetchone()["v"]
        pending = conn.execute("SELECT COUNT(*) c FROM approvals WHERE status='pending'").fetchone()["c"]
        eval_total = conn.execute("SELECT COUNT(*) c FROM evaluation_runs").fetchone()["c"]
        eval_passed = conn.execute("SELECT SUM(passed) c FROM evaluation_runs").fetchone()["c"] or 0
        eval_cases = conn.execute("SELECT SUM(total) c FROM evaluation_runs").fetchone()["c"] or 0
        audit_count = conn.execute("SELECT COUNT(*) c FROM audit_events").fetchone()["c"]
    return {
        "llm_runs": total,
        "llm_success": success,
        "llm_failed": failed,
        "fallback_runs": fallback,
        "fallback_rate_pct": round((fallback / total) * 100, 2) if total else 0.0,
        "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else 0.0,
        "total_tokens": int(total_tokens),
        "estimated_cost_usd": round(cost, 6) if cost is not None else None,
        "pending_approvals": pending,
        "audit_events": audit_count,
        "evaluation_runs": eval_total,
        "evaluation_pass_rate_pct": round((eval_passed / eval_cases) * 100, 2) if eval_cases else 0.0,
    }
