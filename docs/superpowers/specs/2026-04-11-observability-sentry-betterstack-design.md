# Observability v1: Sentry error tracking + BetterStack uptime — Design Spec

**Status:** Draft — awaiting user approval before writing implementation plan.
**Author:** Alex + Claude (brainstorming 2026-04-11)
**Reviewers:** Codex (approved Sections 1 & 2 with tighten-ups folded in), Gemini (approved Sections 1 & 2).
**Tier 1 item:** District production reliability #3 (monitoring/alerting).

---

## Goal

Give Graider its first production observability layer so operational failures become visible *before* a district notices. Specifically:

1. Every unhandled backend exception is captured, grouped, and alertable via **Sentry Cloud (Developer / free tier)**.
2. `/healthz` is externally probed every 60 seconds from multiple regions via **BetterStack (Team tier, $10/mo)**; sustained downtime pages the on-call human.
3. A public status page at **`status.graider.live`** gives district IT a vendor-review-ready signal.
4. Student PII is never shipped to a third-party SaaS (FERPA-clean by construction).
5. Alerts are tuned to avoid fatigue — the pager fires only when a real district is being harmed.

## Non-goals (explicitly deferred)

- **Performance monitoring / APM tracing.** Disabled in Sentry config (`traces_sample_rate=0.0`). Can be turned on later by flipping a single env var; no code changes needed.
- **Business metrics / dashboards** (grading success rate, submission throughput, retry counts over time). Deferred to a separate plan — those are Tier 1 #3 sub-project C.
- **Structured logging migration** (JSON logs with searchable fields). Deferred — Tier 1 #3 sub-project D.
- **Staging environment.** No staging exists today. If one is added later, the path is a separate Sentry DSN + environment tag, not re-enabling the production DSN for staging traffic.
- **PagerDuty integration.** BetterStack's built-in on-call policy (Slack → SMS → voice) is sufficient for a solo-founder setup.

## Design decisions (summary of brainstorming)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | **Student PII in error reports** | Anonymize at capture time via `before_send` scrubber + `send_default_pii=False` | Cheapest FERPA-clean approach; gives real debugging signal without third-party PII exposure |
| 2 | **Alert destinations / escalation** | BetterStack Team tier ($10/mo) — Slack + SMS + voice escalation | Single integration target for both Sentry and uptime; status page included; SMS/voice without a PagerDuty subscription |
| 3 | **Alert fidelity (when to page)** | Sustained-failure pages + business-hours degradation | Avoids fatigue; details in the Alert Routing Rules table below |
| 4 | **Critical-path tagging** | Grading + student-facing write paths (5 functions) | Smallest defensible tag set — every tagged path is a direct student-harm risk if it fails |
| 5 | **Public status page** | Yes, at `status.graider.live` | Enterprise sales asset for district vendor review; BetterStack backdates uptime so we start fresh |
| 6 | **Minor defaults** | Sentry Developer (free), prod-only env, release = git short SHA, traces off, 1-min probe interval, multi-region probes, SSL + domain expiry monitors on | All low-cost, all high-leverage |

---

## Architecture

Two independent sub-projects shipped together in one plan/PR but deployable and reversible separately. They share alert routing (Slack channel + BetterStack on-call policy) but neither depends on the other at runtime.

```
┌────────────────────────────────────────────┐
│              Graider Backend               │
│  ┌──────────────────┐  ┌─────────────────┐ │
│  │  Flask routes +  │  │   /healthz      │ │
│  │  grading worker  │  │   (existing)    │ │
│  └────────┬─────────┘  └────────┬────────┘ │
└───────────┼─────────────────────┼──────────┘
            │                     │
   (unhandled            (probed every 60s)
    exceptions +                  │
    @critical_path)               │
            ↓                     ↓
      ┌─────────┐           ┌────────────┐
      │ Sentry  │           │ BetterStack│
      │  Cloud  │           │   Uptime   │
      │  (free) │           │  (Team)    │
      └────┬────┘           └──────┬─────┘
           │                       │
           └──────┬────────────────┘
                  ↓
      ┌────────────────────┐
      │  Alert routing     │
      │  (BetterStack +    │
      │   Slack webhook)   │
      └──────┬─────┬───────┘
             │     │
             ↓     ↓
           Slack  SMS/voice
          (9-6pm)  (after-hours,
                   critical only)
```

