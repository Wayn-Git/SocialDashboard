# app/api/oauth.py
import uuid
import secrets
from datetime import datetime, timedelta
import redis
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmployeeOAuthToken, SocialPage, PlatformType, TokenStatus
from app.security import vault
from app.api.worker.tasks import sync_employee

router = APIRouter()
redis_url = settings.REDIS_URL
if "CERT_NONE" in redis_url:
    redis_url = redis_url.replace("CERT_NONE", "none")
redis_client = redis.from_url(redis_url, decode_responses=True)

@router.get("/facebook/start")
def fb_start(employee_id: uuid.UUID = Query(...)):
    state = secrets.token_urlsafe(32)
    # Store employee_id in Redis with an expiration of 15 minutes
    redis_client.setex(f"csrf_state:{state}", timedelta(minutes=15), str(employee_id))
    
    auth_url = (
        "https://www.facebook.com/v19.0/dialog/oauth"
        f"?client_id={settings.FB_APP_ID}"
        f"&redirect_uri={settings.FB_REDIRECT_URI}"
        "&scope=pages_show_list,pages_read_engagement,pages_read_user_content,"
        "pages_manage_metadata,instagram_basic,instagram_manage_insights,business_management"
        f"&state={state}"
    )
    return RedirectResponse(auth_url)

@router.get("/facebook/callback")
def fb_callback(code: str, state: str, db: Session = Depends(get_db)):
    employee_id_str = redis_client.get(f"csrf_state:{state}")
    if not employee_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired state token.")
    
    redis_client.delete(f"csrf_state:{state}")
    employee_id = uuid.UUID(employee_id_str)

    with httpx.Client() as client:
        # 1. Exchange code for short-lived token
        token_resp = client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": settings.FB_APP_ID,
                "client_secret": settings.FB_APP_SECRET,
                "redirect_uri": settings.FB_REDIRECT_URI,
                "code": code
            }
        )
        if token_resp.status_code != 200:
            error_details = token_resp.text
            print(f"Facebook Token Error: {error_details}")
            raise HTTPException(status_code=400, detail=f"Failed to exchange code for token. Facebook said: {error_details}")
            
        token_data = token_resp.json()
        short_lived_token = token_data.get("access_token")

        # 2. Exchange for long-lived token
        ll_resp = client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.FB_APP_ID,
                "client_secret": settings.FB_APP_SECRET,
                "fb_exchange_token": short_lived_token
            }
        )
        
        if ll_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get long-lived token")
            
        ll_data = ll_resp.json()
        long_lived_token = ll_data.get("access_token")
        
        # Calculate expiration time, typically 60 days
        expires_in = ll_data.get("expires_in", 60 * 60 * 24 * 60)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Fetch employee details from FB
        me_resp = client.get(
            "https://graph.facebook.com/v19.0/me",
            params={"access_token": long_lived_token, "fields": "id,name"}
        )
        provider_user_id = None
        provider_username = None
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            provider_user_id = me_data.get("id")
            provider_username = me_data.get("name")

        # Encrypt the token
        ct, enc_key, iv = vault.encrypt(long_lived_token)
        
        # Upsert employee token
        existing_token = db.query(EmployeeOAuthToken).filter_by(employee_id=employee_id, provider=PlatformType.facebook).first()
        if existing_token:
            existing_token.enc_access_token = ct
            existing_token.enc_data_key = enc_key
            existing_token.token_iv = iv
            existing_token.expires_at = expires_at
            existing_token.provider_user_id = provider_user_id
            existing_token.provider_username = provider_username
            existing_token.refresh_status = TokenStatus.active
        else:
            new_token = EmployeeOAuthToken(
                employee_id=employee_id,
                provider=PlatformType.facebook,
                enc_access_token=ct,
                enc_data_key=enc_key,
                token_iv=iv,
                expires_at=expires_at,
                provider_user_id=provider_user_id,
                provider_username=provider_username
            )
            db.add(new_token)
        db.commit()

        # Fetch Pages
        pages_resp = client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": long_lived_token, "limit": 100}
        )
        
        if pages_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch pages")
            
        pages_data = pages_resp.json().get("data", [])
        
        fb_page_count = 0
        ig_account_count = 0

        for page in pages_data:
            page_id = page.get("id")
            page_name = page.get("name")
            page_access_token = page.get("access_token")
            
            ct_page, enc_key_page, iv_page = vault.encrypt(page_access_token)
            
            # Check for Instagram Business Account
            ig_resp = client.get(
                f"https://graph.facebook.com/v19.0/{page_id}",
                params={"fields": "instagram_business_account", "access_token": page_access_token}
            )
            
            ig_account_id = None
            if ig_resp.status_code == 200:
                ig_data = ig_resp.json()
                ig_business_account = ig_data.get("instagram_business_account")
                if ig_business_account:
                    ig_account_id = ig_business_account.get("id")
            
            # Upsert FB Page
            fb_page = db.query(SocialPage).filter_by(
                employee_id=employee_id,
                platform=PlatformType.facebook,
                platform_page_id=page_id
            ).first()
            
            if fb_page:
                fb_page.page_name = page_name
                fb_page.enc_page_access_token = ct_page
                fb_page.enc_data_key = enc_key_page
                fb_page.page_token_iv = iv_page
                fb_page.ig_business_account_id = ig_account_id
                fb_page.is_active = True
            else:
                new_fb_page = SocialPage(
                    employee_id=employee_id,
                    platform=PlatformType.facebook,
                    platform_page_id=page_id,
                    page_name=page_name,
                    enc_page_access_token=ct_page,
                    enc_data_key=enc_key_page,
                    page_token_iv=iv_page,
                    ig_business_account_id=ig_account_id,
                    is_active=True
                )
                db.add(new_fb_page)
            
            fb_page_count += 1
            
            # Upsert IG Account if exists
            if ig_account_id:
                ig_page = db.query(SocialPage).filter_by(
                    employee_id=employee_id,
                    platform=PlatformType.instagram,
                    platform_page_id=ig_account_id
                ).first()
                
                # Note: For IG, we also store the FB page access token since IG Graph API calls use it!
                if ig_page:
                    ig_page.page_name = f"{page_name} (Instagram)"
                    ig_page.enc_page_access_token = ct_page
                    ig_page.enc_data_key = enc_key_page
                    ig_page.page_token_iv = iv_page
                    ig_page.is_active = True
                else:
                    new_ig_page = SocialPage(
                        employee_id=employee_id,
                        platform=PlatformType.instagram,
                        platform_page_id=ig_account_id,
                        page_name=f"{page_name} (Instagram)",
                        enc_page_access_token=ct_page,
                        enc_data_key=enc_key_page,
                        page_token_iv=iv_page,
                        is_active=True
                    )
                    db.add(new_ig_page)
                ig_account_count += 1
                
        db.commit()
        
        # Enqueue sync_employee task immediately
        sync_employee.delay(str(employee_id))
        
        html_content = f"""
        <html>
            <head><title>Success</title></head>
            <body style="font-family: sans-serif; text-align: center; margin-top: 50px;">
                <h1>Authentication Successful!</h1>
                <p>Successfully connected to Facebook.</p>
                <p>Discovered <strong>{{fb_page_count}}</strong> Facebook Pages.</p>
                <p>Discovered <strong>{{ig_account_count}}</strong> Instagram Business Accounts.</p>
                <p>Background synchronization has been started.</p>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content)