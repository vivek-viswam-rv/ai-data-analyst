from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_limits_reports_configuration():
    body = client.get("/api/analyses/limits").json()
    assert body["max_upload_bytes"] == settings.max_upload_bytes
    assert body["worker_model"] == settings.worker_model


def test_preview_returns_brief(sales_csv):
    response = client.post("/api/analyses/preview", files={"file": ("sales.csv", sales_csv)})
    assert response.status_code == 200
    brief = response.json()["brief"]
    assert brief["n_rows"] == 203
    assert {c["name"] for c in brief["columns"]} >= {"order_id", "region", "revenue"}


def test_preview_rejects_unreadable_file():
    response = client.post("/api/analyses/preview", files={"file": ("x.parquet", b"nope")})
    assert response.status_code == 422
    assert "Unsupported" in response.json()["detail"]


def test_preview_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    response = client.post("/api/analyses/preview", files={"file": ("x.csv", b"a,b\n1,2\n3,4\n")})
    assert response.status_code == 413


def test_analyse_needs_an_api_key(monkeypatch, sales_csv):
    monkeypatch.setattr(settings, "openai_api_key", "")
    response = client.post("/api/analyses", files={"file": ("sales.csv", sales_csv)})
    assert response.status_code == 503
