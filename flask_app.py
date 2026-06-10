from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ssl
import os
import time
import json
import threading
import requests
import uuid
import urllib.parse
from datetime import datetime, timedelta
from bson.objectid import ObjectId

from dotenv import load_dotenv
import google.generativeai as genai
import pymongo

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'Interview-Question-Analyzer-main'))
from phase2_ir_engine import IREngine
from phase2_ai_models import AIModels
from phase2_recommendation import RecommendationEngine
from phase2_eda_analysis import EDAAnalysis

load_dotenv()  # Load API keys from .env file


# Configuration loaded from .env file
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download NLTK data
try:
    if os.environ.get("VERCEL") == "1":
        nltk.data.path.append('/tmp')
        nltk.download('vader_lexicon', download_dir='/tmp', quiet=True)
        nltk.download('stopwords', download_dir='/tmp', quiet=True)
        nltk.download('punkt', download_dir='/tmp', quiet=True)
        nltk.download('punkt_tab', download_dir='/tmp', quiet=True)
        nltk.download('averaged_perceptron_tagger', download_dir='/tmp', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', download_dir='/tmp', quiet=True)
    else:
        nltk.download('vader_lexicon', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
except Exception:
    pass

def extract_review_summary(reviews_list):
    if not reviews_list:
        return ""
    
    # Simple extraction of common noun phrases/adjectives
    all_text = " ".join(reviews_list).lower()
    stop_words = set(stopwords.words('english'))
    # additional stop words for reviews
    stop_words.update(['course', 'class', 'good', 'great', 'excellent', 'awesome', 'learned', 'learning', 'really', 'much', 'well', 'lot', 'this', 'the', 'it', 'is', 'a', 'to', 'and', 'of', 'in', 'i', 'for'])
    
    words = word_tokenize(re.sub(r'[^a-z\s]', '', all_text))
    filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
    
    if not filtered_words:
        return f"Based on {len(reviews_list)} reviews."
        
    # Get frequent words
    from collections import Counter
    word_counts = Counter(filtered_words)
    top_words = [word for word, count in word_counts.most_common(3)]
    
    if len(top_words) >= 2:
        return f"Based on {len(reviews_list)} reviews, students frequently mention: {', '.join(top_words)}."
    elif len(top_words) == 1:
        return f"Based on {len(reviews_list)} reviews, students frequently mention: {top_words[0]}."
    else:
        return f"Based on {len(reviews_list)} positive reviews."

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

# Global variables for AI model
df = None
vectorizer = None
tfidf_matrix = None
mongo_client = None
mongo_db = None

# Global scraper state (shared across threads)
scraper_state = {
    "status": "idle",   # idle | running | done | error
    "log": [],
    "inserted": 0,
    "found": 0,
    "started_at": None,
    "finished_at": None,
}

# Global variables for Interview Analyzer
interview_ir_engine = None
interview_ai_models = None
interview_rec_engine = None
interview_eda = None
interview_questions = []

def get_db():
    global mongo_client, mongo_db
    if mongo_db is not None:
        return mongo_db
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        mongo_client.server_info()
        mongo_db = mongo_client["cs_recommender"]
        return mongo_db
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None

def check_is_super_admin(user):
    if not user:
        return False
    # Check environment variable
    super_admin_emails = os.environ.get("SUPER_ADMIN_EMAILS", os.environ.get("SUPER_ADMIN_EMAIL", ""))
    if super_admin_emails:
        emails = [e.strip().lower() for e in super_admin_emails.split(",") if e.strip()]
        if user.get("email", "").strip().lower() in emails:
            return True
    # Check database properties
    if user.get("is_super_admin") is True or user.get("role") == "super_admin":
        return True
    return False

def load_and_train_model():
    global df, vectorizer, tfidf_matrix
    print("Loading data and training AI model...")
    
    db_name = "cs_recommender"
    collection_name = "courses"
    loaded_from_mongo = False
    
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    try:
        if os.environ.get("VERCEL") == "1":
            raise Exception("Vercel deployment detected, bypassing MongoDB load for AI model to prevent Serverless timeout.")
            
        db = get_db()
        if db is None:
            raise Exception("Could not connect to MongoDB")
        collection = db[collection_name]
        
        # If collection is empty, auto-seed it from JSON
        if collection.count_documents({}) == 0:
            db_file = "datasets/CS_Dataset_Phase2.json" if os.path.exists("datasets/CS_Dataset_Phase2.json") else "CS_Dataset_Phase2.json"
            print(f"MongoDB collection is empty. Seeding from {db_file}...")
            if os.path.exists(db_file):
                with open(db_file, "r") as f:
                    courses_data = json.load(f)
                if courses_data:
                    collection.insert_many(courses_data)
                    print(f"Successfully seeded {len(courses_data)} courses into MongoDB!")
            else:
                print(f"Warning: {db_file} not found, cannot seed MongoDB.")
                
        # Load directly from MongoDB
        mongo_courses = list(collection.find({}, {'_id': 0}))
        if mongo_courses:
            df = pd.DataFrame(mongo_courses)
            print(f"Successfully loaded {len(df)} records directly from MongoDB!")
            loaded_from_mongo = True
    except Exception as mongo_err:
        print(f"MongoDB connection failed: {mongo_err}")
        db_file = "datasets/CS_Dataset_Phase2.json" if os.path.exists("datasets/CS_Dataset_Phase2.json") else "CS_Dataset_Phase2.json"
        print(f"Falling back to local {db_file} dataset file...")
        
    # Local JSON fallback if MongoDB loading didn't succeed
    if not loaded_from_mongo:
        try:
            db_file = "datasets/CS_Dataset_Phase2.json" if os.path.exists("datasets/CS_Dataset_Phase2.json") else "CS_Dataset_Phase2.json"
            df = pd.read_json(db_file)
            print(f"Successfully loaded {len(df)} records from local JSON fallback ({db_file}).")
        except Exception as e:
            print(f"Error loading local dataset: {e}")
            return

    # Ensure ratings_count column exists
    if 'ratings_count' not in df.columns:
        df['ratings_count'] = 0

    # Calculate 1-5 Stars using Sentiment + Platform Prestige if missing or 0
    sia = SentimentIntensityAnalyzer()
    def calculate_ai_rating(row):
        # If the row already has a real star rating from Kaggle or scraping, preserve the decimal!
        existing_stars = row.get('stars')
        if pd.notnull(existing_stars) and float(existing_stars) > 0:
            return float(existing_stars)

        text = str(row.get('content_text', ''))
        raw_reviews = row.get('raw_reviews', [])
        
        # Calculate base sentiment from description
        desc_sentiment = sia.polarity_scores(text)['compound'] if text and text != "No description provided." else 0
        
        # Calculate review sentiment if available
        review_sentiment = 0
        if isinstance(raw_reviews, list) and raw_reviews:
            review_scores = [sia.polarity_scores(str(r))['compound'] for r in raw_reviews]
            review_sentiment = sum(review_scores) / len(review_scores)
            sentiment = (desc_sentiment * 0.3) + (review_sentiment * 0.7)
        else:
            sentiment = desc_sentiment
            
        stars = (sentiment + 1) * 1.0 + 2.5
        if any(p in str(row.get('provider', '')).lower() for p in ['mit', 'google', 'stanford', 'coursera']):
            stars += 0.8
        return min(max(round(stars, 1), 1.0), 5.0)

    df['stars'] = df.apply(calculate_ai_rating, axis=1)
    
    # Dynamically generate a consistent, realistic reviews count if missing or zero
    def calculate_ratings_count(row):
        val = row.get('ratings_count')
        # If there's already a real count in the database (non-zero), keep it!
        if pd.notnull(val) and int(val) > 0:
            return int(val)
            
        title = str(row.get('title', ''))
        provider = str(row.get('provider', '')).lower()
        stars = float(row.get('stars', 4.0))
        
        # Deterministic count using title character sum to ensure consistency
        base_hash = sum(ord(c) for c in title) % 450 + 50
        
        multiplier = 1.0
        if any(p in provider for p in ['mit', 'stanford', 'harvard', 'oxford', 'yale']):
            multiplier = 6.8
        elif any(p in provider for p in ['google', 'ibm', 'microsoft', 'aws', 'meta']):
            multiplier = 9.5
        elif any(p in provider for p in ['coursera', 'udemy', 'edx']):
            multiplier = 4.2
            
        rating_boost = (stars - 2.5) ** 2 + 1.0
        return int(base_hash * multiplier * rating_boost)
        
    df['ratings_count'] = df.apply(calculate_ratings_count, axis=1).fillna(0).astype(int)
    
    # Calculate stars_int specifically for Jinja range loop rendering (1 to 5)
    df['stars_int'] = df['stars'].apply(lambda x: min(max(round(float(x)), 1), 5))

    # Train TF-IDF
    def build_search_profile(row):
        title = str(row.get('title', ''))
        desc = str(row.get('content_text', ''))
        summary = str(row.get('review_summary', ''))
        reviews = " ".join([str(r) for r in row.get('raw_reviews', [])]) if isinstance(row.get('raw_reviews'), list) else ""
        return f"{title} {title} {title} {title} {title} {title} {title} {title} {title} {title} {desc} {summary} {reviews}".lower()

    df['search_profile'] = df.apply(build_search_profile, axis=1)
    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(df['search_profile'])
    print(f"Successfully loaded {len(df)} courses!")



# Load model at startup
load_and_train_model()

def load_interview_system():
    global interview_ir_engine, interview_ai_models, interview_rec_engine, interview_eda, interview_questions
    print("Loading Interview Analyzer system...")
    try:
        dataset_path = os.path.join(os.path.dirname(__file__), 'Interview-Question-Analyzer-main', 'storage', 'dataset_2.json')
        with open(dataset_path, 'r', encoding='utf-8') as f:
            interview_questions = json.load(f)
        
        interview_ir_engine = IREngine(interview_questions)
        interview_ai_models = AIModels(interview_questions)
        interview_rec_engine = RecommendationEngine(interview_ir_engine, interview_ai_models)
        interview_eda = EDAAnalysis(interview_questions, interview_ir_engine, interview_ai_models)
        
        # Load indexes
        storage_path = os.path.join(os.path.dirname(__file__), 'Interview-Question-Analyzer-main', 'storage')
        interview_ir_engine.load_index(storage_path)
        interview_ai_models.load_models(storage_path)
        
        print("Interview Analyzer models loaded successfully!")
    except Exception as e:
        print(f"Error loading Interview Analyzer system: {e}")

load_interview_system()

def clean_user_query(query):
    stop_words = set(stopwords.words('english'))
    text = str(query).lower()
    text = re.sub(r'[^a-z\s]', '', text) 
    tokens = word_tokenize(text) 
    cleaned_query = [word for word in tokens if word not in stop_words]
    return " ".join(cleaned_query)

@app.route('/')
def index():
    if df is None:
        return "Error: Dataset not loaded. Please ensure datasets/CS_Dataset_Phase2.json exists.", 500

    user = None
    if 'user_id' in session:
        db = get_db()
        if db is not None:
            user = db.users.find_one({"_id": session['user_id']})

    featured_df = df.copy()
    is_personalized = False
    
    if user:
        taken_courses = user.get('taken_courses', [])
        query_terms = [user.get('track', ''), user.get('career_goals', '')]
        query = " ".join([t for t in query_terms if t]).strip()
        
        if len(query) > 5:
            query_vector = vectorizer.transform([query.lower()])
            search_df = df.copy()
            search_df['match_score'] = cosine_similarity(query_vector, tfidf_matrix).flatten()
            search_df = search_df[~search_df['url'].isin(taken_courses)]
            featured = search_df.sort_values(by=['match_score', 'stars'], ascending=[False, False]).head(12)
            is_personalized = True
        else:
            featured_df = featured_df[~featured_df['url'].isin(taken_courses)]
            featured_df['has_review'] = featured_df['review_summary'].apply(lambda x: 1 if x and str(x).strip() else 0)
            featured = featured_df.sort_values(by=['stars', 'has_review'], ascending=[False, False]).head(12)
    else:
        featured_df['has_review'] = featured_df['review_summary'].apply(lambda x: 1 if x and str(x).strip() else 0)
        featured = featured_df.sort_values(by=['stars', 'has_review'], ascending=[False, False]).head(12)

    courses = featured.to_dict('records')
    return render_template('index.html', courses=courses, query="", is_search=False, show_all=False, total_courses=len(df), page=1, total_pages=1, is_personalized=is_personalized)

@app.route('/all')
def all_courses():
    if df is None:
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    per_page = 30
    total_pages = max(1, -(-len(df) // per_page))  # Ceiling division
    page = max(1, min(page, total_pages))
    
    sorted_df = df.sort_values(by='stars', ascending=False)
    start = (page - 1) * per_page
    end = start + per_page
    courses = sorted_df.iloc[start:end].to_dict('records')
    
    return render_template('index.html', courses=courses, query="", is_search=False, show_all=True, total_courses=len(df), page=page, total_pages=total_pages)

@app.route('/search', methods=['GET'])
def search():
    if df is None:
        return redirect(url_for('index'))

    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('index'))

    query_vector = vectorizer.transform([query.lower()])
    
    search_df = df.copy()
    search_df['match_score'] = cosine_similarity(query_vector, tfidf_matrix).flatten()
    
    # Try strict search (0.15) first
    recs = search_df[search_df['match_score'] > 0.15].sort_values(by=['stars', 'match_score'], ascending=[False, False])
    
    # If nothing found, try loose search (0.02)
    if recs.empty:
        recs = search_df[search_df['match_score'] > 0.02].sort_values(by=['stars', 'match_score'], ascending=[False, False])
        
    # Feature 4: Unified Global Search
    interview_results = []
    if interview_ir_engine:
        try:
            interview_results = interview_ir_engine.search(query, top_k=5, method='hybrid')
        except Exception:
            pass

    return render_template('index.html', courses=results, interview_results=interview_results, query=query, is_search=True, show_all=False, total_courses=len(df), page=1, total_pages=1)

@app.route('/validate_link')
def validate_link():
    url = request.args.get('url', '').strip()
    title = request.args.get('title', '').strip()
    provider = request.args.get('provider', '').strip()
    
    if not url:
        return jsonify({"valid": False, "fallback_url": "/"})
        
    # Generate foolproof search fallback URLs
    fallback_url = url
    if provider.lower() == 'udemy':
        fallback_url = f"https://www.udemy.com/courses/search/?q={urllib.parse.quote(title)}"
    elif provider.lower() == 'coursera':
        fallback_url = f"https://www.coursera.org/search?query={urllib.parse.quote(title)}"
    elif provider.lower() == 'edx':
        fallback_url = f"https://www.edx.org/search?q={urllib.parse.quote(title)}"
        
    # We do a quick check
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Use HEAD request for speed, follow redirects, timeout of 2.0s
        res = requests.head(url, headers=headers, timeout=2.0, allow_redirects=True)
        # If HEAD fails or is not allowed, try GET
        if res.status_code == 404 or res.status_code == 403:
            res = requests.get(url, headers=headers, timeout=2.0, allow_redirects=True)
            
        if res.status_code == 404:
            return jsonify({"valid": False, "fallback_url": fallback_url})
        return jsonify({"valid": True, "fallback_url": url})
    except Exception as e:
        # On connection errors or timeout, fallback to the search page just to be safe!
        return jsonify({"valid": False, "fallback_url": fallback_url})

@app.route('/verify_link')
def verify_link():
    url = request.args.get('url', '').strip()
    title = request.args.get('title', '').strip()
    provider = request.args.get('provider', '').strip()
    
    if not url:
        return redirect('/')
        
    fallback_url = url
    if provider.lower() == 'udemy':
        fallback_url = f"https://www.udemy.com/courses/search/?q={urllib.parse.quote(title)}"
    elif provider.lower() == 'coursera':
        fallback_url = f"https://www.coursera.org/search?query={urllib.parse.quote(title)}"
    elif provider.lower() == 'edx':
        fallback_url = f"https://www.edx.org/search?q={urllib.parse.quote(title)}"
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Use HEAD request for maximum speed, timeout of 1.5s
        res = requests.head(url, headers=headers, timeout=1.5, allow_redirects=True)
        if res.status_code == 404:
            return redirect(fallback_url)
        return redirect(url)
    except Exception:
        return redirect(fallback_url)

@app.route('/interview-prep')
def interview_prep():
    # The frontend strategy (Step 3) will render 'interview_analyzer.html' here
    return render_template('interview_analyzer.html')

@app.route('/api/interview/search', methods=['GET'])
def api_interview_search():
    if not interview_ir_engine:
        return jsonify({"error": "Interview system not loaded"}), 500
        
    query = request.args.get('q', '')
    difficulty = request.args.get('difficulty', 'Intermediate')
    
    if not query:
        return jsonify({"results": [], "recommendations": []})
        
    # Perform Search
    results = interview_ir_engine.search(query, top_k=10, method='hybrid')
    
    # Perform AI Analysis on the query
    analysis = interview_ai_models.analyze_question_comprehensive(query)
    
    # Get Recommendations
    recommendations = interview_rec_engine.get_recommendations(query, difficulty, top_k=5)
    
    # Feature 1: Skill-Gap Recommendations (Interviews -> Courses)
    related_courses = []
    if df is not None and not df.empty and vectorizer is not None:
        query_vector = vectorizer.transform([query.lower()])
        search_df = df.copy()
        search_df['match_score'] = cosine_similarity(query_vector, tfidf_matrix).flatten()
        recs = search_df[search_df['match_score'] > 0.05].sort_values(by=['stars', 'match_score'], ascending=[False, False])
        
        for c in recs.head(3).to_dict('records'):
            related_courses.append({
                "title": c.get("title"),
                "provider": c.get("provider"),
                "url": c.get("url", "#"),
                "stars": c.get("stars"),
                "ratings_count": c.get("ratings_count", 0),
                "description": c.get("content_text", "")[:100] + "..."
            })
    
    return jsonify({
        "results": results,
        "analysis": analysis,
        "recommendations": recommendations,
        "related_courses": related_courses
    })

@app.route('/api/interview/explain', methods=['GET'])
def api_interview_explain():
    question = request.args.get('q', '').strip()
    if not question:
        return jsonify({"explanation": None}), 400

    system_prompt = "You are an elite technical interviewer. Provide a clear, accurate, and concise answer and explanation (around 3-4 sentences) for the following interview question. Use markdown for code if necessary."
    user_prompt = f"Interview Question: {question}\n\nPlease provide the answer and explanation."

    explanation = None
    
    # Tier 1: Groq
    if GROQ_API_KEY:
        try:
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }
            res = requests.post(groq_url, json=payload, headers=headers, timeout=5.0)
            if res.status_code == 200:
                explanation = res.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    # Tier 2: Gemini
    if not explanation and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )
            response = model.generate_content(user_prompt)
            explanation = response.text.strip()
        except Exception:
            pass

    return jsonify({"explanation": explanation})

@app.route('/api/stats')
def api_stats():
    # Only allow admin access
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
    db = get_db()
    if db is not None:
        user = db.users.find_one({"_id": session['user_id']})
        if not user or (user.get('role') != 'admin' and not check_is_super_admin(user)):
            return jsonify({"success": False, "error": "Forbidden. Admin access required."}), 403
    else:
        return jsonify({"success": False, "error": "Database connection error."}), 500

    if df is None or len(df) == 0:
        return jsonify({"success": False, "error": "Database is not loaded."}), 500
        
    try:
        # 1. Total metric values
        total_courses = int(len(df))
        avg_rating = round(float(df['stars'].mean()), 2) if 'stars' in df.columns else 4.2
        total_reviews = int(df['ratings_count'].sum()) if 'ratings_count' in df.columns else 0
        
        # 2. Provider Distribution
        provider_counts = df['provider'].value_counts().to_dict()
        
        # 3. Difficulty Distribution (Classifying on-the-fly via title & description keywords)
        def classify_row(row):
            title = str(row.get('title', '')).lower()
            desc = str(row.get('content_text', '')).lower()
            full_text = f"{title} {desc}"
            if any(k in full_text for k in ["beginner", "introduction", "intro", "basic", "fundamental", "foundation", "101"]):
                return "Beginner"
            elif any(k in full_text for k in ["advanced", "expert", "deep dive", "senior", "mastery"]):
                return "Advanced"
            return "Intermediate"
            
        diff_series = df.apply(classify_row, axis=1)
        difficulty_share = diff_series.value_counts().to_dict()
        
        # 4. Keyword Frequency Statistics (Information Retrieval statistics!)
        keywords = ["python", "javascript", "data science", "machine learning", "algorithms", "web development", "databases", "security", "cloud", "artificial intelligence", "c++", "software"]
        keyword_frequencies = {}
        for kw in keywords:
            desc_col = 'content_text' if 'content_text' in df.columns else 'description'
            keyword_frequencies[kw] = int(df[desc_col].str.contains(kw, case=False, na=False).sum())
            
        # 5. Rating Histogram Bins
        stars = df['stars'].fillna(0)
        ratings_bins = {
            "4.5 - 5.0": int((stars >= 4.5).sum()),
            "4.0 - 4.5": int(((stars >= 4.0) & (stars < 4.5)).sum()),
            "3.5 - 4.0": int(((stars >= 3.5) & (stars < 4.0)).sum()),
            "Under 3.5": int((stars < 3.5).sum())
        }
        
        return jsonify({
            "success": True,
            "metrics": {
                "total_courses": total_courses,
                "avg_rating": avg_rating,
                "total_reviews": total_reviews
            },
            "provider_distribution": provider_counts,
            "difficulty_distribution": difficulty_share,
            "keyword_frequencies": keyword_frequencies,
            "ratings_distribution": ratings_bins
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/random_course')
def api_random_course():
    global df
    try:
        # Dynamic loader failover
        if df is None or df.empty:
            for db_file in ["datasets/CS_Dataset_Phase2.json", "CS_Dataset_Phase2.json"]:
                if os.path.exists(db_file):
                    df = pd.read_json(db_file)
                    print(f"Dynamically loaded database from {db_file}")
                    break
        
        if df is not None and not df.empty:
            random_row = df.sample(n=1).iloc[0]
            
            stars = float(random_row.get("stars", 4.5))
            ratings_count = int(random_row.get("ratings_count", 1500))
            
            course_data = {
                "title": str(random_row.get("title", "Computer Science Course")),
                "provider": str(random_row.get("provider", "Elite Institution")),
                "stars": stars,
                "ratings_count": ratings_count,
                "content_text": str(random_row.get("content_text", "Explore core Computer Science algorithms and principles in this course.")),
                "url": str(random_row.get("url", "#"))
            }
            return jsonify({"success": True, "course": course_data})
        return jsonify({"success": False, "error": "Database not initialized"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/graph_data')
def graph_data():
    if df is None or len(df) == 0:
        return jsonify({"nodes": [], "links": []})
    
    # Select the top 25 courses for each unique provider to ensure fair representation in the network
    sample_df = df.copy()
    provider_samples = []
    unique_providers = sample_df['provider'].unique()
    for provider in unique_providers:
        p_sample = sample_df[sample_df['provider'] == provider].sort_values(
            by=['stars', 'ratings_count'], ascending=[False, False]
        ).head(25)
        provider_samples.append(p_sample)
        
    if provider_samples:
        combined_sample = pd.concat(provider_samples).drop_duplicates(subset=['title'])
    else:
        combined_sample = pd.DataFrame()
    
    # If we don't have enough total nodes, fallback to the top 100 overall
    if len(combined_sample) < 50:
        combined_sample = sample_df.sort_values(by=['stars', 'ratings_count'], ascending=[False, False]).head(100)
        
    combined_sample = combined_sample.reset_index(drop=True)
    
    # Construct nodes
    nodes = []
    for idx, row in combined_sample.iterrows():
        # Assign category group based on keywords (prioritize Web/Security/Software first to prevent character overlaps like 'html' matching 'ml')
        title = row['title'].lower()
        group = "General CS"
        if any(w in title for w in ['web', 'html', 'css', 'react', 'js', 'javascript', 'node', 'django', 'flask', 'angular', 'vue']):
            group = "Web Development"
        elif any(w in title for w in ['security', 'cyber', 'network', 'firewall', 'attack', 'cryptography', 'penetration', 'ethical hacking']):
            group = "Cybersecurity"
        elif any(w in title for w in ['java', 'c++', 'c#', 'programming', 'code', 'coding', 'kotlin', 'swift', 'go', 'rust', 'typescript']):
            group = "Software Engineering"
        elif any(w in title for w in ['python', 'machine learning', 'deep learning', 'intelligence', 'ai', 'data science', 'neural', 'nlp', 'pytorch', 'tensorflow']) or re.search(r'\bml\b', title):
            group = "AI & Data Science"
            
        nodes.append({
            "id": int(idx),
            "title": row['title'],
            "provider": row['provider'],
            "stars": float(row['stars']),
            "url": row['url'],
            "group": group
        })
        
    # Construct links based on similarity threshold
    sample_profiles = combined_sample.apply(
        lambda r: f"{r.get('title', '')} {r.get('content_text', '')}".lower(), axis=1
    )
    sample_vec = vectorizer.transform(sample_profiles)
    sim_matrix = cosine_similarity(sample_vec)
    
    links = []
    for i in range(len(combined_sample)):
        for j in range(i + 1, len(combined_sample)):
            sim = float(sim_matrix[i, j])
            # Link if similarity is strong (0.13 provides a beautifully clustered network map)
            if sim > 0.13:
                links.append({
                    "source": i,
                    "target": j,
                    "value": sim
                })
                
    return jsonify({"nodes": nodes, "links": links})

def generate_local_fallback_path(user_goal, matched_courses):
    """
    Generates a beautifully structured, highly customized, and comprehensive 6-week
    academic syllabus from the matched courses when Gemini API rate limits/quotas are exceeded.
    """
    html = []
    
    # 1. Graceful API notice banner
    html.append(
        '<div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); '
        'border-radius: 10px; padding: 1.15rem; margin-bottom: 2rem; display: flex; align-items: center; '
        'gap: 0.85rem; color: #F59E0B; font-size: 0.925rem; font-weight: 600; line-height: 1.55;">'
        '<span style="font-size: 1.25rem;"><i data-lucide="alert-triangle" style="width: 20px; height: 20px; display: inline-block;"></i></span>'
        '<span><strong>Gemini Free-Tier Rate Limit Exceeded:</strong> Your intelligence dashboard has automatically '
        'rerouted to your local high-fidelity VSM Academic Planner to preserve system operational integrity and deliver '
        'your study plan immediately without errors.</span>'
        '</div>'
    )
    
    html.append(f'<h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 1.5rem; background: linear-gradient(135deg, var(--text-main) 30%, var(--primary) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.02em;">6-Week Academic Curriculum</h2>')
    html.append(f'<p style="color: var(--text-muted); line-height: 1.65; margin-bottom: 2rem; font-size: 0.95rem;">This tailored syllabus has been synthesized using vector space TF-IDF cosine-similarity rankings matching your career target: <strong style="color: var(--text-main);">"{user_goal}"</strong>. It arranges your target courses in logical developmental order from fundamental theory to final advanced mastery.</p>')
    
    weeks_info = [
        {"title": "Week 1: Foundational Core & Groundwork", "focus": "Establishing essential concepts, introductory structures, and theoretical principles."},
        {"title": "Week 2: Intermediate Implementation & Systems", "focus": "Stepping into core programming structures, systems development, and data pipelines."},
        {"title": "Week 3: Advanced Architectures & Methodology", "focus": "Deepening methodology, scaling applications, and studying critical algorithms."},
        {"title": "Week 4: Practical Deployments & Integration", "focus": "Bringing concepts together through practical tooling, APIs, and real-world system interfaces."},
        {"title": "Week 5: Enterprise Scaling & Deep Specialization", "focus": "Covering expert topics, performance optimizations, and domain-level complexities."},
        {"title": "Week 6: Capstone Optimization & Full Mastery", "focus": "Synthesizing your skills into an advanced final portfolio project to demonstrate professional competence."}
    ]
    
    for i, week in enumerate(weeks_info):
        c1_idx = i * 2
        c2_idx = i * 2 + 1
        
        if c1_idx >= len(matched_courses):
            break
            
        c1 = matched_courses[c1_idx]
        c2 = matched_courses[c2_idx] if c2_idx < len(matched_courses) else None
        
        html.append(f'<div class="path-step" style="background: var(--card-bg); border: 1px solid var(--border-glass); border-radius: 12px; padding: 1.75rem; margin-bottom: 1.75rem; box-shadow: var(--shadow-glass);">')
        html.append(f'<h3 style="color: var(--secondary); font-size: 1.25rem; font-weight: 700; margin-bottom: 0.35rem;">{week["title"]}</h3>')
        html.append(f'<p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1.25rem; font-style: italic;">Focus Area: {week["focus"]}</p>')
        
        html.append('<ul style="padding-left: 1.2rem; margin-bottom: 1.25rem; list-style-type: square; color: var(--text-muted);">')
        
        # Course 1
        c1_stars = float(c1.get('stars', 4.5))
        c1_reviews = int(c1.get('ratings_count', 1500))
        c1_url = c1.get('url', '#')
        c1_redirect = f"/verify_link?url={urllib.parse.quote(c1_url)}&title={urllib.parse.quote(c1.get('title'))}&provider={urllib.parse.quote(c1.get('provider'))}" if c1_url != '#' else '#'
        
        html.append(f'<li style="margin-bottom: 0.75rem; line-height: 1.6;">')
        html.append(f'<strong style="color: var(--text-main); font-weight: 700;">{c1.get("title")}</strong> ')
        html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c1.get("provider")}) — <i data-lucide="star" style="width: 14px; height: 14px; display: inline-block; fill: currentColor;"></i> {c1_stars:.1f} ({c1_reviews:,} ratings)</span>')
        html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c1.get("content_text")[:200]}...</span>')
        if c1_url != '#':
            html.append(f'<a class="path-link" href="{c1_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;"><i data-lucide="book-open" style="width: 14px; height: 14px; display: inline-block;"></i> View Syllabus & Lectures →</a>')
        html.append('</li>')
        
        # Course 2 (if present)
        if c2:
            c2_stars = float(c2.get('stars', 4.5))
            c2_reviews = int(c2.get('ratings_count', 1500))
            c2_url = c2.get('url', '#')
            c2_redirect = f"/verify_link?url={urllib.parse.quote(c2_url)}&title={urllib.parse.quote(c2.get('title'))}&provider={urllib.parse.quote(c2.get('provider'))}" if c2_url != '#' else '#'
            
            html.append(f'<li style="margin-bottom: 0.75rem; margin-top: 1rem; line-height: 1.6;">')
            html.append(f'<strong style="color: var(--text-main); font-weight: 700;">{c2.get("title")}</strong> ')
            html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c2.get("provider")}) — <i data-lucide="star" style="width: 14px; height: 14px; display: inline-block; fill: currentColor;"></i> {c2_stars:.1f} ({c2_reviews:,} ratings)</span>')
            html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c2.get("content_text")[:200]}...</span>')
            if c2_url != '#':
                html.append(f'<a class="path-link" href="{c2_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;"><i data-lucide="book-open" style="width: 14px; height: 14px; display: inline-block;"></i> View Syllabus & Lectures →</a>')
            html.append('</li>')
            
        html.append('</ul>')
        
        # Feature 5: Bespoke Recommended Practical Exercise with Interview Question!
        interview_q = "Explain the core technical principles you learned this week."
        if 'interview_ir_engine' in globals() and interview_ir_engine:
            try:
                ir_res = interview_ir_engine.search(c1.get("title", ""), top_k=1, method='hybrid')
                if ir_res:
                    interview_q = ir_res[0]['question']
            except Exception:
                pass

        html.append(f'<div style="background: rgba(50, 130, 184, 0.08); border-left: 3px solid var(--secondary); padding: 0.95rem 1.25rem; border-radius: 0 8px 8px 0; margin-top: 1.25rem;">')
        html.append(f'<strong style="color: var(--text-main); font-size: 0.9rem; display: block; margin-bottom: 0.35rem;"><i data-lucide="tool" style="width: 14px; height: 14px; display: inline-block;"></i> Weekly Practical Exercise & Mock Interview:</strong>')
        html.append(f'<span style="color: var(--text-muted); font-size: 0.875rem; line-height: 1.55; display: block; margin-bottom: 0.5rem;">Design and construct a modular software module incorporating the core competencies introduced this week. Focus on writing clean object-oriented logic, defining API schemas, and implementing comprehensive unit tests to validate boundaries on <strong>"{c1.get("title")}"</strong>.</span>')
        html.append(f'<span style="color: var(--secondary); font-size: 0.85rem; font-weight: 600; display: block;">💡 End-of-Week Interview Prep: "{interview_q}"</span>')
        html.append('</div>')
        
        html.append('</div>')
        
    return "".join(html)