---

## Sub-project A: Sentry error tracking

### File structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/observability/__init__.py` | Create | Re-export `init_sentry`, `critical_path` |
| `backend/observability/sentry.py` | Create | `init_sentry()`, `before_send()` scrubber, `@critical_path` decorator |
| `backend/app.py` | Modify | Call `init_sentry()` immediately after `app = Flask(__name__)`, before route registration. Also add the `SENTRY_TEST_ROUTE_ENABLED`-gated `/_debug/sentry-boom` route (see Testing section) and the `FORCE_HEALTHZ_FAIL` short-circuit at the top of the existing `/healthz` handler. |
| `backend/services/portal_grading.py` | Modify | Decorate `run_portal_grading_thread` with `@critical_path` |
| `backend/routes/student_account_routes.py` | Modify | Decorate `submit_student_work` and `save_submission_draft` |
| `backend/routes/student_portal_routes.py` | Modify | Decorate `publish_assessment` and join-code `submit_assessment` |
| `requirements.txt` | Modify | Add `sentry-sdk[flask]>=2.0` |
| `tests/test_sentry_scrub.py` | Create | ~10 unit tests pinning `before_send` behavior |
| `tests/test_critical_path.py` | Create | ~3 unit tests pinning decorator behavior |
| `docs/observability.md` | Create | Runbook, alert rules, rollback, cleanup, drill procedure |

### `init_sentry()`

Reads two env vars: `SENTRY_DSN` (required to enable) and `RAILWAY_GIT_COMMIT_SHA` (optional — used as release tag). Config:

- `dsn = os.getenv("SENTRY_DSN")` — **if unset, `init_sentry()` is a hard no-op.** No client is initialized. `sentry_sdk.Hub.current.client` remains `None`. This is the local-dev / CI / test behavior.
- `environment = "production"` — hardcoded. If/when staging exists, the solution is a second DSN, not an env var override.
- `release = os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown")[:7]` — short SHA.
- `traces_sample_rate = 0.0` — APM off, stays off until a separate decision.
- `send_default_pii = False` — belt + suspenders; prevents Sentry SDK from auto-attaching user data even if our `before_send` has a bug.
- `integrations = [FlaskIntegration(transaction_style="url")]` — standard Flask middleware.
- `before_send = before_send` — our PII scrub (defined below).
- `ignore_errors = [werkzeug.exceptions.BadRequest, werkzeug.exceptions.Unauthorized, werkzeug.exceptions.Forbidden, werkzeug.exceptions.NotFound, werkzeug.exceptions.MethodNotAllowed]` — defensive belt-and-suspenders. In practice, Flask's built-in error handling converts most `werkzeug.exceptions.HTTPException` subclasses to responses before Sentry's middleware sees them, so this config is a backstop for the rare case where code explicitly raises a 4xx from inside a try/except. The primary 4xx filter is the `before_send` drop below.

### `before_send(event, hint)` scrubber

Four responsibilities, in order. Each has at least one unit test pinning its behavior.

**1. Drop 4xx entirely.** Belt + suspenders with `ignore_errors` config — if an exception slips through the SDK's filter, return `None` to drop the event.

**2. Strip request-derived PII.** If the event has a `request` dict (Flask request integration attaches one; background grading thread events do NOT — handle both cases):
- Remove `request["data"]`, `request["json"]`, `request["form"]`, `request["cookies"]`
- Redact `request["headers"]["Authorization"]` → `"[Filtered]"`
- Redact `request["headers"]["Cookie"]` → `"[Filtered]"`
- Strip all query params whose name contains `token`, `key`, `secret`, `password`

**3. Scrub frame locals.** Walk every frame in every exception in `event["exception"]["values"]`, and in the frame's `vars` dict, remove keys matching any of:
```
student_name, student_email, answers, draft_answers,
student_id_number, submission_row, results, feedback,
first_name, last_name, row, s, sdata, assessment,
assessment_content, student_row, assessment_data
```

Replace each removed key with the string `"[PII-scrubbed]"` so reviewers know the scrubber ran.

