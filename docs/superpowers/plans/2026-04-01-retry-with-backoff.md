# Retry with Exponential Backoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified retry-with-exponential-backoff utility (inspired by Claude Code's `withRetry.ts`) and apply it to all unprotected AI API calls across Graider.

**Architecture:** Create a single `backend/retry.py` module exporting a `with_retry()` wrapper function. It uses exponential backoff (0.5s base, 2x growth, 25% jitter, 32s cap) with Retry-After header support. Apply the wrapper to all unprotected OpenAI/Anthropic/Gemini call sites in `assignment_grader.py`, `planner_routes.py`, and other route files. Migrate the existing `storage.py` retry to use the shared utility. (A `@retryable` decorator is intentionally omitted — YAGNI; all current call sites use the inline `with_retry(lambda: ...)` pattern.)

**Tech Stack:** Python 3.11, `time.sleep`, `random`, `logging`, `unittest.mock` for tests

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/retry.py` | **Create** | Unified retry utility: `with_retry()`, `is_retryable_error()`, `get_retry_delay()` |
| `tests/test_retry.py` | **Create** | Unit tests for retry module (backoff math, error classification, max retries, jitter, Retry-After) |
| `assignment_grader.py` | **Modify** | Wrap all `client.messages.create()`, `client.chat.completions.create()`, `gemini_client.generate_content()` calls |
| `backend/routes/planner_routes.py` | **Modify** | Wrap all `client.chat.completions.create()` calls |
| `backend/routes/grading_routes.py` | **Modify** | Wrap `client.messages.create()` call |
| `backend/routes/lesson_routes.py` | **Modify** | Wrap `client.messages.create()` call |
| `backend/routes/assignment_routes.py` | **Modify** | Wrap `client.chat.completions.create()` call |
| `backend/routes/assignment_player_routes.py` | **Modify** | Wrap `client.chat.completions.create()` call |
| `backend/storage.py` | **Modify** | Delete `_retry_supabase()`, replace all 6 retry sites with `with_retry()` |

---

### Task 1: Create the retry utility module

**Files:**
- Create: `backend/retry.py`
- Test: `tests/test_retry.py`

- [ ] **Step 1: Write the failing tests for `get_retry_delay()`**

Create `tests/test_retry.py`:

```python
"""Tests for backend/retry.py — exponential backoff utility."""

import time
import pytest
from unittest.mock import patch, MagicMock


def test_get_retry_delay_base_case():
    """First attempt should return ~500ms (plus up to 25% jitter)."""
    from backend.retry import get_retry_delay
    delay = get_retry_delay(attempt=1)
    assert 0.5 <= delay <= 0.625  # 500ms + up to 25% jitter


def test_get_retry_delay_exponential_growth():
    """Delays should double each attempt: 0.5, 1, 2, 4, 8, 16, 32."""
    from backend.retry import get_retry_delay
    # Use fixed seed for deterministic jitter
    with patch('backend.retry.random.random', return_value=0):
        delays = [get_retry_delay(a) for a in range(1, 8)]
    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]


def test_get_retry_delay_caps_at_max():
    """Delay should never exceed max_delay_s (default 32s)."""
    from backend.retry import get_retry_delay
    with patch('backend.retry.random.random', return_value=0):
        delay = get_retry_delay(attempt=10)
    assert delay == 32.0


def test_get_retry_delay_custom_max():
    """Custom max_delay_s should cap the delay."""
    from backend.retry import get_retry_delay
    with patch('backend.retry.random.random', return_value=0):
        delay = get_retry_delay(attempt=5, max_delay_s=5.0)
    assert delay == 5.0


def test_get_retry_delay_retry_after_header():
    """Retry-After header value should override calculated delay."""
    from backend.retry import get_retry_delay
    delay = get_retry_delay(attempt=1, retry_after="3")
    assert delay == 3.0


def test_get_retry_delay_retry_after_invalid_ignored():
    """Non-numeric Retry-After should fall back to calculated delay."""
    from backend.retry import get_retry_delay
    delay = get_retry_delay(attempt=1, retry_after="not-a-number")
    assert 0.5 <= delay <= 0.625


def test_get_retry_delay_has_jitter():
    """Jitter should add 0-25% of base delay."""
    from backend.retry import get_retry_delay
    with patch('backend.retry.random.random', return_value=1.0):
        delay = get_retry_delay(attempt=1)
    # base=0.5, jitter=0.25*0.5*1.0=0.125 → 0.625
    assert delay == 0.625
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.retry'`

- [ ] **Step 3: Implement `get_retry_delay()`**

Create `backend/retry.py`:

