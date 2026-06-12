import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENROUTER_API_KEY", "")
print("API Key starts with:", api_key[:10] if api_key else "None")

openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "https://cs-recommender.com",
    "X-Title": "MASARI",
    "Content-Type": "application/json" 
}
payload = {
    "model": "google/gemini-2.5-flash",
    "messages": [
        {"role": "user", "content": "hello"}
    ],
    "temperature": 0.3,
    "max_tokens": 100
}
res = requests.post(openrouter_url, json=payload, headers=headers)
print("Status code:", res.status_code)
print("Response:", res.text)