**4. Set hashed user identifier (context-safe).** Use `flask.has_request_context()` to gate every access to `flask.g`. Touching `g.user_id` from outside a Flask request (e.g., the background grading thread, import-time errors, the Sentry SDK's own worker thread flushing events) raises `RuntimeError: Working outside of application context` — which would crash the scrubber during the very events we most want to capture.

```python
from flask import has_request_context, g

def _resolve_user_id():
    if not has_request_context():
        return "anonymous"
    try:
        uid = getattr(g, "user_id", None)
    except RuntimeError:
        # Defensive: some Flask context edge cases raise even after has_request_context() check
        return "anonymous"
    if not uid:
        return "anonymous"
    return hashlib.sha256(str(uid).encode()).hexdigest()[:12]
```

Then in `before_send`:
- Set `event["user"]["id"] = _resolve_user_id()`
- Remove `event["user"]["email"]`, `event["user"]["username"]`, `event["user"]["ip_address"]`

**Do NOT drop the event when the user is anonymous** — critical path failures in the grading thread are exactly the events that need to reach Sentry. Anonymous is a valid user identifier for grouping purposes.

### `@critical_path` decorator

Wraps a callable so that any unhandled exception escaping the function carries a Sentry scope tag `severity=critical`. Shape:

```python
def critical_path(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("severity", "critical")
            return fn(*args, **kwargs)
    return wrapper
```

- **Applied only to outermost entrypoints**, never to inner helpers called from within already-decorated functions. Exact list (5 functions):
  1. `run_portal_grading_thread` (`backend/services/portal_grading.py`) — grading worker entrypoint
  2. `submit_student_work` (`backend/routes/student_account_routes.py`)
  3. `save_submission_draft` (`backend/routes/student_account_routes.py`)
  4. `publish_assessment` (`backend/routes/student_portal_routes.py`)
  5. `submit_assessment` join-code path (`backend/routes/student_portal_routes.py`)

- **No-op when Sentry is uninitialized.** `sentry_sdk.push_scope()` is safe to call when no client is configured — it returns a dummy context manager. Local dev / CI / tests see the decorator as transparent.

### Tests

**`tests/test_sentry_scrub.py` — 11 tests pinning `before_send` contract:**

| # | Test | Asserts |
|---|---|---|
| 1 | `test_4xx_dropped` | BadRequest exception → `before_send` returns `None` |
| 2 | `test_request_data_stripped` | Event with `request.data = "sensitive"` → data is removed |
| 3 | `test_authorization_header_redacted` | `request.headers.Authorization` → `"[Filtered]"` |
| 4 | `test_cookies_removed` | `request.cookies` → absent from event |
| 5 | `test_query_token_stripped` | `?api_key=xxx` → removed |
| 6 | `test_frame_locals_scrubbed` | `student_name`, `answers`, etc. replaced with `"[PII-scrubbed]"` |
| 7 | `test_frame_locals_non_pii_preserved` | `attempt_number`, `content_id`, etc. preserved |
| 8 | `test_missing_request_context_ok` | Event with `hint["request"] = None` → scrub completes, event returned |
| 9 | `test_teacher_id_hashed_when_present` | In Flask request context with `g.user_id = "abc"`, event `user.id` becomes `sha256("abc")[:12]` |
| 10 | `test_anonymous_user_when_gid_missing` | In Flask request context with no `g.user_id` → `user.id = "anonymous"`, event NOT dropped |
| 11 | `test_scrub_outside_request_context_does_not_crash` | Invoke `before_send` from a thread with no Flask context active → no `RuntimeError`, event returned with `user.id = "anonymous"`. Directly pins the background-grading-thread case. |

**`tests/test_critical_path.py` — 3 tests pinning decorator contract:**

| # | Test | Asserts |
|---|---|---|
| 1 | `test_decorator_sets_severity_tag` | Wrapped fn raising → Sentry event carries `severity=critical` tag |
| 2 | `test_decorator_is_noop_when_uninitialized` | With no DSN, decorated fn runs normally and raises normally; no Sentry client access |
| 3 | `test_decorator_preserves_return_value` | Wrapped fn that doesn't raise returns its value unchanged |

---

## Sub-project B: BetterStack uptime + status page

**No code changes.** BetterStack is configured entirely through their web UI and one DNS record in Vercel. What gets created:

### Monitors

| Monitor | URL / target | Interval | Failure condition | Alert |
|---|---|---|---|---|
| **`/healthz` HTTPS** | `https://app.graider.live/healthz` | 60s, multi-region | 2 consecutive non-200 responses OR JSON body missing `"supabase":"ok"` | On-call policy (Slack + SMS/voice after-hours) |
| **SSL cert expiry** | `app.graider.live` | Daily | Cert < 30 days to expiry | Email digest only |
| **Domain expiry** | `graider.live` | Daily | Domain < 30 days to expiry | Email digest only |

### Status page

- **Subdomain:** `status.graider.live`
- **Visibility:** Public (no password)
- **Displayed monitors:** `/healthz` only (SSL and domain expiry stay internal)
- **DNS prerequisite:** add CNAME `status.graider.live → status.betteruptime.com` in the Vercel DNS dashboard for `graider.live` (the Vercel project, not the Railway project). The status page is a Vercel-hosted DNS record even though the app itself is on Railway.

### Slack integration

- Create a new `#alerts` channel in the existing Slack workspace (user must own one or create one)
- Generate a webhook URL via Slack's "Incoming Webhooks" app → paste into BetterStack's Slack integration config
- Verify a test message fires

### On-call policy: "Graider Solo"

- **Responder:** user (sole contact)
- **Escalation chain:** Slack immediately → SMS after 5 minutes if unacknowledged → voice call after 10 minutes if still unacknowledged
- **Active schedule:** outside 9am-6pm America/New_York, Monday-Friday. During business hours, only the Slack step fires.
- **Holiday / vacation override:** BetterStack supports pausing the policy or re-routing to a different contact via its "Schedule overrides" feature. Runbook step: before any multi-day absence, create an override that either suspends SMS/voice or redirects to a backup contact (e.g., a trusted technical friend who has agreed to be a short-term backup). Default state when no override exists is "solo policy active."
- **Who updates the schedule:** user. Runbook lists this explicitly.

---

## Alert routing rules (complete, canonical)

This is the one table that must be right. Every row maps to exactly one Sentry issue-alert or one BetterStack monitor config.

| # | Source | Condition | Action | Channel | Severity |
|---|---|---|---|---|---|
| 1 | BetterStack | `/healthz` returns non-200 for **2 consecutive probes** (2 min) | Incident created + alert | **Slack** during 9am-6pm ET; **Slack → SMS after 5min → voice after 10min** outside business hours | Critical |
| 2 | BetterStack | SSL cert < 30 days to expiry | Email digest | Email only | Info |
| 3 | BetterStack | Domain < 30 days to expiry | Email digest | Email only | Info |
| 4 | Sentry | New issue type appears (first seen ever) | Issue alert | Slack only, regardless of hour | Info |
| 5 | Sentry | Issue tagged `severity=critical` fires **≥3 events within 5 minutes** | Issue alert | **Slack + SMS + voice** via BetterStack on-call integration | Critical |
| 6 | Sentry | Any issue (tagged or not) fires **≥25 events within 10 minutes** affecting **≥5 distinct users** | Issue alert | Slack only during business hours, Slack + SMS after-hours | High |
| 7 | Sentry | 4xx errors (`BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`, `MethodNotAllowed`) | **Dropped in `before_send` + SDK `ignore_errors`** — never sent | n/a | n/a |
| 8 | Sentry | Any event from `environment != production` | **Dropped** — local dev is silent | n/a | n/a |

### Rule 5 & 6 user-grouping semantics

Sentry groups events by `user.id`, which our `before_send` scrubber sets to either:
- `sha256(g.user_id)[:12]` — 12-hex-char hash of the teacher ID, when a teacher context is present
- `"anonymous"` — literal string, when no teacher context is present (unauthenticated routes, background grading thread, import-time errors)

**Implication for Rule 6's "≥5 distinct users" threshold:**
- Events with teacher context correctly count as distinct users (one bucket per unique hash).
- Events WITHOUT teacher context all collapse into the single `"anonymous"` bucket. That's deliberate — anonymous events are usually from bots, uptime probes, or unauthenticated error paths, and we don't want those counting toward user-impact thresholds. **If you see Rule 6 never firing for a bug that only hits anonymous routes**, manually add that route's handlers to the critical-path decorator list so they fall under Rule 5 instead.

---

## Testing plan

### Sub-project A: Sentry — unit + integration

- **Unit tests:** run in CI as part of `pytest tests/`. Both test files (`test_sentry_scrub.py` and `test_critical_path.py`) use a fake Sentry hub — no network calls, no DSN required. Tests pass in any environment.
- **Integration test on production:** after merging, the debug route is gated by a dedicated feature flag — **NOT** Flask's `DEBUG` / `FLASK_DEBUG` env var. Using Flask's debug flag in production enables the Werkzeug interactive debugger, the auto-reloader, and detailed exception pages — all of which are production security holes. We need a flag that only affects the single debug route.

  **Guard implementation** in `backend/app.py`:
  ```python
  if os.getenv("SENTRY_TEST_ROUTE_ENABLED") == "1":
      @app.route("/_debug/sentry-boom")
      def _debug_sentry_boom():
          from flask import request
          severity = request.args.get("severity", "normal")
          if severity == "critical":
              @critical_path
              def _raise():
                  raise RuntimeError("sentry critical smoke test")
              _raise()
          else:
              raise RuntimeError("sentry normal smoke test")
  ```

  When `SENTRY_TEST_ROUTE_ENABLED` is unset (the default for production), the route is never registered — hits return 404.

  **Production verification procedure:**
  1. Set `SENTRY_TEST_ROUTE_ENABLED=1` in Railway env vars. Do NOT set `FLASK_DEBUG`, `DEBUG`, or `app.debug` — those enable Werkzeug's debugger and are a security risk in production.
  2. Wait for Railway auto-deploy (~60 seconds).
  3. Hit `https://app.graider.live/_debug/sentry-boom?severity=normal` and `?severity=critical` once each.
  4. In Sentry dashboard, verify:
     - Both events arrive within 60 seconds
     - Only `?severity=critical` has the `severity=critical` tag
     - Neither event contains `request.data`, `Authorization` header, or scrubbed local variable names (check a frame's `vars` dict for the `[PII-scrubbed]` sentinel)
     - `user.id` is a 12-char hex string (authenticated caller) or `"anonymous"` (unauth probe)
  5. Unset `SENTRY_TEST_ROUTE_ENABLED` in Railway. Wait for auto-deploy. Confirm the debug route returns 404 again.
- **Post-rollout cleanup (explicit runbook step):** delete the `/_debug/sentry-boom` route code (the `if os.getenv(...)` block) in a follow-up PR titled `chore: remove post-rollout sentry debug route`. This is a **required cleanup step**, not an optional one — leaving dormant debug code behind a flag invites accidents. The runbook lists it with a checklist and a target date (within 7 days of sub-project A merging). The env-var gate means the route is 404 without the flag even if the code is still present, so the cleanup PR is about code hygiene, not security.

### Sub-project B: BetterStack — live verification

1. Monitors green in dashboard within 5 minutes of creation.
2. **Alert drill (customer-safe via feature flag).** The drill must NOT corrupt `SUPABASE_URL` or otherwise break live database calls — that would cause a real outage for every student and teacher using the app during the drill window. Instead, the `/healthz` route is taught to short-circuit to a 503 when a dedicated drill env var is set. Student-facing API routes continue to work normally because they call `get_supabase()` directly, not `/healthz`.

   **Additional code change to `backend/app.py`'s `/healthz` route** (small addition, Sub-project A scope):

   ```python
   @app.route('/healthz')
   def healthz():
       # Alert-drill short-circuit — exercises the full alert pipeline without
       # touching Supabase, so student-facing traffic is unaffected during the drill.
       if os.getenv('FORCE_HEALTHZ_FAIL') == '1':
           return jsonify({"app": "ok", "supabase": "drill_forced_failure"}), 503

       status = {"app": "ok"}
       # ... existing Supabase probe ...
   ```

   **Drill procedure (zero customer impact):**
   1. Set `FORCE_HEALTHZ_FAIL=1` in Railway env vars. Wait for auto-deploy (~60 seconds).
   2. Within 3 minutes, BetterStack should observe 2 consecutive 503 responses and fire a Slack alert.
   3. Status page should show the monitor as "down."
   4. Student and teacher API calls continue working normally — they do not route through `/healthz`.
   5. Unset `FORCE_HEALTHZ_FAIL`. Wait for auto-deploy.
   6. Verify the "resolved" notification fires and the monitor returns to green.

3. **After-hours SMS drill:** run step 2 outside 9am-6pm ET. Confirm SMS arrives within 5 minutes of the initial Slack alert, voice call arrives within 10 minutes if unacknowledged.
4. **Status page DNS verification:** `dig status.graider.live` returns a BetterStack CNAME; `curl -I https://status.graider.live` returns 200 with the BetterStack-branded status page HTML.

### Quarterly drill

`docs/observability.md` includes a "Quarterly alert drill" section that re-runs steps 2 and 3 above on a calendar cadence (Jan / Apr / Jul / Oct, first Monday). The drill is safe to run during business hours because it only affects the external monitor — student and teacher traffic is unaffected. Catches silent regressions — e.g., someone accidentally disabled a monitor, Slack webhook expired, phone number changed.

**Why not corrupt `SUPABASE_URL` instead?** The earlier draft of this spec suggested corrupting `SUPABASE_URL` to force the `/healthz` probe to fail. That would cause a real Supabase outage for every live request during the drill window (3-15 minutes), affecting any student mid-assessment or teacher mid-grade. The `FORCE_HEALTHZ_FAIL` flag gives the same alert signal with zero customer impact, so there is no reason to ever corrupt Supabase credentials for drill purposes.

---

## Rollout order and rollback

**Ship B before A.** BetterStack is pure web-UI configuration and a DNS record — zero code, zero Railway deploy, zero rollback risk.

1. **Day 1 — Sub-project B (~30 min):**
   - Create BetterStack account, select Team tier ($10/mo)
   - Create the three monitors
   - Create the on-call policy "Graider Solo" with business-hours schedule
   - Set up Slack `#alerts` channel and webhook
   - Add CNAME `status.graider.live → status.betteruptime.com` in Vercel DNS
   - Verify green dashboard + status page renders
2. **Day 1-2 — Sub-project A (~4 hours code + review):**
   - Branch `feat/observability-sentry`
   - Implement `backend/observability/sentry.py` + tests
   - Apply the 5 `@critical_path` decorators
   - Call `init_sentry()` in `backend/app.py`
   - Add `sentry-sdk[flask]` to `requirements.txt`
   - Write `docs/observability.md`
   - Open PR; follow subagent-driven workflow (spec + code-quality reviews)
   - Wait for CI green; auto-merge
3. **Day 2 — Production verification:**
   - Railway auto-deploys on merge
   - Set `SENTRY_TEST_ROUTE_ENABLED=1` in Railway env vars temporarily
   - Hit `/_debug/sentry-boom` twice (critical and normal)
   - Verify both events in Sentry with correct tags and scrubbed payloads
   - **Unset `SENTRY_TEST_ROUTE_ENABLED`** (or set it back to `0`) in Railway env vars — do NOT leave the flag on
   - Open cleanup PR to delete the debug route code
4. **Day 3 — Alert drill:**
   - Set `FORCE_HEALTHZ_FAIL=1` in Railway env vars to exercise the `/healthz` short-circuit (student/teacher traffic unaffected — they call Supabase directly, not `/healthz`)
   - Confirm the BetterStack escalation chain (Slack → SMS → voice) fires correctly
   - **Unset `FORCE_HEALTHZ_FAIL`** (or set it back to `0`) and confirm the "recovered" notification fires

### Rollback

- **Sub-project A (Sentry):** revert the merge PR. Zero residual state in the codebase. Sentry Cloud retains historical events but takes no further action. Removing the `SENTRY_DSN` env var from Railway is a second, softer rollback that disables the client without reverting code.
- **Sub-project B (BetterStack):** disable the three monitors in the BetterStack UI (one click each), delete the `status.graider.live` CNAME in Vercel DNS. Cancel the Team-tier subscription if you want to stop being billed. No code touched.
- **DNS ownership note:** `graider.live` DNS is managed by **Vercel**, not Railway. The status page CNAME must be added in the Vercel dashboard under the `graider.live` project. The `app.graider.live` record that points at Railway is a separate existing CNAME and should not be touched.

---

## `docs/observability.md` — runbook outline

The runbook lives at `docs/observability.md` and is the single source of truth for on-call behavior. Sections:

1. **What's monitored** — the alert routing table above, verbatim
2. **Alert taxonomy** — what each alert means, expected response time, first 3 debugging steps
3. **Critical-path tag convention** — the 5 currently-decorated functions, how to add a new one, when NOT to add one
4. **Feature flags reference** — all four env vars, what they do, safe vs unsafe values, who's allowed to flip them:
   - `SENTRY_DSN` — enables Sentry. Normally set. Unset to disable Sentry entirely.
   - `RAILWAY_GIT_COMMIT_SHA` — auto-set by Railway. Don't touch manually.
   - `SENTRY_TEST_ROUTE_ENABLED` — **default unset.** Temporarily set to `1` during production Sentry verification (step 3 of rollout). Always unset immediately after verification completes. **Do NOT confuse with `FLASK_DEBUG` / `DEBUG`** — those enable Werkzeug's interactive debugger and are production security holes. Never set them.
   - `FORCE_HEALTHZ_FAIL` — **default unset.** Temporarily set to `1` during alert drills. Exercises the BetterStack → Slack/SMS/voice pipeline by making `/healthz` return 503 without touching Supabase. Always unset immediately after the drill completes. Student and teacher API traffic is unaffected while it's set.
5. **Post-rollout cleanup checklist** — delete the `/_debug/sentry-boom` route code entirely within 7 days of sub-project A merging (explicit deadline). The `FORCE_HEALTHZ_FAIL` short-circuit stays in place permanently — it's the drill mechanism.
6. **Holiday / vacation override procedure** — how to use BetterStack's "Schedule overrides" feature, who to designate as a backup if needed
7. **Quarterly drill procedure** — re-run the alert drills from the testing section via `FORCE_HEALTHZ_FAIL`. Safe to run during business hours.
8. **Rollback procedure** — per above
9. **Known noise sources** — 4xx drops, anonymous user bucketing (Rule 6's "distinct users" check collapses all unauth events into a single bucket), non-prod event dropping — so future operators don't waste time diagnosing expected behavior
10. **Escalation contacts** — user's phone number, Slack handle, email, and any future backup contact

---

## Open questions / deferred items

- **Whether to add a "warning" severity below critical** — currently we only have tagged and untagged events. If it turns out Rule 6 (≥25 events / ≥5 users) is too noisy OR misses things, we may want a middle tier. Not adding one now; revisit after one month of operation.
- **Whether to expose the `/_debug/sentry-boom` route via a dedicated test-only mechanism** (e.g., a pytest fixture + internal Flask test client) instead of a real route that has to be cleaned up. Deferred — the debug-route-with-cleanup approach is simpler for v1.
- **Staging environment.** Not adding one now. If/when added, the path is a second Sentry DSN with `environment="staging"`, NOT reuse of the production DSN.

---

## Summary

| Metric | Value |
|---|---|
| **Sub-projects** | 2 (Sentry error tracking + BetterStack uptime/status page) |
| **New files** | 5 code files, 2 test files, 1 doc file (plus `requirements.txt` change) |
| **Modified files** | 4 backend files (`app.py`, `portal_grading.py`, 2 route files) |
| **New env vars (all default-off)** | `SENTRY_DSN` (enables Sentry), `RAILWAY_GIT_COMMIT_SHA` (auto-set by Railway), `SENTRY_TEST_ROUTE_ENABLED` (gates `/_debug/sentry-boom`), `FORCE_HEALTHZ_FAIL` (alert-drill short-circuit) |
| **Critical-path decorators** | 5 functions total |
| **Unit tests added** | 14 (11 scrub tests + 3 decorator tests) |
| **Monthly cost** | $10 (BetterStack Team) |
| **Rollout time** | ~1 day for B, ~1 day for A + reviews, ~1 day for verification = 3 days |
| **Rollback complexity** | Low — each sub-project reversible independently |
