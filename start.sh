#!/bin/bash

# Start the Celery worker and beat schedule in the background (&)
celery -A app.api.worker.celery_app worker --beat -l info -Q fb-queue,ig-queue,li-queue &

# Start the FastAPI web server in the foreground
uvicorn app.main:app --host 0.0.0.0 --port $PORT
