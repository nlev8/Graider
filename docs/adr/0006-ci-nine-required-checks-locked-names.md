# ADR 0006 — CI: nine named required status checks; job names locked to branch protection

- **Status:** Accepted
- **Date recorded:** 2026-06-10 (decision built up via the cicd-pipeline plan; E2E promoted 2026-05-11)

## Context

`main` auto-deploys to Railway on merge, so a bad merge is a bad deploy.
Direct pushes to `main` are blocked; the only gate between a PR and
production is the required-status-check set. GitHub branch protection
references status checks **by exact job name**, which couples workflow YAML
to repo settings.

## Decision

1. **Nine required checks gate every merge to `main`** (verified via
   `gh api repos/nlev8/Graider/branches/main/protection/required_status_checks`):
   Backend Tests (`--cov-fail-under=70`), Frontend Build (build + test-count
   floor + no committed `backend/static`), Frontend E2E Smoke (Playwright
   health-check against a locally-spawned backend), Migrations Smoke
   (Alembic against raw `postgres:15-alpine`), Lockfile Drift Check
   (pip-compile parity), Ruff Lint, Mypy Strict (Critical Modules) — all in
   `.github/workflows/ci.yml` — plus Bandit SAST and Secret Scan
   (trufflehog, verified only, PR diff) in
   `.github/workflows/security-scan.yml`.
2. **Job names are locked:** renaming a job without updating the branch
   protection rule blocks all merges (the stale name never reports). Any
   rename must update both sides together.
3. **Checks are promoted, not born required:** new jobs start additive /
   non-required (or `continue-on-error`) and are marked required only after
   a proven green streak — e.g. Frontend E2E Smoke was promoted on
   2026-05-11 after 15 consecutive green runs. Marking a job required is an
   explicit admin step, separate from merging the workflow change.
4. **Emergency bypass exists but is exceptional:** repo admins can merge
   without CI (when `enforce_admins` is false), only for critical hotfixes,
   with CI fixed immediately after.

## Consequences

- Every PR pays the full nine-check cost; in exchange, local verification
  discipline (`.claude/rules/workflow.md`) exists to catch failures before
  the slow CI round-trip — CI is the final net, not the first.
- Coverage-floor bumps follow a rule (raise only when measured global is
  ≥0.5% above the new floor) so the floor never flaps.
- Additive workflow jobs (like the Docs Drift Check, ADR-adjacent to this
  one) can merge without touching branch protection, then be promoted.

## Consequences for contributors

Never rename the nine jobs casually; see CLAUDE.md "CI job names are locked"
and `docs/superpowers/plans/2026-04-02-cicd-pipeline.md` Task 3 for the
protection-rule update command.

## Evidence

- `.github/workflows/ci.yml` (7 jobs), `.github/workflows/security-scan.yml`
  (Bandit SAST, Secret Scan)
- `CLAUDE.md` § "CI/CD Pipeline" (the nine checks, lock warning, bypass rule)
- `docs/ARCHITECTURE.md` § 9