```python
"""
Retry with Exponential Backoff
==============================
Unified retry utility for all external API calls (OpenAI, Anthropic, Gemini,
Supabase). Inspired by Claude Code's withRetry.ts pattern.

Usage — wrapper style (preferred for existing call sites):
    result = with_retry(lambda: client.chat.completions.create(...))

Usage — with logging context:
    result = with_retry(
        lambda: client.messages.create(...),
        label="grade_per_question",
    )

Backoff strategy:
    0.5s * 2^(attempt-1), capped at 32s, with 0-25% jitter.
    Respects Retry-After header when present.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

# ── Constants (aligned with Claude Code's withRetry.ts) ──────────────────
BASE_DELAY_S = 0.5          # 500ms initial delay
MAX_DELAY_S = 32.0          # Cap at 32 seconds
MAX_RETRIES = 5             # 5 retries = 6 total attempts
JITTER_FACTOR = 0.25        # 0-25% random jitter

# HTTP status codes that warrant a retry
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504, 529}


def get_retry_delay(attempt, retry_after=None, max_delay_s=MAX_DELAY_S):
    """Calculate delay for a given retry attempt.

    Args:
        attempt: 1-based attempt number (1 = first retry).
        retry_after: Value from Retry-After header (string, seconds).
        max_delay_s: Maximum delay cap in seconds.

    Returns:
        Delay in seconds (float).
    """
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            pass  # Fall through to calculated delay

    base = min(BASE_DELAY_S * (2 ** (attempt - 1)), max_delay_s)
    jitter = random.random() * JITTER_FACTOR * base
    return base + jitter
```

- [ ] **Step 4: Run tests to verify `get_retry_delay` tests pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v -k "get_retry_delay"`
Expected: All 7 `test_get_retry_delay_*` tests PASS

- [ ] **Step 5: Write failing tests for `is_retryable_error()`**

Append to `tests/test_retry.py`:

```python
# ── is_retryable_error tests ──


def _make_sdk_error(status_code, message="error"):
    """Create a lightweight stub exception that mimics SDK error shape.

    Works regardless of whether openai/anthropic packages are installed.
    The retry utility classifies errors by status_code attribute, not by
    isinstance checks, so stubs exercise the same code paths as real SDKs.
    """
    err = Exception(message)
    err.status_code = status_code
    err.response = MagicMock(status_code=status_code, headers={})
    return err


def test_retryable_openai_rate_limit():
    """OpenAI-style 429 RateLimitError should be retryable."""
    from backend.retry import is_retryable_error
    err = _make_sdk_error(429, "Rate limit exceeded")
    assert is_retryable_error(err) is True


def test_retryable_openai_server_error():
    """OpenAI-style 500 InternalServerError should be retryable."""
    from backend.retry import is_retryable_error
    err = _make_sdk_error(500, "Internal server error")
    assert is_retryable_error(err) is True


def test_retryable_anthropic_rate_limit():
    """Anthropic-style 429 RateLimitError should be retryable."""
    from backend.retry import is_retryable_error
    err = _make_sdk_error(429, "Rate limit exceeded")
    assert is_retryable_error(err) is True


def test_not_retryable_auth_error():
    """Authentication errors (401) should NOT be retryable."""
    from backend.retry import is_retryable_error
    err = _make_sdk_error(401, "Invalid API key")
    assert is_retryable_error(err) is False


def test_not_retryable_bad_request():
    """Bad request (400) should NOT be retryable."""
    from backend.retry import is_retryable_error
    err = _make_sdk_error(400, "Invalid request")
    assert is_retryable_error(err) is False


def test_retryable_connection_error():
    """ConnectionError should be retryable."""
    from backend.retry import is_retryable_error
    err = ConnectionError("Connection refused")
    assert is_retryable_error(err) is True


def test_retryable_timeout_error():
    """TimeoutError should be retryable."""
    from backend.retry import is_retryable_error
    err = TimeoutError("Request timed out")
    assert is_retryable_error(err) is True


def test_retryable_generic_with_status_code():
    """Any exception with a retryable status_code attribute should be retryable."""
    from backend.retry import is_retryable_error
    err = Exception("Server error")
    err.status_code = 503
    assert is_retryable_error(err) is True


def test_not_retryable_generic_exception():
    """Generic exceptions without status codes should NOT be retryable."""
    from backend.retry import is_retryable_error
    err = ValueError("bad value")
    assert is_retryable_error(err) is False


