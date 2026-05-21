# Tier 1 OpSafety Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Tier 1 OpSafety hardening — a customer-facing banner on `graider.live` that auto-renders when `status.graider.live` shows non-operational, a "Railway down" runbook capturing the 2026-05-19 diagnosis sequence, pre-drafted customer comms templates, and a probe-coverage audit verifying BetterStack detects the 2026-05-19 incident class.

**Architecture:** Two sequenced PRs mirroring the Slice 4/5 PR1+PR2 split. PR1 is docs-only (zero deploy risk). PR2 adds the banner code to the existing vanilla JS landing project and appends a probe-audit section to `docs/observability.md`. The banner pulls `status.graider.live/api/v1/status.json` on each landing page-load and fails-open on fetch error.

**Tech Stack:** Vanilla JavaScript (no React; the `landing/` project is plain HTML/CSS/JS — `landing/index.html` + `landing/script.js` + `landing/styles.css`), Node 20+ `node:test` for the pure-logic unit tests (no test framework currently in `landing/`; built-in `node --test` runs them with zero install), Vercel deployment via `cd landing && npx vercel --prod` (per CLAUDE.md).

**Spec:** `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md`. Two-PR split + the failing-open contract are mandatory.

**Environment note:** Backend tests use the venv at `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`) and `--ignore=tests/load`. Landing tests are Node-native and need no venv. Never contact `:3000`. All changes via PR with the 9 CI checks green and the commit trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

**Spec correction note:** The spec assumed React (`landing/src/components/StatusBanner.jsx`) but the `landing/` project is vanilla HTML/CSS/JS. This plan implements the same behavior in vanilla JS, with pure-logic tests via `node:test`. The behavior, failure modes, and integration points are unchanged from the spec; only the language and test runner differ.

---

## File Structure

**PR1 (docs-only):**

- **Create:** `docs/runbooks/railway-down.md`. The on-call reference for Railway-class incidents. Distilled from the 2026-05-19 incident dated section in the assessment doc. Five sections: confirm it's Railway, decision tree, escalation thresholds, what NOT to do, post-incident.
- **Create:** `docs/runbooks/customer-comms-templates.md`. Three templates: Slack `#alerts` (internal-team-facing, posted immediately on incident confirmation), customer email (school admins, multi-hour outages only), reference to the in-app banner (auto-rendered by PR2).

**PR2 (infrastructure):**

- **Create:** `landing/status-banner.js`. Vanilla JS module. Pure function `shouldShowBanner(statusJSON)` that takes a BetterStack public-status JSON object and returns a boolean. DOM-mounting code (`mountStatusBanner()`) that fetches the API on page-load, calls `shouldShowBanner`, and renders the banner into a pre-existing container. Failing-open on any error.
- **Create:** `landing/status-banner.test.js`. Node-native unit tests via `node:test` for `shouldShowBanner` covering the 4 BetterStack status states (operational, degraded, partial outage, major outage), the incident-active-with-monitor-operational case, malformed-JSON, and missing-fields cases.
- **Modify:** `landing/index.html`. Add `<div id="status-banner" hidden></div>` immediately after `<body>` (before the navbar). Add `<script src="status-banner.js"></script>` near the existing `<script src="script.js"></script>` tag.
- **Modify:** `landing/styles.css`. Add CSS for `#status-banner.visible` (yellow/orange background, full-width, sticky-top, dismiss button styling). Banner stays hidden by default; the JS adds the `visible` class when active.
- **Modify:** `docs/observability.md`. Append a new section "Probe-coverage audit (2026-05-21)" at the bottom (before the existing "Follow-ups / known gaps" section if convenient, otherwise appended at the very end). Document the BetterStack monitor config audit findings, any fixes made via the BetterStack dashboard, and verification scope.

**PR2 closeout (still part of PR2 or follow-up commits, controller choice):**

- **Modify:** `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md`. STATUS-CLOSED stamp.
- **Modify:** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`. Append a "2026-05-2X Tier 1 OpSafety hardening closeout" dated section.

---

## Shared context for both PRs

### What the 2026-05-19 incident actually revealed

The BetterStack stack (Uptime + Status Page + Slack alerts + iOS Critical Alerts) already existed and worked: the Slack alert fired within minutes. What was missing:

1. Customers had no path from broken `app.graider.live` to working `status.graider.live` — the marketing site at `graider.live` (on Vercel, off-Railway) didn't surface the status page.
2. The diagnosis sequence (curl/openssl/dig + `status.railway.app`) wasn't in a runbook anywhere — controller redid it in real-time.
3. The Slack message warning the team not to revert recent merges was drafted in-session by the controller — no template.
4. The probe-coverage question: BetterStack's `/healthz` probe correctly fired on 2026-05-19, but the failure mode (TLS handshake failure at Railway's edge) doesn't return any HTTP status, so the alert routing rule's "non-200" condition doesn't strictly cover it. The probe may have detected via a different mechanism (connection failure, cert validation failure); the actual classification needs verification.

### BetterStack public status JSON API shape

BetterStack exposes the status page state at `https://<page-slug>.betteruptime.com/api/v1/status.json` and (for custom domains) at the configured custom domain. For `status.graider.live` the URL is `https://status.graider.live/api/v1/status.json`. Response shape (documented at <https://docs.betterstack.com/uptime/api/status-pages>, snapshot below — implementer should re-verify before relying on specific fields):

```json
{
  "status": "operational" | "degraded" | "partial_outage" | "major_outage",
  "monitors": [
    { "name": "<monitor name>", "status": "operational" | "degraded" | "down" }
  ],
  "incidents": [
    { "id": "...", "name": "...", "status": "investigating" | "identified" | "monitoring" | "resolved" }
  ]
}
```

The pure-logic function `shouldShowBanner(statusJSON)` MUST treat any of these as banner-on:
- Top-level `statusJSON.status !== "operational"` (any aggregate non-operational)
- Any `monitors[i].status !== "operational"` (specific monitor degraded or down)
- Any `incidents[i].status in {"investigating", "identified", "monitoring"}` (active incident, even if all monitors happen to be reporting operational at that moment — e.g., scheduled maintenance window or a delayed monitor pickup)

Banner-off only when ALL of: top-level operational + all monitors operational + zero active incidents.

### Vercel deploy

Per CLAUDE.md, the landing project deploys with `cd landing && npx vercel --prod`. This is a separate Vercel project from the backend. PR2 merging to `main` does NOT auto-deploy the landing — the landing deploys via the explicit Vercel CLI command. **Document this in the PR2 description so the deploy step is not forgotten.**

---

## PR 1: docs-only (railway-down.md + customer-comms-templates.md)

### Task 1.1: Branch + create `docs/runbooks/railway-down.md`

**Files:** Create `docs/runbooks/railway-down.md`

- [ ] **Step 1: Branch off main.**

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull origin main && git checkout -b feature/opsafety-tier1-pr1
mkdir -p docs/runbooks
```

- [ ] **Step 2: Create the runbook.**

```bash
cat > docs/runbooks/railway-down.md <<'EOF'
# Railway-Down Runbook

What to do when `app.graider.live` is unreachable. Use this BEFORE touching code or production state.

**Related docs:**
- `docs/runbooks/customer-comms-templates.md` — pre-drafted Slack and email templates
- `docs/observability.md` — alert routing rules and the existing BetterStack stack
- `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` — the 2026-05-19 incident postmortem and Tier 3 trigger conditions for provider migration

## 1. Confirm it's Railway, not us

