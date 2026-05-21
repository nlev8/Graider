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
