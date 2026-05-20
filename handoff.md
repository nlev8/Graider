# Handoff: 2026-05-19 evening / 2026-05-20 early UTC

Long session covering Tier 2 Slice 3 (app.py route god-module extraction), Tier 2 Slice 4 (dual publish-path consolidation), the post-slice 3-model re-scores, and an ongoing production incident (Railway edge outage caused by Google Cloud blocking Railway's GCP account). Two follow-up brainstorms are queued. Written per CLAUDE.md §12 because the session is long, there is an unresolved prod incident, and a `/compact` is likely.

## 1. Goal

Decompose Graider's biggest-lever Code Quality and Architecture concentrated complexity via repeated brainstorm → spec → plan → subagent-driven slices, each verbatim under a characterization net with zero behavior change, post-slice 3-model reconciled re-scores, all CI-green and merged. Sub-goal active tonight: the dual publish-path consolidation lever closed; OpSafety hardening roadmap recorded; next lever queued behind your design approval. Sub-goal blocked tonight: a production outage caused by Railway's GCP-side incident, waiting on Railway recovery.

## 2. TL;DR

- **Production is down.** `app.graider.live/healthz` returns Railway's edge 404 placeholder, and the cert served is the default `*.up.railway.app` wildcard. Root cause: Google Cloud blocked Railway's GCP account (status.railway.app Major Outage from 22:29 UTC 2026-05-19, ongoing past 01:34 UTC 2026-05-20, no ETA). **Recovery is upstream-bound. Do nothing on our side until Railway is back.**
- **Tier 2 Slice 4 (dual publish-path consolidation) is fully shipped and CI-green.** Four PRs merged tonight: #429 spec+plan, #430 PR1 (`SubmissionRepository` + char net, additive), #432 PR2 (rewire pipeline onto the repository), #433 post-slice 3-model reconciled re-score (Architecture held 7, Overall 8.0). Full suite 5115 passed / 0 failed.
- **PR #434 is open** with the recorded follow-up artifact in `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`: 2026-05-19 production incident plus OpSafety hardening Tier 1/2/3 roadmap. Auto-merge armed.
- **Four follow-up issues open** (each with fix sketch + repro): #423 (pre-existing latent NameError in grading paths), #426 (dead-shadowed roster routes), #431 (post-PR2 cleanup tail: unify on_failure write + retire 2 dead char-net-pinned helpers + rename supabase_table params), and the implicit "Tier 1 OpSafety hardening" recorded in PR #434.
- **Two brainstorms queued, gated on (a) prod recovery and (b) your design approval at the brainstorming HARD-GATE.** First in priority: Tier 1 OpSafety hardening (off-Railway status page + runbook + external uptime monitor + customer comms template). Second in priority: next architectural lever (dual-path code-boundary completion / system-wide DI / PlannerTab.jsx decomposition / cleanup tail). You explicitly asked to brainstorm OpSafety hardening with Claude + Codex + Gemini; design forks will use 3-model consultation, mechanical implementation Claude-only.

## 3. Current state

### Code state on `main`

- HEAD `1f1031c` (PR #433 merge, the post-dual-path re-score).
- `backend/app.py` 585 LOC (post Slice 3); only SPA/static factory-shell routes remain.
- `backend/services/portal_grading.py` routes submission-row I/O through `SubmissionRepository`; zero `supabase_table` string dispatch remains (grep gate green).
- `backend/services/submission_repository.py` is live and load-bearing (`SubmissionPathType` enum, ABC, two adapters, `repository_for` factory).
- Full suite 5115 passed / 0 failed; ruff clean.

### Branches and PRs

- **PR #434 OPEN** on `docs/opsafety-incident-2026-05-19`: the OpSafety incident + hardening roadmap doc section. Auto-merge armed; waiting on the 9 CI checks.
- All other code branches from tonight are merged (#424/#425/#427/#428 for Slice 3; #429/#430/#432/#433 for Slice 4).

### Follow-up issues filed

| # | Title | Class |
|---|---|---|
| #423 | save_results / grade_with_parallel_detection latent NameError | Pre-existing latent bug, faithfully preserved by Slice 3 verbatim moves, not a regression |
| #426 | Dead-shadowed roster routes | Pre-existing dead code, faithfully preserved by Slice 3 PR3 verbatim move |
| #431 | Post-PR2 dual-path cleanup tail | Three transitional residuals from the dual-path PR2 rewire (on_failure write unification, retire 2 dead char-net-pinned helpers, rename supabase_table params); requires mutating pinned char-net assertions which the PR2 contract forbade |

### Production incident state

- Slack alert at roughly 22:00 UTC 2026-05-19 said `app.graider.live/healthz` is down.
- Root cause: Google Cloud blocked Railway's GCP account, breaking Railway's GCP-hosted control plane and custom-domain routing.
- Last status.railway.app update read: 01:34 UTC 2026-05-20 ("recovered our compute on Google Cloud, but services are unable to start because of ongoing networking issues on Google Cloud's side. We are engaged with Google Cloud support to resolve this. ... gradual recovery on Railway metal workloads. To ensure things remain stable as we ramp back up, we are temporarily throttling all non-enterprise builds.").
- Two Railway edge Request IDs captured: `hEiwsGzBS0Gv6ZYlozsQ6Q` (initial), `tYn-Df0BRxuVzufTGbGh5g` (later attempt). Useful only if Railway customer support is engaged.
- Slack comms template was drafted in-session and given to the user to paste into the alerting channel. It explicitly says do not roll back PRs #430/#432/#433.

## 4. Local repro

Each of these is a single shell command, read-only, safe to run from a fresh agent.

### Verify production is down (TLS-layer failure, not application failure)

```bash
curl -sS -m 10 -o /tmp/healthz_body -w "HTTP %{http_code} | total %{time_total}s\n" https://app.graider.live/healthz
# Expected during incident: libcurl SSL error 51 ("SSL peer cert or SSH remote key was not OK").
# Expected after recovery: HTTP 200, JSON body with health status.

openssl s_client -connect app.graider.live:443 -servername app.graider.live -showcerts </dev/null 2>&1 | head -30
# Expected during incident: leaf cert subject=CN=*.up.railway.app, SAN=DNS:*.up.railway.app only (default Railway wildcard, wrong cert for our hostname).
# Expected after recovery: leaf subject and SAN both include app.graider.live.

dig +short app.graider.live A
# Expected throughout: 66.33.22.209 (Railway edge POP). DNS is correct; the gap is between DNS and Railway's project-domain mapping.
```

### Verify the local repo state

```bash
cd /Users/alexc/Downloads/Graider
git log --oneline -8 origin/main
# Expected top: 1f1031c docs(assessment): post-dual-path 3-model reconciled re-score (Architecture held 7, Overall 8.0) (#433)
# Then in order: 6767d3e dual-path PR2, 370f08c dual-path PR1, 130e574 dual-path spec/plan, 6c40246 post-Slice-3 re-score, d54ee8e Slice 3 PR3 + closeout, 4bb82e3 Slice 3 PR2, 9d0ffc8 Slice 3 PR1.

source venv/bin/activate
python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -5
# Expected: 5115 passed, 14 skipped, 0 failed (the post-Slice-4 baseline). If this drops, something landed that wasn't covered tonight.

grep -nE "supabase_table ==|table_name=supabase_table|supabase_table=\"(submissions|student_submissions)\"" backend/services/portal_grading.py
# Expected: EMPTY (the dual-path string dispatch is eliminated from the grading pipeline; this is the PR2 grep gate, recorded in tests/test_dual_path_consolidation_char.py::test_no_supabase_table_string_dispatch_remains).

gh pr view 434 --json state,mergedAt -q '.state + " @ " + (.mergedAt // "open")'
# Expected: MERGED if CI cleared (docs PR, no risk); OPEN if the 9 checks are still running.
```

### Verify Railway recovery before any dashboard action

```bash
curl -I https://app.graider.live/healthz
# If HTTP 200: prod recovered, domain config survived the outage, no further action needed.
# If still HTTP 404 / cert mismatch persists 30 min after Railway status flips to Monitoring / Resolved: the outage left the registration in a bad state, re-add app.graider.live in Railway dashboard (see section 7 below).
```

## 5. Disproved hypotheses (and other paths considered, ruled out)

- **"Recent code merges (#430/#432/#433) caused prod-down."** Ruled out within minutes of triage: the failure mode is a TLS handshake rejection (the connection never reached Flask), not an HTTP 5xx. The openssl probe showed the wrong cert served at the edge. A code regression cannot cause this class of failure. Reflexive revert would have done nothing useful and was explicitly recommended against in the Slack template.
- **"TLS cert expired."** Ruled out by openssl: notBefore 2026-04-05, notAfter 2026-07-04, Verify return code 0. The cert is valid; it is just the wrong cert for our hostname (SAN list is `*.up.railway.app` only, no `app.graider.live` entry).
- **"DNS misconfigured."** Ruled out by dig: app.graider.live CNAME chain resolves correctly to a Railway edge POP. The gap is at the Railway project-domain mapping, not at DNS.
- **"Custom domain genuinely lost from Railway, re-add it now."** Was the first plan after the openssl probe pointed at a Railway-side domain-registration gap. ABANDONED once the user found status.railway.app showing a Major Outage with the GCP account block: re-adding the domain mid-outage risks stuck pending cert state, duplicate registrations, or failed Let's Encrypt provisioning while the edge plane is degraded. Hold position until Railway recovers; then if the domain is still missing in the dashboard, re-add it.
- **"Open a Railway customer support ticket."** Ruled out: Railway has identified the root cause, escalated to Google Cloud, and is actively working with GCP support. A customer ticket adds backlog without changing the outcome. Reserved for if Railway goes silent past 03:34 UTC (the 2-hour-silence threshold) without further status updates.
- **"Reactive provider migration off Railway."** Considered and ruled out as reliability theater: every PaaS competitor has lived analogous multi-hour outages; provider choice rotates which incidents we are exposed to, it does not eliminate the class. Trigger conditions for genuine re-evaluation are recorded in the PR #434 doc section (3+ multi-hour outages in 6 months, SLA contract demand, scale outgrowing pricing, blocking feature need).

## 6. Most likely remaining causes (ranked, for the prod incident specifically)

Not "what is causing the symptom" (we know: GCP blocked Railway's account), but ranked by what may still go wrong from here:

1. **Railway recovers and `app.graider.live` works automatically.** Most likely. The domain config probably survived server-side; the dashboard just could not render it correctly during the outage. After full Railway recovery, re-test with `curl -I https://app.graider.live/healthz`. If 200, done.
2. **Railway recovers but our custom domain remains unregistered.** Possible: the outage may have damaged the registration state. In that case, re-add `app.graider.live` in the Railway dashboard. DNS is already correct (per dig); cert provisioning takes 30 to 90 seconds.
3. **Railway recovers but its build queue stays throttled when we next need to deploy.** Non-enterprise builds were explicitly throttled during ramp-back. Deploys may be slow for several hours after the status page flips to Resolved. Not a concern unless you need to ship a hotfix.
4. **Railway's GCP-side issue escalates and stays unresolved past dawn UTC.** Then the customer ticket and Tier 3 re-evaluation conversations become real. Currently below threshold.

## 7. Concrete next step

In priority order. **None of these run until Railway is back unless explicitly marked otherwise.**

### When Railway recovers

1. **Verify prod is back.** `curl -I https://app.graider.live/healthz` returns 200. `openssl s_client -connect app.graider.live:443 -servername app.graider.live </dev/null 2>&1 | grep -E "subject|SAN"` shows app.graider.live in the cert SAN.
2. **If the custom domain shows missing in Railway dashboard after recovery:** Settings → Networking → Custom Domains → Add `app.graider.live`. Railway returns a CNAME target; confirm it matches `ar90ys35.up.railway.app` (what DNS already points to). If yes, do nothing on DNS. Wait 30 to 90 seconds for cert provisioning; status badge goes Pending → Active.
3. **Slack the alerting channel** that prod is back, root cause was upstream (Railway plus GCP), no Graider code was at fault, no rollback occurred. Use the in-session Slack template plus an "all clear" addendum.

### Already in flight (runs independent of prod state)

4. **PR #434 merge.** GitHub Actions CI runs on GitHub's runners (Railway-independent); the docs PR should merge whenever the 9 checks clear regardless of Railway state. Verify with `gh pr view 434 --json state,mergedAt`.

### Queued brainstorms (gated on prod recovery + your design approval at the brainstorming HARD-GATE)

5. **Tier 1 OpSafety hardening brainstorm.** Off-Railway status page (Statuspage / Instatus / Cachet / GitHub Pages static, design fork, 3-model consultation), external uptime monitor (UptimeRobot / BetterStack / Healthchecks.io, design fork, 3-model consultation), "Railway down" runbook (capture tonight's diagnosis sequence + decision tree + Slack template), customer comms template. Invoke `superpowers:brainstorming` with the controller framing "Claude + superpowers + Codex + Gemini": Claude drives the brainstorm and writing-plans, Codex and Gemini consulted at the genuine design forks (provider picks, v1 scope vs Tier 2 deferral). Recorded in PR #434 doc section.
6. **Next architectural lever decision (deferred from before the incident).** The post-dual-path re-score named two tier-gating items: (a) finish the dual-path consolidation outside the write layer (routes plus published_* read split plus #431 cleanup) and (b) system-wide dependency injection. PlannerTab.jsx is the separate Code Quality lever. The cleanup tail (#423/#426/#431) is the small-PR alternative. Your last message before the incident asked for clarification on these options; the AskUserQuestion was interrupted and the answer never came. Resume after Tier 1 OpSafety ships, since Tier 1 hardening is the right next thing anyway.

## 8. References

- PR #424 (Slice 3 PR1 grading_results_routes), #425 (Slice 3 PR2 ferpa_routes), #427 (Slice 3 PR3 roster_routes + closeout), #428 (post-Slice-3 re-score), #429 (dual-path spec+plan), #430 (dual-path PR1 SubmissionRepository), #432 (dual-path PR2 rewire), #433 (post-dual-path re-score). All merged.
- PR #434 (this session's OpSafety incident doc section). Open with auto-merge armed.
- Issues #423, #426, #431. Open follow-ups with fix sketches.
- Plan docs: `docs/superpowers/plans/2026-05-19-app-routes-extraction.md` (Slice 3, CLOSED), `docs/superpowers/plans/2026-05-19-dual-publish-path-consolidation.md` (Slice 4, CLOSED).
- Spec docs: `docs/superpowers/specs/2026-05-19-app-routes-extraction-design.md`, `docs/superpowers/specs/2026-05-19-dual-publish-path-consolidation-design.md`.
- Assessment doc: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`. Latest dated sections: post-Slice-3 re-score (HEAD `d54ee8e`), 2026-05-19 Tier 2 Slice 4 closeout, post-dual-path re-score (HEAD `6767d3e`), 2026-05-19 production incident + OpSafety hardening roadmap (this PR #434 once merged).
- Railway status incident IDs: 22:29 UTC 2026-05-19 Major Outage on Edge Network; root cause identified 23:37 UTC ("Google Cloud has blocked our account"); ongoing past 01:34 UTC 2026-05-20.
- Railway edge Request IDs captured tonight: `hEiwsGzBS0Gv6ZYlozsQ6Q`, `tYn-Df0BRxuVzufTGbGh5g`.

## Honest meta-note

Per CLAUDE.md §12, this handoff should have been maintained throughout the session, not written at the end after the user prompted. I did not maintain it as we went; the user's question "are you documenting the session with claude mem in case we have to compact?" correctly flagged the gap. Writing it now closes that gap so a `/compact` or fresh session can resume cleanly. Claude-mem captures the conversation passively (no active action needed; the session log JSONL is the durable transcript and observations surface to future sessions automatically per the SessionStart message); handoff.md is the active artifact that captures the open threads and decisions cleanly enough for a fresh agent to pick up without re-deriving context. Both are useful; they serve different purposes.