Run these checks in order before considering any code rollback or production change:

```bash
# Check 1: HTTP / TLS layer
curl -sS -m 10 https://app.graider.live/healthz
```

- libcurl TLS errors (`SSL peer cert or SSH remote key was not OK`, browser shows `NET::ERR_CERT_COMMON_NAME_INVALID`) → Railway edge layer is degraded. Skip the code-rollback reflex.
- HTTP 5xx → app-level failure. Check BetterStack errors first (Slack `#alerts` or the BetterStack dashboard).
- Connection refused / timeout → likely Railway-edge or upstream-of-Railway.

```bash
# Check 2: which cert is being served
openssl s_client -connect app.graider.live:443 -servername app.graider.live -showcerts </dev/null 2>&1 | head -25
```

- If the served cert `subject=` is `CN=*.up.railway.app` and SAN list is `DNS:*.up.railway.app` only (NOT `app.graider.live`) → Railway's custom-domain routing is impaired. This is NOT a cert expiry issue (the wildcard cert is valid; it just isn't the right cert for our hostname).
- If the served cert `subject=` includes `app.graider.live` → cert is correct; problem is elsewhere.

```bash
# Check 3: DNS resolution
dig +short app.graider.live A
```

- Expected: `app.graider.live` → CNAME to a Railway POP (`ar90ys35.up.railway.app` historically) → A record like `66.33.22.209`. DNS is on **Cloudflare** (not Vercel — see `docs/observability.md` "DNS ownership note"). If DNS resolves correctly, the gap is at Railway's project-domain mapping.

```bash
# Check 4: upstream status
open https://status.railway.app
```

- Look for active Edge Network, Control Plane, or Database incidents. If `status.railway.app` shows a Major Outage, root cause is upstream. Note the incident time and the cited root cause (e.g., "Google Cloud has blocked our account" on 2026-05-19).

## 2. Decision tree

| Symptom | Likely cause | Action |
|---|---|---|
| TLS handshake fails + wrong-cert SAN + `status.railway.app` shows incident | Railway-side outage (possibly upstream like GCP) | Hold. Post Slack template (see comms templates). Do NOT re-add the domain, do NOT file a Railway ticket yet. |
| HTTP 5xx | App-level failure | Check BetterStack errors. Consider rollback ONLY if a recent merge correlates with the start of errors. |
| DNS misconfigured | Our side | Check Cloudflare DNS dashboard. Fix the CNAME / A record. |
| Custom domain missing from Railway dashboard | Possibly stale registration | Wait for Railway recovery before re-adding. Mid-outage re-add risks stuck "pending" cert state, duplicate registrations, or failed Let's Encrypt provisioning while the edge plane is degraded. |
| Connection refused / timeout, `status.railway.app` is green | Railway-side localized incident not yet on their status page | Capture the Railway edge Request ID from `curl -v` output. Wait 15 min for Railway status to catch up. |

## 3. Escalation thresholds

| Time into incident | Action |
|---|---|
| 0 to 30 min | Observe. Post the Slack template to `#alerts` (`docs/runbooks/customer-comms-templates.md` Template 1). Verify the BetterStack incident on `status.graider.live` and the `graider.live` banner. |
| 30 min to 2 hr | Keep observing. Update Slack `#alerts` if the situation materially changes. Do NOT email customers yet — short outages don't warrant proactive customer comms. |
| 2 hr Railway silence | File a Railway customer support ticket. Capture: the edge Request IDs from the curl probes, your Railway project name, the incident timeline. The ticket is reserved for if `status.railway.app` goes silent for 2+ hours past the initial incident post. |
| Multi-hour incident with active customer impact | Send the customer email template (`docs/runbooks/customer-comms-templates.md` Template 2) to school admins. Coordinate with the on-call to time the send. |

## 4. What NOT to do

- **Do not roll back recent merges based on the prod-down alert alone.** A TLS-handshake failure means the connection never reached Flask. Code cannot cause it. Verify the failure mode via Checks 1–2 before considering any rollback.
- **Do not re-add the custom domain in the Railway dashboard during the incident.** Risks stuck "pending" cert state, duplicate registrations, or failed Let's Encrypt provisioning while the edge plane is degraded. Wait for Railway recovery.
- **Do not file a Railway ticket within the first 2 hours unless Railway has gone silent.** Their team is already engaged on a public Major Outage. A customer ticket adds backlog without changing the outcome.
- **Do not migrate providers reactively.** Single-provider risk is the structural item; provider choice rotates which incidents we are exposed to, it does not eliminate the class. See the assessment doc's "Tier 3 trigger conditions" for the recorded thresholds (3+ multi-hour outages in 6 months, a paying-customer SLA contract demand, scale outgrowing Railway's pricing model, a specific feature becoming blocking).

## 5. Post-incident

1. Once Railway recovers, verify `curl https://app.graider.live/healthz` returns 200 with `"status":"ok"` in the body. Verify the BetterStack incident auto-resolves on `status.graider.live`. Verify the `graider.live` banner disappears on next page-load.
2. Post "all clear" in Slack `#alerts`.
3. Update `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` with a dated section IF anything new was learned (a novel failure mode, a runbook gap, a new escalation pattern). If the incident was a clean repeat of 2026-05-19, no doc update is necessary.
4. If a Tier 3 trigger condition was met, open a brainstorm for provider re-evaluation. Trigger conditions are deliberately strict to prevent reactive migration after a single bad night.
5. Verify the alert pipeline + customer banner worked end-to-end. Note any gaps; file follow-ups.
EOF
```

- [ ] **Step 3: Verify the file is readable.**

Run:
```bash
cat docs/runbooks/railway-down.md | head -20
wc -l docs/runbooks/railway-down.md
```

Expected: file exists, first line is `# Railway-Down Runbook`, total around 90 lines.

- [ ] **Step 4: Commit.**

```bash
git add docs/runbooks/railway-down.md
git commit -m "docs(runbook): railway-down.md — 5-section on-call reference for Railway-class incidents (Tier 1 OpSafety PR1)

Distills the 2026-05-19 incident dated section into a checked-in runbook:
diagnosis sequence (curl/openssl/dig/status.railway.app), decision tree
mapping symptom to likely cause and action, escalation thresholds at
30 min / 2 hr / multi-hour, explicit what-NOT-to-do list (no reflex
rollback on TLS handshake fail, no domain re-add mid-outage, no Railway
ticket within 2 hr, no reactive provider migration), and post-incident
verification + dated-section update protocol.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.2: Create `docs/runbooks/customer-comms-templates.md`

**Files:** Create `docs/runbooks/customer-comms-templates.md`

- [ ] **Step 1: Create the file.**

```bash
cat > docs/runbooks/customer-comms-templates.md <<'EOF'
# Customer Comms Templates

Pre-drafted messages for outage incidents. The on-call copies these into Slack / email, fills in the `<bracketed>` fields, and sends. Goal: do not improvise customer comms under pressure.

**When each template fires** (referenced from `docs/runbooks/railway-down.md`):

| Template | Audience | When |
|---|---|---|
| Template 1: Slack `#alerts` | Internal team | Immediately on any Railway-side incident confirmation |
| Template 2: Customer email | School admins | Only on multi-hour outages with student-facing impact (not for brief edge blips) |
| Template 3: In-app banner | Customers (any landing visitor) | Automatic via `graider.live` `<StatusBanner />` — no manual send needed |

---

## Template 1 — Slack `#alerts` channel (internal-team-facing)

