import os
import json
import hashlib
import time
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from sklearn.metrics.pairwise import cosine_similarity
import httpx
import google.generativeai as genai
import tempfile

router = APIRouter()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

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

@router.get("/api/interview/search")
async def api_interview_search(request: Request, q: str = "", difficulty: str = "Intermediate"):
    query = q.strip()
    if not query:
        return JSONResponse({"results": [], "recommendations": []})
        
    system_prompt = (
        "You are an expert technical interviewer. Generate 5 highly relevant interview questions "
        f"and detailed answers for the query: '{query}' at the {difficulty} level. "
        "Respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        "  \"results\": [\n"
        "    {\n"
        "      \"question\": \"<the interview question>\",\n"
        "      \"answer\": \"<detailed explanation>\",\n"
        "      \"relevance_percentage\": <integer from 80 to 99>\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    cache_key = f"search_{hashlib.md5(f'{query.lower()}_{difficulty.lower()}'.encode('utf-8')).hexdigest()}"
    db = request.app.state.mongo_db
    cached_results = None
    
    if db is not None:
        try:
            cached_doc = await db.interview_prep_cache.find_one({"key": cache_key})
            if cached_doc:
                created_at = cached_doc.get("created_at")
                if created_at and (datetime.utcnow() - created_at < timedelta(days=14)):
                    cached_results = cached_doc.get("results")
        except Exception as e:
            pass

    if cached_results:
        results = cached_results
    else:
        results = []
        if OPENROUTER_API_KEY:
            try:
                groq_url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
                payload = {
                    "model": "meta-llama/llama-4-scout",
                    "messages": [{"role": "user", "content": system_prompt}],
                    "temperature": 0.5,
                    "max_tokens": 1500,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient() as client:
                    res = await client.post(groq_url, json=payload, headers=headers, timeout=30.0)
                if res.status_code == 200:
                    data = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
                    results = data.get("results", [])
            except Exception:
                pass

        if not results and GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel(model_name='gemini-1.5-flash')
                response = await model.generate_content_async(system_prompt)
                data = extract_json_from_llm(response.text)
                results = data.get("results", [])
            except Exception:
                pass

        if results and db is not None:
            try:
                await db.interview_prep_cache.update_one(
                    {"key": cache_key},
                    {"$set": {
                        "key": cache_key,
                        "results": results,
                        "created_at": datetime.utcnow()
                    }},
                    upsert=True
                )
            except Exception:
                pass

    import ai_core
    analysis = None
    if ai_core.interview_ai_models:
        analysis = ai_core.interview_ai_models.analyze_question_comprehensive(query)
    
    recommendations = []
    if ai_core.interview_rec_engine:
        recommendations = ai_core.interview_rec_engine.get_recommendations(query, difficulty, top_k=5)
    
    related_courses = []
    if ai_core.df is not None and not ai_core.df.empty and ai_core.vectorizer is not None:
        query_vector = ai_core.vectorizer.transform([query.lower()])
        search_df = ai_core.df.copy()
        search_df['match_score'] = cosine_similarity(query_vector, ai_core.tfidf_matrix).flatten()
        recs = search_df[search_df['match_score'] > 0.05].sort_values(by=['stars', 'match_score'], ascending=[False, False])
        
        for c in recs.head(3).to_dict('records'):
            related_courses.append({
                "title": c.get("title"),
                "provider": c.get("provider"),
                "url": c.get("url", "#"),
                "stars": c.get("stars"),
                "ratings_count": c.get("ratings_count", 0),
                "description": c.get("content_text", "")[:100] + "..."
            })
    
    return JSONResponse({
        "results": results,
        "analysis": analysis,
        "recommendations": recommendations,
        "related_courses": related_courses
    })


@router.get("/api/interview/explain")
async def api_interview_explain(q: str = ""):
    question = q.strip()
    if not question:
        return JSONResponse({"explanation": None}, status_code=400)

    system_prompt = "You are an elite technical interviewer. Provide a clear, accurate, and concise answer and explanation (around 3-4 sentences) for the following interview question. Use markdown for code if necessary."
    user_prompt = f"Interview Question: {question}\n\nPlease provide the answer and explanation."

    explanation = None
    
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
                "temperature": 0.3,
                "max_tokens": 500
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(openrouter_url, json=payload, headers=headers, timeout=30.0)
            if res.status_code == 200:
                explanation = res.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    if not explanation and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_prompt)
            response = await model.generate_content_async(user_prompt)
            explanation = response.text.strip()
        except Exception:
            pass

    return JSONResponse({"explanation": explanation})


@router.post("/api/interview/followup")
async def api_interview_followup(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    question = data.get('question', '').strip()
    user_answer = data.get('user_answer', '').strip()
    conversation_history = data.get('conversation_history', [])

    if not question or not user_answer:
        return JSONResponse({"error": "Missing question or user_answer"}, status_code=400)

    system_prompt = (
        "You are a rigorous technical interviewer. Evaluate the candidate's answer (which may be text or code) to a technical question. "
        "If the candidate provides code, you MUST evaluate its Time Complexity (Big-O), Space Complexity, and identify any missed edge cases. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"verdict\": \"complete\" | \"incomplete\",\n"
        "  \"feedback\": \"<specific feedback about what is correct or missing. Include Big-O if code is provided.>\",\n"
        "  \"followup\": \"<a single probing follow-up question, or null if verdict is complete>\",\n"
        "  \"score\": <integer 1-10>\n"
        "}\n"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in conversation_history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({
        "role": "user",
        "content": f"Question: {question}\n\nCandidate's answer: {user_answer}"
    })

    result = None

    if OPENROUTER_API_KEY:
        try:
            groq_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 400,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(groq_url, json=payload, headers=headers, timeout=30.0)
            if res.status_code == 200:
                result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
        except Exception:
            pass

    if not result and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_prompt)
            response = await model.generate_content_async(f"Question: {question}\n\nCandidate's answer: {user_answer}")
            result = extract_json_from_llm(response.text)
        except Exception:
            pass

    if not result:
        return JSONResponse({"error": "AI model unavailable. Please try again."}, status_code=503)

    result.setdefault("verdict", "incomplete")
    result.setdefault("feedback", "")
    result.setdefault("followup", None)
    result.setdefault("score", 5)

    if result.get("verdict") == "complete":
        user_id = request.session.get('user_id')
        db = request.app.state.mongo_db
        if user_id and db is not None:
            try:
                await db.interview_results.insert_one({
                    "user_id": user_id,
                    "category": "Technical",
                    "score": result.get("score", 5),
                    "date": datetime.utcnow()
                })
            except Exception:
                pass

    return JSONResponse(result)


@router.post("/api/interview/generate_technical")
async def api_interview_generate_technical(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    topic = data.get('topic', '').strip()
    difficulty = data.get('difficulty', 'Intermediate')

    if not topic:
        return JSONResponse({"error": "Missing topic"}, status_code=400)

    system_prompt = (
        "You are an expert technical interviewer. Generate exactly 5 technical interview questions "
        f"for the topic: '{topic}' at {difficulty} level. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"questions\": [\n"
        "    { \"question\": \"<the interview question>\" }\n"
        "  ]\n"
        "}"
    )

    cache_key = f"generate_{hashlib.md5(f'{topic.lower()}_{difficulty.lower()}'.encode('utf-8')).hexdigest()}"
    db = request.app.state.mongo_db
    cached_result = None
    
    if db is not None:
        try:
            cached_doc = await db.interview_prep_cache.find_one({"key": cache_key})
            if cached_doc:
                created_at = cached_doc.get("created_at")
                if created_at and (datetime.utcnow() - created_at < timedelta(days=14)):
                    cached_result = cached_doc.get("results")
        except Exception:
            pass

    if cached_result:
        result = cached_result
    else:
        result = None
        if OPENROUTER_API_KEY:
            try:
                groq_url = "https://openrouter.ai/api/v1/chat/completions"
                headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
                payload = {
                    "model": "meta-llama/llama-4-scout",
                    "messages": [{"role": "user", "content": system_prompt}],
                    "temperature": 0.5,
                    "max_tokens": 800,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient() as client:
                    res = await client.post(groq_url, json=payload, headers=headers, timeout=30.0)
                if res.status_code == 200:
                    result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
            except Exception:
                pass

        if not result and GEMINI_API_KEY:
            try:
                model = genai.GenerativeModel(model_name='gemini-1.5-flash')
                response = await model.generate_content_async(system_prompt)
                result = extract_json_from_llm(response.text)
            except Exception:
                pass

        if not result or "questions" not in result:
            return JSONResponse({"error": "Could not generate technical questions."}, status_code=503)

        if db is not None:
            try:
                await db.interview_prep_cache.update_one(
                    {"key": cache_key},
                    {"$set": {
                        "key": cache_key,
                        "results": result,
                        "created_at": datetime.utcnow()
                    }},
                    upsert=True
                )
            except Exception:
                pass

    return JSONResponse(result)


@router.post("/api/interview/transcribe")
async def api_interview_transcribe(audio: UploadFile = File(...)):
    if not audio:
        return JSONResponse({"error": "No audio file provided"}, status_code=400)
        
    if not GROQ_API_KEY:
        return JSONResponse({"error": "GROQ_API_KEY is required for voice transcription"}, status_code=503)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        content = await audio.read()
        temp_audio.write(content)
        temp_path = temp_audio.name
        
    try:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        
        async with httpx.AsyncClient() as client:
            with open(temp_path, "rb") as f:
                files = {"file": (os.path.basename(temp_path), f, "audio/webm")}
                data = {"model": "whisper-large-v3-turbo"}
                # httpx syntax for files
                response = await client.post(url, headers=headers, files=files, data=data, timeout=20.0)
            
        os.remove(temp_path)
        
        if response.status_code == 200:
            return JSONResponse({"text": response.json().get("text", "").strip()})
        else:
            return JSONResponse({"error": f"Transcription failed: {response.text}"}, status_code=response.status_code)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return JSONResponse({"error": f"Internal error during transcription: {str(e)}"}, status_code=500)


@router.post("/api/interview/behavioral")
async def api_interview_behavioral(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    topic = data.get('topic', '').strip()
    difficulty = data.get('difficulty', 'Intermediate')

    if not topic:
        return JSONResponse({"error": "Missing topic"}, status_code=400)

    system_prompt = (
        "You are an expert technical recruiter. Generate exactly 6 behavioral interview questions "
        f"for the theme: '{topic}' at {difficulty} level. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"questions\": [\n"
        "    {\n"
        "      \"question\": \"<behavioral question starting with 'Tell me about a time...' or 'Describe a situation...'\",\n"
        "      \"star_tips\": \"<one sentence tip for each STAR element: Situation, Task, Action, Result>\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    result = None

    if OPENROUTER_API_KEY:
        try:
            groq_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": [{"role": "user", "content": system_prompt}],
                "temperature": 0.7,
                "max_tokens": 1200,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(groq_url, json=payload, headers=headers, timeout=30.0)
            if res.status_code == 200:
                result = extract_json_from_llm(res.json()["choices"][0]["message"]["content"])
        except Exception:
            pass

    if not result and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(model_name='gemini-1.5-flash')
            response = await model.generate_content_async(system_prompt)
            result = extract_json_from_llm(response.text)
        except Exception:
            pass

    if not result or "questions" not in result:
        return JSONResponse({"error": "Could not generate behavioral questions."}, status_code=503)

    return JSONResponse(result)


@router.post("/api/interview/star_analyze")
async def api_interview_star_analyze(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    question = data.get('question', '').strip()
    user_answer = data.get('user_answer', '').strip()

    if not question or not user_answer:
        return JSONResponse({"error": "Missing question or user_answer"}, status_code=400)

    system_prompt = (
        "You are an expert behavioral interview coach who strictly evaluates answers using the STAR method. "
        "Respond ONLY with a valid JSON object — no markdown, no code fences. Use this exact schema:\n"
        "{\n"
        "  \"situation\": {\"score\": <1-10>, \"comment\": \"<feedback>\"},\n"
        "  \"task\":      {\"score\": <1-10>, \"comment\": \"<feedback>\"},\n"
        "  \"action\":    {\"score\": <1-10>, \"comment\": \"<feedback>\"},\n"
        "  \"result\":    {\"score\": <1-10>, \"comment\": \"<feedback>\"},\n"
        "  \"overall\":   \"<2-3 sentence holistic summary with the most important improvement tip>\"\n"
        "}\n"
    )

    user_prompt = f"Behavioral Question: {question}\n\nCandidate's Answer:\n{user_answer}"
    result = None

    if OPENROUTER_API_KEY:
        try:
            groq_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 600,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(groq_url, json=payload, headers=headers, timeout=15.0)
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
        return JSONResponse({"error": "AI model unavailable. Please try again."}, status_code=503)

    for component in ["situation", "task", "action", "result"]:
        result.setdefault(component, {"score": 5, "comment": "No data"})
    result.setdefault("overall", "")

    try:
        avg_score = sum([result[c].get("score", 5) for c in ["situation", "task", "action", "result"]]) / 4.0
        user_id = request.session.get('user_id')
        db = request.app.state.mongo_db
        if user_id and db is not None:
            await db.interview_results.insert_one({
                "user_id": user_id,
                "category": "Behavioral",
                "score": round(avg_score, 1),
                "date": datetime.utcnow()
            })
    except Exception:
        pass

    return JSONResponse(result)


@router.get("/api/interview/stats")
async def api_interview_stats(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    db = request.app.state.mongo_db
    if db is None:
        return JSONResponse({"error": "Database error"}, status_code=500)
        
    try:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$category",
                "average_score": {"$avg": "$score"},
                "attempts": {"$sum": 1}
            }}
        ]
        stats = []
        async for doc in db.interview_results.aggregate(pipeline):
            stats.append(doc)
            
        categories = ["Technical", "Behavioral", "System Design", "Algorithms", "Data Structures"]
        results = {c: 0 for c in categories}
        for s in stats:
            cat = s["_id"]
            if cat in results:
                results[cat] = round(s["average_score"], 1)
            else:
                results[cat] = round(s["average_score"], 1)
                categories.append(cat)
                
        labels = list(results.keys())
        data = list(results.values())
        
        return JSONResponse({
            "labels": labels,
            "data": data
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/chat_assistant_stream")
async def chat_assistant_stream(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
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
    
    async def generate():
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
                    "messages": [{"role": "system", "content": system_prompt}] + messages,
                    "temperature": 0.5,
                    "max_tokens": 1024,
                    "stream": True
                }
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", openrouter_url, json=payload, headers=headers, timeout=15.0) as res:
                        if res.status_code == 200:
                            async for line in res.aiter_lines():
                                if line:
                                    decoded = line.strip()
                                    if decoded.startswith("data: "):
                                        data_str = decoded[6:]
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(data_str)
                                            delta = chunk["choices"][0]["delta"].get("content", "")
                                            if delta:
                                                yield f"data: {json.dumps({'content': delta})}\n\n"
                                        except:
                                            pass
                            return
            except Exception as e:
                print(f"OpenRouter streaming connection error: {e}")

        if GEMINI_API_KEY:
            try:
                transcript = ""
                for m in messages:
                    role = "Student" if m['role'] == 'user' else "Advisor"
                    transcript += f"{role}: {m['content']}\n"
                user_prompt = f"Dialogue history:\n{transcript}\nAdvisor:"
                
                model = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=system_prompt)
                response = await model.generate_content_async(user_prompt, stream=True)
                async for chunk in response:
                    yield f"data: {json.dumps({'content': chunk.text})}\n\n"
                return
            except Exception as e:
                print(f"Gemini streaming error: {e}")

        fallback_response = (
            "Hello! I am currently running in offline mode. Here are a few general CS study tips:\n"
            "1. **Practice coding daily**: Sites like LeetCode or building small personal projects help cement syntax.\n"
            "2. **Optimize your learning path**: Complete your saved plans week-by-week.\n"
        )
        for char in fallback_response:
            yield f"data: {json.dumps({'content': char})}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.get("/api/generate_quiz")
async def generate_quiz(request: Request):
    db = request.app.state.mongo_db
    user_id = request.session.get('user_id')
    if not user_id or db is None:
        return JSONResponse({"success": False, "error": "Database error or unauthorized"}, status_code=500)
        
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
        
    track = user.get('track', 'General CS')
    skill_level = user.get('current_skill_level', 'Beginner')
    
    system_prompt = (
        "You are an expert computer science educator and examiner.\n"
        "Your task is to generate a high-quality 5-question multiple choice quiz matching the student's learning track and current skill level.\n"
        "Provide your output ONLY as a valid JSON object. Do not wrap in markdown tags like ```json or ```.\n"
        "The JSON object must have a single key 'questions' containing a list of 5 objects.\n"
        "Each question object MUST contain the following fields exactly:\n"
        "- 'id': unique integer (1 to 5)\n"
        "- 'question': the question text (clear, challenging, and educational)\n"
        "- 'options': an array of exactly 4 strings (options A, B, C, D)\n"
        "- 'correct_index': the index of the correct option in the options array (0 to 3)\n"
        "- 'explanation': a short explanation explaining why the correct answer is correct.\n"
    )
    
    user_prompt = f"Please generate a quiz for the track: '{track}' at the level: '{skill_level}'."
    
    if OPENROUTER_API_KEY:
        try:
            openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": "https://cs-recommender.com", "X-Title": "MASARI", "Content-Type": "application/json"}
            payload = {
                "model": "meta-llama/llama-4-scout",
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": 0.4,
                "max_tokens": 1500,
                "response_format": {"type": "json_object"}
            }
            async with httpx.AsyncClient() as client:
                res = await client.post(openrouter_url, json=payload, headers=headers, timeout=15.0)
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"].strip()
                quiz_data = extract_json_from_llm(reply)
                if "questions" in quiz_data and len(quiz_data["questions"]) == 5:
                    return JSONResponse({"success": True, "track": track, "skill_level": skill_level, "questions": quiz_data["questions"]})
        except Exception:
            pass
            
    from routers.quiz_bank import get_local_fallback_questions
    questions = get_local_fallback_questions(track, skill_level)
    return JSONResponse({"success": True, "track": track, "skill_level": skill_level, "questions": questions})

@router.post("/api/submit_quiz")
async def submit_quiz(request: Request):
    try:
        data = await request.json()
    except:
        data = {}
        
    user_answers = data.get('quiz_answers', [])
    quiz_questions = data.get('quiz_questions', [])
    
    if len(user_answers) != 5 or len(quiz_questions) != 5:
        return JSONResponse({"success": False, "error": "Invalid quiz submission data"}, status_code=400)
        
    db = request.app.state.mongo_db
    user_id = request.session.get('user_id')
    
    if db is None or not user_id:
        return JSONResponse({"success": False, "error": "Database error or not logged in"}, status_code=500)
        
    user = await db.users.find_one({"_id": user_id})
    if not user:
        return JSONResponse({"success": False, "error": "User not found"}, status_code=404)
        
    correct_count = sum(1 for idx, q in enumerate(quiz_questions) if user_answers[idx] == q.get('correct_index'))
    score = int((correct_count / 5) * 100)
    passed = score >= 80
    
    promoted = False
    current_level = user.get('current_skill_level', 'Beginner')
    new_level = current_level
    
    if passed:
        if current_level == 'Beginner':
            new_level = 'Intermediate'
            promoted = True
        elif current_level == 'Intermediate':
            new_level = 'Advanced'
            promoted = True
            
        if promoted:
            await db.users.update_one({"_id": user_id}, {"$set": {"current_skill_level": new_level}})
            
    return JSONResponse({
        "success": True,
        "score": score,
        "correct_count": correct_count,
        "passed": passed,
        "promoted": promoted,
        "new_level": new_level
    })
