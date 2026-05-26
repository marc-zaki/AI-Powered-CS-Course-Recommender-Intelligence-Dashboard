import os
import time
import json
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
from dotenv import load_dotenv
import pymongo

load_dotenv()  # Load API keys from .env file

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

def get_db():
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        db = client['cs_recommender']
        return db
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None

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

def extract_review_summary(reviews):
    if not reviews:
        return ""
    # Simplified summary for CLI, or could implement NLP summarization here
    return f"Aggregated {len(reviews)} reviews successfully."

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
        print(f"SerpApi: Searching '{topic}' ({i+1}/{len(topics)})...")

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

def run_scraper():
    print("Initializing scraper...")
    
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

    driver = setup_browser()
    
    for site in targets:
        print(f"Scanning {site['name']}...")
        
        if not check_robots_txt(site['url']):
            print(f"Skipping {site['name']} due to robots.txt")
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
            
            # 1. COURSERA
            if "Coursera" in site['name']:
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
                
                # Deep scrape each Coursera course for reviews
                for i, course in enumerate(course_links):
                    print(f"Deep scraping reviews: {course['title']} ({i+1}/{len(course_links)})...")
                    raw_reviews = []
                    try:
                        review_url = course['url'].rstrip('/') + '/reviews'
                        driver.get(review_url)
                        time.sleep(4)
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                        time.sleep(2)
                        
                        course_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        review_elements = course_soup.find_all('p', class_='css-1ry8q1o')
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
            
    driver.quit()

    # Phase 2: SerpApi
    print("Starting SerpApi phase...")
    serpapi_courses = serpapi_fetch_courses()
    all_data.extend(serpapi_courses)
    
    if all_data:
        print("Saving courses...")
        
        # 1. Save to MongoDB
        db = get_db()
        if db is not None:
            new_inserts = 0
            for item in all_data:
                # Upsert based on title to avoid duplicates
                result = db.courses.update_one(
                    {"title": item['title']},
                    {"$set": item},
                    upsert=True
                )
                if result.upserted_id:
                    new_inserts += 1
            print(f"MongoDB Update: Inserted {new_inserts} new courses out of {len(all_data)} found.")
            
        # 2. Save to local JSON dataset as fallback
        os.makedirs("datasets", exist_ok=True)
        db_file = "datasets/CS_Dataset_Phase2.json"
        try:
            existing_df = pd.read_json(db_file)
        except:
            existing_df = pd.DataFrame()
        
        df_new = pd.DataFrame(all_data)
        combined_df = pd.concat([existing_df, df_new]).drop_duplicates(subset=['title'], keep='last')
        combined_df.to_json(db_file, orient='records', indent=4)
        print(f"Saved {len(combined_df)} total courses to local {db_file}")

        print("Complete! Scraper finished successfully.")
    else:
        print("Complete! No new courses found.")

if __name__ == "__main__":
    run_scraper()
