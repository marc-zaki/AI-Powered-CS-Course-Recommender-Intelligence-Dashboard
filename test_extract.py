import re
import json

def extract_json_from_llm(text):
    print("Extracting from:")
    print(text[:100], "...")
    try:
        # If the LLM returned code block formatting
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        return {}

sample_response = '''{
  "results": [
    {
      "question": "What is Python?",
      "answer": "A programming language.",
      "relevance_percentage": 95
    }
  ]
}'''
print("Result:", extract_json_from_llm(sample_response))
