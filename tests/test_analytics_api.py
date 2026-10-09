from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analytics_endpoints_are_documented_and_traceable():
    response = client.get("/analytics/summary", headers={"X-Request-ID": "report-42"})

    assert response.status_code == 200
    assert response.json()["total_items"] > 0
    assert response.headers["X-Request-ID"] == "report-42"
    assert float(response.headers["X-Process-Time-Ms"]) >= 0
    schema = client.get("/openapi.json").json()
    assert "/analytics/summary" in schema["paths"]
    assert "/content" in schema["paths"]


def test_content_payload_requires_timezone_and_consistent_metrics():
    payload = {
        "source": {"platform": "tiktok", "category": "fitness"},
        "external_id": "invalid-item",
        "author": "demo",
        "text": "Test item",
        "views": 10,
        "likes": 100,
        "comments": 0,
        "shares": 0,
        "url": "https://example.com/item",
        "created_at": "2026-10-01T10:00:00Z",
    }

    response = client.post("/content", json=payload)

    assert response.status_code == 422
    assert "inconsistent" in response.text
