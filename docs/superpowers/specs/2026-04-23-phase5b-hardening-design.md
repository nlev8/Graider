# Phase 5b — Adapter Hardening Design

**Date:** 2026-04-23
**Status:** Specified, awaiting user review then implementation plan
**Review history:** Brainstorm → Codex design review (APPROVED_WITH_REVISIONS, 7 findings reconciled) → this document
**Follows:** Phase 5a (excellence-tier first slice, 7 PRs shipped 2026-04-22)

---

## Goal

Tighten the LLM adapter seam Phase 5a built. Six small-to-medium sequential PRs add circuit-breaker protection, migrate Gemini off its deprecated SDK, and close the reviewer-flagged hygiene gaps from Phase 5a. Clever/ClassLink/OneRoster contracts are NOT touched.

**Dimensions targeted:** Operational safety (→9), Error handling (→8.5), Code quality (→7), Data integrity (→8.5).

**Non-goal:** expanding the adapter's provider surface (image generation, TTS). Those are Phase 5c.

---

## Scope — what's IN and OUT

**In Phase 5b (6 PRs):**

| PR | Item | Primary dimension(s) |
|---|---|---|
| 1 | pybreaker circuit breakers on `chat()` / `stream_chat()` | Operational safety, Error handling |
| 2 | Gemini SDK migration `google.generativeai` → `google.genai` | Code quality, Operational safety |
| 3 | OpenAI vision `detail: high` hint via `ImagePart.detail` | Data integrity (OCR quality) |
| 4 | Stream close/cancel + route-level `GeneratorExit` hook | Operational safety |
| 5 | Memory caps on tool-arg buffers + streaming error-path tests | Operational safety, Test coverage |
| 6 | Dead-dep cleanup (`selenium`, `webdriver-manager`) | Code quality |

**Explicitly deferred to Phase 5c:**
- Gemini image-generation adapter sibling (`slide_generator.py:258` currently calls `google.genai` directly — already on maintained SDK, working, not worth adapter-wrapping now)
- OpenAI TTS adapter (`openai_tts_service.py` — orthogonal shape from chat)
- APM tracing enablement (requires Sentry billing decision; not in scope)
- Multi-round tool-loop VCR-cassette integration tests (Phase 5a D2 deferral, stays deferred pending cassette infrastructure)

**Explicitly deferred to later phases:**
- mypy strict
- Pydantic models for API payloads
- RFC 7807 error responses
- OpenAPI / Swagger generation
- Mutation testing

---

## Current-state inventory (verified 2026-04-23)

