"""
Shared Flask extensions for Graider.
Import these in blueprints to avoid circular imports with app.py.
"""
import os
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

redis_url = os.getenv('REDIS_URL')
is_dev = os.getenv('FLASK_ENV', '').lower() in ('development', 'dev', 'testing', 'test')
if not redis_url and not is_dev:
    logging.getLogger(__name__).warning(
        "REDIS_URL not set in production — rate limits are per-worker and easily bypassed. "
        "Set REDIS_URL for shared rate limiting across gunicorn workers."
    )

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=redis_url or "memory://",
)
