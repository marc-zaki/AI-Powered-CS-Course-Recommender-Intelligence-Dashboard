import re
with open('flask_app.py', 'r') as f:
    content = f.read()

# 1. Update Key
content = content.replace('GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")', 'OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")')
content = content.replace('if GROQ_API_KEY:', 'if OPENROUTER_API_KEY:')
content = content.replace('GROQ_API_KEY', 'OPENROUTER_API_KEY')
content = content.replace('groq_url = "https://api.groq.com/openai/v1/chat/completions"', 'openrouter_url = "https://openrouter.ai/api/v1/chat/completions"')
content = content.replace('groq_url', 'openrouter_url')
content = content.replace('"model": "llama-3.3-70b-versatile"', '"model": "google/gemini-2.5-flash"')
content = content.replace('"model": "llama3-70b-8192"', '"model": "google/gemini-2.5-flash"')
content = content.replace('"engine": "groq"', '"engine": "openrouter"')
content = content.replace('Tier 1: Groq Cloud API', 'Tier 1: OpenRouter API')
content = content.replace('Querying Groq Cloud API', 'Querying OpenRouter API')
content = content.replace('using Groq Cloud API!', 'using OpenRouter API!')
content = content.replace('Groq API returned error status', 'OpenRouter API returned error status')
content = content.replace('Groq Cloud connection error', 'OpenRouter Cloud connection error')

with open('flask_app.py', 'w') as f:
    f.write(content)
print("Updated flask_app.py")
