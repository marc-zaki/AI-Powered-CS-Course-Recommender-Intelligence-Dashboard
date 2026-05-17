import pandas as pd
import json
import os
import re

# Comprehensive list of Computer Science and Programming keywords
CS_KEYWORDS = [
    r"\bpython\b", r"\bprogramming\b", r"\bcode\b", r"\bcoding\b", r"\bsoftware\b", 
    r"\bdeveloper\b", r"\bjava\b", r"\bjavascript\b", r"\bc\+\+\b", r"\bc#\b", r"\bhtml\b", 
    r"\bcss\b", r"\breact\b", r"\bnode\b", r"\bweb dev\b", r"\bweb development\b", 
    r"\bmachine learning\b", r"\bartificial intelligence\b", r"\bdata science\b", 
    r"\bdatabase\b", r"\bsql\b", r"\bcybersecurity\b", r"\bcyber security\b", 
    r"\bnetwork\b", r"\balgorithm\b", r"\bdata structures\b", r"\bcloud\b", r"\baws\b", 
    r"\bgit\b", r"\blinux\b", r"\bdevops\b", r"\bdocker\b", r"\bkubernetes\b", 
    r"\bflutter\b", r"\bandroid\b", r"\bios\b", r"\bswift\b", r"\bkotlin\b", 
    r"\btypescript\b", r"\bruby\b", r"\bphp\b", r"\bgo\blang\b", r"\bgolang\b", 
    r"\brust\b", r"\bcompiler\b", r"\boperating system\b", r"\bcomputer science\b",
    r"\bfront\b-?end\b", r"\bback\b-?end\b", r"\bfull\b-?stack\b", r"\bdeep learning\b",
    r"\bneural network\b", r"\bdata analytics\b", r"\bux/ui\b", r"\bagile\b"
]

def is_cs_related(title, description):
    """
    Checks if a course is CS/programming related by scanning title and description.
    """
    text_to_scan = f"{title} {description}".lower()
    for kw in CS_KEYWORDS:
        if re.search(kw, text_to_scan):
            return True
    return False

