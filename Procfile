web: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --graceful-timeout 30 --max-requests 1000 --max-requests-jitter 50
worker: celery -A backend.celery_app worker --loglevel=info --pool=prefork --concurrency=8