@app.route('/generate_path', methods=['POST'])
def generate_path():
    if df is None:
        return jsonify({"success": False, "error": "Dataset is not loaded."}), 500

    data = request.get_json() or {}
    user_goal = data.get('goal', '').strip()
    if not user_goal:
        return jsonify({"success": False, "error": "Please enter a learning goal or career target."}), 400

    # 1. Use TF-IDF to retrieve top 12 relevant courses
    query_vector = vectorizer.transform([user_goal.lower()])
    search_df = df.copy()
    search_df['match_score'] = cosine_similarity(query_vector, tfidf_matrix).flatten()
    matched_courses = search_df.sort_values(by='match_score', ascending=False).head(12).to_dict('records')

    if not matched_courses:
        return jsonify({"success": False, "error": "No related courses found in our database to build a path."}), 404

    # Fallback instantly if Gemini API Key is missing
    if not GEMINI_API_KEY:
        print("Gemini API key not found. Seamlessly generating local academic study plan fallback.")
        path_html = generate_local_fallback_path(user_goal, matched_courses)
        return jsonify({
            "success": True,
            "goal": user_goal,
            "path_html": path_html,
            "fallback": True
        })

    # 2. Format the courses data to pass to the LLM (including stars & ratings)
    courses_context = []
    for c in matched_courses:
        courses_context.append({
            "title": c.get('title'),
            "provider": c.get('provider'),
            "description": c.get('content_text', '')[:200],
            "url": c.get('url', '#'),
            "stars": c.get('stars', 4.0),
            "ratings_count": int(c.get('ratings_count', 0))
        })

    # 3. Create the SYSTEM PROMPT and USER PROMPT
    system_prompt = (
        "You are an elite Computer Science Academic Advisor and curriculum planner.\n"
        "Your task is to organize a highly customized, logical, week-by-week learning syllabus "
        "tailored specifically to the student's career or learning goal.\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST ONLY recommend courses from the provided list of Available Courses.\n"
        "2. Do NOT recommend any external, made-up, or imaginary courses.\n"
        "3. You must construct a timeline (e.g., Week 1, Week 2, Week 3, etc.) explaining why "
        "each course was selected, what the student will learn, and a quick practical exercise recommendation.\n"
        "4. Structure your response in clean, premium HTML using only standard CSS classes. "
        "Use <h3> for weekly headings, <p> for descriptions, <div class='path-step'> for wrappers, "
        "and <a class='path-link' target='_blank'> for course links.\n"
        "5. CRITICAL: For every course listed, you MUST write its exact star rating and review count right next to its name "
        "in the bullet point list in parentheses. Example: 'Course Title (Udemy) - ⭐ 4.7 (15,230 ratings)'. "
        "Ensure you pull the exact 'stars' and 'ratings_count' values provided in the data.\n"
        "6. CRITICAL (Feature 5): In the practical exercise section for each week, include exactly ONE mock interview question from the provided list of 'Relevant Mock Interview Questions'. You MUST wrap both the practical exercise and the mock interview question together in a visually distinct, beautifully styled HTML block like this: `<div style=\"background: rgba(50, 130, 184, 0.08); border-left: 3px solid var(--secondary); padding: 0.95rem 1.25rem; border-radius: 0 8px 8px 0; margin-top: 1.25rem;\"><strong style=\"color: var(--text-main); font-size: 0.9rem; display: block; margin-bottom: 0.35rem;\"><i data-lucide=\"tool\" style=\"width: 14px; height: 14px; display: inline-block;\"></i> Weekly Practical Exercise & Mock Interview:</strong><span style=\"color: var(--text-muted); font-size: 0.875rem; line-height: 1.55; display: block; margin-bottom: 0.5rem;\">[Insert practical exercise here]</span><span style=\"color: var(--secondary); font-size: 0.85rem; font-weight: 600; display: block;\">💡 End-of-Week Interview Prep: \"[Insert Interview Question Here]\"</span></div>`\n"
        "7. Start directly with the syllabus layout. Do not include introductory conversational fluff or markdown code blocks like ```html."
    )

    interview_context = []
    if 'interview_ir_engine' in globals() and interview_ir_engine:
        try:
            ir_res = interview_ir_engine.search(user_goal, top_k=5, method='hybrid')
            interview_context = [r['question'] for r in ir_res]
        except Exception:
            pass

    user_prompt = f"""
    Student Goal: "{user_goal}"
    
    Available Courses in Database (with Ratings):
    {json.dumps(courses_context, indent=2)}
    
    Relevant Mock Interview Questions from Database:
    {json.dumps(interview_context, indent=2)}
    
    Please build a premium week-by-week curriculum using these courses and injecting one relevant mock interview question per week.
    """

    # ── Multi-Tier Study Plan Generator ──────────────────────────────
    # Tier 1: Groq Cloud API (Llama-3.1-70b-versatile) — Extremely fast, generous 30 RPM free limit!
    if GROQ_API_KEY:
        try:
            print("Querying Groq Cloud API for study plan...")
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2048
            }
            res = requests.post(groq_url, json=payload, headers=headers, timeout=12.0)
            if res.status_code == 200:
                res_data = res.json()
                path_html = res_data["choices"][0]["message"]["content"].strip()
                
                path_html = re.sub(r"^```html\n", "", path_html)
                path_html = re.sub(r"\n```$", "", path_html)
                
                print("Successfully generated study plan using Groq Cloud API!")
                return jsonify({
                    "success": True,
                    "goal": user_goal,
                    "path_html": path_html,
                    "engine": "groq"
                })
            else:
                print(f"Groq API returned error status {res.status_code}. Routing to Tier 2 (Gemini)...")
        except Exception as groq_err:
            print(f"Groq Cloud connection error: {groq_err}. Routing to Tier 2 (Gemini)...")

    # Tier 2: Gemini Cloud API (gemini-2.5-flash) — Standard Google cloud endpoint
    if GEMINI_API_KEY:
        try:
            print("Querying Gemini Cloud API for study plan...")
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )

            response = model.generate_content(user_prompt)
            path_html = response.text.strip()
            
            path_html = re.sub(r"^```html\n", "", path_html)
            path_html = re.sub(r"\n```$", "", path_html)

            print("Successfully generated study plan using Gemini Cloud API!")
            return jsonify({
                "success": True,
                "goal": user_goal,
                "path_html": path_html,
                "engine": "gemini"
            })
        except Exception as gemini_err:
            print(f"Gemini API returned error: {gemini_err}. Routing to Tier 3 (Local VSM Academic Planner)...")

    # Tier 3: Local VSM Academic Planner — Robust, instant, offline-capable fallback
    try:
        print("Routing to local high-fidelity VSM Academic Planner fallback...")
        path_html = generate_local_fallback_path(user_goal, matched_courses)
        return jsonify({
            "success": True,
            "goal": user_goal,
            "path_html": path_html,
            "fallback": True,
            "engine": "local"
        })
    except Exception as fallback_err:
        print(f"Fallback generation error: {fallback_err}")
        return jsonify({"success": False, "error": f"Failed to generate study plan: {str(fallback_err)}"}), 500