def import_csv(file_path, provider_name, title_col, desc_col, url_col, default_url_prefix=""):
    """
    Parses an external CSV, strictly filters for CS-related courses, and merges them.
    """
    db_path = "CS_Dataset_Phase2.json"
    xlsx_path = "CS_Dataset_Phase2.xlsx"
    
    if not os.path.exists(file_path):
        print(f"Error: External file '{file_path}' not found.")
        return
        
    print(f"Reading '{file_path}'...")
    try:
        ext_df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return
        
    print(f"Found {len(ext_df)} records. Filtering strictly for Computer Science...")
    
    new_courses = []
    skipped_count = 0
    
    for idx, row in ext_df.iterrows():
        title = str(row.get(title_col, '')).strip()
        desc = str(row.get(desc_col, '')).strip()
        url = str(row.get(url_col, '')).strip()
        
        # Validation
        if not title or title.lower() == 'nan':
            continue
        if not desc or desc.lower() == 'nan':
            desc = "No description provided."
        if not url or url.lower() == 'nan':
            url = default_url_prefix
            
        # Check relevance
        if not is_cs_related(title, desc):
            skipped_count += 1
            continue
            
        # Extract stars and rating count if present in the CSV
        stars = 0.0
        ratings_count = 0

        # Try to find star rating (value from 1 to 5)
        if 'Stars' in ext_df.columns and pd.notnull(row.get('Stars')):
            try:
                stars = float(row.get('Stars'))
            except:
                pass
        if (stars == 0.0 or stars is None) and 'Rating' in ext_df.columns and pd.notnull(row.get('Rating')):
            val = str(row.get('Rating')).strip()
            if 'stars' in val.lower():
                try:
                    stars = float(val.lower().replace('stars', '').strip())
                except:
                    pass
            else:
                try:
                    f_val = float(val)
                    if 0.0 <= f_val <= 5.0:
                        stars = f_val
                except:
                    pass

        # Try to find ratings count
        possible_rating_count_cols = ['Number of ratings', 'Number of Reviews', 'Rating', 'Number of viewers']
        for col in possible_rating_count_cols:
            if col in ext_df.columns and pd.notnull(row.get(col)):
                val = str(row.get(col)).strip()
                if col == 'Rating' and 'stars' in val.lower():
                    continue
                val_clean = val.replace(',', '').replace(' ', '').replace('+', '').strip()
                try:
                    ratings_count = int(float(val_clean))
                    break
                except:
                    pass

        new_courses.append({
            "provider": provider_name,
            "title": title,
            "content_text": desc,
            "url": url,
            "raw_reviews": [],
            "review_summary": "",
            "stars": stars,
            "ratings_count": ratings_count
        })
        
    print(f"Filter Complete: Kept {len(new_courses)} CS courses. Skipped {skipped_count} non-CS courses.")
    
    if not new_courses:
        print("No matching CS courses found. Database was not updated.")
        return

    # Load current database
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                current_data = json.load(f)
            print(f"Loaded existing database with {len(current_data)} courses.")
        except Exception as e:
            print(f"Could not read existing database, starting fresh: {e}")
            current_data = []
    else:
        current_data = []
        
    # Merge and eliminate duplicates by title
    combined = current_data + new_courses
    
    seen_titles = set()
    deduped = []
    for course in combined:
        title_lower = course['title'].lower().strip()
        if title_lower not in seen_titles:
            seen_titles.add(title_lower)
            deduped.append(course)
            
    print(f"Total unique CS courses in database after merging: {len(deduped)}")
    
    # Save back
    try:
        with open(db_path, 'w') as f:
            json.dump(deduped, f, indent=4)
        print(f"Saved merged database to '{db_path}'")
        
        pd.DataFrame(deduped).to_excel(xlsx_path, index=False)
        print(f"Saved Excel backup to '{xlsx_path}'")
        
        print("\n🎉 Success! Restart your Flask server to load the new courses.")
    except Exception as e:
        print(f"Failed to save database: {e}")

if __name__ == "__main__":
    print("--- Kaggle / External CS CSV Importer Utility ---")
    print("This utility will automatically FILTER OUT non-CS courses (e.g. music, finance, cooking).")
    
    # Import Udemy Tech CSV if present
    udemy_file = 'udemy_tech.csv'
    if os.path.exists(udemy_file):
        print(f"\nDetected '{udemy_file}' in workspace! Starting auto-import...")
        import_csv(
            file_path=udemy_file,
            provider_name='Udemy',
            title_col='Title',
            desc_col='Summary',
            url_col='Link'
        )
    else:
        print(f"\nCould not find '{udemy_file}' in the root directory.")
        
    # Import Coursera English CSV if present
    coursera_file = 'courses_en.csv'
    if os.path.exists(coursera_file):
        print(f"\nDetected '{coursera_file}' in workspace! Starting auto-import...")
        import_csv(
            file_path=coursera_file,
            provider_name='Coursera',
            title_col='name',
            desc_col='content',
            url_col='url'
        )
    else:
        print(f"\nCould not find '{coursera_file}' in the root directory.")

    # Import EdX CSV if present
    edx_file = 'EdX.csv'
    if os.path.exists(edx_file):
        print(f"\nDetected '{edx_file}' in workspace! Starting auto-import...")
        import_csv(
            file_path=edx_file,
            provider_name='EdX',
            title_col='Name',
            desc_col='Course Description',
            url_col='Link'
        )
    else:
        print(f"\nCould not find '{edx_file}' in the root directory.")

    # Import Online Courses CSV if present
    online_file = 'Online_Courses.csv'
    if os.path.exists(online_file):
        print(f"\nDetected '{online_file}' in workspace! Starting auto-import...")
        import_csv(
            file_path=online_file,
            provider_name='Online Courses',
            title_col='Title',
            desc_col='Short Intro',
            url_col='URL'
        )
    else:
        print(f"\nCould not find '{online_file}' in the root directory.")
