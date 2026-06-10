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
