# ADR 0004 — Rate limiting: Redis required in prod (fail-fast), startup probe + bounded retries

- **Status:** Accepted (shaped by two production incidents; amended 2026-06-10 by PR #727)
- **Date recorded:** 2026-06-10 (decisions: Phase 4.6, 2026-05-20 hotfix #5, and PR #727)

## Context

`flask-limiter` with in-memory storage keeps a *per-worker* counter. Under
gunicorn with N workers, an advertised "10/min" limit silently becomes
N×10/min, and an attacker cycling connections across workers bypasses it
entirely. The original behavior (warn and continue without Redis) produced
no real enforcement in prod — the warning was noise operators missed.

A second failure mode appeared on 2026-05-19 (Railway/GCP incident): Redis
unreachable *in a way that raised no exception* — redis-py's internal
connection-retry loop hung until gunicorn's worker timeout fired SIGABRT.
`in_memory_fallback_enabled=True` never fired because the storage call never
returned.

## Decision

Three layers in `backend/extensions.py`:

1. **Config-missing is fail-fast:** in production (non-dev `FLASK_ENV`),
   missing `REDIS_URL` raises `RuntimeError` at import. A config error is a
   deploy-time bug and must not boot a silently-unprotected app (Phase 4.6).
2. **Startup probe:** at module import, probe Redis with a bounded connect
   (~2 s, zero retries). Reachable → use Redis. Unreachable in production →
   raise `RuntimeError` at import (fail closed: the deploy aborts and the
   previous image keeps serving — PR #727, amending the original
   `memory://`-for-process-lifetime fallback). Unreachable in dev/test →
   fall back to `memory://`, logged loudly. Either way the limiter never
   talks to broken Redis at request time, so workers cannot hang in
   redis-py's retry loop (2026-05-20 hotfix #5).
3. **Bounded request-time options:** when Redis was reachable at startup,
   pass `socket_timeout=2.0` / `retry(NoBackoff, retries=0)` as
   `storage_options`, so a *later* outage raises fast and
   `in_memory_fallback_enabled` degrades per-request instead of hanging.

The load-bearing distinction (as amended by PR #727): **boot-time failures
fail closed — missing config and unreachable-at-startup both refuse to
boot; a post-boot transient outage fails open (degraded per-worker limits,
app keeps serving students)**. These are different failure classes and get
opposite treatments deliberately: at boot time the previous image is still
serving, so aborting costs nothing and surfaces the problem; mid-class the
only alternative to degradation is refusing service to students.

## Consequences

- Operators must set `REDIS_URL` on every production web service; local dev
  (`FLASK_ENV=development`) is exempt.
- A deploy now fails if Redis is unreachable at boot (PR #727). Before any
  infra change that could break Redis connectivity, confirm the deployed
  service reaches its `REDIS_URL` (e.g. `/healthz` reports `"redis":"ok"`).
- During a *post-boot* Redis outage, rate limits are per-worker
  (bypassable) — accepted as better than refusing service to students
  mid-class. This per-request degradation (layer 3) is unchanged by #727.
- The hardening rubric's Security anchors treated the original
  startup-probe `memory://` fallback as the reason this dimension sat at 7
  (a level-8 criterion is "no silent memory:// fallback") — PR #727 closed
  that gap at startup; the deliberate remaining fail-open surface is the
  post-boot transient-outage path, justified by the 2026-05-19 hang.

## Amendment history

- **2026-06-10, PR #727:** production startup-probe failure changed from
  fail-open (`memory://` for process lifetime) to fail-closed
  (`RuntimeError` at import). Verified live: the first fail-closed image
  (`ba60d21`) booted on Railway with `/healthz` reporting `"redis":"ok"`.
  Dev/test fallback and layer 3 unchanged.

## Evidence

- `backend/extensions.py` (header comments narrate both incidents and all
  three layers; the `RuntimeError` text cites Phase 4.6)
- Hardening anchors: `docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md` § 1
