import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

# Download required NLTK data (runs once)
try:
    nltk.download('vader_lexicon', quiet=True)
except Exception:
    pass

# Set up the Streamlit Page
st.set_page_config(page_title="CS Course Intelligence", page_icon="💻", layout="centered")

# --- 1. DATA LOADING & AI TRAINING (Cached so it's fast) ---
@st.cache_data
def load_and_train_model():
    try:
        df = pd.read_json("CS_Dataset_Phase2.json")
    except Exception:
        st.error("Could not find CS_Dataset_Phase2.json! Make sure your scraping script ran.")
        return None, None, None

    # Calculate 1-5 Stars using NLTK Sentiment Analysis
    sia = SentimentIntensityAnalyzer()
    def get_stars(text):
        if not text or text == "No description provided.":
            return 3 # Default to 3 stars if there is no text
        
        # 'compound' is a score from -1 (very negative) to +1 (very positive)
        score = sia.polarity_scores(str(text))['compound']
        
        # Math trick to map a [-1 to 1] score into a [1 to 5] star rating
        stars = round((score + 1) * 2) + 1
        return min(max(stars, 1), 5) # Ensure it stays exactly between 1 and 5

    df['stars'] = df['content_text'].apply(get_stars)

    # Train the TF-IDF Search Engine
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(df['indexed_string'])
    
    return df, vectorizer, tfidf_matrix

df, vectorizer, tfidf_matrix = load_and_train_model()

# --- 2. SEARCH LOGIC ---
def clean_user_query(query):
    stop_words = set(stopwords.words('english'))
    text = str(query).lower()
    text = re.sub(r'[^a-z\s]', '', text) 
    tokens = word_tokenize(text) 
    cleaned_query = [word for word in tokens if word not in stop_words]
    return " ".join(cleaned_query)

# --- 3. THE GUI DASHBOARD ---
st.title("🧠 AI-Powered CS Course Recommender")
st.markdown("Search for any computer science track (e.g., *'Web Development'*, *'Cybersecurity'*, *'Python programming'*).")

# The Search Bar
user_query = st.text_input("🔍 What do you want to learn today?", placeholder="Type a topic or track...")

# When the user types a query
if user_query and df is not None:
    # 1. Clean query and get math vectors
    cleaned_query = clean_user_query(user_query)
    query_vector = vectorizer.transform([cleaned_query])
    
    # 2. Calculate Cosine Similarity
    similarity_scores = cosine_similarity(query_vector, tfidf_matrix).flatten()
    
    # 3. Get top 5 matches
    top_indices = similarity_scores.argsort()[-5:][::-1]
    
    st.markdown("### 🎯 Recommended Courses")
    
    found_match = False
    for i in top_indices:
        score = similarity_scores[i]
        
        # Only show the course if it actually matches the user's search
        if score > 0.05:
            found_match = True
            course = df.iloc[i]
            
            # Create a nice visual card for each course
            with st.container():
                st.subheader(course['title'])
                
                # Display the AI-Calculated Stars!
                star_display = "⭐" * course['stars']
                st.write(f"**Provider:** {course['provider']} | **AI Rating:** {star_display}")
                
                # Show a snippet of the description
                st.info(course['content_text'][:250] + "...")
                
                # Add a clickable link button
                st.markdown(f"[🔗 View Course]({course['url']})")
                st.divider()
                
    if not found_match:
        st.warning("No perfect matches found. Try using different keywords!")

# Sidebar for extra flair
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2103/2103140.png", width=100)
st.sidebar.title("Dashboard Stats")
if df is not None:
    st.sidebar.metric("Courses Indexed", len(df))
    st.sidebar.metric("Platforms Tracked", df['provider'].nunique())
st.sidebar.caption("Powered by TF-IDF, NLTK VADER, & Cosine Similarity.")