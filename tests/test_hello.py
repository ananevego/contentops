from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_hello_check():
    response = client.get("/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from ContentOps"}

