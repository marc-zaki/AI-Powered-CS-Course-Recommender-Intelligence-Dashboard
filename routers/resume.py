import os
import json
import tempfile
import asyncio

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
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

@router.get("/checkout/premium")
async def checkout_premium(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        flash(request, "Please log in to upgrade.", "warning")
        return RedirectResponse(url="/login", status_code=303)
        
    db = request.app.state.mongo_db
    user = None
    if db is not None:
        user = await db.users.find_one({"_id": user_id})
        
    from core_templates import templates
    return templates.TemplateResponse(request=request, name="simulated_checkout.html", context= {"request": request, "current_user": user})

@router.get("/checkout/success")
async def checkout_success(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
        
    db = request.app.state.mongo_db
    if db is not None:
        await db.users.update_one({"_id": user_id}, {"$set": {"is_premium": True, "subscription_type": "pro"}})
        
    flash(request, "Payment successful! You are now a PRO user.", "success")
    return RedirectResponse(url="/resume-optimizer", status_code=303)

@router.post("/api/resume/analyze")
async def api_resume_analyze(request: Request, job_description: str = Form(""), resume: UploadFile = File(None)):
    if not resume:
        return JSONResponse({"error": "No resume file uploaded"}, status_code=400)
        
    job_description = job_description.strip()
    if not job_description:
        return JSONResponse({"error": "No job description provided"}, status_code=400)

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
        "Analyze the candidate's resume against the target Job Description. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"ats_score\": <integer 0-100>,\n"
        "  \"missing_keywords\": [\"<keyword1>\", \"<keyword2>\"],\n"
        "  \"bullet_rewrites\": [\n"
        "    {\n"
        "      \"original\": \"<weak bullet point from resume>\",\n"
        "      \"improved\": \"<rewritten bullet using STAR method tailored to the JD>\",\n"
        "      \"reasoning\": \"<why this is better>\"\n"
        "    }\n"
        "  ],\n"
        "  \"recommended_upskilling\": [\"<CS concept or project to learn/build>\"]\n"
        "}\n"
        "Provide exactly 3 bullet_rewrites for the weakest bullet points in the resume."
    )

    user_prompt = f"### TARGET JOB DESCRIPTION ###\n{job_description}\n\n### CANDIDATE RESUME ###\n{resume_text}"
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
        return JSONResponse({"error": "AI model unavailable or failed to generate analysis. Please try again."}, status_code=503)

    result.setdefault("ats_score", 0)
    result.setdefault("missing_keywords", [])
    result.setdefault("bullet_rewrites", [])
    result.setdefault("recommended_upskilling", [])

    return JSONResponse(result)
