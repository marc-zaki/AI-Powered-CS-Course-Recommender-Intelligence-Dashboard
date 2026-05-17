from flask import Flask, render_template, request, redirect, url_for, jsonify
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
import urllib.robotparser
import urllib.parse
from urllib.parse import urlparse, urljoin
import requests
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()  # Load API keys from .env file

scrape_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "message": ""
}

# Configuration loaded from .env file
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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

    # Parse Stars and Ratings directly if they exist
    if 'ratings_count' not in df.columns:
        df['ratings_count'] = 0
    else:
        df['ratings_count'] = df['ratings_count'].fillna(0).astype(int)

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

def setup_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=chrome_options)

def check_robots_txt(url, user_agent="*"):
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    robots_url = f"{base_url}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True

def serpapi_fetch_courses():
    """Fetch CS courses from Google via SerpApi across multiple topics."""
    if not SERPAPI_KEY:
        print("SerpApi: No API key set. Skipping. Set SERPAPI_KEY env variable.")
        return []

    topics = [
        "computer science online course",
        "python programming course",
        "machine learning course",
        "artificial intelligence course",
        "data science course",
        "cybersecurity course",
        "web development course",
        "algorithms and data structures course",
        "cloud computing course",
        "database management course",
        "software engineering course",
        "deep learning course",
        "computer networking course",
        "operating systems course",
        "blockchain course",
    ]

    all_courses = []
    for i, topic in enumerate(topics):
        scrape_status["message"] = f"SerpApi: Searching '{topic}' ({i+1}/{len(topics)})..."
        print(scrape_status["message"])
        scrape_status["progress"] += 1

        try:
            params = {
                "engine": "google",
                "q": topic,
                "api_key": SERPAPI_KEY,
                "gl": "us",
                "hl": "en",
                "num": 20,
            }
            search = GoogleSearch(params)
            results = search.get_dict()

            # Extract from organic results that look like courses
            for result in results.get("organic_results", []):
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                link = result.get("link", "")
                source = result.get("source", "")

                # Filter: only keep results from known course platforms
                course_platforms = [
                    "coursera", "edx", "udemy", "udacity", "futurelearn",
                    "pluralsight", "linkedin learning", "skillshare",
                    "codecademy", "datacamp", "brilliant", "stanford",
                    "mit", "harvard", "class central", "classcentral",
                    "freecodecamp", "kaggle", "google", "microsoft learn",
                ]
                source_lower = source.lower() if source else ""
                link_lower = link.lower() if link else ""
                is_course = any(
                    p in source_lower or p in link_lower
                    for p in course_platforms
                )

                if title and is_course:
                    # Determine provider from source or URL
                    provider = source if source else "Online"
                    for p_name in ["Coursera", "edX", "Udemy", "Udacity",
                                   "FutureLearn", "Pluralsight", "Codecademy",
                                   "DataCamp", "Kaggle", "Brilliant"]:
                        if p_name.lower() in link_lower:
                            provider = p_name
                            break

                    all_courses.append({
                        "provider": provider,
                        "title": title,
                        "content_text": snippet if snippet else "No description provided.",
                        "url": link,
                        "raw_reviews": [],
                        "review_summary": "",
                    })

            # Respect rate limits
            time.sleep(1)

        except Exception as e:
            print(f"SerpApi error for '{topic}': {e}")

    print(f"SerpApi: Fetched {len(all_courses)} courses total.")
    return all_courses

