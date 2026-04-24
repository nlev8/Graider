"""Unified retry-with-exponential-backoff utility for external API calls.

Inspired by Claude Code's withRetry.ts. Provides a single retry pattern
for all external service calls (OpenAI, Anthropic, Supabase, Clever, etc.).
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DELAY_S = 0.5
MAX_DELAY_S = 32.0
MAX_RETRIES = 5
JITTER_FACTOR = 0.25
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504, 529}

_TRANSIENT_KEYWORDS = [
    "connection reset",
    "connection refused",
    "connection aborted",
    "temporary failure",
    "timed out",
    "timeout",
    "server disconnected",
    "broken pipe",
    "bad gateway",
    "service unavailable",
    "internal server error",
    "rate limit",
    "overloaded",
    "capacity",
    "try again",
    "temporarily unavailable",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_status_code(error):
    """Extract HTTP status code from an exception, if available."""
    code = getattr(error, "status_code", None)
    if code is not None:
        return code
    resp = getattr(error, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if code is not None:
            return code
    return None


def _get_retry_after(error):
    """Extract Retry-After header value from an exception's response."""
    resp = getattr(error, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    return headers.get("Retry-After") or headers.get("retry-after")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_retry_delay(attempt, retry_after=None, max_delay_s=MAX_DELAY_S):
    """Compute delay in seconds for a given retry attempt.

    Args:
        attempt: 1-based attempt number.
        retry_after: Optional Retry-After header value (numeric string).
        max_delay_s: Maximum delay cap in seconds.

    Returns:
        Delay in seconds (float).
    """
    # Honour Retry-After if it parses as a valid positive number.
    if retry_after is not None:
        try:
            ra = float(retry_after)
            if ra > 0:
                return ra
        except (ValueError, TypeError):
            pass  # fall through to exponential backoff

    base = BASE_DELAY_S * (2 ** (attempt - 1))
    base = min(base, max_delay_s)
    jitter = random.random() * JITTER_FACTOR * base
    return base + jitter


def is_retryable_error(error):
    """Determine whether *error* is transient and worth retrying.

    Returns True for HTTP 408/429/5xx/529, ConnectionError, TimeoutError,
    OSError, and exceptions whose string representation contains transient
    keywords.  Returns False for client errors (400, 401, 403, 404) and
    ordinary programming errors (ValueError, TypeError, etc.).
    """
    # Network / OS-level errors are always retryable.
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True

    status = _get_status_code(error)
    if status is not None:
        return status in RETRYABLE_STATUS_CODES

    # Keyword matching on the string representation.
    err_str = str(error).lower()
    for keyword in _TRANSIENT_KEYWORDS:
        if keyword in err_str:
            return True

    return False


def with_retry(fn, max_retries=MAX_RETRIES, label="", max_delay_s=MAX_DELAY_S, non_retryable=()):
    """Call *fn()* with automatic retry on transient failures.

    Args:
        fn: No-argument callable.
        max_retries: Maximum number of retry attempts (after the initial call).
        label: Human-readable label for log messages.
        max_delay_s: Maximum backoff delay in seconds.
        non_retryable: Tuple of exception classes that should propagate
            immediately without retry, even if they'd match
            is_retryable_error(). Used for pybreaker.CircuitBreakerError
            so open-circuit raises fail-fast rather than backing off.

    Returns:
        The return value of *fn()* on success.

    Raises:
        The last exception if all retries are exhausted, or a non-retryable
        exception immediately.
    """
    tag = f"[{label}] " if label else ""
    last_error = None

    for attempt in range(1, max_retries + 2):  # 1 initial + max_retries retries
        try:
            return fn()
        except Exception as exc:
            last_error = exc

            if non_retryable and isinstance(exc, non_retryable):
                raise

            if not is_retryable_error(exc):
                raise

            if attempt > max_retries:
                # Exhausted all retries.
                logger.error(
                    "%sAll %d retries exhausted. Last error: %s",
                    tag, max_retries, exc,
                )
                raise

            retry_after = _get_retry_after(exc)
            delay = get_retry_delay(attempt, retry_after=retry_after, max_delay_s=max_delay_s)
            logger.warning(
                "%sAttempt %d/%d failed (%s). Retrying in %.2fs...",
                tag, attempt, max_retries + 1, exc, delay,
            )
            time.sleep(delay)

    # Should never reach here, but just in case.
    raise last_error  # type: ignore[misc]
