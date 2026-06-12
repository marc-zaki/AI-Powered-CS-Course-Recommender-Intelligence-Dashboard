import re

with open('flask_app.py', 'r') as f:
    content = f.read()

# Replace GROQ_API_KEY with OPENROUTER_API_KEY
content = content.replace('GROQ_API_KEY', 'OPENROUTER_API_KEY')

# Replace groq URLs
content = content.replace('https://api.groq.com/openai/v1/chat/completions', 'https://openrouter.ai/api/v1/chat/completions')

# Replace llama-3.3-70b-versatile with google/gemini-2.5-flash
content = content.replace('"llama-3.3-70b-versatile"', '"google/gemini-2.5-flash"')
content = content.replace("'llama-3.3-70b-versatile'", '"google/gemini-2.5-flash"')

# Replace headers for OpenRouter
old_header_1 = '{"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}'
new_header = '{"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}'
content = content.replace(old_header_1, new_header)

with open('flask_app.py', 'w') as f:
    f.write(content)

print("Fixed remaining Groq references in flask_app.py")