# --- User Authentication and Profile Management ---
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        db = get_db()
        user = db.users.find_one({"_id": session['user_id']})
        if not user or (user.get('role') != 'admin' and not check_is_super_admin(user)):
            flash("Admin access required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    user = None
    is_super = False
    if 'user_id' in session:
        db = get_db()
        if db is not None:
            user = db.users.find_one({"_id": session['user_id']})
            if user:
                is_super = check_is_super_admin(user)
    return dict(current_user=user, is_super_admin=is_super)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        if db is None:
            flash("Database connection error.", "danger")
            return redirect(url_for('register'))
            
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        track = request.form.get('track', '').strip()
        career_goals = request.form.get('career_goals', '').strip()
        skill_level = request.form.get('skill_level', 'Beginner')
        
        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return redirect(url_for('register'))
            
        if db.users.find_one({"email": email}):
            flash("Email already registered.", "danger")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        user_id = str(hashlib.sha256(email.encode()).hexdigest())[:16]
        
        user_doc = {
            "_id": user_id,
            "name": name,
            "email": email,
            "password_hash": hashed_password,
            "track": track,
            "career_goals": career_goals,
            "current_skill_level": skill_level,
            "role": "user",
            "taken_courses": [],
            "onboarding_preferences": {}
        }
        
        db.users.insert_one(user_doc)
        session['user_id'] = user_id
        flash("Registration successful! Please complete your onboarding.", "success")
        return redirect(url_for('onboarding'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        if db is None:
            flash("Database connection error.", "danger")
            return redirect(url_for('login'))
            
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user = db.users.find_one({"email": email})
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['_id']
            flash(f"Welcome back, {user['name']}!", "success")
            next_url = request.args.get('next')
            return redirect(next_url or url_for('index'))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

@app.route('/login/google')
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash("Google OAuth credentials are not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", "warning")
        return redirect(url_for('login'))
    # Generate redirect URI
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    redirect_uri = f"{scheme}://{request.host}/login/google/callback"
    
    # Store dynamic redirect URI in session because we need it for token exchange
    session['google_oauth_redirect_uri'] = redirect_uri
    
    state = str(uuid.uuid4())
    session['google_oauth_state'] = state
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account"
    }
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return redirect(auth_url)

@app.route('/login/google/callback')
def google_callback():
    db = get_db()
    if db is None:
        flash("Database connection error.", "danger")
        return redirect(url_for('login'))
        
    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f"Google login error: {error}", "danger")
        return redirect(url_for('login'))
        
    if not state or state != session.pop('google_oauth_state', None):
        flash("Invalid state parameter. Possible CSRF attempt.", "danger")
        return redirect(url_for('login'))
        
    if not code:
        flash("Authorization code missing.", "danger")
        return redirect(url_for('login'))
        
    # Get the redirect URI we stored during initialization
    redirect_uri = session.pop('google_oauth_redirect_uri', None)
    if not redirect_uri:
        # Fallback dynamic calculation
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        redirect_uri = f"{scheme}://{request.host}/login/google/callback"
        
    # Exchange code for tokens
    try:
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        res = requests.post(token_url, data=payload, timeout=10.0)
        if res.status_code != 200:
            flash(f"Failed to retrieve access token from Google: {res.text}", "danger")
            return redirect(url_for('login'))
            
        token_data = res.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            flash("Google response did not include access token.", "danger")
            return redirect(url_for('login'))
            
        # Get user profile information
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_res = requests.get(userinfo_url, headers=headers, timeout=10.0)
        if userinfo_res.status_code != 200:
            flash("Failed to retrieve user profile from Google.", "danger")
            return redirect(url_for('login'))
            
        user_info = userinfo_res.json()
        email = user_info.get("email")
        name = user_info.get("name", "Google User")
        
        if not email:
            flash("Failed to retrieve user email from Google.", "danger")
            return redirect(url_for('login'))
            
        # Check if user exists in database
        user = db.users.find_one({"email": email})
        if user:
            session['user_id'] = user['_id']
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('index'))
        else:
            # Create a new user with Google login
            user_id = str(hashlib.sha256(email.encode()).hexdigest())[:16]
            
            # Since they registered through Google, they don't have a password hash
            user_doc = {
                "_id": user_id,
                "name": name,
                "email": email,
                "password_hash": "", # login is authenticated via Google
                "track": "General CS",
                "career_goals": "",
                "current_skill_level": "Beginner",
                "role": "user",
                "taken_courses": [],
                "onboarding_preferences": {}
            }
            
            db.users.insert_one(user_doc)
            session['user_id'] = user_id
            flash("Registration successful via Google! Please complete your onboarding.", "success")
            return redirect(url_for('onboarding'))
            
    except Exception as e:
        print(f"Google OAuth Exception: {e}")
        flash(f"An error occurred during Google OAuth: {e}", "danger")
        return redirect(url_for('login'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for('forgot_password'))
            
        db = get_db()
        if db is None:
            flash("Database connection error.", "danger")
            return redirect(url_for('forgot_password'))
            
        user = db.users.find_one({"email": email})
        if not user:
            flash("If that email address is registered, a password reset link has been sent.", "info")
            return redirect(url_for('login'))
            
        # Generate token and expiry
        token = str(uuid.uuid4())
        expiry = datetime.utcnow() + timedelta(hours=1)
        
        # Save to database
        db.users.update_one(
            {"email": email},
            {"$set": {"reset_token": token, "reset_token_expiry": expiry}}
        )
        
        # Generate the reset link dynamically supporting Vercel and local hosting
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        reset_link = f"{scheme}://{request.host}{url_for('reset_password', token=token)}"
        
        # Send Email / Fallback to console
        email_sent = False
        smtp_email = os.environ.get("SMTP_EMAIL", "")
        smtp_password = os.environ.get("SMTP_PASSWORD", "")
        
        if smtp_email and smtp_password:
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
                smtp_port = int(os.environ.get("SMTP_PORT", "587"))
                
                msg = MIMEMultipart()
                msg['From'] = smtp_email
                msg['To'] = email
                msg['Subject'] = "Password Reset Request - MASARI"
                
                body = f"""Hello {user.get('name', 'User')},

We received a request to reset the password for your account on MASARI.

Click the link below to set a new password:
{reset_link}

This link is valid for 1 hour. If you did not request this, please ignore this email.

Best regards,
MASARI Team"""
                
                msg.attach(MIMEText(body, 'plain'))
                
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, email, msg.as_string())
                server.quit()
                email_sent = True
            except Exception as e:
                print(f"SMTP Error: {e}")
                
        is_production = os.environ.get("VERCEL") == "1"
        
        if not email_sent:
            print("\n" + "="*80)
            print(f"[DEVELOPER MODE] Password Reset Request for: {email}")
            print(f"Reset Link: {reset_link}")
            print("="*80 + "\n")
            if is_production:
                flash("If that email address is registered, a password reset link has been sent.", "success")
            else:
                flash("If that email address is registered, a password reset link has been sent. [Developer Mode: Check the server console log for the link!]", "success")
        else:
            flash("If that email address is registered, a password reset link has been sent.", "success")
            
        return redirect(url_for('login'))
        
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()
    if db is None:
        flash("Database connection error.", "danger")
        return redirect(url_for('login'))
        
    # Find user with active token
    user = db.users.find_one({
        "reset_token": token,
        "reset_token_expiry": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        flash("The password reset token is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for('forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password:
            flash("Please enter a new password.", "danger")
            return render_template('reset_password.html', token=token)
            
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('reset_password.html', token=token)
            
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('reset_password.html', token=token)
            
        # Hash new password and clear token fields
        hashed_password = generate_password_hash(password)
        db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {"password_hash": hashed_password},
                "$unset": {"reset_token": "", "reset_token_expiry": ""}
            }
        )
        
        flash("Your password has been successfully updated! Please log in with your new password.", "success")
        return redirect(url_for('login'))
        
    return render_template('reset_password.html', token=token)

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    db = get_db()
    if request.method == 'POST':
        # Save preferences
        preferences = {}
        for key, value in request.form.items():
            if key.startswith('course_'):
                course_id = key.replace('course_', '')
                # value could be interest level or skill level depending on form structure
                preferences[course_id] = value
                
        # Simplify: just save the raw form data to onboarding_preferences
        db.users.update_one(
            {"_id": session['user_id']},
            {"$set": {"onboarding_preferences": dict(request.form)}}
        )
        flash("Onboarding complete! Your recommendations are now personalized.", "success")
        return redirect(url_for('index'))
        
    # GET: fetch 5 courses based on user track
    global df
    if df is not None and not df.empty:
        user = db.users.find_one({"_id": session['user_id']}) if db is not None else {}
        user_track = user.get('track', '').lower() if user else ''
        
        relevant_df = pd.DataFrame()
        if user_track:
            # Filter courses containing the track keywords in their profile or title
            relevant_df = df[df['search_profile'].str.contains(user_track, case=False, na=False) | df['title'].str.contains(user_track, case=False, na=False)]
            
        if len(relevant_df) >= 5:
            random_courses = relevant_df.sample(n=5).to_dict('records')
        elif len(relevant_df) > 0:
            # Pad with random courses if we have less than 5 relevant ones
            relevant = relevant_df.to_dict('records')
            remaining = 5 - len(relevant)
            other_df = df[~df.index.isin(relevant_df.index)]
            others = other_df.sample(n=min(remaining, len(other_df))).to_dict('records') if not other_df.empty else []
            random_courses = relevant + others
        else:
            # Fallback to pure random if no matches or track empty
            random_courses = df.sample(n=5).to_dict('records')
            
        # generate a simple ID for them if they don't have one
        for i, c in enumerate(random_courses):
            c['temp_id'] = f"course_{i}"
    else:
        random_courses = []
        
    return render_template('onboarding.html', courses=random_courses)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = get_db()
    user = db.users.find_one({"_id": session['user_id']})
    
    if request.method == 'POST':
        updates = {
            "name": request.form.get('name', user.get('name')),
            "track": request.form.get('track', user.get('track')),
            "career_goals": request.form.get('career_goals', user.get('career_goals')),
            "current_skill_level": request.form.get('current_skill_level', user.get('current_skill_level'))
        }
        db.users.update_one({"_id": session['user_id']}, {"$set": updates})
        flash("Profile updated successfully.", "success")
        return redirect(url_for('profile'))
        
    # Get user's taken courses details from df
    taken_courses_info = []
    global df
    if df is not None and not df.empty and user.get('taken_courses'):
        taken_urls = user.get('taken_courses', [])
        # We store url as the unique identifier for now
        taken_df = df[df['url'].isin(taken_urls)]
        taken_courses_info = taken_df.to_dict('records')
        
    return render_template('profile.html', user=user, taken_courses=taken_courses_info)

@app.route('/submit_course', methods=['POST'])
def submit_course():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    title = request.form.get('title')
    provider = request.form.get('provider')
    url = request.form.get('url')
    description = request.form.get('description')
    rating = request.form.get('rating')
    
    if not title or not provider or not url:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
        
    db = get_db()
    
    # Store in a separate collection for unverified courses
    submitted_course = {
        "title": title,
        "provider": provider,
        "url": url,
        "content_text": description,
        "stars": float(rating) if rating else 5.0,
        "ratings_count": 1,
        "status": "pending",
        "submitted_by": session['user_id'],
        "submitted_at": time.time()
    }
    
    db.submitted_courses.insert_one(submitted_course)
    return jsonify({"success": True, "message": "Course submitted successfully and is pending admin approval!"})

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    db = get_db()
    if db is None:
        flash("Database connection error.", "danger")
        return redirect(url_for('profile'))
        
    password = request.form.get('password', '')
    user_id = session.get('user_id')
    
    user = db.users.find_one({"_id": user_id})
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('logout'))
        
    if user.get('password_hash'):
        if not check_password_hash(user['password_hash'], password):
            flash("Incorrect password, please try again.", "danger")
            return redirect(url_for('profile'))
        
    db.users.delete_one({"_id": user_id})
    session.clear()
    flash("Sorry to see you leave! Your account has been permanently deleted.", "success")
    return redirect(url_for('index'))