**Already exists (don't rebuild):**
- `backend/services/llm_adapter/` package with 5 files: `types.py`, `streaming.py`, `openai_adapter.py`, `anthropic_adapter.py`, `gemini_adapter.py`, `__init__.py`.
- All 3 adapters implement `chat(request) -> LLMResponse` and `stream_chat(request) -> Iterator[StreamEvent]`.
- Every call wrapped in `with_retry()` from `backend/retry.py`. `MAX_RETRIES = 5` in the existing retry primitive.
- Metrics via `backend.observability.events.emit` as `llm.call.start/complete/error`. Sentry breadcrumb on error.
- `LLMAdapter(@runtime_checkable Protocol)` exported from `__init__.py`.
- `normalize_finish_reason()` in `types.py` maps provider-native finish reasons to canonical 4 values.
- `_unwrap_protobuf` helper in `gemini_adapter.py` recursively converts protobuf Struct/ListValue to plain dict/list.
- `handle_route_errors` decorator in `backend/utils/errors.py`. Currently turns unknown exceptions into generic 500 responses — will be extended in PR 1 to map `pybreaker.CircuitBreakerError` → 503 with `Retry-After`.
- `pybreaker` is NOT yet in `requirements.in`. Added in PR 1.
- `google.generativeai` (deprecated) is used by `gemini_adapter.py`. `google.genai` (maintained) is ALREADY in `requirements.in` and used by `slide_generator.py` for image gen.
- `backend/routes/assistant_routes.py:36, 1331` imports `google.generativeai as genai_pkg` for install-check strings only.
- `backend/routes/assignment_player_routes.py:353-355` (OCR call site) was the Phase 5a D1 regression for missing `detail: high` — it's still missing; PR 3 addresses it.

**CI state:** 7 jobs (`Backend Tests`, `Frontend Build`, `Migrations Smoke`, `Lockfile Drift Check`, `Ruff Lint`, `Bandit SAST`, `Secret Scan`). 1620 tests passing on main.

---

## PR 1 — pybreaker circuit breakers

**Goal:** make the adapter seam fail-fast when a provider is unhealthy, instead of hammering a failing endpoint with each caller's request.

**New module:** `backend/services/llm_adapter/breakers.py`

**Granularity:** one breaker per `(provider, model)` tuple — lazy-populated dict. Prevents a flaky `gpt-4o` from blackouting `gpt-4o-mini`. Codex flagged the original per-provider design as too coarse.

**Why not per-credential?** Graider is BYOK — teachers/districts can supply their own API keys (`backend/api_keys.py:48-103`). Adding credential to the breaker key would grow the breaker count unboundedly with teacher count, and the failure mode we care about (provider-side health for a given model) is credential-independent: if OpenAI's `gpt-4o` endpoint is degraded, every key sees that degradation. Per-(provider, model) is the right altitude — granular enough to isolate a failing model, coarse enough to share health signal across keys.

```python
# backend/services/llm_adapter/breakers.py
from __future__ import annotations

import pybreaker
from typing import Any

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
    # Lazy imports so the classifier works across SDK versions.
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
    # HTTP status fallback for other SDK error shapes
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int):
        if status == 429 or (400 <= status < 500 and status != 408):
            return True
    return False


class _BreakerListener(pybreaker.CircuitBreakerListener):
    def __init__(self, provider: str, model: str):
        self._provider = provider
        self._model = model

    def state_change(self, cb, old_state, new_state):
        # pybreaker types old_state as optional (first transition has no prior
        # state). Guard against None via getattr-with-default rather than
        # unconditional .name dereference.
        emit(
            "llm.breaker.state_change",
            provider=self._provider,
            model=self._model,
            from_state=getattr(old_state, "name", None) or "initial",
            to_state=getattr(new_state, "name", None) or "unknown",
        )


def get_breaker(provider: str, model: str) -> pybreaker.CircuitBreaker:
    """Return (creating if needed) the breaker for this provider+model."""
    key = (provider, model)
    if key not in _BREAKERS:
        _BREAKERS[key] = pybreaker.CircuitBreaker(
            fail_max=FAIL_MAX,
            reset_timeout=RESET_TIMEOUT,
            exclude=[_is_user_error],
            listeners=[_BreakerListener(provider, model)],
        )
    return _BREAKERS[key]
```

**Wrapping**: breaker wraps the RAW network call INSIDE the retry loop, not the adapter's outer `chat()` call. This means each raw HTTP failure counts toward breaker trip (5 consecutive raw 5xx/timeouts per `(provider, model)` open the breaker), not each retry-exhausted adapter call (which would require ~30 raw failures and minutes of Gunicorn worker blocking). Gemini Round-7 flagged the original breaker-wraps-retry placement as a worker-exhaustion risk — a single unhealthy provider could hold a worker in retry-backoff for multiple minutes before protection kicked in.

```python
# openai_adapter.py (sketch)
def chat(self, request: LLMRequest) -> LLMResponse:
    breaker = get_breaker("openai", request.model)

    def _raw_network_call():
        return self._client.chat.completions.create(...)

    def _breakered():
        return breaker.call(_raw_network_call)

    # Retry iterates over breakered calls. CircuitBreakerError is NON-retryable —
    # it propagates immediately, so once the breaker is open, retry exits on the
    # first attempt rather than backing off pointlessly.
    return with_retry(
        _breakered,
        max_retries=MAX_RETRIES,
        non_retryable=(pybreaker.CircuitBreakerError,),
    )
```

For `stream_chat`, the breaker still wraps only the stream-open call (not iteration); same retry-wraps-breaker layering:

```python
def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]:
    breaker = get_breaker("openai", request.model)

    def _raw_open_stream():
        return self._client.chat.completions.create(..., stream=True)

    def _breakered_open():
        return breaker.call(_raw_open_stream)

    stream = with_retry(
        _breakered_open,
        max_retries=MAX_RETRIES,
        non_retryable=(pybreaker.CircuitBreakerError,),
    )
    yield from self._iterate_stream(stream, request)
```

**Retry extension:** `backend/retry.py::with_retry` needs a `non_retryable` parameter that short-circuits the retry loop on listed exception types. Verify at implementation time whether the existing retry primitive already supports a skip-list (it may via `retryable_exceptions`); the change is at most a handful of lines in the retry loop's except branch.

**Trip math (revised):** 5 consecutive raw network failures per `(provider, model)` open the breaker. Because retry backs off exponentially within ONE user call (up to 6 attempts ≈ 30-60s total), one severely-unhealthy provider can open the breaker **within a single user call** rather than across ~30 attempts. Subsequent calls fail-fast in nanoseconds via `CircuitBreakerError`. This is the fail-fast behavior the primitive is meant to provide.

**Known limitation documented in the spec:** a stream that opens cleanly but yields zero chunks before erroring doesn't count toward trip. Revisit if evidence accumulates — not worth the complexity for an unmeasured failure mode.

**Error-response contract** — extend `backend/utils/errors.py::handle_route_errors`:

```python
# Added inside handle_route_errors' except chain
except pybreaker.CircuitBreakerError:
    return jsonify({
        "error": "LLM provider temporarily unavailable — circuit breaker open",
        "retry_after_seconds": 60,
    }), 503, {"Retry-After": "60"}
```

This makes breaker-open a clean `503 + Retry-After: 60` contract for **non-streaming** HTTP callers.

**SSE route contract is two-tier** (revised in Round 7 after Gemini flagged the original TOCTOU-rejection reasoning as weak — circuit breakers ARE probabilistic by nature, so the TOCTOU argument was over-weighted).

**Tier 1 — preflight check** (the common case, ~99% of breaker-open traffic):

Before constructing `Response(stream_with_context(generate()))`, the SSE route checks the breaker state directly:

```python
# assistant_routes.py (added before Response(...) construction)
breaker = get_breaker(active_provider, active_model)
if breaker.current_state == pybreaker.STATE_OPEN:
    return jsonify({
        "error": "LLM provider temporarily unavailable — circuit breaker open",
        "retry_after_seconds": 60,
    }), 503, {"Retry-After": "60"}
```

This gives the SSE route the SAME HTTP contract as non-streaming routes for the overwhelmingly-common case (breaker has been open long enough that a real request arrives while open).

**Tier 2 — TOCTOU fallback** (the rare race, ~1%):

In the rare case where the breaker is `STATE_CLOSED` at preflight time but opens DURING iteration (e.g., a stream-open call fails and opens the breaker mid-request), the existing `except Exception` handler at `assistant_routes.py:1703-1708` still catches `CircuitBreakerError` and yields an SSE `error` frame:

```json
{"type": "error", "content": "CircuitBreakerError: Circuit 'openai:gpt-4o' is open"}
```

The frontend consumes `event.content` at `frontend/src/components/AssistantChat.jsx:507` (`last.content + '\n\n' + event.content`) and renders inline with `isError: true`. No frontend change required — SSE error handling already exists for all provider errors.

**Why the TOCTOU concern was over-weighted:** circuit breakers are inherently probabilistic — the whole point is that a rare race is acceptable in exchange for fail-fast protection on the common path. The two-tier design gives clean HTTP semantics for the 99% case and graceful degradation for the 1%, which is strictly better than a single-tier "always emit an SSE error frame" design that gives up the HTTP-status-code signal for every caller.

**Dependency addition:** `pybreaker>=1.0` in `requirements.in`. Regenerate lockfiles per `docs/dependencies.md`.

**Tests (new `tests/test_llm_adapter_breakers.py`):**
- Trip after 5 network errors on one (provider, model) key.
- Does NOT trip on `BadRequestError`, `AuthenticationError`.
- Does NOT trip on `RateLimitError` (429).
- Half-open after 60s; probe success closes, probe failure re-opens.
- State-change emits `llm.breaker.state_change` with correct from/to.
- Per-model isolation: flooding `gpt-4o` with failures doesn't open `gpt-4o-mini`.
- `handle_route_errors` test: raise `pybreaker.CircuitBreakerError` in a route handler → 503 response with `Retry-After: 60` header.

**Risk:** pybreaker is a new runtime dep; confirm it plays nicely with Gunicorn's process model. Module-level singletons are per-worker — each worker trips independently. This means the EFFECTIVE `fail_max` across the whole app is `fail_max × worker_count` before every worker has tripped (Round 7 — Gemini). Documented as a known limitation; Redis-backed shared state deferred to Phase 5c.

---

## PR 2 — Gemini SDK migration `google.generativeai` → `google.genai`

**Goal:** retire deprecated SDK before it breaks. Upstream is EOL; `FutureWarning` fires on import today.

**In-place rewrite:** `backend/services/llm_adapter/gemini_adapter.py`

**Key shape changes:**

| Area | Old (`google.generativeai`) | New (`google.genai`) |
|---|---|---|
| Import | `import google.generativeai as genai` | `from google import genai`<br>`from google.genai import types` |
| Client | `genai.configure(api_key=...)` + `genai.GenerativeModel(model, system_instruction=...)` | `client = genai.Client(api_key=...)` once per adapter instance |
| Non-stream call | `model.generate_content(contents, generation_config=..., request_options={"timeout": X})` | `client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(system_instruction=..., temperature=..., max_output_tokens=..., response_mime_type=..., response_schema=..., tools=..., function_calling_config=...))` |
| Stream call | `model.generate_content(..., stream=True)` | `client.models.generate_content_stream(model=..., contents=..., config=...)` |
| Tools | `types.Tool(function_declarations=[FunctionDeclaration(...)])` | same namespace lives under `google.genai.types` |
| Function call args | `FunctionCall.args` — protobuf `Struct` | Usually `dict` in the new SDK; `_unwrap_protobuf` stays as defensive fallback |
| Finish reason | `candidate.finish_reason.name` (enum) | Same surface; verify enum names match `normalize_finish_reason` map |
| Usage metadata | `response.usage_metadata.prompt_token_count` / `.candidates_token_count` | Same surface — double-check field names |

**Touch-ups outside the adapter:**
- `backend/routes/assistant_routes.py:36` — change install-check to `from google import genai as genai_pkg`.
- `backend/routes/assistant_routes.py:1331` — update error message string: "google-generativeai package not installed" → "google-genai package not installed. Run: pip install google-genai".

**Tests — three groups that all need attention:**

1. **Adapter-level tests** (`test_llm_adapter_gemini.py`, `test_llm_adapter_gemini_stream.py`) — update mock targets from `google.generativeai` to `google.genai`. Verify finish_reason enum values still route through `normalize_finish_reason` correctly.

2. **Route-level tests that mock the adapter's SDK import** — these patch `backend.services.llm_adapter.gemini_adapter.genai.GenerativeModel` (pre-migration path). After migration, they need to patch `gemini_adapter.genai_client.models` (or whatever the new client attribute is named in the rewritten adapter). Affected files:
   - `tests/test_flashcards.py:65-69, 97-101` (patches `gemini_adapter.genai`)
   - `tests/test_study_guide.py:82-86, 114-118` (same pattern)
   - `tests/test_slide_generator.py:82-89` (uses `gemini_adapter.genai` for text gen; the image-gen path already uses `google.genai` via slide_generator directly, untouched)

3. **Contract-pinning tests** (new) — add one test per new SDK entry point that asserts the expected response-field names (`finish_reason`, `usage_metadata.prompt_token_count`, `candidates[0].content.parts`). Catches future SDK breaks at test time rather than production time.

**Dependency change:** `google-generativeai` removed from `requirements.in`. `google-genai` stays (already there). Regenerate lockfiles.

**Comment cleanup in `requirements.in`:** the header comment currently says "chat-style text generation (planner_routes, assistant_routes, slide_generator:155)" uses `google-generativeai`. Update this to remove the `google-generativeai` reference entirely — post-PR2, `google-genai` handles both chat and image generation.

**Risk:** the biggest PR in Phase 5b. Subtle SDK field-name differences could surface only at runtime. Mitigation: exercise against captured chunk sequences in the tests before merging.

---

## PR 3 — OpenAI vision `detail: high` hint via `ImagePart.detail`

**Goal:** restore pre-Phase-5a-migration OCR quality. The `assignment_player_routes.py:353-355` OCR call used `{"detail": "high"}` before migration; the adapter dropped it.

**Change in `types.py`:**

```python
@dataclass(frozen=True)
class ImagePart:
    url: str | None
    base64: str | None
    mime_type: str
    detail: Literal["auto", "low", "high"] | None = None  # OpenAI-only hint; other providers ignore.
```

**Change in `openai_adapter.py`** `_content_to_openai`:

```python
elif isinstance(p, ImagePart):
    image_url_obj = {"url": p.url if p.url else f"data:{p.mime_type};base64,{p.base64}"}
    if p.detail:
        image_url_obj["detail"] = p.detail
    parts.append({"type": "image_url", "image_url": image_url_obj})
```

**No changes in `anthropic_adapter.py` or `gemini_adapter.py`** — they ignore the field silently.

**Change in `assignment_player_routes.py:353-355`:**

```python
ImagePart(url=image_data, base64=None, mime_type="image/png", detail="high"),
```

**Tests:**
- `test_llm_adapter_openai.py`: add a test that passes `ImagePart(detail="high")` and asserts the kwarg round-trips to `image_url.detail` in the OpenAI call kwargs.
- `test_llm_adapter_anthropic.py` + `test_llm_adapter_gemini.py`: add a test that `ImagePart(detail="high")` doesn't break those adapters (silent ignore).
- `test_assignment_player_routes.py` (or equivalent): update any mock assertions if they inspected the old `image_url` shape.

---

## PR 4 — Stream close/cancel + route-level `GeneratorExit` hook

**Goal:** release upstream provider stream connections when clients disconnect mid-SSE. Adapter cleanup alone isn't enough without route-level signaling.

**Three layers:**

**(a) OpenAI adapter** — wrap the iterator in try/finally, call `.close()` on exit:

```python
def _iterate_stream(self, stream, request):
    try:
        for chunk in stream:
            yield ...  # existing TextDelta / ToolCallDelta / etc emission
    finally:
        try:
            stream.close()  # idempotent per OpenAI SDK — safe on re-call
        except Exception:
            _logger.debug("openai stream.close() raised on cleanup", exc_info=True)
```

**(b) Gemini adapter** — retain a handle to the underlying raw iterator (the one `client.models.generate_content_stream` returns, BEFORE any wrapping). Call `.cancel()` in finally if the method exists:

```python
def _iterate_stream(self, stream, request):
    try:
        for chunk in stream:
            yield ...
    finally:
        # google.genai sync stream: verify at implementation time whether the
        # underlying iterator has .cancel() or .close(); call best-effort.
        for method_name in ("cancel", "close"):
            method = getattr(stream, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    _logger.debug("gemini stream %s() raised on cleanup", method_name, exc_info=True)
                break
```

**Decision flagged for implementation:** if neither `.cancel()` nor `.close()` exists on the `google.genai` sync stream, document the limitation and rely on generator garbage collection. Do NOT block the PR on this — it's a best-effort cleanup, not a correctness requirement.

**(c) `assistant_routes.py` route-level hook** — the SSE route wraps the adapter stream in `stream_with_context(generate())` and owns non-trivial post-stream cleanup (conversation persistence, TTS sentence-buffer flush, TTS stream close, final audio-queue drain, `tts_muted_sessions` and `cancelled_sessions` teardown, cost recording — currently at `backend/routes/assistant_routes.py:1710-1749`). A `GeneratorExit` (client disconnect or Flask teardown) must route through the SAME cleanup path as the normal-completion path, not skip it.

Implementation: factor the route's post-stream cleanup into a `_finalize_assistant_stream()` helper that's called from BOTH normal completion AND the `GeneratorExit` branch. The full design is specified below — including helper shape, responsibilities, idempotency guard, and call-site sketches.

**Idempotency guard (Round 7 — Codex).** A module-level `_finalizing_sessions: set[str]` registry prevents double-execution. Without this guard, a real race exists: normal completion's `yield from _finalize_assistant_stream(...)` can be mid-drain when the client disconnects; `GeneratorExit` propagates into both the inner finalize (closing it early) AND the outer generator's `except GeneratorExit` branch, which then calls `_finalize_assistant_stream_silent()` — running cleanup AGAIN. Without a guard this would double-close `tts_stream`, double-record cost, and double-persist the conversation.

```python
# assistant_routes.py — module-level state
_finalizing_sessions: set[str] = set()
_finalizing_lock = threading.Lock()
```

The helper's first action is to check-and-add under lock; first call wins, re-entrance is a silent no-op (also a no-yield). On exit, the helper removes the session_id in `finally` so a future unrelated request with the same session_id isn't spuriously blocked.

**Shape:** it's a generator, not a plain function — the normal-path cleanup yields `audio_chunk` SSE frames as it drains the final audio queue. Disconnect mode skips the yields but still releases resources.

```python
def _finalize_assistant_stream(
    *,
    session_id: str,
    conv: dict,
    messages: list,
    tts_stream,
    sentence_buffer,
    audio_out_queue,
    total_input_tokens: int,
    total_output_tokens: int,
    total_tts_chars: int,
    active_model: str,
    cancelled: bool,
):
    """Idempotent cleanup for the assistant SSE stream. Yields SSE audio_chunk
    frames in normal-completion mode; silent in disconnect mode.

    Preserves ALL the behavior that currently lives at
    assistant_routes.py:1710-1749 — do NOT drop any of these responsibilities:

      1. conv["messages"] = messages  (:1711)
      2. _persist_conversation(session_id)  (:1712)
      3. If tts_stream set + session not muted + sentence_buffer nonempty:
         sentence_buffer.flush(), tts_stream.send_text(remaining + " "),
         total_tts_chars += len(...)  (:1715-1721)
      4. tts_stream.flush() + tts_stream.wait_for_flush(timeout=15.0)  (:1722-1723)
      5. tts_stream.close()  (:1724)
      6. Final audio-queue drain: yield `{'type': 'audio_chunk', 'audio': chunk}`
         SSE frames until queue empty OR 3s timeout (normal mode only; skip
         yields in disconnect mode — client is gone)  (:1725-1734)
      7. tts_muted_sessions.discard(session_id)  (:1735-1736)
      8. cancelled_sessions.discard(session_id)  (:1738-1739)
      9. _record_assistant_cost(total_input_tokens, total_output_tokens,
         active_model, total_tts_chars) and yield its cost-summary SSE frame
         if returned  (:1741-1749)

    In disconnect mode (`cancelled=True` or called from GeneratorExit path):
    - Steps 1-2 (persistence), 5 (TTS close), 7-9 (flag + cost cleanup)
      STILL RUN. These are pure state cleanup that must happen regardless
      of client connectivity.
    - Step 3 (sentence-buffer flush + send) is skipped — sending more text
      to TTS when the client is gone wastes Eleven Labs credits.
    - Step 4 (tts_stream.flush + wait_for_flush(timeout=15.0)) is SKIPPED
      in disconnect mode (Gemini Round 7). Blocking a Gunicorn worker for
      up to 15 seconds to flush audio that will be discarded is a worker-
      starvation risk. Step 5's close() still runs directly — the Eleven
      Labs client handles abrupt close gracefully, and any in-flight audio
      the server already sent is wasted anyway.
    - Step 6 (yield audio chunks) is skipped — no client to receive them.
    - Step 9's cost SSE frame is also suppressed in disconnect mode, but
      the underlying _record_assistant_cost call still runs so cost
      tracking in the backend DB is accurate.

    This preserves current behavior at :1710-1749 for normal completion
    AND ensures a disconnect doesn't orphan cancelled_sessions, leak tts_stream
    connections, lose conversation state, miss cost records, or block a
    worker in a 15-second TTS flush wait.
    """
    # Round 7 idempotency guard — first call wins, re-entrance is silent no-op.
    with _finalizing_lock:
        if session_id in _finalizing_sessions:
            return  # generator terminates with no yields; no side effects.
        _finalizing_sessions.add(session_id)
    try:
        # ... steps 1-9 per normal vs disconnect branch above ...
        # (step 6 uses `yield`; steps 1-5, 7-9 are side-effects)
        ...
    finally:
        with _finalizing_lock:
            _finalizing_sessions.discard(session_id)
```

**Why a generator, not a plain function:** step 6 (audio-chunk yields) needs to happen FROM INSIDE the Flask generator's yield context. Returning audio chunks as a list would buffer potentially-large PCM data in memory. A generator lets us stream them directly.

**Call sites in the route:**

```python
def generate():
    try:
        for event in adapter.stream_chat(request):
            # existing SSE mapping
            yield ...
        # Normal completion
        yield from _finalize_assistant_stream(
            session_id=session_id, conv=conv, messages=messages,
            tts_stream=tts_stream, sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=False,
        )
    except GeneratorExit:
        # Client disconnected. Run state cleanup but skip audio yields.
        # `yield from` would still attempt to yield, which is illegal here —
        # call the helper in non-yielding mode via a separate drain path.
        _finalize_assistant_stream_silent(  # thin wrapper that discards yields
            session_id=session_id, conv=conv, messages=messages,
            tts_stream=tts_stream, sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=True,
        )
        _logger.info("assistant stream generator closed by client disconnect (session=%s)", session_id)
        raise
    except Exception as e:
        # Existing error-to-SSE-frame handler stays in place.
        error_msg = str(e)
        if "APIError" in type(e).__name__ or "AuthenticationError" in type(e).__name__:
            error_msg = f"API error ({active_provider}): {error_msg}"
        error_payload = {"type": "error", "content": error_msg}
        yield f"data: {json.dumps(error_payload)}\n\n"
        # Still finalize — error path also needs state cleanup.
        yield from _finalize_assistant_stream(
            session_id=session_id, conv=conv, messages=messages,
            tts_stream=tts_stream, sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=True,  # treat as cancelled for cleanup purposes
        )
```

**`_finalize_assistant_stream_silent()` thin wrapper:**
```python
def _finalize_assistant_stream_silent(**kwargs):
    """Run finalize's state cleanup but discard any SSE yields.
    For disconnect path where client is gone."""
    for _ in _finalize_assistant_stream(**kwargs):
        pass  # discard audio_chunk frames — no client to receive
```

**Observability:** `_finalize_assistant_stream` emits `assistant.stream.finalized` with `cancelled`, `duration_ms`, `total_input_tokens`, `total_output_tokens`, `total_tts_chars` so operators can see disconnect patterns.

**No change needed for Anthropic adapter** — Phase 5a D2's context manager pattern already cleans up correctly.

**Tests:**
- Mock an OpenAI stream that raises partway through; verify `.close()` was called on cleanup.
- Mock a stream that runs to completion; verify `.close()` is still called (via finally).
- For Gemini: mock both "has `.cancel()`" and "has neither" cases — verify graceful degradation.
- Route-level: mock `GeneratorExit` during iteration (before finalize starts); verify cleanup path fires.
- **Round 7 — Round-trip re-entrance**: fire `GeneratorExit` DURING `_finalize_assistant_stream()` normal-drain (i.e., while step 6's audio-chunk yields are active). Verify the `_finalizing_sessions` guard prevents duplicate cleanup: `tts_stream.close()` called exactly once, `_record_assistant_cost` called exactly once, `_persist_conversation` called exactly once.
- **Round 7 — Disconnect-mode TTS-skip**: assert that in disconnect mode `tts_stream.wait_for_flush` is NOT called (step 4 skipped) while `tts_stream.close()` IS called (step 5 kept).
- **Round 7 — Guard lifecycle**: (a) invoke `_finalize_assistant_stream(session_id=X)` concurrently from two call sites (simulated by calling the helper once, asserting it's mid-iteration, then calling it again from a second path while the first is still yielding). Verify the SECOND call is a silent no-op — it sees `X in _finalizing_sessions` and returns without running steps 1-9. (b) After the first call fully completes (generator exhausted AND `finally` ran), assert `X not in _finalizing_sessions` — `finally`-release validated. (c) A subsequent fresh `_finalize_assistant_stream(session_id=X)` after first completion runs normally (not a no-op) — the guard is scoped to concurrent re-entrance, not permanent deduplication.

**Not in scope:** Gunicorn worker-level timeout tuning. If workers hang past the generator close, that's a deployment config issue outside this PR.

---

## PR 5 — Memory caps + streaming error-path tests

**Goal:** bound tool-call args buffer growth + fill Phase 5a D2's streaming error-path test gap.

**Memory cap — OpenAI + Anthropic adapters:**

```python
# types.py — new exception
class LLMToolArgsOverflow(Exception):
    """Tool-call args exceeded the adapter's buffer cap during streaming."""
```

```python
# in both openai_adapter.py stream_chat and anthropic_adapter.py stream_chat:
_MAX_TOOL_ARGS_BYTES = 5 * 1024 * 1024  # 5 MB — bounded OOM guardrail

# inside stream loop, when appending args fragment:
if len(pending_tool_calls[idx]["arguments"]) + len(fragment) > _MAX_TOOL_ARGS_BYTES:
    emit("llm.tool_call.args_overflow", provider=self._provider, model=request.model,
         tool_name=pending_tool_calls[idx]["name"], bytes_accumulated=len(pending_tool_calls[idx]["arguments"]))
    raise LLMToolArgsOverflow(
        f"tool_call args exceeded {_MAX_TOOL_ARGS_BYTES} bytes "
        f"for tool {pending_tool_calls[idx]['name']!r} on {self._provider}"
    )
pending_tool_calls[idx]["arguments"] += fragment
```

**Gemini exempt** — it delivers args atomically as whole dicts, not incremental fragments. No unbounded growth path.

**Cap rationale (revised Round 7):** 5 MB is a deliberate guardrail against unbounded growth, NOT a tuned-to-prod value. Round 7 reviewers (Codex + Gemini) flagged the original 256 KB ceiling as too tight — cited real Graider tool-call payloads that can legitimately exceed it:
- `generate_document.content` (`backend/services/assistant_tools_reports.py:220-267`) — full lesson plans, can reach ~40-50k words (~300-500 KB raw)
- `save_assignment_config.document_text` (`backend/services/assistant_tools_reports.py:582-585`) — long reading assignments, bulk transcripts
- `generate_worksheet.questions` (`backend/services/assistant_tools_reports.py:154-186`) — compiled question sets
- `create_automation.steps` (`backend/services/assistant_tools_automation.py:41-53`) — multi-step workflow JSON

5 MB is ~10× the largest single-tool-call payload we'd reasonably expect, still bounded enough to prevent a runaway streaming tool call from consuming gigabytes before the adapter catches it. Overflow emits `llm.tool_call.args_overflow` with tool name + bytes, so operators can retune if real traffic ever bites. A per-tool cap was considered and rejected for Phase 5b scope-creep reasons — the 5 MB single cap is the minimum-viable bound.

**Streaming error-path tests:** one test per provider. Inject an exception mid-stream, verify:
- `llm.call.error` emitted with `duration_ms > 0`
- `sentry_sdk.add_breadcrumb` called
- Exception propagates cleanly to caller (not swallowed)
- Any partial state (chunks_seen, partial_tool_call_ids) included in breadcrumb data

**Test file:** extend existing `tests/test_llm_adapter_openai_stream.py`, `tests/test_llm_adapter_anthropic_stream.py`, `tests/test_llm_adapter_gemini_stream.py` rather than adding a new file.

---

## PR 6 — Dead-dep cleanup

**Goal:** remove two packages with zero Python importers. Verified in Phase 5a code review.

**Changes:**
- `requirements.in` — remove `webdriver-manager>=4.0.0` line.
- `requirements-dev.in` — remove `selenium>=4.15.0` line.
- Regenerate both lockfiles with Python 3.12 + `pip-compile --generate-hashes --allow-unsafe`.
- Update header comment in `requirements.in` — drop `selenium` from the "non-runtime dev tooling" mention (it's already referenced in the comment about why `playwright` stays runtime).

**Pre-merge safety check:** `grep -rn "import selenium\|from selenium\|webdriver.manager\|webdriver_manager" backend/ --include="*.py" | grep -v __pycache__` must return zero hits.

**Risk:** near-zero. Lockfile regeneration is routine at this point.

---

## Sequencing + dependencies

**Merge order:** PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6.

**Hard dependencies:**
- PR 1 requires `pybreaker` added to `requirements.in` — regen lockfiles in PR 1 itself.
- PR 5 depends on PR 1 landed (memory-cap test assertions may reference breaker behavior indirectly).
- PR 4 touches `openai_adapter.py` + `gemini_adapter.py`. PR 2 touched `gemini_adapter.py` entirely. Landing PR 2 first avoids massive merge conflicts in PR 4.

**Soft dependencies / parallel-safe:**
- PR 3 (detail hint) and PR 6 (dead-dep cleanup) touch unrelated files; could ship in any order relative to PR 4/5. Kept sequential for simplicity.

**No cross-PR functional coupling** — each PR's feature works standalone.

---

## Testing strategy

**Per-PR:**
- All PRs maintain CI green on 7 jobs: Backend Tests, Frontend Build, Migrations Smoke, Lockfile Drift Check, Ruff Lint, Bandit SAST, Secret Scan.
- Coverage floor stays at 32% (CI enforced). New code ≥80% line coverage by own unit tests.
- Each PR adds targeted tests per its section above.

**Cross-PR:**
- After Phase 5b merges, run full suite (1620+ tests) one more time against main to catch any integration-level regression.

**No SIS contract touched** — no SIS-specific regression tests needed. 199 Clever/ClassLink/OneRoster tests will continue to pass as before.

---

## Rollout + risks

**Rollout:** each PR merged independently; Railway auto-deploys on merge. Operator monitors `/healthz` (3× 200 pattern from Phase 5a) after each deploy.

**Per-PR risks:**

| PR | Risk | Mitigation |
|---|---|---|
| 1 | pybreaker opens aggressively on transient blips (5 raw failures) and legitimate traffic briefly sees 503s | `reset_timeout=60s` limits blast radius; half-open probe lets traffic resume quickly once provider recovers. Retry primitive still handles sub-threshold transients inside a single call before escalating to breaker. User-visible impact is bounded to the ~60s window and surfaces as a clean `Retry-After` header. |
| 1 | **Per-worker breaker-state dilution** (Gemini Round 7) — breakers are module-level singletons per Gunicorn worker, so with 4 workers, `fail_max=5` × 4 = 20 raw failures are needed before the WHOLE app trips | Acceptable for Phase 5b: each worker's traffic gets protected independently after 5 failures in its own process, which is the failure-isolation boundary that matters (a worker that's already been making healthy requests can still be blocked by this provider). Full cross-worker agreement via Redis-backed breaker is explicitly deferred to Phase 5c. Operators sizing `fail_max` should note the worker-count multiplier. |
| 1 | Per-model breaker count grows unbounded if users request obscure model names | Lazy dict has no GC; accept minor memory overhead (< 1 KB per breaker × O(10) models) |
| 2 | `google.genai` SDK field-name difference not caught by tests | Add contract-pinning tests; exercise real call paths in dev before merge |
| 2 | Missed install-check string update at `assistant_routes.py:1331` breaks diagnostic error | Grep for "google-generativeai" before merge |
| 3 | OpenAI vision call regression from wrong `detail` values | Typed `Literal["auto", "low", "high"]` enforces valid values at construction time |
| 4 | `.cancel()` doesn't exist on new Gemini SDK's sync stream | Best-effort cleanup with fallback; documented limitation, not a blocker |
| 5 | 5 MB cap blocks legitimate large tool calls | Cap was raised from 256 KB to 5 MB in Round 7 after dual reviewers cited real Graider tools that exceed the lower bound. 5 MB is ~10× the largest single-tool-call payload we'd reasonably expect. Emits `llm.tool_call.args_overflow` on overflow so operators can retune if real traffic ever bites. |
| 6 | `selenium` accidentally used somewhere we missed | Pre-merge grep verification |

**Rollback per PR:** `git revert <squash-commit>`. No stateful changes (no DB migrations, no RLS policies, no feature flags) in Phase 5b.

---

## Effort estimate

| PR | Days |
|---|---|
| 1 | 1-2 |
| 2 | 2-3 |
| 3 | 0.5 |
| 4 | 1 |
| 5 | 1 |
| 6 | 0.5 |
| **Total (sequential)** | **6-8 days (~1-1.5 weeks)** |

Compressible to ~4-5 days with parallel worktrees for PR 3, PR 6 (non-conflicting with adapter PRs).

---

## Deviations from review rounds (2026-04-23)

**Round 1 (design-level)** flagged 7 items; reconciled as:

| Codex finding | Resolution |
|---|---|
| Per-provider breaker too coarse — suggests per-(provider, credential) | Changed to per-(provider, model). Provider-side health is credential-independent (rate limits / 5xx / outages hit all teachers at once on the same provider endpoints), so keying by BYOK credential would multiply breaker count by teacher count without improving failure isolation. Model granularity handles the real failure-isolation issue (e.g., gpt-4o down while gpt-4o-mini is fine). See corrected Round-2 rationale below. |
| Remove 429 from breaker trip | **Accepted.** `RateLimitError` + `status_code == 429` now in `_is_user_error`. Retry handles 429 with Retry-After; breaker stays out of rate-limit state. |
| Document breaker+retry math explicitly | **Accepted.** Noted in `_is_user_error` docstring AND in this spec's PR 1 section. |
| "Open succeeded but no first chunk" streaming gap | **Accepted as known limitation.** Documented; fix deferred. |
| Verify Gemini `.cancel()` exists | **Accepted.** PR 4 implementation flagged to check the SDK at implementation time; best-effort fallback documented. |
| Missing scope: pybreaker install, 503 error contract, Gemini finish-reason map update, PR2 test migration | **All accepted.** Folded into PR 1 (pybreaker + 503) and PR 2 (test migration + finish-reason verification). |
| PR 4 reframe — adapter cleanup alone doesn't fix Railway worker leak | **Accepted.** PR 4 now includes route-level `GeneratorExit` hook in `assistant_routes.py`. |

**Round 2 (committed-spec review)** flagged 5 additional items; all reconciled:

| Round-2 finding | Resolution |
|---|---|
| BYOK-model rationale for breaker keying — Codex correctly noted Graider uses per-teacher BYOK keys, not a single env-var credential | **Accepted.** Rationale updated: per-(provider, model) is the right altitude because provider-side health is credential-independent; adding credential dimension would grow breakers with teacher count. Decision unchanged; rationale corrected. |
| Retry math — Codex correctly noted `with_retry` attempts 1 initial + 5 retries, so fail_max=5 × 6 = ~30 attempts before trip (not ~25) | **Accepted at the time.** *Superseded in Round 7:* breaker placement was restructured so breaker wraps the raw network call (not the retry-wrapped adapter call), meaning each raw HTTP failure counts toward trip. New math: 5 consecutive raw failures open the breaker, often within a single unhealthy user call. See Round-7 deviations below. |
| PR 2 test-migration scope incomplete (`test_flashcards.py`, `test_study_guide.py`, `test_slide_generator.py` patch the old Gemini SDK) | **Accepted.** PR 2 test section now enumerates all three test files + specifies mock-target updates. |
| PR 4 `GeneratorExit` sketch bypasses route-owned cleanup (`tts_stream`, conversation persistence, `cancelled_sessions`) | **Accepted.** PR 4 now specifies a `_finalize_assistant_stream()` helper that runs from BOTH normal completion and `GeneratorExit` paths. Idempotent; consolidates existing cleanup from `assistant_routes.py:1710-1749`. |
| SSE breaker-open contract wrong — Flask returns `Response(...)` before iteration, so a breaker raise inside `stream_chat()` becomes an SSE `error` frame, not a 503 | **Accepted.** Spec now explicitly documents: non-streaming routes get 503 + Retry-After; SSE route falls back to an `error` frame (existing handler at `assistant_routes.py:1703-1708`). *Updated in Round 7:* preflight check was re-accepted — TOCTOU argument was over-weighted. SSE route now has two-tier contract: preflight 503 for the common case, SSE error frame as TOCTOU fallback. |
| Stale `:344` citation (now `:353-355`) | **Fixed.** |
| Ungrounded "10× observed prod" claim for 256 KB cap | **Fixed.** Cap reframed as deliberate guardrail with observable overflow event, not tuned-to-data value. |
| `requirements.in` header comment still mentions `google-generativeai` | **Fixed.** PR 2 scope now explicitly includes comment update. |

**Round 7 (dual-reviewer — Codex fresh pass + Gemini independent review)** flagged 8 items; 7 reconciled, 1 rejected:

| Round-7 finding | Source | Resolution |
|---|---|---|
| Breaker wraps retry → ~30 raw attempts before trip = Gunicorn worker exhaustion during provider outages | Gemini | **Accepted.** Breaker now wraps the raw network call; retry wraps breaker. 5 raw failures per `(provider, model)` open the breaker — often within a single user call during a severe outage. `with_retry` adds a `non_retryable=(CircuitBreakerError,)` parameter so retry exits immediately on open-state. See revised PR 1 section. |
| SSE preflight breaker-check rejection reasoning was weak — TOCTOU race is inherent to breakers, not a blocker | Gemini | **Accepted.** SSE route now has a two-tier contract: preflight checks `current_state == STATE_OPEN` and returns 503 + Retry-After for the common case; existing SSE error-frame handler remains as the TOCTOU fallback for the rare race (breaker flips from closed to open between preflight and iteration). |
| TTS `wait_for_flush(timeout=15.0)` blocks a Gunicorn worker for up to 15s on disconnect | Gemini | **Accepted.** `_finalize_assistant_stream` skips step 4 entirely in disconnect mode. Step 5 (`tts_stream.close()`) still runs directly — Eleven Labs handles abrupt close gracefully. Worker frees immediately on client disconnect. |
| 256 KB tool-args cap too small for real Graider tools (`generate_document.content`, `save_assignment_config.document_text`, `generate_worksheet.questions`, `create_automation.steps`) | Codex + Gemini | **Accepted.** Cap raised to 5 MB. Rationale rewritten with cited tool references. Overflow still emits `llm.tool_call.args_overflow` so operators can retune on observed data. |
| Finalizer re-entrance race — `GeneratorExit` mid-drain would cause double TTS close / double cost record / double persistence | Codex | **Accepted.** Added module-level `_finalizing_sessions: set[str]` guard (plus `_finalizing_lock` for thread-safety under Flask threaded workers). Helper first-action is check-and-add under lock; re-entrance silently no-ops. `finally` releases the session_id so unrelated future requests aren't blocked. |
| Per-worker breaker singletons dilute aggregate `fail_max` — 4 Gunicorn workers × `fail_max=5` = 20 raw failures before the entire app sees the breaker open | Gemini | **Accepted as risk-table entry only.** No architectural change in Phase 5b. Documented that each worker's traffic is still protected independently after 5 failures in its own process (the failure-isolation boundary that matters operationally). Redis-backed shared breaker deferred to Phase 5c. |
| Missing test for `GeneratorExit` during normal-finalizer drain (idempotency validation) | Codex | **Accepted.** PR 4 test list now includes three Round-7 tests: mid-drain disconnect with guard assertions, disconnect-mode step-4 skip, and guard-lifecycle cleanup. |
| PR 4 line-range citation `:1710-1749` suspected of drift (blends cleanup + cost recording) | Gemini | **Rejected (false positive).** Codex's Round-6 fresh pass independently verified that `:1710-1749` covers exactly: persistence (:1711-1712), TTS flush/close (:1715-1724), audio drain (:1725-1734), flag discard (:1735-1739), cost record (:1741-1749). The range is not drifted — the spec deliberately scopes the helper to "post-stream cleanup + cost recording" as two conceptually-related responsibilities that already live adjacent in the source. No change. |

---

## Expected outcome (dimension deltas after Phase 5b)

| Dimension | Pre-5b | After 5b |
|---|---|---|
| Operational safety | 9 | 9.5 (breaker + stream cleanup) |
| Error handling | 7.5 | 8.5 (breaker semantics explicit) |
| Code quality | 6.5 | 7 (Gemini on maintained SDK, dead deps gone) |
| Data integrity | 8.5 | 8.75 (OCR detail hint restored) |
| Test coverage | 9 | 9 (streaming error-paths added but no major line-coverage shift) |
| Other dimensions unchanged | | |

Phase 5b moves the composite average from ~7.3 (post-5a) to ~7.5–7.6.

---

## Self-review (2026-04-23)

**1. Placeholder scan:** none. Every PR section has concrete code, commands, or exact file refs.

**2. Internal consistency:** sequencing table matches per-PR dependencies. Testing strategy matches per-PR test plans. Risk table has an entry per PR.

**3. Scope check:** 6 PRs is Phase-5a-sized; cleanly bounded. Each PR is small enough to review in one sitting. No PR mixes two unrelated concerns.

**4. Ambiguity check:**
- PR 1 breaker-open HTTP contract: explicit two-tier (preflight 503 + `Retry-After: 60`; SSE error-frame TOCTOU fallback).
- PR 4 Gemini `.cancel()` availability: explicitly flagged as runtime-verify with documented fallback.
- PR 4 finalizer idempotency: module-level `_finalizing_sessions` guard + `_finalizing_lock`; re-entrance is a silent no-op.
- PR 5 5 MB cap: explicit constant; overflow emits observable event.

Plan-writing can proceed.