Posted immediately when a Railway-side incident is confirmed via the runbook's Section 1 checks. Tells the team not to reflexively revert recent merges and where to go for updates.

```
🚨 Production unreachable — Railway-side incident, NOT a code regression.

Symptoms:
- app.graider.live returning <TLS handshake errors / cert mismatch / edge 404 / HTTP 5xx — fill in what you saw>
- status.railway.app shows: <Major Outage / Edge Network / GCP-side / etc. — paste the relevant excerpt>

What this means:
- The Flask app is almost certainly healthy. The connection isn't reaching it.
- Recent PRs (<list any PRs merged in the past 24h>) are NOT the cause. Do not revert.

What we're doing:
- Holding position. Railway has identified the issue and is working with their upstream provider.
- Customer status page at status.graider.live is updated automatically by BetterStack.
- Marketing-site banner on graider.live auto-renders (no manual toggle needed).

ETA: see status.railway.app. I'll update here when there's a material change.

Runbook: docs/runbooks/railway-down.md
```

---

## Template 2 — Customer-facing email (school admins, multi-hour outages only)

Send only if the runbook's Section 3 escalation threshold for multi-hour customer impact is met. Plain-language, FERPA-aware, factual. No marketing language, no apologizing in a way that creates legal exposure.

```
Subject: Graider service interruption — <date> <time> UTC

Hi <admin name>,

Graider experienced a service interruption today starting at <UTC time>.

What happened: Our cloud provider had an upstream outage that affected
how requests reach the Graider application. The interruption was on the
networking side, not the application side. Student work submitted
before the interruption is safe in our database — we never lost data,
only the ability to serve new requests for the duration of the outage.

Current status: <Resolved / In progress; see https://status.graider.live
for live updates>.

What we're doing about it: We're documenting the incident, what we did
to respond, and what we've learned. Concrete steps that came out of this
event will be in the next release notes.

If you have questions or saw something specific go wrong for one of your
teachers or students, reply directly to this email and I'll get back to
you within one business day.

Thanks for your patience,
<sender name>
Graider
```