@app.route('/api/toggle_taken', methods=['POST'])
@login_required
def toggle_taken():
    data = request.get_json() or {}
    course_url = data.get('url')
    
    if not course_url:
        return jsonify({"success": False, "error": "No course URL provided"}), 400
        
    db = get_db()
    user = db.users.find_one({"_id": session['user_id']})
    taken = user.get('taken_courses', [])
    
    if course_url in taken:
        taken.remove(course_url)
        action = "removed"
    else:
        taken.append(course_url)
        action = "added"
        
    db.users.update_one({"_id": session['user_id']}, {"$set": {"taken_courses": taken}})
    return jsonify({"success": True, "action": action, "taken_courses": taken})

# --- LOCAL QUIZ BANK FOR OFFLINE FALLBACK ---
LOCAL_QUIZ_BANK = {
    "artificial intelligence": {
        "beginner": [
            {
                "id": 1,
                "question": "What is the primary goal of Machine Learning?",
                "options": [
                    "To create static webpages",
                    "To enable computers to learn from data without explicit programming",
                    "To design high-speed processors",
                    "To manage relational databases"
                ],
                "correct_index": 1,
                "explanation": "Machine learning focuses on algorithms that allow systems to learn patterns from data and make decisions."
            },
            {
                "id": 2,
                "question": "Which of the following is a type of Supervised Learning?",
                "options": [
                    "Clustering",
                    "Dimensionality Reduction",
                    "Classification",
                    "Anomaly Detection"
                ],
                "correct_index": 2,
                "explanation": "Classification (like email spam detection) is supervised learning because the training data is labeled."
            },
            {
                "id": 3,
                "question": "What does 'Neural Network' in AI draw inspiration from?",
                "options": [
                    "Computer network routers",
                    "The human brain's network of neurons",
                    "Social media friend networks",
                    "Electrical power grids"
                ],
                "correct_index": 1,
                "explanation": "Artificial Neural Networks are loosely inspired by the structure and biological processing of human brain neurons."
            },
            {
                "id": 4,
                "question": "What is the role of training data in AI?",
                "options": [
                    "To store the final output of the program",
                    "To display charts to users",
                    "To teach the AI model and adjust its parameters",
                    "To compile the source code"
                ],
                "correct_index": 2,
                "explanation": "Training data is used by machine learning algorithms to learn weights, patterns, and representations."
            },
            {
                "id": 5,
                "question": "Which of these is a common programming language used in AI development?",
                "options": [
                    "HTML",
                    "SQL",
                    "Python",
                    "Assembly"
                ],
                "correct_index": 2,
                "explanation": "Python is the most popular language for AI due to its rich library ecosystem (TensorFlow, PyTorch, Scikit-learn)."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is the purpose of the 'Activation Function' in a Neural Network?",
                "options": [
                    "To compile the neural network code",
                    "To introduce non-linearity into the network",
                    "To clean training datasets",
                    "To speed up database search queries"
                ],
                "correct_index": 1,
                "explanation": "Without activation functions (like ReLU or Sigmoid), a neural network would just be a linear regression model, unable to learn complex patterns."
            },
            {
                "id": 2,
                "question": "What is the difference between Supervised and Unsupervised Learning?",
                "options": [
                    "Supervised uses labeled data, whereas unsupervised uses unlabeled data",
                    "Supervised is faster, unsupervised is slower",
                    "Unsupervised is only for neural networks",
                    "Supervised does not use algorithms"
                ],
                "correct_index": 0,
                "explanation": "Supervised learning relies on pairs of input-labeled outputs, while unsupervised learning uncovers hidden structures in unlabeled datasets."
            },
            {
                "id": 3,
                "question": "What is overfitting in machine learning?",
                "options": [
                    "When a model performs well on training data but poorly on unseen test data",
                    "When a model is too small to fit the memory",
                    "When training takes too long to execute",
                    "When the data has too many columns"
                ],
                "correct_index": 0,
                "explanation": "Overfitting happens when a model learns the training data's noise and details too well, failing to generalize to new, unseen data."
            },
            {
                "id": 4,
                "question": "What does a Decision Tree split data based on?",
                "options": [
                    "Random coin flips",
                    "Feature values that maximize information gain or minimize impurity",
                    "The chronological order of data points",
                    "ASCII character values"
                ],
                "correct_index": 1,
                "explanation": "Decision trees split nodes based on features that maximize metrics like Information Gain (using Entropy) or Gini Impurity."
            },
            {
                "id": 5,
                "question": "What is 'Gradient Descent'?",
                "options": [
                    "An optimization algorithm used to minimize a loss function",
                    "A sorting algorithm for large arrays",
                    "A data visualization charting technique",
                    "A method for secure network routing"
                ],
                "correct_index": 0,
                "explanation": "Gradient Descent is an optimization algorithm that iteratively adjusts parameters to find the minimum of a cost/loss function."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "In Transformer architectures, what is the primary purpose of the 'Self-Attention' mechanism?",
                "options": [
                    "To compress the input tokens into a single vector representation",
                    "To relate different positions of a single sequence to compute a representation of the sequence",
                    "To speed up CPU multi-threading during training",
                    "To eliminate the need for backpropagation"
                ],
                "correct_index": 1,
                "explanation": "Self-attention allows the model to look at other words in the input sequence to better understand each word in context."
            },
            {
                "id": 2,
                "question": "What problem does 'Backpropagation Through Time' (BPTT) face in deep RNNs?",
                "options": [
                    "Deadlock conditions",
                    "Vanishing and exploding gradients",
                    "Memory fragmentation",
                    "Infinite recursion compiler crashes"
                ],
                "correct_index": 1,
                "explanation": "Due to the long sequence lengths, gradients multiplied repeatedly over time steps tend to either exponentially vanish or explode."
            },
            {
                "id": 3,
                "question": "What is the key idea behind Generative Adversarial Networks (GANs)?",
                "options": [
                    "Two databases merging with conflict resolution",
                    "A generator and a discriminator network competing in a minimax game",
                    "Parallel execution of multiple regression models",
                    "Strict rule-based expert systems"
                ],
                "correct_index": 1,
                "explanation": "GANs consist of a generator creating fake data and a discriminator trying to detect fakes, training each other through competition."
            },
            {
                "id": 4,
                "question": "Which regularization technique randomly drops connections between neural units during training?",
                "options": [
                    "L2 Weight Decay",
                    "Batch Normalization",
                    "Dropout",
                    "Early Stopping"
                ],
                "correct_index": 2,
                "explanation": "Dropout randomly sets a fraction of input units to 0 at each update during training, which prevents co-adaptation of feature detectors."
            },
            {
                "id": 5,
                "question": "What does the 'Q' represent in Q-Learning (Reinforcement Learning)?",
                "options": [
                    "Queue size",
                    "Quality (expected utility of a state-action pair)",
                    "Query latency",
                    "Quantum state"
                ],
                "correct_index": 1,
                "explanation": "Q stands for Quality, representing the expected long-term reward of taking a specific action in a given state."
            }
        ]
    },
    "web development": {
        "beginner": [
            {
                "id": 1,
                "question": "What is the primary language used to define the style and layout of a webpage?",
                "options": ["HTML", "XML", "CSS", "SQL"],
                "correct_index": 2,
                "explanation": "CSS (Cascading Style Sheets) is designed to separate the presentation of a document from its structure (defined in HTML)."
            },
            {
                "id": 2,
                "question": "Which HTML tag is used to create a hyperlink?",
                "options": ["<link>", "<a>", "<href>", "<nav>"],
                "correct_index": 1,
                "explanation": "The <a> (anchor) tag is used to define hyperlinks linking one page to another."
            },
            {
                "id": 3,
                "question": "What does DOM stand for in Web Development?",
                "options": [
                    "Document Object Model",
                    "Data Object Management",
                    "Domain Outline Mapping",
                    "Digital Ordinance Matrix"
                ],
                "correct_index": 0,
                "explanation": "DOM stands for Document Object Model, which represents the page structure so that programs can change the document structure, style, and content."
            },
            {
                "id": 4,
                "question": "Which CSS property is used to change the text color of an element?",
                "options": ["font-color", "text-color", "color", "background-color"],
                "correct_index": 2,
                "explanation": "The 'color' property in CSS specifies the text color of an element."
            },
            {
                "id": 5,
                "question": "What is the primary purpose of JavaScript in a standard webpage?",
                "options": [
                    "To store user credentials on the database",
                    "To compile HTML templates",
                    "To add interactivity, behavior, and dynamic content to a webpage",
                    "To design graphics and logos"
                ],
                "correct_index": 2,
                "explanation": "JavaScript is a client-side scripting language that enables interactive elements, animations, and dynamic updates."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is a major difference between HTTP GET and POST methods?",
                "options": [
                    "GET requests can send parameters in the request body, while POST cannot",
                    "GET is used to retrieve data, whereas POST is used to submit data to be processed",
                    "GET is secure by default, while POST is not",
                    "POST is only compatible with XML data formats"
                ],
                "correct_index": 1,
                "explanation": "GET requests are designed to retrieve data and append parameters to the URL. POST requests submit data, typically in the request body, to create/update resources."
            },
            {
                "id": 2,
                "question": "What is the purpose of 'localStorage' in browser storage APIs?",
                "options": [
                    "To cache images on a proxy server",
                    "To store key-value data locally with no expiration date",
                    "To store temporary session variables that expire when the tab closes",
                    "To sync database transactions in real-time"
                ],
                "correct_index": 1,
                "explanation": "localStorage stores data with no expiration time, whereas sessionStorage clears data when the page session ends (tab closes)."
            },
            {
                "id": 3,
                "question": "In JavaScript, what is a closure?",
                "options": [
                    "A method of ending an infinite loop",
                    "A function that has access to its outer lexical scope even after the outer function has executed",
                    "A method for closing database connections",
                    "An event handler that stops event propagation"
                ],
                "correct_index": 1,
                "explanation": "A closure is the combination of a function bundled together with references to its surrounding state (lexical environment)."
            },
            {
                "id": 4,
                "question": "What is the virtual DOM in modern frameworks like React?",
                "options": [
                    "An exact replica of the browser's window object",
                    "A lightweight, virtual representation of the real DOM in memory used to calculate efficient updates",
                    "A server-side cache for HTML pages",
                    "A browser extension that debugs web applications"
                ],
                "correct_index": 1,
                "explanation": "React uses a virtual DOM to determine the minimum number of changes needed (reconciliation) before updating the actual browser DOM, improving performance."
            },
            {
                "id": 5,
                "question": "What does CORS stand for?",
                "options": [
                    "Cross-Origin Resource Sharing",
                    "Client-Oriented Routing System",
                    "Core Object Request Service",
                    "Compiled Object Responsive Styles"
                ],
                "correct_index": 0,
                "explanation": "CORS (Cross-Origin Resource Sharing) is a browser security mechanism that uses headers to allow or restrict resources requested from other domains."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What is the core difference between Server-Side Rendering (SSR) and Client-Side Rendering (CSR)?",
                "options": [
                    "SSR only runs on SQL databases, while CSR runs on MongoDB",
                    "SSR pre-renders HTML on the server for each request, while CSR renders the UI dynamically in the browser using JavaScript",
                    "SSR is always slower to load the first paint than CSR",
                    "CSR is executed on a Content Delivery Network (CDN) only"
                ],
                "correct_index": 1,
                "explanation": "SSR parses page content on the server and delivers fully populated HTML to the browser, while CSR delivers an empty container and renders page content via client-side JavaScript."
            },
            {
                "id": 2,
                "question": "What is the goal of optimizing the 'Critical Rendering Path' in a web application?",
                "options": [
                    "To secure database queries from SQL injection",
                    "To minimize the time the browser takes to process and paint HTML, CSS, and JS onto the screen",
                    "To design better routing algorithms",
                    "To compile TypeScript files into JavaScript faster"
                ],
                "correct_index": 1,
                "explanation": "Critical Rendering Path optimization reduces render-blocking resources so the browser can display the page to the user as fast as possible."
            },
            {
                "id": 3,
                "question": "How does HTTP/2 improve loading performance compared to HTTP/1.1?",
                "options": [
                    "It replaces TCP with UDP completely",
                    "It introduces multiplexing, allowing multiple request/response cycles over a single TCP connection",
                    "It disallows cookie headers to compress size",
                    "It encrypts all data automatically without needing SSL certificates"
                ],
                "correct_index": 1,
                "explanation": "HTTP/2 introduces multiplexing, header compression, and server push, allowing browsers to request multiple files simultaneously over one connection."
            },
            {
                "id": 4,
                "question": "What is the WebSockets protocol used for?",
                "options": [
                    "Encrypting email notifications",
                    "Enabling full-duplex, persistent communication channels between client and server",
                    "Mapping domain names to server IP addresses",
                    "Downloading binary zip files faster"
                ],
                "correct_index": 1,
                "explanation": "WebSockets establish a continuous, bidirectional connection suitable for real-time web applications like chat or collaborative tools."
            },
            {
                "id": 5,
                "question": "What is Cross-Site Scripting (XSS)?",
                "options": [
                    "An attack where a user is forced to execute actions they didn't intend to",
                    "A vulnerability allowing malicious scripts to be injected into trusted websites and executed in the client's browser",
                    "An exploit targeting database servers by bypassing firewalls",
                    "A method for intercepting network packets in transit"
                ],
                "correct_index": 1,
                "explanation": "XSS allows attackers to inject client-side scripts (usually JavaScript) into web pages viewed by other users, potentially stealing cookies, tokens, or sensitive information."
            }
        ]
    },
    "data science": {
        "beginner": [
            {
                "id": 1,
                "question": "Which Python library is the standard for data manipulation and analysis?",
                "options": ["Django", "NumPy", "Pandas", "Flask"],
                "correct_index": 2,
                "explanation": "Pandas is the leading Python package for structured data manipulation, providing the powerful DataFrame object."
            },
            {
                "id": 2,
                "question": "What is a DataFrame in Pandas?",
                "options": [
                    "A single-dimensional array of numbers",
                    "A 2D, size-mutable, tabular data structure with labeled axes (rows and columns)",
                    "A connection object to a PostgreSQL database",
                    "A layout model for CSS formatting"
                ],
                "correct_index": 1,
                "explanation": "A DataFrame is a two-dimensional, tabular data structure resembling a spreadsheet or SQL table."
            },
            {
                "id": 3,
                "question": "In statistics, what is the 'Mean' of a dataset?",
                "options": [
                    "The middle value when the data is sorted",
                    "The average calculated by summing all values and dividing by the total count",
                    "The most frequently occurring value",
                    "The difference between the highest and lowest values"
                ],
                "correct_index": 1,
                "explanation": "The mean is the arithmetic average of a set of numbers."
            },
            {
                "id": 4,
                "question": "What type of chart is best suited to visualize the relationship between two continuous variables?",
                "options": ["Pie Chart", "Bar Chart", "Scatter Plot", "Histogram"],
                "correct_index": 2,
                "explanation": "A scatter plot plots individual points along X and Y axes, making it ideal for displaying the correlation or distribution of two numerical features."
            },
            {
                "id": 5,
                "question": "What is the primary objective of data cleaning?",
                "options": [
                    "To write code comments",
                    "To identify missing values, handle duplicates, fix formatting, and prepare the dataset for analysis",
                    "To make the files run faster on servers",
                    "To upload the files to GitHub"
                ],
                "correct_index": 1,
                "explanation": "Data cleaning fixes corrupt, incomplete, or incorrectly formatted records before feeding the data into a model."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What does the term 'Imputation' mean in data preprocessing?",
                "options": [
                    "Deleting columns with missing values",
                    "Replacing missing values with estimated values (like mean, median, or predictions)",
                    "Scaling features between 0 and 1",
                    "Encrypting data tables"
                ],
                "correct_index": 1,
                "explanation": "Imputation is the process of replacing missing data with substituted values so that algorithms can process the dataset without errors."
            },
            {
                "id": 2,
                "question": "What is a key difference between L1 (Lasso) and L2 (Ridge) regularization?",
                "options": [
                    "L1 regularization is only for decision trees",
                    "L1 regularization can shrink coefficients to exactly zero, performing feature selection; L2 shrinks them close to zero but not exactly zero",
                    "L2 is faster to execute than L1",
                    "L1 cannot handle continuous target variables"
                ],
                "correct_index": 1,
                "explanation": "Lasso (L1) adds an absolute penalty which can lead to sparse coefficients (feature selection). Ridge (L2) adds a squared penalty, shrinking weights but retaining all variables."
            },
            {
                "id": 3,
                "question": "What is a Confusion Matrix used for?",
                "options": [
                    "To solve encryption algorithm conflicts",
                    "To evaluate the classification performance of a model showing true/false positives and negatives",
                    "To identify memory leaks in Python scripts",
                    "To merge database tables automatically"
                ],
                "correct_index": 1,
                "explanation": "A confusion matrix shows correct and incorrect predictions broken down by class, helping calculate Precision, Recall, and F1-Score."
            },
            {
                "id": 4,
                "question": "What is the main goal of Principal Component Analysis (PCA)?",
                "options": [
                    "To train neural networks faster",
                    "To reduce the dimensionality of a dataset while preserving as much variance as possible",
                    "To split data into train and test sets",
                    "To encrypt column headers for security"
                ],
                "correct_index": 1,
                "explanation": "PCA is an unsupervised technique that projects high-dimensional data onto orthogonal directions of maximum variance."
            },
            {
                "id": 5,
                "question": "In statistical testing, what is the p-value?",
                "options": [
                    "The probability of the model being 100% correct",
                    "The probability of obtaining the observed results (or more extreme) assuming the null hypothesis is true",
                    "The parameter representing the number of folds in cross validation",
                    "The error rate of a classification model"
                ],
                "correct_index": 1,
                "explanation": "A small p-value (typically <= 0.05) indicates strong evidence against the null hypothesis, allowing you to reject it."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What does the 'Curse of Dimensionality' refer to?",
                "options": [
                    "Slow database loading speeds in big data platforms",
                    "As dimensionality increases, the volume of space grows exponentially, making data points sparse and distance metrics less meaningful",
                    "An error code that happens in neural network layers",
                    "Having too many rows of data in a CSV file"
                ],
                "correct_index": 1,
                "explanation": "In high-dimensional spaces, points become very far apart, and concepts like distance (Euclidean) become ineffective for clustering or classification."
            },
            {
                "id": 2,
                "question": "What is the difference between Bagging and Boosting ensemble methods?",
                "options": [
                    "Bagging models are built sequentially, while Boosting models are built in parallel",
                    "Bagging models are trained in parallel independently, while Boosting models are trained sequentially where each model corrects the errors of its predecessor",
                    "Bagging is only for linear models, while Boosting is for neural networks",
                    "There is no difference; they are synonymous"
                ],
                "correct_index": 1,
                "explanation": "Bagging (like Random Forest) reduces variance by averaging independent models. Boosting (like XGBoost) reduces bias by training sequentially, targeting misclassified instances."
            },
            {
                "id": 3,
                "question": "What is a Random Forest model?",
                "options": [
                    "A single very deep decision tree",
                    "An ensemble of decision trees trained on bootstrapped datasets and random feature subsets",
                    "A neural network architecture that resembles branches",
                    "A sorting algorithm for hierarchical data structures"
                ],
                "correct_index": 1,
                "explanation": "Random Forest is an ensemble classifier consisting of many decision trees, voting on the output class to improve prediction accuracy."
            },
            {
                "id": 4,
                "question": "What is the purpose of K-Fold Cross Validation?",
                "options": [
                    "To multiply the data size K times",
                    "To evaluate model generalizability by partitioning data into K subsets, training K times, and averaging performance",
                    "To run model optimization on K GPU cores",
                    "To cluster the data into K distinct categories"
                ],
                "correct_index": 1,
                "explanation": "K-Fold Cross Validation ensures that every data point is used for both training and testing, reducing evaluation bias."
            },
            {
                "id": 5,
                "question": "What is the F1-Score in binary classification?",
                "options": [
                    "The ratio of true positives to false positives",
                    "The harmonic mean of Precision and Recall, providing a balanced metric for imbalanced classes",
                    "The training speed coefficient of a model",
                    "The accuracy percentage of the model"
                ],
                "correct_index": 1,
                "explanation": "F1-Score balances Precision and Recall, which is crucial when evaluating datasets with highly imbalanced class distributions."
            }
        ]
    },
    "general cs": {
        "beginner": [
            {
                "id": 1,
                "question": "What is an algorithm?",
                "options": [
                    "A programming language compiler",
                    "A step-by-step procedure or set of rules to solve a problem or perform a task",
                    "A database management system",
                    "A graphical user interface design"
                ],
                "correct_index": 1,
                "explanation": "An algorithm is a finite, well-defined sequence of instructions to solve a particular problem."
            },
            {
                "id": 2,
                "question": "Which data structure operates on a Last-In, First-Out (LIFO) basis?",
                "options": ["Queue", "Stack", "Linked List", "Binary Tree"],
                "correct_index": 1,
                "explanation": "A stack is LIFO (elements added last are removed first), whereas a queue is FIFO (First-In, First-Out)."
            },
            {
                "id": 3,
                "question": "What is the time complexity of searching in a sorted array using Binary Search?",
                "options": ["O(1)", "O(n)", "O(log n)", "O(n log n)"],
                "correct_index": 2,
                "explanation": "Binary search divides the search space in half at each step, yielding a logarithmic time complexity O(log n)."
            },
            {
                "id": 4,
                "question": "What does HTML stand for in web technologies?",
                "options": [
                    "HyperText Markup Language",
                    "HighText Machine Language",
                    "Hyperlink Technical Management List",
                    "Home Tool Markup Layout"
                ],
                "correct_index": 0,
                "explanation": "HTML stands for HyperText Markup Language, the standard formatting language for web browsers."
            },
            {
                "id": 5,
                "question": "What is the primary role of a compiler?",
                "options": [
                    "To execute program code line by line",
                    "To translate high-level source code into low-level machine code or bytecode",
                    "To backup code files to cloud storage",
                    "To manage relational databases"
                ],
                "correct_index": 1,
                "explanation": "A compiler translates the entire source code file into executable machine instructions before execution."
            }
        ],
        "intermediate": [
            {
                "id": 1,
                "question": "What is the average-case time complexity of the QuickSort algorithm?",
                "options": ["O(n)", "O(n^2)", "O(n log n)", "O(log n)"],
                "correct_index": 2,
                "explanation": "QuickSort averages O(n log n) time complexity, though its worst-case is O(n^2) when poor pivots are chosen."
            },
            {
                "id": 2,
                "question": "In object-oriented programming, what is polymorphism?",
                "options": [
                    "The ability to restrict access to class variables",
                    "The capability of different classes to respond to the same message/method in their own unique way",
                    "Creating multiple instances of a class",
                    "Inheriting all variables from a parent class without modification"
                ],
                "correct_index": 1,
                "explanation": "Polymorphism means 'many forms', enabling a single interface to represent different underlying forms (like overriding methods in subclasses)."
            },
            {
                "id": 3,
                "question": "Which data structure uses a hashing function to map keys to values?",
                "options": ["Binary Search Tree", "Hash Table", "Double Ended Queue", "Graph"],
                "correct_index": 1,
                "explanation": "A Hash Table uses a hash function to compute index positions for keys, allowing O(1) average lookup time."
            },
            {
                "id": 4,
                "question": "What is a primary difference between a process and a thread?",
                "options": [
                    "Processes run in parallel, while threads never run in parallel",
                    "Threads share the same memory space of their parent process, whereas processes run in separate memory spaces",
                    "Threads are managed by the database, while processes are managed by the compiler",
                    "Processes do not consume memory, while threads do"
                ],
                "correct_index": 1,
                "explanation": "A thread is a lightweight unit of execution within a process; threads share memory and resources of the process, making inter-thread communication faster but more complex."
            },
            {
                "id": 5,
                "question": "What is the main purpose of Database Normalization?",
                "options": [
                    "To speed up database connection times",
                    "To minimize data redundancy and prevent anomalies by structuring tables logically",
                    "To compress files for smaller storage footprint",
                    "To run analytical reports on large databases"
                ],
                "correct_index": 1,
                "explanation": "Database normalization structures tables to reduce duplicate data (redundancy) and ensure dependency constraints are maintained."
            }
        ],
        "advanced": [
            {
                "id": 1,
                "question": "What does it mean for a problem to be 'NP-complete'?",
                "options": [
                    "It cannot be solved on any standard computer",
                    "It belongs to the class of problems for which no polynomial-time algorithm is known, but any proposed solution can be verified in polynomial time",
                    "It has a constant time complexity O(1)",
                    "It is solved exclusively using neural network models"
                ],
                "correct_index": 1,
                "explanation": "NP-complete problems represent the hardest problems in NP. If a polynomial-time algorithm is found for one, P would equal NP."
            },
            {
                "id": 2,
                "question": "What does the CAP Theorem state for distributed databases?",
                "options": [
                    "A database can never scale horizontally",
                    "A distributed system can guarantee at most two of: Consistency, Availability, and Partition Tolerance",
                    "Transactions must always satisfy ACID properties",
                    "Security, Speed, and Stability cannot coexist"
                ],
                "correct_index": 1,
                "explanation": "CAP states that in the event of a network partition (P), a distributed system must choose between Consistency (C) and Availability (A)."
            },
            {
                "id": 3,
                "question": "In operating systems, what is thrashing?",
                "options": [
                    "A hardware failure in the CPU cache controller",
                    "A condition where the OS spends more time swapping pages in and out of virtual memory than executing actual process instructions",
                    "Removing old log files to clear disk space",
                    "Multiple processes deadlock waiting for print spoolers"
                ],
                "correct_index": 1,
                "explanation": "Thrashing occurs when the OS active working sets exceed physical RAM, causing constant page faults and swapping."
            },
            {
                "id": 4,
                "question": "What is a mutex (mutual exclusion) object used for in multi-threading?",
                "options": [
                    "To speed up CPU clock cycles",
                    "To lock a shared resource so that only one thread can access it at any given time",
                    "To allocate dynamic heap memory",
                    "To compile thread-safe scripts"
                ],
                "correct_index": 1,
                "explanation": "A mutex prevents race conditions by ensuring multiple threads do not access or modify a shared resource simultaneously."
            },
            {
                "id": 5,
                "question": "What did Alan Turing prove with the Halting Problem?",
                "options": [
                    "That all programs will eventually stop executing",
                    "That it is undecidable whether an arbitrary program will halt or run forever on a given input",
                    "That computer speed is limited by thermodynamics",
                    "That compiler errors are unavoidable"
                ],
                "correct_index": 1,
                "explanation": "The Halting Problem is a classic example of an undecidable decision problem in computability theory, proving absolute mathematical limits of computers."
            }
        ]
    }
}

