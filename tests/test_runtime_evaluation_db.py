from app import db as database


def test_application_event_persists_experiment_lineage(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_URL", "")
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "runtime-events.db")
    database.init_db()

    inserted = database.insert_application_event(
        event_id="ef-" + "a" * 32,
        project="evidenceflow",
        event_type="evaluation.completed",
        status="success",
        workflow="rag_query",
        duration_ms=12.5,
        model="provider/model",
        request_id="request-1",
        metrics={"external.ragas.faithfulness": 0.94},
        experiment_id="experiment-1",
        dataset_version="dataset-v2",
        prompt_version="prompt-v3",
        model_version="model-v4",
        config_version="retrieval-v5",
    )
    rows = database.query_application_events(limit=10, project="evidenceflow")

    assert inserted is True
    assert rows[0]["experiment_id"] == "experiment-1"
    assert rows[0]["dataset_version"] == "dataset-v2"
    assert rows[0]["prompt_version"] == "prompt-v3"
    assert rows[0]["model_version"] == "model-v4"
    assert rows[0]["config_version"] == "retrieval-v5"
    assert rows[0]["metrics"] == {"external.ragas.faithfulness": 0.94}


def test_application_event_lineage_migration_preserves_legacy_events(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setattr(database, "DATABASE_URL", "")
    db_path = tmp_path / "legacy-events.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE application_events (
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
            )
            """
        )
        connection.execute(
            """
            INSERT INTO application_events
            (id, created_at, project, event_type, status, workflow, metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("legacy-1", "2026-11-27T10:00:00+00:00", "flowpilot",
             "run.completed", "success", "content", "{}"),
        )
        connection.commit()

    database.init_db()
    rows = database.query_application_events(limit=10, project="flowpilot")

    assert len(rows) == 1
    assert rows[0]["id"] == "legacy-1"
    assert rows[0]["experiment_id"] is None
