import time
import json
import re
import urllib.robotparser
from urllib.parse import urlparse
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

# Initial NLTK Setup
print("Downloading NLTK Data...")
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt_tab', quiet=True)

def check_robots_txt(url, user_agent="*"):
    """Strict Robots.txt compliance check."""
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    robots_url = f"{base_url}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        is_allowed = rp.can_fetch(user_agent, url)
        status = "🟢 ALLOWED" if is_allowed else "🔴 BLOCKED"
        print(f"[{status}] Robots.txt check for: {base_url}")
        return is_allowed
    except Exception:
        print(f"[🟡 WARNING] Could not read robots.txt for {base_url}. Assuming allowed.")
        return True

def setup_browser():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=chrome_options)

def clean_and_process_data(raw_data):
    """Applies NLTK pipeline and handles missing/noisy data."""
    print("\nStarting Data Processing Pipeline...")
    df = pd.DataFrame(raw_data)
    if df.empty:
        print("Dataframe is empty! No data was scraped.")
        return df

    initial_count = len(df)
    df = df.dropna(subset=['title'])
    df = df.drop_duplicates(subset=['title'])
    print(f"Data Quality Check: Removed {initial_count - len(df)} duplicates/bad rows.")
    
    stop_words = set(stopwords.words('english'))
    stop_words.update(['course', 'introduction', 'part', 'learning', 'fundamentals', 'science', 'computer'])
    
    def apply_nltk_pipeline(text):
        if not isinstance(text, str): return ""
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text) 
        tokens = word_tokenize(text) 
        return [word for word in tokens if word not in stop_words]

    df['cleaned_tokens'] = df['title'].apply(apply_nltk_pipeline)
    df['indexed_string'] = df['cleaned_tokens'].apply(lambda x: " ".join(x))
    return df

def perform_eda_and_visualize(df):
    """Generates keyword frequencies and platform distribution charts."""
    print("\nGenerating EDA & Visualizations...")
    if df.empty: return

    # 1. Keyword Frequency Analysis
    all_words = [word for tokens in df['cleaned_tokens'] for word in tokens]
    word_freq = Counter(all_words)
    top_10_words = word_freq.most_common(10)
    
    plt.figure(figsize=(10, 6))
    if top_10_words:
        words, counts = zip(*top_10_words)
        sns.barplot(x=list(counts), y=list(words), hue=list(words), palette='viridis', legend=False)
        plt.title('Top 10 Most Frequent Tech Keywords')
        plt.xlabel('Frequency')
        plt.ylabel('Keyword')
        plt.tight_layout()
        plt.savefig('keyword_frequency.png')

    # 2. Courses by Platform
    plt.figure(figsize=(8, 8))
    platform_counts = df['provider'].value_counts()
    if not platform_counts.empty:
        platform_counts.plot.pie(autopct='%1.1f%%', cmap='Pastel1')
        plt.title('Course Distribution by Platform')
        plt.ylabel('')
        plt.savefig('platform_distribution.png')
    
    print("✅ Visualizations saved as 'keyword_frequency.png' and 'platform_distribution.png'.")

def main():
    # 1. DEFINE TARGETS
    targets = [
        {"name": "CourseTalk", "url": "https://coursetalk.tumblr.com/"},
        {"name": "Cybrary", "url": "https://www.cybrary.it/catalog/"},
        {"name": "MIT OpenCourseWare (Python)", "url": "https://ocw.mit.edu/search/?q=python"},
        {"name": "MIT OpenCourseWare (AI)", "url": "https://ocw.mit.edu/search/?q=artificial+intelligence"},
        {"name": "MIT OpenCourseWare (Data)", "url": "https://ocw.mit.edu/search/?q=data+science"},
        {"name": "Khan Academy", "url": "https://www.khanacademy.org/computing/computer-programming"},
        {"name": "MaharaTech", "url": "https://maharatech.gov.eg/course/index.php"},
        {"name": "SECC", "url": "https://secc.org.eg/English/Pages/course-catalogue.aspx"}
    ]

    all_scraped_data = []
    driver = setup_browser()

    for site in targets:
        print(f"\n{'-'*40}\nInitiating sequence for: {site['name']}")
        
        if not check_robots_txt(site['url']):
            print(f"Skipping {site['name']} to strictly follow robots.txt guidelines.")
            continue
            
        try:
            driver.get(site['url'])
            time.sleep(6) 
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            courses_found = 0

            # PARSING
            if "MIT" in site['name']:
                for card in soup.find_all('article'):
                    title_tag = card.find('div', class_='course-title')
                    if title_tag:
                        all_scraped_data.append({"provider": "MIT OpenCourseWare", "title": title_tag.text.strip(), "url": site['url']})
                        courses_found += 1
            
            elif site['name'] == "MaharaTech":
                for card in soup.find_all('div', class_='coursename'):
                    all_scraped_data.append({"provider": site['name'], "title": card.text.strip(), "url": site['url']})
                    courses_found += 1
                    
            elif site['name'] == "Khan Academy":
                for card in soup.find_all('h2', class_='_14hvpoy'): 
                    all_scraped_data.append({"provider": site['name'], "title": card.text.strip(), "url": site['url']})
                    courses_found += 1

            else:
                headers = soup.find_all(['h2', 'h3'])
                for header in headers[:20]: 
                    title = header.text.strip()
                    if len(title) > 5: 
                        all_scraped_data.append({"provider": site['name'], "title": title, "url": site['url']})
                        courses_found += 1
            
            print(f"✅ Extracted {courses_found} records from {site['name']}")

        except Exception as e:
            print(f"❌ Error scraping {site['name']}: {e}")

    driver.quit()

    # DATA PIPELINE
    processed_df = clean_and_process_data(all_scraped_data)

    if not processed_df.empty:
        export_df = processed_df.drop(columns=['cleaned_tokens'])
        
        json_export = export_df.to_dict(orient='records')
        with open("CS_Dataset_Phase1.json", "w") as f:
            json.dump(json_export, f, indent=4)
            
        try:
            export_df.to_excel("CS_Dataset_Phase1.xlsx", index=False)
            print("\n✅ Data successfully saved to JSON and Excel.")
        except PermissionError:
            print("\n❌ CRITICAL ERROR: The file 'CS_Dataset_Phase1.xlsx' is currently open in Excel.")
            print("❌ CLOSE EXCEL AND RUN AGAIN.")
            return
            
        # Visualization
        perform_eda_and_visualize(processed_df)

if __name__ == "__main__":
    main()