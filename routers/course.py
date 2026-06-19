import os
import json
import hashlib
from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from sklearn.metrics.pairwise import cosine_similarity
import httpx
import google.generativeai as genai

router = APIRouter()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def extract_json_from_llm(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception as e:
        print(f"JSON parsing error: {e}")
        return {}

async def perform_course_analysis(course: dict, user_goals: str, request: Request):
    if not course or not course.get('title'):
        return None

    title = course.get('title', '')
    provider = course.get('provider', '')
    stars = course.get('stars', 0)
    ratings_count = course.get('ratings_count', 0)
    description = course.get('content_text', '')[:1200]
    review_summary = course.get('review_summary', '')
    raw_reviews = course.get('raw_reviews', [])[:5]

    profile_goals = ""
    db = request.app.state.mongo_db
    user_id = request.session.get('user_id')
    
    if user_id and db is not None:
        user = await db.users.find_one({"_id": user_id})
        if user:
            p_parts = []
            if user.get('track'): p_parts.append(user.get('track'))
            if user.get('career_goals'): p_parts.append(user.get('career_goals'))
            profile_goals = " ".join(p_parts).strip()

    if not user_goals and profile_goals:
        user_goals = profile_goals

    goals_context = f"\n\nLearner's goals: {user_goals}" if user_goals else ""
    reviews_text = ""
    if raw_reviews:
        reviews_text = "\nSample student reviews:\n" + "\n".join(f"- {r}" for r in raw_reviews[:5] if r)

    system_prompt = (
        "You are an expert CS education analyst. You have been given REAL data about an online course "
        "from a curated catalog. Analyze it critically and honestly. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"verdict\": \"yes\" | \"maybe\" | \"no\",\n"
        "  \"verdict_reason\": \"<one clear sentence summarizing your verdict>\",\n"
        "  \"scores\": {\n"
        "    \"content_depth\": <integer 0-100>,\n"
        "    \"provider_reputation\": <integer 0-100>,\n"
        "    \"career_relevance\": <integer 0-100>,\n"
        "    \"value_for_money\": <integer 0-100>\n"
        "  },\n"
        "  \"pros\": [\"<strength 1>\", \"<strength 2>\", \"<strength 3>\"],\n"
        "  \"cons\": [\"<weakness 1>\", \"<weakness 2>\", \"<weakness 3>\"],\n"
        "  \"summary\": \"<2-3 sentence balanced analysis of this specific course's value>\",\n"
        "  \"topic_keywords\": [\"<keyword1>\", \"<keyword2>\", \"<keyword3>\"]\n"
        "}\n"
    )

    user_prompt = (
        f"Course Title: {title}\n"
        f"Provider / Platform: {provider}\n"
        f"Star Rating: {stars} / 5.0\n"
        f"Number of Ratings: {ratings_count:,}\n"
        f"Description: {description}\n"
        f"Review Summary: {review_summary}"
        f"{reviews_text}"
        f"{goals_context}\n\n"
        "Evaluate this course and return the JSON analysis."
    )

    cache_key = f"{course.get('url', '')}_{hashlib.md5(user_goals.encode('utf-8')).hexdigest()}"
    cached_result = None

    if db is not None:
        try:
            cached_doc = await db.course_analyses.find_one({"cache_key": cache_key})
            if cached_doc:
                created_at = cached_doc.get("created_at")
                if created_at and (datetime.utcnow() - created_at < timedelta(days=7)):
                    cached_result = cached_doc.get("analysis_result")
                    print(f"Cache HIT for course analysis: {title}")
        except Exception as e:
            print(f"Cache read error: {e}")

    if cached_result:
        result = cached_result
    else:
        result = None

        if OPENROUTER_API_KEY:
            try:
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
                    "temperature": 0.25,
                    "max_tokens": 900,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient() as client:
                    res = await client.post(openrouter_url, json=payload, headers=headers, timeout=12.0)
                if res.status_code == 200:
                    result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"OpenRouter analyzer error: {e}")

        if not result and GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_prompt)
                response = await model.generate_content_async(user_prompt)
                result = extract_json_from_llm(response.text)
            except Exception as e:
                print(f"Gemini analyzer error: {e}")

        if not result or not isinstance(result, dict):
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                result = result[0]
            else:
                return None

        result.setdefault("verdict", "maybe")
        result.setdefault("scores", {"content_depth": 50, "provider_reputation": 50, "career_relevance": 50, "value_for_money": 50})
        result.setdefault("pros", [])
        result.setdefault("cons", [])
        result.setdefault("summary", "")
        result.setdefault("topic_keywords", [])

        if db is not None:
            try:
                await db.course_analyses.update_one(
                    {"cache_key": cache_key},
                    {"$set": {
                        "cache_key": cache_key,
                        "analysis_result": result,
                        "created_at": datetime.utcnow()
                    }},
                    upsert=True
                )
            except Exception as e:
                print(f"Cache write error: {e}")

    return result


