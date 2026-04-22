# Observability Runbook

Graider's production observability stack. This is the on-call document —
when an alert fires, start here.

**Stack (as-shipped, free tier):**
- **BetterStack Error Tracking** (free tier, 100k exceptions/mo, EU data region) — Python backend error capture via the Sentry SDK. Our code uses `sentry-sdk[flask]` with a DSN pointing at BetterStack's ingest endpoint.
- **BetterStack Uptime** (free tier, 10 monitors) — `/healthz` probe every 3 minutes from multi-region
- **BetterStack Status Page** (free tier, 1 page included) — public page at https://status.graider.live
- **BetterStack Mobile App** with iOS Critical Alerts — the pager substitute for after-hours alerts
- **Slack** `#alerts` channel — real-time alert feed, routed via BetterStack's Slack integration

**Design spec (historical):** `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md` — the original design assumed paid Team tier with Sentry Cloud + SMS/voice; the as-shipped version is free tier with BetterStack error tracking + iOS Critical Alerts. This runbook reflects the as-shipped state.

**Monthly cost:** $0

**Data residency note:** BetterStack stores error tracking events in the EU (free-tier constraint). Our `before_send` PII scrubber strips all student data, teacher names, request bodies, and sensitive frame locals BEFORE events leave the Railway backend. What actually reaches BetterStack EU is pure metadata — stack traces, route names, HTTP status codes, hashed teacher IDs. No FERPA-sensitive content ever leaves US-hosted Graider infrastructure. Defensible answer for district vendor questionnaires: *"error telemetry metadata is processed in the EU by our monitoring provider. Student data and records are stored exclusively in US-hosted Supabase. PII is scrubbed at capture time via a `before_send` hook, source at `backend/observability/sentry.py`."*

---

## Alert routing rules

| # | Source | Condition | Action | Channel | Severity |
|---|---|---|---|---|---|
| 1 | BetterStack Uptime | `/healthz` returns non-200 for **2 consecutive probes** (~6 min on 3-min interval) OR response body missing `"supabase":"ok"` | Incident + alert | **Slack `#alerts`** + **iOS Critical Alert** via BetterStack mobile app (bypasses DND) + **Email** | Critical |
| 2 | BetterStack Error Tracking | New error type first seen | Issue alert | **Slack `#alerts`** + **iOS push** (not Critical) | Info |
| 3 | BetterStack Error Tracking | Issue tagged `severity=critical` fires **≥3 events within 5 minutes** | Issue alert | **Slack `#alerts`** + **iOS Critical Alert** (bypasses DND) + **Email** | Critical |
| 4 | BetterStack Error Tracking | Any issue fires **≥25 events within 10 minutes** affecting **≥5 distinct users** | Issue alert | **Slack `#alerts`** + **iOS push** (not Critical) | High |
| 5 | BetterStack Error Tracking | 4xx errors (`BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`, `MethodNotAllowed`) | **Dropped in `before_send`** — never sent | n/a | n/a |
| 6 | BetterStack Error Tracking | Any event from `environment != production` | **Dropped** — local dev is silent | n/a | n/a |

**Business hours note:** Unlike the original paid-tier design, the free tier doesn't support time-based escalation gating. Critical Alerts fire on the iPhone via the BetterStack mobile app regardless of time of day. You can silence them manually via iOS Focus modes during work hours if they get noisy, but since the tuning (Rules 1 and 3 require sustained failures) is strict, false pages during the day should be rare.

**No SMS or voice escalation** — the BetterStack free tier does not include these. Critical Alerts via the mobile app are the replacement. This was a deliberate trade-off to stay on $0/mo; revisit Team tier ($10/mo) if SMS/voice becomes necessary (e.g., when signing a district contract with a 24/7 SLA).

### How `user.id` grouping works in Rules 3 and 4

Our `before_send` scrubber sets `user.id` to either:
- A 12-char sha256 hash of `g.user_id` (when inside a Flask request with a teacher attached)
- The literal string `"anonymous"` otherwise

Rule 4's "≥5 distinct users" threshold counts each unique hash as one user. **Anonymous events all collapse into a single bucket**, so Rule 4 will never fire for bugs that only affect unauthenticated paths (public landing, health probes, unauth API calls). If a specific unauthenticated code path needs direct paging, add it to the critical-path decorator list so it falls under Rule 3 instead.

