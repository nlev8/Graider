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

**In Phase 5d (4 PRs):**

| PR | Item | Primary dimension(s) |
|---|---|---|
| 1 | RFC 7807 error responses (backward-compatible) | Error handling |
| 2 | mypy strict CI job — config + new CI step (no code fixes yet) | Code quality |
| 3 | Fix type errors mypy uncovers on 4 critical modules | Code quality |
| 4 | Mutation testing baseline (mutmut) on same 4 critical modules — NOT a CI gate | Test coverage |

**Explicitly deferred to later phases:**
- Pydantic request/response models for API payloads (~200 routes)
- OpenAPI/Swagger generation (depends on Pydantic)
- APM tracing enablement (Sentry billing-blocked)
- mypy strict expansion beyond the 4 critical modules
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

## PR 1 — RFC 7807 error responses (backward-compatible)

**Branch:** `phase5d/pr1-rfc7807-errors` off `main`.

**Goal:** standard error envelope so external API consumers (district webhook callbacks, gradebook passback clients, future SDK consumers) get a typed shape they can program against. **Backward compat preserved:** existing `error` field stays alongside the new RFC 7807 fields so the React frontend keeps working without any frontend change.

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
| Frontend breaks because response shape changed | Backward-compat `error` field preserved; `Content-Type` change is mostly invisible to fetch callers reading JSON |
| Some routes call `error_response` with positional args that no longer line up | `error_response(message, status_code, code)` signature unchanged |
| `code` extension field collides with RFC 7807 reserved members | Reserved members per RFC 7807 § 3.1 are `type`, `title`, `status`, `detail`, `instance`. `code` is permitted as an extension. |

---

## PR 2 — mypy strict CI job (config only, no code fixes)

**Branch:** `phase5d/pr2-mypy-config` off `main` (after PR 1 merges).

**Goal:** add the type-check infrastructure. Strict on the 4 critical modules; loose elsewhere. PR 3 fixes the errors this surfaces.

### Add `mypy.ini` at repo root

```ini
[mypy]
python_version = 3.12
plugins =
warn_unused_ignores = True
warn_redundant_casts = True
no_implicit_optional = True

# Repo-wide: lenient — everything ELSE in backend/ runs mypy in non-strict mode
# so we don't drown in pre-existing untyped code. Strict mode applies only to
# the 4 critical modules below.
disallow_untyped_defs = False
check_untyped_defs = False

[mypy-backend.utils.auth_decorators]
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
warn_return_any = True
no_implicit_reexport = True
strict_equality = True

[mypy-backend.observability.events]
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
warn_return_any = True
no_implicit_reexport = True
strict_equality = True

[mypy-backend.supabase_client]
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
warn_return_any = True
no_implicit_reexport = True
strict_equality = True

[mypy-backend.supabase_resilient]
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
warn_return_any = True
no_implicit_reexport = True
strict_equality = True

[mypy-backend.grading.*]
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
warn_return_any = True
no_implicit_reexport = True
strict_equality = True

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
          mypy backend/utils/auth_decorators.py backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/grading/
```

**Critical:** add `Mypy Strict (Critical Modules)` to branch protection's required-status-checks list AFTER PR 3 lands (don't block on it during PR 2/3).

### Tests

- New: `tests/test_mypy_config.py` — runs `subprocess.run(["mypy", "--version"])` to confirm mypy is installed and the config file parses.
- This is enough; the real test is the CI job itself, which fails the build if any strict-module file has a type error.

---

## PR 3 — Fix type errors in 4 critical modules

**Branch:** `phase5d/pr3-mypy-fixes` off `main` (after PR 2 merges).

**Goal:** make `mypy --strict` pass on the 4 critical modules. Add annotations where missing. Fix any actual type bugs uncovered.

### Approach: one module at a time

Each commit fixes ONE module:

1. `backend/utils/auth_decorators.py` (~58 lines, 3 decorators) — straightforward
2. `backend/observability/events.py` — `emit()` signature is `**kwargs` heavy; may need `# type: ignore` on the `_logger.log(level, msg)` line if mypy can't infer level
3. `backend/supabase_client.py` + `backend/supabase_resilient.py` — Supabase client is untyped; expect heavy use of `Any` for postgrest return values, but the resilient wrapper's signatures should be precise
4. `backend/grading/state.py`, `backend/grading/thread.py`, `backend/grading/pipeline.py` — biggest module; may need significant annotation work

### Strategy for unavoidable `Any`

