import os
import ssl
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import nltk
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

import google.generativeai as genai

# Load custom flash messages helper
from flash import get_flashed_messages

load_dotenv(override=True)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
SECRET_KEY = os.environ.get("SECRET_KEY", "masari_super_secret_fallback_key_2026")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# SSL context for older Python versions
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Setup NLTK
try:
    if os.environ.get("VERCEL") == "1":
        nltk.data.path.append('/tmp')
        nltk.download('vader_lexicon', download_dir='/tmp', quiet=True)
        nltk.download('stopwords', download_dir='/tmp', quiet=True)
        nltk.download('punkt', download_dir='/tmp', quiet=True)
        nltk.download('punkt_tab', download_dir='/tmp', quiet=True)
        nltk.download('averaged_perceptron_tagger', download_dir='/tmp', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', download_dir='/tmp', quiet=True)
    else:
        nltk.download('vader_lexicon', quiet=True)
        nltk.download('stopwords', quiet=True)
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        nltk.download('averaged_perceptron_tagger_eng', quiet=True)
except Exception:
    pass

# Global dependencies
mongo_client = None
mongo_db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo_client, mongo_db
    # Startup
    try:
        mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        mongo_db = mongo_client["cs_recommender"]
        app.state.mongo_client = mongo_client
        app.state.mongo_db = mongo_db
        await mongo_db.users.create_index("email", unique=True, sparse=True)
        await mongo_db.courses.create_index("url")
        await mongo_db.course_analyses.create_index("cache_key")
        await mongo_db.link_status.create_index("url")
        await mongo_db.interview_results.create_index("user_id")
        await mongo_db.interview_prep_cache.create_index("key")
        await mongo_db.study_plans_cache.create_index("key")
        print("Connected to MongoDB securely.")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")

    # Load ML models and TF-IDF
    try:
        from ai_core import load_and_train_model, load_interview_system
        load_and_train_model()
        load_interview_system()
    except ImportError as e:
        print(f"Error importing AI core: {e}")
    
    yield
    
    # Shutdown
    if mongo_client:
        mongo_client.close()

app = FastAPI(lifespan=lifespan)

# --- VERCEL SERVERLESS COMPATIBILITY ---
# Vercel's Python runtime skips FastAPI lifespan events.
# We explicitly set the state here so it's guaranteed to be available.
try:
    if os.environ.get("VERCEL") == "1":
        if mongo_client is None:
            mongo_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            mongo_db = mongo_client["cs_recommender"]
            app.state.mongo_client = mongo_client
            app.state.mongo_db = mongo_db
        
    from ai_core import load_and_train_model, load_interview_system
    load_and_train_model()
    load_interview_system()
except Exception as e:
    print(f"Vercel Global Init Error: {e}")
# ---------------------------------------

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400 * 30)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

# Inject get_flashed_messages into all templates



# We will import and mount routers here:
from routers import pages, auth, course, interview, resume, admin, dashboard

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(course.router)
app.include_router(interview.router)
app.include_router(resume.router)
app.include_router(admin.router)
app.include_router(dashboard.router)