def test_retryable_string_matching():
    """Exceptions mentioning transient keywords should be retryable."""
    from backend.retry import is_retryable_error
    err = Exception("temporarily unavailable, please retry")
    assert is_retryable_error(err) is True
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v -k "retryable"`
Expected: FAIL with `ImportError: cannot import name 'is_retryable_error'`

- [ ] **Step 7: Implement `is_retryable_error()`**

Append to `backend/retry.py`:

```python
# ── Transient error keywords (for string-matching fallback) ──────────────
_TRANSIENT_KEYWORDS = (
    'temporarily unavailable', 'timeout', 'timed out',
    'connection', 'network', 'rate limit', 'rate_limit',
    '502', '503', '504', '529', 'overloaded',
)


def _get_status_code(error):
    """Extract HTTP status code from an exception, if present."""
    # OpenAI/Anthropic SDK errors have .status_code
    code = getattr(error, 'status_code', None)
    if code is not None:
        return int(code)
    # Some errors nest it in .response
    resp = getattr(error, 'response', None)
    if resp is not None:
        code = getattr(resp, 'status_code', None)
        if code is not None:
            return int(code)
    return None


def _get_retry_after(error):
    """Extract Retry-After header value from an exception, if present."""
    # Try error.response.headers
    resp = getattr(error, 'response', None)
    if resp is not None:
        headers = getattr(resp, 'headers', {})
        if hasattr(headers, 'get'):
            val = headers.get('retry-after') or headers.get('Retry-After')
            if val is not None:
                return str(val)
    return None


def is_retryable_error(error):
    """Determine if an error is transient and worth retrying.

    Retryable:
        - HTTP 408, 429, 500, 502, 503, 504, 529
        - ConnectionError, TimeoutError, OSError
        - Any exception whose str contains transient keywords

    Not retryable:
        - HTTP 400, 401, 403, 404 (client errors)
        - ValueError, TypeError, KeyError (programming errors)
        - Any other non-transient exception
    """
    # Network-level errors are always retryable
    if isinstance(error, (ConnectionError, TimeoutError, OSError)):
        return True

    # Check HTTP status code
    status = _get_status_code(error)
    if status is not None:
        return status in RETRYABLE_STATUS_CODES

    # Fallback: string matching for transient keywords
    err_str = str(error).lower()
    return any(kw in err_str for kw in _TRANSIENT_KEYWORDS)
```

- [ ] **Step 8: Run tests to verify `is_retryable_error` tests pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v -k "retryable"`
Expected: All 11 `test_*retryable*` tests PASS

- [ ] **Step 9: Write failing tests for `with_retry()`**

Append to `tests/test_retry.py`:

```python
# ── with_retry tests ──


def test_with_retry_succeeds_first_try():
    """Should return result immediately on success."""
    from backend.retry import with_retry
    result = with_retry(lambda: "ok")
    assert result == "ok"


def test_with_retry_retries_on_transient_error():
    """Should retry and succeed after transient failures."""
    from backend.retry import with_retry

    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            err = Exception("temporarily unavailable")
            raise err
        return "recovered"

    with patch('backend.retry.time.sleep'):  # Don't actually sleep
        result = with_retry(flaky)

    assert result == "recovered"
    assert call_count == 3


def test_with_retry_raises_after_max_retries():
    """Should raise the last error after exhausting retries."""
    from backend.retry import with_retry

    def always_fails():
        raise ConnectionError("refused")

    with patch('backend.retry.time.sleep'):
        with pytest.raises(ConnectionError, match="refused"):
            with_retry(always_fails, max_retries=3)


def test_with_retry_does_not_retry_non_transient():
    """Should immediately raise non-retryable errors."""
    from backend.retry import with_retry

    call_count = 0

    def bad_request():
        nonlocal call_count
        call_count += 1
        raise ValueError("invalid input")

    with pytest.raises(ValueError, match="invalid input"):
        with_retry(bad_request)

    assert call_count == 1  # No retries


def test_with_retry_sleeps_with_backoff():
    """Should sleep with exponential backoff between retries."""
    from backend.retry import with_retry

    call_count = 0

    def fails_twice():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ConnectionError("refused")
        return "ok"

    with patch('backend.retry.time.sleep') as mock_sleep:
        with patch('backend.retry.random.random', return_value=0):
            with_retry(fails_twice)

    # Two sleeps: attempt 1 → 0.5s, attempt 2 → 1.0s
    assert mock_sleep.call_count == 2
    assert mock_sleep.call_args_list[0][0][0] == 0.5
    assert mock_sleep.call_args_list[1][0][0] == 1.0


def test_with_retry_respects_retry_after_header():
    """Should use Retry-After header delay when present."""
    from backend.retry import with_retry

    call_count = 0

    def rate_limited():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            err = Exception("rate limited")
            err.status_code = 429
            err.response = MagicMock(
                status_code=429,
                headers={'retry-after': '5'},
            )
            raise err
        return "ok"

    with patch('backend.retry.time.sleep') as mock_sleep:
        with_retry(rate_limited)

    assert mock_sleep.call_args_list[0][0][0] == 5.0


def test_with_retry_logs_retries():
    """Should log each retry attempt."""
    from backend.retry import with_retry

    call_count = 0

    def fails_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("refused")
        return "ok"

    with patch('backend.retry.time.sleep'):
        with patch('backend.retry.logger') as mock_logger:
            with_retry(fails_once, label="test_call")

    mock_logger.warning.assert_called_once()
    log_msg = mock_logger.warning.call_args[0][0]
    assert "test_call" in log_msg


def test_with_retry_custom_max_retries():
    """Should respect custom max_retries parameter."""
    from backend.retry import with_retry

    call_count = 0

    def always_fails():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("refused")

    with patch('backend.retry.time.sleep'):
        with pytest.raises(ConnectionError):
            with_retry(always_fails, max_retries=2)

    assert call_count == 3  # 1 initial + 2 retries
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v -k "with_retry"`
Expected: FAIL with `ImportError: cannot import name 'with_retry'`

