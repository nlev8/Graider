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

# Phase 4.6: in production, REDIS_URL is required. Without it, each gunicorn
# worker has its own in-memory rate-limit counter, so an advertised "10/min"
# limit becomes effectively N * 10/min (N = worker count) and an attacker can
# cycle connections across workers to bypass the limit entirely. Fail fast
# rather than warn-and-continue — the warning was silent noise operators
# could miss and led to no real enforcement in prod.
if not redis_url and not is_dev:
    raise RuntimeError(
        "REDIS_URL is required in production for flask-limiter. "
        "Without it, rate limits are per-worker (bypassable). "
        "Set REDIS_URL on the Railway service, OR set FLASK_ENV=development "
        "for local dev. This is a hard requirement as of Phase 4.6."
    )

if not redis_url:
    logging.getLogger(__name__).info(
        "REDIS_URL not set; running in dev mode with per-worker in-memory rate limits."
    )

# Phase 4.6: global default tightened from 200/min → 100/min. Per-route
# explicit @limiter.limit(...) decorators override this for endpoints that
# need tighter (auth, writes) or looser (dashboards, polling) limits.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],
    storage_uri=redis_url or "memory://",
)
