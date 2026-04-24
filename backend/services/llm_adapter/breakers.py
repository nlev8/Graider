"""Circuit breakers for the LLM adapter seam (Phase 5b PR 1).

Breakers wrap the RAW provider network call — retry wraps breaker.
Each raw HTTP failure counts toward fail_max=5. User errors (4xx + 429)
are excluded via _is_user_error so authentication problems and
rate-limiting don't trip the breaker.

See docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md § PR 1.
"""
from __future__ import annotations

import pybreaker

from backend.observability.events import emit

_BREAKERS: dict[tuple[str, str], pybreaker.CircuitBreaker] = {}

FAIL_MAX = 5
RESET_TIMEOUT = 60  # seconds


def _is_user_error(exc: Exception) -> bool:
    """Return True for 4xx-class errors that shouldn't count toward breaker trip.

    Retry+breaker math (Round-7 design): breaker wraps the RAW network call,
    retry wraps breaker. Each raw HTTP failure counts as one strike toward
    fail_max=5. So 5 consecutive raw 5xx/timeouts open the breaker — often
    within a single unhealthy user call since retry's exponential backoff
    keeps all 5 strikes inside one ~30-60s retry cycle. Subsequent calls
    fail-fast in nanoseconds via CircuitBreakerError.

    429 (rate limit) is EXCLUDED here — retry+backoff with Retry-After is
    the right response to throttling, not a circuit break.
    """
    name = type(exc).__name__
    user_error_names = {
        "BadRequestError",            # OpenAI, Anthropic — 400
        "AuthenticationError",        # OpenAI, Anthropic — 401
        "PermissionDeniedError",      # OpenAI, Anthropic — 403
        "NotFoundError",              # OpenAI — 404
        "UnprocessableEntityError",   # OpenAI — 422
        "RateLimitError",             # OpenAI, Anthropic — 429 (excluded per design)
    }
    if name in user_error_names:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int):
        if status == 429 or (400 <= status < 500 and status != 408):
            return True
    return False


class _BreakerListener(pybreaker.CircuitBreakerListener):
    """Emits observability events on breaker state transitions."""

    def __init__(self, provider: str, model: str):
        self._provider = provider
        self._model = model

    def state_change(self, cb, old_state, new_state):
        emit(
            "llm.breaker.state_change",
            provider=self._provider,
            model=self._model,
            from_state=getattr(old_state, "name", None) or "initial",
            to_state=getattr(new_state, "name", None) or "unknown",
        )


def get_breaker(provider: str, model: str) -> pybreaker.CircuitBreaker:
    """Return (creating if needed) the breaker for this provider+model.

    Breakers are module-level singletons per Gunicorn worker. Cross-worker
    state is NOT shared — Phase 5c may add Redis-backed sharing. With N
    workers, effective fail_max is N x FAIL_MAX before every worker trips.
    """
    key = (provider, model)
    if key not in _BREAKERS:
        _BREAKERS[key] = pybreaker.CircuitBreaker(
            fail_max=FAIL_MAX,
            reset_timeout=RESET_TIMEOUT,
            exclude=[_is_user_error],
            listeners=[_BreakerListener(provider, model)],
            # Preserve the original exception on the tripping failure —
            # only subsequent (fast-fail) calls surface CircuitBreakerError.
            # Keeps retry logic's exception-classification stable: a 5xx
            # that happens to be the fail_max-th strike still reaches retry
            # as a 5xx, not as a CircuitBreakerError.
            throw_new_error_on_trip=False,
        )
    return _BREAKERS[key]
