# Hardening Sprint — push the honest 7.0 toward ~7.9 (2026-06-02)

> **Goal:** raise the mechanical rubric score from ~7.0 to ~7.9 via the
> level-7→8 (and CQ/TC 6→7) items that are safe in one sprint. NOT a chase for
> 10 — the true-10 items (external pen-test, full DI re-arch, 90% coverage +
> mutation, schema property tests, chaos/DR, ClassLink cert) are explicitly out.
>
> **Honest target: ~7.9.** Each item is its own sequenced PR: TDD, full
> `pytest -q --ignore=tests/load` gate, cross-cutting grep, SIS-pin scan, and a
> Class B review where it touches auth/security/data. Verified against the
> anchors in `2026-06-02-hardening-rubric-anchors.md`.

| # | PR | Dimension | Now→Target | Class | Risk |
|--|--|--|--|--|--|
| 1 | Silent-swallow sweep | Error Handling | 7→8 | B | low |
| 2 | Metrics layer + audit-durability + Sentry-always-on | Observability | 7→8 | B | med |
| 3 | Rate-limiter fail-closed + public-prefix auth audit | Security | 7→8 | B | med |
| 4 | Fill API-reference blank cells | Documentation | 7→8 | A | none |
| 5 | Real Alembic schema baseline | Data Integrity | 7.5→8 | B | med |
| 6 | Feature flags + post-deploy smoke gate | Operational Safety | 7→8 | B | med |
| 7 | Tests to ≥70% + raise CI floor + de-skill e2e | Test Coverage | 6→7 | B | low |
| 8 | App.jsx decomposition (under 3,000 LOC) | Code Quality | 6→7 | A | med |

## Per-PR level-8 criteria (from the rubric — the definition of done)

- **PR1 Error Handling 8:** 100% routes via decorator (or listed exempt), 0
  `str(e)`-to-client (done in #631), **<10 silent `except…: pass`**, every broad
  `except` logs or captures. → audit the ~69 swallow sites; add `logger`/Sentry
  to each, or re-raise. Add a guard test (no new silent swallow in backend/).
- **PR2 Observability 8:** structured logs + request_id + Sentry (have) **+ a
  metrics/tracing layer** (add OTel or a lightweight Prometheus `/metrics`),
  audit durably persisted with the DB insert no longer swallowing, Sentry active
  in prod (don't disable when DSN unset — warn once instead).
- **PR3 Security 8:** 0 leaks (done) **+ limiter fails closed in prod** (no silent
  `memory://` fallback when REDIS_URL set-but-unreachable; require REDIS_URL in
  prod) **+ every PUBLIC_PREFIX handler has documented secondary auth** (audit +
  inline comments + a test asserting each prefix's handlers enforce auth).
  **PREREQ: confirm Railway has REDIS_URL set before failing closed.**
- **PR4 Documentation 8:** 0 blank Purpose cells in `docs/API_REFERENCE.md`;
  per-auth-tier column correct; route count within ±5% of live.
- **PR5 Data Integrity 8:** `0001_baseline` expresses the real live schema (not a
  `pass` stamp) — generate from the live DB; FK/constraints versioned; up+down
  tested in CI. **Scope guard:** additive baseline only; no destructive ops on
  live data.
- **PR6 Operational Safety 8:** a feature-flag mechanism (env- or DB-backed,
  `flag_enabled(name)`), used on at least one risky path; a post-deploy smoke
  job that hits the **deployed** `/healthz` + a read endpoint after Railway
  deploy; (status page/uptime monitor noted — external, may stay a follow-up).
- **PR7 Test Coverage 7:** measured ≥70% AND CI floor raised to 70; remove the
  silent `test.skip(!setup)` masks or convert them to real fixtures; CI runs ≥5
  real e2e specs.
- **PR8 Code Quality 7:** no file >3,000 LOC AND no function >300 LOC. `App.jsx`
  4,811 → <3,000 via the proven pure-forward component-extraction pattern (under
  a Vitest characterization harness); confirm `grade_assignment` (405) and
  `grade_multipass` (361) are already <300 (they are post-Wave-8 minus the 405 —
  re-verify; split `grade_assignment` if still >300... it's 405, so it ALSO needs
  a small split to clear 300). Pure moves, behavior-preserving.

## Sequencing rationale
PR1–4 are independent and low/no-risk → land first. PR5 (schema) and PR6 (flags)
are infra. PR7 depends on nothing but is large. PR8 is the largest and riskiest
(frontend god-file) → last. Each merges on green before the next starts.

## Out of scope (the true-10 gold-plating — deliberately NOT attempted)
External pen-test + threat model (Sec 10); typed-exception hierarchy + fault
injection (EH 10); full DI + unified physical schema (Arch 10); 90% + mutation
(TC 10); schema property tests + drift detection (DI 10); canary + auto-rollback
+ chaos/DR (Ops 10); every-file-<1000-LOC (CQ 10); ClassLink cert + webhook
reconciliation (SSO 10). These are weeks of work with diminishing return for a
pre-revenue product — revisit when a contract demands them.
