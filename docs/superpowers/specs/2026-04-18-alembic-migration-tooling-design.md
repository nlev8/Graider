# Alembic Migration Tooling — Design Spec

**Status:** Draft — awaiting Codex cross-check + user approval
**Authors:** Alexander Crionas + Claude Opus 4.7
**Date:** 2026-04-18
**Roadmap phase:** Phase 4 follow-on (infrastructure / operational safety)

---

## Motivation

On 2026-04-18, a drift audit against the live Supabase database revealed
three tables with RLS policies materially different from what the repo
said was deployed. Two policies used `teacher_email = auth.email()` where
the repo expected `teacher_id = auth.uid()::text`, and one blocked all
teacher reads with `USING (false)` where the repo expected a SELECT
policy scoped by class ownership. Reconciling the drift (PR #101) added
eight defensive `DROP POLICY IF EXISTS` statements to the migration
before we could apply it safely.

The root cause is operational, not technical. Graider has no migration
framework. Schema changes are hand-authored SQL files in
`backend/database/`, applied manually via the Supabase SQL Editor. No
replay ordering. No applied-vs-pending state. No CI gate that the files
were run in production in order. Any engineer can paste SQL into
production without committing matching changes — and did, at some point
before we were paying attention.

This spec introduces [Alembic](https://alembic.sqlalchemy.org/) as the
single forward path for schema changes so drift between the repo and
live becomes structurally impossible.

---

## Goals and non-goals

### Goals

- Eliminate schema drift between the repo and live Supabase
- Apply migrations automatically as a Railway pre-deploy step so deploys
  cannot proceed with a schema mismatch
- Enforce a backward-compatible (expand-contract) migration policy so
  rolling deploys never serve old code against a new schema or vice versa
- Freeze the existing raw-SQL migration directory on a named cutoff so
  the historical set stops growing

### Non-goals

- **No SQLAlchemy models, no ORM adoption, no `autogenerate`.** All
  migrations are raw `op.execute(...)` SQL. The Supabase Python client
  remains the sole runtime data-access path.
- **No fresh-DB bootstrap from Alembic alone.** Alembic becomes
  authoritative for forward changes only, not historical reconstruction.
  If a new environment ever needs to be bootstrapped from scratch, that
  is a separate project (rebaseline from live, or maintain a bootstrap
  snapshot).
- **No staging environment or ephemeral envs in this work.** That is a
  separate roadmap item. The CI smoke test described below is the only
  new non-production environment introduced here.
- **No round-trip reversibility testing.** Rollback policy is strictly
  forward-only in production (see § 6).
- **No retrofit of the existing five raw SQL migration files into
  Alembic revisions.** They remain historical artifacts.

---

## Architecture

```
requirements.txt                  +alembic>=1.13,<2
                                  +psycopg[binary]>=3.2,<4
alembic.ini                       new — points at backend/migrations, reads ALEMBIC_DATABASE_URL
backend/migrations/               new directory
  env.py                          reads ALEMBIC_DATABASE_URL, configures the online context
  script.py.mako                  revision template, includes forward-only downgrade() default
  versions/
    0001_baseline_existing_live_schema.py   no-op; records the anchor
backend/database/                 frozen after cutoff
  CUTOFF.md                       documents the freeze date + where to add new migrations
  migration_*.sql                 historical; do not edit
  rollback_*.sql                  historical; do not edit
  verify_*.sql                    historical; do not edit
  supabase_schema.sql             historical; do not edit
railway.json                      +"preDeployCommand": "alembic upgrade head" on web service
.github/workflows/ci.yml          +"Migrations Smoke" job
.env.example                      +ALEMBIC_DATABASE_URL=...
backend/app.py                    no change — does not invoke Alembic at request time
```

The new dependencies are Alembic itself and psycopg 3 (the modern
Postgres driver). We do not add SQLAlchemy as a dependency beyond what
Alembic itself pulls in; no application code imports from
`sqlalchemy`.

---

## Baseline — `0001_baseline_existing_live_schema`

A deliberate no-op revision that records the migration-system anchor
without attempting to replay history:

```python
"""Baseline — existing live schema at Alembic introduction.

This revision does NOT replay the pre-cutoff raw SQL migrations under
backend/database/. It exists only to provide a named anchor for the
Alembic revision graph.

Tradeoff accepted: Alembic becomes authoritative for forward schema
changes only, not for historical reconstruction. If a fresh-environment
bootstrap requirement arises later, we rebaseline then.
"""
revision = "0001_baseline_existing_live_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    raise NotImplementedError("forward-only")
```

**Day-one operator step (once, against live):**

```bash
ALEMBIC_DATABASE_URL=<session-pooler-url> alembic stamp 0001_baseline
```

After that, `alembic current` against live returns this revision, and
future migrations (`0002_...`, `0003_...`) append from here. The Railway
`preDeployCommand` then becomes a no-op on the first deploy after Alembic
is introduced and only does work when a new revision is merged.

---

## Deployment flow

### Railway pre-deploy migration

Update `railway.json` on the web service:

```json
{
  "deploy": {
    "preDeployCommand": "alembic upgrade head",
    "startCommand": "cd backend && gunicorn app:app --bind 0.0.0.0:$PORT",
    "healthcheckPath": "/healthz",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

`preDeployCommand` is Railway's documented hook that runs between
build and deploy. Per
[Railway docs](https://docs.railway.com/deployments/pre-deploy-command):
"if the Pre-Deploy Command fails, the deployment will not proceed."
Combined with `healthcheckPath: "/healthz"`, Railway's deploy lifecycle
waits for readiness on the new container before swapping traffic
([deploys reference](https://docs.railway.com/deployments/healthchecks)),
so a failed migration or a failed healthcheck both keep the old
container serving. The healthcheck path is non-optional for the
traffic-swap guarantee — without it Railway activates the new
deployment as soon as the container starts.

**The worker service does not run migrations.** Only the web service's
`preDeployCommand` invokes Alembic. The worker's `railway.worker.json`
remains untouched. Rationale: the web service has a single container
per deploy that runs the pre-deploy command once; the Celery worker is
prefork concurrency 8 which would race.

### Connection string

A new dedicated env var, `ALEMBIC_DATABASE_URL`, points at the database.
Not reused from any existing variable — Alembic's connection
requirements are different from the Supabase client's.

**Pooler choice:** Supabase's **session pooler** (or direct connection),
NOT the transaction pooler. Three reasons:

1. **Multi-transaction migrations.** Alembic wraps each revision in a
   single DDL transaction by default, but migrations can legitimately
   cross transaction boundaries — `autocommit_block()` for
   autocommit-only DDL (`CREATE INDEX CONCURRENTLY`,
   `ALTER TYPE ... ADD VALUE`), explicit `op.execute("COMMIT")`, or
   `transaction_per_migration=True` in `env.py` for per-revision
   transactions. Transaction pooler (pgbouncer in transaction mode)
   silently releases the connection at each `COMMIT`, so server-side
   session state — statement caches, `SET LOCAL`, session variables —
   evaporates between statements inside a single revision.
2. **Supabase's own recommendation.** Per Supabase database-connection
   docs, direct connection or session pooler is recommended for
   migrations; transaction pooler is recommended only for short
   stateless request/response traffic.
3. **Advisory locks (if we later add them).** Some CI/CD wrappers
   around Alembic add `SELECT pg_advisory_lock(<hash>)` to serialise
   concurrent deploys. Session-mode pooling preserves that; transaction
   mode drops it. We don't use this today, but the choice stays safe
   if we add it later.

(Earlier drafts of this spec attributed the pooler choice primarily to
Alembic's own use of `pg_advisory_lock` — a 2026-04-18 Codex source
review found no such usage in upstream Alembic and the rationale has
been rewritten to the three points above.)

**Direct connection** is acceptable if Railway's IPv6 (or IPv4 add-on)
reaches Supabase without issue; session pooler is the documented
fallback. We do not commit a specific URL — that is operator
configuration.

### CI smoke test

A new GitHub Actions job, `Migrations Smoke`, runs on every PR:

```yaml
migrations-smoke:
  name: Migrations Smoke
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15-alpine
      env:
        POSTGRES_PASSWORD: smoke
      ports: ["5432:5432"]
      options: >-
        --health-cmd pg_isready
        --health-interval 5s
        --health-timeout 5s
        --health-retries 10
  env:
    ALEMBIC_DATABASE_URL: postgresql+psycopg://postgres:smoke@localhost:5432/postgres
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.12", cache: pip }
    - run: pip install -r requirements.txt
    - run: psql "$ALEMBIC_DATABASE_URL" -f .github/ci/supabase_stubs.sql
    - run: alembic upgrade head
    - run: alembic current --verbose
```

`supabase_stubs.sql` (new, committed) creates the minimum Supabase-
flavoured scaffolding. This reuses the existing in-repo pattern from
`tests/test_rls_migration_applies.py` and
`tests/test_schema_tightening_applies.py` (which already do in-process
Postgres smoke tests) plus `auth.email()` for the drift-reconciled
policies:

```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE AS $$ SELECT NULL::uuid; $$;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb; $$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;
CREATE OR REPLACE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;
```

Choice of `uid/jwt/role/email` over `uid/email` alone: existing Graider
schema (e.g. `backend/database/supabase_schema.sql`) uses
`auth.role() = 'service_role'` in service-role policies. Stubbing only
`uid/email` would cause a smoke-test failure the first time someone
reuses that pattern in a new migration. Matching the existing richer
stub keeps future-proofing minimal.

The stubs return NULL, which is correct for a fresh ephemeral DB with
no request context — policies that test `auth.uid() = teacher_id`
simply evaluate FALSE, which is what we want for a schema-validity
smoke test.

**Explicit limitations.**
1. The smoke test cannot catch drift against live. The baseline is a
   no-op; we seed nothing. It verifies only that each new migration
   is a syntactically valid Python file that applies cleanly against
   a fresh ephemeral Postgres.
2. Supabase-specific constructs beyond the stubbed functions (RLS
   evaluator internals, the `realtime` schema, storage, pgsodium,
   `pg_graphql`, etc.) are not available in vanilla Postgres and are
   not stubbed. Migrations that depend on them will fail the smoke
   test even though they'd work against live.
3. If a migration needs a pre-cutoff table that's only defined in
   `backend/database/*.sql` (not in an Alembic revision), the smoke
   test will fail because that SQL is not replayed. This is an
   intentional consequence of the cutoff rule: new migrations should
   not reference tables from the pre-cutoff set without at minimum an
   explicit `op.execute("CREATE TABLE IF NOT EXISTS ...")` guard.

We accept these limitations as the cost of option C (§ Baseline). The
smoke test is defence-in-depth, not the primary gate — Railway's
`preDeployCommand` against real Supabase is the authoritative
verification.

Branch protection is extended (operator action) to require this job
alongside the existing `Backend Tests` + `Frontend Build`.

---

## Forward migration policy

Adopted verbatim from the user's Q4 answer:

> **Policy:** production migrations are forward-only.
> **Convention:** `downgrade()` defaults to `raise NotImplementedError("forward-only")`.
> **Exception:** an author may add a reversible `downgrade()` for local
> iteration, but CI does not rely on it and ops must never use it in
> production.
> **Recovery model:** rollback = code revert plus corrective forward
> migration.

### Expand-contract (backward-compatible) discipline

A migration is classified as either **additive** or **destructive** in
its PR description. This classification controls PR shape, not Alembic
behaviour.

**Additive** (new column, new table, new index, permissive CHECK, new
RLS policy): safe to ship in the same PR as the code that depends on it.
Deploy order:

1. Migration runs during Railway `preDeployCommand`
2. Old container still serving — its code does not reference the new
   thing, so no harm
3. New container starts — its code uses the new thing
4. Traffic swap

**Destructive** (drop column, drop table, rename, narrow CHECK, replace
RLS policy, tighten NOT NULL, drop index that code relies on): **must**
ship as two PRs across two deploys.

1. PR A: remove all code references to the soon-to-be-removed thing.
   Merge + deploy. Live code no longer touches it.
2. PR B: Alembic migration that actually drops/renames/narrows. Merge +
   deploy. Schema catches up.

Data backfills on live tables are treated as destructive (they mutate
existing rows) and ship in their own PR.

### Author responsibilities per PR

Every PR that touches schema must include:

- Exactly one new Alembic revision under `backend/migrations/versions/`
- A `downgrade()` body — either a meaningful dev-only reverse or
  `raise NotImplementedError("forward-only")`
- A PR description classifying the change as additive or destructive,
  with the deploy-order rationale for destructive changes
- The expand-contract invariant: at no point during a rolling deploy may
  old code run against new schema (or vice versa) in a way that breaks
  requests

### Mechanical enforcement — destructive-op CI scan

A new pytest (`tests/test_alembic_destructive_ops.py`) scans every
revision file under `backend/migrations/versions/` for patterns that
indicate destructive operations and fails CI unless the revision
carries an explicit acknowledgment comment:

```python
DESTRUCTIVE_PATTERNS = [
    # Alembic op helpers — schema destruction
    r"op\.drop_column\b",
    r"op\.drop_table\b",
    r"op\.rename_table\b",
    r"op\.drop_constraint\b",
    r"op\.drop_index\b",
    # alter_column tightening: type change or nullable=False
    r"op\.alter_column\([^)]*\btype_=",
    r"op\.alter_column\([^)]*\bnullable=False\b",
    # op.execute("...") escape hatches — raw SQL destruction
    r"\bDROP\s+(TABLE|COLUMN|CONSTRAINT|INDEX|POLICY|SCHEMA)\b",
    r"\bALTER\s+TABLE\s+\S+\s+DROP\b",
    r"\bALTER\s+TABLE\s+\S+.*\bSET\s+NOT\s+NULL\b",
    r"\bALTER\s+TABLE\s+\S+.*\bDROP\s+DEFAULT\b",
    r"\bTRUNCATE\b",
    # Data migrations — UPDATE/DELETE mutate existing rows and are
    # always destructive even if the net effect is desired.
    r"op\.execute\([^)]*\bUPDATE\s+\w+\s+SET\b",
    r"op\.execute\([^)]*\bDELETE\s+FROM\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bDELETE\s+FROM\b",
]
ACK_MARKER = "# destructive:"  # comment line in the revision
```

If a file matches any pattern AND does not contain a line starting with
`# destructive: <one-line justification>`, the test fails. The
justification forces the author to think through the expand-contract
implications at PR time rather than in review comments.

**Excluded from the scan:**
- `0001_baseline_existing_live_schema.py` (empty by design)
- Any file matching a configured allowlist in `pyproject.toml`
  (expected to stay empty; present only so emergency exemptions don't
  require test changes)

**Known false-positive pattern** (and how to handle):
`DROP POLICY IF EXISTS foo` followed by `CREATE POLICY foo` in the
same revision is the idempotent policy-swap pattern we used in PR #101
and is net-zero destructive. The author adds
`# destructive: idempotent policy swap — net-zero change` to
acknowledge. Marker fatigue is deliberate — the cost of false positives
is low (one comment line), the cost of missed true positives is a
production schema surprise.

### Autocommit-only DDL policy

Certain Postgres DDL cannot run inside a transaction:
`CREATE INDEX CONCURRENTLY`, `ALTER TYPE ... ADD VALUE`, and a few
extension operations. These require `op.execute` inside
`op.get_context().autocommit_block()` (Alembic 1.13+) or setting
`transaction_per_migration=True` in `env.py` so a FAILED
autocommit-only migration does not leave a previously-applied
autocommit op stranded in a half-done state.

Policy:

- An Alembic revision that contains ANY autocommit-only DDL must
  contain ONLY that DDL — no other statements in the same revision
- The revision header includes `# autocommit: <op name>` as an
  acknowledgment comment (the destructive-op CI scan pattern above is
  extended to detect autocommit-only ops and enforce this rule)
- `env.py` is configured with `transaction_per_migration=True` from
  day one so that autocommit migrations run in their own transaction
  context and failures don't leak across revisions.

**Why strict isolation (one autocommit op per revision) rather than
mixing.** When `autocommit_block()` opens, Alembic commits any
previously-accumulated work in the same revision before entering
autocommit mode. If the autocommit op then fails, the prior-committed
work is stranded on live with no rollback path — exactly the state
this spec is trying to prevent. Splitting keeps each piece independently
replayable and prevents split-brain failure states. Alembic's own
documentation implicitly recommends this when it notes that
`transaction_per_migration` is the right setting when autocommit
migrations exist (otherwise all prior revisions in the same upgrade
run could be affected by one autocommit failure). The strict rule
costs one extra PR per concurrent-index addition; the relaxed rule
costs a production recovery of arbitrary complexity.

---

## Cutoff rule

**Effective on the first commit that adds `backend/migrations/` to
`main`** (which will be the implementation PR for this spec):

- No new `backend/database/migration_*.sql` files for forward schema
  changes. All forward schema work is an Alembic revision under
  `backend/migrations/versions/`.
- Existing pre-cutoff files remain in place as historical artifacts.
  We do not delete, rename, or edit them.
- A `backend/database/CUTOFF.md` file documents the freeze date, points
  readers to `backend/migrations/`, and names the commit that
  established the cutoff.
- Pre-cutoff `rollback_*.sql` and `verify_*.sql` files remain
  discoverable. New Alembic revisions do not ship matching rollback or
  verify SQL — the forward-only policy replaces rollback, and
  verification either lives inside the migration as `op.execute(...)`
  assertions or in a companion test.

A pytest lint rule (`tests/test_cutoff_policy.py`) enforces this at PR
time. It:

1. Fails if any new file matching
   `backend/database/migration_*.sql`,
   `backend/database/rollback_*.sql`, or
   `backend/database/verify_*.sql` is added on the current branch
   relative to `origin/main`.
2. Fails if any existing pre-cutoff file (the set captured by
   `git ls-tree origin/main -- backend/database/`) has been modified
   on the current branch — they are frozen, not just capped.
3. The `supabase_schema.sql` and sibling top-level schema files
   (`supabase_behavior_schema.sql`, `supabase_roster_rls.sql`,
   `supabase_student_portal_schema.sql`, `supabase_submission_
   confirmations.sql`) are included in the freeze set.

A short `CUTOFF.md` at the top of `backend/database/` documents why
these files are frozen and points at `backend/migrations/versions/`
for forward work.

---

## Recovery model (when a migration has shipped and caused trouble)

1. Revert the application code that broke, if code is the proximate
   cause. Roll the image back via Railway's deploy history.
2. Write a new Alembic migration that corrects the schema/data/policy
   state forward. Merge + deploy it.
3. Never run `alembic downgrade` against production. The `downgrade()`
   body exists for local dev convenience only; its correctness against
   prod-like data and policy state is unverified and a mistake to rely
   on.

This mirrors the recovery path we've been using anyway — the pre-cutoff
rollback files are forward-fix helpers under a misleading name
(`rollback_2026_04_17_phase4.2_rls.sql` explicitly says it does not
restore the prior live policy set). The forward-only policy
just makes that existing practice explicit.

---

## Supabase-specific considerations

- **RLS policies, grants, CHECK constraints, extensions** are raw SQL
  via `op.execute("...")`. Alembic's op helpers do not know about these.
  This is fine — raw SQL is the same format as the existing `backend/
  database/*.sql` files, just wrapped in a `def upgrade():` function.
- **Supabase-reserved schemas** (`auth`, `storage`, `graphql_public`,
  `realtime`) are referenced by qualified name inside `op.execute`
  strings. Alembic does not attempt to version those schemas; their
  tables and functions live outside our control.
- **Service role behaviour.** The backend uses the Supabase service-role
  key which bypasses all RLS. RLS-policy migrations are zero-impact at
  runtime until Phase 4.5 introduces per-user JWT clients.
  Nothing in this spec changes that.
- **Connection pooler semantics.** See § Deployment flow — use session
  pooler (or direct), not transaction pooler.

---

## Rollout sequence

1. **Implementation PR** adds the scaffolding (`alembic.ini`, `backend/
   migrations/env.py`, `backend/migrations/script.py.mako`, `0001_
   baseline_existing_live_schema.py`), updates `requirements.txt`,
   `railway.json`, `.env.example`, adds the CI smoke job, adds
   `backend/database/CUTOFF.md`. No deploy behaviour change yet because
   the `preDeployCommand` runs Alembic which no-ops on `0001` baseline.
2. **Operator sets `ALEMBIC_DATABASE_URL`** on the Railway web service
   pointing at Supabase's session pooler. Sets same env var on operator
   workstation for first-time stamp. CI gets its own stub URL via the
   smoke job's service container.
3. **Operator stamps live**: `alembic stamp
   0001_baseline_existing_live_schema`. Verify with `alembic current`.
4. **Merge the implementation PR.** Railway deploys. `alembic upgrade
   head` runs as `preDeployCommand` and no-ops (already at head).
5. **First real migration** is the next schema PR. Naming pattern:
   `0002_<slug>.py`. Ships through the usual review + CI + deploy flow,
   now with Alembic as gate instead of the Supabase SQL Editor.

---

## Explicitly deferred

- Staging environment (would motivate a real rebaseline from live)
- Schema-first ORM adoption (SQLAlchemy models + autogenerate)
- Round-trip reversibility testing (the A option from Q4 of
  brainstorming)
- Phase 4.2 PR2 (behavior, LTI, OneRoster RLS policies). First real
  Alembic migration will be a non-RLS change to exercise the tooling on
  easier terrain before tackling Phase 4.2 PR2.
- Migration hashing / applied-state verification at app boot (Alembic's
  `alembic_version` table is the state of record)

---

## Open questions

None at spec-draft time — all four major decisions (tool choice,
deployment model, baseline handling, rollback policy) resolved during
brainstorming. Remaining detail is implementation plan material, not
spec material.

---

## References

- `backend/database/migration_2026_04_17_phase4.2_rls.sql` — the
  drift reconciliation that motivated this work
- `backend/database/rollback_2026_04_17_phase4.2_rls.sql` — real-world
  example of "rollback" that is actually a corrective forward script,
  cited in the Q4 policy answer
- Memory: `project_phase4.2_complete.md` — documents the drift
  reconciliation outcome
- Memory: `project_codebase_improvement_roadmap.md` — Phase 4 overview;
  this work is a Phase 4 follow-on
