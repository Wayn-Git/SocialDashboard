# app/worker/celery_app.py
from celery import Celery
from celery.schedules import crontab
from app.config import settings

app = Celery("agency_sync", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

app.conf.task_routes = {
    "app.worker.tasks.sync_page_facebook": {"queue": "fb-queue"},
    "app.worker.tasks.sync_page_instagram": {"queue": "ig-queue"},
    "app.worker.tasks.sync_page_linkedin": {"queue": "li-queue"},
}

app.conf.beat_schedule = {
    "hourly-sync": {
        "task": "app.worker.tasks.sync_all_employees",
        "schedule": crontab(minute=0),
    },
    "daily-discovery": {
        "task": "app.worker.tasks.discover_all_employees",
        "schedule": crontab(hour=2, minute=30),
    },
    "daily-token-refresh": {
        "task": "app.worker.tasks.refresh_expiring_tokens",
        "schedule": crontab(hour=3, minute=0),
    },
}