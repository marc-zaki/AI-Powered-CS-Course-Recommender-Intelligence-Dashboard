import os
import sys
import json
import numpy
try:
    import numpy.core
    sys.modules['numpy._core'] = numpy.core
except ImportError:
    pass
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.sentiment import SentimentIntensityAnalyzer
from interview_analyzer.phase2_ir_engine import IREngine
from interview_analyzer.phase2_ai_models import AIModels
from interview_analyzer.phase2_recommendation import RecommendationEngine
from interview_analyzer.phase2_eda_analysis import EDAAnalysis

# Global variables for Course Analyzer
df = None
vectorizer = None
tfidf_matrix = None
global_featured_courses = None

# Global variables for Interview Analyzer
interview_ir_engine = None
interview_ai_models = None
interview_rec_engine = None
interview_eda = None
interview_questions = []

def load_and_train_model(db=None):
    global df, vectorizer, tfidf_matrix, global_featured_courses
    
    # Path to cache file
    cache_dir = os.path.join(os.path.dirname(__file__), "datasets")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = os.path.join(cache_dir, "tfidf_cache.pkl")
    
    # Always load local JSON first
    db_file = os.path.join(os.path.dirname(__file__), "datasets", "CS_Dataset_Phase2.json")
    try:
        df = pd.read_json(db_file)
        print(f"Successfully loaded {len(df)} records from local JSON.")
    except Exception as e:
        print(f"Error loading local dataset: {e}")
        return
        
    if os.path.exists(cache_file):
        try:
            print("Loading TF-IDF vectorizer and model from disk cache...")
            import pickle
            with open(cache_file, "rb") as f:
                cache_data = pickle.load(f)
            vectorizer = cache_data["vectorizer"]
            tfidf_matrix = cache_data["tfidf_matrix"]
            global_featured_courses = cache_data["global_featured_courses"]
            print(f"Successfully loaded TF-IDF matrix and vectorizer from disk cache!")
            return
        except Exception as cache_err:
            print(f"Disk cache load failed, rebuilding model: {cache_err}")

    print("Training AI model...")
    # Train TF-IDF
    def build_search_profile(row):
        title = str(row.get('title', ''))
        desc = str(row.get('content_text', ''))
        summary = str(row.get('review_summary', ''))
        reviews = " ".join([str(r) for r in row.get('raw_reviews', [])]) if isinstance(row.get('raw_reviews'), list) else ""
        return f"{title} {title} {title} {title} {title} {desc} {summary} {reviews}".lower()

    df['search_profile'] = df.apply(build_search_profile, axis=1)
    vectorizer = TfidfVectorizer(stop_words='english', ngram_range=(1, 1), max_features=10000)
    tfidf_matrix = vectorizer.fit_transform(df['search_profile'])
    
    df['has_review'] = df['review_summary'].apply(lambda x: 1 if x and str(x).strip() else 0)
    df['stars_int'] = df['stars'].apply(lambda x: int(float(x)) if pd.notnull(x) else 0)
    global_featured_courses = df.sort_values(by=['stars', 'has_review'], ascending=[False, False]).head(12)
    
    try:
        import pickle
        cache_data = {"vectorizer": vectorizer, "tfidf_matrix": tfidf_matrix, "global_featured_courses": global_featured_courses}
        with open(cache_file, "wb") as f:
            pickle.dump(cache_data, f)
        print("Saved optimized TF-IDF cache to disk.")
    except Exception as save_err:
        pass
    print(f"Successfully loaded and vectorized {len(df)} courses!")

def load_interview_system():
    global interview_ir_engine, interview_ai_models, interview_rec_engine, interview_eda, interview_questions
    print("Loading Interview Analyzer system...")
    try:
        dataset_path = os.path.join(os.path.dirname(__file__), 'interview_analyzer', 'storage', 'dataset_2.json')
        with open(dataset_path, 'r', encoding='utf-8') as f:
            interview_questions = json.load(f)
        
        interview_ir_engine = IREngine(interview_questions)
        interview_ai_models = AIModels(interview_questions)
        interview_rec_engine = RecommendationEngine(interview_ir_engine, interview_ai_models)
        interview_eda = EDAAnalysis(interview_questions, interview_ir_engine, interview_ai_models)
        
        storage_path = os.path.join(os.path.dirname(__file__), 'interview_analyzer', 'storage')
        interview_ir_engine.load_index(storage_path)
        interview_ai_models.load_models(storage_path)
        
        print("Interview Analyzer models loaded successfully!")
    except Exception as e:
        print(f"Error loading Interview Analyzer system: {e}")