**Why this template's wording matters:**
- "Cloud provider had an upstream outage" is honest and non-technical. Avoids exposing Railway as the dependency by name (most school admins don't care which PaaS we use, and naming the vendor invites future "are you still on Railway?" questions).
- "Student work submitted before the interruption is safe in our database" is the FERPA-relevant reassurance. Supabase is on a separate stack from Railway; the data layer was not affected. Don't say more than this in the email body — the data-safety boundary is documented in the Tier 2 follow-up.
- "Concrete steps... in the next release notes" commits to follow-through without overpromising specific fixes.
- "I'll get back to you within one business day" sets a realistic SLA. Don't promise 24/7.

---

## Template 3 — In-app banner

The auto-rendered banner on `graider.live` (PR2 of this slice) is the in-app version. It links to `status.graider.live`. No manual copy needed — the banner pulls live state from BetterStack's public status JSON and fails-open on fetch error.

Banner text (already coded into `landing/status-banner.js`):
```
⚠️ We're experiencing service issues. Check status.graider.live for live updates.
```

---

## Tone calibration

- **Slack template:** Technical, direct, action-oriented (audience = team).
- **Email template:** Plain-language, FERPA-aware, factual about cause and action, promises follow-through.
- **No marketing language** in either. No apologizing in a way that creates legal exposure. Honest about what happened, factual about what we did.

## Quarterly review

Review both templates during the existing quarterly alert drill (first Monday of Jan / Apr / Jul / Oct — see `docs/observability.md`). Check: do they still match Graider's current language, ownership, and tooling? Are there new failure modes worth pre-drafting for?
EOF
```

- [ ] **Step 2: Verify.**

Run:
```bash
cat docs/runbooks/customer-comms-templates.md | head -10
wc -l docs/runbooks/customer-comms-templates.md
```

Expected: file exists, around 90 lines, first line `# Customer Comms Templates`.

- [ ] **Step 3: Verify the cross-references resolve.**

Run:
```bash
grep -nE "docs/runbooks/customer-comms-templates\.md|docs/runbooks/railway-down\.md" docs/runbooks/*.md
```

Expected: each file references the other at least once. Both files exist (`ls docs/runbooks/`).

- [ ] **Step 4: Commit.**

```bash
git add docs/runbooks/customer-comms-templates.md
git commit -m "docs(runbook): customer-comms-templates.md — 3 pre-drafted outage templates (Tier 1 OpSafety PR1)

Three templates:
- Slack #alerts (internal-team, immediate on incident confirmation)
- Customer email (school admins, multi-hour outages with active impact only;
  FERPA-aware reassurance that Supabase-stored student work is safe)
- In-app banner reference (handled by PR2's status-banner.js, no manual send)

Tone calibration notes explain why specific wording choices matter (e.g.,
'cloud provider had an upstream outage' is honest without naming Railway;
'within one business day' sets a realistic SLA without 24/7 promises).

Quarterly review cadence pinned to the existing alert drill (first Monday
of Jan/Apr/Jul/Oct per docs/observability.md).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.3: Open PR1

- [ ] **Step 1: Push branch.**

```bash
git push -u origin feature/opsafety-tier1-pr1
```

- [ ] **Step 2: Open PR.**

```bash
gh pr create --base main --head feature/opsafety-tier1-pr1 \
  --title "docs(runbooks): Railway-down runbook + customer comms templates (Tier 1 OpSafety PR1)" \
  --body "$(cat <<'BODY'
## Summary

Tier 1 OpSafety hardening PR1 — pure docs, zero deploy risk. Distills the 2026-05-19 Railway/GCP incident artifacts into checked-in runbooks the next on-call can open instead of redoing the diagnosis from scratch.

## Files created

- \`docs/runbooks/railway-down.md\` — 5 sections: confirm it's Railway (curl/openssl/dig/status.railway.app), decision tree, escalation thresholds (30min/2hr/multi-hour), what NOT to do, post-incident verification.
- \`docs/runbooks/customer-comms-templates.md\` — 3 templates: Slack #alerts, customer email for school admins, in-app banner reference (handled by PR2).

## Why a separate file (not appended to docs/observability.md)

\`docs/observability.md\` covers the whole observability stack and alert pipeline. A Railway-down runbook is incident-specific — when Railway is hard-down, the on-call needs ONE doc that says \"do this.\" Splitting keeps each focused.

## Verification

- Cross-references resolve: runbook links to comms templates and vice versa.
- Both files use the existing repo's prose style (markdown, no extra lint).
- No production code touched.

## What stays out of scope for this PR

- Landing-page banner code (PR2 of this slice).
- BetterStack probe-coverage audit (PR2 of this slice).
- Slice closeout dated section in the assessment doc (after PR2 merges).
- Post-slice 3-model re-score (Task 4, optional, controller judgment).

## Plan + spec

- Plan: \`docs/superpowers/plans/2026-05-21-opsafety-tier1.md\`
- Spec: \`docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

- [ ] **Step 3: Arm auto-merge.**

```bash
gh pr merge --squash --auto
```

- [ ] **Step 4: Wait for PR1 to merge.**

Background-watch the PR until merged. Confirm sha lands on main; clean up local branch.

```bash
PR_NUM=$(gh pr view --json number -q .number)
echo "Watching PR #$PR_NUM"
# Poll until merged (max 30 min); then capture sha
for i in $(seq 1 90); do
  STATE=$(gh pr view $PR_NUM --json state -q .state)
  if [ "$STATE" = "MERGED" ]; then
    SHA=$(gh pr view $PR_NUM --json mergeCommit -q .mergeCommit.oid | head -c 7)
    echo "MERGED sha=$SHA"
    break
  fi
  sleep 20
done
git checkout main && git pull origin main && git branch -D feature/opsafety-tier1-pr1
```

---

## PR 2: infrastructure (status-banner.js + probe audit)

### Task 2.1: Branch + pure-logic module + tests

**Files:** Create `landing/status-banner.js` (pure logic only — DOM mount comes in Task 2.2). Create `landing/status-banner.test.js`.

- [ ] **Step 1: Branch.**

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull origin main && git checkout -b feature/opsafety-tier1-pr2
```

- [ ] **Step 2: RED — write the failing tests first.**

Create `landing/status-banner.test.js`:

```bash
cat > landing/status-banner.test.js <<'EOF'
// Tests for the status-banner pure logic. Run with `node --test landing/status-banner.test.js`.
// No test framework dependency — uses Node 20+ built-in node:test runner.

const test = require('node:test');
const assert = require('node:assert/strict');
const { shouldShowBanner } = require('./status-banner.js');

test('returns false when top-level operational, all monitors operational, no incidents', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), false);
});

test('returns true when top-level status is degraded', () => {
  const json = {
    status: 'degraded',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when top-level status is partial_outage', () => {
  const json = {
    status: 'partial_outage',
    monitors: [{ name: 'app', status: 'down' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when top-level status is major_outage', () => {
  const json = {
    status: 'major_outage',
    monitors: [{ name: 'app', status: 'down' }],
    incidents: [{ id: '1', name: 'Outage', status: 'investigating' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when any monitor is degraded (even if top-level says operational)', () => {
  const json = {
    status: 'operational',
    monitors: [
      { name: 'app', status: 'operational' },
      { name: 'api', status: 'degraded' },
    ],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true on incident-active-with-monitor-operational (scheduled maintenance window or delayed monitor pickup)', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', name: 'Maintenance', status: 'monitoring' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true for incidents with status investigating', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'investigating' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true for incidents with status identified', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'identified' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns false when only resolved incidents are present', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'resolved' }],
  };
  assert.equal(shouldShowBanner(json), false);
});

test('returns false (fails-open) when input is null', () => {
  assert.equal(shouldShowBanner(null), false);
});

test('returns false (fails-open) when input is undefined', () => {
  assert.equal(shouldShowBanner(undefined), false);
});

test('returns false (fails-open) when input is not an object', () => {
  assert.equal(shouldShowBanner('not json'), false);
  assert.equal(shouldShowBanner(42), false);
  assert.equal(shouldShowBanner([]), false);
});

test('returns false (fails-open) when input is missing all expected fields', () => {
  assert.equal(shouldShowBanner({}), false);
});

test('handles missing monitors array (treats as no-monitor signal)', () => {
  const json = { status: 'operational', incidents: [] };
  assert.equal(shouldShowBanner(json), false);
});

test('handles missing incidents array (treats as no-incident signal)', () => {
  const json = { status: 'operational', monitors: [{ status: 'operational' }] };
  assert.equal(shouldShowBanner(json), false);
});

test('handles monitor entries with missing status field (treats as operational)', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), false);
});
EOF
```

- [ ] **Step 3: Run the tests — must FAIL with module-not-found.**

```bash
cd /Users/alexc/Downloads/Graider/landing
node --test status-banner.test.js
```

Expected output includes: `Cannot find module './status-banner.js'` (or similar). All 16 tests should be reported as failures.

- [ ] **Step 4: GREEN — write the minimal pure-logic module.**

Create `landing/status-banner.js`:

```bash
cat > landing/status-banner.js <<'EOF'
/* ============================================
   GRAIDER LANDING — STATUS BANNER
   ============================================

   Pulls the BetterStack public status JSON from status.graider.live and
   renders a banner at the top of the page when any of:
   - top-level status != "operational"
   - any monitor status != "operational"
   - any incident status in {"investigating", "identified", "monitoring"}

   Fails-open on any fetch error, parse error, or unexpected shape:
   a "status unknown" banner is worse than no banner during a normal
   page-load with an API hiccup.

   See docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md.
   ============================================ */

const STATUS_URL = 'https://status.graider.live/api/v1/status.json';
const FETCH_TIMEOUT_MS = 3000;
const ACTIVE_INCIDENT_STATES = ['investigating', 'identified', 'monitoring'];

/**
 * Decide whether to show the banner.
 *
 * Fails-open: returns false on any unexpected input shape so the banner
 * does not render when the API is having a hiccup.
 *
 * @param {object} statusJSON - Parsed BetterStack /api/v1/status.json response.
 * @returns {boolean} true to show banner, false otherwise.
 */
function shouldShowBanner(statusJSON) {
  if (!statusJSON || typeof statusJSON !== 'object' || Array.isArray(statusJSON)) {
    return false;
  }

  // Check top-level aggregate status. Banner ON if anything other than
  // explicit "operational".
  if (statusJSON.status && statusJSON.status !== 'operational') {
    return true;
  }

  // Check individual monitors. Banner ON if any monitor reports non-operational.
  const monitors = Array.isArray(statusJSON.monitors) ? statusJSON.monitors : [];
  for (const m of monitors) {
    if (m && m.status && m.status !== 'operational') {
      return true;
    }
  }

  // Check active incidents. Banner ON if any incident is in an active
  // (non-resolved) state.
  const incidents = Array.isArray(statusJSON.incidents) ? statusJSON.incidents : [];
  for (const inc of incidents) {
    if (inc && inc.status && ACTIVE_INCIDENT_STATES.includes(inc.status)) {
      return true;
    }
  }

  return false;
}

// CommonJS export for node:test. The browser-mounting path in Task 2.2
// uses a separate IIFE that does not depend on CommonJS.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { shouldShowBanner, STATUS_URL, FETCH_TIMEOUT_MS, ACTIVE_INCIDENT_STATES };
}
EOF
```

- [ ] **Step 5: Run the tests — must PASS.**

```bash
cd /Users/alexc/Downloads/Graider/landing
node --test status-banner.test.js
```

Expected: `tests 16, pass 16, fail 0`. Report the exact `tests/pass/fail` line.

- [ ] **Step 6: Commit.**

```bash
cd /Users/alexc/Downloads/Graider
git add landing/status-banner.js landing/status-banner.test.js
git commit -m "feat(landing): status-banner.js pure-logic module + 16 unit tests (Tier 1 OpSafety PR2)

Vanilla JS module. The pure function shouldShowBanner(statusJSON) takes
a BetterStack public-status JSON object and returns a boolean per the
spec's banner-on conditions:

- top-level status != \"operational\", OR
- any monitor status != \"operational\", OR
- any incident status in {\"investigating\", \"identified\", \"monitoring\"}

Fails-open on any unexpected input (null, non-object, missing fields,
malformed shape) so an API hiccup never renders a misleading banner.

Tests use Node 20+ built-in node:test (no test framework dependency).
16 cases cover the 4 BetterStack status states + monitor-degraded +
incident-active-with-monitor-operational + 3 resolved-status + 8
fails-open shape edge cases.

DOM mounting is the follow-up commit. This commit is the pure-logic
foundation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.2: DOM mount + index.html + styles.css

**Files:** Modify `landing/status-banner.js` (add the IIFE that mounts on DOMContentLoaded). Modify `landing/index.html` (add the banner container + script tag). Modify `landing/styles.css` (add banner styles).

- [ ] **Step 1: Append the DOM-mounting IIFE to `status-banner.js`.**

Append (NOT replace) — preserve the CommonJS export block at the bottom of the file. The IIFE runs only in a browser context (where `window` and `document` exist) and is a no-op in a Node test context.

```bash
cat >> landing/status-banner.js <<'EOF'

// ============================================
// BROWSER MOUNTING (IIFE — no-op in Node)
// ============================================
//
// On DOMContentLoaded, fetch the status JSON, decide whether to render,
// and inject the banner into #status-banner. Failing-open is critical:
// any error path silently renders nothing.

(function () {
  // Skip in non-browser environments (e.g., node:test runner).
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return;
  }

  function buildBannerHTML() {
    return [
      '<div class="status-banner-content">',
      '  <span class="status-banner-icon" aria-hidden="true">⚠️</span>',
      '  <span class="status-banner-text">',
      '    We\'re experiencing service issues. Check ',
      '    <a href="https://status.graider.live" target="_blank" rel="noopener noreferrer">status.graider.live</a>',
      '    for live updates.',
      '  </span>',
      '  <button class="status-banner-dismiss" aria-label="Dismiss banner" type="button">×</button>',
      '</div>',
    ].join('');
  }

  function mountBanner(container) {
    container.innerHTML = buildBannerHTML();
    container.classList.add('visible');
    container.removeAttribute('hidden');
    const dismissBtn = container.querySelector('.status-banner-dismiss');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', function () {
        container.classList.remove('visible');
        container.setAttribute('hidden', '');
        try {
          sessionStorage.setItem('graider:status-banner-dismissed', '1');
        } catch (_) {
          // sessionStorage can throw in private-browsing or quota-exceeded
          // contexts. Failing-open: dismissal is per-tab even without storage.
        }
      });
    }
  }

  async function fetchStatusWithTimeout() {
    const controller = new AbortController();
    const timeout = setTimeout(function () { controller.abort(); }, FETCH_TIMEOUT_MS);
    try {
      const resp = await fetch(STATUS_URL, { signal: controller.signal, cache: 'no-store' });
      if (!resp.ok) {
        return null;
      }
      return await resp.json();
    } catch (_) {
      return null;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function init() {
    const container = document.getElementById('status-banner');
    if (!container) {
      return;
    }
    try {
      if (sessionStorage.getItem('graider:status-banner-dismissed') === '1') {
        return;
      }
    } catch (_) {
      // No sessionStorage available — proceed without dismissal memory.
    }
    const statusJSON = await fetchStatusWithTimeout();
    if (statusJSON && shouldShowBanner(statusJSON)) {
      mountBanner(container);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
EOF
```

- [ ] **Step 2: Run the existing tests again to confirm the IIFE addition didn't break the pure-logic exports.**

```bash
cd /Users/alexc/Downloads/Graider/landing
node --test status-banner.test.js
```

Expected: `tests 16, pass 16, fail 0`. (The IIFE has an early-return guard for non-browser environments, so it's a no-op in the test runner.)

- [ ] **Step 3: Add the banner container + script tag to `landing/index.html`.**

Read the current `<body>` opening (around line 228 — re-derive with `grep -n '<body>' landing/index.html`) and the existing `<script>` tag for `script.js` (search with `grep -n 'script\.js' landing/index.html`).

Insert the banner container immediately after `<body>` (before the navbar). Insert the new script tag right next to the existing `script.js` tag (load order is fine either way since `status-banner.js`'s IIFE waits for `DOMContentLoaded`).

Use surgical edits — do NOT rewrite the whole HTML file.

```bash
# Re-derive the exact line numbers
grep -n '<body>' landing/index.html
grep -n 'src="script\.js"' landing/index.html
```

Then use the Edit tool (or `sed` if you prefer) to:

1. Right after the line `<body>`, insert: `    <!-- Off-Railway status banner — auto-rendered by status-banner.js when BetterStack reports non-operational. Hidden by default; fails-open. -->` then `    <div id="status-banner" hidden></div>`.
2. Right before the line containing `src="script.js"`, insert: `    <script src="status-banner.js"></script>`.

After the edit, confirm:

```bash
grep -A 1 '<body>' landing/index.html | head -5
grep -B 1 'src="script\.js"' landing/index.html | head -5
```

Expected: the banner div appears right after `<body>`, and the `<script src="status-banner.js"></script>` appears right before the existing `<script src="script.js"></script>`.

- [ ] **Step 4: Add banner CSS to `landing/styles.css`.**

Find the end of the existing `styles.css` (last line) and append the banner styles. Use a class-based approach so the JS adds/removes `.visible` to toggle display.

```bash
cat >> landing/styles.css <<'EOF'

/* ============================================
   STATUS BANNER (Tier 1 OpSafety, 2026-05-21)
   ============================================ */

#status-banner {
  display: none;
}

#status-banner.visible {
  display: block;
  position: sticky;
  top: 0;
  z-index: 9999;
  background: #fff7e6;
  border-bottom: 1px solid #f0ad4e;
  color: #5a3e0b;
  font-size: 14px;
  line-height: 1.4;
  padding: 10px 16px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
}

.status-banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 1200px;
  margin: 0 auto;
}

.status-banner-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.status-banner-text {
  flex: 1;
}

.status-banner-text a {
  color: #5a3e0b;
  text-decoration: underline;
  font-weight: 600;
}

.status-banner-text a:hover {
  color: #2d1f06;
}

.status-banner-dismiss {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: #5a3e0b;
  font-size: 20px;
  line-height: 1;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
}

.status-banner-dismiss:hover {
  background: rgba(90, 62, 11, 0.1);
}

.status-banner-dismiss:focus-visible {
  outline: 2px solid #f0ad4e;
  outline-offset: 2px;
}

@media (max-width: 600px) {
  #status-banner.visible {
    font-size: 13px;
    padding: 8px 12px;
  }
}
EOF
```

- [ ] **Step 5: Manual smoke test in a local server.**

The banner cannot be tested without a real BetterStack response. Two smoke checks:

5a. Serve the landing locally and confirm the banner is hidden when BetterStack is operational:

```bash
cd /Users/alexc/Downloads/Graider/landing
python3 -m http.server 8765 &
SERVER_PID=$!
sleep 1
curl -sS http://localhost:8765/index.html | grep -c 'id="status-banner"'
# Expected: 1
curl -sS http://localhost:8765/status-banner.js | head -3
# Expected: header comment from status-banner.js
kill $SERVER_PID
```

5b. Smoke-test the rendering path locally using a stub status JSON. Create a one-off test page:

```bash
cat > /tmp/banner-smoke.html <<'EOF'
<!DOCTYPE html>
<html><head><title>Banner smoke test</title>
<link rel="stylesheet" href="http://localhost:8765/styles.css">
</head><body>
<div id="status-banner" hidden></div>
<script>
  // Stub the fetch to return a "degraded" status
  window.fetch = async function() {
    return {
      ok: true,
      json: async () => ({
        status: 'degraded',
        monitors: [{ name: 'app', status: 'degraded' }],
        incidents: [],
      }),
    };
  };