---

## Critical-path tag convention

The `@critical_path` decorator from `backend/observability` tags any escaping exception with `severity=critical`, which is what Rule 3 above pages on. Currently decorated functions (5):

1. `run_portal_grading_thread` in `backend/services/portal_grading.py` — grading worker entrypoint
2. `submit_student_work` in `backend/routes/student_account_routes.py`
3. `save_submission_draft` in `backend/routes/student_account_routes.py`
4. `publish_assessment` in `backend/routes/student_portal_routes.py`
5. `submit_assessment` (join-code path) in `backend/routes/student_portal_routes.py`

**When to add a new critical path:**
- The function is an **outermost entrypoint** (Flask route handler or background worker entrypoint), not an inner helper
- Failure in the function directly harms students (lost submissions, wrong grades) or loses teacher work (lost published content)
- Recovery requires a human — an auto-retry wouldn't fix it

**When NOT to add a new critical path:**
- Inner helpers called from within an already-decorated function (they inherit the tag via the scope)
- Read-only routes (GET endpoints that just list data)
- Administrative routes that only affect the teacher, not students
- Anything where silent failure is acceptable until the next deploy

**How to add a new critical path:**
1. Import: `from backend.observability import critical_path`
2. Place `@critical_path` BELOW the Flask route decorator and any auth decorators, directly above the `def` line. This order matters: Flask registers the wrapped function, and auth checks run before the `critical_path` scope is entered (so auth-failure 401s don't fire pages).
3. Update this list.

---

## Feature flags reference

All four env vars are default-off or normally-set. Flip the two "debug" flags only when necessary and unset immediately after.

| Env var | Default | What it does | When to set it |
|---|---|---|---|
| `SENTRY_DSN` | **Normally set in Railway production** to the BetterStack Error Tracking DSN (format: `https://[token]@in.logs.betterstack.com/[project-id]` or similar). When unset, `init_sentry()` is a hard no-op — no client, no events sent. | Enables error tracking. Always set in Railway production. Unset to disable error tracking entirely. Despite the variable name, it points at BetterStack's Sentry-compatible ingest endpoint, NOT sentry.io. |
| `RAILWAY_GIT_COMMIT_SHA` | Auto-set by Railway | Used as the error-tracking release tag (short SHA form). Don't touch manually. | Never touch manually. |
| `SENTRY_TEST_ROUTE_ENABLED` | **Unset** | When `1`, registers `/_debug/sentry-boom` at app startup. Unset, the route is 404. | Temporarily during post-deploy production verification (Task 12 step 3 of the observability v1 rollout). **Always unset immediately after.** **Do NOT confuse with `FLASK_DEBUG` / `DEBUG`** — those enable Werkzeug's interactive debugger and are a remote code execution vector. Never set them. |
| `FORCE_HEALTHZ_FAIL` | **Unset** | When `1`, `/healthz` returns 503 without touching Supabase. Used for alert drills. Student/teacher API traffic is unaffected because they call Supabase directly, not `/healthz`. | During alert drills. Always unset immediately after the drill completes. Safe to set during business hours — does not affect customer traffic. |

---

## Post-rollout cleanup checklist

The `/_debug/sentry-boom` route code block in `backend/app.py` is a temporary fixture for initial error-tracking verification. It must be deleted in a follow-up PR within **7 days** of the observability v1 PR merging.

**Owner:** user
**Target date:** (merge date + 7 days)
**Cleanup PR title:** `chore: remove post-rollout sentry debug route`

The `FORCE_HEALTHZ_FAIL` short-circuit stays in place permanently — it's the drill mechanism and has zero customer impact when the flag is unset.

---

## Holiday / vacation / time-off coverage

The free-tier pager is iOS Critical Alerts via the BetterStack mobile app. Since it fires regardless of time of day, "on-call handoff" is a matter of phone availability rather than schedule configuration. Three scenarios:

### Short absence (1-3 days, phone available)

No action needed. Critical Alerts continue to reach your phone. If you actually want to silence them briefly (a wedding, a funeral, a flight), use **iOS Focus modes** to temporarily disable BetterStack notifications:

1. iPhone Settings → Focus → Do Not Disturb → Apps → add BetterStack to the silenced list
2. Revert when you're back

**Note:** This defeats the whole point of Critical Alerts bypassing DND, so only do it when you truly cannot be reached. Critical Alerts are Apple-guaranteed to punch through standard DND — adding the app to a Focus silence list is a manual opt-out, not an accidental block.

### Medium absence (3-7 days, phone available but you want a backup)

1. BetterStack dashboard → Team → invite a trusted technical friend as a collaborator
2. Configure the BetterStack Slack integration to also @mention them in `#alerts` during the absence window
3. Ask them to install the BetterStack mobile app and enable Critical Alerts so the pager reaches two humans
4. Remove them when you're back

**Gotcha:** The free tier limits team members. Verify you're not hitting the cap before inviting.

### Long absence (>7 days) or phone unavailable

If you're going somewhere without reliable phone service (backpacking, overseas without roaming, etc.), there's no free-tier pager substitute. Two options:

1. **Accept monitoring blindness** for the window — let alerts land in Slack only, check when you're back
2. **Upgrade to Team tier ($10/mo) before leaving**, configure SMS or voice to a trusted person, downgrade when you return

**Who updates the mobile app / invites / plan changes:** user (sole contact). No one else has access to BetterStack.

---

## Quarterly alert drill

Re-verify the alert pipeline on a calendar cadence: **first Monday of Jan, Apr, Jul, Oct.** This catches silent regressions like a disabled monitor, an expired Slack webhook, or the BetterStack mobile app losing Critical Alerts permission after an iOS update.

### Drill procedure (safe during business hours)

1. **Announce the drill.** Post in `#alerts`: "Running quarterly alert drill — ignore incoming alerts for the next ~10 minutes."
2. **Set the flag.** In Railway env vars, set `FORCE_HEALTHZ_FAIL=1`. Wait for Railway to auto-deploy (~60 seconds).
3. **Verify detection.** Within 6 minutes (2 consecutive 3-min checks), BetterStack should observe the 503 responses and create an incident. A Slack alert should land in `#alerts` immediately.
4. **Verify the iOS Critical Alert fires.** Check your phone — you should see a BetterStack push notification that punches through silent mode and plays a sound even if your phone is muted. If it doesn't fire:
   - Check Settings → Notifications → BetterStack → Critical Alerts is ON
   - Check the BetterStack mobile app is signed in to the same account
   - Check the app is NOT in an iOS Focus silence list
5. **Verify status page.** Visit `https://status.graider.live` and confirm the `/healthz` monitor shows as "down."
6. **Acknowledge the incident** in BetterStack (either the mobile app or the web dashboard).
7. **Unset the flag.** Remove `FORCE_HEALTHZ_FAIL` from Railway env vars (or set to `0`). Wait for auto-deploy.
8. **Verify recovery.** BetterStack should fire a "resolved" notification in Slack within 6 minutes of the auto-deploy completing.
9. **Log the drill.** Post in `#alerts`: "Drill complete. Detection: X minutes. iOS Critical Alert: fired / did not fire. Recovery: Z minutes." Track any issues and fix them before the next quarterly drill.

**Customer impact during the drill: zero.** Student-facing and teacher-facing API routes call `get_supabase()` directly, which continues to work normally while `/healthz` is short-circuited.

---

## Rollback procedure

### Sub-project A (error tracking code) — code-level

1. **Soft rollback (fastest):** remove `SENTRY_DSN` from Railway env vars. Wait for Railway to auto-deploy (~60 seconds). `init_sentry()` becomes a no-op and no more events are sent. The code stays in place, decorators become transparent.
2. **Hard rollback:** revert the merge PR via `gh pr revert <PR#>`. Auto-deploy removes all observability code. Zero residual state in the codebase. BetterStack retains historical events but takes no further action.

### Sub-project B (BetterStack monitoring) — ops-level

1. **Disable monitors:** BetterStack UI → Monitors → disable the `/healthz` monitor. One click.
2. **Delete status page subdomain:** remove the CNAME `status.graider.live` from **Cloudflare DNS** dashboard.
3. **Delete the BetterStack application / error tracking project:** BetterStack UI → Error Tracking → your application → Settings → Delete. This invalidates the DSN.
4. **Cancel BetterStack account entirely (optional):** only necessary if you want to fully stop using the service. Keeping the free plan active costs nothing.

No code changes required to roll back Sub-project B — it's all configuration.

**DNS ownership note:** `graider.live` DNS is authoritative on **Cloudflare**, NOT Vercel. The `status.graider.live` CNAME was added in the Cloudflare dashboard via their one-click BetterStack integration. Vercel hosts the landing page content at `graider.live` but DNS is delegated to Cloudflare. Do not touch the `app.graider.live` CNAME that points at Railway — that's production API traffic.

---

## Known noise sources

Expected behavior that future operators should not waste time diagnosing:

- **4xx errors never reach BetterStack.** The `before_send` scrubber drops them before they leave the app. Matches both bare class names (`"BadRequest"`) and fully-qualified paths (`"werkzeug.exceptions.BadRequest"`). If a teacher reports "I got a 400 error," that information is in Railway logs, not error tracking.
- **Anonymous events all bucket as one user.** Rule 4's "≥5 distinct users" threshold will never fire for bugs that only affect unauthenticated paths (the scrubber sets `user.id = "anonymous"` for all such events, so they collapse to one bucket). Fix: move the affected handler onto the critical-path list so Rule 3 catches it instead.
- **Non-production events are dropped.** Local dev and CI runs never hit BetterStack because `init_sentry()` is a no-op when `SENTRY_DSN` is unset. If you're running locally and expect events to show up, they won't.
- **Frame locals named `assessment`, `row`, `s`, `sdata`, etc. are scrubbed.** The full list is in `backend/observability/sentry.py::_PII_LOCAL_NAMES`. If you're debugging an event and the locals look empty, they were scrubbed on purpose.
- **`init_sentry()` is idempotent.** The module-level `_initialized` flag prevents double-init when `backend.app` is re-imported (common in test teardown/setup). Transient init failures (malformed DSN caught at startup) do NOT set the flag, so a later call can retry after the env var is fixed.
- **`init_sentry()` catches only `BadDsn` / `ValueError`.** Other init errors (wrong kwargs, SDK regressions) intentionally surface loudly so they're caught in CI/staging before reaching production.
- **`transaction_style="endpoint"`** — events are grouped by Flask route function name, not URL path. This prevents cardinality explosion on routes like `/api/student/submission/<id>/draft`. The regression test `test_init_called_with_expected_kwargs` pins this — a future revert to `"url"` would fail the suite.

---

## Escalation contacts

**Primary on-call:** user (solo)
- Phone: (set in BetterStack notification preferences)
- Slack: (set in BetterStack notification preferences)
- Email: (set in BetterStack notification preferences)
- BetterStack mobile app: installed with iOS Critical Alerts permission granted

**Backup contact:** none currently. If a backup is arranged in the future, update the BetterStack team members list AND this section.

---

## Structured events (`emit()` helper)

For machine-parsed log events (e.g. traffic split, LLM call metrics),
use `backend.observability.events.emit()`:

```python
from backend.observability.events import emit

emit("llm.call.complete", model="gpt-4", duration_ms=423, tokens=150)
```

The event name and fields are serialized as JSON inside the outer log
line's `message` field — consumers parse `message` as JSON to extract
`event` and its fields. This is intentional: the existing `JsonFormatter`
at `backend/utils/logging_utils.py` serializes only a fixed set of outer
fields and drops `extra={...}` kwargs. The `emit()` helper routes around
that limitation without modifying the formatter.

For human-readable operational messages, continue using standard
`logger.info/warning/exception` calls.

**Note on logger names (Phase 5a PR C1):** `request.db_mode` events now
emit from logger `backend.observability.events` (previously
`backend.db_mode`). If you have BetterStack filters or searches keyed on
the old logger name, update them to `backend.observability.events` — or
better, key on `message.event == "request.db_mode"` since the event name
is the stable contract regardless of where it's emitted from.

---

## Follow-ups / known gaps

- **Frontend error tracking not yet implemented** — see memory: `project_frontend_error_tracking.md`. Observability v1 only captures Python backend errors. React rendering crashes, stuck spinners, and event handler exceptions are currently invisible. Estimated 4-6 hours of follow-up work.
- **Google OAuth consent screen shows raw Supabase URL** — see memory: `project_google_oauth_branding_fix.md`. Unrelated to observability but flagged during the rollout. 30-45 min follow-up.
- **SSL and domain expiry monitoring deferred** — BetterStack's paid feature, skipped for free tier. Railway auto-renews the SSL cert for `app.graider.live` via Let's Encrypt, and domain renewal is handled by registrar auto-renew. Risk is low.
