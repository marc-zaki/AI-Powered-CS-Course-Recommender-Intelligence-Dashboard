import json
import re

def clean_dataset():
    input_path = '/Users/marczaki/AI-Powered-CS-Course-Recommender-Intelligence-Dashboard/interview_analyzer/storage/dataset_2.json'
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    initial_count = len(data)
    print(f"Initial count: {initial_count}")
    
    cleaned_data = []
    
    # Garbage keywords indicative of scraping errors
    garbage_phrases = [
        "window.dataLayer", 
        "Aptitude Questions and Answers",
        "Play Free Sudoku Online",
        "internships in Web Development",
        "Publish Web Site tool",
        "I have strong interest in",
        "I have completed internships",
        "strong interest in software development",
        "cookie", "privacy policy", "terms of service", "copyright",
        "sign in", "log in", "create account",
        "subscribe", "newsletter",
        "google tag manager", "gtag",
        "Click to Reveal Answer",
        "Interview Questions",
        "adsbygoogle",
        "Enter a page number",
        "Check out the latest",
        "Submit\r\n", "Submit\n",
        "IndiaBIX",
        "Quantitative Aptitude",
        "Mechanical Engineering",
        "Technical Interview Questions",
        "Interview Questions and Answers",
        "applications)"
    ]
    
    for item in data:
        q = item.get('question', '').strip()
        
        # Filter 1: Empty or too short
        if not q or len(q) < 15:
            continue
            
        # Filter 2: Too long (likely an essay or answer)
        if len(q) > 400:
            continue
            
        # Filter 3: Contains garbage phrases
        q_lower = q.lower()
        if any(phrase.lower() in q_lower for phrase in garbage_phrases):
            continue
            
        # Filter 4: Only keep Technical CS questions
        if item.get('main_category', '') != 'Technical':
            continue
            
        # Filter 5: Must look like an actual question
        has_question_mark = '?' in q
        starts_with_question_word = any(q_lower.startswith(w) for w in [
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'explain', 
            'describe', 'define', 'write', 'compare', 'discuss', 'differentiate',
            'can', 'is', 'are', 'do', 'does', 'tell me'
        ])
        
        # If it doesn't have a question mark AND doesn't start with a question/imperative word, 
        # it's probably an answer/paragraph scraped by mistake.
        if not has_question_mark and not starts_with_question_word:
            # Exception for short topics like "Python - Polymorphism" (max 40 chars)
            if len(q) > 40:
                continue
        
        cleaned_data.append(item)
        
    # Reset IDs sequentially
    for i, item in enumerate(cleaned_data):
        item['id'] = i + 1
        
    final_count = len(cleaned_data)
    print(f"Final count: {final_count}")
    print(f"Removed {initial_count - final_count} garbage entries.")
    
    # We will overwrite dataset_2.json
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2)

if __name__ == "__main__":
    clean_dataset()