</script>
<script src="http://localhost:8765/status-banner.js"></script>
</body></html>
EOF
# Manually open /tmp/banner-smoke.html in a browser and verify the banner renders.
# After verifying, dismiss it and reload — verify it stays dismissed (sessionStorage).
# Then close the tab and reopen — verify it renders again (sessionStorage scoped to tab).
```

Document the manual smoke result in the commit message.

- [ ] **Step 6: Commit.**

```bash
git add landing/status-banner.js landing/index.html landing/styles.css
git commit -m "feat(landing): mount status-banner on graider.live with sticky CSS + dismiss button (Tier 1 OpSafety PR2)

Appends the DOM-mounting IIFE to status-banner.js (no-op in Node, so the
pure-logic tests still pass at 16/16). Adds a #status-banner container
to index.html right after <body>, hidden by default. Adds CSS for the
yellow/orange sticky banner with the BetterStack-linked text and a
dismiss × button that remembers per-tab via sessionStorage.

Manual smoke test verified:
- index.html serves the #status-banner div and the status-banner.js script
- with a stub fetch returning 'degraded' the banner renders correctly
- dismiss persists per tab via sessionStorage
- new tab re-renders the banner (per-tab scope only)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.3: Probe-coverage audit + observability.md section

**Files:** Modify `docs/observability.md`.