- [ ] **Step 11: Implement `with_retry()`**

Append to `backend/retry.py`:

```python
def with_retry(fn, max_retries=MAX_RETRIES, label="", max_delay_s=MAX_DELAY_S):
    """Execute fn() with exponential backoff on transient failures.

    Args:
        fn: Callable (no args) to execute. Typically a lambda wrapping the API call.
        max_retries: Maximum number of retries (default 5 → 6 total attempts).
        label: Human-readable label for log messages (e.g., "grade_per_question").
        max_delay_s: Maximum backoff delay in seconds.

    Returns:
        Whatever fn() returns on success.

    Raises:
        The last exception if all retries are exhausted, or immediately
        if the error is not retryable.
    """
    last_error = None
    tag = f" [{label}]" if label else ""

    for attempt in range(1, max_retries + 2):  # +2 because range is exclusive and attempt 1 is initial
        try:
            return fn()
        except Exception as e:
            last_error = e

            if not is_retryable_error(e):
                raise

            if attempt > max_retries:
                # Exhausted all retries
                logger.error(
                    "All %d retries exhausted%s: %s",
                    max_retries, tag, e,
                )
                raise

            retry_after = _get_retry_after(e)
            delay = get_retry_delay(
                attempt=attempt,
                retry_after=retry_after,
                max_delay_s=max_delay_s,
            )

            status = _get_status_code(e)
            status_str = f" (HTTP {status})" if status else ""
            logger.warning(
                "Retry %d/%d%s%s: %s — waiting %.1fs",
                attempt, max_retries, tag, status_str, e, delay,
            )

            time.sleep(delay)

    raise last_error  # Should never reach here, but safety net
```

- [ ] **Step 12: Run all retry tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v`
Expected: All 26 tests PASS

- [ ] **Step 13: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/retry.py tests/test_retry.py
git commit -m "feat: add unified retry-with-backoff utility inspired by Claude Code's withRetry.ts"
```

---

### Task 2: Apply retry to assignment_grader.py (grading engine)

This is the highest-impact file — 16 unprotected API calls across OpenAI, Anthropic, and Gemini.

**Files:**
- Modify: `assignment_grader.py`

The pattern is the same everywhere: wrap the existing API call in `with_retry(lambda: ...)`. The surrounding error handling stays unchanged.

- [ ] **Step 1: Add the import**

At the top of `assignment_grader.py`, add the import alongside existing imports:

```python
from backend.retry import with_retry
```

Find the existing import block (near the top of the file, after the other `from backend.*` imports) and add it there.

- [ ] **Step 2: Wrap OpenAI structured output calls (lines ~3995, ~4656, ~4925, ~6534)**

For each `client.beta.chat.completions.parse(...)` call, change:

```python
response = client.beta.chat.completions.parse(
    model=model,
    messages=messages,
    ...
)
```

to:

```python
response = with_retry(
    lambda: client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        ...
    ),
    label="openai_structured",
)
```

There are 4 locations. For each one, wrap the entire `client.beta.chat.completions.parse(...)` call (including all its keyword arguments) inside `with_retry(lambda: ...)`.

**Important:** Python lambdas capture variables by reference. Each of these calls is inside its own function scope, so closures are safe — the variables (`model`, `messages`, etc.) won't change between the lambda creation and execution.

