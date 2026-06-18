from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from core_templates import templates
from typing import Optional
import urllib.parse
from datetime import datetime, timedelta
import math
import concurrent.futures

from ai_core import (
    df, vectorizer, tfidf_matrix, global_featured_courses,
    interview_ir_engine
)
from sklearn.metrics.pairwise import cosine_similarity
import httpx

# In FastAPI, we usually share a templates instance or import it from main
# But to avoid circular imports, we can pass it, or just create it here since globals are bound per env
from flash import get_flashed_messages
templates.env.globals["get_flashed_messages"] = get_flashed_messages

router = APIRouter()

# Helper to get the database asynchronously
async def get_db_async(request: Request):
    return request.app.state.mongo_db if hasattr(request.app.state, 'mongo_db') else None

async def get_current_user(request: Request):
    user_id = request.session.get('user_id')
    if user_id:
        db = request.app.state.mongo_db
        if db is not None:
            # Note: in real implementation, you might need to use bson.ObjectId if _id is an ObjectId
            return await db.users.find_one({"_id": user_id})
    return None

@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name="privacy.html", context= {"request": request, "current_user": user})

@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name="terms.html", context= {"request": request, "current_user": user})

@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name="pricing.html", context= {"request": request, "current_user": user})

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    import ai_core
    if ai_core.df is None:
        return HTMLResponse("Error: Dataset not loaded. Please ensure datasets/CS_Dataset_Phase2.json exists.", status_code=500)

    user = await get_current_user(request)
    is_personalized = False
    
    if user:
        taken_courses = user.get('taken_courses', [])
        query_terms = [user.get('track', ''), user.get('career_goals', '')]
        query = " ".join([t for t in query_terms if t]).strip()
        
        if len(query) > 5:
            query_vector = ai_core.vectorizer.transform([query.lower()])
            search_df = ai_core.df.copy()
            search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
            search_df = search_df[~search_df['url'].isin(taken_courses)]
            featured = search_df.sort_values(by=['match_score', 'stars'], ascending=[False, False]).head(12)
            is_personalized = True
        else:
            featured = ai_core.global_featured_courses[~ai_core.global_featured_courses['url'].isin(taken_courses)].head(12)
    else:
        featured = ai_core.global_featured_courses

    courses = featured.to_dict('records')
    return templates.TemplateResponse(request=request, name='index.html', context= {"request": request, "courses": courses, "query": "", "is_search": False, "show_all": False, "total_courses": len(ai_core.df), "page": 1, "total_pages": 1, "is_personalized": is_personalized, "current_user": user})

@router.get("/all", response_class=HTMLResponse)
async def all_courses(request: Request, page: int = Query(1)):
    import ai_core
    if ai_core.df is None:
        return RedirectResponse(url="/")

    per_page = 30
    total_pages = max(1, math.ceil(len(ai_core.df) / per_page))
    page = max(1, min(page, total_pages))
    
    sorted_df = ai_core.df.sort_values(by='stars', ascending=False)
    start = (page - 1) * per_page
    end = start + per_page
    courses = sorted_df.iloc[start:end].to_dict('records')
    
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name='index.html', context= {"request": request, "courses": courses, "query": "", "is_search": False, "show_all": True, "total_courses": len(ai_core.df), "page": page, "total_pages": total_pages, "current_user": user})

@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(''),
    provider: str = Query(''),
    difficulty: str = Query(''),
    rating: str = Query('')
):
    import ai_core
    if ai_core.df is None:
        return RedirectResponse(url="/")

    query = q.strip()
    if not query:
        return RedirectResponse(url="/")

    provider_clean = provider.strip().lower()
    diff_clean = difficulty.strip().lower()
    rating_val = rating.strip()

    def run_course_search(q_str):
        try:
            query_vector = ai_core.vectorizer.transform([q_str.lower()])
            search_df = ai_core.df.copy()
            search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
            
            if provider_clean:
                search_df = search_df[search_df['provider'].str.lower().str.contains(provider_clean, na=False)]
            if diff_clean:
                search_df = search_df[search_df['difficulty'].str.lower() == diff_clean]
            if rating_val:
                try:
                    search_df = search_df[search_df['stars'] >= float(rating_val)]
                except ValueError:
                    pass

            recs = search_df[search_df['match_score'] > 0.15].sort_values(by=['stars', 'match_score'], ascending=[False, False])
            
            if recs.empty:
                recs = search_df[search_df['match_score'] > 0.02].sort_values(by=['stars', 'match_score'], ascending=[False, False])
                
            return recs.to_dict('records')
        except Exception as e:
            print(f"Error in parallel course search: {e}")
            return []

    def run_interview_search(q_str):
        if not ai_core.interview_ir_engine:
            return []
        try:
            return ai_core.interview_ir_engine.search(q_str, top_k=5, method='hybrid')
        except Exception as e:
            print(f"Error in parallel interview search: {e}")
            return []

    # In FastAPI, we can use run_in_threadpool or just ThreadPoolExecutor
    from fastapi.concurrency import run_in_threadpool
    import asyncio
    
    courses, interview_results = await asyncio.gather(
        run_in_threadpool(run_course_search, query),
        run_in_threadpool(run_interview_search, query)
    )

    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name='index.html', context= {"request": request, "courses": courses, "interview_results": interview_results, "query": query, "is_search": True, "show_all": False, "total_courses": len(ai_core.df), "page": 1, "total_pages": 1, "current_user": user})

@router.get("/interview-prep", response_class=HTMLResponse)
async def interview_prep(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name='interview_analyzer.html', context= {"request": request, "current_user": user})

@router.get("/resume-optimizer", response_class=HTMLResponse)
async def resume_optimizer(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name='resume_optimizer.html', context= {"request": request, "current_user": user})

@router.get("/course-analyzer", response_class=HTMLResponse)
async def course_analyzer(request: Request):
    user = await get_current_user(request)
    return templates.TemplateResponse(request=request, name='course_analyzer.html', context= {"request": request, "current_user": user})