def background_scraper():
    global scrape_status
    scrape_status["is_running"] = True
    scrape_status["progress"] = 0
    scrape_status["message"] = "Initializing scraper..."
    
    all_data = []
    
    mit_topics = [
        "python", "artificial+intelligence", "data+science", "machine+learning", 
        "cybersecurity", "algorithms", "software+engineering", "database",
        "web+development", "networking", "cloud+computing", "robotics",
        "computer+architecture", "operating+systems", "blockchain"
    ]
    
    targets = []
    for topic in mit_topics:
        targets.append({"name": f"MIT OCW ({topic})", "url": f"https://ocw.mit.edu/search/?q={topic}"})
        
    targets.extend([
        {"name": "CourseTalk", "url": "https://coursetalk.tumblr.com/"},
        {"name": "Cybrary (AI Foundations)", "url": "https://www.cybrary.it/career-path/ai-technical-foundations"},
        {"name": "Cybrary (AI Cyber)", "url": "https://www.cybrary.it/career-path/ai-for-cybersecurity"},
        {"name": "Cybrary (Cloud)", "url": "https://www.cybrary.it/career-path/cloud-security-engineer"},
        {"name": "Cybrary (Network)", "url": "https://www.cybrary.it/career-path/network-engineer"},
        {"name": "Coursera (CS)", "url": "https://www.coursera.org/browse/computer-science"},
        {"name": "Coursera (Data Science)", "url": "https://www.coursera.org/browse/data-science"},
        {"name": "Coursera (IT)", "url": "https://www.coursera.org/browse/information-technology"},
        {"name": "Khan Academy", "url": "https://www.khanacademy.org/computing/computer-programming"}
    ])

    # Total includes Selenium targets + 15 SerpApi topic searches
    serpapi_topic_count = 15 if SERPAPI_KEY else 0
    scrape_status["total"] = len(targets) + serpapi_topic_count
    driver = setup_browser()
    
    for site in targets:
        scrape_status["message"] = f"Scanning {site['name']}..."
        print(scrape_status["message"])
        
        if not check_robots_txt(site['url']):
            print(f"Skipping {site['name']} due to robots.txt")
            scrape_status["progress"] += 1
            continue
            
        try:
            driver.get(site['url'])
            time.sleep(4)
            # Scroll multiple times to trigger lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # 1. COURSERA (Deep Scraping for Reviews)
            if "Coursera" in site['name']:
                # First collect the URLs
                course_links = []
                for card in soup.find_all('div', class_='cds-ProductCard-content'):
                    title_tag = card.find('h3', class_='cds-CommonCard-title')
                    partner_tag = card.find('p', class_='cds-ProductCard-partnerNames')
                    if title_tag:
                        title = title_tag.text.strip()
                        raw_text = card.get_text(separator=' ', strip=True)
                        clean_desc = raw_text.replace(title, "").replace(partner_tag.text.strip() if partner_tag else "", "").strip()
                        link_tag = title_tag.parent if title_tag.parent.name == 'a' else card.find('a', href=True)
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        course_links.append({
                            "provider": partner_tag.text.strip() if partner_tag else "Coursera", 
                            "title": title, 
                            "content_text": clean_desc,
                            "url": exact_url
                        })
                
                # Now deep scrape each Coursera course for reviews
                for i, course in enumerate(course_links):
                    scrape_status["message"] = f"Deep scraping reviews: {course['title']} ({i+1}/{len(course_links)})..."
                    print(scrape_status["message"])
                    raw_reviews = []
                    try:
                        # Navigate to the /reviews page — Coursera puts reviews there, not on the main page
                        review_url = course['url'].rstrip('/') + '/reviews'
                        driver.get(review_url)
                        time.sleep(4)
                        
                        # Scroll down to load dynamically-rendered reviews
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                        time.sleep(2)
                        
                        course_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        
                        # Coursera uses <p class="css-1ry8q1o"> for the actual review body text
                        review_elements = course_soup.find_all('p', class_='css-1ry8q1o')
                        
                        # Fallback: any <p> inside elements with 'review' in their class
                        if not review_elements:
                            review_containers = course_soup.find_all('div', class_=lambda c: c and 'review' in str(c).lower())
                            for container in review_containers:
                                for p in container.find_all('p'):
                                    if len(p.get_text(strip=True)) > 40:
                                        review_elements.append(p)
                             
                        for rev in review_elements:
                            text = rev.get_text(strip=True)
                            if len(text) > 40 and text not in raw_reviews:
                                raw_reviews.append(text)
                                if len(raw_reviews) >= 10:
                                    break
                    except Exception as e:
                        print(f"Error deep scraping {course['url']}: {e}")
                    
                    course["raw_reviews"] = raw_reviews
                    course["review_summary"] = extract_review_summary(raw_reviews)
                    all_data.append(course)

            # 2. CYBRARY
            elif "Cybrary" in site['name']:
                for card in soup.find_all('div', class_='career-path_sub-content-item'):
                    title_tag = card.find(['h6', 'h3'], class_='career-course-title')
                    desc_tag = card.find('div', class_='course-description')
                    if title_tag:
                        link_tag = title_tag.parent if title_tag.parent.name == 'a' else card.find('a', href=True)
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        all_data.append({
                            "provider": "Cybrary", 
                            "title": title_tag.text.strip(), 
                            "content_text": desc_tag.text.strip() if desc_tag else "",
                            "url": exact_url
                        })

            # 3. KHAN ACADEMY
            elif site['name'] == "Khan Academy":
                headers = soup.find_all(['h2', 'h3'])
                ignore_list = [
                    'log in', 'sign up', 'donate', 'search', 'about us', 'courses', 
                    'site navigation', 'contact', 'download our apps', 'use of cookies', 
                    'privacy preference center', 'manage consent preferences', 'cookie list',
                    'welcome!', 'browse projects', 'meet the professional'
                ]
                for header in headers:
                    title = header.text.strip()
                    title_lower = title.lower()
                    if len(title) > 6 and title_lower not in ignore_list and not title_lower.startswith('unit'):
                        parent = header.parent
                        raw_text = parent.get_text(separator=' ', strip=True) if parent else ""
                        clean_desc = raw_text.replace(title, "").strip()
                        if len(clean_desc) < 5 and parent.parent:
                            raw_text = parent.parent.get_text(separator=' ', strip=True)
                            clean_desc = raw_text.replace(title, "").strip()
                        link_tag = header.find_parent('a', href=True) or header.find('a', href=True)
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        if "Cookies are small files" not in clean_desc:
                            all_data.append({
                                "provider": site['name'], 
                                "title": title, 
                                "content_text": clean_desc if clean_desc else "No description provided.",
                                "url": exact_url
                            })

            # 4. MIT & COURSETALK
            else:
                for card in soup.find_all(['article', 'div'], class_=['course-card', 'post', 'card']):
                    title_tag = card.find(['h2', 'h3', 'div'], class_=['course-title', 'title'])
                    if not title_tag:
                        title_tag = card.find(['h2', 'h3'])
                    if title_tag and len(title_tag.text.strip()) > 5:
                        title = title_tag.text.strip()
                        raw_text = card.get_text(separator=' ', strip=True)
                        clean_desc = raw_text.replace(title, "").strip()
                        link_tag = card.find('a', href=True)
                        if not link_tag and title_tag.parent.name == 'a':
                            link_tag = title_tag.parent
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        all_data.append({
                            "provider": site['name'].split(" ")[0], 
                            "title": title, 
                            "content_text": clean_desc,
                            "url": exact_url
                        })
        except Exception as e: 
            print(f"Error scraping {site['name']}: {e}")
            
        scrape_status["progress"] += 1
            
    driver.quit()

    # ── Phase 2: SerpApi ─────────────────────────────────────────────
    scrape_status["message"] = "Starting SerpApi phase..."
    serpapi_courses = serpapi_fetch_courses()
    all_data.extend(serpapi_courses)
    
    if all_data:
        scrape_status["message"] = "Saving and retraining AI model..."
        try:
            existing_df = pd.read_json("CS_Dataset_Phase2.json")
        except:
            existing_df = pd.DataFrame()
        
        df_new = pd.DataFrame(all_data)
        combined_df = pd.concat([existing_df, df_new]).drop_duplicates(subset=['title'], keep='last')
        combined_df.to_json("CS_Dataset_Phase2.json", orient='records', indent=4)
        
        try:
            combined_df.to_excel("CS_Dataset_Phase2.xlsx", index=False)
        except:
            pass
            
        load_and_train_model() # Reload global model

        selenium_count = len(df_new) - len(serpapi_courses)
        scrape_status["message"] = f"Complete! Indexed {selenium_count} scraped + {len(serpapi_courses)} API courses."
    else:
        scrape_status["message"] = "Complete! No new courses found."
        
    scrape_status["is_running"] = False

