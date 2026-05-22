# Dependency-Injection Provider (Repository/Supabase Seam) — Design Spec

**Date:** 2026-05-22
**Brainstorm:** Claude (controller) + Codex + Gemini consulted on the mechanism fork; user gave the final picks (motivation, mechanism, scope).
**Predecessor:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` "2026-05-21 Post-Slice-5 3-Model Reconciled Re-Score" — named "no dependency injection" as the dominant remaining Architecture lever holding the dimension at 8 (short of 9).
**Status:** OPEN

---

## 1. Goal

Make the database dependency swappable for a fake at a single switch, instead of monkeypatching the module-level `get_supabase()` accessor in dozens of test sites. Introduce a lightweight, hand-rolled dependency provider at the already-abstracted repository/supabase seam, prove the testability win, and leave the rest of the codebase for proof-driven follow-up slices.

This is the third and final Architecture-7 (now 8) ground from the re-score series. The first two grounds (the `app.py` god-module and the dual publish-path code boundary) closed in Slices 3 through 5.

## 2. Motivation (decided)

**Testability at the seams.** Today ~85 call sites acquire the database via `get_supabase()` / `get_supabase_or_raise()` / duplicate local `_get_supabase()` definitions. Tests that want a fake database must intercept that accessor per-module — repetitive and fragile (Slice 5 caught a real bug where tests patched the wrong module path and silently failed to intercept). A provider with a single test-override hook lets a test inject a fake once; every provider-routed seam picks it up.

The repository layer from Slices 4+5 already uses constructor injection (`JoinCodeSubmissionRepository(sb)`, `repository_for(path_type, sb)`). The remaining gap is that callers still acquire `sb` via `get_supabase()` and pass it in manually. This slice closes that gap at the repository seam.

## 3. Mechanism (3-model reconciled: hand-rolled provider)

Claude and Codex independently recommended a **hand-rolled provider module** (option A) over a DI library (option B, Gemini's lean) or constructor-injection-everywhere (option C). Reconciliation: 2 of 3 converged on A with constraint-grounded reasoning; Gemini's B lean failed to engage the Flask+Celery dual-context constraint or the single-developer maintenance cost (it went off-task attempting implementation and hit quota limits — treated as a weak signal per the failed-to-run-not-failed-low precedent).

**Why A:**
- Zero new runtime dependencies (a DI library is ongoing cost + a learning curve for a one-person team; the testability outcome is identical).
- Works in both Flask-request and Celery-task contexts (plain module functions; no `flask.g`/`current_app` coupling). The Celery/thread grading paths run outside Flask request context — this is the constraint that rules out Flask-native DI. Confirmed by `backend/supabase_client_scoped.py`, which documents the no-request-context rule for background paths.
- Smallest diff. The repo factories already do 90% of the work; the provider wraps them.

**Honest framing for a future re-score:** this is a *lightweight provider-based DI* at one seam, not a DI framework across the whole codebase. It retires the testability objection cleanly. Whether it moves Architecture 8 → 9, or whether a re-score wants the broader conversion (follow-up slices), is a judgment call deferred to the post-slice 3-model re-score.

## 4. Scope (decided: small, one slice)

**In scope (the repository/supabase seam only):**
- New `backend/providers.py`.
- Evolve `repository_for(path_type, sb=None)` and `published_content_repository_for(path_type, sb=None)` to default-resolve `sb` from the provider when omitted (backward-compatible).
- Migrate the seam call sites that acquire `sb` *only* to build a repo: in `backend/services/portal_grading.py`, `backend/tasks/grading_tasks.py`, `backend/routes/student_portal_routes.py` (`submit_assessment`), `backend/routes/student_account_routes.py` (`submit_student_work`).
- A `contextvars`-backed test-override hook.

**Out of scope (follow-up slices, gated on this pattern proving out):**
- The ~80 other `get_supabase()` call sites.
- The 6 duplicate local `_get_supabase()` definitions (`roster_sync.py`, `routes/behavior_routes.py`, `routes/sync_routes.py`, 3× `services/assistant_tools_*.py`).
- AI/LLM clients (`services/llm_adapter/`, `api_keys.py`).
- Config loading (`load_teacher_config`).

## 5. Architecture

```
backend/providers.py
  get_supabase_provider()                → override (if set) else supabase_client.get_supabase()
  get_submission_repository(path_type)   → repository_for(path_type, get_supabase_provider())
  get_published_content_repository(pt)    → published_content_repository_for(pt, get_supabase_provider())
  override_supabase(fake)  [contextmanager, test-only, contextvars-scoped]
