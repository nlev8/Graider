"""
Shared Flask extensions for Graider.
Import these in blueprints to avoid circular imports with app.py.
"""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

redis_url = os.getenv('REDIS_URL')
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=redis_url or "memory://",
)