- [ ] **Step 3: Wrap OpenAI standard calls (lines ~4012, ~5518, ~6558)**

For each `client.chat.completions.create(...)` call, change:

```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    ...
)
```

to:

```python
response = with_retry(
    lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        ...
    ),
    label="openai_chat",
)
```

There are 3 locations. Same wrapping pattern.

- [ ] **Step 4: Wrap Anthropic calls (lines ~4623, ~4880, ~5492, ~6490)**

For each `client.messages.create(...)` call, change:

```python
response = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    messages=messages,
    ...
)
```

to:

```python
response = with_retry(
    lambda: client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        ...
    ),
    label="anthropic_messages",
)
```

There are 4 locations. Same wrapping pattern.

- [ ] **Step 5: Wrap Gemini calls (lines ~4646, ~4909, ~5510)**

For each `gemini_client.generate_content(...)` or `client.generate_content(...)` call that does NOT already have retry logic:

```python
response = gemini_client.generate_content(full_prompt)
```

becomes:

```python
response = with_retry(
    lambda: gemini_client.generate_content(full_prompt),
    label="gemini_generate",
)
```

There are 3 unprotected locations (lines ~4646, ~4909, ~5510). The call at lines ~6515-6518 already has its own retry loop — leave that one unchanged.

- [ ] **Step 6: Remove the existing Gemini-only retry loop (lines ~6500-6529)**

The existing retry block around lines 6500-6529 looks like:

```python
max_retries = 3
retry_delay = 2  # seconds

for attempt in range(max_retries):
    try:
        if assignment_data.get("type") == "image":
            ...
            response = gemini_client.generate_content([full_prompt, image_part])
        else:
            ...
            response = gemini_client.generate_content(text_content)
        ...
        break  # Success, exit retry loop
    except Exception as e:
        if "429" in str(e) and attempt < max_retries - 1:
            ...
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
            raise
```

Replace the entire retry loop with:

```python
if assignment_data.get("type") == "image":
    import base64
    image_data = base64.b64decode(assignment_data['content'])
    image_part = {
        "mime_type": assignment_data['media_type'],
        "data": image_data
    }
    full_prompt = prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."
    response = with_retry(
        lambda: gemini_client.generate_content([full_prompt, image_part]),
        label="gemini_image",
    )
else:
    text_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]
    response = with_retry(
        lambda: gemini_client.generate_content(text_content),
        label="gemini_text",
    )
if token_tracker:
    token_tracker.record_gemini(response, actual_model)
response_text = response.text.strip()
```

- [ ] **Step 7: Search-based verification — no unwrapped calls remain**

Run these grep commands and verify zero matches (all calls should be inside `with_retry`):
```bash
cd /Users/alexc/Downloads/Graider
# These should return ZERO lines (all wrapped):
grep -n 'client\.messages\.create(' assignment_grader.py | grep -v 'with_retry' | grep -v '#'
grep -n 'client\.chat\.completions\.create(' assignment_grader.py | grep -v 'with_retry' | grep -v '#'
grep -n 'client\.beta\.chat\.completions\.parse(' assignment_grader.py | grep -v 'with_retry' | grep -v '#'
grep -n 'gemini_client\.generate_content(' assignment_grader.py | grep -v 'with_retry' | grep -v '#'
grep -n 'client\.generate_content(' assignment_grader.py | grep -v 'with_retry' | grep -v '#'

# This should show the import + all 16 wrapper calls:
grep -c 'with_retry' assignment_grader.py
# Expected: 17 (1 import + 16 calls)
```

- [ ] **Step 8: Verify the app starts without import errors**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -c "import assignment_grader; print('OK')"`
Expected: `OK`

- [ ] **Step 9: Run existing grading tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_grading_pipeline.py tests/test_grading_factors.py -v --timeout=60`
Expected: All existing tests PASS (the retry wrapper is transparent when calls succeed)

- [ ] **Step 10: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add assignment_grader.py
git commit -m "feat: wrap all AI API calls in assignment_grader.py with retry-with-backoff"
```

---

### Task 3: Apply retry to planner_routes.py (12 unprotected calls)

**Files:**
- Modify: `backend/routes/planner_routes.py`

- [ ] **Step 1: Add the import**

At the top of `backend/routes/planner_routes.py`, add:

```python
from backend.retry import with_retry
```

- [ ] **Step 2: Wrap all 12 `client.chat.completions.create()` calls**

For each of the 12 locations (lines ~680, ~2415, ~2504, ~2720, ~3151, ~3189, ~3660, ~5870, ~6741, ~6876, ~6981, ~7074):

Change:

```python
completion = client.chat.completions.create(
    model=model,
    messages=messages,
    ...
)
```

to:

```python
completion = with_retry(
    lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        ...
    ),
    label="planner_generate",
)
```

Each call is inside its own route handler function, so lambda closures are safe.

- [ ] **Step 3: Search-based verification — no unwrapped calls remain**

```bash
cd /Users/alexc/Downloads/Graider
# Should return ZERO lines (all wrapped):
grep -n 'client\.chat\.completions\.create(' backend/routes/planner_routes.py | grep -v 'with_retry' | grep -v '#'

