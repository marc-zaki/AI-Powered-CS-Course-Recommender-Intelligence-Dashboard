import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    # Even if unauthenticated or error, the router might return 200 (HTML)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_api_course_quick_search_empty():
    response = client.get("/api/course/quick_search?q=")
    assert response.status_code == 200
    assert response.json() == {"courses": []}

def test_validate_link_empty():
    response = client.get("/validate_link")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["fallback_url"] == "/"
