# Tier 1 OpSafety Hardening — Design Spec

**Date:** 2026-05-21
**Brainstorm:** Claude (controller) + Codex/Gemini consulted on the provider picks per the original 2026-05-19 OpSafety roadmap mandate; user gave the final picks
**Predecessor:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` "2026-05-19 Production incident: Railway edge outage (GCP-side) and OpSafety hardening roadmap" (PR #434)
**Status:** CLOSED 2026-05-21 — shipped via PR1 (#447: railway-down runbook + customer comms templates) and PR2 (#448: status-banner.js + deferred probe-coverage audit). Probe audit deferred to the Jul 2026 quarterly drill per user decision.

---

## 1. Goal

Close the OpSafety gap the 2026-05-19 Railway/GCP incident verified live: when `app.graider.live` is unreachable, customers and the on-call have the information and tooling they need to know what is happening, who is doing what, and what NOT to do. Specifically:

1. Customers land on a working status page automatically, not on a cert warning or a Railway 404.
2. The on-call has a checked-in runbook capturing the 2026-05-19 diagnosis sequence + decision tree + escalation thresholds — not a blank page at 22:00 UTC.
3. Pre-drafted comms templates are ready to send — no improvising under pressure.
4. The existing BetterStack `/healthz` probe is verified to catch the 2026-05-19 incident class (TLS handshake failure at Railway's edge), not just HTTP 5xx.

## 2. Scope correction vs the original 2026-05-19 roadmap

The 2026-05-19 PR #434 dated section listed "off-Railway status page" and "external uptime monitor" as Tier 1 items. Those already exist (BetterStack Uptime + BetterStack Status Page at `https://status.graider.live`, shipped 2026-04-11 per `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md` and `docs/observability.md`). The PR #434 roadmap was written assuming a blank slate that didn't match repo reality.

The actual remaining gap is narrower: customers had no path from the broken `app.graider.live` to the working `status.graider.live`, and the diagnosis + comms artifacts from the 2026-05-19 incident weren't captured anywhere durable. The "marketing-site banner" item that was originally labeled Tier 2 in PR #434 is promoted to Tier 1 here because the incident verified it as the missing piece of customer trust.

## 3. Architecture

```
graider.live (Vercel)              status.graider.live (BetterStack)        app.graider.live (Railway)
        │                                       ▲                                    │
        │  GET /api/v1/status.json              │                                    │
        ├──────────────────────────────────────►│   ◄── /healthz probe every 3 min ──┤
        │  ◄── { status, incidents }            │       (BetterStack Uptime)         │
        │                                       │                                    │
   render banner if any                         │
   monitor/incident not "operational"           │
                                                │
                                  Slack #alerts │ iOS Critical Alert | Email
                                                │
                                          on-call: opens runbook
                                          → docs/runbooks/railway-down.md
                                          → posts comms template
                                          → escalates per decision tree
```

Four components, all consuming the existing BetterStack stack as the source of truth for "are we up?" No duplicate detection, no new monitoring infrastructure to maintain.

## 4. Components

### 4.1 Marketing-site banner (PR2)

**File:** new `<StatusBanner />` React component in the `landing/` Vercel project. Modify `landing/src/App.jsx` (or equivalent root, confirmed at implementation time) to render the banner at the top of the page.

**Behavior:**

1. On page load, fetch `https://status.graider.live/api/v1/status.json` with a 3-second timeout.
2. Parse the JSON. Render the banner when any monitor's `status !== "operational"` OR any incident is `status in {"investigating", "identified", "monitoring"}`.
3. Banner text: `"⚠️ We're experiencing service issues. Check [status.graider.live](https://status.graider.live) for live updates."` Yellow/orange background, dismissible (sessionStorage flag so a fresh visit during a sustained outage shows the banner again).
4. If the fetch fails (timeout, CORS, BetterStack down): render nothing (failing-open). A banner saying "status unknown" is worse than no banner during a normal page load with an API hiccup.

**Coupling:**

- Only depends on the BetterStack Status Page public JSON API (documented, stable).
- Does NOT depend on `app.graider.live` (the whole point — Railway-down does not break the banner).
- Does NOT depend on any env var (no manual toggle for ops to forget during triage).

**Failure modes:**

- BetterStack outage → banner does not render (failing-open).
- Race between BetterStack updating the incident and a user hitting the landing: banner is correct within ~3-min probe interval. Acceptable.
- Slow API (>3s timeout): banner does not render that page-load. Page-refresh recovers.

### 4.2 "Railway down" runbook (PR1)

**File:** new `docs/runbooks/railway-down.md` (new `docs/runbooks/` directory).