- [ ] **Step 1: Manual audit step — log into BetterStack and document the `/healthz` monitor's current settings.**

This step requires the user (controller cannot access BetterStack credentials). Controller asks the user to run the audit and report back; controller drafts the doc section based on the user's findings.

The implementer subagent CANNOT perform this audit step. Therefore: dispatch the implementer with the task of drafting the section conditional on user-supplied audit findings, OR skip subagent dispatch and have the controller draft the section directly after the user reports back.

For the plan: the implementer's task is to draft a TEMPLATE for the audit section in `docs/observability.md` with explicit `<TO_FILL>` placeholders for the user's findings, AND to write the cross-references and the verification scope. The user fills in the placeholders and the controller commits the final version.

- [ ] **Step 2: Draft the audit section template.**

The implementer modifies `docs/observability.md` by appending the following at the very end of the file (after the existing "Follow-ups / known gaps" section). Use the Edit tool with `old_string` = the last line of the existing file (re-derive at edit time) and `new_string` = that last line + the appended block. Do NOT rewrite the whole file.

The appended block:

```markdown

---

## Probe-coverage audit (2026-05-21, Tier 1 OpSafety)

Verifies that BetterStack's `/healthz` probe correctly detects the 2026-05-19 incident class (TLS handshake failure at Railway's edge), not just HTTP 5xx. The existing alert routing Rule 1 above says *"`/healthz` returns non-200 for 2 consecutive probes OR response body missing `"supabase":"ok"`"*. A TLS handshake failure returns no HTTP status at all — neither 200 nor non-200. Whether BetterStack classifies that as "down" depends on monitor configuration.

### Audit findings (2026-05-21)

**Probe URL:** `<TO_FILL: confirm the BetterStack monitor URL — must be https://app.graider.live/healthz (custom domain), NOT https://<railway-internal>.up.railway.app/healthz. The internal URL would have served correctly during the 2026-05-19 incident even though customer traffic was broken.>`

**Expected status code:** `<TO_FILL: e.g., "200 OK" — BetterStack's expected-status field.>`

**Expected response body keyword:** `<TO_FILL: e.g., "ok" or empty — BetterStack's response-body-keyword field. The existing alert routing Rule 1 says the probe also checks for `"supabase":"ok"` in the body; document whether that's via the response-body-keyword field or via a separate mechanism.>`

**Timeout:** `<TO_FILL: e.g., 10s — BetterStack's probe-timeout setting. Should be ≥ the worst-case Supabase round-trip latency (currently ~4s during nominal load per the Slow Request warnings in container logs).>`

**Follow-redirects:** `<TO_FILL: true / false — BetterStack's follow-redirects setting. Should be false; a redirect on /healthz is itself a misconfiguration worth alerting on.>`

**TLS-failure classification:** `<TO_FILL: confirm BetterStack treats TLS handshake failures as "down". Per BetterStack docs, the default behavior is to fail the check on any TLS error; document the actual config and any non-default override.>`

### Config fixes made (if any)

`<TO_FILL: list any changes made in the BetterStack dashboard, e.g., "Changed probe URL from https://...up.railway.app/healthz to https://app.graider.live/healthz on 2026-05-2X" or "No changes; existing config verified correct">`

### Verification scope

What this audit covered:
- BetterStack monitor configuration for the `/healthz` probe.
- The probe URL is the customer-facing custom domain, not a Railway-internal URL.
- TLS-handshake failure is correctly classified as "down."

What this audit deliberately did NOT cover:
- Probe behavior under load (false positives during traffic spikes). Out of scope for Tier 1.
- Multi-region probe geographic coverage. BetterStack free tier is multi-region by default; not verified per region.
- Probe behavior during BetterStack-side incidents. Out of scope; same risk class as any monitoring vendor.

### Next quarterly drill

Verify that during the next `FORCE_HEALTHZ_FAIL=1` drill (first Monday of Jul 2026), the `graider.live` banner appears within ~6 minutes of the BetterStack incident being created.
```

- [ ] **Step 3: Commit the audit-section template.**

```bash
git add docs/observability.md
git commit -m "docs(observability): probe-coverage audit section template (Tier 1 OpSafety PR2)

Appends a 'Probe-coverage audit (2026-05-21)' section to docs/observability.md
with <TO_FILL> placeholders for the BetterStack monitor config findings.
The user fills in the placeholders after running the audit in the
BetterStack dashboard; the controller commits the final version in a
follow-up commit before merging this PR.

Audit scope (per spec section 4.4): probe URL is custom domain not
Railway-internal; expected status code, response-body keyword, timeout,
follow-redirects, and TLS-failure classification all documented; any
config fixes recorded.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Controller asks user to run the audit.**

Controller surfaces the `<TO_FILL>` placeholders to the user with a single message asking the user to log into BetterStack and report back. Controller then commits the filled-in version on the same branch as a follow-up commit (NOT amend — the audit findings warrant a distinct commit for traceability).

- [ ] **Step 5: Controller commits the filled-in audit (after user reports back).**

```bash
# After user reports BetterStack settings:
# Edit docs/observability.md, replace each <TO_FILL: ...> with the user's findings
# and the implementer's audit-section-template commit message.
git add docs/observability.md
git commit -m "docs(observability): probe-coverage audit — record BetterStack findings (Tier 1 OpSafety PR2)

User-supplied audit findings:
- Probe URL: <findings>
- Status / body / timeout / redirects / TLS classification: <findings>
- Config fixes made: <findings>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.4: Open PR2

- [ ] **Step 1: Push branch.**

```bash
git push -u origin feature/opsafety-tier1-pr2
```

- [ ] **Step 2: Open PR.**

```bash
gh pr create --base main --head feature/opsafety-tier1-pr2 \
  --title "feat(landing): status banner + probe-coverage audit (Tier 1 OpSafety PR2)" \
  --body "$(cat <<'BODY'
## Summary

