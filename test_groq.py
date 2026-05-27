import os
import requests
from dotenv import load_dotenv

load_dotenv()

groq_key = os.environ.get("GROQ_API_KEY", "")
if not groq_key:
    print("[ERROR] GROQ_API_KEY is not set.")
    exit(1)

groq_url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {groq_key}",
    "Content-Type": "application/json"
}

# Test model 1: llama-3.1-70b-versatile (current model in code)
payload = {
    "model": "llama-3.1-70b-versatile",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
}

print("Testing llama-3.1-70b-versatile...")
res = requests.post(groq_url, json=payload, headers=headers)
print(f"Status Code: {res.status_code}")
print(f"Response: {res.text}\n")

# Test model 2: llama-3.3-70b-versatile
payload["model"] = "llama-3.3-70b-versatile"
print("Testing llama-3.3-70b-versatile...")
res = requests.post(groq_url, json=payload, headers=headers)
print(f"Status Code: {res.status_code}")
print(f"Response: {res.text}\n")

# Test model 3: llama-3.1-8b-instant
payload["model"] = "llama-3.1-8b-instant"
print("Testing llama-3.1-8b-instant...")
res = requests.post(groq_url, json=payload, headers=headers)
print(f"Status Code: {res.status_code}")
print(f"Response: {res.text}\n")
