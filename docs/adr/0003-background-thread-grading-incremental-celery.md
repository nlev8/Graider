# ADR 0003 — In-process background-thread grading, migrated incrementally to Celery per path

- **Status:** Accepted (retrospective record; migration in progress — Phase 4.1b pending)
- **Date recorded:** 2026-06-10 (decisions span the project history through Phase 4.1)

## Context

Grading a class set calls LLM APIs dozens of times and can run for minutes.
Blocking a Flask route for that long is not acceptable (gunicorn worker
starvation, client timeouts). The original deployment was a single process
with no broker available, so the cheapest correct primitive was a daemon
`threading.Thread` plus a shared in-memory state dict polled by the frontend
(500 ms polling; see CLAUDE.md "Performance Notes").

As hosted load grew, in-process threads showed their limits for the
*student-facing* path: a thread dies with its worker (deploys/restarts lose
in-flight grading), and there is no retry or time-limit machinery.

## Decision

1. **Teacher-initiated grading runs in a background thread in the web
   process** (`backend/grading/thread.py` → `backend/grading/pipeline.py`),
   with status in `backend/grading/state.py` polled by the dashboard.
2. **Student portal grading migrates to Celery path-by-path, not big-bang:**
   - Join-code submissions: Celery is the always-on primary path
     (Phase 4.1 PR3; the `CELERY_PORTAL_GRADING` flag gate was removed after
     a 48h post-flip monitor window closed green). Task:
     `backend/tasks/grading_tasks.py` (`PortalGradingTask`, soft/hard time
     limits at 14/15 min).
   - Class-based submissions: still thread-backed
     (`backend/routes/student_account_routes.py`); migration is Phase 4.1b.
3. **Broker outage degrades, never drops:** if the Celery enqueue raises a
   known broker-communication failure (`kombu.exceptions.OperationalError`
   / `kombu.exceptions.ConnectionError` — only those, never bare
   `Exception`), the route falls back to the legacy thread spawn so the
   student does not lose their submission. The fallback is Sentry-tagged
   (`celery_enqueue_failure`).

## Consequences

- Teacher dashboard grading survives with zero infrastructure beyond the web
  process; the cost is that a deploy mid-run abandons the run (acceptable —
  the teacher re-runs; no student data is lost).
- The Celery worker is a separate Railway service sharing `nixpacks.toml`
  (hence `SKIP_FRONTEND_BUILD=true` on the worker — see ADR 0005) and fails
  fast if `CELERY_BROKER_URL` is unset (`backend/celery_app.py`).
- The enqueue-fallback means join-code grading has *two* execution
  substrates; the wire contract (`SubmissionPathType.*.value` strings, the
  8-arg `run_portal_grading_thread` signature) is load-bearing for both and
  for `PortalGradingTask.on_failure`.

## Evidence

- `backend/grading/thread.py`, `backend/grading/pipeline.py`,
  `backend/grading/state.py` (Phase 3a extraction docstrings)
- `backend/routes/student_portal_routes.py` (Phase 4.1 PR3 comment: Celery
  primary, flag gate removed; kombu-only fallback rationale)
- `backend/tasks/grading_tasks.py`, `backend/celery_app.py`
- `CLAUDE.md` § "Performance Notes" (thread + 500 ms polling)
