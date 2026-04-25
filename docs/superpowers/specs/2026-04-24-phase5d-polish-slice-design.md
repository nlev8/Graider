# Phase 5d — Polish Slice Design

**Date:** 2026-04-24
**Status:** Specified, awaiting review then implementation plan
**Follows:** Phase 5c (image adapter, 2 PRs shipped 2026-04-24)

---

## Goal

Close out the remaining Plan A Phase 5 ("excellence tier") items not already shipped in 5a/5b/5c. Targets the last gaps in error handling, type-safety, and test quality. After this slice, Plan A Phase 5 is **done** and the codebase quality roadmap (6.8 → 9.1+) has hit its end-state targets.

**Dimensions targeted:** Error handling (8.5→9), Code quality (7→9), Test coverage (9→9.5).

**Non-goal:** Pydantic models for API payloads (Phase-5e candidate), OpenAPI schema generation (depends on Pydantic), APM tracing (blocked on Sentry billing).

---

## Scope — what's IN and OUT

**In Phase 5d (5 PRs):**

| PR | Item | Primary dimension(s) |
|---|---|---|
| 1 | RFC 7807 error responses (backward-compatible) — applies ONLY to `error_response` + `handle_route_errors`. Ad-hoc `jsonify({"error": ...})` call sites are NOT swept in this PR (deferred). | Error handling |
| 2 | mypy strict CI job — config + new CI step with `continue-on-error: true` so untyped modules don't break the build | Code quality |
| 3a | Fix type errors mypy uncovers on 5 small critical modules (auth_decorators, observability.events, supabase_client, supabase_resilient, retry). Grading is its own PR (3b) because it's the largest. | Code quality |
| 3b | Fix type errors in the grading package (grading.state, grading.thread, grading.pipeline) — its own PR because it's the largest module. Final commit flips `continue-on-error: false` and adds the mypy job to branch protection. | Code quality |
| 4 | Mutation testing baseline (mutmut) on 6 critical modules — NOT a CI gate | Test coverage |

**Explicitly deferred to later phases:**
- Pydantic request/response models for API payloads (~200 routes)
- OpenAPI/Swagger generation (depends on Pydantic)
- APM tracing enablement (Sentry billing-blocked)
- mypy strict expansion beyond the 6 critical modules
- Mutation testing as CI gate (too slow for per-PR; revisit if survivors accumulate)

---

## Current-state inventory (verified 2026-04-24)

