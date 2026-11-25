from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_uses_unprivileged_user_and_owns_sqlite_data():
    content = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "useradd --create-home --uid 10001 appuser" in content
    assert "chown -R appuser:appuser /app" in content
    assert "USER appuser" in content
    assert "COPY data ./data" in content
    assert "uvicorn" in content
