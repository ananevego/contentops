from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import router

client = TestClient(app)

def test_config():
    response = client.get("/config")
    assert response.status_code == 200
    assert response.json() == {"app_name": "ContentOps", "environment": "development"}
