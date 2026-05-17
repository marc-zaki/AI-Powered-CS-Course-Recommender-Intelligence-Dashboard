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
from urllib.parse import urlparse, urljoin
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

scrape_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "message": ""
}
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

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

    # Calculate 1-5 Stars using Sentiment + Platform Prestige
    sia = SentimentIntensityAnalyzer()
    def calculate_ai_rating(row):
        text = str(row.get('content_text', ''))
        raw_reviews = row.get('raw_reviews', [])
        
        # Calculate base sentiment from description
        desc_sentiment = sia.polarity_scores(text)['compound'] if text and text != "No description provided." else 0
        
        # Calculate review sentiment if available
        review_sentiment = 0
        if isinstance(raw_reviews, list) and raw_reviews:
            review_scores = [sia.polarity_scores(str(r))['compound'] for r in raw_reviews]
            review_sentiment = sum(review_scores) / len(review_scores)
            # Heavy weighting towards actual reviews
            sentiment = (desc_sentiment * 0.3) + (review_sentiment * 0.7)
        else:
            sentiment = desc_sentiment
            
        stars = (sentiment + 1) * 1.0 + 2.5
        if any(p in str(row.get('provider', '')).lower() for p in ['mit', 'google', 'stanford', 'coursera']):
            stars += 0.8
        return min(max(round(stars), 1), 5)

    df['stars'] = df.apply(calculate_ai_rating, axis=1)

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

    scrape_status["total"] = len(targets)
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
        scrape_status["message"] = f"Complete! Indexed {len(df_new)} scraped courses."
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