```

- **Wraps, does not replace.** `backend/supabase_client.py` keeps `get_supabase()` exactly as-is; the provider calls it. The ~80 non-seam call sites are untouched in this slice.
- **Context-independent.** Plain module functions; works identically in Flask requests and Celery tasks.
- **`contextvars` override**, not a module-global dict — so the override cannot leak across tests or across worker threads, and resets cleanly on `with`-block exit.

## 6. Components

### 6.1 `backend/providers.py` (new)

```python
import contextlib
import contextvars
from typing import Any

_supabase_override: contextvars.ContextVar = contextvars.ContextVar(
    "supabase_override", default=None
)


def get_supabase_provider() -> Any:
    """Resolve the supabase client. Returns the test override if one is set
    in the current context, else the real client from supabase_client."""
    override = _supabase_override.get()
    if override is not None:
        return override
    from backend.supabase_client import get_supabase
    return get_supabase()


def get_submission_repository(path_type):
    """Build the SubmissionRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.submission_repository import repository_for
    return repository_for(path_type, get_supabase_provider())


def get_published_content_repository(path_type):
    """Build the PublishedContentRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.published_content_repository import (
        published_content_repository_for,
    )
    return published_content_repository_for(path_type, get_supabase_provider())


@contextlib.contextmanager
def override_supabase(fake):
    """Test-only: route get_supabase_provider() to `fake` for the duration of
    the with-block. contextvars-scoped so it cannot leak across tests or
    worker threads; resets on exit."""
    token = _supabase_override.set(fake)
    try:
        yield
    finally:
        _supabase_override.reset(token)
```

In-function imports avoid circular-import risk (`providers` ↔ `submission_repository`/`published_content_repository`/`supabase_client`).

### 6.2 Factory evolution (backward-compatible)

`backend/services/submission_repository.py`:
```python
def repository_for(path_type, sb=None):
    if sb is None:
        from backend.providers import get_supabase_provider
        sb = get_supabase_provider()
    # ... rest unchanged (isinstance coercion + adapter dispatch)
