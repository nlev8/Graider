# Handoff: 2026-05-22 — three slices shipped, clean stopping point

This session ran from a production incident (Railway/GCP edge outage) through three complete architecture-decomposition slices. Everything is shipped and merged; nothing is mid-flight. Written for a fresh `/clear` session per CLAUDE.md §12 (clean handoff beats `/compact` when starting a new topic). The next agent should read this first, then `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (the canonical scorecard + every dated closeout section).

## 1. Goal

Decompose Graider's biggest-lever Architecture and Code-Quality concentrated complexity via repeated brainstorm → spec → plan → subagent-driven slices, each behavior-preserving under a characterization net, with post-slice 3-model reconciled re-scores, all CI-green and merged. This session closed the dual-path consolidation, shipped Tier 1 operational-safety hardening, and addressed the dependency-injection ground at the repository seam.

## 2. TL;DR

- **Production incident resolved.** A 2026-05-19 Railway/GCP edge outage (Google blocked Railway's GCP account) was diagnosed (TLS-layer, not app-layer) and recovered. Five hotfixes (#438–#442) made the app resilient to a degraded Redis: `/healthz` soft-dep contract, flask-limiter + flask-session startup probes that fall back to `memory://`/filesystem when Redis is unreachable, and `Retry(NoBackoff(), 0)` to stop redis-py's hang loop. Prod verified back (200s on `/` and `/healthz`).
- **Slice 5 (dual-path completion) shipped** — #443 (PR1 additive: `PublishedContentRepository` + `find_existing_submission` + route char-net) + #444 (PR2 rewire + #431 fold-in). Issue #431 closed. Post-slice re-score (#445): Architecture **7 → 8**, Overall ~8.1.
- **Slice 6 (Tier 1 OpSafety) shipped** — #446 (spec/plan) + #447 (railway-down runbook + customer comms templates) + #448 (graider.live status banner + deferred probe audit) + #449 (closeout). The BetterStack stack already existed; the real gap was the customer path from broken app → working status page, now closed by the banner.
- **Slice 7 (DI provider) shipped** — #450 (spec) + #451 (spec-refinement + plan, race-recovery) + #452 (PR1 provider + factory `sb=_UNSET` evolution) + #453 (PR2 failure-seam migration + falsifiable char-net split + ergonomics proof) + #454 (closeout). DI addressed at the repository seam; honest framing: seam-level, not codebase-wide.
- **No DI re-score run** (deliberate). Predictable "holds Architecture at 8" — seam-level DI is live and the testability win is demonstrated, but the ~80 other `get_supabase()` sites still acquire deps directly. The judgment is recorded in the DI closeout dated section instead of burning a 3-model dispatch.

## 3. Current state

