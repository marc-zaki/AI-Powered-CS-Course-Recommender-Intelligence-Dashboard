import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
response = client.post("/generate_path", json={"goal": "Learn React"})
print(response.status_code)
print(response.json())