@app.route('/scrape', methods=['POST'])
def start_scraper():
    if not scrape_status["is_running"]:
        thread = threading.Thread(target=background_scraper)
        thread.start()
        return jsonify({"success": True, "message": "Scraper started"})
    return jsonify({"success": False, "message": "Scraper is already running"})

@app.route('/scrape_status', methods=['GET'])
def get_scrape_status():
    return jsonify(scrape_status)

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

    # Featured = top 12 highest-rated courses, preferring those with review summaries
    featured_df = df.copy()
    featured_df['has_review'] = featured_df['review_summary'].apply(lambda x: 1 if x and str(x).strip() else 0)
    featured = featured_df.sort_values(by=['stars', 'has_review'], ascending=[False, False]).head(12)
    courses = featured.to_dict('records')
    return render_template('index.html', courses=courses, query="", is_search=False, show_all=False, total_courses=len(df), page=1, total_pages=1)

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

@app.route('/generate_path', methods=['POST'])
def generate_path():
    if df is None:
        return jsonify({"success": False, "error": "Dataset is not loaded."}), 500

    if not GEMINI_API_KEY:
        return jsonify({
            "success": False, 
            "error": "Gemini API Key is missing. Please set GEMINI_API_KEY in your .env file."
        }), 400

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

    try:
        # Define the model — we use gemini-2.5-flash which is extremely fast and free
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )

        response = model.generate_content(user_prompt)
        path_html = response.text.strip()
        
        # Clean any accidental markdown code fences
        path_html = re.sub(r"^```html\n", "", path_html)
        path_html = re.sub(r"\n```$", "", path_html)

        return jsonify({
            "success": True,
            "goal": user_goal,
            "path_html": path_html
        })

    except Exception as e:
        print(f"Gemini generation error: {e}")
        return jsonify({"success": False, "error": f"Failed to generate roadmap: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
