"""Unified retry-with-exponential-backoff utility for external API calls.

Inspired by Claude Code's withRetry.ts. Provides a single retry pattern
for all external service calls (OpenAI, Anthropic, Supabase, Clever, etc.).
"""

import logging
import random
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_DELAY_S = 0.5
MAX_DELAY_S = 32.0
MAX_RETRIES = 5
JITTER_FACTOR = 0.25
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504, 529}

# LLM SDK exception classes whose names indicate transient failures.
# Matched by class name only — avoids hard imports of optional deps so
# the classifier works whether or not openai/anthropic/google-genai are
# installed in the venv. Codex audit MAJOR #7 round-2: APIConnectionError
# in openai/anthropic doesn't subclass builtin ConnectionError and
# stringifies as "Connection error." which is too short for the keyword
# loop below — needs an explicit class-name check.
_TRANSIENT_CLASS_NAMES = frozenset({
    # openai>=1.0
    "APIConnectionError",   # also matches anthropic.APIConnectionError
    "APITimeoutError",
    "RateLimitError",
    "InternalServerError",
    # NOTE: APIStatusError deliberately NOT in this set (Codex round-2 round-2).
    # It's a generic wrapper covering ALL HTTP statuses including 400/401, so
    # class-name match would cause 4xx false positives. It falls through to
    # _get_status_code below, which correctly classifies by status code.
    # google.api_core
    "ServiceUnavailable",
    "DeadlineExceeded",
    "ResourceExhausted",
    # google.genai
    "ServerError",
    # urllib3 / requests
    "MaxRetryError",
    "ProtocolError",
    "RemoteDisconnected",
    "IncompleteRead",
    # httpx
    "TimeoutException",
    "ConnectTimeout",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "ConnectError",
    "ReadError",
    "WriteError",
    "RemoteProtocolError",
    "NetworkError",
})

_TRANSIENT_KEYWORDS = [
    "connection reset",
    "connection refused",
    "connection aborted",
    "connection error",         # openai.APIConnectionError stringifies as this
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

def _get_status_code(error: BaseException) -> int | None:
    """Extract HTTP status code from an exception, if available."""
    code = getattr(error, "status_code", None)
    if code is not None:
        try:
            return int(code)
        except (ValueError, TypeError):
            return None
    resp = getattr(error, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if code is not None:
            try:
                return int(code)
            except (ValueError, TypeError):
                return None
    return None


def _get_retry_after(error: BaseException) -> str | None:
    """Extract Retry-After header value from an exception's response."""
    resp = getattr(error, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    value: str | None = headers.get("Retry-After") or headers.get("retry-after")
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_retry_delay(
    attempt: int,
    retry_after: str | int | float | None = None,
    max_delay_s: float = MAX_DELAY_S,
) -> float:
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

    base: float = BASE_DELAY_S * (2 ** (attempt - 1))
    base = min(base, max_delay_s)
    jitter = random.random() * JITTER_FACTOR * base
    return base + jitter


def is_retryable_error(error: BaseException) -> bool:
    """Determine whether *error* is transient and worth retrying.

    Returns True for HTTP 408/429/5xx/529, ConnectionError, TimeoutError,
    OSError, exception class names that match known LLM SDK transient
    types (e.g., openai.APIConnectionError, anthropic.APIConnectionError),
    and exceptions whose string representation contains transient keywords.
    Returns False for client errors (400, 401, 403, 404) and ordinary
    programming errors (ValueError, TypeError, etc.).
    """
    # Network / OS-level errors are always retryable.
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True

    # LLM SDK class-name match (Codex audit MAJOR #7 round-2).
    # openai.APIConnectionError + anthropic.APIConnectionError do NOT
    # subclass builtin ConnectionError, stringify as "Connection error."
    # (too short for the keyword loop), and don't expose .status_code.
    # Match by class name to avoid hard imports of optional deps.
    cls_name = type(error).__name__
    if cls_name in _TRANSIENT_CLASS_NAMES:
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


def with_retry(
    fn: Callable[[], Any],
    max_retries: int = MAX_RETRIES,
    label: str = "",
    max_delay_s: float = MAX_DELAY_S,
    non_retryable: tuple[type[BaseException], ...] = (),
) -> Any:
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
    assert last_error is not None
    raise last_error
