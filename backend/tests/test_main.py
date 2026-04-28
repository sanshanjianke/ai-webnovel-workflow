import pytest
from fastapi.testclient import TestClient


def test_root():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_modules():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/api/modules")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
    assert "open_ai_compat" in data["llm"]
