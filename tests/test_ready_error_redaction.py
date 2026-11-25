from contextlib import contextmanager

from fastapi.testclient import TestClient

from app import db as db_module
from app.main import app


def test_ready_does_not_echo_database_connection_errors(monkeypatch):
    @contextmanager
    def broken_db():
        raise RuntimeError(
            "connection failed for postgresql://admin:secret-password@db.internal"
        )
        yield  # pragma: no cover

    monkeypatch.setattr(db_module, "db", broken_db)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "not ready"
    assert "secret-password" not in response.text
    assert "db.internal" not in response.text
