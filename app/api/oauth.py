# app/api/oauth.py
from fastapi import APIRouter, Request
from httpx import AsyncClient
from app.config import settings

router = APIRouter()

@router.get("/facebook/start")
async def fb_start(request: Request):
    # Generate CSRF state token and store in session
    state = "random_csrf_state"
    auth_url = (
        "https://www.facebook.com/v19.0/dialog/oauth"
        f"?client_id={settings.FB_APP_ID}"
        f"&redirect_uri={settings.FB_REDIRECT_URI}"
        "&scope=pages_show_list,pages_read_engagement,pages_read_user_content,"
        "pages_manage_metadata,instagram_basic,instagram_manage_insights,business_management"
        f"&state={state}"
    )
    return {"auth_url": auth_url}

@router.get("/facebook/callback")
async def fb_callback(code: str, state: str):
    # 1. Verify state
    # 2. Exchange code for short-lived token
    # 3. Exchange short-lived for long-lived (60 days)
    # 4. Discover pages via /me/accounts
    # 5. Encrypt page tokens via TokenVault
    # 6. Persist to DB
    return {"status": "Authentication successful, pages discovering in background."}