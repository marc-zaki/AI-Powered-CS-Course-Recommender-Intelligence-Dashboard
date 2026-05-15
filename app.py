import time
import json
import re
import urllib.robotparser
from urllib.parse import urlparse, urljoin
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import ssl

# Bypass SSL certificate verification for NLTK (Mac Fix)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Initial NLTK Setup
print("Downloading NLTK Data...")
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt_tab', quiet=True)
except Exception as e:
    print(f"NLTK Warning: {e}")

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

def setup_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Invisible mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=chrome_options)

def clean_and_process_data(raw_data):
    """Processes titles and REVIEWS for AI Model ingestion."""
    print("\nStarting Data Processing Pipeline...")
    df = pd.DataFrame(raw_data)
    if df.empty:
        return df

    initial_count = len(df)
    df = df.dropna(subset=['title'])
    df = df.drop_duplicates(subset=['title'])
    print(f"Data Quality Check: Removed {initial_count - len(df)} duplicates/bad rows.")
    
    stop_words = set(stopwords.words('english'))
    stop_words.update(['course', 'introduction', 'part', 'learning', 'fundamentals', 'science', 'computer', 'class', 'students', 'available', 'catalog', 'review', 'will'])
    
    def apply_nltk_pipeline(text):
        if not isinstance(text, str): return ""
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text) 
        tokens = word_tokenize(text) 
        return [word for word in tokens if word not in stop_words]

    df['full_text'] = df['title'] + " " + df['content_text'].fillna("")
    df['cleaned_tokens'] = df['full_text'].apply(apply_nltk_pipeline)
    df['indexed_string'] = df['cleaned_tokens'].apply(lambda x: " ".join(x))
    
    df = df.drop(columns=['full_text'])
    return df

def perform_eda_and_visualize(df):
    print("\nGenerating Phase 2 Visualizations...")
    if df.empty: return

    all_words = [word for tokens in df['cleaned_tokens'] for word in tokens]
    word_freq = Counter(all_words)
    top_15_words = word_freq.most_common(15) 
    
    plt.figure(figsize=(12, 7))
    if top_15_words:
        words, counts = zip(*top_15_words)
        sns.barplot(x=list(counts), y=list(words), hue=list(words), palette='magma', legend=False)
        plt.title('Top 15 Most Frequent Tech Keywords (Titles & Reviews)')
        plt.xlabel('Frequency')
        plt.ylabel('Keyword')
        plt.tight_layout()
        plt.savefig('keyword_frequency_phase2.png')

    plt.figure(figsize=(8, 8))
    platform_counts = df['provider'].value_counts()
    if not platform_counts.empty:
        platform_counts.plot.pie(autopct='%1.1f%%', cmap='Set3')
        plt.title('Course Distribution by Platform')
        plt.ylabel('')
        plt.savefig('platform_distribution_phase2.png')
    print("✅ Visualizations saved as '_phase2' PNGs.")

def main():
    mit_topics = ["python", "artificial+intelligence", "data+science", "machine+learning", 
                  "cybersecurity", "algorithms", "software+engineering", "database"]
    
    targets = []
    for topic in mit_topics:
        targets.append({"name": f"MIT OCW ({topic})", "url": f"https://ocw.mit.edu/search/?q={topic}"})
        
    targets.extend([
        {"name": "CourseTalk", "url": "https://coursetalk.tumblr.com/"},
        {"name": "Cybrary (AI Foundations)", "url": "https://www.cybrary.it/career-path/ai-technical-foundations"},
        {"name": "Cybrary (AI Cyber)", "url": "https://www.cybrary.it/career-path/ai-for-cybersecurity"},
        {"name": "Coursera", "url": "https://www.coursera.org/browse/computer-science"},
        {"name": "Khan Academy", "url": "https://www.khanacademy.org/computing/computer-programming"}
    ])

    all_scraped_data = []
    driver = setup_browser()

    for site in targets:
        print(f"Scraping: {site['name']}...")
        if not check_robots_txt(site['url']): continue
            
        try:
            driver.get(site['url'])
            time.sleep(4)
            # Force lazy-loading sites to render content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            courses_found = 0

            # 1. COURSERA
            if site['name'] == "Coursera":
                for card in soup.find_all('div', class_='cds-ProductCard-content'):
                    title_tag = card.find('h3', class_='cds-CommonCard-title')
                    partner_tag = card.find('p', class_='cds-ProductCard-partnerNames')
                    
                    if title_tag:
                        title = title_tag.text.strip()
                        raw_text = card.get_text(separator=' ', strip=True)
                        clean_desc = raw_text.replace(title, "").replace(partner_tag.text.strip() if partner_tag else "", "").strip()
                        
                        link_tag = title_tag.parent if title_tag.parent.name == 'a' else card.find('a', href=True)
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        
                        all_scraped_data.append({
                            "provider": partner_tag.text.strip() if partner_tag else "Coursera", 
                            "title": title, 
                            "content_text": clean_desc,
                            "url": exact_url
                        })
                        courses_found += 1

            # 2. CYBRARY
            elif "Cybrary" in site['name']:
                for card in soup.find_all('div', class_='career-path_sub-content-item'):
                    title_tag = card.find(['h6', 'h3'], class_='career-course-title')
                    desc_tag = card.find('div', class_='course-description')
                    
                    if title_tag:
                        link_tag = title_tag.parent if title_tag.parent.name == 'a' else card.find('a', href=True)
                        exact_url = urljoin(site['url'], link_tag['href']) if link_tag else site['url']
                        
                        all_scraped_data.append({
                            "provider": "Cybrary", 
                            "title": title_tag.text.strip(), 
                            "content_text": desc_tag.text.strip() if desc_tag else "",
                            "url": exact_url
                        })
                        courses_found += 1

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
                            all_scraped_data.append({
                                "provider": site['name'], 
                                "title": title, 
                                "content_text": clean_desc if clean_desc else "No description provided.",
                                "url": exact_url
                            })
                            courses_found += 1

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
                        
                        all_scraped_data.append({
                            "provider": site['name'].split(" ")[0], 
                            "title": title, 
                            "content_text": clean_desc,
                            "url": exact_url
                        })
                        courses_found += 1
            
            print(f"  -> Extracted {courses_found} records")

        except Exception as e:
            print(f"❌ Error scraping {site['name']}: {e}")

    driver.quit()

    processed_df = clean_and_process_data(all_scraped_data)

    if not processed_df.empty:
        export_df = processed_df.drop(columns=['cleaned_tokens'])
        
        json_export = export_df.to_dict(orient='records')
        with open("CS_Dataset_Phase2.json", "w") as f:
            json.dump(json_export, f, indent=4)
            
        try:
            export_df.to_excel("CS_Dataset_Phase2.xlsx", index=False)
            print("\n✅ DATASET EXPANDED! Real Course Text successfully saved to CS_Dataset_Phase2.json and Excel.")
        except PermissionError:
            print("\n❌ CRITICAL ERROR: Please close your Excel file and run again.")
            return
            
        perform_eda_and_visualize(processed_df)
        print("\n🚀 You are 100% ready for the Phase 2 AI Model ingestion!")

if __name__ == "__main__":
    main()