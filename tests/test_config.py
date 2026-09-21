from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_config(monkeypatch):
    monkeypatch.setenv("APP_NAME", "ContentOps")
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = client.get("/config")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "ContentOps",
        "environment": "development",
    }
