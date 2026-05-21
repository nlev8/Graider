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
