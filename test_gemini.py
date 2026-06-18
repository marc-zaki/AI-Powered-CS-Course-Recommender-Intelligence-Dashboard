import asyncio
import os
from fastapi.testclient import TestClient
from main import app

os.environ["OPENROUTER_API_KEY"] = ""
# we leave GEMINI_API_KEY as is

client = TestClient(app)
response = client.post("/generate_path", json={"goal": "Learn Python"})
print(response.status_code)
print(response.json())