Where Supabase returns are genuinely untyped (`postgrest` doesn't ship stubs), use `Any` explicitly with a comment:

```python
def _fetch_class(class_id: str) -> Any:  # postgrest response — untyped upstream
    return supabase.table("classes").select("*").eq("id", class_id).execute()
```

vs reaching for `# type: ignore` (which is louder and harder to grep for).

### Commits per module

```
fix(mypy): typed auth_decorators
fix(mypy): typed observability.events
fix(mypy): typed supabase_client + supabase_resilient
fix(mypy): typed grading package
```

Each commit must keep `mypy <module>` green for that module. Don't bundle.

### Acceptance

- `mypy backend/utils/auth_decorators.py backend/observability/events.py backend/supabase_client.py backend/supabase_resilient.py backend/grading/` exits 0 locally.
- All 7 CI jobs green, including `Mypy Strict (Critical Modules)`.
- Add `Mypy Strict (Critical Modules)` to branch protection required checks list.

### Risks

| Risk | Mitigation |
|---|---|
| mypy uncovers a real type bug that needs a code change beyond annotations | If pure annotation isn't sufficient, fix the bug + add a regression test in the same commit |
| `Any` proliferates because postgrest is untyped | Comment each `Any` with the upstream-untyped reason; revisit if `postgrest-stubs` ever ships |
| Strict mypy is too brittle on grading package | If grading needs more time, split PR 3 into PR 3a (auth + observability + supabase) and PR 3b (grading) |

---

## PR 4 — Mutation testing baseline (mutmut, NOT a CI gate)

**Branch:** `phase5d/pr4-mutation-testing` off `main` (after PR 3 merges).

**Goal:** measure how well our tests actually catch bugs in the 4 critical modules. Baseline result is documentation, not a CI gate (mutmut runtime is too slow per PR — minutes-to-hours).

### Add to `requirements-dev.in`

```
mutmut>=2.5
```

Regenerate `requirements-dev.txt`.

### Add `mutmut.ini` config

```ini
[mutmut]
paths_to_mutate =
    backend/utils/auth_decorators.py,
    backend/observability/events.py,
    backend/supabase_client.py,
    backend/supabase_resilient.py,
    backend/grading/

runner = python -m pytest tests/ -x --quiet --no-header

# Skip mutations in lines matching these patterns (logging, imports, debug)
filter = lambda line: not line.startswith(("import ", "from ", "logger.", "_logger."))
```

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

- mutmut runs successfully on all 4 critical modules in dev (one-shot, may take 30-60 min)
- Baseline survivor counts recorded in `docs/operations/mutation-testing.md`
- NOT added to CI; this is a manual audit tool

### Risks

| Risk | Mitigation |
|---|---|
| Mutmut surfaces dozens of survivors and the team can't triage them all in this PR | Document the count + commit to a follow-up triage sprint; not a blocker for Phase 5d completion |
| Mutmut slows down test execution to the point of frustration | Don't run by default; only via explicit `mutmut run` command |

---

## Sequencing

**Merge order:** PR 1 → PR 2 → PR 3 → PR 4. Strictly sequential.

**Hard dependencies:**
- PR 2 depends on PR 1 only because we want one PR per concern.
- PR 3 depends on PR 2 (mypy.ini + CI job + dependencies).
- PR 4 depends on PR 3 (PR 3's annotations help mutmut produce more meaningful mutations on typed code).

**Branch-protection update:** add `Mypy Strict (Critical Modules)` to required checks AFTER PR 3 merges. Don't block PRs 2-3 on it.

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
| 3 | 2-3 |
| 4 | 0.5-1 |
| **Total** | **4-5.5 days** |

---

## Expected outcome (dimension deltas after Phase 5d)

| Dimension | Pre-5d | After 5d |
|---|---|---|
| Error handling | 8.5 | 9 (RFC 7807 standard error envelope) |
| Code quality | 7 | 9 (mypy strict on critical modules) |
| Test coverage | 9 | 9.5 (mutation-testing baseline establishes effective-coverage measure) |

Phase 5d completes Plan A Phase 5. Composite avg moves from ~7.65 → **~9.1+** matching the original `project_codebase_improvement_roadmap.md` end-state target.

---

## Self-review (2026-04-24)

**1. Placeholder scan:** none. Every PR section has concrete config, code, file refs, and command examples.

**2. Internal consistency:** sequencing is strictly linear (1→2→3→4). Dependencies between PRs are explicit. PR 1's backward-compat `error` field is referenced consistently across "Changes" + "Tests" + "Risks." PR 3's per-module commit strategy maps to the modules listed in PR 2's `mypy.ini`.

**3. Scope check:** 4 PRs; each is small enough to review in one sitting. No PR mixes concerns (PR 1 = errors only, PR 2 = config only, PR 3 = type fixes only, PR 4 = mutmut only).

**4. Ambiguity check:**
- RFC 7807 backward-compat: explicit — `error` field preserved.
- mypy strict scope: explicit — 4 modules listed by name.
- Mutation testing as CI gate: explicit — NO, manual baseline only.
- `Content-Type` on errors: explicit — `application/problem+json`.

Plan-writing can proceed.
