with open('flask_app.py', 'r') as f:
    content = f.read()

content = content.replace('Groq API returned status', 'OpenRouter API returned status')
content = content.replace('Groq Quiz Generation failed', 'OpenRouter Quiz Generation failed')
content = content.replace('# Tier 1: Groq', '# Tier 1: OpenRouter')
content = content.replace('groq_err', 'openrouter_err')

with open('flask_app.py', 'w') as f:
    f.write(content)
print("Fixed remaining Groq references in flask_app.py")
