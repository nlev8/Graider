# Gemini Review Result — Phase 5b Spec

**Reviewed commit:** `020d0d5` on `spec/phase5b-hardening`
**Verdict:** APPROVED_WITH_REVISIONS

## Findings

1. **Breaker math creates cascading worker exhaustion** (PR 1 / lines 188-192)
   pybreaker wraps the entire adapter call, which includes the retry.py primitive. A single adapter failure represents 6 network attempts with exponential backoff. To hit fail_max=5, ~30 request attempts must time out or 5xx. Gunicorn workers will block out for minutes absorbing this latency before the breaker ever opens.
   **Fix:** Breaker must wrap the inner network call inside the retry loop so it tracks raw HTTP failures, or fail_max must be drastically reduced if it must track post-retry exhaustion.

2. **SSE TOCTOU race rejection is flawed** (PR 1 / lines 275-276)
   Rejecting a preflight `breaker.current_state != STATE_OPEN` check due to TOCTOU is a mistake. Circuit breakers are inherently probabilistic. A preflight check before returning `Response(stream_with_context(...))` allows a clean 503 Retry-After for the vast majority of cases where the breaker is already open. Existing SSE error frame logic naturally serves as fallback for the rare TOCTOU edge case.

3. **TTS `wait_for_flush` blocks Flask workers on disconnect** (PR 4 / lines 453-454)
   In disconnect mode (`cancelled=True`), step 4 dictates `tts_stream.wait_for_flush(timeout=15.0)` still runs even though step 6 (audio chunk yield) is skipped. Blocking a Gunicorn worker for up to 15s to wait for TTS to flush audio that will be discarded is a severe resource leak.
   **Fix:** Step 4 must be skipped in the GeneratorExit path to free the worker immediately.

4. **256 KB memory cap too small for legitimate payloads** (PR 5 / line 562)
   256 KB corresponds to ~40-50k words. Bulk transcript analysis, long reading assignments, or compiled worksheets can reasonably exceed this. A safety cap meant to prevent OOMs shouldn't arbitrarily bite legitimate heavy traffic.
   **Fix:** Increase guardrail to 5-10 MB.

5. **Risk 7: Diluted breaker state across Gunicorn workers** (PR 1 / line 295)
   Breakers are module-level singletons per-worker without Redis. With 4 workers, `fail_max=5` actually means it takes 20 consecutive failures (4 workers × 5) to open the breaker universally across the application. This drastically blunts fail-fast protection.
   **Fix:** Add to risk table along with mitigation (e.g., lower fail_max).

6. **Suspicious range citation in PR 4** (lines 448-462)
   Spec claims all cleanup logic lives at `assistant_routes.py:1710-1749`, which explicitly includes cost recording. Bundling heavy operations like cost recording into a range categorized as "pure cleanup logic" suggests the line numbers have drifted or the abstraction inadvertently encompasses setup/reporting logic.

## Things That Worked

- **4xx/429 exception filtering:** pushing user errors and rate limits out of breaker trip math via `exclude=[_is_user_error]` is an excellent, production-grade insight.
- **Granularity choice:** `(provider, model)` tuning is exactly right. Since 4xx errors are excluded, the breaker only trips on 5xx/timeouts, which are inherently model-wide provider outages.
- **Test migration strategy:** contract-pinning tests for the mocked `google.genai` SDK structure is a highly resilient approach to catching future upstream breaks.
- **GeneratorExit handling:** catching the quirk cleanly via `_finalize_assistant_stream_silent` wrapper avoids illegal `yield from` execution and shows deep understanding of Flask's generator lifecycle.