def get_local_fallback_questions(track, skill_level):
    track_key = track.lower() if track else 'general cs'
    level_key = skill_level.lower() if skill_level else 'beginner'
    
    # Normalizer
    if 'artificial' in track_key or 'ai' in track_key or 'machine' in track_key:
        track_key = 'artificial intelligence'
    elif 'web' in track_key or 'frontend' in track_key or 'backend' in track_key or 'full-stack' in track_key:
        track_key = 'web development'
    elif 'data' in track_key or 'science' in track_key or 'analytics' in track_key:
        track_key = 'data science'
    else:
        track_key = 'general cs'
        
    if level_key not in ['beginner', 'intermediate', 'advanced']:
        level_key = 'beginner'
        
    track_bank = LOCAL_QUIZ_BANK.get(track_key, LOCAL_QUIZ_BANK['general cs'])
    return track_bank.get(level_key, track_bank['beginner'])

@app.route('/api/save_path', methods=['POST'])
@login_required
def save_path():
    data = request.get_json() or {}
    goal = data.get('goal', '').strip()
    path_html = data.get('path_html', '').strip()
    
    if not goal or not path_html:
        return jsonify({"success": False, "error": "Goal and path HTML are required"}), 400
        
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    path_id = str(uuid.uuid4())
    new_path = {
        "id": path_id,
        "goal": goal,
        "path_html": path_html,
        "checked_items": [],
        "progress_percent": 0.0,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Push into user's saved_paths array
    db.users.update_one(
        {"_id": session['user_id']},
        {"$push": {"saved_paths": new_path}}
    )
    
    return jsonify({"success": True, "path_id": path_id})

@app.route('/api/update_path_progress', methods=['POST'])
@login_required
def update_path_progress():
    data = request.get_json() or {}
    path_id = data.get('path_id')
    checked_items = data.get('checked_items', [])
    total_items = data.get('total_items', 0)
    
    if not path_id:
        return jsonify({"success": False, "error": "Path ID is required"}), 400
        
    progress_percent = 0.0
    if total_items > 0:
        progress_percent = round((len(checked_items) / total_items) * 100, 1)
        
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    # Update matching array element using positional operator $
    db.users.update_one(
        {"_id": session['user_id'], "saved_paths.id": path_id},
        {"$set": {
            "saved_paths.$.checked_items": checked_items,
            "saved_paths.$.progress_percent": progress_percent
        }}
    )
    
    return jsonify({"success": True, "progress_percent": progress_percent})

@app.route('/api/delete_path', methods=['POST'])
@login_required
def delete_path():
    data = request.get_json() or {}
    path_id = data.get('path_id')
    
    if not path_id:
        return jsonify({"success": False, "error": "Path ID is required"}), 400
        
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    db.users.update_one(
        {"_id": session['user_id']},
        {"$pull": {"saved_paths": {"id": path_id}}}
    )
    
    return jsonify({"success": True})

@app.route('/api/chat_assistant', methods=['POST'])
@login_required
def chat_assistant():
    data = request.get_json() or {}
    messages = data.get('messages', [])
    if not messages:
        return jsonify({"success": False, "error": "No messages provided"}), 400
        
    system_prompt = (
        "You are an elite Computer Science Academic Advisor and tutor.\n"
        "Answer the student's questions concisely, helpfully, and professionally.\n"
        "Explain complex CS concepts clearly, suggest appropriate learning habits, "
        "and mention matching courses or track guidelines when appropriate.\n"
        "Formatting tip: Use standard Markdown formatting like **bold** or `code` snippets where appropriate."
    )
    
    # Tier 1: Groq Cloud API
    if GROQ_API_KEY:
        try:
            print("Querying Groq Cloud API for chat assistant...")
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": 0.5,
                "max_tokens": 1024
            }
            res = requests.post(groq_url, json=payload, headers=headers, timeout=10.0)
            if res.status_code == 200:
                res_data = res.json()
                reply = res_data["choices"][0]["message"]["content"].strip()
                return jsonify({"success": True, "response": reply, "engine": "groq"})
            else:
                print(f"Groq API returned status {res.status_code}. Routing to Tier 2 (Gemini)...")
        except Exception as e:
            print(f"Groq Cloud connection error: {e}. Routing to Tier 2 (Gemini)...")
            
    # Tier 2: Gemini Cloud API
    if GEMINI_API_KEY:
        try:
            print("Querying Gemini Cloud API for chat assistant...")
            # format conversation transcript
            transcript = ""
            for m in messages:
                role = "Student" if m['role'] == 'user' else "Advisor"
                transcript += f"{role}: {m['content']}\n"
            user_prompt = f"Dialogue history:\n{transcript}\nAdvisor:"
            
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )
            response = model.generate_content(user_prompt)
            reply = response.text.strip()
            return jsonify({"success": True, "response": reply, "engine": "gemini"})
        except Exception as e:
            print(f"Gemini API returned error: {e}. Routing to Tier 3...")
            
    # Tier 3: Static Fallback
    fallback_response = (
        "Hello! I am currently running in offline mode. Here are a few general CS study tips:\n"
        "1. **Practice coding daily**: Sites like LeetCode or building small personal projects help cement syntax.\n"
        "2. **Optimize your learning path**: Complete your saved plans week-by-week.\n"
        "3. **Take assessments**: Try the Skill Assessment quiz under your profile page to rank up!"
    )
    return jsonify({"success": True, "response": fallback_response, "engine": "static"})

