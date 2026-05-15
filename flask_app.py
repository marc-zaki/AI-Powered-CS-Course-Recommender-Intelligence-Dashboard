from flask import Flask, render_template, request, redirect, url_for
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
except Exception:
    pass

app = Flask(__name__)

# Global variables for AI model
df = None
vectorizer = None
tfidf_matrix = None

def load_and_train_model():
    global df, vectorizer, tfidf_matrix
    print("Loading data and training AI model...")
    try:
        df = pd.read_json("CS_Dataset_Phase2.json")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    # Calculate 1-5 Stars
    sia = SentimentIntensityAnalyzer()
    def get_stars(text):
        if not text or text == "No description provided.":
            return 3
        score = sia.polarity_scores(str(text))['compound']
        stars = round((score + 1) * 2) + 1
        return min(max(stars, 1), 5)

    df['stars'] = df['content_text'].apply(get_stars)

    # Train TF-IDF
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(df['indexed_string'])
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
        return "Error: Dataset not loaded. Please ensure CS_Dataset_Phase2.json exists.", 500

    # Show first 50 courses by default to keep page load fast
    courses = df.head(50).to_dict('records')
    return render_template('index.html', courses=courses, query="", is_search=False, total_courses=len(df))

@app.route('/search', methods=['GET'])
def search():
    if df is None:
        return redirect(url_for('index'))

    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('index'))

    cleaned_query = clean_user_query(query)
    if not cleaned_query:
        cleaned_query = query.lower()

    query_vector = vectorizer.transform([cleaned_query])
    similarity_scores = cosine_similarity(query_vector, tfidf_matrix).flatten()
    
    top_indices = similarity_scores.argsort()[-20:][::-1]
    
    results = []
    for i in top_indices:
        score = similarity_scores[i]
        if score > 0.02: # Threshold
            results.append(df.iloc[i].to_dict())

    return render_template('index.html', courses=results, query=query, is_search=True, total_courses=len(df))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
