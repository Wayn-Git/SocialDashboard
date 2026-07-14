# app/main.py
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from app.api import oauth, analytics
from app.database import Base, engine

app = FastAPI(title="Multi-Client Social Media Analytics Dashboard")

# Create tables (In prod, use Alembic migrations)
Base.metadata.create_all(bind=engine)

app.include_router(oauth.router, prefix="/auth", tags=["OAuth"])
app.include_router(analytics.router, prefix="/api", tags=["Analytics"])

@app.get("/")
def health_check():
    return {"status": "healthy", "version": "1.0"}

@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return """
    <html>
        <head><title>Privacy Policy</title></head>
        <body style="font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6;">
            <h1>Privacy Policy & Data Deletion Instructions</h1>
            <p><em>Last Updated: July 2026</em></p>
            
            <h3>1. Information We Collect</h3>
            <p>When you connect your Facebook or Instagram account to our application, we collect your basic profile information and access tokens. We use these tokens to securely fetch analytics and engagement data for your social media pages on behalf of our agency.</p>
            
            <h3>2. How We Use Your Information</h3>
            <p>The data we pull from Facebook and Instagram is strictly used to generate analytics reports and dashboards for our internal agency operations and client reporting. We do not sell your data, we do not share it with any third parties, and we do not use it for external marketing.</p>
            
            <h3>3. Data Security</h3>
            <p>All access tokens are encrypted using AES-256 military-grade encryption before being stored in our secure database.</p>
            
            <h3>4. Data Deletion Instructions</h3>
            <p>If you wish to revoke our access and have your data completely deleted from our servers, you can do so at any time:</p>
            <ol>
                <li>Go to your Facebook account's "Settings & Privacy".</li>
                <li>Click on "Settings" -> "Security and Login" -> "Business Integrations" (or "Apps and Websites").</li>
                <li>Find our application in the list and click "Remove".</li>
                <li>To request full deletion of all historical analytics data from our database, please contact our agency directly or email the developer. We will purge all associated records within 48 hours of your request.</li>
            </ol>
        </body>
    </html>
    """