@app.route('/api/generate_quiz', methods=['GET'])
@login_required
def generate_quiz():
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    user = db.users.find_one({"_id": session['user_id']})
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
        
    track = user.get('track', 'General CS')
    skill_level = user.get('current_skill_level', 'Beginner')
    
    system_prompt = (
        "You are an expert computer science educator and examiner.\n"
        "Your task is to generate a high-quality 5-question multiple choice quiz matching the student's learning track and current skill level.\n"
        "Provide your output ONLY as a valid JSON object. Do not wrap in markdown tags like ```json or ```.\n"
        "The JSON object must have a single key 'questions' containing a list of 5 objects.\n"
        "Each question object MUST contain the following fields exactly:\n"
        "- 'id': unique integer (1 to 5)\n"
        "- 'question': the question text (clear, challenging, and educational)\n"
        "- 'options': an array of exactly 4 strings (options A, B, C, D)\n"
        "- 'correct_index': the index of the correct option in the options array (0 to 3)\n"
        "- 'explanation': a short explanation explaining why the correct answer is correct.\n"
        "\n"
        "Ensure all questions are directly related to the specified track and appropriate for the skill level."
    )
    
    user_prompt = f"Please generate a quiz for the track: '{track}' at the level: '{skill_level}'."
    
    # Tier 1: Groq Cloud API
    if GROQ_API_KEY:
        try:
            print("Querying Groq Cloud API for quiz generation...")
            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 1500,
                "response_format": {"type": "json_object"}
            }
            res = requests.post(groq_url, json=payload, headers=headers, timeout=12.0)
            if res.status_code == 200:
                res_data = res.json()
                reply = res_data["choices"][0]["message"]["content"].strip()
                reply = re.sub(r"^```(?:json)?\n", "", reply)
                reply = re.sub(r"\n```$", "", reply)
                quiz_data = json.loads(reply)
                if "questions" in quiz_data and len(quiz_data["questions"]) == 5:
                    return jsonify({
                        "success": True,
                        "track": track,
                        "skill_level": skill_level,
                        "questions": quiz_data["questions"],
                        "engine": "groq"
                    })
            else:
                print(f"Groq API returned error status {res.status_code}. Routing to Tier 2 (Gemini)...")
        except Exception as e:
            print(f"Groq Quiz Generation failed: {e}. Routing to Tier 2 (Gemini)...")
            
    # Tier 2: Gemini Cloud API
    if GEMINI_API_KEY:
        try:
            print("Querying Gemini Cloud API for quiz generation...")
            model = genai.GenerativeModel(
                model_name='gemini-2.5-flash',
                system_instruction=system_prompt
            )
            response = model.generate_content(user_prompt)
            reply = response.text.strip()
            reply = re.sub(r"^```(?:json)?\n", "", reply)
            reply = re.sub(r"\n```$", "", reply)
            quiz_data = json.loads(reply)
            if "questions" in quiz_data and len(quiz_data["questions"]) == 5:
                return jsonify({
                    "success": True,
                    "track": track,
                    "skill_level": skill_level,
                    "questions": quiz_data["questions"],
                    "engine": "gemini"
                })
        except Exception as e:
            print(f"Gemini Quiz Generation failed: {e}. Routing to Tier 3...")
            
    # Tier 3: Local Fallback
    print("Routing to local fallback quiz bank...")
    questions = get_local_fallback_questions(track, skill_level)
    return jsonify({
        "success": True,
        "track": track,
        "skill_level": skill_level,
        "questions": questions,
        "engine": "fallback"
    })

