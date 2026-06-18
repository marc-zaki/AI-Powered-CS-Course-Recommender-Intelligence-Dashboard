import requests
import hashlib
from datetime import timedelta
import random
import re
import json
import ast
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import google.generativeai as genai
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity

import ai_core

router = APIRouter()

@router.get('/api/stats')

async def api_stats(request: Request):
    # Make stats public so it can be displayed on the EDA Dashboard

    if ai_core.df is None or len(ai_core.df) == 0:
        return JSONResponse({"success": False, "error": "Database is not loaded."}, status_code=500)
        
    try:
        filter_diff = request.query_params.get('difficulty', 'all').lower()
        
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
            
        diff_series = ai_core.df.apply(classify_row, axis=1)
        
        filtered_df = ai_core.df.copy()
        filtered_df['calculated_difficulty'] = diff_series
        if filter_diff != 'all':
            filtered_df = filtered_df[filtered_df['calculated_difficulty'].str.lower() == filter_diff]
            if len(filtered_df) == 0:
                filtered_df = ai_core.df.copy()  # fallback if empty
        
        # 1. Total metric values
        total_courses = int(len(filtered_df))
        avg_rating = round(float(filtered_df['stars'].mean()), 2) if 'stars' in filtered_df.columns else 4.2
        total_reviews = int(filtered_df['ratings_count'].sum()) if 'ratings_count' in filtered_df.columns else 0
        
        # 2. Provider Distribution
        provider_counts = filtered_df['provider'].value_counts().to_dict()
        difficulty_share = filtered_df['calculated_difficulty'].value_counts().to_dict()
        
        # 4. Keyword Frequency Statistics (Information Retrieval statistics!)
        keywords = ["python", "javascript", "data science", "machine learning", "algorithms", "web development", "databases", "security", "cloud", "artificial intelligence", "c++", "software"]
        keyword_frequencies = {}
        for kw in keywords:
            desc_col = 'content_text' if 'content_text' in filtered_df.columns else 'description'
            keyword_frequencies[kw] = int(filtered_df[desc_col].str.contains(kw, case=False, na=False).sum())
            
        top_topic = max(keyword_frequencies, key=keyword_frequencies.get).title() if keyword_frequencies else "Software"
            
        # 5. Rating Histogram Bins
        stars = filtered_df['stars'].fillna(0)
        ratings_bins = {
            "4.5 - 5.0": int((stars >= 4.5).sum()),
            "4.0 - 4.5": int(((stars >= 4.0) & (stars < 4.5)).sum()),
            "3.5 - 4.0": int(((stars >= 3.5) & (stars < 4.0)).sum()),
            "Under 3.5": int((stars < 3.5).sum())
        }
        
        return JSONResponse({
            "success": True,
            "metrics": {
                "total_courses": total_courses,
                "avg_rating": avg_rating,
                "total_reviews": total_reviews,
                "top_topic": top_topic
            },
            "provider_distribution": provider_counts,
            "difficulty_distribution": difficulty_share,
            "keyword_frequencies": keyword_frequencies,
            "ratings_distribution": ratings_bins
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get('/api/random_course')
async def api_random_course(request: Request):
    try:
        # Dynamic loader failover
        if ai_core.df is None or ai_core.df.empty:
            for db_file in ["datasets/CS_Dataset_Phase2.json", "CS_Dataset_Phase2.json"]:
                if os.path.exists(db_file):
                    df = pd.read_json(db_file)
                    print(f"Dynamically loaded database from {db_file}")
                    break
        
        if df is not None and not ai_core.df.empty:
            random_row = ai_core.df.sample(n=1).iloc[0]
            
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
            return JSONResponse({"success": True, "course": course_data})
        return JSONResponse({"success": False, "error": "Database not initialized"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get('/graph_data')
async def graph_data(request: Request):
    if ai_core.df is None or len(ai_core.df) == 0:
        return JSONResponse({"nodes": [], "links": []})
    # Select the top 25 courses for each unique provider to ensure fair representation in the network
    sample_df = ai_core.df.copy()
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
    sample_vec = ai_core.vectorizer.transform(sample_profiles)
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
                
    return JSONResponse({"nodes": nodes, "links": links})
def generate_local_fallback_path(user_goal, matched_courses):
    """
    Generates a beautifully structured, highly customized, and comprehensive 6-week
    academic syllabus from the matched courses when Gemini API rate limits/quotas are exceeded.
    """
    html = []
    
    # 1. Graceful API notice banner
    html.append(
        '<div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); '
        'border-radius: 10px; padding: 1.15rem; margin-bottom: 2rem; display: flex; align-items: center; '
        'gap: 0.85rem; color: #F59E0B; font-size: 0.925rem; font-weight: 600; line-height: 1.55;">'
        '<span style="font-size: 1.25rem;"><i data-lucide="alert-triangle" style="width: 20px; height: 20px; display: inline-block;"></i></span>'
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
        html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c1.get("provider")}) — <i data-lucide="star" style="width: 14px; height: 14px; display: inline-block; fill: currentColor;"></i> {c1_stars:.1f} ({c1_reviews:,} ratings)</span>')
        html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c1.get("content_text")[:200]}...</span>')
        if c1_url != '#':
            html.append(f'<a class="path-link" href="{c1_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;"><i data-lucide="book-open" style="width: 14px; height: 14px; display: inline-block;"></i> View Syllabus & Lectures →</a>')
        html.append('</li>')
        
        # Course 2 (if present)
        if c2:
            c2_stars = float(c2.get('stars', 4.5))
            c2_reviews = int(c2.get('ratings_count', 1500))
            c2_url = c2.get('url', '#')
            c2_redirect = f"/verify_link?url={urllib.parse.quote(c2_url)}&title={urllib.parse.quote(c2.get('title'))}&provider={urllib.parse.quote(c2.get('provider'))}" if c2_url != '#' else '#'
            
            html.append(f'<li style="margin-bottom: 0.75rem; margin-top: 1rem; line-height: 1.6;">')
            html.append(f'<strong style="color: var(--text-main); font-weight: 700;">{c2.get("title")}</strong> ')
            html.append(f'<span style="color: var(--text-muted); font-size: 0.85rem;">({c2.get("provider")}) — <i data-lucide="star" style="width: 14px; height: 14px; display: inline-block; fill: currentColor;"></i> {c2_stars:.1f} ({c2_reviews:,} ratings)</span>')
            html.append(f'<br><span style="color: var(--text-muted); font-size: 0.9rem; display:block; margin: 0.35rem 0; line-height: 1.5;">{c2.get("content_text")[:200]}...</span>')
            if c2_url != '#':
                html.append(f'<a class="path-link" href="{c2_redirect}" target="_blank" style="font-size: 0.875rem; color: var(--secondary); text-decoration: none; border-bottom: 1px dashed rgba(187, 225, 250, 0.4); font-weight: 600;"><i data-lucide="book-open" style="width: 14px; height: 14px; display: inline-block;"></i> View Syllabus & Lectures →</a>')
            html.append('</li>')
            
        html.append('</ul>')
        
        # Feature 5: Bespoke Recommended Practical Exercise with Interview Question!
        interview_q = "Explain the core technical principles you learned this week."
        if ai_core.interview_ir_engine is not None:
            try:
                ir_res = ai_core.interview_ir_engine.search(c1.get("title", ""), top_k=1, method='hybrid')
                if ir_res:
                    interview_q = ir_res[0]['question']
            except Exception:
                pass

        html.append(f'<div style="background: rgba(50, 130, 184, 0.08); border-left: 3px solid var(--secondary); padding: 0.95rem 1.25rem; border-radius: 0 8px 8px 0; margin-top: 1.25rem;">')
        html.append(f'<strong style="color: var(--text-main); font-size: 0.9rem; display: block; margin-bottom: 0.35rem;"><i data-lucide="tool" style="width: 14px; height: 14px; display: inline-block;"></i> Weekly Practical Exercise & Mock Interview:</strong>')
        html.append(f'<span style="color: var(--text-muted); font-size: 0.875rem; line-height: 1.55; display: block; margin-bottom: 0.5rem;">Design and construct a modular software module incorporating the core competencies introduced this week. Focus on writing clean object-oriented logic, defining API schemas, and implementing comprehensive unit tests to validate boundaries on <strong>"{c1.get("title")}"</strong>.</span>')
        html.append(f'<span style="color: var(--secondary); font-size: 0.85rem; font-weight: 600; display: block; align-items: center; gap: 0.35rem;"><i data-lucide="lightbulb" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> End-of-Week Interview Prep: "{interview_q}"</span>')
        html.append('</div>')
        
        html.append('</div>')
        
    return "".join(html)

@router.post('/generate_path')
async def generate_path(request: Request):
    if ai_core.df is None:
        return JSONResponse({"success": False, "error": "Dataset is not loaded."}, status_code=500)

    data = await request.json() or {}
    user_goal = data.get('goal', '').strip()
    if not user_goal:
        return JSONResponse({"success": False, "error": "Please enter a learning goal or career target."}, status_code=400)

    # Cache check
    clean_goal = re.sub(r'\s+', ' ', user_goal.lower().strip())
    cache_key = hashlib.md5(clean_goal.encode('utf-8')).hexdigest()
    db = request.app.state.mongo_db
    if db is not None:
        try:
            cached_plan = db.study_plans_cache.find_one({"key": cache_key})
            if cached_plan:
                created_at = cached_plan.get("created_at")
                if created_at and (datetime.utcnow() - created_at < timedelta(days=30)):
                    print(f"Cache HIT for study plan goal: {user_goal}")
                    return JSONResponse({
                        "success": True,
                        "goal": user_goal,
                        "path_html": cached_plan.get("path_html"),
                        "engine": "cache"
                    })
        except Exception as e:
            print(f"Cache check error in generate_path: {e}")

    # 1. Use TF-IDF to retrieve top 12 relevant courses
    query_vector = ai_core.vectorizer.transform([user_goal.lower()])
    search_df = ai_core.df.copy()
    search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
    matched_courses = search_df.sort_values(by='match_score', ascending=False).head(12).to_dict('records')

    if not matched_courses:
        return JSONResponse({"success": False, "error": "No related courses found in our database to build a path."}, status_code=404)

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
        "in the bullet point list in parentheses. Example: 'Course Title (Udemy) - <i data-lucide=\"star\" style=\"width:12px;height:12px;display:inline-block;vertical-align:-1px;fill:currentColor;color:#FBBF24;\"></i> 4.7 (15,230 ratings)'. "
        "Ensure you pull the exact 'stars' and 'ratings_count' values provided in the data.\n"
        "6. CRITICAL (Feature 5): In the practical exercise section for each week, include exactly ONE mock interview question from the provided list of 'Relevant Mock Interview Questions'. You MUST wrap both the practical exercise and the mock interview question together in a visually distinct, beautifully styled HTML block like this: `<div style=\"background: rgba(50, 130, 184, 0.08); border-left: 3px solid var(--secondary); padding: 0.95rem 1.25rem; border-radius: 0 8px 8px 0; margin-top: 1.25rem;\"><strong style=\"color: var(--text-main); font-size: 0.9rem; display: block; margin-bottom: 0.35rem;\"><i data-lucide=\"tool\" style=\"width: 14px; height: 14px; display: inline-block;\"></i> Weekly Practical Exercise & Mock Interview:</strong><span style=\"color: var(--text-muted); font-size: 0.875rem; line-height: 1.55; display: block; margin-bottom: 0.5rem;\">[Insert practical exercise here]</span><span style=\"color: var(--secondary); font-size: 0.85rem; font-weight: 600; display: block;\"><i data-lucide=\"lightbulb\" style=\"width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:4px;\"></i> End-of-Week Interview Prep: \"[Insert Interview Question Here]\"</span></div>`\n"
        "7. Start directly with the syllabus layout. Do not include introductory conversational fluff or markdown code blocks like ```html."
    )

    interview_context = []
    if ai_core.interview_ir_engine is not None:
        try:
            ir_res = ai_core.interview_ir_engine.search(user_goal, top_k=5, method='hybrid')
            interview_context = [r['question'] for r in ir_res]
        except Exception:
            pass

    user_prompt = f"""
    Student Goal: "{user_goal}"
    
    Available Courses in Database (with Ratings):
    {json.dumps(courses_context, indent=2)}
    
    Relevant Mock Interview Questions from Database:
    {json.dumps(interview_context, indent=2)}
    
    Please build a premium week-by-week curriculum using these courses and injecting one relevant mock interview question per week.
    """

    path_html = None
    engine = None
    fallback = False

    # ── Multi-Tier Study Plan Generator ──────────────────────────────
    # Tier 1: OpenRouter API
    import os
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if OPENROUTER_API_KEY:
        try:
            print("Querying OpenRouter API for study plan...")
            openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://cs-recommender.com",
                "X-Title": "MASARI",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
            }
            res = requests.post(openrouter_url, json=payload, headers=headers, timeout=12.0)
            if res.status_code == 200:
                res_data = res.json()
                path_html = res_data["choices"][0]["message"]["content"].strip()
                path_html = re.sub(r"^```html\n", "", path_html)
                path_html = re.sub(r"\n```$", "", path_html)
                engine = "openrouter"
                print("Successfully generated study plan using OpenRouter API!")
            else:
                print(f"OpenRouter API returned error status {res.status_code}. Routing to Tier 2 (Gemini)...")
        except Exception as openrouter_err:
            print(f"OpenRouter Cloud connection error: {openrouter_err}. Routing to Tier 2 (Gemini)...")

    # Tier 2: Gemini Cloud API (gemini-2.5-flash)
    if not path_html and GEMINI_API_KEY:
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
            engine = "gemini"
            print("Successfully generated study plan using Gemini Cloud API!")
        except Exception as gemini_err:
            print(f"Gemini API returned error: {gemini_err}. Routing to Tier 3 (Local VSM Academic Planner)...")

    # Tier 3: Local VSM Academic Planner fallback
    if not path_html:
        try:
            print("Routing to local high-fidelity VSM Academic Planner fallback...")
            path_html = generate_local_fallback_path(user_goal, matched_courses)
            engine = "local"
            fallback = True
        except Exception as fallback_err:
            return JSONResponse({"success": False, "error": f"Failed to build a path: {fallback_err}"}, status_code=500)

    # Write to cache
    if db is not None and path_html:
        try:
            db.study_plans_cache.update_one(
                {"key": cache_key},
                {"$set": {
                    "key": cache_key,
                    "path_html": path_html,
                    "created_at": datetime.utcnow()
                }},
                upsert=True
            )
            print(f"Cached generated study plan for: {user_goal}")
        except Exception as e:
            print(f"Cache write error in generate_path: {e}")

    return JSONResponse({
        "success": True,
        "goal": user_goal,
        "path_html": path_html,
        "engine": engine,
        "fallback": fallback
    })

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
        db = request.app.state.mongo_db
        user = db.users.find_one({"_id": session['user_id']})
        if not user or (user.get('role') != 'admin' and not check_is_super_admin(user)):
            flash("Admin access required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


import uuid
from datetime import datetime

@router.post('/api/save_path')
async def save_path(request: Request):
    from routers.auth import get_current_user
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json() or {}
    goal = data.get('goal', '').strip()
    path_html = data.get('path_html', '').strip()
    
    if not goal or not path_html:
        return JSONResponse({"success": False, "error": "Goal and path HTML are required"}, status_code=400)
        
    db = request.app.state.mongo_db
    if db is None:
        return JSONResponse({"success": False, "error": "Database connection error"}, status_code=500)
        
    path_id = str(uuid.uuid4())
    new_path = {
        "id": path_id,
        "goal": goal,
        "path_html": path_html,
        "checked_items": [],
        "progress_percent": 0.0,
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Push into user's saved_paths array
    await db.users.update_one(
        {"_id": user['_id']},
        {"$push": {"saved_paths": new_path}}
    )
    
    return JSONResponse({"success": True, "path_id": path_id})

@router.post('/api/update_path_progress')
async def update_path_progress(request: Request):
    from routers.auth import get_current_user
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json() or {}
    path_id = data.get('path_id')
    checked_items = data.get('checked_items', [])
    total_items = data.get('total_items', 0)
    
    if not path_id:
        return JSONResponse({"success": False, "error": "Path ID is required"}, status_code=400)
        
    progress_percent = 0.0
    if total_items > 0:
        progress_percent = round((len(checked_items) / total_items) * 100, 1)
        
    db = request.app.state.mongo_db
    if db is None:
        return JSONResponse({"success": False, "error": "Database connection error"}, status_code=500)
        
    # Update matching array element using positional operator $
    await db.users.update_one(
        {"_id": user['_id'], "saved_paths.id": path_id},
        {"$set": {
            "saved_paths.$.checked_items": checked_items,
            "saved_paths.$.progress_percent": progress_percent
        }}
    )
    
    return JSONResponse({"success": True, "progress_percent": progress_percent})

@router.post('/api/delete_path')
async def delete_path(request: Request):
    from routers.auth import get_current_user
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json() or {}
    path_id = data.get('path_id')
    
    if not path_id:
        return JSONResponse({"success": False, "error": "Path ID is required"}, status_code=400)
        
    db = request.app.state.mongo_db
    if db is None:
        return JSONResponse({"success": False, "error": "Database connection error"}, status_code=500)
        
    await db.users.update_one(
        {"_id": user['_id']},
        {"$pull": {"saved_paths": {"id": path_id}}}
    )
    
    return JSONResponse({"success": True})

@router.post('/api/chat_assistant')
async def chat_assistant(request: Request):
    from routers.auth import get_current_user
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        
    data = await request.json() or {}
    messages = data.get('messages', [])
    if not messages:
        return JSONResponse({"success": False, "error": "No messages provided"}, status_code=400)
        
    system_prompt = (
        "You are an elite Computer Science Academic Advisor and tutor.\n"
        "Answer the student's questions concisely, helpfully, and professionally.\n"
        "Explain complex CS concepts clearly, suggest appropriate learning habits, "
        "and mention matching courses or track guidelines when appropriate.\n"
        "Formatting tip: Use standard Markdown formatting like **bold** or `code` snippets where appropriate."
    )
    
    import requests
    import os
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    
    # Tier 1: OpenRouter API
    import os
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if OPENROUTER_API_KEY:
        try:
            print("Querying OpenRouter API for chat assistant...")
            openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://cs-recommender.com",
                "X-Title": "MASARI",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": 0.5,
            }
            res = requests.post(openrouter_url, json=payload, headers=headers, timeout=10.0)
            if res.status_code == 200:
                res_data = res.json()
                reply = res_data["choices"][0]["message"]["content"].strip()
                return JSONResponse({"success": True, "response": reply, "engine": "openrouter"})
            else:
                print(f"OpenRouter API returned status {res.status_code}. Routing to Tier 2 (Gemini)...")
        except Exception as e:
            print(f"OpenRouter Cloud connection error: {e}. Routing to Tier 2 (Gemini)...")
            
    # Tier 2: Gemini Cloud API
    if GEMINI_API_KEY:
        try:
            print("Querying Gemini Cloud API for chat assistant...")
            # format conversation transcript
            transcript = ""
            for m in messages:
                role = "Student" if m['role'] == 'user' else "Advisor"
                transcript += f"{role}: {m['content']}\n"
            user_prompt = f"Dialogue history:\n{transcript}\nAdvisor:"
            
            import google.generativeai as genai
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=system_prompt
            )
            response = model.generate_content(user_prompt)
            reply = response.text.strip()
            return JSONResponse({"success": True, "response": reply, "engine": "gemini"})
        except Exception as e:
            print(f"Gemini API returned error: {e}. Routing to Tier 3...")
            
    # Tier 3: Static Fallback
    fallback_response = (
        "Hello! I am currently running in offline mode. Here are a few general CS study tips:\n"
        "1. **Practice coding daily**: Sites like LeetCode or building small personal projects help cement syntax.\n"
        "2. **Optimize your learning path**: Complete your saved plans week-by-week.\n"
        "3. **Take assessments**: Try the Skill Assessment quiz under your profile page to rank up!"
    )
    return JSONResponse({"success": True, "response": fallback_response, "engine": "static"})
