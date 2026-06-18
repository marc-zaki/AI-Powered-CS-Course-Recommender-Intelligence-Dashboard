import os
import time
import uuid
import hashlib
import urllib.parse
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from core_templates import templates
from werkzeug.security import generate_password_hash, check_password_hash
import httpx
import pandas as pd

from flash import get_flashed_messages, flash

templates.env.globals["get_flashed_messages"] = get_flashed_messages

router = APIRouter()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

async def get_db_async(request: Request):
    return request.app.state.mongo_db if hasattr(request.app.state, 'mongo_db') else None

async def get_current_user(request: Request):
    user_id = request.session.get('user_id')
    if user_id:
        db = request.app.state.mongo_db
        if db is not None:
            return await db.users.find_one({"_id": user_id})
    return None

def login_required(func):
    """
    In FastAPI, it's better to use dependencies, but since we are migrating,
    we will handle this manually in the routes for now.
    """
    pass

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context= {"request": request})

@router.post("/register")
async def register(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    track: str = Form(""),
    career_goals: str = Form(""),
    skill_level: str = Form("Beginner")
):
    db = request.app.state.mongo_db
    if db is None:
        flash(request, "Database connection error.", "danger")
        return RedirectResponse(url="/register", status_code=303)
        
    name = name.strip()
    email = email.strip()
    
    if not name or not email or not password:
        flash(request, "Name, email, and password are required.", "danger")
        return RedirectResponse(url="/register", status_code=303)
        
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        flash(request, "Email already registered.", "danger")
        return RedirectResponse(url="/register", status_code=303)
        
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    user_id = str(hashlib.sha256(email.encode()).hexdigest())[:16]
    
    is_student_email = email.endswith('.edu') or email.endswith('.ac.uk') or '.edu.' in email
    
    user_doc = {
        "_id": user_id,
        "name": name,
        "email": email,
        "password_hash": hashed_password,
        "track": track,
        "career_goals": career_goals,
        "current_skill_level": skill_level,
        "role": "user",
        "taken_courses": [],
        "onboarding_preferences": {},
        "is_premium": is_student_email,
        "subscription_type": "student" if is_student_email else "none"
    }
    
    await db.users.insert_one(user_doc)
    request.session['user_id'] = user_id
    flash(request, "Registration successful! Please complete your onboarding.", "success")
    return RedirectResponse(url="/onboarding", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context= {"request": request})

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(""),
    password: str = Form("")
):
    db = request.app.state.mongo_db
    if db is None:
        flash(request, "Database connection error.", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    email = email.strip()
    user = await db.users.find_one({"email": email})
    
    if user and check_password_hash(user['password_hash'], password):
        request.session['user_id'] = user['_id']
        flash(request, f"Welcome back, {user['name']}!", "success")
        next_url = request.query_params.get('next', '/')
        return RedirectResponse(url=next_url, status_code=303)
    else:
        flash(request, "Invalid email or password.", "danger")
        return templates.TemplateResponse(request=request, name="login.html", context= {"request": request})

@router.get("/logout")
async def logout(request: Request):
    request.session.pop('user_id', None)
    flash(request, "You have been logged out.", "success")
    return RedirectResponse(url="/", status_code=303)

@router.get("/login/google")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash(request, "Google OAuth credentials are not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.", "warning")
        return RedirectResponse(url="/login", status_code=303)
        
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    redirect_uri = f"{scheme}://{request.url.hostname}{'' if request.url.port in [80, 443, None] else ':' + str(request.url.port)}/login/google/callback"
    
    request.session['google_oauth_redirect_uri'] = redirect_uri
    
    state = str(uuid.uuid4())
    request.session['google_oauth_state'] = state
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account"
    }
    
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=auth_url, status_code=303)