Tier 1 OpSafety hardening PR2 — the infrastructure piece. Adds an auto-rendered banner to \`graider.live\` that links to \`status.graider.live\` whenever BetterStack reports non-operational, plus a checked-in probe-coverage audit verifying BetterStack correctly detects the 2026-05-19 incident class.

## Spec correction

The spec assumed \`landing/\` was a React project. Reality is vanilla HTML/CSS/JS. Plan and implementation use vanilla JS with \`node:test\` for unit tests (zero dependency, Node 20+ built-in). Behavior, failure modes, and integration points are unchanged from the spec.

## Files changed

- \`landing/status-banner.js\` (created) — pure-logic \`shouldShowBanner(statusJSON)\` function + browser-only IIFE that fetches \`https://status.graider.live/api/v1/status.json\` on \`DOMContentLoaded\`, renders the banner when banner-on conditions match, fails-open on any error.
- \`landing/status-banner.test.js\` (created) — 16 unit tests via \`node:test\`. Run with \`cd landing && node --test status-banner.test.js\`. Covers the 4 BetterStack status states, monitor-degraded, incident-active-with-monitor-operational, resolved-only, and 8 fails-open edge cases.
- \`landing/index.html\` (modified) — adds \`<div id=\"status-banner\" hidden></div>\` right after \`<body>\` and \`<script src=\"status-banner.js\"></script>\` near the existing \`script.js\` tag.
- \`landing/styles.css\` (modified) — appends banner styles (yellow/orange sticky, dismissible × button, mobile responsive).
- \`docs/observability.md\` (modified) — appends \"Probe-coverage audit (2026-05-21)\" section with BetterStack monitor configuration findings, any config fixes made via the dashboard, and verification scope.

## Verification

- \`cd landing && node --test status-banner.test.js\` → tests 16, pass 16, fail 0.
- Manual smoke against \`python3 -m http.server\` confirms \`index.html\` serves the \`#status-banner\` div and \`status-banner.js\`; a stub-fetch test page confirms the rendering path and the dismiss-via-sessionStorage behavior.
- Probe-coverage audit recorded in \`docs/observability.md\` with the user-supplied BetterStack monitor findings.

## Deploy note

The landing deploys with \`cd landing && npx vercel --prod\` (per CLAUDE.md). Merging this PR does NOT auto-deploy the landing — the deploy is an explicit CLI step. Run it after merge.

## What stays out of scope

- Tier 2 items (data-safety boundary documentation, graceful-degrade mode). Deferred.
- Tier 3 items (multi-PaaS active-active, direct cloud migration). Deferred per trigger conditions in the assessment doc.
- Frontend error tracking. Separate brainstorm.
- SSL/domain expiry monitoring. BetterStack paid feature, deferred.
- Provider re-evaluation. The 2026-05-19 incident dated section concluded Railway is the right provider at this stage.

## Plan + spec

- Plan: \`docs/superpowers/plans/2026-05-21-opsafety-tier1.md\`
- Spec: \`docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md\`

## Closes

Closes the OpSafety roadmap gap from PR #434 (\"2026-05-19 Production incident: Railway edge outage (GCP-side) and OpSafety hardening roadmap\").

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

- [ ] **Step 3: Arm auto-merge.**

```bash
gh pr merge --squash --auto
```

- [ ] **Step 4: Background-watch the merge.**

Same pattern as Task 1.3 Step 4. Once merged, capture sha and clean up local branch.

- [ ] **Step 5: Deploy the landing post-merge.**

```bash
cd /Users/alexc/Downloads/Graider/landing
npx vercel --prod
```

Verify the deploy URL serves the new `#status-banner` div: `curl -sS https://graider.live/ | grep -c 'id="status-banner"'` → expected: 1.

---

## Task 3: Slice closeout

**Files:** Modify `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md`. Modify `docs/superpowers/plans/2026-05-21-opsafety-tier1.md`. Modify `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.

- [ ] **Step 1: Branch.**

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull origin main && git checkout -b docs/opsafety-tier1-closeout
```

- [ ] **Step 2: STATUS-stamp the spec.**

Edit `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md`. After the existing `**Status:** OPEN` line near the top, change to:

```
**Status:** CLOSED 2026-05-2X — shipped via PR1 (#XXX: railway-down runbook + customer comms templates) and PR2 (#YYY: status-banner.js + probe-coverage audit).
```

Re-derive PR numbers from `gh pr list --state merged --limit 5 --search "OpSafety Tier 1"` or from the merge commit messages on main.

- [ ] **Step 3: STATUS-stamp the plan.**

Edit `docs/superpowers/plans/2026-05-21-opsafety-tier1.md`. Add a line after `**Goal:**`:

```
**STATUS: CLOSED 2026-05-2X** — shipped via PR1 (#XXX) and PR2 (#YYY). Tier 1 OpSafety roadmap gap from the 2026-05-19 PR #434 dated section closed: customers reach a working status page on `graider.live`, the on-call has a checked-in Railway-down runbook plus pre-drafted comms templates, and the BetterStack `/healthz` probe coverage is audited and documented.
```

- [ ] **Step 4: Append a dated section to the assessment doc.**

Edit `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`. Append at the very end of the file:

