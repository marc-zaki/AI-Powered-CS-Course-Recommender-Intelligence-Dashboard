import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENROUTER_API_KEY")

groq_url = "https://openrouter.ai/api/v1/chat/completions"
headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
system_prompt = (
    "You are an expert technical interviewer. Generate 1 interview question. "
    "Respond ONLY with a valid JSON object matching this exact schema:\n"
    "{\n"
    "  \"results\": [\n"
    "    {\n"
    "      \"question\": \"<the interview question>\",\n"
    "      \"answer\": \"<detailed explanation>\"\n"
    "    }\n"
    "  ]\n"
    "}"
)
payload = {
    "model": "meta-llama/llama-4-scout",
    "messages": [{"role": "user", "content": system_prompt}],
    "max_tokens": 1500,
    "temperature": 0.5,
    "response_format": {"type": "json_object"}
}

res = requests.post(groq_url, json=payload, headers=headers)
print("Status Scout:", res.status_code)
print("Response:", res.text)
