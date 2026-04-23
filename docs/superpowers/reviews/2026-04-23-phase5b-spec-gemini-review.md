# Gemini Review Packet — Phase 5b Hardening Spec

**For:** Gemini (independent third-party review)
**Date:** 2026-04-23
**Spec path (repo):** `docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md`
**Spec commit:** `020d0d5` on branch `spec/phase5b-hardening`
**Prior review:** 6 rounds with Codex (gpt-5-codex, high reasoning). Round 6 verdict: APPROVED.

---

## What I want from you

A fresh, independent read of the Phase 5b design. Codex has already scrutinized it repeatedly; I want a different model's perspective before the implementation plan lands. Focus on things Codex may have over-normalized to across 6 rounds of iteration.

**Output format (required):**

1. **Verdict** — one of `APPROVED`, `APPROVED_WITH_REVISIONS`, `BLOCK`.
2. **Findings** — numbered list. Each finding cites `spec_section_or_line` + a one-paragraph rationale. If the finding is factual (a claim is wrong), say what is wrong. If it's judgmental (a design choice is off), say what you'd do instead and why.
3. **Things that worked** — a short section calling out what's genuinely solid, so the signal-to-noise of future revisions stays calibrated.

Keep the review under ~800 words unless you find material design-level problems.

---

## Review directives — things to probe specifically

**A. Design soundness** — the spec makes several non-obvious architectural choices. Are they right?

1. **Circuit-breaker granularity.** Spec picks per-`(provider, model)` keying (e.g., `(openai, gpt-4o)`). Alternatives considered and rejected: per-provider (too coarse — one flaky model takes out all), per-`(provider, model, credential)` (unbounded in BYOK context). Is per-`(provider, model)` the right altitude? What failure modes does it miss?

2. **Breaker trip math.** `fail_max=5`, `reset_timeout=60s`, retries=`1 initial + 5 retries = 6 provider attempts` per call, so ~30 provider attempts precede trip. Is 30 too lax? Too aggressive? Does this interact badly with Graider's existing retry primitive (`backend/retry.py`)?

3. **SSE breaker-open contract.** Non-streaming HTTP routes return `503 + Retry-After: 60`. The SSE route (`assistant_routes.py`) can't, because Flask flushes `Response(stream_with_context(generate()))` headers before the generator starts iterating. Spec accepts that the SSE route will emit an `error` SSE frame with `content: "CircuitBreakerError..."` instead of a 503. The frontend already handles `error` frames. A preflight `breaker.current_state != OPEN` check was rejected due to TOCTOU. Is the TOCTOU argument tight, or is there a cleaner path?

4. **`_finalize_assistant_stream()` helper (PR 4).** 9 cleanup responsibilities, 2 call modes (normal + disconnect). The `GeneratorExit` path uses a `_finalize_assistant_stream_silent()` wrapper that discards yields because `yield from` inside `except GeneratorExit` is illegal. Is the split into yielding/silent helpers cleanly idempotent, or is there a subtle bug (e.g., re-entrance, partial state, double-close on `tts_stream`)?

