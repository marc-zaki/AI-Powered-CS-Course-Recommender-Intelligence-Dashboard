import requests
import json

url = "https://openrouter.ai/api/v1/models"
try:
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get("data", [])
        
        # Sort by cost and context
        free_models = [m for m in models if m.get("pricing", {}).get("prompt", "0") == "0" and m.get("pricing", {}).get("completion", "0") == "0"]
        print("Top Free Models:")
        for m in sorted(free_models, key=lambda x: x.get("context_length", 0), reverse=True)[:10]:
            print(f"- {m['id']} (Context: {m.get('context_length')})")
            
        print("\nSmartest/Best Value Models (Low Cost, High Intelligence):")
        # Looking for claude or gpt models that are not too expensive
        smart_models = [m for m in models if "claude-3.7" in m.get("id", "") or "gpt-5.5" in m.get("id", "") or "gemini-3.5" in m.get("id", "") or "llama-4" in m.get("id", "")]
        for m in sorted(smart_models, key=lambda x: x.get("context_length", 0), reverse=True)[:10]:
            print(f"- {m['id']} (Context: {m.get('context_length')}) - Cost/1M: {float(m.get('pricing', {}).get('prompt', 0))*1000000:.2f}")

    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Exception: {e}")
