import asyncio
import os
from fastapi.testclient import TestClient
from main import app

os.environ["OPENROUTER_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

client = TestClient(app)
response = client.post("/generate_path", json={"goal": "Learn React"})
print(response.status_code)
print(response.json())