@router.get("/login/google/callback")
async def google_callback(request: Request):
    db = request.app.state.mongo_db
    if db is None:
        flash(request, "Database connection error.", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    state = request.query_params.get('state')
    code = request.query_params.get('code')
    error = request.query_params.get('error')
    
    if error:
        flash(request, f"Google login error: {error}", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    if not state or state != request.session.pop('google_oauth_state', None):
        flash(request, "Invalid state parameter. Possible CSRF attempt.", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    if not code:
        flash(request, "Authorization code missing.", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    redirect_uri = request.session.pop('google_oauth_redirect_uri', None)
    if not redirect_uri:
        scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
        redirect_uri = f"{scheme}://{request.url.hostname}{'' if request.url.port in [80, 443, None] else ':' + str(request.url.port)}/login/google/callback"
        
    try:
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        async with httpx.AsyncClient() as client:
            res = await client.post(token_url, data=payload, timeout=10.0)
            
        if res.status_code != 200:
            flash(request, f"Failed to retrieve access token from Google: {res.text}", "danger")
            return RedirectResponse(url="/login", status_code=303)
            
        token_data = res.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            flash(request, "Google response did not include access token.", "danger")
            return RedirectResponse(url="/login", status_code=303)
            
        userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            userinfo_res = await client.get(userinfo_url, headers=headers, timeout=10.0)
            
        if userinfo_res.status_code != 200:
            flash(request, "Failed to retrieve user profile from Google.", "danger")
            return RedirectResponse(url="/login", status_code=303)
            
        user_info = userinfo_res.json()
        email = user_info.get("email")
        name = user_info.get("name", "Google User")
        
        if not email:
            flash(request, "Failed to retrieve user email from Google.", "danger")
            return RedirectResponse(url="/login", status_code=303)
            
        is_student_email = email.endswith('.edu') or email.endswith('.ac.uk') or '.edu.' in email

        user = await db.users.find_one({"email": email})
        if user:
            if is_student_email and not user.get('is_premium'):
                await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_premium": True, "subscription_type": "student"}})
            
            request.session['user_id'] = user['_id']
            flash(request, f"Welcome back, {user['name']}!", "success")
            return RedirectResponse(url="/", status_code=303)
        else:
            user_id = str(hashlib.sha256(email.encode()).hexdigest())[:16]
            user_doc = {
                "_id": user_id,
                "name": name,
                "email": email,
                "password_hash": "", 
                "track": "General CS",
                "career_goals": "",
                "current_skill_level": "Beginner",
                "role": "user",
                "taken_courses": [],
                "onboarding_preferences": {},
                "is_premium": is_student_email,
                "subscription_type": "student" if is_student_email else "none"
            }
            
            await db.users.insert_one(user_doc)
            request.session['user_id'] = user_id
            flash(request, "Registration successful via Google! Please complete your onboarding.", "success")
            return RedirectResponse(url="/onboarding", status_code=303)
            
    except Exception as e:
        print(f"Google OAuth Exception: {e}")
        flash(request, f"An error occurred during Google OAuth: {e}", "danger")
        return RedirectResponse(url="/login", status_code=303)

@router.get("/forgot_password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html", context= {"request": request})

@router.post("/forgot_password")
async def forgot_password(request: Request, email: str = Form("")):
    email = email.strip()
    if not email:
        flash(request, "Please enter your email address.", "danger")
        return RedirectResponse(url="/forgot_password", status_code=303)
        
    db = request.app.state.mongo_db
    if db is None:
        flash(request, "Database connection error.", "danger")
        return RedirectResponse(url="/forgot_password", status_code=303)
        
    user = await db.users.find_one({"email": email})
    if not user:
        flash(request, "If that email address is registered, a password reset link has been sent.", "info")
        return RedirectResponse(url="/login", status_code=303)
        
    token = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(hours=1)
    
    await db.users.update_one(
        {"email": email},
        {"$set": {"reset_token": token, "reset_token_expiry": expiry}}
    )
    
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    reset_link = f"{scheme}://{request.url.hostname}{'' if request.url.port in [80, 443, None] else ':' + str(request.url.port)}/reset_password/{token}"
    
    # Simulating email logic for now...
    is_production = os.environ.get("VERCEL") == "1"
    print(f"[DEVELOPER MODE] Password Reset Link: {reset_link}")
    
    if is_production:
        flash(request, "If that email address is registered, a password reset link has been sent.", "success")
    else:
        flash(request, "If that email address is registered, a password reset link has been sent. [Developer Mode: Check the server console log for the link!]", "success")
        
    return RedirectResponse(url="/login", status_code=303)

@router.get("/reset_password/{token}")
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(request=request, name="reset_password.html", context= {"request": request, "token": token})

@router.post("/reset_password/{token}")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(""),
    confirm_password: str = Form("")
):
    db = request.app.state.mongo_db
    if db is None:
        flash(request, "Database connection error.", "danger")
        return RedirectResponse(url="/login", status_code=303)
        
    user = await db.users.find_one({
        "reset_token": token,
        "reset_token_expiry": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        flash(request, "The password reset token is invalid or has expired. Please request a new one.", "danger")
        return RedirectResponse(url="/forgot_password", status_code=303)
        
    if not password:
        flash(request, "Please enter a new password.", "danger")
        return templates.TemplateResponse(request=request, name="reset_password.html", context= {"request": request, "token": token})
        
    if password != confirm_password:
        flash(request, "Passwords do not match.", "danger")
        return templates.TemplateResponse(request=request, name="reset_password.html", context= {"request": request, "token": token})
        
    if len(password) < 6:
        flash(request, "Password must be at least 6 characters long.", "danger")
        return templates.TemplateResponse(request=request, name="reset_password.html", context= {"request": request, "token": token})
        
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hashed_password},
            "$unset": {"reset_token": "", "reset_token_expiry": ""}
        }
    )
    
    flash(request, "Your password has been successfully updated! Please log in with your new password.", "success")
    return RedirectResponse(url="/login", status_code=303)

@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    user = await get_current_user(request)
    if not user:
        flash(request, "Please log in.", "warning")
        return RedirectResponse(url="/login", status_code=303)
        
    db = request.app.state.mongo_db
    import ai_core
    
    if ai_core.df is not None and not ai_core.df.empty:
        user_track = user.get('track', '').lower()
        relevant_df = pd.DataFrame()
        if user_track:
            relevant_df = ai_core.df[ai_core.df['search_profile'].str.contains(user_track, case=False, na=False) | ai_core.df['title'].str.contains(user_track, case=False, na=False)]
            
        if len(relevant_df) >= 5:
            random_courses = relevant_df.sample(n=5).to_dict('records')
        elif len(relevant_df) > 0:
            relevant = relevant_df.to_dict('records')
            remaining = 5 - len(relevant)
            other_df = ai_core.df[~ai_core.df.index.isin(relevant_df.index)]
            others = other_df.sample(n=min(remaining, len(other_df))).to_dict('records') if not other_df.empty else []
            random_courses = relevant + others
        else:
            random_courses = ai_core.df.sample(n=5).to_dict('records')
            
        for i, c in enumerate(random_courses):
            c['temp_id'] = f"course_{i}"
    else:
        random_courses = []
        
    return templates.TemplateResponse(request=request, name='onboarding.html', context= {"request": request, "courses": random_courses})

@router.post("/onboarding")
async def onboarding(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    form_data = await request.form()
    db = request.app.state.mongo_db
    
    await db.users.update_one(
        {"_id": request.session['user_id']},
        {"$set": {"onboarding_preferences": dict(form_data)}}
    )
    flash(request, "Onboarding complete! Your recommendations are now personalized.", "success")
    return RedirectResponse(url="/", status_code=303)

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user = await get_current_user(request)
    if not user:
        flash(request, "Please log in.", "warning")
        return RedirectResponse(url="/login", status_code=303)
        
    taken_courses_info = []
    import ai_core
    if ai_core.df is not None and not ai_core.df.empty and user.get('taken_courses'):
        taken_urls = user.get('taken_courses', [])
        taken_df = ai_core.df[ai_core.df['url'].isin(taken_urls)]
        taken_courses_info = taken_df.to_dict('records')
        
    return templates.TemplateResponse(request=request, name="profile.html", context= {"request": request, "user": user, "taken_courses": taken_courses_info, "current_user": user})

@router.post("/profile")
async def profile(
    request: Request,
    name: str = Form(None),
    track: str = Form(None),
    career_goals: str = Form(None),
    current_skill_level: str = Form(None)
):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    db = request.app.state.mongo_db
    
    updates = {}
    if name is not None: updates["name"] = name
    if track is not None: updates["track"] = track
    if career_goals is not None: updates["career_goals"] = career_goals
    if current_skill_level is not None: updates["current_skill_level"] = current_skill_level
    
    if updates:
        await db.users.update_one({"_id": request.session['user_id']}, {"$set": updates})
        
    flash(request, "Profile updated successfully.", "success")
    return RedirectResponse(url="/profile", status_code=303)

@router.post("/delete_account")
async def delete_account(request: Request, password: str = Form("")):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    db = request.app.state.mongo_db
    if user.get('password_hash'):
        if not check_password_hash(user['password_hash'], password):
            flash(request, "Incorrect password, please try again.", "danger")
            return RedirectResponse(url="/profile", status_code=303)
            
    await db.users.delete_one({"_id": user['_id']})
    request.session.pop('user_id', None)
    flash(request, "Sorry to see you leave! Your account has been permanently deleted.", "success")
    return RedirectResponse(url="/", status_code=303)
