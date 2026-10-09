from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.main import app
from app.models.content_db import Base


def test_content_patch_and_delete_with_tags():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            created = client.post(
                "/content",
                json={
                    "source": {"platform": "tiktok", "category": "fitness"},
                    "external_id": "api-mutation-item",
                    "author": "demo",
                    "text": "Original text",
                    "views": 100,
                    "likes": 10,
                    "comments": 2,
                    "shares": 1,
                    "url": "https://example.com/content",
                    "created_at": "2026-10-01T10:00:00Z",
                    "tags": ["fitness", "training"],
                },
            )
            assert created.status_code == 201
            item_id = created.json()["id"]
            assert created.json()["tags"] == ["fitness", "training"]

            updated = client.patch(
                f"/content/{item_id}",
                json={"text": "Updated text", "tags": ["fitness", "recovery"]},
            )
            assert updated.status_code == 200
            assert updated.json()["text"] == "Updated text"
            assert updated.json()["tags"] == ["fitness", "recovery"]

            deleted = client.delete(f"/content/{item_id}")
            assert deleted.status_code == 204
            assert client.patch(f"/content/{item_id}", json={"text": "no"}).status_code == 404
    finally:
        app.dependency_overrides.clear()
