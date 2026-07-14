# app/api/analytics.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Post, PostMetric, SocialPage
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/clients/{client_id}/posts")
def get_client_posts(client_id: str, days: int = Query(7, alias="days"), db: Session = Depends(get_db)):
    """
    Read-only endpoint querying PostgreSQL. No external API calls.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    
    posts = (
        db.query(
            Post.id,
            Post.platform,
            Post.caption,
            Post.permalink_url,
            Post.created_at,
            func.max(PostMetric.likes).label('likes'),
            func.max(PostMetric.comments).label('comments'),
            func.max(PostMetric.shares).label('shares')
        )
        .join(PostMetric, Post.id == PostMetric.post_id)
        .join(SocialPage, Post.page_id == SocialPage.id)
        .filter(SocialPage.client_id == client_id)
        .filter(Post.created_at >= since_date)
        .group_by(Post.id)
        .order_by(Post.created_at.desc())
        .all()
    )
    
    return {
        "client_id": client_id,
        "window_days": days,
        "posts": [
            {
                "id": str(p.id),
                "platform": p.platform.value,
                "caption": p.caption,
                "url": p.permalink_url,
                "created_at": p.created_at.isoformat(),
                "metrics": {
                    "likes": p.likes,
                    "comments": p.comments,
                    "shares": p.shares
                }
            } for p in posts
        ]
    }