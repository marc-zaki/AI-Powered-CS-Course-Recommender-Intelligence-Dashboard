import os
import json
import tempfile
import asyncio
import base64
import uuid

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from core_templates import templates
import httpx
import google.generativeai as genai
from pdfminer.high_level import extract_text

from flash import flash

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
    except:
        return {}

import hmac
import hashlib
from datetime import datetime, timezone

@router.get("/checkout/premium")
async def checkout_premium(request: Request, tier: str = "10"):
    user_id = request.session.get('user_id')
    if not user_id:
        flash(request, "Please log in to purchase scans.", "warning")
        return RedirectResponse(url="/login", status_code=303)
        
    products = {
        "10": {
            "product_name": "MASARI PRO 10 SCANS",
            "product_price": "10",
            "product_cover": "h23hlttkyiwe3x8own7qitxfvqcw",
            "gumroad_url": "https://gumroad.com/l/masari-10",
            "description": "Instantly unlock 10 Premium ATS Scans on the MASARI platform! Get AI-powered feedback on your software engineering resume, discover missing keywords, and optimize your bullet points to bypass ATS filters and land more interviews."
        },
        "15": {
            "product_name": "MASARI PRO 20 SCANS",
            "product_price": "15",
            "product_cover": "arw29xgaucbl0zg583emwr6rwyse",
            "gumroad_url": "https://gumroad.com/l/masari-20",
            "description": "Instantly unlock 20 Premium ATS Scans on the MASARI platform! Get AI-powered feedback on your software engineering resume, discover missing keywords, and optimize your bullet points to bypass ATS filters and land more interviews."
        },
        "25": {
            "product_name": "MASARI PRO 50 SCANS",
            "product_price": "25",
            "product_cover": "2c74gmg3i7sbb5wc75epnracqxr3",
            "gumroad_url": "https://gumroad.com/l/masari-25",
            "description": "Instantly unlock 50 Premium ATS Scans on the MASARI platform! Get AI-powered feedback on your software engineering resume, discover missing keywords, and optimize your bullet points to bypass ATS filters and land more interviews."
        }
    }
    
    product = products.get(tier, products["10"])
    
    return templates.TemplateResponse(
        request=request,
        name="gumroad_checkout.html", 
        context={
            "user_id": user_id,
            **product
        }
    )

@router.get("/checkout/demo_unlock")
async def demo_unlock(request: Request, tier: str = "10"):
    user_id = request.session.get('user_id')
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    credits_map = {
        "10": 10,
        "15": 20,
        "25": 50
    }
    
    amount = credits_map.get(tier, 10)
    db = request.app.state.mongo_db
    if db is not None:
        await db.users.update_one({"_id": user_id}, {"$inc": {"resume_credits": amount}})
        
    flash(request, f"Demo Successful! {amount} credits have been added to your account.", "success")
    return RedirectResponse(url="/dashboard", status_code=303)

from fastapi import HTTPException
import logging

@router.post("/api/webhooks/gumroad")
async def gumroad_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("x-gumroad-signature")
    db = request.app.state.mongo_db
    
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = dict(await request.form())
    except:
        data = {"raw_payload": payload.decode('utf-8', errors='ignore')}
        
    # Log the webhook for debugging
    if db is not None:
        await db.webhook_logs.insert_one({
            "source": "gumroad",
            "signature_present": bool(signature),
            "data": data,
            "timestamp": datetime.now(timezone.utc)
        })
        
    user_id = data.get("user_id")
    permalink = data.get("permalink") or data.get("product_permalink")
    email = data.get("email")
    
    if not user_id:
        user_id = data.get("url_params[user_id]")
        
    if not user_id:
        for k, v in data.items():
            if "user_id" in k.lower():
                user_id = v
                break
                
    # FOOLPROOF FALLBACK: Look up by email
    if not user_id and email and db is not None:
        user = await db.users.find_one({"email": email})
        if user:
            user_id = str(user["_id"])
            
    if not user_id:
        return {"status": "ignored", "reason": "No user_id found (and email didn't match)"}
        
    credits_map = {
        "masari-10": 10,
        "masari-20": 20,
        "masari-25": 50
    }
    
    amount = credits_map.get(permalink, 0)
    
    if amount > 0 and db is not None:
        await db.users.update_one({"_id": user_id}, {"$inc": {"resume_credits": amount}})
        
    return {"status": "success"}