@router.get("/api/course/quick_search")
async def api_course_quick_search(q: str = ""):
    import ai_core
    if ai_core.df is None:
        return JSONResponse({"courses": []})
        
    query = q.strip()
    if not query or len(query) < 2:
        return JSONResponse({"courses": []})
        
    try:
        query_vector = ai_core.vectorizer.transform([query.lower()])
        search_df = ai_core.df.copy()
        search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
        results = search_df[search_df['match_score'] > 0.01].sort_values(
            by=['match_score', 'stars'], ascending=[False, False]
        ).head(8)
        
        courses = []
        for _, row in results.iterrows():
            courses.append({
                "title": str(row.get("title", "")),
                "provider": str(row.get("provider", "")),
                "url": str(row.get("url", "#")),
                "stars": float(row.get("stars", 4.0)),
                "ratings_count": int(row.get("ratings_count", 0)),
                "content_text": str(row.get("content_text", ""))[:800],
                "review_summary": str(row.get("review_summary", "")),
                "raw_reviews": row.get("raw_reviews", []) if isinstance(row.get("raw_reviews"), list) else [],
            })
        return JSONResponse({"courses": courses})
    except Exception as e:
        print(f"Quick search error: {e}")
        return JSONResponse({"courses": []})


@router.post("/api/course/analyze")
async def api_course_analyze(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    course = data.get('course', {})
    user_goals = data.get('goals', '').strip()

    if not course or not course.get('title'):
        return JSONResponse({"error": "No course data provided"}, status_code=400)

    result = await perform_course_analysis(course, user_goals, request)
    if not result:
        return JSONResponse({"error": "AI model unavailable. Please try again in a moment."}, status_code=503)

    title = course.get('title', '')
    taken_courses = []
    user_id = request.session.get('user_id')
    db = request.app.state.mongo_db
    
    if user_id and db is not None:
        user = await db.users.find_one({"_id": user_id})
        if user:
            taken_courses = user.get('taken_courses', [])
            if not user_goals:
                p_parts = []
                if user.get('track'): p_parts.append(user.get('track'))
                if user.get('career_goals'): p_parts.append(user.get('career_goals'))
                user_goals = " ".join(p_parts).strip()

    alternatives = []
    goal_based = False
    import ai_core

    if (result.get("verdict") in ["no", "maybe"]) and user_goals and ai_core.df is not None:
        try:
            goal_vector = ai_core.vectorizer.transform([user_goals.lower()])
            search_df = ai_core.df.copy()
            search_df['match_score'] = cosine_similarity(goal_vector, ai_core.tfidf_matrix).flatten()
            search_df = search_df[search_df['title'] != title]
            if taken_courses:
                search_df = search_df[~search_df['url'].isin(taken_courses)]
                
            top_matches = search_df[search_df['match_score'] > 0.05].sort_values(
                by=['match_score', 'stars'], ascending=[False, False]
            ).head(4)
            
            for _, row in top_matches.iterrows():
                alternatives.append({
                    "title": row.get("title", ""),
                    "provider": row.get("provider", ""),
                    "url": row.get("url", "#"),
                    "stars": float(row.get("stars", 4.0))
                })
            if alternatives:
                goal_based = True
        except Exception as e:
            print(f"Goal recommendations error: {e}")

    if not alternatives and ai_core.df is not None and result.get("topic_keywords"):
        try:
            keyword_query = " ".join(result["topic_keywords"])
            query_vector = ai_core.vectorizer.transform([keyword_query.lower()])
            search_df = ai_core.df.copy()
            search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
            search_df = search_df[search_df['title'] != title]
            if taken_courses:
                search_df = search_df[~search_df['url'].isin(taken_courses)]
                
            top_alts = search_df[search_df['match_score'] > 0.05].sort_values(
                by=['stars', 'match_score'], ascending=[False, False]
            ).head(4)
            for _, row in top_alts.iterrows():
                alternatives.append({
                    "title": row.get("title", ""),
                    "provider": row.get("provider", ""),
                    "url": row.get("url", "#"),
                    "stars": float(row.get("stars", 4.0))
                })
        except Exception:
            pass

    result["alternatives"] = alternatives
    result["goal_based_recommendations"] = goal_based

    # Fetch relevant interview questions for the analyzed course topic
    interview_questions = []
    if ai_core.interview_ir_engine:
        search_query = " ".join(result.get("topic_keywords", [])) or title
        try:
            questions = ai_core.interview_ir_engine.search(search_query, top_k=3, method='hybrid')
            for q in questions:
                interview_questions.append({
                    "question": q.get("question", ""),
                    "answer": q.get("answer", "")
                })
        except Exception as e:
            print(f"Error fetching course interview questions: {e}")
    result["interview_questions"] = interview_questions

    return JSONResponse(result)


@router.post("/api/course/compare")
async def api_course_compare(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    course_a = data.get('course_a', {})
    course_b = data.get('course_b', {})
    user_goals = data.get('goals', '').strip()

    if not course_a or not course_a.get('title') or not course_b or not course_b.get('title'):
        return JSONResponse({"error": "Two courses must be provided for comparison."}, status_code=400)

    result_a, result_b = await asyncio.gather(
        perform_course_analysis(course_a, user_goals, request),
        perform_course_analysis(course_b, user_goals, request)
    )

    if not result_a or not result_b:
        return JSONResponse({"error": "AI model unavailable for comparison. Please try again."}, status_code=503)

    return JSONResponse({
        "course_a": result_a,
        "course_b": result_b
    })



@router.post("/api/toggle_taken")
async def toggle_taken(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
        
    try:
        data = await request.json()
    except:
        data = {}
        
    course_url = data.get('url')
    if not course_url:
        return JSONResponse({"success": False, "error": "No course URL provided"}, status_code=400)
        
    db = request.app.state.mongo_db
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
        
    taken = user.get('taken_courses', [])
    if course_url in taken:
        taken.remove(course_url)
        action = "removed"
    else:
        taken.append(course_url)
        action = "added"
        
    await db.users.update_one({"_id": user_id}, {"$set": {"taken_courses": taken}})
    return JSONResponse({"success": True, "action": action, "taken_courses": taken})

@router.post("/submit_course")
async def submit_course(
    request: Request,
    title: str = Form(None),
    provider: str = Form(None),
    url: str = Form(None),
    description: str = Form(None),
    rating: str = Form(None)
):
    user_id = request.session.get('user_id')
    if not user_id:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
        
    if not title or not provider or not url:
        return JSONResponse({"success": False, "error": "Missing required fields"}, status_code=400)
        
    import time
    db = request.app.state.mongo_db
    
    submitted_course = {
        "title": title,
        "provider": provider,
        "url": url,
        "content_text": description,
        "stars": float(rating) if rating else 5.0,
        "ratings_count": 1,
        "status": "pending",
        "submitted_by": user_id,
        "submitted_at": time.time()
    }
    
    await db.submitted_courses.insert_one(submitted_course)
    return JSONResponse({"success": True, "message": "Course submitted successfully and is pending admin approval!"})

import urllib.parse
import requests
from fastapi.responses import RedirectResponse

async def check_link_cached(request, url, title, provider):
    db = request.app.state.mongo_db
    fallback_url = url
    if provider.lower() == 'udemy':
        fallback_url = f"https://www.udemy.com/courses/search/?q={urllib.parse.quote(title)}"
    elif provider.lower() == 'coursera':
        fallback_url = f"https://www.coursera.org/search?query={urllib.parse.quote(title)}"
    elif provider.lower() == 'edx':
        fallback_url = f"https://www.edx.org/search?q={urllib.parse.quote(title)}"
        
    if db is not None:
        try:
            cached = await db.link_status.find_one({"url": url})
            if cached:
                created_at = cached.get("created_at")
                if created_at and (datetime.utcnow() - created_at < timedelta(days=30)):
                    return cached.get("valid", False), cached.get("fallback_url", fallback_url)
        except Exception as e:
            print(f"Link status cache check error: {e}")
            
    # Perform actual HTTP validation check
    valid = False
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        res = requests.head(url, headers=headers, timeout=1.5, allow_redirects=True)
        if res.status_code == 404 or res.status_code == 403:
            res = requests.get(url, headers=headers, timeout=1.5, allow_redirects=True)
        valid = (res.status_code != 404)
    except Exception:
        valid = False
        
    # Write result to cache
    if db is not None:
        try:
            await db.link_status.update_one(
                {"url": url},
                {"$set": {
                    "url": url,
                    "valid": valid,
                    "fallback_url": fallback_url,
                    "created_at": datetime.utcnow()
                }},
                upsert=True
            )
        except Exception as e:
            print(f"Link status cache save error: {e}")
            
    return valid, fallback_url

@router.get('/validate_link')
async def validate_link(request: Request):
    url = request.query_params.get('url', '').strip()
    title = request.query_params.get('title', '').strip()
    provider = request.query_params.get('provider', '').strip()
    
    if not url:
        return JSONResponse({"valid": False, "fallback_url": "/"})
    valid, fallback_url = await check_link_cached(request, url, title, provider)
    return JSONResponse({"valid": valid, "fallback_url": url if valid else fallback_url})

@router.get('/verify_link')
async def verify_link(request: Request):
    url = request.query_params.get('url', '').strip()
    title = request.query_params.get('title', '').strip()
    provider = request.query_params.get('provider', '').strip()
    
    if not url:
        return RedirectResponse(url='/')
        
    valid, fallback_url = await check_link_cached(request, url, title, provider)
    return RedirectResponse(url=url if valid else fallback_url)