5. **256 KB tool-args cap (PR 5).** Applied to OpenAI + Anthropic streaming tool-call args. Not applied to Gemini (args arrive atomically). Spec lists known large payloads: `generate_document.content`, `generate_worksheet.questions`, `save_assignment_config.document_text`, `create_automation.steps`. Is 256 KB large enough for any of those? Is there a case where the cap would bite legitimate traffic? (Spec's defense: overflow emits `llm.tool_call.args_overflow` event so the value can be retuned.)

**B. Scope.** 6 PRs. Anything listed that shouldn't be in Phase 5b? Anything missing that should be? (Image-gen adapter, TTS adapter, APM, mypy, Pydantic, RFC 7807 are all deferred — is any of those actually a blocker?)

**C. Risks not in the risk table.** Spec enumerates 6 risks, one per PR. Any 7th risk you'd name?

**D. Citation spot-check.** Several claims cite file paths + line numbers. Flag any that smell stale even without code access (e.g., a citation that claims cleanup logic at a range that also includes cost recording or TTS setup would be suspicious).

---

## Context — project background

Graider is a Flask + React AI grading assistant for educators (grades 6-12), deployed to Railway (app.graider.live). Phase 5a just landed — 7 PRs over ~3 days — that introduced the LLM adapter seam. Phase 5b is the followup tightening pass for that seam.

**Tech stack relevant to review:**
- Python 3.12, Flask, React + Vite
- LLM providers: OpenAI (`openai` SDK), Anthropic (`anthropic` SDK), Google Gemini (`google.generativeai` — deprecated, being migrated)
- BYOK: per-teacher API keys (`backend/api_keys.py:48-103`), not a single provider env-var
- Retry primitive: `backend/retry.py` with `MAX_RETRIES=5` default exponential backoff
- Observability: structured JSON events via `backend.observability.events.emit`, Sentry breadcrumbs on error
- SSE streaming only on `assistant_routes.py` (live voice+text chat)
- pybreaker (to be added in PR 1) — in-process circuit breaker library, per-worker singletons under Gunicorn

**Phase 5a recap (shipped 2026-04-22):**
- Bandit + trufflehog CI
- pip-tools lockfile with `--require-hashes`
- Structured JSON logging
- LLM adapter layer (`backend/services/llm_adapter/`) with `chat()` + `stream_chat()` on all 3 providers
- `with_retry()` applied uniformly; Sentry breadcrumbs on all error paths

**What Phase 5b does NOT touch:**
- Clever / ClassLink / OneRoster SIS contracts (199 tests protect these)
- DB migrations, RLS policies (Phase 4.2 territory)
- Feature flags (none added; none removed)

---

## Review rounds summary (so you can see what Codex already caught)

| Round | Verdict | Key findings resolved |
|---|---|---|
| 1 (design) | APPROVED_WITH_REVISIONS | Per-provider breaker too coarse → changed to per-(provider, model); 429 in breaker trip → excluded; missing scope items (pybreaker install, 503 contract, GeneratorExit route hook) folded in |
| 2 (spec commit) | BLOCK | BYOK rationale wrong; retry math off (~25 → ~30); PR 2 test migration incomplete; PR 4 `GeneratorExit` sketch bypassed route-owned cleanup; SSE breaker-open contract wrong (returns error frame not 503) |
| 3 | BLOCK | Retry-math contradiction; `_finalize_assistant_stream` under-specified; SSE error-frame example used `message` instead of `content`; pybreaker listener `old_state.name` unguarded |
| 4 | BLOCK | Residual `~25` in review-history table; contradictory earlier sketch; 8-item cleanup list didn't match source; stale `:1403-1424` citation (TTS setup not cleanup); BYOK rationale contradicted itself in appendix |
| 5 | BLOCK | Line 611 stale BYOK rationale; line 402 "steps 5" vs step-6 numbering; line 444 single-quoted dict literal |
| 6 (fresh pass) | **APPROVED** | All prior items resolved; regression sweep clean |

---

## The spec (inline for review convenience)

The full spec is reproduced below. The authoritative file is `docs/superpowers/specs/2026-04-23-phase5b-hardening-design.md` at commit `020d0d5`.

---

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

    Retry+breaker math: with_retry attempts 1 initial + MAX_RETRIES=5 retries
    = 6 provider attempts per call. A FAILED adapter call (retries exhausted)
    counts as 1 failure toward fail_max=5. So ~30 provider attempts precede
    breaker open. Transient 5xx handled inside retry; only retry-exhausted
    5xx reaches the breaker.

    429 (rate limit) is EXCLUDED here — retry+backoff with Retry-After is
    the right response to throttling, not a circuit break.
    """
    name = type(exc).__name__
    user_error_names = {
        "BadRequestError",
        "AuthenticationError",
        "PermissionDeniedError",
        "NotFoundError",
        "UnprocessableEntityError",
        "RateLimitError",
    }
    if name in user_error_names:
        return True
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
        emit(
            "llm.breaker.state_change",
            provider=self._provider,
            model=self._model,
            from_state=getattr(old_state, "name", None) or "initial",
            to_state=getattr(new_state, "name", None) or "unknown",
        )


def get_breaker(provider: str, model: str) -> pybreaker.CircuitBreaker:
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

**Wrapping**: each adapter's `chat()` and `stream_chat()` wraps the network call via the provider+model's breaker. The breaker gate fires at stream-open, not during iteration.

```python
def chat(self, request: LLMRequest) -> LLMResponse:
    breaker = get_breaker("openai", request.model)
    return breaker.call(self._chat_impl, request)
```

For `stream_chat`, the breaker wraps the stream-open side only:

```python
def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]:
    breaker = get_breaker("openai", request.model)
    stream = breaker.call(self._open_stream, request)
    yield from self._iterate_stream(stream, request)
```

**Known limitation documented in the spec:** a stream that opens cleanly but yields zero chunks before erroring doesn't count toward trip. Revisit if evidence accumulates — not worth the complexity for an unmeasured failure mode.

**Error-response contract** — extend `backend/utils/errors.py::handle_route_errors`:

```python
except pybreaker.CircuitBreakerError:
    return jsonify({
        "error": "LLM provider temporarily unavailable — circuit breaker open",
        "retry_after_seconds": 60,
    }), 503, {"Retry-After": "60"}
```

This makes breaker-open a clean `503 + Retry-After: 60` contract for **non-streaming** HTTP callers.

**SSE route contract is different.** `assistant_routes.py` constructs `Response(stream_with_context(generate()))` and returns BEFORE `generate()` starts iterating (`assistant_routes.py:1504, 1753-1761`). By the time the breaker's `CircuitBreakerError` fires inside `stream_chat()`, the HTTP response header is already flushed — we can't turn that into a 503. The generator's `except Exception` handler at `assistant_routes.py:1703-1708` catches it and emits an SSE `error` frame instead.

**Design decision:** accept the SSE `error` frame as the breaker-open contract for this one route. Clients already handle SSE `error` frames (they surface as chat failures in the UI). The alternative — a preflight `get_breaker(...).current_state != pybreaker.STATE_OPEN` check before constructing the `Response(...)` — adds a TOCTOU race (breaker could open between check and call) and surfaces a distinct error path that UI code would need to handle. Not worth the complexity for a rare condition.

**What the error frame looks like** (existing route handler at `assistant_routes.py:1708`, no change):
```json
{"type": "error", "content": "CircuitBreakerError: Circuit 'openai:gpt-4o' is open"}
```

Note: the payload field is `content`, not `message`. The frontend consumes `event.content` at `frontend/src/components/AssistantChat.jsx:507` (`last.content + '\n\n' + event.content`). The existing error-frame handler renders this inline in the assistant's last message with `isError: true`, styling it as a transient chat-failure banner. Operators see the event in logs; users see the banner and retry. Consistent with the non-streaming 503 behavior from the user's perspective.

**Dependency addition:** `pybreaker>=1.0` in `requirements.in`. Regenerate lockfiles per `docs/dependencies.md`.

**Tests (new `tests/test_llm_adapter_breakers.py`):**
- Trip after 5 network errors on one (provider, model) key.
- Does NOT trip on `BadRequestError`, `AuthenticationError`.
- Does NOT trip on `RateLimitError` (429).
- Half-open after 60s; probe success closes, probe failure re-opens.
- State-change emits `llm.breaker.state_change` with correct from/to.
- Per-model isolation: flooding `gpt-4o` with failures doesn't open `gpt-4o-mini`.
- `handle_route_errors` test: raise `pybreaker.CircuitBreakerError` in a route handler → 503 response with `Retry-After: 60` header.

**Risk:** pybreaker is a new runtime dep; confirm it plays nicely with Gunicorn's process model (module-level singletons are per-worker, which is fine — each worker trips independently). No shared Redis-backed breaker for Phase 5b.

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
    detail: Literal["auto", "low", "high"] | None = None
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
            yield ...
    finally:
        try:
            stream.close()
        except Exception:
            _logger.debug("openai stream.close() raised on cleanup", exc_info=True)
```

**(b) Gemini adapter** — retain a handle to the underlying raw iterator. Call `.cancel()` in finally if the method exists:

```python
def _iterate_stream(self, stream, request):
    try:
        for chunk in stream:
            yield ...
    finally:
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

Implementation: factor the route's post-stream cleanup into a `_finalize_assistant_stream()` helper that's called from BOTH normal completion AND the `GeneratorExit` branch.

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
    - Steps 1-2 (persistence), 4-5 (TTS flush/close), 7-9 (flag + cost
      cleanup) STILL RUN. These are pure state cleanup that must happen
      regardless of client connectivity.
    - Step 3 (sentence-buffer flush + send) is skipped — sending more text
      to TTS when the client is gone wastes Eleven Labs credits.
    - Step 6 (yield audio chunks) is skipped — no client to receive them.
    - Step 9's cost SSE frame is also suppressed in disconnect mode, but
      the underlying _record_assistant_cost call still runs so cost
      tracking in the backend DB is accurate.
    """
```

**Why a generator, not a plain function:** step 6 (audio-chunk yields) needs to happen FROM INSIDE the Flask generator's yield context. Returning audio chunks as a list would buffer potentially-large PCM data in memory. A generator lets us stream them directly.

**Call sites in the route:**

```python
def generate():
    try:
        for event in adapter.stream_chat(request):
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
        _finalize_assistant_stream_silent(
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
        error_msg = str(e)
        if "APIError" in type(e).__name__ or "AuthenticationError" in type(e).__name__:
            error_msg = f"API error ({active_provider}): {error_msg}"
        error_payload = {"type": "error", "content": error_msg}
        yield f"data: {json.dumps(error_payload)}\n\n"
        yield from _finalize_assistant_stream(
            session_id=session_id, conv=conv, messages=messages,
            tts_stream=tts_stream, sentence_buffer=sentence_buffer,
            audio_out_queue=audio_out_queue,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tts_chars=total_tts_chars,
            active_model=active_model,
            cancelled=True,
        )
```

**`_finalize_assistant_stream_silent()` thin wrapper:**
```python
def _finalize_assistant_stream_silent(**kwargs):
    """Run finalize's state cleanup but discard any SSE yields.
    For disconnect path where client is gone."""
    for _ in _finalize_assistant_stream(**kwargs):
        pass
```

**Observability:** `_finalize_assistant_stream` emits `assistant.stream.finalized` with `cancelled`, `duration_ms`, `total_input_tokens`, `total_output_tokens`, `total_tts_chars` so operators can see disconnect patterns.

**No change needed for Anthropic adapter** — Phase 5a D2's context manager pattern already cleans up correctly.

**Tests:**
- Mock an OpenAI stream that raises partway through; verify `.close()` was called on cleanup.
- Mock a stream that runs to completion; verify `.close()` is still called (via finally).
- For Gemini: mock both "has `.cancel()`" and "has neither" cases — verify graceful degradation.
- Route-level: mock `GeneratorExit` during iteration; verify cleanup path fires.

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
_MAX_TOOL_ARGS_BYTES = 256 * 1024  # 256 KB — generous but bounded

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

**Cap rationale:** 256 KB is a deliberate guardrail, NOT a measured against-prod-data number. Some Graider tool calls are intentionally large (`generate_document.content`, `generate_worksheet.questions`, `save_assignment_config.document_text`, `create_automation.steps`). Overflow emits an observable event rather than silently truncating.

**Streaming error-path tests:** one test per provider. Inject an exception mid-stream, verify:
- `llm.call.error` emitted with `duration_ms > 0`
- `sentry_sdk.add_breadcrumb` called
- Exception propagates cleanly to caller (not swallowed)
- Any partial state (chunks_seen, partial_tool_call_ids) included in breadcrumb data

---

## PR 6 — Dead-dep cleanup

**Goal:** remove two packages with zero Python importers. Verified in Phase 5a code review.

**Changes:**
- `requirements.in` — remove `webdriver-manager>=4.0.0` line.
- `requirements-dev.in` — remove `selenium>=4.15.0` line.
- Regenerate both lockfiles with Python 3.12 + `pip-compile --generate-hashes --allow-unsafe`.
- Update header comment in `requirements.in`.

**Pre-merge safety check:** `grep -rn "import selenium\|from selenium\|webdriver.manager\|webdriver_manager" backend/ --include="*.py" | grep -v __pycache__` must return zero hits.

---

## Sequencing + dependencies

**Merge order:** PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6.

**Hard dependencies:**
- PR 1 requires `pybreaker` added to `requirements.in` — regen lockfiles in PR 1 itself.
- PR 5 depends on PR 1 landed.
- PR 4 touches `openai_adapter.py` + `gemini_adapter.py`. PR 2 touched `gemini_adapter.py` entirely. Landing PR 2 first avoids massive merge conflicts in PR 4.

---

## Per-PR risks

| PR | Risk | Mitigation |
|---|---|---|
| 1 | pybreaker misconfiguration causes legitimate traffic to hit 503s | Trip threshold fail_max=5 × (1 initial + 5 retries) = ~30 provider attempts before open — very hard to trip from normal usage |
| 1 | Per-model breaker count grows unbounded if users request obscure model names | Lazy dict has no GC; accept minor memory overhead (< 1 KB per breaker × O(10) models) |
| 2 | `google.genai` SDK field-name difference not caught by tests | Add contract-pinning tests; exercise real call paths in dev before merge |
| 2 | Missed install-check string update at `assistant_routes.py:1331` breaks diagnostic error | Grep for "google-generativeai" before merge |
| 3 | OpenAI vision call regression from wrong `detail` values | Typed `Literal["auto", "low", "high"]` enforces valid values at construction time |
| 4 | `.cancel()` doesn't exist on new Gemini SDK's sync stream | Best-effort cleanup with fallback; documented limitation, not a blocker |
| 5 | 256 KB cap blocks legitimate large tool calls | Cap is a deliberate guardrail with observable overflow event; retune if events accumulate |
| 6 | `selenium` accidentally used somewhere we missed | Pre-merge grep verification |

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

---

## Expected outcome (dimension deltas after Phase 5b)

| Dimension | Pre-5b | After 5b |
|---|---|---|
| Operational safety | 9 | 9.5 (breaker + stream cleanup) |
| Error handling | 7.5 | 8.5 (breaker semantics explicit) |
| Code quality | 6.5 | 7 (Gemini on maintained SDK, dead deps gone) |
| Data integrity | 8.5 | 8.75 (OCR detail hint restored) |
| Test coverage | 9 | 9 (streaming error-paths added but no major line-coverage shift) |

Phase 5b moves the composite average from ~7.3 (post-5a) to ~7.5–7.6.

---

## End of spec

Please produce the verdict, findings, and "things that worked" section described at the top of this packet.
