# Hardening Sprint — push the verified 7.5 toward ~8.4 (2026-06-09)

> **Goal:** raise the mechanical rubric score from the re-verified **7.5** to
> ~**8.4** via the highest-leverage level-8/9 items, plus two cheap regression
> locks. NOT a chase for 10 — the true-10 exclusions from the 2026-06-02 plan
> (external pen-test, full DI re-arch, 90% + mutation, schema property tests,
> chaos/DR, multi-provider cert) remain out unless a contract demands them.
>
> Scored against `docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md`
> per its own procedure: every number below cites command output collected
> 2026-06-09 (subagent sweep, raw outputs in the session transcript).

## Re-score 2026-06-09 (mechanical, evidence-backed)

| Dimension | 2026-06-03 (#639) | 2026-06-09 | Evidence for the move |
|---|--:|--:|---|
| Security | 7 | **8** | str(e)-to-client 4→0 + guard test (`test_no_exception_leak_in_responses.py`); limiter raises without `REDIS_URL` in prod (`extensions.py:19-25`); CSP/HSTS (`app.py:98,113`); `test_public_prefix_auth.py` |
| Error Handling | 7.5 | **7** | Honest correction: anchor grep counts **53** silent `except…: pass` (69 on Jun 2; level 8 needs <10). #639's +0.5 doesn't survive the partial-credit rule (1 of 4 level-8 criteria) |
| Code Quality | 6→7 (campaign) | **7** | Largest file 2,954 (AnalyticsTab); App.jsx 2,931; largest function ~295 def-to-def. Level 8 fails: 3 files >2,500, ~26 functions 200–295 |
| Architecture | 7 | **7** | 0 DI-library hits; 91 `get_supabase()`; dual table families (15/14 files). `providers.py` seam exists but isn't injection |
| Test Coverage | 6 | **6.5** | Floor 70 + measured 70.5% (2 of 3 level-7 criteria → +0.5). Pre-merge e2e still 1 smoke spec; 111 conditional `test.skip(` masks |
| Documentation | 8 | **8** | 0 blank Purpose cells; 308 documented vs 315 live (≈2.2%) |
| Observability | 7 | **7.5** | Audit DB-insert failures capture+warn (`utils/audit.py:177-209`); missing-DSN warns loudly outside dev. 0 metrics/tracing → not 8 |
| Data Integrity | 7.5 | **7.5** | Unchanged: `0001` pass-stamp + 1 real DDL |
| Operational Safety | 7.5 | **7.5** | `post-deploy-smoke.yml` verifies deployed build SHA; BetterStack uptime + status.graider.live. Feature flags still 0 → not 8 |
| SSO/Roster | 9 | **9\*** | \* In-repo evidence says "production-ready **for** certification", not certified. **Operator action: confirm cert status in the Clever dashboard.** If not granted, this is 7.5 and overall is ~7.35 |
| **OVERALL** | 7.25 | **7.5** | Unweighted mean per the rubric |

## Reconciliation (2026-06-09, post-Codex adversarial audit) — corrected overall: **7.05**

A Codex high-effort adversarial audit of the table above disputed 5 dimensions.
Each dispute was settled by re-running commands, not by vote. Corrections and
the **binding interpretation rulings** (so the next re-score is deterministic):

| Dimension | Above | **Corrected** | Ruling |
|---|--:|--:|---|
| Security | 8 | **7** | Level 8 says "fails **closed**" — the loud `memory://` fallback when the startup Redis **probe** fails (`extensions.py:95-106`) is fail-open for the process lifetime. The "no *silent* fallback" parenthetical is an example, not the bar. (Codex's "caps at 4: bandit red" was a misread — it quoted bandit's *confidence* histogram; severity HIGH = 0, Medium = 7, verified via `bandit -f json`.) |
| Code Quality | 7 | **6** | "No function >300 LOC" applies to ALL source files FE+BE per the rubric header. `SettingsClassroom.jsx:6` is a 2,307-line component function. (Backend is clean: AST true-span scan finds **0** functions >300 — Codex's `get_missing_assignments: 329` was a def-to-def span artifact.) |
| Test Coverage | 6.5 | **6** | The level-7 line is TWO criteria (coverage floor+measured; e2e). 1 of 2 is not a strict majority → no +0.5. Codex's upgrade to 7 is also rejected: the 111 `test.skip(!joinCode)` masks sit in the very specs nightly runs, violating "no silent-skip masking" (same ruling as #639). |
| Observability | 7.5 | **7** | "Error tracking active in prod" is not repo-verifiable (Sentry still disables when DSN unset; DSN presence is external state). Evidence rule: unverifiable ≠ met → 1 of 3 level-8 criteria → no +0.5. |
| SSO/Roster | 9\* | **7.5\*** | The anchors' own evidence rule decides: `CLEVER_COMPLIANCE_STATUS.md` proves "production-ready **for** certification", not a granted cert. **Reverts to 9 the moment an operator confirms the cert in the Clever dashboard.** |

**Corrected mean: 7+7+6+7+6+8+7+7.5+7.5+7.5 = 70.5/10 = 7.05** (7.2 if
Clever cert is confirmed). Note this also implies June 3's 7.25 was ~0.2
optimistic (its EH 7.5 and SSO 9 don't survive the same strictness).

**Sprint impact:** PR1 gains a sub-item — make the limiter startup probe
failure fail-closed in prod (exit non-zero, not memory:// fallback), closing
the Security level-8 gap properly. CQ 7 additionally requires splitting the
giant FE component functions (`SettingsClassroom` 2,307 LOC; audit
`AnalyticsTab`/`ResultsTab` for the same pattern) — fold into the existing CQ
campaign. Revised projection for this sprint as listed: **~7.6–7.75**;
reaching ~8 additionally needs the FE component splits.

## Re-score 2026-06-11 (sprint COMPLETE, mechanical) — overall: **7.6** (7.75 on Clever-cert confirmation)

All seven sprint items are now merged: PR1 #724, PR2 #735 (ruff E722+BLE001
lock), PR3 #725, PR4 #736 (/metrics), PR5 #740 (e2e de-skip wave 1 +
`Frontend E2E Extended` job, first CI run green 8m52s), PR6 #739
(silent-swallow sweep 49→9 + ratchet guard), PR7 #738 (real Alembic baseline,
live-introspected). Commands re-run 2026-06-11 against `main` @ 9b1cbde;
binding rulings applied; two new scoring notes from the sprint's opus reviews
incorporated (DI "down intentionally N/A"; TC factual-basis change).

| Dimension | 2026-06-10 | 2026-06-11 | Evidence for the move |
|---|--:|--:|---|
| Security | 9 | **9** | Unchanged (level-10 still blocked: bandit baseline waivers, no threat model/pen-test). |
| Error Handling | 7 | **7.5** | Anchor grep silent swallows = **9** (was 49; level-8 needs <10 ✓) with ratchet guard `tests/test_no_silent_swallows.py` (ceiling 9); 0 str(e) [CAP ✓]; ~325 decorations/303 routes ✓. Fourth level-8 criterion ("every broad except logs or captures") still fails: ~43 `returns fallback` BLE001 sites are justified-but-unlogged → 3/4 = strict majority → +0.5, not 8. Path to 8: log the returns-fallback class (or amend the criterion reading). |
| Code Quality | 6 | **6** | Unchanged: `SettingsClassroom.jsx` 2,307-line component function binds; AnalyticsTab 2,954 / App.jsx 2,931. |
| Architecture | 7 | **7** | Unchanged: DI hits = 0. |
| Test Coverage | 6 | **7** | Level-7 criteria now BOTH met: floor 70 + measured ≥70 (CI green); **PR CI runs 6 real e2e specs** (smoke + 5 promoted via `Frontend E2E Extended`) **with no silent-skip masking in any spec CI runs** — 0 `test.skip(` in the promoted five, enforced by a CI guard step (also catching only/fixme). The 2026-06-09 Reconciliation rejection of TC 7 was decided when CI ran ONLY the smoke spec and the ≥5 real specs existed solely in masked nightly files — that factual basis no longer holds; the 49 remaining masks live in nightly-only specs outside CI's gate, which is wave-2 scope. Level 8 fails (floor/measured <80; 49 conditional skips repo-wide) → no further credit. |
| Documentation | 9 | **9** | Unchanged. |
| Observability | 7 | **7.5** | Metrics layer now present: `/metrics` Prometheus text endpoint + request instrumentation (#736; anchor grep `opentelemetry|prometheus|statsd|metrics_` = 2 hits, was 0). Audit durably persisted (insert failures capture+warn, per 06-09 evidence). 2 of 3 level-8 criteria → +0.5; "error tracking active in prod" remains repo-unverifiable (binding ruling) → not 8. |
| Data Integrity | 7.5 | **7.5** | Same number, transformed basis (#738): 0001 is now a REAL live-introspected baseline (16 `CREATE TABLE IF NOT EXISTS`, FKs/UNIQUEs/CHECKs/indexes/RLS versioned), up-tested in CI (Migrations Smoke + 15 bootstrap tests). Only level-8 sub-clause unmet: "down tested in CI" — `downgrade()` is intentionally `NotImplementedError` (reversing a baseline = full schema drop; per #738's opus review: credit as "level 8-minus", do NOT record a clean 8). Strict majority of level 8 → +0.5 stands on a much stronger basis. |
| Operational Safety | 8 | **8** | Unchanged (level 9 needs canary/auto-rollback/on-call). |
| SSO/Roster | 7.5\* | **7.5\*** | Ruling stands; reverts to 9 on operator cert confirmation in the Clever dashboard. |
| **OVERALL** | 7.4 | **7.6** | 9+7.5+6+7+9+7+7.5+7.5+8+7.5 = 76.0/10. **7.75 if Clever cert confirms.** |

**Worklist implied:** EH 7.5→8 = log the ~43 returns-fallback sites; TC 7→8 =
floor/measured 80 + de-mask the remaining 49 (e2e wave 2); Obs 7.5→8 = make
prod error-tracking repo-verifiable (e.g. a healthz field or boot assertion);
DI literal-8 = downgrade coverage for post-baseline migrations; CQ 6→7 = FE
component-function splits (SettingsClassroom et al.) — now the single biggest
drag. Sec/Doc/OpSafety are at their practical ceilings short of
threat-model/pen-test, generated docs, and canary infra.

## Re-score 2026-06-10 (post-Wave-1, mechanical) — overall: **7.4** (7.55 on Clever-cert confirmation)

Wave 1 (#724–#727) + follow-ups (#729 ADR amendment, #730 dep-bump retiring all
8 CVE waivers, #732 audit-trail test isolation, #733 docs sync) merged and
deployed 2026-06-10; the two new CI jobs were **promoted to required** the same
day (11 required checks, verified via `gh api`). All verification commands
re-run 2026-06-10 evening against `main` @ 1c9d80c; binding interpretation
rulings from the Reconciliation section applied unchanged.

| Dimension | 7.05 (reconciled) | 2026-06-10 | Evidence for the move |
|---|--:|--:|---|
| Security | 7 | **9** | Level 8 now fully met: str(e)-to-client = **0**; limiter startup probe **fails closed** in prod (`extensions.py:58` "in PRODUCTION: raise RuntimeError" — #727, closing the exact Reconciliation gap; verified live: image ba60d21 booted with `/healthz` redis ok). Level 9 all three met: dep-CVE scan gating CI as a **required** check (#724 + same-day promotion); path-traversal regression tests (`tests/test_document_generator_path_traversal.py`, `tests/test_security.py`); CSP/HSTS (`app.py:98,113`). Level 10 fails: no threat model; bandit baseline is a non-zero waiver ledger (pip-audit ledger IS zero after #730); no pen-test → 0/3, no partial. Bandit severity (json, per the ruling's method): HIGH=0, MEDIUM=3 (was 7). |
| Error Handling | 7 | **7** | Unchanged: anchor grep counts **53** silent `except…: pass`; 0 str(e) [CAP met] but 2/4 level-8 criteria is not a strict majority. PR2/PR6 remain the path to 8. |
| Code Quality | 6 | **6** | Unchanged per ruling: `SettingsClassroom.jsx` 2,307-line component function binds "no function >300 (FE+BE)". Largest files: AnalyticsTab 2,954 / App.jsx 2,931 / assistant_tools_reports.py 2,723. |
| Architecture | 7 | **7** | Unchanged: DI hits = 0; `get_supabase()` = 91; dual table families 15/14 files. |
| Test Coverage | 6 | **6** | Unchanged per ruling: floor 70 + measured ≥70 (CI green) but pre-merge e2e is still the single smoke spec and the 111 `test.skip(` masks persist → 1 of 2 level-7 criteria, no +0.5. |
| Documentation | 8 | **9** | Level 9 met (#726): `docs/adr/` (8 evidence-cited ADRs + index) + `docs/MODULES.md` (module map + 3 sequence narratives). Level 10 "docs **generated** and drift-checked in CI" is half-met — `Docs Drift Check` exists and is now REQUIRED (stale docs literally fail the build) but docs are hand-written, not generated → compound criterion not met, no partial. 0 blank Purpose cells; 315 live vs 308 documented = 2.2%. |
| Observability | 7 | **7** | Unchanged per ruling: metrics/tracing layer = 0 grep hits; SENTRY_DSN presence remains repo-unverifiable external state. (Audit-trail integrity hardened by #732 — test fixtures can no longer pollute the prod `audit_log` — but that doesn't move a level-8 criterion.) |
| Data Integrity | 7.5 | **7.5** | Unchanged: 2 migrations, `0001` still a pass-stamp; dedup constraints CI-asserted (+0.5 stands per the anchors note). |
| Operational Safety | 7.5 | **8** | All three level-8 criteria now met: env-backed feature flags adopted on a real risky path (#725, `flag_enabled` / FLAG_CLEVER_ROSTER_SYNC kill switch, 7 grep hits); post-deploy smoke verifies the **deployed** image SHA (`post-deploy-smoke.yml:8,35`); BetterStack uptime + status.graider.live (docs/observability.md). Level 9 (canary/auto-rollback/on-call) not met → no partial. |
| SSO/Roster | 7.5\* | **7.5\*** | Ruling stands: `CLEVER_COMPLIANCE_STATUS.md` proves "ready for cert", not granted. **Reverts to 9 the moment an operator confirms the cert in the Clever partner dashboard** (worth +0.15 overall). Today's live verifications (real Clever teacher login + real ClassLink SSO login on the deployed image) strengthen the evidence base but don't change cert status. |
| **OVERALL** | 7.05 | **7.4** | 9+7+6+7+6+9+7+7.5+8+7.5 = 74.0/10. **7.55 if Clever cert confirms.** |

**Worklist implied by the deltas** (per the anchors' "score moves = worklist" rule):
sprint items PR2/PR6 (EH 7→8, swallows 53→<10), PR5 (TC 6→7, de-skip e2e),
PR4 (Obs 7→8, /metrics), PR7 (DI 7.5→8, real baseline) remain the open
leverage; CQ 6→7 needs the FE component-function splits (SettingsClassroom et
al.). Security and OpSafety have banked their sprint targets; Documentation
overshot (8→9 vs no sprint item).

## The sprint (ordered by leverage-per-effort)

| # | PR | Dimension | Now→Target | Class | Risk |
|--|--|--|--|--|--|
| 1 | Dep-CVE scan gating CI (pip-audit or osv-scanner job) + `npm audit` advisory | Security | 8→8.5 | A (CI only) | low |
| 2 | Ruff `E722`+`BLE001` (bare/broad except) — fix-or-noqa the violations, gate in CI | Error Handling | lock | A/B | low |
| 3 | Env-backed `flag_enabled(name)` + adopt on one risky path | Op Safety | 7.5→8 | B | low |
| 4 | Lightweight `/metrics` (Prometheus text format: request counts/latency/grading-thread gauges) | Observability | 7.5→8 | B | med |
| 5 | E2E de-skip: promote ≥5 nightly specs to PR-gating; replace the 111 `test.skip(!joinCode)` masks with real fixtures | Test Coverage | 6.5→7 | B | med |
| 6 | Silent-swallow sweep 53→<10 (log/capture/re-raise each; guard test) | Error Handling | 7→8 | B | med |
| 7 | Real Alembic baseline generated from the live DB (additive only; no destructive ops) | Data Integrity | 7.5→8 | B | med |

Projected: Security 8.5, EH 8, TC 7, Obs 8, OpSafety 8, DI 8 → mean ≈ **8.35–8.4**
(8.2 if SSO\* downgrades pending cert confirmation).

## Per-PR definition of done

Anchors-doc criteria are the DoD; each PR is its own branch with TDD, full
`pytest -q --ignore=tests/load`, cross-cutting test grep, SIS-pin scan
(items 2/6 touch many files — pin scan is mandatory), and Class B review where
marked. Re-run the dimension's verify commands in the PR body as evidence.

- **PR1:** a required CI job fails on a known-vulnerable pin (prove with a
  deliberately old dep in a scratch branch, then revert); document the waiver
  process. Note: the Bandit baseline (`.bandit-baseline.json`, 34 KB) is a
  waiver ledger — burning it down is a stretch goal, not a gate.
- **PR2:** `ruff check` with E722/BLE001 green repo-wide; every `noqa` carries a
  justification comment. This is the regression lock for PR6 — land before it.
- **PR3:** `flag_enabled()` reads env (`FLAG_<NAME>`), defaults false, unit-tested;
  one real risky path gated (candidate: the Clever background roster sync).
- **PR4:** `/metrics` exposes request count/latency histograms + grading-queue
  gauges; scrape-format test; no auth bypass (metrics endpoint must not leak PII).
- **PR5:** `ci.yml` runs ≥5 real specs as required checks 15 consecutive green
  runs before flipping required (mirror the E2E-smoke promotion playbook from
  2026-05-11); 0 conditional skips in promoted specs.
- **PR6:** anchor grep ≤10 with every survivor justified inline; guard test
  asserting the count doesn't regrow (complements PR2's lint rule).
- **PR7:** baseline autogenerated against live schema; `alembic upgrade head`
  from empty DB in CI reproduces it; **scope guard:** additive only.

## Out of scope (unchanged true-10 exclusions + deferred heavies)

External pen-test; mutation testing / 90% coverage; chaos/DR; full DI +
unified physical schema (Architecture 7→8 deferred — `providers.py` is the
seam to build on when we do); CQ 7→8 (3 files >2,500 + 26 functions >200 —
its own campaign, the CQ7 pattern applies); dual-schema consolidation;
ClassLink cert. Revisit when a contract or the post-Volusia roadmap demands.

## Open operator items

1. **Clever certification status** — check the Clever partner dashboard; the
   repo only proves "ready for cert". Worth ±0.15 overall.
2. Volusia beta timing gates the Clever Secure-Sync rostering work (#716
   dormant) — unrelated to this sprint but shares the SSO dimension.
