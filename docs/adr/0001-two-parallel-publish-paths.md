# ADR 0001 — Two parallel publish paths, unified behind a repository abstraction

- **Status:** Accepted (retrospective record)
- **Date recorded:** 2026-06-10 (decision predates this record)

## Context

Teachers need two distinct ways to put work in front of students:

1. Quick, friction-free sharing (makeup exams, substitute days, students who
   are not yet enrolled in the system) — no login, no roster.
2. Tracked, class-scoped assignment delivery — enrollment-gated, with due
   dates, content types, and per-student submission tracking.

These are different trust models: the first is anonymous-by-design (a 6-char
join code is the only credential), the second is authenticated (Clever SSO or
email+code login bound to a class roster).

## Decision

Keep **two parallel publish paths with separate physical tables**, and
consolidate the duplicated read/write logic at the **code boundary** instead
of merging the schemas:

| Path | Access | Tables |
|---|---|---|
| Join-code | Anonymous via 6-char code | `published_assessments` + `submissions` |
| Class-based | Authenticated (SSO / email+code), enrollment required | `published_content` + `student_submissions` |

The per-table branching is collapsed into one repository with two thin
adapters: `backend/services/submission_repository.py`. The enum values are
deliberately the legacy table-name strings so the Celery wire argument
(`supabase_table=...`) stayed byte-for-byte unchanged during the migration.
Both paths share the same grading entry points and the same student-facing
UI (`frontend/src/components/StudentPortal.jsx`).

## Consequences

- Anonymous and authenticated data never mix in one table, which keeps the
  FERPA story simple: the anonymous path stores only what the student typed
  plus a self-reported name; the class-based path carries roster identity.
- Every submission-adjacent feature must be checked against both paths (the
  repository makes this a single seam, but feature work that bypasses the
  repository regresses to per-table `if` dispatch).
- The dual *physical* schema is a documented, tolerated residual — the
  hardening rubric's Architecture anchors accept "dual physical schema +
  repository code boundary" at level 7 and treat physical unification as a
  separate, future decision.

## Evidence

- `backend/services/submission_repository.py` (module docstring states the
  consolidation rationale and the byte-compatibility constraint)
- `CLAUDE.md` § "Two Publish Paths"; `docs/ARCHITECTURE.md` § 5
- Join-code generation + anonymous access: `backend/routes/student_portal_routes.py`
  (`generate_join_code`, CSPRNG via `secrets`)
- Class-based path: `backend/routes/student_account_routes.py`
