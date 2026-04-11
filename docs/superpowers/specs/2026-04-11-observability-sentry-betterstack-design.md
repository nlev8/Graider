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
| `backend/app.py` | Modify | Call `init_sentry()` immediately after `app = Flask(__name__)`, before route registration |
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

**4. Set hashed user identifier (optional).** If the event has a `user` dict and `g.user_id` (teacher ID) is available via `flask.g`:
- Replace `user.id` with `hashlib.sha256(str(g.user_id).encode()).hexdigest()[:12]`
- Remove `user.email`, `user.username`, `user.ip_address`

**If `g.user_id` is absent** (unauthenticated routes, background grading thread, import-time errors): set `user.id = "anonymous"`. **Do NOT drop the event** — critical path failures can happen in contexts where `g` is empty.

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

**`tests/test_sentry_scrub.py` — 10 tests pinning `before_send` contract:**

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
| 9 | `test_teacher_id_hashed_when_present` | With `g.user_id = "abc"`, event `user.id` becomes `sha256("abc")[:12]` |
| 10 | `test_anonymous_user_when_gid_missing` | No `g.user_id` → `user.id = "anonymous"`, event NOT dropped |

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
- **Integration test on production:** after merging, add a temporary `GET /_debug/sentry-boom` route (guarded by `DEBUG=1` env, which is NOT set in Railway production — so the route literally 404s unless the env is flipped). Flip `DEBUG=1`, hit the route with both `?severity=critical` and `?severity=normal`, verify:
  1. Both events arrive in Sentry within 60 seconds
  2. Only `?severity=critical` has the `severity=critical` tag
  3. Neither event contains `request.data`, `Authorization` header, or scrubbed local variable names
  4. `user.id` is a 12-char hex string (logged-in caller) or `"anonymous"` (unauth)
- **Post-rollout cleanup (explicit runbook step):** delete the `/_debug/sentry-boom` route in a follow-up PR titled `chore: remove post-rollout sentry debug route`. This is a **required cleanup step**, not an optional one. The runbook lists it with a checklist and a target date (within 7 days of sub-project A merging).

### Sub-project B: BetterStack — live verification

1. Monitors green in dashboard within 5 minutes of creation.
2. **Alert drill:** temporarily set `SUPABASE_URL` to an invalid value in Railway (`https://broken.supabase.co`). Within 3 minutes, `/healthz` should return non-200 twice in a row, BetterStack should fire a Slack alert, status page should show the monitor as "down." Revert the env var, verify recovery within 3 more minutes, confirm the "resolved" notification fires.
3. **After-hours SMS drill:** run the alert drill above outside 9am-6pm ET. Confirm SMS arrives within 5 minutes of the initial Slack alert.
4. **Status page DNS verification:** `dig status.graider.live` returns a BetterStack CNAME; `curl -I https://status.graider.live` returns 200 with the BetterStack-branded status page HTML.

### Quarterly drill

`docs/observability.md` includes a "Quarterly alert drill" section that re-runs steps 2 and 3 above on a calendar cadence (Jan / Apr / Jul / Oct, first Monday). Catches silent regressions — e.g., someone accidentally disabled a monitor, Slack webhook expired, phone number changed.

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
   - Flip `DEBUG=1` env var temporarily
   - Hit `/_debug/sentry-boom` twice (critical and normal)
   - Verify both events in Sentry with correct tags and scrubbed payloads
   - Flip `DEBUG=1` off again
   - Open cleanup PR to delete the debug route
4. **Day 3 — Alert drill:**
   - Break `/healthz` on purpose via `SUPABASE_URL` override
   - Confirm the BetterStack escalation chain (Slack → SMS → voice) fires correctly
   - Revert and confirm recovery

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
4. **Post-rollout cleanup checklist** — delete the `/_debug/sentry-boom` route within 7 days of sub-project A merging (explicit deadline)
5. **Holiday / vacation override procedure** — how to use BetterStack's "Schedule overrides" feature, who to designate as a backup if needed
6. **Quarterly drill procedure** — re-run the alert drills from the testing section
7. **Rollback procedure** — per above
8. **Known noise sources** — 4xx drops, anonymous user bucketing, non-prod event dropping — so future operators don't waste time diagnosing expected behavior
9. **Escalation contacts** — user's phone number, Slack handle, email, and any future backup contact

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
| **Critical-path decorators** | 5 functions total |
| **Unit tests added** | 13 (10 scrub tests + 3 decorator tests) |
| **Monthly cost** | $10 (BetterStack Team) |
| **Rollout time** | ~1 day for B, ~1 day for A + reviews, ~1 day for verification = 3 days |
| **Rollback complexity** | Low — each sub-project reversible independently |