### main HEAD
- `751123d` (#454 DI closeout). `git log --oneline origin/main -6` shows #454→#449 in order.
- Full backend suite: **5155 passed, 14 skipped, 1 known network flake** (`test_openai_chat_uses_breaker`; passes in isolation in ~19s — sibling of the anthropic/gemini breaker flakes). GitNexus index refreshed to `a369606`, embeddings 11211 preserved.

### Shipped this session (all merged)
| PRs | What |
|---|---|
| #438–#442 | Production incident hotfixes (Redis resilience) |
| #443, #444, #445 | Slice 5 dual-path completion + re-score |
| #446, #447, #448, #449 | Slice 6 Tier 1 OpSafety |
| #450, #451, #452, #453, #454 | Slice 7 DI provider |

### New durable code/docs
- `backend/providers.py` — the DI provider (get_supabase_provider / get_submission_repository / get_published_content_repository / override_supabase). 11 unit tests in `tests/test_providers.py`.
- `repository_for(path_type, sb=_UNSET)` + `published_content_repository_for(path_type, sb=_UNSET)` — default-resolve via provider when omitted; sentinel distinguishes omitted from explicit-None.
- `docs/runbooks/railway-down.md` + `docs/runbooks/customer-comms-templates.md`.
- `landing/status-banner.js` + `landing/status-banner.test.js` (vanilla JS, node:test) + banner wired into `landing/index.html` + `landing/styles.css`.
- `docs/observability.md` — appended a deferred probe-coverage audit section.
- `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` — dated closeout sections for all three slices + the Slice 5 re-score + the 2026-05-19 incident.

## 4. Open loops (BOTH require the user — an agent cannot do them)

1. **Deploy the OpSafety landing banner.** It's merged but NOT live: the landing deploys via an explicit `cd landing && npx vercel --prod` (needs Vercel auth). Until then `graider.live` does not show the status banner. Verify after: `curl -sS https://graider.live/ | grep -c 'id="status-banner"'` → expect `1`.
2. **OpSafety probe-coverage audit** — deferred to the next quarterly alert drill (first Monday of Jul 2026). Needs BetterStack dashboard access. The 6 config fields to verify are listed as a checklist in `docs/observability.md` ("Probe-coverage audit" section). The probe DID fire correctly on 2026-05-19, so this is a "verify the why," not a blocker.

## 5. What changed scope mid-flight (so the next agent doesn't re-derive)

- **OpSafety scope correction:** the PR #434 roadmap listed "off-Railway status page" + "external uptime monitor" as Tier 1, but BetterStack (Uptime + Status Page at status.graider.live + Slack + iOS Critical Alerts) already shipped 2026-04-11. The real Tier 1 gap was the marketing-site banner (originally labeled Tier 2) + the runbook + comms templates. Don't rebuild the BetterStack stack — it exists.
- **DI scope refinement (planning-time audit):** the call-site migration is narrower than the spec first assumed. (a) The char net pinned call-count at the `if sb:` guards — migrating makes `repository_for` fire even with a None client (repo no-ops via its own guard; observable effect identical), so ~2 TestFailureSeam tests were updated from call-count to falsifiable observable-effect assertions. (b) `submit_student_work` uses `get_supabase_or_raise` (raise-vs-None vs the provider's `get_supabase`) — deferred. (c) Dual-use sites (`sb` used for both repo + direct `db.table` queries) double-acquire — deferred. Only the clean repo-only `get_supabase`-based failure seams migrated.
- **`landing/` is vanilla HTML/CSS/JS, NOT React.** The OpSafety spec assumed React; the plan corrected to vanilla JS + `node:test`. Any future landing work: it's plain `index.html` + `script.js` + `styles.css`, no build step beyond Vercel.

## 6. Recommended next lever (ranked)

1. **PlannerTab.jsx decomposition** (RECOMMENDED) — `frontend/src/tabs/PlannerTab.jsx` (~7,405 LOC), the largest raw file, named across re-scores as the distinct Code-Quality concentrated-complexity lever (separate from the Architecture-tier work). A different kind of slice (frontend, no Celery/char-net coupling).

   **IMPORTANT — this is NOT greenfield; it's an in-progress multi-wave refactor (scouted 2026-05-22, deferred to a fresh session for the heavy analysis):**
   - Existing plan: `docs/superpowers/plans/2026-05-04-planner-tab-extraction.md` (went through 3 Codex review rounds). Read it first.
   - **Wave 1** (PR 1–7, PRs #193–#203): extracted the inline Planner JSX out of `App.jsx` into `PlannerTab.jsx` + decentralized ~91 Planner-only `useState` pairs out of App.
   - **Wave 2** (PR 7a–7e, 8a–8d, PRs #199–#207): extracted clusters *out of* `PlannerTab.jsx` into `frontend/src/components/` (AttemptDrawer, ShareWithClasses, NewUnit+tag, matching, doc-upload, preview, lesson-gen) — these are the imports at the top of PlannerTab.jsx.
   - **Despite both waves it's still 7,405 LOC / 75 useState / 6 useEffect / ~20 handlers / a ~6,100-line JSX return (line 1275 → end) with deeply nested conditional sub-renders.** That's how huge it started (~5,943 LOC inline originally).
   - **The next slice's first job (do this FRESH, with full context budget):** identify the largest cohesive clusters STILL inline in PlannerTab.jsx (by line count + cohesion) that haven't been extracted by waves 1+2, pick one as the v1 extraction target, and brainstorm THAT cluster's extraction. Don't redesign the whole decomposition — continue the established cluster-extraction cadence (extract one cluster → component or hook, prove via Vite build + frontend test count floor + Playwright E2E smoke, no behavior change).
   - Frontend "no behavior change" proof = Vite build succeeds + frontend test count ≥ floor (Frontend Build CI check) + Playwright `health-check.spec.js` E2E smoke. There is no backend-style char-net; the prior PlannerTab PRs relied on Codex parity review + the test suite (currently ~160+ frontend tests; `frontend/src/__tests__/PlannerTab.test.jsx` exists).
   - Begin with `superpowers:brainstorming`, but the brainstorm should be SHORT — the decomposition strategy is already designed in the 2026-05-04 plan; the open question is just "which remaining inline cluster is next."
2. **Broader DI conversion** — what would actually move Architecture 8 → 9 codebase-wide: the dual-use sites + `submit_student_work` + the 6 duplicate `_get_supabase()` defs + progressively the ~80 other `get_supabase()` call sites + AI clients + config. Multi-slice; each its own spec/plan. The provider seam from this session is the foundation.
3. **Physical two-table consolidation** — the deferred dual-path end-state (`submissions`+`student_submissions`, `published_assessments`+`published_content`). Deliberately deferred for FERPA-data-safety reasons; needs its own design + migration. Highest blast radius.

## 7. Concrete next step

Start a fresh session: `/clear`, then "read handoff.md first." Then invoke `superpowers:brainstorming` for the PlannerTab.jsx decomposition (or whichever lever above the user picks). The established cadence: brainstorm (3-model consult on genuine design forks) → spec → writing-plans → subagent-driven-development with two-stage review (spec-compliance then code-quality) per task → closeout dated section → optional 3-model re-score.

Standing constraints (from CLAUDE.md + this session): venv at `/Users/alexc/Downloads/Graider/venv/`; pytest always `--ignore=tests/load`; never contact `:3000`; all changes via PR (9 CI checks); commit trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`; PR body trailer `🤖 Generated with [Claude Code](https://claude.com/claude-code)`; skip em-dash sweeps on internal docs (humanizer was for pitch decks); active frontend is `frontend/src/App.jsx` (never edit `graider_app.py` for UI); landing is vanilla JS on Vercel.

## 8. Disproved / ruled-out this session (don't re-try)

- **Reverting recent merges during the prod incident** — ruled out fast: the failure was a TLS handshake rejection (connection never reached Flask), which a code regression cannot cause. Reflexive revert would have done nothing.
- **`flask.g`/`current_app`-based DI** — ruled out: the Celery/thread grading paths run outside Flask request context (`backend/supabase_client_scoped.py` documents this). The DI provider must be context-independent; that's why it's plain module functions + contextvars.
- **A DI library (punq/dependency-injector)** — considered (Gemini leaned this way) and ruled out for v1: adds a runtime dependency + learning curve for a single-dev team, identical testability outcome to the hand-rolled provider. Revisit only if a re-score says the hand-rolled provider doesn't retire the objection.
- **Running the DI re-score** — skipped deliberately (predictable hold-at-8); not a gap, a judgment recorded in the closeout.

## 9. References

- Assessment doc (canonical): `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`
- Slice specs/plans: `docs/superpowers/specs/2026-05-19-dual-path-completion-design.md` + plan; `docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md` + plan; `docs/superpowers/specs/2026-05-22-di-provider-design.md` + plan (`docs/superpowers/plans/2026-05-22-di-provider.md`).
- Observability runbook: `docs/observability.md`. Incident runbook: `docs/runbooks/railway-down.md`.
- PRs this session: #438–#454. All merged. Pre-existing OPEN PRs (#367, #115, #103, #90, #42, #40) are NOT from this session and were not touched — leave for the user to triage.
- Stale local branches (chore/*, ci/*, docs/*) are pre-existing, not from this session.
