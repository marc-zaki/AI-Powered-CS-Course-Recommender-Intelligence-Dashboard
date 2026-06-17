import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENROUTER_API_KEY")

groq_url = "https://openrouter.ai/api/v1/chat/completions"
headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
system_prompt = (
    "You are an expert technical interviewer. Generate 5 highly relevant interview questions "
    "and detailed answers for the query: 'python' at the Intermediate level. "
    "Respond ONLY with a valid JSON object matching this exact schema:\n"
    "{\n"
    "  \"results\": [\n"
    "    {\n"
    "      \"question\": \"<the interview question>\",\n"
    "      \"answer\": \"<detailed explanation>\",\n"
    "      \"relevance_percentage\": <integer from 80 to 99>\n"
    "    }\n"
    "  ]\n"
    "}"
)
payload = {
    "model": "google/gemini-2.5-flash",
    "messages": [{"role": "user", "content": system_prompt}],
    "max_tokens": 1500,
    "temperature": 0.5,
    "response_format": {"type": "json_object"}
}

print("Sending request to OpenRouter with exact prompt...")
start_time = time.time()
try:
    res = requests.post(groq_url, json=payload, headers=headers, timeout=15.0)
    print("Time taken:", time.time() - start_time)
    print("Status:", res.status_code)
    if res.status_code != 200:
        print("Error:", res.text)
    else:
        print("Success:", len(res.text), "bytes")
except Exception as e:
    print("Exception:", str(e))
    print("Time taken:", time.time() - start_time)
