# Adversarial Re-Score Brief — Graider Hardening Dimensions (2026-06-02)

You are re-scoring the Graider codebase across 10 hardening dimensions. The repo
root is `/Users/alexc/Downloads/Graider`. **Verify every claim yourself with your
own shell commands against the LIVE code — do not trust the scorecard below.**

## Your stance: ADVERSARIAL / SHREWD, NOT OPTIMISTIC
The current scores were produced by a prior 3-model process that may have drifted
optimistic. Your job is to find **concrete file:line evidence that JUSTIFIES
LOWERING each score.** Default to skepticism. Do NOT credit anything you cannot
verify with a command. A score is only as high as the evidence you can personally
confirm. If you cannot verify a claimed improvement, treat the dimension as if it
does not have it.

## Current scorecard you are critiquing (claimed reconciled, ~2026-05-25)
| Dimension | Claimed |
|---|--:|
| Security | 8 |
| Error Handling | 8 |
| Code Quality | 9.5 |
| Architecture | 8 |
| Test Coverage | 8 |
| Documentation | 8 |
| Debugging/Observability | 8 |
| Data Integrity | 9 |
| Operational Safety | 9 |
| Clever Compliance | 10 |
| **Overall** | **~8.5** |

## What to actually check (examples — go beyond these)
- **Security 8:** grep `PUBLIC_PREFIXES` in `backend/auth.py` — does it still expose
  broad route subtrees? Are there `except` blocks leaking exception strings in
  responses (`backend/routes/planner_routes.py`)? Path traversal on download
  endpoints? Is rate limiting actually shared across workers (Redis) or in-memory?
- **Error Handling 8:** count broad `except Exception` / `except: pass` that don't
  log or re-raise. Is `handle_route_errors` actually applied, or just defined?
- **Code Quality 9.5:** verify the LOC claims (`wc -l` on `backend/services/grading_pipeline.py`,
  `assignment_grader.py`, `frontend/src/App.jsx`, `frontend/src/tabs/*.jsx`,
  `backend/routes/*.py`). Was complexity ELIMINATED or RELOCATED into sibling
  files that are themselves large? Are there god-FUNCTIONS remaining inside the
  "decomposed" files (`grade_assignment`, `grade_multipass`)? Is 9.5 defensible
  when App.jsx and other files are still 2k–5k LOC?
- **Architecture 8:** is there ANY dependency injection, or do call sites still
  acquire deps via in-function imports / module-level `get_supabase()`? Is the
  dual publish path consolidated at the SCHEMA level or only the code boundary?
  Two physical table families still exist?
- **Test Coverage 8:** what is the REAL measured coverage? Read the CI floor in
  `.github/workflows/ci.yml` (`--cov-fail-under`). Run a coverage sample if you
  can. Is e2e a real suite or a smoke set with conditional skips?
- **Documentation 8:** does `docs/API_REFERENCE.md` exist and match the real route
  count? Blank/truncated cells? Is `docs/ARCHITECTURE.md` accurate to the hosted
  reality?
- **Debugging/Observability 8:** structured logging + request IDs real? Sentry
  wired? Metrics/OTel present or absent? Is the audit log still file-first (lost
  on redeploy)?
- **Data Integrity 9:** is the dedup UNIQUE constraint actually in a migration
  (`backend/migrations/` or alembic versions)? Forward-only gaps? Orphan cascade?
- **Operational Safety 9:** migrations discipline (how many real migrations?),
  feature flags (exist?), rollback story beyond Railway auto-deploy, post-deploy
  smoke gate? Off-Railway status page / external uptime monitor — shipped or not?
- **Clever Compliance 10:** is a 10 genuinely defensible, or is there residual
  (multi-district token write path, duplicate-student handling)? Note: a related
  Clever→UUID identity parity change shipped recently (PR #617) — verify it didn't
  introduce regressions.

## Output format (REQUIRED — end your run with exactly this)
```
RESCORE_TABLE
Security: <n> | <one-line disconfirming evidence with file:line>
Error Handling: <n> | <evidence>
Code Quality: <n> | <evidence>
Architecture: <n> | <evidence>
Test Coverage: <n> | <evidence>
Documentation: <n> | <evidence>
Debugging/Observability: <n> | <evidence>
Data Integrity: <n> | <evidence>
Operational Safety: <n> | <evidence>
Clever Compliance: <n> | <evidence>
OVERALL: <n>
BIGGEST_OPTIMISM: <the one score you think is most inflated vs reality, and why>
```
Scores may be decimals (e.g. 7.5). Be willing to LOWER scores you can't justify.