@app.route('/api/submit_quiz', methods=['POST'])
@login_required
def submit_quiz():
    data = request.get_json() or {}
    user_answers = data.get('quiz_answers', [])
    quiz_questions = data.get('quiz_questions', [])
    
    if len(user_answers) != 5 or len(quiz_questions) != 5:
        return jsonify({"success": False, "error": "Invalid quiz submission data"}), 400
        
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error"}), 500
        
    user = db.users.find_one({"_id": session['user_id']})
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 404
        
    # Grade the quiz
    correct_count = 0
    for idx, question in enumerate(quiz_questions):
        correct_idx = question.get('correct_index')
        user_idx = user_answers[idx]
        if user_idx == correct_idx:
            correct_count += 1
            
    score = int((correct_count / 5) * 100)
    passed = score >= 80
    
    promoted = False
    current_level = user.get('current_skill_level', 'Beginner')
    new_level = current_level
    
    if passed:
        # Check promotion
        if current_level == 'Beginner':
            new_level = 'Intermediate'
            promoted = True
        elif current_level == 'Intermediate':
            new_level = 'Advanced'
            promoted = True
        else:
            new_level = 'Advanced'
            promoted = False
            
        if promoted:
            db.users.update_one(
                {"_id": session['user_id']},
                {"$set": {"current_skill_level": new_level}}
            )
            
    return jsonify({
        "success": True,
        "score": score,
        "correct_count": correct_count,
        "passed": passed,
        "promoted": promoted,
        "new_level": new_level
    })

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    users = list(db.users.find({}))
    
    page = request.args.get('page', 1, type=int)
    per_page = 50
    total_courses = db.courses.count_documents({})
    total_pages = (total_courses + per_page - 1) // per_page
    
    # load courses from DB directly with pagination
    courses = list(db.courses.find({}, {'_id': 0}).skip((page - 1) * per_page).limit(per_page))
    
    # load pending courses
    pending_courses = list(db.submitted_courses.find({"status": "pending"}))
    
    return render_template('admin.html', users=users, courses=courses, page=page, total_pages=total_pages, pending_courses=pending_courses)

@app.route('/api/admin/approve_course', methods=['POST'])
@admin_required
def approve_course():
    data = request.get_json() or {}
    course_id = data.get('course_id')
    
    if not course_id:
        return jsonify({"success": False, "error": "No course ID provided"}), 400
        
    db = get_db()
    pending = db.submitted_courses.find_one({"_id": ObjectId(course_id)})
    
    if not pending:
        return jsonify({"success": False, "error": "Pending course not found"}), 404
        
    # Remove MongoDB specific fields before inserting into main dataset
    course_to_insert = pending.copy()
    course_to_insert.pop('_id', None)
    course_to_insert.pop('status', None)
    course_to_insert.pop('submitted_by', None)
    course_to_insert.pop('submitted_at', None)
    
    # Insert into main courses DB
    db.courses.insert_one(course_to_insert)
    
    # Delete from pending
    db.submitted_courses.delete_one({"_id": ObjectId(course_id)})
    
    # Reload model asynchronously
    thread = threading.Thread(target=load_and_train_model)
    thread.start()
    
    return jsonify({"success": True, "message": "Course approved and added to catalog!"})

@app.route('/api/admin/reject_course', methods=['POST'])
@admin_required
def reject_course():
    data = request.get_json() or {}
    course_id = data.get('course_id')
    
    if not course_id:
        return jsonify({"success": False, "error": "No course ID provided"}), 400
        
    db = get_db()
    result = db.submitted_courses.delete_one({"_id": ObjectId(course_id)})
    
    if result.deleted_count > 0:
        return jsonify({"success": True, "message": "Course rejected and deleted"})
    else:
        return jsonify({"success": False, "error": "Course not found"}), 404