@router.post("/api/resume/analyze")
async def api_resume_analyze(request: Request, job_description: str = Form(""), resume: UploadFile = File(None)):
    user_id = request.session.get('user_id')
    if not user_id:
        return JSONResponse({"error": "You must be logged in to analyze resumes."}, status_code=401)
        
    db = request.app.state.mongo_db
    user = await db.users.find_one({"_id": user_id})
    if not user or (not user.get('is_premium') and user.get('role') != 'admin' and user.get('resume_credits', 0) <= 0):
        return JSONResponse({"error": "You have 0 Resume Scans remaining. Please purchase more scans to continue."}, status_code=403)

    if not resume:
        return JSONResponse({"error": "No resume file uploaded"}, status_code=400)
        
    job_description = job_description.strip()

    if not resume.filename.lower().endswith('.pdf'):
        return JSONResponse({"error": "Resume must be a PDF file"}, status_code=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        content = await resume.read()
        temp_pdf.write(content)
        temp_path = temp_pdf.name

    try:
        # Run synchronous pdf text extraction in threadpool
        resume_text = await asyncio.to_thread(extract_text, temp_path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return JSONResponse({"error": f"Failed to parse PDF: {str(e)}"}, status_code=500)

    if os.path.exists(temp_path):
        os.remove(temp_path)

    if not resume_text.strip():
        return JSONResponse({"error": "Could not extract text from the PDF. It might be an image-based PDF."}, status_code=400)

    system_prompt = (
        "You are an expert technical recruiter and Applicant Tracking System (ATS). "
        "Analyze the candidate's resume. Recommend the single best-fitting professional job title for them. "
        "If a target Job Description is provided, evaluate the match score and missing keywords against it. "
        "If no Job Description is provided, evaluate the candidate's overall profile strength (ats_score from 0-100) and identify missing high-demand industry skills for their recommended role as missing_keywords.\n"
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"ats_score\": <integer 0-100>,\n"
        "  \"perfect_job_title\": \"<the single best-fitting professional job title recommended for this candidate based on their CV and experience>\",\n"
        "  \"missing_keywords\": [\"<keyword1>\", \"<keyword2>\"],\n"
        "  \"bullet_rewrites\": [\n"
        "    {\n"
        "      \"original\": \"<weak bullet point from resume>\",\n"
        "      \"improved\": \"<rewritten bullet using STAR method tailored to their skills and recommended role>\",\n"
        "      \"reasoning\": \"<why this is better>\"\n"
        "    }\n"
        "  ],\n"
        "  \"recommended_upskilling\": [\"<CS concept or project to learn/build>\"]\n"
        "}\n"
        "Provide exactly 3 bullet_rewrites for the weakest bullet points in the resume."
    )

    user_prompt = f"### TARGET JOB DESCRIPTION (IF PROVIDED) ###\n{job_description or 'No job description provided'}\n\n### CANDIDATE RESUME ###\n{resume_text}"
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
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": 0.3,
                "max_tokens": 1500,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(openrouter_url, json=payload, headers=headers, timeout=20.0)
            if res.status_code == 200:
                result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
        except Exception:
            pass

    if not result and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=system_prompt)
            response = await model.generate_content_async(user_prompt)
            result = extract_json_from_llm(response.text)
        except Exception:
            pass

    if not result:
        return JSONResponse({"error": "Our AI servers are currently experiencing high load or your API keys are invalid. No credits were consumed. Please check your API limits or try again later."}, status_code=503)

    # Decrement credit only on success
    if not user.get('is_premium') and user.get('role') != 'admin':
        await db.users.update_one({"_id": user_id}, {"$inc": {"resume_credits": -1}})

    result.setdefault("ats_score", 0)
    result.setdefault("perfect_job_title", "Software Engineer")
    result.setdefault("missing_keywords", [])
    result.setdefault("bullet_rewrites", [])
    result.setdefault("recommended_upskilling", [])

    return JSONResponse(result)

