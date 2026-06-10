# ADR 0004 — Rate limiting: Redis required in prod (fail-fast), startup probe + bounded retries

- **Status:** Accepted (shaped by two production incidents)
- **Date recorded:** 2026-06-10 (decisions: Phase 4.6 and 2026-05-20 hotfix #5)

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
   (~2 s, zero retries). Reachable → use Redis. Unreachable → fall back to
   `memory://` for the entire process lifetime, logged loudly — the limiter
   never talks to broken Redis at request time, so workers cannot hang in
   its retry loop (2026-05-20 hotfix #5).
3. **Bounded request-time options:** when Redis was reachable at startup,
   pass `socket_timeout=2.0` / `retry(NoBackoff, retries=0)` as
   `storage_options`, so a *later* outage raises fast and
   `in_memory_fallback_enabled` degrades per-request instead of hanging.

The load-bearing distinction: **config-missing fails closed (refuse to
boot); transient outage fails open (degraded per-worker limits, app keeps
serving students)**. These are different failure classes and get opposite
treatments deliberately.

## Consequences

- Operators must set `REDIS_URL` on every production web service; local dev
  (`FLASK_ENV=development`) is exempt.
- During a Redis outage, rate limits are per-worker (bypassable) — accepted
  as better than refusing service to students mid-class. Recovery requires a
  worker restart if the outage spanned startup (the `memory://` choice is
  for the process lifetime).
- The hardening rubric's Security anchors treat the startup-probe
  `memory://` fallback as the reason this dimension sits at 7 (a level-8
  criterion is "no silent memory:// fallback") — the trade-off is recorded
  here as deliberate, with the 2026-05-19 hang as the justification.

## Evidence

- `backend/extensions.py` (header comments narrate both incidents and all
  three layers; the `RuntimeError` text cites Phase 4.6)
- Hardening anchors: `docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md` § 1
