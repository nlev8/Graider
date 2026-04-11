# Observability Runbook

Graider's production observability stack. This is the on-call document —
when an alert fires, start here.

**Stack:**
- **Sentry Cloud** (Developer / free tier) — error tracking with PII scrubbing
- **BetterStack** (Team tier, $10/mo) — uptime monitoring + public status page + on-call escalation
- **Slack** `#alerts` channel — real-time alert feed
- **Public status page:** https://status.graider.live

**Design spec:** `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md`

---

## Alert routing rules

| # | Source | Condition | Action | Channel | Severity |
|---|---|---|---|---|---|
| 1 | BetterStack | `/healthz` returns non-200 for **2 consecutive probes** (2 min) | Incident + alert | **Slack** 9am-6pm ET; **Slack → SMS after 5min → voice after 10min** outside business hours | Critical |
| 2 | BetterStack | SSL cert < 30 days to expiry | Email digest | Email only | Info |
| 3 | BetterStack | Domain < 30 days to expiry | Email digest | Email only | Info |
| 4 | Sentry | New issue type first seen | Issue alert | Slack only, any hour | Info |
| 5 | Sentry | Issue tagged `severity=critical` fires **≥3 events within 5 minutes** | Issue alert | **Slack + SMS + voice** via BetterStack on-call | Critical |
| 6 | Sentry | Any issue fires **≥25 events within 10 minutes** affecting **≥5 distinct users** | Issue alert | Slack during business hours; Slack + SMS after-hours | High |
| 7 | Sentry | 4xx errors (`BadRequest`, `Unauthorized`, `Forbidden`, `NotFound`, `MethodNotAllowed`) | **Dropped in `before_send`** — never sent | n/a | n/a |
| 8 | Sentry | Any event from `environment != production` | **Dropped** — local dev is silent | n/a | n/a |

**Business hours:** 09:00-18:00 America/New_York, Monday-Friday.

**Rule 5/6 user-grouping note:** Sentry groups events by `user.id`, which our scrubber sets to either a 12-char sha256 hash of `g.user_id` (when available) or the literal string `"anonymous"`. Anonymous events all bucket as a single user, so Rule 6's "≥5 distinct users" threshold will not fire for bugs that only affect unauthenticated paths. If a specific unauthenticated path needs direct paging, add it to the critical-path decorator list so it falls under Rule 5 instead.

---

## Critical-path tag convention

The `@critical_path` decorator from `backend/observability` tags any escaping exception with `severity=critical`, which is what Rule 5 above pages on. Currently decorated functions (5):

1. `run_portal_grading_thread` in `backend/services/portal_grading.py`
2. `submit_student_work` in `backend/routes/student_account_routes.py`
3. `save_submission_draft` in `backend/routes/student_account_routes.py`
4. `publish_assessment` in `backend/routes/student_portal_routes.py`
5. `submit_assessment` (join-code path) in `backend/routes/student_portal_routes.py`

**When to add a new critical path:**
- The function is an **outermost entrypoint** (Flask route handler or background worker entrypoint), not an inner helper.
- Failure in the function directly harms students (lost submissions, wrong grades) or loses teacher work (lost published content).
- Recovery requires a human — an auto-retry wouldn't fix it.

**When NOT to add a new critical path:**
- Inner helpers called from within an already-decorated function (they inherit the tag).
- Read-only routes (GET endpoints that just list data).
- Administrative routes that only affect the teacher, not students.
- Anything where silent failure is acceptable until the next deploy.