**Already exists (don't rebuild):**
- `backend/utils/errors.py` — `handle_route_errors` decorator already maps `pybreaker.CircuitBreakerError` → 503 with `Retry-After: 60` (Phase 5b PR 1). Generic `Exception` → `error_response("Internal server error", status_code=500)`. `error_response(message, status_code, code)` returns `jsonify({"error": message, "code": code if code else None}), status_code`.
- 25 routes use `@handle_route_errors`. Frontend reads `response.error` in many places (e.g., `frontend/src/services/api.js`, individual tab components).
- 7 CI jobs in `.github/workflows/ci.yml`: Backend Tests, Frontend Build, Migrations Smoke, Lockfile Drift Check, Ruff Lint, Bandit SAST, Secret Scan. No mypy job.
- `pip-tools` lockfile workflow (`requirements-dev.in` + `requirements-dev.txt` regenerated with Python 3.12 pip-compile).
- `backend/observability/events.py` — `emit(event_name, **kwargs)` JSON-in-message structured event sink (Phase 5a). `_logger = logging.getLogger("backend.observability.events")`.
- `backend/utils/auth_decorators.py` — `require_teacher`, `require_clever_session`, `require_admin` decorators (small file, ~58 lines).
- `backend/supabase_client.py` (and `backend/supabase_resilient.py`) — singleton + retry wrapper (Tier 1 #2 shipped on `feat/supabase-resilience`).
- `backend/grading/` package — split out in Phase 3a, contains `state.py`, `thread.py`, `pipeline.py`.

---

## PR 1 — RFC 7807 error responses (compatibility layer)

**Branch:** `phase5d/pr1-rfc7807-errors` off `main`.

**Goal:** standard error envelope so external API consumers (district webhook callbacks, gradebook passback clients, future SDK consumers) get a typed shape they can program against. **Backward compat preserved:** existing `error` field stays alongside the new RFC 7807 fields so the React frontend keeps working without any frontend change.

**Scope limit (Codex Round-1 finding):** PR 1 standardizes responses from `error_response()` and `handle_route_errors()` ONLY. Routes that bypass those helpers and return raw `jsonify({"error": ...})` directly (e.g., `assistant_routes.py:1482-1518` breaker preflight, scattered throughout other route files) keep their current shape. Sweeping those ad-hoc sites to use `error_response()` is **explicitly deferred** to a follow-up PR (5d follow-on or 5e). The risk table entry below documents this gap so it's visible to future readers.

### Change in `backend/utils/errors.py`

Replace the file contents with:

```python
"""
Shared error handling utilities for Graider API routes.

Error responses follow RFC 7807 (Problem Details for HTTP APIs) with a
backward-compatible `error` field preserved for the React frontend.
Response Content-Type is `application/problem+json` per RFC 7807 § 3.

See https://datatracker.ietf.org/doc/html/rfc7807 for the full spec.
"""
import logging
import functools
from flask import jsonify, request
import pybreaker

logger = logging.getLogger(__name__)

# Base URI for problem-type identifiers. Each problem type gets a path under
# this base, e.g. "/internal", "/breaker-open", "/validation". Districts can
# fetch the URI to get human-readable context (we don't host the docs yet —
# the URI is a stable identifier even when nothing serves it). RFC 7807 § 4.2
# allows opaque type URIs.
PROBLEM_BASE_URI = "https://graider.live/errors"


def _problem_response(
    *,
    type_slug: str,
    title: str,
    status: int,
    detail: str | None = None,
    extra_headers: dict[str, str] | None = None,
):
    """Build an RFC 7807 problem+json response with backward-compat `error` field.

    The `error` field duplicates `detail` so the existing React frontend
    (which reads `response.error`) keeps working without any change.
    """
    body = {
        "type": f"{PROBLEM_BASE_URI}/{type_slug}",
        "title": title,
        "status": status,
        "instance": request.path if request else None,
    }
    if detail is not None:
        body["detail"] = detail
        # Backward-compat: legacy clients (Graider's own React frontend, internal
        # scripts) read `response.error`. Keep it pointing at the same human
        # message as `detail`. Removing this field is a future breaking-change
        # PR coordinated with frontend.
        body["error"] = detail
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Content-Type"] = "application/problem+json"
    if extra_headers:
        for k, v in extra_headers.items():
            resp.headers[k] = v
    return resp


def error_response(message, status_code=400, code=None):
    """Return a consistent JSON error response with proper HTTP status code.

    Backward-compatible signature — every existing caller continues to work.
    Internally, emits RFC 7807 problem+json. The `code` arg (if provided)
    becomes a `code` member field per RFC 7807 § 3.2 ("Members") which permits
    extension fields outside the standard ones.
    """
    type_slug = code or _slug_from_status(status_code)
    body_extra = {"code": code} if code else {}
    resp = _problem_response(
        type_slug=type_slug,
        title=_title_from_status(status_code),
        status=status_code,
        detail=message,
    )
    if body_extra:
        # Re-attach the optional `code` extension on the JSON body.
        json_body = resp.get_json()
        json_body.update(body_extra)
        resp.set_data(jsonify(json_body).get_data())
    return resp


def _slug_from_status(status_code: int) -> str:
    return {
        400: "bad-request",
        401: "unauthenticated",
        403: "forbidden",
        404: "not-found",
        409: "conflict",
        422: "unprocessable",
        429: "rate-limited",
        500: "internal",
        503: "service-unavailable",
    }.get(status_code, f"http-{status_code}")


def _title_from_status(status_code: int) -> str:
    return {
        400: "Bad Request",
        401: "Authentication Required",
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        503: "Service Unavailable",
    }.get(status_code, f"HTTP {status_code}")


def handle_route_errors(f):
    """Decorator that catches unhandled exceptions and returns RFC 7807 problem+json.

    Specializes pybreaker.CircuitBreakerError → 503 with `Retry-After: 60`,
    matching the Phase 5b breaker-open HTTP contract.

    Logs the full traceback server-side but never exposes it to the client.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except pybreaker.CircuitBreakerError as e:
            logger.warning("Circuit breaker open in %s: %s", f.__name__, e)
            resp = _problem_response(
                type_slug="breaker-open",
                title="Service Unavailable",
                status=503,
                detail="LLM provider temporarily unavailable — circuit breaker open",
                extra_headers={"Retry-After": "60"},
            )
            # Preserve the legacy retry_after_seconds field that older callers read
            json_body = resp.get_json()
            json_body["retry_after_seconds"] = 60
            resp.set_data(jsonify(json_body).get_data())
            return resp
        except Exception:
            logger.exception("Unhandled error in %s", f.__name__)
            return _problem_response(
                type_slug="internal",
                title="Internal Server Error",
                status=500,
                detail="Internal server error",
            )
    return wrapper
```

### Tests (extend `tests/test_handle_route_errors_breaker.py` + new `tests/test_rfc7807_errors.py`)

- `tests/test_handle_route_errors_breaker.py` — update existing tests to also assert RFC 7807 fields (`type`, `title`, `status`, `instance`) AND the legacy `error` field both present. `Content-Type` is `application/problem+json`.
- `tests/test_rfc7807_errors.py` (new):
  - `error_response("validation failed", 400, code="invalid-email")` produces body with `type=https://graider.live/errors/invalid-email`, `title="Bad Request"`, `status=400`, `detail="validation failed"`, `instance` = request path, `code="invalid-email"`, `error="validation failed"`.
  - `error_response("not found", 404)` (no code) → `type` slug derived from status (`/errors/not-found`).
  - `handle_route_errors` 500 path → `type=https://graider.live/errors/internal`, includes legacy `error` field.
  - `handle_route_errors` 503 (CircuitBreakerError) path → `type=https://graider.live/errors/breaker-open`, `Retry-After: 60` header, `retry_after_seconds: 60` in body.
  - All error responses set `Content-Type: application/problem+json`.

### Risks + mitigations

| Risk | Mitigation |
|---|---|
| Frontend breaks because response shape changed | Backward-compat `error` field preserved; `Content-Type` change is mostly invisible to fetch callers reading JSON. Verified: `frontend/src/services/api.js:75-106` reads `errData.error` via `response.json()` without strict MIME matching. |
| Some routes call `error_response` with positional args that no longer line up | `error_response(message, status_code, code)` signature unchanged |
| `code` extension field collides with RFC 7807 reserved members | Reserved members per RFC 7807 § 3.1 are `type`, `title`, `status`, `detail`, `instance`. `code` is permitted as an extension. |
| Partial RFC 7807 rollout — many routes still return raw `jsonify({"error": ...})` and bypass the helpers (Codex Round-1 finding) | Acknowledged. PR 1 covers the helper paths only. Follow-up sweep tracked as a known gap; not a 5d blocker because: (a) the helpers cover ~25 decorated routes including all `@handle_route_errors` paths, (b) the React frontend reads `response.error` everywhere so user-facing UX is unaffected, (c) external API consumers are minimal today (district webhooks not yet shipped). |

---

## PR 2 — mypy strict CI job (config only, no code fixes)

**Branch:** `phase5d/pr2-mypy-config` off `main` (after PR 1 merges).

**Goal:** add the type-check infrastructure. Strict on the 6 critical modules; loose elsewhere. PR 3 fixes the errors this surfaces.

### Add `mypy.ini` at repo root

```ini
[mypy]
python_version = 3.12
warn_unused_ignores = True
warn_redundant_casts = True
warn_unused_configs = True
no_implicit_optional = True

# Repo-wide: lenient — everything ELSE in backend/ runs mypy in non-strict mode
# so we don't drown in pre-existing untyped code. Strict mode applies only to
# the 6 critical modules below via `strict = True`.
disallow_untyped_defs = False
check_untyped_defs = False

# Each strict-module section uses `strict = True` (mypy's preset that turns on
# disallow_untyped_defs, disallow_incomplete_defs, check_untyped_defs,
# warn_return_any, no_implicit_reexport, strict_equality, disallow_any_generics,
# disallow_subclassing_any, warn_unused_ignores, no_implicit_optional —
# all the strictness knobs). Per https://mypy.readthedocs.io/en/stable/config_file.html#confval-strict

[mypy-backend.utils.auth_decorators]
strict = True

[mypy-backend.observability.events]
strict = True

[mypy-backend.supabase_client]
strict = True

[mypy-backend.supabase_resilient]
strict = True

[mypy-backend.retry]
strict = True

[mypy-backend.grading.*]
strict = True

# Ignore third-party untyped imports — Supabase/postgrest don't ship type stubs.
[mypy-supabase.*]
ignore_missing_imports = True

[mypy-postgrest.*]
ignore_missing_imports = True

[mypy-pybreaker]
ignore_missing_imports = True

[mypy-google.*]
ignore_missing_imports = True
```

### Add to `requirements-dev.in`

```
mypy>=1.10
types-requests
```

Regenerate `requirements-dev.txt` via `pip-compile -c requirements.txt`.

### Add CI job

In `.github/workflows/ci.yml`, after the `Ruff Lint` job, add:

```yaml
  mypy-strict:
    name: Mypy Strict (Critical Modules)
    runs-on: ubuntu-latest
    # Phase 5d PR 2: untyped modules will produce many errors until PR 3a/3b
    # land the type fixes. Allow this job to fail without blocking the build.
    # The final PR 3b commit removes this `continue-on-error` AND adds the job
    # to branch protection's required-status-checks list.
    continue-on-error: true
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install --require-hashes -r requirements.txt
          pip install --require-hashes -r requirements-dev.txt
      - name: Run mypy on critical modules
        run: |
          mypy backend/utils/auth_decorators.py backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/retry.py backend/grading/
```

**Critical:**
- PR 2 ships the job with `continue-on-error: true` — mypy will fail loudly but the CI build stays green so PRs can still merge.
- PR 3a fixes `auth_decorators`, `observability.events`, `supabase_client`, `supabase_resilient`, `retry`. The job's failure-set should shrink by the end of PR 3a.
- PR 3b's final commit fixes `grading.*`, removes `continue-on-error`, AND updates branch protection to require `Mypy Strict (Critical Modules)`.

### Tests

- New: `tests/test_mypy_config.py` — runs `subprocess.run(["mypy", "--version"])` to confirm mypy is installed and the config file parses.
- This is enough; the real test is the CI job itself, which fails the build if any strict-module file has a type error.

---

## PR 3a — Fix type errors in 5 small critical modules

**Branch:** `phase5d/pr3a-mypy-fixes-small-modules` off `main` (after PR 2 merges).

**Goal:** make per-module `strict = True` mypy pass on the 5 small critical modules. Add annotations where missing. Fix any actual type bugs uncovered.

### Approach: one module per commit

```
fix(mypy): typed auth_decorators
fix(mypy): typed observability.events
fix(mypy): typed retry
fix(mypy): typed supabase_client + supabase_resilient
```

Each commit must keep `mypy <module>` green for the module(s) it touches. The mypy CI job (`continue-on-error: true` from PR 2) will progressively report fewer errors as commits land.

### Strategy for unavoidable `Any`

Where Supabase / postgrest returns are genuinely untyped, use `Any` explicitly with a comment:

```python
def _fetch_class(class_id: str) -> Any:  # postgrest response — untyped upstream
    return supabase.table("classes").select("*").eq("id", class_id).execute()
```

vs reaching for `# type: ignore` (which is louder and harder to grep for).

### Acceptance

- `mypy backend/utils/auth_decorators.py backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/retry.py` exits 0 locally.
- The mypy CI job's error count drops to ZERO for these 5 modules. (Job is still `continue-on-error: true` until PR 3b finishes the grading package.)

### Risks

| Risk | Mitigation |
|---|---|
| mypy uncovers a real type bug that needs a code change beyond annotations | If pure annotation isn't sufficient, fix the bug + add a regression test in the same commit |
| `Any` proliferates because postgrest is untyped | Comment each `Any` with the upstream-untyped reason; revisit if `postgrest-stubs` ever ships |

---

## PR 3b — Fix type errors in grading package

**Branch:** `phase5d/pr3b-mypy-fixes-grading` off `main` (after PR 3a merges).

**Goal:** make `strict = True` mypy pass on `backend/grading/state.py`, `backend/grading/thread.py`, `backend/grading/pipeline.py`. Final commit removes `continue-on-error: true` from the CI job and updates branch protection.

### Approach: per-file commits within the package

```
fix(mypy): typed grading.state
fix(mypy): typed grading.thread
fix(mypy): typed grading.pipeline
chore(ci): require Mypy Strict job + remove continue-on-error
```

The final `chore(ci)` commit:
- Removes `continue-on-error: true` from the `mypy-strict` job in `.github/workflows/ci.yml`.
- Documents the branch-protection update step the operator must take post-merge: add `Mypy Strict (Critical Modules)` to required-status-checks via `gh api -X PATCH ...` or the GitHub UI.

### Acceptance

- `mypy backend/grading/` exits 0 locally.
- Full critical-module mypy run exits 0: `mypy backend/utils/auth_decorators.py backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/retry.py backend/grading/`.
- All 8 CI jobs green (the original 7 + `Mypy Strict (Critical Modules)` now required).
- Branch protection updated post-merge.

### Risks

| Risk | Mitigation |
|---|---|
| Grading package has more type complexity than expected (state-machine logic, dynamic dispatch) | Each file is a separate commit; if one file blows up the PR, isolate it with `# type: ignore[attr-defined]` and a TODO comment, then revisit in 5e |
| Removing `continue-on-error` accidentally fails a future PR's CI on an unrelated module | The mypy run is scoped to the 6 named files only; broader code can still merge with mypy errors elsewhere |

---

## PR 4 — Mutation testing baseline (mutmut, NOT a CI gate)

**Branch:** `phase5d/pr4-mutation-testing` off `main` (after PR 3 merges).

**Goal:** measure how well our tests actually catch bugs in the 6 critical modules. Baseline result is documentation, not a CI gate (mutmut runtime is too slow per PR — minutes-to-hours).

### Add to `requirements-dev.in`

```
mutmut>=2.5
```

Regenerate `requirements-dev.txt`.

### Add mutmut config in `setup.cfg`

mutmut reads its config from `setup.cfg` (`[mutmut]` section) or `pyproject.toml` (`[tool.mutmut]`). It does NOT support a top-level `mutmut.ini` or arbitrary lambda filters.

Append to existing `setup.cfg` (create the file if it doesn't exist):

```ini
[mutmut]
paths_to_mutate=backend/utils/auth_decorators.py,backend/observability/events.py,backend/supabase_client.py,backend/supabase_resilient.py,backend/retry.py,backend/grading/
runner=python -m pytest tests/ -x --quiet --no-header
# Skip lines we don't want mutated. mutmut respects `# pragma: no mutate` per-line
# and the `do_not_mutate` config knob for whole-pattern excludes. We don't list
# per-line excludes here — operators triage survivors and add `# pragma: no mutate`
# inline as needed (the documented mutmut workflow per
# https://mutmut.readthedocs.io/en/latest/).
mutate_only_covered_lines=True
```

`mutate_only_covered_lines=True` skips lines that pytest-cov shows uncovered — useful because mutating uncovered code surfaces test-coverage gaps, not test-quality gaps, and we already have a coverage CI check.

### Add `docs/operations/mutation-testing.md`

Document:
- How to run: `mutmut run --paths-to-mutate backend/grading/`
- How to inspect results: `mutmut show <id>`, `mutmut html`
- Baseline survival count per module (after first run)
- Pattern for triaging survivors:
  1. Survivor has no test asserting the mutated line → add test (action item)
  2. Survivor is logging/observability noise → mark `# pragma: no mutate`
  3. Survivor is a defensive guard against an "impossible" branch → mark + comment

### Tests

- `tests/test_mutmut_config.py` — runs `mutmut --version` to confirm mutmut is installed and config parses.

### Acceptance

- mutmut runs successfully on all 6 critical modules in dev (one-shot, may take 30-60 min)
- Baseline survivor counts recorded in `docs/operations/mutation-testing.md`
- NOT added to CI; this is a manual audit tool

### Risks

| Risk | Mitigation |
|---|---|
| Mutmut surfaces dozens of survivors and the team can't triage them all in this PR | Document the count + commit to a follow-up triage sprint; not a blocker for Phase 5d completion |
| Mutmut slows down test execution to the point of frustration | Don't run by default; only via explicit `mutmut run` command |

---

## Sequencing

**Merge order:** PR 1 → PR 2 → PR 3a → PR 3b → PR 4. Strictly sequential.

**Hard dependencies:**
- PR 2 depends on PR 1 only because we want one PR per concern.
- PR 3a depends on PR 2 (mypy.ini + CI job + dependencies).
- PR 3b depends on PR 3a (less critical — could parallelize, but keeping sequential for review-load smoothing).
- PR 4 depends on PR 3b (PR 3's annotations help mutmut produce more meaningful mutations on typed code).

**Branch-protection update:** PR 2 ships the `Mypy Strict (Critical Modules)` job with `continue-on-error: true` so untyped modules don't break the build. PR 3b's final commit removes `continue-on-error` AND requires the operator to add the job to required-status-checks via `gh api -X PATCH /repos/nlev8/Graider/branches/main/protection ...`. Don't block PRs 2 / 3a on the mypy job.

---

## Testing strategy

- Each PR maintains CI green on the existing 7 jobs PLUS the new `Mypy Strict (Critical Modules)` job (after PR 2 lands).
- Coverage floor stays at 32% (CI enforced).
- No SIS contract touched. 199 Clever/ClassLink/OneRoster tests untouched.
- Mutmut baseline runs once locally; not in CI.

---

## Rollout + risks

**Rollout:** each PR merged independently; Railway auto-deploys backend on merge. No frontend changes required (RFC 7807 backward-compat preserves `error` field).

**Per-PR risks:**

| PR | Risk | Mitigation |
|---|---|---|
| 1 | Some downstream API consumer (district webhook, internal script) chokes on the `Content-Type: application/problem+json` change | Most JSON-parsing clients treat any `application/json*` MIME as JSON; problem+json is structurally JSON. If a real consumer breaks, we can drop the Content-Type back to `application/json` and keep the body shape — the body is the load-bearing change |
| 1 | Frontend reads a field we didn't preserve | Spot-grep `response\.\w+` against frontend; we only NEED `error` and (per breaker contract) `retry_after_seconds`. Both preserved |
| 2 | `pip-compile` regenerates with unrelated drift on dev requirements | Use Python 3.12 pip-compile (matches CI); minimal drift expected |
| 3 | Postgrest type stubs simply don't exist; `Any` proliferates | Document each `Any` with comment; revisit when stubs ship upstream |
| 3 | Grading module too large to type in one PR | Split PR 3 into 3a (auth + observability + supabase) + 3b (grading) |
| 4 | Mutmut surfaces many survivors → distraction | Document the baseline; don't fix all in this PR; create follow-up triage sprint |

**Rollback per PR:** `git revert <squash-commit>`. No stateful changes (no DB migrations, no feature flags, no shared infra).

---

## Effort estimate

| PR | Days |
|---|---|
| 1 | 1 |
| 2 | 0.5 |
| 3a | 1.5-2 |
| 3b | 1-2 |
| 4 | 0.5-1 |
| **Total** | **4.5-6.5 days** |

---

## Expected outcome (dimension deltas after Phase 5d)

| Dimension | Pre-5d | After 5d |
|---|---|---|
| Error handling | 8.5 | 9 (RFC 7807 standard error envelope) |
| Code quality | 7 | 9 (mypy strict on critical modules) |
| Test coverage | 9 | 9.5 (mutation-testing baseline establishes effective-coverage measure) |

Phase 5d completes Plan A Phase 5. Composite avg moves from ~7.65 → **~9.1+** matching the original `project_codebase_improvement_roadmap.md` end-state target.

---

## Deviations from review rounds (2026-04-24)

**Round 1 (Codex pre-review)** flagged 4 MAJOR + 2 MINOR; all reconciled:

| Codex finding | Severity | Resolution |
|---|---|---|
| PR 2/PR 3 CI contract contradiction — config-only PR adds a job that will fail on untyped modules while spec claims each PR stays green | MAJOR | **Accepted.** PR 2's mypy job now ships with `continue-on-error: true`. PR 3b's final commit removes `continue-on-error` AND adds the job to branch protection. |
| `strict` underspecified — config enumerates a subset of strictness flags, CI runs plain `mypy`, but PR 3 acceptance says `mypy --strict` should pass | MAJOR | **Accepted.** Config now uses `strict = True` per-module-section (mypy preset that enables all strictness flags including `disallow_any_generics`, `disallow_subclassing_any`, etc.). Added `warn_unused_configs = True` at top. PR 3a/3b acceptance criteria reworded to "`mypy <files>` exits 0 locally" (no `--strict` flag — config has it). |
| PR 1 scope narrower than goal — `error_response()` + `handle_route_errors()` won't standardize all errors because many routes call `jsonify({"error": ...})` directly | MAJOR | **Accepted as documented limitation.** PR 1 is now explicitly framed as a "compatibility layer" for the helper paths only. Risk-table entry documents that ad-hoc `jsonify({"error": ...})` sites (`assistant_routes.py:1482-1518` etc.) are NOT swept; a follow-up sweep is deferred. Acceptable because: (a) the React frontend reads `response.error` everywhere so user-facing UX is unaffected, (b) external API consumers are minimal today. |
| mutmut config wrong — `mutmut.ini` + `filter = lambda` aren't real mutmut config knobs | MAJOR | **Accepted.** Config moved to `setup.cfg` `[mutmut]` section per https://mutmut.readthedocs.io/en/latest/. Replaced fictional `filter = lambda` with `mutate_only_covered_lines=True` (real knob) + per-line `# pragma: no mutate` comments for survivor triage. |
| PR 3 sizing optimistic — grading is the largest piece and shouldn't be a "fallback split" | MINOR | **Accepted.** PR 3 split into PR 3a (5 small modules: auth_decorators, observability.events, supabase_client, supabase_resilient, retry) + PR 3b (grading package). PR count is now 5 (1 + 2 + 3a + 3b + 4). |
| Add `backend/retry.py` to strict scope — `supabase_resilient` depends on its retry contract directly | MINOR | **Accepted.** `backend/retry.py` added to mypy.ini strict module list and to the CI job's run command. Typed in PR 3a. |

---

## Self-review (2026-04-24)

**1. Placeholder scan:** none. Every PR section has concrete config, code, file refs, and command examples.

**2. Internal consistency:** sequencing is strictly linear (1→2→3→4). Dependencies between PRs are explicit. PR 1's backward-compat `error` field is referenced consistently across "Changes" + "Tests" + "Risks." PR 3's per-module commit strategy maps to the modules listed in PR 2's `mypy.ini`.

**3. Scope check:** 5 PRs (1, 2, 3a, 3b, 4); each is small enough to review in one sitting. No PR mixes concerns (PR 1 = errors helpers, PR 2 = mypy config + non-blocking job, PR 3a/3b = type fixes only, PR 4 = mutmut only).

**4. Ambiguity check:**
- RFC 7807 backward-compat: explicit — `error` field preserved.
- RFC 7807 sweep beyond helpers: explicitly DEFERRED — risk-table entry calls it out as known gap.
- mypy strict scope: explicit — 6 modules listed by name (auth_decorators, observability.events, supabase_client, supabase_resilient, retry, grading.*).
- mypy CI gating: explicit — `continue-on-error: true` in PR 2, removed in PR 3b's final commit.
- Mutation testing as CI gate: explicit — NO, manual baseline only.
- `Content-Type` on errors: explicit — `application/problem+json`.

Plan-writing can proceed.
