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
#
# 2026-05-20 hotfix #5: STARTUP REDIS PROBE + storage_options bounds.
#
# Hotfix #3 added in_memory_fallback_enabled=True, but in_memory_fallback
# only kicks in when the storage backend RAISES an exception. The
# 2026-05-19 Railway/GCP incident exposed the case where Redis is
# unreachable in a way that makes redis-py's internal connection-retry
# loop HANG (no exception ever raised) until gunicorn's worker timeout
# fires SIGABRT → SystemExit(1). The fallback never fired because the
# call never returned. Sentry traces showed the worker stuck deep in
# limits/storage/redis.py:incr → flask-limiter's own internal redis
# client (separate from the redis.from_url calls in app.py).
#
# Fix has two layers:
#
# 1. STARTUP PROBE: at module import, probe Redis with a bounded connect
#    (~2s, no retries). If reachable, use the configured Redis URL as the
#    storage. If unreachable:
#      - in DEV/TEST (is_dev): fall back to memory:// for the entire
#        process lifetime — the limiter never even tries to talk to broken
#        Redis at request time, so workers can't get stuck in its retry
#        loop. Sessions are per-worker in this mode (matches the existing
#        flask-session filesystem fallback in app.py from hotfix #3).
#      - in PRODUCTION: raise RuntimeError → non-zero exit (2026-06-10,
#        hardening sprint PR1 sub-item / 2026-06-09 reconciliation ruling).
#        The original hotfix #5 fell back to memory:// in prod too, which
#        is fail-OPEN: rate limits silently became per-worker (bypassable)
#        for the process lifetime. A Redis that is unreachable AT BOOT is
#        a config/infra error in the same class as a missing REDIS_URL —
#        fail the deploy loudly (Railway keeps the previous image serving)
#        rather than boot with unenforceable limits.
#
# 2. storage_options BOUNDS: passed to the Limiter so that IF Redis was
#    reachable at startup but becomes unreachable later (network blip),
#    the limiter's redis client fails fast (~2s, no retries) instead of
#    hanging. in_memory_fallback_enabled then correctly catches the
#    raised exception and degrades per-request. This RUNTIME degradation
#    path is deliberate and unchanged — a transient outage mid-flight
#    should degrade, not crash a serving worker; only the STARTUP probe
#    fails closed.
#
# The hard config requirement at the top of this file (REDIS_URL must be
# SET in production) still raises at import — startup failures (config
# missing, or probe failure in prod) are fail-fast; only post-boot
# transient outages degrade.

_storage_uri = redis_url or "memory://"
_storage_options: dict = {}

if redis_url:
    try:
        import redis as _redis_lib
        from redis.backoff import NoBackoff as _NoBackoff
        from redis.retry import Retry as _Retry

        _probe = _redis_lib.from_url(
            redis_url,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            retry=_Retry(_NoBackoff(), retries=0),
        )
        _probe.ping()
        # Redis reachable at startup — use it, with bounded options so a
        # later transient unreachable fails fast and lets the fallback fire.
        _storage_options = {
            "socket_timeout": 2.0,
            "socket_connect_timeout": 2.0,
            "retry": _Retry(_NoBackoff(), retries=0),
        }
        logging.getLogger(__name__).info(
            "Redis reachable at startup; flask-limiter using Redis storage."
        )
    except Exception as _redis_err:
        if not is_dev:
            # PRODUCTION fails CLOSED (2026-06-10): booting with memory://
            # would mean per-worker, bypassable rate limits for the process
            # lifetime — fail the deploy instead, same as missing REDIS_URL.
            raise RuntimeError(
                "Redis is configured (REDIS_URL set) but unreachable at startup: "
                f"{_redis_err!r}. Refusing to start with per-worker memory:// "
                "rate limits in production (fail-closed). Fix Redis "
                "reachability from this service, or set FLASK_ENV=development "
                "for local dev."
            ) from _redis_err
        # DEV/TEST: Redis unreachable at startup — fall back to memory:// so
        # the limiter never tries to talk to broken Redis at request time.
        # Rate limits become per-worker in-memory for this process lifetime;
        # bypassable but the app serves users correctly. Restart pods to
        # pick Redis back up once it recovers.
        logging.getLogger(__name__).warning(
            "Redis unreachable at startup (%s); flask-limiter falling back "
            "to memory:// for this process lifetime. Restart workers once "
            "Redis recovers to pick the shared backend back up.",
            _redis_err,
        )
        _storage_uri = "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"],
    storage_uri=_storage_uri,
    storage_options=_storage_options,
    in_memory_fallback_enabled=True,
)