**How to add a new critical path:**
1. Import: `from backend.observability import critical_path`
2. Place `@critical_path` BELOW the Flask route decorator and any auth decorators, directly above the `def` line. This order matters: Flask registers the wrapped function, and auth checks run before the critical_path scope is entered (so auth-failure 401s don't fire pages).
3. Update this list.

---

## Feature flags reference

All four env vars are default-off. Flip only when necessary, unset immediately after.

| Env var | Default | What it does | When to set it |
|---|---|---|---|
| `SENTRY_DSN` | Normally set in production | Enables Sentry. When unset, `init_sentry()` is a hard no-op — no client, no events sent. | Always set in Railway production. Unset to disable Sentry entirely. |
| `RAILWAY_GIT_COMMIT_SHA` | Auto-set by Railway | Used as the Sentry release tag (short form). Do not touch manually. | Never touch manually. |
| `SENTRY_TEST_ROUTE_ENABLED` | **Unset** | When `1`, registers `/_debug/sentry-boom` at app startup. Unset, the route is 404. | Temporarily during post-deploy production verification (step 3 of rollout). Always unset immediately after. **Do NOT confuse with `FLASK_DEBUG` / `DEBUG`** — those enable Werkzeug's interactive debugger and are a remote code execution vector. Never set them. |
| `FORCE_HEALTHZ_FAIL` | **Unset** | When `1`, `/healthz` returns 503 without touching Supabase. Used for alert drills. Student/teacher API traffic is unaffected because they call Supabase directly, not `/healthz`. | During alert drills. Always unset immediately after the drill completes. Safe to set during business hours — does not affect customer traffic. |

---

## Post-rollout cleanup checklist

The `/_debug/sentry-boom` route code block in `backend/app.py` is a temporary fixture for initial Sentry verification. It must be deleted in a follow-up PR within **7 days** of the observability v1 PR merging.

**Owner:** user
**Target date:** (merge date + 7 days)
**Cleanup PR title:** `chore: remove post-rollout sentry debug route`

The `FORCE_HEALTHZ_FAIL` short-circuit stays in place permanently — it's the drill mechanism and has zero customer impact when the flag is unset.

---

## Holiday / vacation override procedure

Before any multi-day absence, update the BetterStack on-call policy:

1. Log in to BetterStack → Policies → "Graider Solo"
2. Click "Schedule overrides"
3. Add an override for the absence window. Options:
   - **Suspend SMS/voice entirely** for the window (alerts still land in Slack, you check when you're back)
   - **Redirect to a backup contact** if you've arranged one (enter their phone + email)
4. Save. Overrides auto-revert at the end of the window.

**Who updates the schedule:** user (sole contact). No one else has access to BetterStack.

**If you forget to set an override and the pager fires during your absence:** the alert will attempt to call your phone. If unanswered, BetterStack logs the incident as "unacknowledged" but takes no further action. The incident persists in the BetterStack dashboard until you acknowledge it manually.

---

## Quarterly alert drill

Re-verify the alert pipeline on a calendar cadence: **first Monday of Jan, Apr, Jul, Oct.** This catches silent regressions like a disabled monitor, an expired Slack webhook, or a phone number change.

### Drill procedure (safe during business hours)

1. **Tell yourself you're starting a drill.** Post in `#alerts`: "Running quarterly alert drill — ignore incoming alerts for the next ~10 minutes." This prevents confusion if someone else is watching.
2. **Set the flag.** In Railway env vars, set `FORCE_HEALTHZ_FAIL=1`. Wait for Railway to auto-deploy (~60 seconds).
3. **Verify detection.** Within 3 minutes, BetterStack should observe 2 consecutive 503 responses from `/healthz` and create an incident. A Slack alert should land in `#alerts` immediately.
4. **Verify status page.** Visit `https://status.graider.live` and confirm the `/healthz` monitor shows as "down."
5. **(After-hours drill only) Verify SMS.** Wait 5 minutes after the Slack alert. If the drill is running outside business hours, SMS should arrive.
6. **(After-hours drill only) Verify voice.** Wait another 5 minutes (total 10 from the Slack alert). If unacknowledged, voice call should fire.
7. **Acknowledge the incident** in BetterStack.
8. **Unset the flag.** Remove `FORCE_HEALTHZ_FAIL` from Railway env vars (or set to `0`). Wait for auto-deploy.
9. **Verify recovery.** BetterStack should fire a "resolved" notification in Slack within 3 minutes of the auto-deploy completing.
10. **Log the drill.** Post in `#alerts`: "Drill complete. Detection: X minutes. Escalation: Y minutes. Recovery: Z minutes." Track any issues and fix them before the next quarterly drill.

**Customer impact during the drill: zero.** Student-facing and teacher-facing API routes call `get_supabase()` directly, which continues to work normally while `/healthz` is short-circuited.

---

## Rollback procedure

### Sub-project A (Sentry) — code-level

1. **Soft rollback (fastest):** remove `SENTRY_DSN` from Railway env vars. Wait for Railway to auto-deploy (~60 seconds). `init_sentry()` becomes a no-op and no more events are sent. The code stays in place.
2. **Hard rollback:** revert the merge PR via `gh pr revert <PR#>`. Auto-deploy removes all observability code. Zero residual state in the codebase. Sentry Cloud retains historical events but takes no further action.

### Sub-project B (BetterStack) — ops-level

1. **Disable monitors:** BetterStack UI → Monitors → disable each of the three monitors (`/healthz`, SSL cert, domain expiry). One click each.
2. **Delete status page subdomain:** remove the CNAME `status.graider.live` from Vercel DNS dashboard.
3. **Cancel subscription (optional):** BetterStack UI → Billing → cancel the Team tier plan to stop being billed.

No code changes are required to roll back Sub-project B — it's all configuration.

**DNS ownership note:** `graider.live` DNS is managed by **Vercel**, not Railway. The `status.graider.live` CNAME is added in the Vercel dashboard under the `graider.live` project. Do not touch the `app.graider.live` CNAME that points at Railway — that's a separate record and is production traffic.

---

## Known noise sources

Expected behavior that future operators should not waste time diagnosing:

- **4xx errors never reach Sentry.** The `before_send` scrubber drops them before they leave the app. If a teacher reports "I got a 400 error," that information is in Railway logs, not Sentry. Note: the scrubber matches both bare class names (`"BadRequest"`) and fully-qualified paths (`"werkzeug.exceptions.BadRequest"`).
- **Anonymous events all bucket as one user.** Rule 6's "≥5 distinct users" threshold will never fire for bugs that only affect unauthenticated paths (the scrubber sets `user.id = "anonymous"` for all such events, so they collapse to one bucket). Fix: move the affected handler onto the critical-path list so Rule 5 catches it instead.
- **Non-production events are dropped.** Local dev and CI runs never hit Sentry because `init_sentry()` is a no-op when `SENTRY_DSN` is unset. If you're running locally and expect events to show up, they won't.
- **Frame locals named `assessment`, `row`, `s`, `sdata`, etc. are scrubbed.** The full list is in `backend/observability/sentry.py::_PII_LOCAL_NAMES`. If you're debugging a Sentry event and the locals look empty, they were scrubbed on purpose.
- **`sentry_sdk.init()` is idempotent.** The module-level `_initialized` flag prevents double-init when `backend.app` is re-imported (common in test teardown/setup). Transient init failures (e.g., malformed DSN caught at startup) do NOT set the flag, so a later call can retry after the env var is fixed.

---

## Escalation contacts

**Primary on-call:** user (solo)
- Phone: (set in BetterStack on-call policy)
- Slack: (set in BetterStack on-call policy)
- Email: (set in BetterStack on-call policy)

**Backup contact:** none currently. If a backup is arranged in the future, update the BetterStack on-call policy AND this section.