**Structure** (mirrors the 2026-05-19 incident section's prose but reorganized as a runbook):

1. **Confirm it's Railway, not us** — curl + openssl + dig + `status.railway.app` sequence.
2. **Decision tree** — table matching symptom to likely cause and action (TLS handshake fail + wrong-cert SAN = Railway-side; HTTP 5xx = app-level; DNS misconfig = our side; custom domain missing = wait, don't re-add mid-outage).
3. **Escalation thresholds** — 0-30 min observe; 30 min-2 hr keep observing + update Slack; 2 hr silence from `status.railway.app` = file a Railway ticket; multi-hour = send the customer email template.
4. **What NOT to do** — do not reflexive-rollback; do not re-add the custom domain mid-outage; do not file a Railway ticket within the first 2 hours; do not migrate providers reactively.
5. **Post-incident** — update the assessment doc with a dated section if anything new was learned; verify alert pipeline + banner worked end-to-end; check Tier 3 trigger conditions.

The 2026-05-19 incident section in the assessment doc stays as historical record. This runbook is the on-call reference distilled from it.

### 4.3 Customer comms templates (PR1)

**File:** new `docs/runbooks/customer-comms-templates.md` (same `docs/runbooks/` directory).

**Three templates:**

1. **Slack `#alerts` channel** (internal-team-facing) — posted immediately on Railway-side incident confirmation. Tells the team not to reflexively revert recent merges; points at `status.railway.app` for ETA and `docs/runbooks/railway-down.md` for triage.
2. **Customer-facing email** (school admins, sent only on multi-hour outages with student-facing impact) — plain-language, acknowledges student data is safe in Supabase, factual about cause and action, promises follow-through. No marketing language, no apologizing in a way that creates legal exposure.
3. **In-app banner** — already handled by Section 4.1's auto-rendered banner. No separate template needed.

**When each fires** (referenced from the runbook):

| Template | When |
|---|---|
| Slack `#alerts` | Immediately on any Railway-side incident confirmation |
| Customer email | Only on multi-hour outages with student-facing impact; not for brief edge blips |
| In-app banner | Automatic via the marketing-site banner whenever BetterStack shows non-operational |

### 4.4 Probe-coverage audit (PR2)

**Question:** did BetterStack's `/healthz` probe correctly detect the 2026-05-19 incident class (TLS handshake failure at Railway's edge), or did the alert fire only coincidentally?

**Why it matters:** the existing observability runbook's Rule 1 says *"`/healthz` returns non-200 for 2 consecutive probes OR response body missing `"supabase":"ok"`"*. A TLS handshake failure returns no HTTP status at all. Whether BetterStack's probe classifies that as "down" depends on the monitor configuration.

**Audit scope** (concrete, mechanical, fits in a single PR):

1. Pull BetterStack monitor config — document the `/healthz` monitor's current settings (URL, expected status code, expected response body, timeout, follow-redirects).
2. Verify the probe URL is `https://app.graider.live/healthz` (custom domain), NOT `https://<railway-internal>.up.railway.app/healthz`. If it's the internal URL, change to the custom domain — the internal URL would have served correctly during the 2026-05-19 incident even though customer traffic was broken.
3. Verify the probe treats TLS failure as "down" — BetterStack's default behavior is to fail on any TLS error, but document the actual config.
4. Simulate the 2026-05-19 failure mode in a staging context if cheap to do (e.g., point a test subdomain at a wrong-cert origin). If not trivial, skip and rely on the config audit alone.
5. Append a "Probe-coverage audit (2026-05-21)" section to `docs/observability.md` recording what was verified and any config changes. If the audit finds misconfiguration, the PR also fixes it via BetterStack dashboard config (not code) and records the change.

**No code changes expected** unless the audit finds something genuinely broken. The audit IS the deliverable.

## 5. Sequencing: two PRs

Mirrors the Slice 4/5 PR1+PR2 split pattern. PR1 is zero-deploy-risk pure docs; PR2 is the infrastructure change with the probe audit.

### PR1 — docs-only

**Files:**
- Create: `docs/runbooks/railway-down.md`
- Create: `docs/runbooks/customer-comms-templates.md`

**Verification:** lint readable (no enforced markdown linter; just `cat`-clean). Cross-reference internal links resolve (the runbook links to `customer-comms-templates.md` and to the assessment doc).

### PR2 — infrastructure

**Files:**
- Create: `landing/src/components/StatusBanner.jsx`
- Create: `landing/src/__tests__/StatusBanner.test.jsx`
- Modify: `landing/src/App.jsx` (or equivalent root) to render `<StatusBanner />` at the top
- Modify: `docs/observability.md` to append the "Probe-coverage audit (2026-05-21)" section
- BetterStack dashboard config: fix if audit finds misconfiguration (recorded in PR description, no code)

**Verification:**

| Test | Type | Location |
|---|---|---|
| `<StatusBanner />` parses 4 BetterStack status states correctly (operational, degraded, partial outage, major outage) | Unit | `landing/src/__tests__/StatusBanner.test.jsx` |
| `<StatusBanner />` renders nothing on fetch failure (timeout, malformed JSON, CORS) | Unit | same file |
| `<StatusBanner />` shows banner on incident-active + monitor-operational (e.g., scheduled maintenance with no probe failure) | Unit | same file |
| Probe-audit findings | Manual | Documented in `docs/observability.md` section appended by the PR |
| End-to-end during next quarterly alert drill (first Monday of Jul 2026) | Manual | When `FORCE_HEALTHZ_FAIL=1` flips the BetterStack monitor, verify banner appears on `graider.live` within ~6 minutes |

## 6. Data flow

**Normal operations:**

1. BetterStack Uptime probes `https://app.graider.live/healthz` every 3 min → 200 OK.
2. `status.graider.live`'s `/api/v1/status.json` returns `{ status: "operational", incidents: [] }`.
3. `graider.live`'s `<StatusBanner />` fetches that JSON, parses operational, renders nothing.

**Incident in progress:**

1. BetterStack probe fails for 2 consecutive checks (~6 min).
2. BetterStack auto-creates an incident on `status.graider.live`. Slack `#alerts` + iOS Critical Alert + email fire (existing routing rules 1-4 in `docs/observability.md`).
3. `/api/v1/status.json` returns non-operational on the next page-load.
4. `<StatusBanner />` renders with link to `status.graider.live`.
5. On-call opens `docs/runbooks/railway-down.md`, runs diagnosis, picks the right escalation.
6. If multi-hour: on-call posts Slack template; sends email template to school admins.

**Recovery:**

1. BetterStack probe succeeds for 2 consecutive checks.
2. BetterStack auto-resolves the incident.
3. `<StatusBanner />` parses operational, banner disappears on next page-load.
4. On-call posts "all clear" in `#alerts` (manual). Updates assessment doc if anything new was learned.

## 7. Error handling

| Component | Failure mode | Behavior |
|---|---|---|
| `<StatusBanner />` fetch | Timeout, CORS, BetterStack API down | Failing-open — render nothing |
| `<StatusBanner />` parse | Malformed JSON | Catch, console.log, render nothing |
| BetterStack probe | Probe service itself down | Out of scope. Same risk class as any monitoring vendor. |
| Runbook | Stale | Quarterly review during existing alert drill (Jan/Apr/Jul/Oct first Monday) |
| Comms template | Stale | Same quarterly review cadence |
| Probe audit | Probe was misconfigured | PR2 fixes config (BetterStack dashboard, no code). Audit documents before/after in `docs/observability.md` |

## 8. Out of scope (recorded explicitly)

- **Tier 2 items from the PR #434 roadmap:** data-safety boundary documentation, graceful-degrade mode (static export). Stay deferred.
- **Tier 3 items:** multi-PaaS active-active, direct cloud migration. Stay deferred per the trigger conditions in the assessment doc.
- **Frontend error tracking** (existing known gap in `docs/observability.md` follow-ups). Separate brainstorm.
- **SSL/domain expiry monitoring** — BetterStack paid feature, deferred per existing observability doc.
- **Provider re-evaluation** — the 2026-05-19 incident dated section concluded Railway is the right provider at this stage. Not re-litigating.

## 9. Success criteria

- Both PRs merged with 9 CI checks green.
- Quarterly alert drill (next: first Monday of Jul 2026, or sooner if convenient) verifies the banner appears on `graider.live` within ~6 minutes of `FORCE_HEALTHZ_FAIL=1` being set.
- Probe-coverage audit recorded in `docs/observability.md` with either "verified correct" or "fixed config X to Y" outcome.
- Runbook is the first thing the next on-call opens during a Railway-class incident (not a blank page).
- Closeout dated section in `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` records what shipped.
- Decision on whether to run a post-slice 3-model reconciled re-score: probably YES because this directly addresses the OpSafety dimension the 2026-05-19 incident verified the gap on. Whether Operational Safety moves 9 → 10 is a judgment call; the re-score is the established way to make it.

## 10. Risks

- **Vercel banner adds a runtime fetch on every landing page-load.** Adds ~50-200ms latency in the happy case. Failing-open keeps the page from being blocked. Acceptable.
- **BetterStack public status JSON API changes shape.** Low-probability vendor risk. The parser should be defensive (use `.get()` with defaults, treat unknown shapes as failing-open).
- **Probe audit finds a misconfiguration that requires fixing during a quiet window.** If the existing probe is the wrong URL, fixing it means BetterStack may briefly think the service is down or up depending on the new probe's first reading. Low risk; do the fix during business hours with the comms template ready.
- **Runbook + comms template go stale.** Mitigated by quarterly review during the existing alert drill cadence.

## 11. Approval

This is the design. The next step per the `superpowers:brainstorming` flow is user review of this written spec, followed by `superpowers:writing-plans` to produce the implementation plan.