@app.route('/api/delete_course', methods=['POST'])
@admin_required
def delete_course():
    data = request.get_json() or {}
    course_url = data.get('url')
    
    if not course_url:
        return jsonify({"success": False, "error": "No course URL provided"}), 400
        
    db = get_db()
    result = db.courses.delete_one({"url": course_url})
    
    if result.deleted_count > 0:
        # Reload model asynchronously so we don't block the UI
        thread = threading.Thread(target=load_and_train_model)
        thread.start()
        return jsonify({"success": True, "message": "Course deleted successfully"})
    else:
        return jsonify({"success": False, "error": "Course not found"}), 404

@app.route('/api/admin/toggle_user_role', methods=['POST'])
@admin_required
def toggle_user_role():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_role = data.get('role')
    
    if not user_id or not new_role:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
        
    db = get_db()
    target_user = db.users.find_one({"_id": user_id})
    if not target_user:
        return jsonify({"success": False, "error": "User not found"}), 404
        
    current_user = db.users.find_one({"_id": session.get('user_id')})
    if not current_user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    current_is_super = check_is_super_admin(current_user)
    target_is_super = check_is_super_admin(target_user)
    
    # Rule 1: Cannot demote the last remaining admin
    if target_user.get('role') == 'admin' and new_role != 'admin':
        admin_count = db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            return jsonify({"success": False, "error": "Security Restriction: Cannot demote the only remaining admin."}), 403
            
    # Rule 2: Cannot demote the last remaining super admin
    if target_is_super and new_role != 'admin' and new_role != 'super_admin':
        all_admins = list(db.users.find({"role": {"$in": ["admin", "super_admin"]}}))
        super_count = sum(1 for u in all_admins if check_is_super_admin(u))
        if super_count <= 1:
            return jsonify({"success": False, "error": "Security Restriction: Cannot demote the only remaining Super Admin."}), 403

    # Rule 3: Promoting, demoting, or modifying an Admin/Super Admin account
    if (target_user.get('role') in ['admin', 'super_admin'] or target_is_super or new_role in ['admin', 'super_admin']):
        if not current_is_super:
            return jsonify({"success": False, "error": "Security Restriction: Only a Super Admin can promote, demote, or modify admin accounts."}), 403

    result = db.users.update_one({"_id": user_id}, {"$set": {"role": new_role}})
    
    if result.modified_count > 0:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Role already set to this value"}), 400

@app.route('/api/admin/delete_user', methods=['POST'])
@admin_required
def delete_user_admin():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"success": False, "error": "Missing user ID"}), 400
        
    # Prevent admin from deleting themselves accidentally
    if user_id == session.get('user_id'):
        return jsonify({"success": False, "error": "You cannot delete your own admin account from here."}), 403
        
    db = get_db()
    target_user = db.users.find_one({"_id": user_id})
    if not target_user:
        return jsonify({"success": False, "error": "User not found"}), 404
        
    current_user = db.users.find_one({"_id": session.get('user_id')})
    if not current_user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    current_is_super = check_is_super_admin(current_user)
    target_is_super = check_is_super_admin(target_user)
    
    # Rule 1: Cannot delete the last remaining admin
    if target_user.get('role') == 'admin':
        admin_count = db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            return jsonify({"success": False, "error": "Security Restriction: Cannot delete the only remaining admin."}), 403
            
    # Rule 2: Cannot delete the last remaining super admin
    if target_is_super:
        all_admins = list(db.users.find({"role": {"$in": ["admin", "super_admin"]}}))
        super_count = sum(1 for u in all_admins if check_is_super_admin(u))
        if super_count <= 1:
            return jsonify({"success": False, "error": "Security Restriction: Cannot delete the only remaining Super Admin."}), 403
            
    # Rule 3: Deleting an Admin or Super Admin requires being a Super Admin themselves
    if target_user.get('role') in ['admin', 'super_admin'] or target_is_super:
        if not current_is_super:
            return jsonify({"success": False, "error": "Security Restriction: Only a Super Admin can delete another admin account."}), 403
            
    result = db.users.delete_one({"_id": user_id})
    
    if result.deleted_count > 0:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "User not found"}), 404

@app.route('/api/admin/add_course', methods=['POST'])
@admin_required
def add_course():
    data = request.get_json() or {}
    
    title = data.get('title')
    provider = data.get('provider')
    url = data.get('url')
    stars = data.get('stars', 0.0)
    
    if not title or not provider or not url:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
        
    db = get_db()
    
    # Check if URL already exists
    if db.courses.find_one({"url": url}):
        return jsonify({"success": False, "error": "Course with this URL already exists"}), 400
        
    new_course = {
        "title": title,
        "provider": provider,
        "url": url,
        "stars": float(stars),
        "track": "General CS" # Default track
    }
    
    db.courses.insert_one(new_course)
    
    # Reload model asynchronously
    thread = threading.Thread(target=load_and_train_model)
    thread.start()
    
    return jsonify({"success": True})

@app.route('/api/admin/edit_course', methods=['POST'])
@admin_required
def edit_course():
    data = request.get_json() or {}
    
    old_url = data.get('old_url')
    title = data.get('title')
    provider = data.get('provider')
    url = data.get('url')
    stars = data.get('stars', 0.0)
    
    if not old_url or not title or not provider or not url:
        return jsonify({"success": False, "error": "Missing required fields"}), 400
        
    db = get_db()
    
    # If URL is being changed, ensure new URL doesn't conflict
    if old_url != url and db.courses.find_one({"url": url}):
        return jsonify({"success": False, "error": "A course with the new URL already exists"}), 400
        
    update_data = {
        "title": title,
        "provider": provider,
        "url": url,
        "stars": float(stars)
    }
    
    result = db.courses.update_one({"url": old_url}, {"$set": update_data})
    
    if result.modified_count > 0 or result.matched_count > 0:
        # Reload model asynchronously
        thread = threading.Thread(target=load_and_train_model)
        thread.start()
        return jsonify({"success": True})
        
    return jsonify({"success": False, "error": "Course not found"}), 404


# ─────────────────────────────────────────────────────────────────
# Admin: Live Scraper Control
# ─────────────────────────────────────────────────────────────────

def _run_scraper_background():
    """Run the scraper in a background thread and update scraper_state."""
    global scraper_state
    try:
        # Patch scraper to capture log output
        import io as _io
        import sys as _sys
        from scraper import run_scraper as _run_scraper

        scraper_state["status"] = "running"
        scraper_state["log"] = ["[Scraper] Starting live scraper — this may take several minutes..."]
        scraper_state["inserted"] = 0
        scraper_state["found"] = 0
        scraper_state["started_at"] = datetime.utcnow().isoformat()
        scraper_state["finished_at"] = None

        # Redirect stdout so we capture print() from scraper.py
        old_stdout = _sys.stdout
        _sys.stdout = captured = _io.StringIO()

        try:
            _run_scraper()
        finally:
            _sys.stdout = old_stdout

        output = captured.getvalue()
        lines = [l for l in output.splitlines() if l.strip()]
        scraper_state["log"] = lines[-80:]  # keep last 80 lines

        # Parse inserted count from output
        for line in lines:
            if "Inserted" in line and "new courses" in line:
                try:
                    parts = line.split()
                    idx = parts.index("Inserted")
                    scraper_state["inserted"] = int(parts[idx + 1])
                except Exception:
                    pass
            if "Fetched" in line and "courses total" in line:
                try:
                    parts = line.split()
                    scraper_state["found"] = int(parts[1])
                except Exception:
                    pass

        scraper_state["log"].append(f"[Scraper] ✅ Done! Found {scraper_state['found']} courses, inserted {scraper_state['inserted']} new ones.")
        scraper_state["status"] = "done"

        # Reload AI model with new data
        thread = threading.Thread(target=load_and_train_model)
        thread.start()

    except Exception as exc:
        scraper_state["log"].append(f"[Scraper] ❌ Error: {exc}")
        scraper_state["status"] = "error"
    finally:
        scraper_state["finished_at"] = datetime.utcnow().isoformat()


@app.route('/api/admin/run_scraper', methods=['POST'])
@admin_required
def api_run_scraper():
    global scraper_state
    if scraper_state.get("status") == "running":
        return jsonify({"success": False, "error": "Scraper is already running."}), 400

    # Reset state
    scraper_state = {
        "status": "starting",
        "log": ["[Scraper] Initializing..."],
        "inserted": 0,
        "found": 0,
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }

    t = threading.Thread(target=_run_scraper_background, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Scraper started in background."})


@app.route('/api/admin/scraper_status', methods=['GET'])
@admin_required
def api_scraper_status():
    global scraper_state
    return jsonify({
        "status": scraper_state.get("status", "idle"),
        "log": scraper_state.get("log", []),
        "inserted": scraper_state.get("inserted", 0),
        "found": scraper_state.get("found", 0),
        "started_at": scraper_state.get("started_at"),
        "finished_at": scraper_state.get("finished_at"),
    })


# ─────────────────────────────────────────────────────────────────
# Admin: CSV Upload & Clean
# ─────────────────────────────────────────────────────────────────

# Known column aliases (lowercase) → canonical field name
_CSV_COLUMN_MAP = {
    # title
    "title": "title", "name": "title", "course_name": "title",
    "course title": "title", "coursetitle": "title",
    # url
    "url": "url", "link": "url", "course_url": "url", "courseurl": "url",
    "course link": "url",
    # provider
    "provider": "provider", "platform": "provider", "source": "provider",
    "organization": "provider", "institution": "provider",
    # stars / rating
    "stars": "stars", "rating": "stars", "score": "stars",
    "average rating": "stars", "avg_rating": "stars",
    # description / content
    "content_text": "content_text", "description": "content_text",
    "desc": "content_text", "about": "content_text",
    "content": "content_text", "overview": "content_text",
    # ratings count
    "ratings_count": "ratings_count", "num_ratings": "ratings_count",
    "reviews": "ratings_count", "review_count": "ratings_count",
}


def _clean_csv_dataframe(raw_df):
    """Normalize, clean, and validate a raw CSV DataFrame."""
    # Build column rename mapping
    rename_map = {}
    for col in raw_df.columns:
        canon = _CSV_COLUMN_MAP.get(col.strip().lower())
        if canon:
            rename_map[col] = canon

    df_clean = raw_df.rename(columns=rename_map)

    # Must have at least a title column after mapping
    if "title" not in df_clean.columns:
        raise ValueError("Could not detect a 'title' or 'name' column in the CSV.")

    # Fill required fields
    if "url" not in df_clean.columns:
        df_clean["url"] = ""
    if "provider" not in df_clean.columns:
        df_clean["provider"] = "Unknown"
    if "content_text" not in df_clean.columns:
        df_clean["content_text"] = ""
    if "stars" not in df_clean.columns:
        df_clean["stars"] = 0.0
    if "ratings_count" not in df_clean.columns:
        df_clean["ratings_count"] = 0

    # Clean strings
    for col in ["title", "url", "provider", "content_text"]:
        df_clean[col] = df_clean[col].astype(str).str.strip()

    # Coerce numeric
    df_clean["stars"] = pd.to_numeric(df_clean["stars"], errors="coerce").fillna(0.0).clip(0, 5)
    df_clean["ratings_count"] = pd.to_numeric(df_clean["ratings_count"], errors="coerce").fillna(0).astype(int)

    # Remove rows with blank title
    df_clean = df_clean[df_clean["title"].str.len() > 0]
    df_clean = df_clean.drop_duplicates(subset=["title"])

    return df_clean


@app.route('/api/admin/upload_csv', methods=['POST'])
@admin_required
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files['file']
    if not file.filename or not file.filename.lower().endswith('.csv'):
        return jsonify({"success": False, "error": "Please upload a .csv file."}), 400

    try:
        raw_df = pd.read_csv(file, encoding='utf-8', on_bad_lines='skip')
    except Exception:
        try:
            file.seek(0)
            raw_df = pd.read_csv(file, encoding='latin-1', on_bad_lines='skip')
        except Exception as e:
            return jsonify({"success": False, "error": f"Could not parse CSV: {e}"}), 400

    try:
        df_clean = _clean_csv_dataframe(raw_df)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database connection error."}), 500

    inserted = 0
    skipped = 0
    for _, row in df_clean.iterrows():
        doc = {
            "title": row["title"],
            "url": row["url"],
            "provider": row["provider"],
            "content_text": row["content_text"],
            "stars": float(row["stars"]),
            "ratings_count": int(row["ratings_count"]),
        }
        # Upsert by title to avoid duplicates
        result = db.courses.update_one(
            {"title": doc["title"]},
            {"$set": doc},
            upsert=True
        )
        if result.upserted_id:
            inserted += 1
        else:
            skipped += 1

    # Reload AI model asynchronously
    if inserted > 0:
        thread = threading.Thread(target=load_and_train_model)
        thread.start()

    return jsonify({
        "success": True,
        "inserted": inserted,
        "skipped": skipped,
        "total_in_file": len(df_clean),
        "message": f"Imported {inserted} new courses, skipped {skipped} duplicates."
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)

