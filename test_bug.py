import asyncio
from fastapi.testclient import TestClient
from main import app
import hashlib

with TestClient(app) as client:
    # use random email to avoid duplicate key
    import random
    email = f"test{random.randint(1,1000)}@test.com"
    response = client.post('/register', data={'name': 'test2', 'email': email, 'password': 'password', 'track': '', 'career_goals': '', 'skill_level': 'Beginner'}, follow_redirects=True)
    print("STATUS:", response.status_code)
    print("TEXT:", response.text[:200])
