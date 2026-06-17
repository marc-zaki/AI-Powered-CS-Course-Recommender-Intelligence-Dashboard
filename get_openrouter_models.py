import requests
import json

url = "https://openrouter.ai/api/v1/models"
try:
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get("data", [])
        
        # Look for gemini models specifically
        gemini_models = [m for m in models if "gemini" in m.get("id", "").lower()]
        print("Gemini Models:")
        for m in sorted(gemini_models, key=lambda x: x["id"]):
            print(f"- {m['id']}")
            
        print("\nAll Top Models by Context Length:")
        top_models = sorted(models, key=lambda x: x.get("context_length", 0), reverse=True)[:10]
        for m in top_models:
            print(f"- {m['id']} (Context: {m.get('context_length')})")
            
        print(f"\nTotal models available: {len(models)}")
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Exception: {e}")
