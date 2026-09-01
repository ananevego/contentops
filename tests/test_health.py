from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import router

client =  TestClient(app)

def test_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "contentops-api"}
