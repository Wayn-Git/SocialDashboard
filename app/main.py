# app/main.py
from fastapi import FastAPI, Depends
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