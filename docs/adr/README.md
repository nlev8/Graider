# Architecture Decision Records

Lightweight ADRs (Status / Context / Decision / Consequences / Evidence) for
the load-bearing decisions already made in this codebase. Most are
**retrospective records**: the decision shipped first, the record cites the
code, docs, and incidents that evidence it.

Conventions:

- Files are `NNNN-short-title.md`, numbered in the order recorded (not the
  order decided).
- Every ADR carries an **Evidence** section pointing at the code/docs that
  prove the decision is real — claims without evidence don't get an ADR.
- New ADRs: copy the section structure of any existing record, add a row
  here. The CI "Docs Drift Check" job fails if an index row points at a
  missing file or an ADR file is missing from this index
  (`scripts/check_docs_drift.py`).
- Superseding: don't edit history — write a new ADR and mark the old one
  `Superseded by NNNN`.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-two-parallel-publish-paths.md) | Two parallel publish paths, unified behind a repository abstraction | Accepted |
| [0002](0002-supabase-system-of-record-teacher-data-kv.md) | Supabase as system of record; per-teacher key-value `teacher_data` with a file fallback | Accepted |
| [0003](0003-background-thread-grading-incremental-celery.md) | In-process background-thread grading, migrated incrementally to Celery per path | Accepted (Phase 4.1b pending) |
| [0004](0004-rate-limiting-redis-required-fail-fast.md) | Rate limiting: Redis required in prod (fail-fast), startup probe + bounded retries | Accepted |
| [0005](0005-frontend-built-at-deploy-nixpacks.md) | Frontend built at deploy by Railway/NIXPACKS; `backend/static/` gitignored | Accepted |
| [0006](0006-ci-nine-required-checks-locked-names.md) | CI: named required status checks (eleven as of 2026-06-10); job names locked to branch protection | Accepted (amended) |
| [0007](0007-oidc-require-lists-core-required-claims-only.md) | OIDC `require` lists may contain only OIDC Core §2 REQUIRED claims | Accepted |
| [0008](0008-multipass-grading-pipeline-18-factors.md) | Multipass grading pipeline with all grading factors accumulated into prompt context | Accepted |