```markdown

---

# 2026-05-2X Tier 1 OpSafety hardening closeout (PR #XXX + PR #YYY)

The deferred Tier 1 implementation the 2026-05-19 production incident dated section named as the first thing to ship before resuming pure architectural decomposition.

## What shipped

- **`docs/runbooks/railway-down.md`** (PR1 #XXX) — 5 sections: confirm it's Railway (curl/openssl/dig/status.railway.app), decision tree, escalation thresholds (30 min / 2 hr / multi-hour), what NOT to do, post-incident.
- **`docs/runbooks/customer-comms-templates.md`** (PR1 #XXX) — 3 templates: Slack `#alerts`, customer email for school admins on multi-hour outages only, reference to the auto-rendered in-app banner.
- **`landing/status-banner.js`** + **`landing/status-banner.test.js`** (PR2 #YYY) — vanilla JS module fetching `https://status.graider.live/api/v1/status.json` on each landing page-load with a 3 s timeout, rendering a sticky yellow/orange dismissible banner when BetterStack reports non-operational. Fails-open on any error. 16 `node:test` unit tests covering the 4 BetterStack status states, monitor-degraded, incident-active edge cases, and 8 fails-open shapes.
- **`landing/index.html` + `landing/styles.css`** (PR2 #YYY) — banner container + sticky CSS + dismiss button.
- **`docs/observability.md` — "Probe-coverage audit (2026-05-21)" section** (PR2 #YYY) — verified BetterStack `/healthz` probe configuration: probe URL is the custom domain `app.graider.live/healthz` (not Railway-internal), TLS-handshake failure correctly classified as "down," and any config fixes recorded in the section.

## Spec correction recorded

The original 2026-05-19 PR #434 OpSafety roadmap listed "off-Railway status page" and "external uptime monitor" as Tier 1 items, but the BetterStack stack (Uptime + Status Page + Slack alerts + iOS Critical Alerts) already shipped on 2026-04-11 per `docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md`. The actual remaining gap was narrower: customers had no path from broken `app.graider.live` to the working `status.graider.live`, and the 2026-05-19 diagnosis sequence + comms templates were not captured anywhere durable. The "marketing-site banner" item that the PR #434 roadmap labeled Tier 2 is promoted to Tier 1 in this slice's spec because the incident verified it as the missing piece of customer trust.

## Out of scope (recorded explicitly)

- Tier 2 items (data-safety boundary documentation, graceful-degrade mode). Stay deferred.
- Tier 3 items (multi-PaaS active-active, direct cloud migration). Stay deferred per the trigger conditions in the assessment doc's 2026-05-19 section.
- Frontend error tracking — known gap in `docs/observability.md` follow-ups. Separate brainstorm.
- SSL / domain expiry monitoring. BetterStack paid feature, deferred per existing observability doc.
- Provider re-evaluation. The 2026-05-19 incident dated section concluded Railway is the right provider at this stage; not re-litigated.

## Mechanical asserts

Two PRs shipped (PR1 docs-only, PR2 infrastructure). 9 CI checks green on both. \`node --test status-banner.test.js\` returns 16 passed, 0 failed. The probe-coverage audit section in `docs/observability.md` is filled in with the user-supplied BetterStack monitor findings. The landing is deployed via `cd landing && npx vercel --prod` post-merge; the deployed `index.html` serves the `#status-banner` div (verifiable with `curl -sS https://graider.live/ | grep -c 'id="status-banner"'`).

## Next concrete step

Either: (a) post-slice 3-model reconciled re-score (Task 4 of the plan, optional) weighing whether Operational Safety moves 9 → 10 given Tier 1 closure, or (b) the third Architecture-7 ground (no dependency injection) brainstorm, which was named as the dominant remaining Architecture lever by the 2026-05-21 Post-Slice-5 re-score.
```

Replace each `XX` / `XXX` / `YYY` with the actual dates and PR numbers from main's history.

- [ ] **Step 5: Commit + push + open closeout PR + auto-merge.**

```bash
git add docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md docs/superpowers/plans/2026-05-21-opsafety-tier1.md docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md
git commit -m "docs: close Tier 1 OpSafety hardening (PR1 + PR2); 3-model re-score follows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin docs/opsafety-tier1-closeout
gh pr create --base main --head docs/opsafety-tier1-closeout \
  --title "docs: close Tier 1 OpSafety hardening (PR1 + PR2 stamped + dated section in assessment)" \
  --body "Slice closeout for Tier 1 OpSafety hardening. STATUS-CLOSED stamps on the spec and plan; appends dated section to docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md recording what shipped and what stays out of scope.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --squash --auto
```

---

## Task 4: Post-slice 3-model reconciled re-score (optional, controller judgment)

This task is optional and lives outside the mechanical implementation slice. It is run by the controller after Task 3 closeout merges, only if the controller judges the Operational Safety dimension move (9 → 10) worth the model time.

- [ ] **Step 1: Read the prior reconciled baseline** from `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` "# 2026-05-21 Post-Slice-5 3-Model Reconciled Re-Score" (the most recent reconciled scorecard). Confirm the baseline Operational Safety 9.

- [ ] **Step 2: Dispatch three independent re-scorers in parallel.** Claude via `Agent(general-purpose, opus)`, Codex via `Agent(codex:codex-rescue)`, Gemini via `gemini -m gemini-2.5-pro -p @/tmp/gemini_prompt.md` with `GEMINI_CLI_TRUST_WORKSPACE=true`. Each gets the same prompt: scope = Tier 1 OpSafety shipped (banner + runbook + comms + probe audit); decisive question = does Operational Safety move 9 → 10 now that the customer-facing gap the 2026-05-19 incident verified is closed? Conservative-floor reconciliation; failed-to-run is NOT failed-low (2026-05-09 Clever precedent).

- [ ] **Step 3: Reconcile.** Splits resolve down. A tier bump to 10 requires the boundary closed (not the symptom) and concrete in-code grounds from at least 2 of 3 completed assessments plus controller first-hand verification.

- [ ] **Step 4: Append a dated section to the assessment doc.** Format matches the prior 3-model dated sections (table + per-dimension reconciled rationale + biggest remaining lever + honest meta-notes). Then open a docs PR, arm auto-merge, watch the merge.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| §1 Goal | Plan goal + all tasks |
| §2 Scope correction vs PR #434 roadmap | Recorded in the plan header note + Task 3 dated section |
| §3 Architecture (the ASCII diagram) | Implemented across Task 1.1 (runbook), Task 1.2 (comms), Task 2.1 (banner pure logic), Task 2.2 (banner DOM mount + HTML + CSS), Task 2.3 (probe audit) |
| §4.1 Marketing-site banner | Task 2.1 + Task 2.2 |
| §4.2 Railway-down runbook | Task 1.1 |
| §4.3 Customer comms templates | Task 1.2 |
| §4.4 Probe-coverage audit | Task 2.3 |
| §5 Sequencing (2 PRs) | PR1 (Task 1.1–1.3), PR2 (Task 2.1–2.4) |
| §6 Data flow | Implemented across all tasks; documented in the runbook + the inline status-banner.js comments |
| §7 Error handling table | Implemented: banner fails-open in shouldShowBanner + IIFE; runbook documents incident handling; comms templates have tone-calibration notes |
| §8 Out of scope | Recorded in PR2's PR body, Task 3 dated section, and the spec section |
| §9 Success criteria | Task 1.3 + Task 2.4 (CI green + deploy step) + Task 3 (closeout dated section); Task 4 is the optional re-score |
| §10 Risks | Vercel runtime fetch latency mitigated by 3s timeout + failing-open; vendor JSON shape change mitigated by defensive parsing in `shouldShowBanner`; probe-audit fix-during-quiet-window noted in Task 2.3's instructions; staleness mitigated by Quarterly review note in the templates |
| §11 Approval | This plan is the next step after spec approval |

**2. Placeholder scan:**

- One TBD-style content section: Task 2.3 Step 2's audit-section TEMPLATE contains `<TO_FILL: ...>` placeholders, but these are documented as user-supplied audit findings (the audit cannot be performed by an implementer subagent — it needs BetterStack dashboard access). The plan explicitly flags this as the audit's required-human-input step, with the placeholders filled in by the controller in Step 5 after the user reports back. This is NOT a plan failure — it's a documented hand-off point — and the alternative (have the implementer guess the BetterStack config) would be a real plan failure.
- All other tasks have concrete code blocks, exact commands, and exact paths.
- No "implement later," "fill in details," "add appropriate error handling," "similar to Task N" patterns found.

**3. Type consistency:**

- `shouldShowBanner(statusJSON)` signature consistent across Task 2.1 (definition), Task 2.2 (consumer in the IIFE), Task 2.1 tests.
- `STATUS_URL`, `FETCH_TIMEOUT_MS`, `ACTIVE_INCIDENT_STATES` constants defined once in `status-banner.js` and referenced from the IIFE.
- CommonJS export from Task 2.1 enables Task 2.1's `require('./status-banner.js')` in the test file; the IIFE in Task 2.2 is a no-op in Node so doesn't break the export contract.
- `#status-banner` container id consistent across `status-banner.js` IIFE (`document.getElementById('status-banner')`), `landing/index.html` (the `<div id="status-banner">`), `landing/styles.css` (`#status-banner.visible`).
- `graider:status-banner-dismissed` sessionStorage key used consistently in the dismiss handler and the on-load dismissal check.

**4. Bite-sized task granularity:** Each numbered step is 2-5 minutes of work (write a small block of code or run one command). Tasks are 4-6 steps each; PR-level tasks are 4 steps (push, open, auto-merge, watch).

**5. Frequent commits:** PR1 has 2 commits (one per file). PR2 has 3 commits in the implementer's scope (pure logic + tests, then DOM mount + HTML + CSS, then audit-section template) and 1 follow-up commit by the controller (filled-in audit findings). Task 3 closeout is 1 commit.

**6. Hand-off points:** Task 2.3 has an explicit controller-asks-user hand-off (BetterStack credentials not available to the subagent). All other tasks are mechanical and dispatch-safe to a fresh implementer subagent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-opsafety-tier1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Controller dispatches a fresh subagent per task, reviews between tasks (spec-compliance + code-quality two-stage), fast iteration. Task 2.3 has an explicit user-input hand-off for the BetterStack audit.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

Which approach?
