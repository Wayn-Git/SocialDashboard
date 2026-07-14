# app/worker/tasks.py
import httpx
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.worker.celery_app import app
from app.database import SessionLocal
from app.models import Employee, SocialPage, SyncJob, SyncStatus, SyncJobType
from app.security import vault
from app.integrations.platforms import FacebookAPI, LinkedInAPI, PlatformAPIError


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.task(bind=True)
def sync_all_employees(self):
    db: Session = next(get_db())
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    for emp in employees:
        sync_employee.delay(str(emp.id))
    return {"enqueued": len(employees)}

@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=60, max_retries=3, retry_jitter=True)
def sync_employee(self, employee_id: str):
    db: Session = next(get_db())
    emp = db.query(Employee).get(employee_id)
    if not emp: return
    
    # Token refresh logic would go here...
    
    pages = db.query(SocialPage).filter(
        SocialPage.employee_id == emp.id, 
        SocialPage.is_active == True
    ).all()
    
    for page in pages:
        task_name = f"app.worker.tasks.sync_page_{page.platform.value}"
        app.send_task(task_name, args=[str(page.id)], queue=f"{page.platform.value}-queue")

# Inside app/worker/tasks.py

@app.task(bind=True, autoretry_for=(PlatformAPIError, httpx.HTTPStatusError), retry_backoff=60, max_retries=3)
def sync_page_facebook(self, page_id: str):
    db: Session = next(get_db())
    page = db.query(SocialPage).get(page_id)
    
    # Decrypt token
    plaintext_token = vault.decrypt(page.enc_page_access_token, page.enc_data_key, page.page_token_iv)
    
    try:
        # Use the integration layer!
        posts = FacebookAPI.fetch_posts(
            page_id=page.platform_page_id, 
            access_token=plaintext_token, 
            days=7
        )
        
        # Upsert logic to DB...
        for p_data in posts:
            # Insert into posts table (ON CONFLICT DO UPDATE)
            # Insert into post_metrics table (ON CONFLICT DO UPDATE)
            pass
            
        page.last_synced_at = datetime.utcnow()
        db.commit()
        
    finally:
        del plaintext_token # Zero out memory (Chapter 10.4)