# Should show import + all wrapper calls:
grep -c 'with_retry' backend/routes/planner_routes.py
# Expected: 13 (1 import + 12 calls)
```

- [ ] **Step 4: Verify the app starts**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -c "from backend.routes.planner_routes import planner_bp; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Run existing planner tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_planner_routes.py -v --timeout=60`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/planner_routes.py
git commit -m "feat: wrap all AI API calls in planner_routes.py with retry-with-backoff"
```

---

### Task 4: Apply retry to remaining route files (4 files, 1 call each)

**Files:**
- Modify: `backend/routes/grading_routes.py:728`
- Modify: `backend/routes/lesson_routes.py:462`
- Modify: `backend/routes/assignment_routes.py:145`
- Modify: `backend/routes/assignment_player_routes.py:342`

- [ ] **Step 1: Add imports to all 4 files**

Add to each file's import block:

```python
from backend.retry import with_retry
```

- [ ] **Step 2: Wrap grading_routes.py (line ~728)**

Change:

```python
message = client.messages.create(
    ...
)
```

to:

```python
message = with_retry(
    lambda: client.messages.create(
        ...
    ),
    label="grading_anthropic",
)
```

- [ ] **Step 3: Wrap lesson_routes.py (line ~462)**

Change:

```python
message = client.messages.create(
    ...
)
```

to:

```python
message = with_retry(
    lambda: client.messages.create(
        ...
    ),
    label="lesson_anthropic",
)
```

- [ ] **Step 4: Wrap assignment_routes.py (line ~145)**

Change:

```python
response = client.chat.completions.create(
    ...
)
```

to:

```python
response = with_retry(
    lambda: client.chat.completions.create(
        ...
    ),
    label="assignment_openai",
)
```

- [ ] **Step 5: Wrap assignment_player_routes.py (line ~342)**

Change:

```python
response = client.chat.completions.create(
    ...
)
```

to:

```python
response = with_retry(
    lambda: client.chat.completions.create(
        ...
    ),
    label="player_openai",
)
```

- [ ] **Step 6: Search-based verification — no unwrapped calls remain**

```bash
cd /Users/alexc/Downloads/Graider
# Each file should have ZERO bare API calls outside with_retry:
for f in backend/routes/grading_routes.py backend/routes/lesson_routes.py backend/routes/assignment_routes.py backend/routes/assignment_player_routes.py; do
  echo "=== $f ==="
  grep -n 'client\.messages\.create\|client\.chat\.completions\.create' "$f" | grep -v 'with_retry' | grep -v '#'
done
# Expected: no output (all calls wrapped)
```

- [ ] **Step 7: Verify all 4 files import cleanly**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -c "from backend.routes.grading_routes import grading_bp; from backend.routes.lesson_routes import lesson_bp; from backend.routes.assignment_routes import assignment_bp; from backend.routes.assignment_player_routes import assignment_player_bp; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Run existing route tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_grading_routes.py tests/test_assignment_routes.py -v --timeout=60`
Expected: All existing tests PASS

- [ ] **Step 9: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/grading_routes.py backend/routes/lesson_routes.py backend/routes/assignment_routes.py backend/routes/assignment_player_routes.py
git commit -m "feat: wrap AI API calls in 4 remaining route files with retry-with-backoff"
```

---

### Task 5: Migrate all 6 Supabase retry sites in storage.py to shared utility

**Files:**
- Modify: `backend/storage.py`

There are 6 retry sites in `storage.py`:
- 2 use the `_retry_supabase()` helper: `_sb_load()`, `_sb_save()`
- 4 use inline `for attempt in range(3)` loops: `_sb_delete()`, `_sb_list_keys()`, `_sb_load_student_history()`, `_sb_save_student_history()`

All 6 will be migrated to `with_retry()`. The inline loops have slightly different error detection (checking `'Resource temporarily unavailable'` only) vs `_retry_supabase` (which checks a broader keyword list), but `is_retryable_error()` from `backend/retry.py` covers all of these cases via its `_TRANSIENT_KEYWORDS` list.

- [ ] **Step 1: Add the import**

At the top of `backend/storage.py`, add:

```python
from backend.retry import with_retry
```

- [ ] **Step 2: Delete the `_retry_supabase()` function**

Delete the entire `_retry_supabase` function (lines 21-36):

```python
def _retry_supabase(fn, max_retries=3, initial_delay=0.5):
    """Retry a Supabase operation on transient failures."""
    import time as _time
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(s in err_str for s in [
                'temporarily unavailable', 'timeout', 'connection',
                'network', '502', '503', '504', 'rate limit',
            ])
            if not is_transient or attempt == max_retries - 1:
                raise
            delay = initial_delay * (2 ** attempt)
            _time.sleep(delay)
