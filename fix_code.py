import re

with open('flask_app.py', 'r') as f:
    code = f.read()

# 1. Add GROQ_API_KEY back to configuration section
code = re.sub(
    r'OPENROUTER_API_KEY = os\.environ\.get\("OPENROUTER_API_KEY", ""\)\n',
    r'OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")\nGROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")\n',
    code
)

# 2. Add extract_json_from_llm utility function right after configuration
json_util = """
def extract_json_from_llm(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    import json
    try:
        return json.loads(text.strip())
    except Exception as e:
        print(f"JSON parsing error: {e}")
        return {}
"""
if "def extract_json_from_llm(" not in code:
    code = code.replace('GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")\n', 'GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")\n' + json_util)

# 3. Fix api_interview_transcribe to use GROQ_API_KEY
code = code.replace(
    'if not OPENROUTER_API_KEY:\n        return jsonify({"error": "OPENROUTER_API_KEY is required for voice transcription"}), 503',
    'if not GROQ_API_KEY:\n        return jsonify({"error": "GROQ_API_KEY is required for voice transcription"}), 503'
)
code = code.replace(
    '\'Authorization\': f"Bearer {OPENROUTER_API_KEY}"',
    '\'Authorization\': f"Bearer {GROQ_API_KEY}"'
)
code = code.replace(
    '"Authorization": f"Bearer {OPENROUTER_API_KEY}"',
    '"Authorization": f"Bearer {GROQ_API_KEY}"'
)

# 4. Fix JSON extraction logic
code = re.sub(
    r'import json as _json\n\s*data = _json\.loads\(res\.json\(\)\["choices"\]\[0\]\["message"\]\["content"\]\)',
    r'data = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])',
    code
)
code = re.sub(
    r'import json as _json\n\s*result = _json\.loads\(res\.json\(\)\["choices"\]\[0\]\["message"\]\["content"\]\)',
    r'result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])',
    code
)

code = re.sub(
    r'import json as _json\n\s*text = response\.text\.strip\(\)\n\s*if text\.startswith\("```"\):\n\s*text = text\.split\("```"\)\[1\]\n\s*if text\.startswith\("json"\):\n\s*text = text\[4:\]\n\s*data = _json\.loads\(text\)',
    r'data = extract_json_from_llm(response.text)',
    code
)
code = re.sub(
    r'import json as _json\n\s*text = response\.text\.strip\(\)\n\s*# Strip any markdown fences if present\n\s*if text\.startswith\("```"\):\n\s*text = text\.split\("```"\)\[1\]\n\s*if text\.startswith\("json"\):\n\s*text = text\[4:\]\n\s*result = _json\.loads\(text\)',
    r'result = extract_json_from_llm(response.text)',
    code
)
code = re.sub(
    r'import json as _json\n\s*text = response\.text\.strip\(\)\n\s*if text\.startswith\("```"\):\n\s*text = text\.split\("```"\)\[1\]\n\s*if text\.startswith\("json"\):\n\s*text = text\[4:\]\n\s*result = _json\.loads\(text\)',
    r'result = extract_json_from_llm(response.text)',
    code
)

with open('flask_app.py', 'w') as f:
    f.write(code)
