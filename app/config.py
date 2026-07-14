# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://user:pass@localhost:5432/agency"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    JWT_SECRET_KEY: str = "super-secret-rs256-key"
    MASTER_ENCRYPTION_KEY: str = "change-this-to-a-long-random-string-in-production"
    
    # Meta
    FB_APP_ID: str = "your-fb-app-id"
    FB_APP_SECRET: str = "your-fb-app-secret"
    FB_REDIRECT_URI: str = "http://localhost:8000/auth/facebook/callback"
    
    # LinkedIn
    LI_CLIENT_ID: str = "your-li-client-id"
    LI_CLIENT_SECRET: str = "your-li-client-secret"
    LI_REDIRECT_URI: str = "http://localhost:8000/auth/linkedin/callback"

settings = Settings()