```

- [ ] **Step 3: Migrate `_sb_load()` and `_sb_save()` (the 2 `_retry_supabase` callers)**

```python
# _sb_load (~line 259):
# Before:
return _retry_supabase(_query)
# After:
return with_retry(_query, label="supabase_load", max_retries=3)

# _sb_save (~line 279):
# Before:
return _retry_supabase(_query)
# After:
return with_retry(_query, label="supabase_save", max_retries=3)
```

- [ ] **Step 4: Migrate `_sb_delete()` (~line 285)**

Replace the entire inline retry loop with a `with_retry` call. The function currently:
1. Loops `for attempt in range(3)`
2. Tries the Supabase delete
3. On `'Resource temporarily unavailable'`, sleeps and retries
4. On other errors or final attempt, logs and returns `False`

Rewrite to:

```python
def _sb_delete(data_key, teacher_id):
    """Delete a row from Supabase teacher_data table."""
    def _op():
        sb = _get_supabase()
        if not sb:
            return False
        sb.table('teacher_data') \
            .delete() \
            .eq('teacher_id', teacher_id) \
            .eq('data_key', data_key) \
            .execute()
        return True
    try:
        return with_retry(_op, label="supabase_delete", max_retries=3)
    except Exception as e:
        logger.error("Supabase delete failed for key=%s teacher=%s: %s", data_key, teacher_id, e)
        return False
```

- [ ] **Step 5: Migrate `_sb_list_keys()` (~line 307)**

Same pattern — extract the operation into a nested function, wrap with `with_retry`:

```python
def _sb_list_keys(prefix, teacher_id):
    """List data keys matching a prefix from Supabase."""
    def _op():
        sb = _get_supabase()
        if not sb:
            return []
        result = sb.table('teacher_data') \
            .select('data_key') \
            .eq('teacher_id', teacher_id) \
            .like('data_key', f"{prefix}%") \
            .execute()
        return sorted([row['data_key'] for row in result.data]) if result.data else []
    try:
        return with_retry(_op, label="supabase_list_keys", max_retries=3)
    except Exception as e:
        logger.error("Supabase list_keys failed for prefix=%s teacher=%s: %s", prefix, teacher_id, e)
        return None
```

- [ ] **Step 6: Migrate `_sb_load_student_history()` (~line 360)**

```python
def _sb_load_student_history(teacher_id, student_id):
    """Load student history from Supabase."""
    def _op():
        sb = _get_supabase()
        if not sb:
            return None
        result = sb.table('student_history') \
            .select('history') \
            .eq('teacher_id', teacher_id) \
            .eq('student_id', student_id) \
            .execute()
        if result.data and len(result.data) > 0:
            return result.data[0]['history']
        return None
    try:
        return with_retry(_op, label="supabase_load_history", max_retries=3)
    except Exception as e:
        logger.error("Supabase load student_history failed: %s", e)
        return None
```

- [ ] **Step 7: Migrate `_sb_save_student_history()` (~line 384)**

```python
def _sb_save_student_history(teacher_id, student_id, history):
    """Upsert student history to Supabase."""
    def _op():
        sb = _get_supabase()
        if not sb:
            return False
        sb.table('student_history').upsert({
            'teacher_id': teacher_id,
            'student_id': student_id,
            'history': history,
            'updated_at': datetime.now(tz=timezone.utc).isoformat(),
        }).execute()
        return True
    try:
        return with_retry(_op, label="supabase_save_history", max_retries=3)
    except Exception as e:
        logger.error("Supabase save student_history failed: %s", e)
        return False
```

- [ ] **Step 8: Remove stale `import time as _time` lines**

Each of the 4 inline-loop functions has its own `import time as _time`. After migration, these are unused. Remove them from `_sb_delete`, `_sb_list_keys`, `_sb_load_student_history`, and `_sb_save_student_history`.

- [ ] **Step 9: Search-based verification — no inline retry loops remain**

```bash
cd /Users/alexc/Downloads/Graider
# Should return ZERO matches (all loops replaced):
grep -n 'for attempt in range' backend/storage.py
# Expected: no output

