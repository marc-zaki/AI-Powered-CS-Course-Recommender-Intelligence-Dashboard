with open('flask_app.py', 'r') as f:
    content = f.read()

header_replacement = """                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://cs-recommender.com",
                "X-Title": "MASARI",
                "Content-Type": "application/json" """

# Find all blocks of:
# "Authorization": f"Bearer {OPENROUTER_API_KEY}",
# "Content-Type": "application/json"

import re
# Use regex to replace Authorization and Content-Type with the new headers
pattern = r'"Authorization": f"Bearer \{OPENROUTER_API_KEY\}",\s*"Content-Type": "application/json"'
content = re.sub(pattern, header_replacement.strip(), content)

with open('flask_app.py', 'w') as f:
    f.write(content)
print("Updated headers in flask_app.py")
