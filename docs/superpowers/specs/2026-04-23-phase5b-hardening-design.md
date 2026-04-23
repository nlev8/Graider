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
- `backend/routes/assignment_player_routes.py:344` (OCR call site) was the Phase 5a D1 regression for missing `detail: high` — it's still missing; PR 3 addresses it.

**CI state:** 7 jobs (`Backend Tests`, `Frontend Build`, `Migrations Smoke`, `Lockfile Drift Check`, `Ruff Lint`, `Bandit SAST`, `Secret Scan`). 1620 tests passing on main.

---

## PR 1 — pybreaker circuit breakers

**Goal:** make the adapter seam fail-fast when a provider is unhealthy, instead of hammering a failing endpoint with each caller's request.

**New module:** `backend/services/llm_adapter/breakers.py`

**Granularity:** one breaker per `(provider, model)` tuple — lazy-populated dict. Prevents a flaky `gpt-4o` from blackouting `gpt-4o-mini`. Codex flagged the original per-provider design as too coarse.

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

    Retry+breaker math: with_retry attempts up to MAX_RETRIES=5 times per call.
    A FAILED adapter call (retries exhausted) counts as 1 failure toward
    fail_max=5. So ~25 provider attempts precede breaker open. Transient 5xx
    handled inside retry; only retry-exhausted 5xx reaches the breaker.

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
        emit(
            "llm.breaker.state_change",
            provider=self._provider,
            model=self._model,
            from_state=str(old_state.name),
            to_state=str(new_state.name),
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

**Wrapping**: each adapter's `chat()` and `stream_chat()` wraps the network call via the provider+model's breaker. The breaker gate fires at stream-open, not during iteration.

```python
# openai_adapter.py (sketch)
def chat(self, request: LLMRequest) -> LLMResponse:
    breaker = get_breaker("openai", request.model)
    return breaker.call(self._chat_impl, request)

def _chat_impl(self, request: LLMRequest) -> LLMResponse:
    # existing body — retry, emit, map response
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
# Added inside handle_route_errors' except chain
except pybreaker.CircuitBreakerError:
    return jsonify({
        "error": "LLM provider temporarily unavailable — circuit breaker open",
        "retry_after_seconds": 60,
    }), 503, {"Retry-After": "60"}
```

This makes breaker-open a clean `503 + Retry-After: 60` contract for HTTP callers. For the SSE streaming route in `assistant_routes.py`, the breaker's raise happens BEFORE SSE iteration begins, so the standard JSON-error path handles it.

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

**Tests:**
- All existing Gemini tests (`test_llm_adapter_gemini.py`, `test_llm_adapter_gemini_stream.py`) must pass against the new SDK. Test-mock targets change from `google.generativeai` to `google.genai`.
- Tests in `test_flashcards.py`, `test_study_guide.py`, `test_slide_generator.py` already patch `google.genai` / their adapter-level mocks — verify they still pass.
- Add one test per SDK that pins the field-name contract (`finish_reason.name`, `usage_metadata.prompt_token_count`) so a future SDK break is caught.

**Dependency change:** `google-generativeai` removed from `requirements.in`. `google-genai` stays (already there). Regenerate lockfiles.

**Risk:** the biggest PR in Phase 5b. Subtle SDK field-name differences could surface only at runtime. Mitigation: exercise against captured chunk sequences in the tests before merging.

---

## PR 3 — OpenAI vision `detail: high` hint via `ImagePart.detail`

**Goal:** restore pre-Phase-5a-migration OCR quality. The `assignment_player_routes.py:344` OCR call used `{"detail": "high"}` before migration; the adapter dropped it.

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

**Change in `assignment_player_routes.py:344`:**

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

**(c) `assistant_routes.py` route-level hook** — the SSE route wraps the adapter stream in `stream_with_context(generate())`. Add `GeneratorExit` handling so the adapter's finally runs when Flask signals shutdown:

```python
def generate():
    try:
        for event in adapter.stream_chat(request):
            # existing SSE-event mapping
            yield ...
    except GeneratorExit:
        # Client disconnected or Flask is tearing down the response.
        # Just let the finally in _iterate_stream run cleanup.
        _logger.info("assistant stream generator closed by client disconnect")
        raise
```

**No change needed for Anthropic adapter** — Phase 5a D2's context manager pattern already cleans up correctly.

**Tests:**
- Mock an OpenAI stream that raises partway through; verify `.close()` was called on cleanup.
- Mock a stream that runs to completion; verify `.close()` is still called (via finally).
- For Gemini: mock both "has `.cancel()`" and "has neither" cases — verify graceful degradation.
- Route-level: mock `GeneratorExit` during iteration; verify cleanup path fires.

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
_MAX_TOOL_ARGS_BYTES = 256 * 1024  # 256 KB — generous but bounded

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
| 1 | pybreaker misconfiguration causes legitimate traffic to hit 503s | Trip threshold 5 failures × 5 retries ≈ 25 attempts — very hard to trip from normal usage |
| 1 | Per-model breaker count grows unbounded if users request obscure model names | Lazy dict has no GC; accept minor memory overhead (< 1 KB per breaker × O(10) models) |
| 2 | `google.genai` SDK field-name difference not caught by tests | Add contract-pinning tests; exercise real call paths in dev before merge |
| 2 | Missed install-check string update at `assistant_routes.py:1331` breaks diagnostic error | Grep for "google-generativeai" before merge |
| 3 | OpenAI vision call regression from wrong `detail` values | Typed `Literal["auto", "low", "high"]` enforces valid values at construction time |
| 4 | `.cancel()` doesn't exist on new Gemini SDK's sync stream | Best-effort cleanup with fallback; documented limitation, not a blocker |
| 5 | 256 KB cap blocks legitimate large tool calls | Cap is 10× the largest tool-args we've observed in prod; revisit if `llm.tool_call.args_overflow` events accumulate |
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

## Deviations from original Codex design-review (2026-04-23)

Codex flagged 7 items; reconciled as:

| Codex finding | Resolution |
|---|---|
| Per-provider breaker too coarse — suggests per-(provider, credential) | Changed to per-(provider, model). Single credential per provider env var; multi-tenant routing isn't a Phase 5b concern. Model granularity handles the real failure-isolation issue. |
| Remove 429 from breaker trip | **Accepted.** `RateLimitError` + `status_code == 429` now in `_is_user_error`. Retry handles 429 with Retry-After; breaker stays out of rate-limit state. |
| Document breaker+retry math explicitly | **Accepted.** Noted in `_is_user_error` docstring AND in this spec's PR 1 section. |
| "Open succeeded but no first chunk" streaming gap | **Accepted as known limitation.** Documented; fix deferred. |
| Verify Gemini `.cancel()` exists | **Accepted.** PR 4 implementation flagged to check the SDK at implementation time; best-effort fallback documented. |
| Missing scope: pybreaker install, 503 error contract, Gemini finish-reason map update, PR2 test migration | **All accepted.** Folded into PR 1 (pybreaker + 503) and PR 2 (test migration + finish-reason verification). |
| PR 4 reframe — adapter cleanup alone doesn't fix Railway worker leak | **Accepted.** PR 4 now includes route-level `GeneratorExit` hook in `assistant_routes.py`. |

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
- PR 1 breaker-open HTTP contract: explicit (503 + `Retry-After: 60`).
- PR 4 Gemini `.cancel()` availability: explicitly flagged as runtime-verify with documented fallback.
- PR 5 256 KB cap: explicit constant; overflow emits observable event.

Plan-writing can proceed.
