import re

with open('flask_app.py', 'r') as f:
    code = f.read()

# Fix the auth replacement bug from earlier
code = code.replace(
    '"Authorization": f"Bearer {GROQ_API_KEY}"',
    '"Authorization": f"Bearer {OPENROUTER_API_KEY}"
)

# Only replace in transcription endpoint
old_transcribe = """@app.route('/api/interview/transcribe', methods=['POST'])
def api_interview_transcribe():
    \"\"\"
    Accepts an audio file upload, sends it to Groq Whisper API, 
    and returns the transcribed text.
    \"\"\"
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
        
    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY is required for voice transcription"}), 503

    audio_file = request.files['audio']
    
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        audio_file.save(temp_audio.name)
        temp_path = temp_audio.name
        
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }"""
new_transcribe = old_transcribe.replace(
    '"Authorization": f"Bearer {OPENROUTER_API_KEY}"',
    '"Authorization": f"Bearer {GROQ_API_KEY}"'
)
code = code.replace(old_transcribe, new_transcribe)

with open('flask_app.py', 'w') as f:
    f.write(code)

print("Fixed auth tokens")
