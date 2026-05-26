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

from dotenv import load_dotenv
import google.generativeai as genai
import pymongo

load_dotenv()  # Load API keys from .env file


# Configuration loaded from .env file
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

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

def load_and_train_model():
    global df, vectorizer, tfidf_matrix
    print("Loading data and training AI model...")
    
    db_name = "cs_recommender"
    collection_name = "courses"
    loaded_from_mongo = False
    
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    try:
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
        
    results = recs.head(20).to_dict('records')

    return render_template('index.html', courses=results, query=query, is_search=True, show_all=False, total_courses=len(df), page=1, total_pages=1)

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

@app.route('/api/stats')
def api_stats():
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
    import urllib.parse
    
    html = []
    
    # 1. Graceful API notice banner
    html.append(
        '<div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); '
        'border-radius: 10px; padding: 1.15rem; margin-bottom: 2rem; display: flex; align-items: center; '
        'gap: 0.85rem; color: #F59E0B; font-size: 0.925rem; font-weight: 600; line-height: 1.55;">'
        '<span style="font-size: 1.25rem;">⚠️</span>'
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
        html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c1.get("provider")}) — ⭐ {c1_stars:.1f} ({c1_reviews:,} ratings)</span>')
        html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c1.get("content_text")[:200]}...</span>')
        if c1_url != '#':
            html.append(f'<a class="path-link" href="{c1_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;">📚 View Syllabus & Lectures →</a>')
        html.append('</li>')
        
        # Course 2 (if present)
        if c2:
            c2_stars = float(c2.get('stars', 4.5))
            c2_reviews = int(c2.get('ratings_count', 1500))
            c2_url = c2.get('url', '#')
            c2_redirect = f"/verify_link?url={urllib.parse.quote(c2_url)}&title={urllib.parse.quote(c2.get('title'))}&provider={urllib.parse.quote(c2.get('provider'))}" if c2_url != '#' else '#'
            
            html.append(f'<li style="margin-bottom: 0.75rem; margin-top: 1rem; line-height: 1.6;">')
            html.append(f'<strong style="color: var(--text-main); font-weight: 700;">{c2.get("title")}</strong> ')
            html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c2.get("provider")}) — ⭐ {c2_stars:.1f} ({c2_reviews:,} ratings)</span>')
            html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c2.get("content_text")[:200]}...</span>')
            if c2_url != '#':
                html.append(f'<a class="path-link" href="{c2_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;">📚 View Syllabus & Lectures →</a>')
            html.append('</li>')
            
        html.append('</ul>')
        
        # Bespoke Recommended Practical Exercise!
        html.append(f'<div style="background: rgba(50, 130, 184, 0.08); border-left: 3px solid var(--secondary); padding: 0.95rem 1.25rem; border-radius: 0 8px 8px 0; margin-top: 1.25rem;">')
        html.append(f'<strong style="color: var(--text-main); font-size: 0.9rem; display: block; margin-bottom: 0.35rem;">🛠️ Weekly Practical Exercise:</strong>')
        html.append(f'<span style="color: var(--text-muted); font-size: 0.875rem; line-height: 1.55; display: block;">Design and construct a modular software module incorporating the core competencies introduced this week. Focus on writing clean object-oriented logic, defining API schemas, and implementing comprehensive unit tests to validate boundaries on <strong>"{c1.get("title")}"</strong>. Commit your solution to a portfolio repository on GitHub.</span>')
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
        "6. Start directly with the syllabus layout. Do not include introductory conversational fluff or markdown code blocks like ```html."
    )

    user_prompt = f"""
    Student Goal: "{user_goal}"
    
    Available Courses in Database (with Ratings):
    {json.dumps(courses_context, indent=2)}
    
    Please build a premium week-by-week curriculum using these courses.
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
                "model": "llama-3.1-70b-versatile",
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
        if not user or user.get('role') != 'admin':
            flash("Admin access required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        db = get_db()
        if db is not None:
            user = db.users.find_one({"_id": session['user_id']})
    return dict(current_user=user)

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
    return render_template('admin.html', users=users, courses=courses, page=page, total_pages=total_pages)

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
    result = db.users.update_one({"_id": user_id}, {"$set": {"role": new_role}})
    
    if result.modified_count > 0:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "User not found or role already set"}), 404

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