# Should return ZERO matches (_retry_supabase deleted):
grep -n '_retry_supabase' backend/storage.py
# Expected: no output

# Should show import + 6 calls:
grep -c 'with_retry' backend/storage.py
# Expected: 7 (1 import + 6 calls)
```

- [ ] **Step 10: Run storage tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_storage_keys.py -v`
Expected: All existing tests PASS

- [ ] **Step 11: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/storage.py
git commit -m "refactor: migrate all 6 Supabase retry sites in storage.py to shared with_retry utility"
```

---

### Task 6: Integration test — retry under simulated failures

**Files:**
- Modify: `tests/test_retry.py` (append integration tests)

- [ ] **Step 1: Write integration tests that simulate real SDK errors**

Append to `tests/test_retry.py`:

```python
# ── Integration tests: simulate real SDK error patterns ──


def test_retry_openai_rate_limit_then_success():
    """Simulate OpenAI returning 429 twice, then succeeding."""
    from backend.retry import with_retry

    call_count = 0

    def mock_openai_call():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            err = _make_sdk_error(429, "Rate limit exceeded")
            err.response = MagicMock(status_code=429, headers={'retry-after': '1'})
            raise err
        return {"choices": [{"message": {"content": "graded"}}]}

    with patch('backend.retry.time.sleep') as mock_sleep:
        result = with_retry(mock_openai_call, label="test_openai")

    assert result == {"choices": [{"message": {"content": "graded"}}]}
    assert call_count == 3
    # Should have respected Retry-After: 1
    assert mock_sleep.call_args_list[0][0][0] == 1.0
    assert mock_sleep.call_args_list[1][0][0] == 1.0


def test_retry_anthropic_503_then_success():
    """Simulate Anthropic returning 503 once, then succeeding."""
    from backend.retry import with_retry

    call_count = 0

    def mock_anthropic_call():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _make_sdk_error(503, "Service temporarily unavailable")
        return {"content": [{"text": "feedback"}]}

    with patch('backend.retry.time.sleep'):
        result = with_retry(mock_anthropic_call, label="test_anthropic")

    assert result == {"content": [{"text": "feedback"}]}
    assert call_count == 2


def test_retry_connection_reset_recovery():
    """Simulate ECONNRESET → retry → success."""
    from backend.retry import with_retry

    call_count = 0

    def mock_call():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Connection reset by peer")
        return "ok"

    with patch('backend.retry.time.sleep'):
        result = with_retry(mock_call, label="test_connreset")

    assert result == "ok"
    assert call_count == 2


def test_retry_total_delay_reasonable():
    """Total delay for 5 retries with zero jitter should be 0.5+1+2+4+8 = 15.5s."""
    from backend.retry import with_retry

    def always_fails():
        raise ConnectionError("refused")

    delays = []
    original_sleep = time.sleep

    def capture_sleep(s):
        delays.append(s)

    with patch('backend.retry.time.sleep', side_effect=capture_sleep):
        with patch('backend.retry.random.random', return_value=0):
            with pytest.raises(ConnectionError):
                with_retry(always_fails, max_retries=5)

    assert len(delays) == 5
    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0]
    assert sum(delays) == 15.5
```

- [ ] **Step 2: Run the full test suite**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_retry.py -v`
Expected: All 30 tests PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add tests/test_retry.py
git commit -m "test: add integration tests for retry-with-backoff under simulated API failures"
```

---

## Summary

| Task | What | Calls Protected | Risk |
|------|------|-----------------|------|
| 1 | Create `backend/retry.py` + unit tests | Foundation | None — new file |
| 2 | Wrap `assignment_grader.py` | 16 calls | Low — transparent wrapper |
| 3 | Wrap `planner_routes.py` | 12 calls | Low — transparent wrapper |
| 4 | Wrap 4 remaining route files | 4 calls | Low — transparent wrapper |
| 5 | Migrate `storage.py` | 6 calls (delete `_retry_supabase` + 4 inline loops) | Low — same behavior, shared code |
| 6 | Integration tests | Validation | None — tests only |

**Total: 38 call sites protected with retry-with-backoff** (32 AI API + 6 Supabase).

**Before:** A single OpenAI 429 during a 30-student grading run kills the entire batch.
**After:** Transient errors auto-recover with up to 15.5s of backoff, and the teacher never knows it happened.