```

`backend/services/published_content_repository.py`: same `sb=None` evolution.

Every existing caller that passes `sb` explicitly keeps working byte-identically. Only the `sb is None` branch is new.

### 6.3 Call-site migration (the small, surgical set)

Only sites that acquire `sb` *solely* to build a repo collapse to the provider:

| File | Sites | Change |
|---|---|---|
| `backend/services/portal_grading.py` | `fetch_submission_full_context`, `grade_portal_submission_sync`, `run_portal_grading_thread` | Where `sb` is acquired only to build a repo, use `get_submission_repository(path_type)`. Where `sb` is also used for direct `db.table(...)` queries, keep `get_supabase()` and only route the repo construction through the provider. |
| `backend/tasks/grading_tasks.py` | `on_failure`, no-assessment failure branch | `repository_for(path_type, sb)` → `get_submission_repository(path_type)` (drop the now-unneeded `sb` acquisition where it was only for the repo) |
| `backend/routes/student_portal_routes.py` | `submit_assessment` | the Slice 5 repo-construction lines → provider |
| `backend/routes/student_account_routes.py` | `submit_student_work` | the Slice 5 repo-construction lines → provider |

**Nuance:** several of those sites use `sb` for both repo construction AND direct queries. In those, keep the `get_supabase()` call (the direct query needs it) and route only the repo construction through the provider. Direct-query conversion is a later slice. This keeps the diff small and honest.

## 7. Sequencing — one slice, two PRs

**PR1 (additive):**
- Create `backend/providers.py` + `tests/test_providers.py`.
- Evolve the two factories to `sb=None` default (backward-compatible; every existing caller still works).
- No call-site changes yet. Behavior change impossible by construction.

**PR2 (the rewire):**
- Migrate the seam call sites to the provider.
- Rewrite one or two existing seam tests to use `override_supabase` instead of multi-patch — the proof-of-ergonomics.
- The Slice 5 char net (`TestRouteContractSeam`, 9 tests) stays byte-identical green.

## 8. Testing

**PR1 — `tests/test_providers.py`:**

| Test | Pins |
|---|---|
| `get_supabase_provider()` returns the real client when no override is set | default path |
| `override_supabase(fake)` makes the provider return `fake` inside the block, real client after | override + reset |
| `get_submission_repository(JOIN_CODE)` returns a `JoinCodeSubmissionRepository` wrapping the provider's client | factory-via-provider |
| `get_submission_repository(CLASS)` returns a `ClassSubmissionRepository` | both adapters |
| `get_published_content_repository(JOIN_CODE)` / `(CLASS)` return the right adapters | published-content factory-via-provider |
| `repository_for(path_type)` with no `sb` resolves via the provider | the optional-arg evolution |
| `repository_for(path_type, explicit_sb)` uses `explicit_sb` (back-compat) | the explicit-arg path is unchanged |
| nested/threaded override isolation — one context's fake does not leak to another | the contextvars safety property |

**PR2:**
- At least one existing seam test rewritten from multi-`patch(...get_supabase...)` to `override_supabase(fake)` — proves the ergonomics win is real.
- The Slice 5 `TestRouteContractSeam` (9 tests) stays byte-identical green — the rewire is behavior-preserving.
- Full regression: 0 failed (tolerating the known `test_anthropic_chat_uses_breaker` / `test_gemini_chat_uses_breaker` network flakes that pass in isolation).

## 9. Error handling

| Scenario | Behavior |
|---|---|
| No override set | provider returns `supabase_client.get_supabase()` (which may return `None` if unconfigured — same as today; callers already handle `None`) |
| Override set to a fake | provider returns the fake; resets on `with`-block exit |
| Exception inside the `override_supabase` block | `finally: reset(token)` runs; no leak |
| Worker thread runs concurrently with a test override | `contextvars` isolates per-context; the worker doesn't see the test's fake |
| Circular import at module load | avoided by in-function imports in `providers.py` and the factory `sb is None` branch |

## 10. Success criteria

- Both PRs merged, 9 CI checks green.
- A test demonstrably swaps the database for a fake via a single `override_supabase(fake)` instead of multi-module patching.
- The Slice 5 char net stays byte-identical green (zero behavior change at the rewired seams).
- `backend/providers.py` is the single resolution point for the repository/supabase seam; the factories default-resolve from it.
- Closeout dated section in the assessment doc.
- Post-slice 3-model reconciled re-score weighing whether Architecture moves 8 → 9, with honest framing (lightweight provider DI at one seam, not a framework across the codebase).

## 11. Risks

| Risk | Mitigation |
|---|---|
| `contextvars` override leaks across tests/threads | the contextmanager always `reset(token)` in `finally`; an isolation test pins the property |
| Circular import (`providers` ↔ repos ↔ supabase_client) | in-function imports in both `providers.py` and the factory `sb is None` branch |
| The rewire accidentally changes a seam's behavior | char-net-first discipline; `TestRouteContractSeam` stays byte-identical; the repo object built via the provider is identical to the one built via `repository_for(pt, get_supabase())` |
| Re-score says "one seam isn't enough DI" | recorded as an accepted outcome — this slice proves the pattern; broader conversion is sequenced follow-up slices, not a failure of this one |
| Over-conversion creep (touching direct-query `get_supabase()` sites) | explicit out-of-scope list; only repo-construction sites migrate |

## 12. Out of scope (recorded)

- The ~80 non-seam `get_supabase()` call sites.
- The 6 duplicate `_get_supabase()` definitions.
- AI/LLM clients and `api_keys.py`.
- Config loading.
- Any DI library adoption (revisit only if a re-score says the hand-rolled provider doesn't retire the objection).

## 13. Approval

This is the design. The next step per the `superpowers:brainstorming` flow is user review of this written spec, followed by `superpowers:writing-plans` to produce the implementation plan.
