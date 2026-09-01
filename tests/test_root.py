from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import router

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ContentOps is running"}
