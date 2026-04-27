-- Phase 4 — Quick-Click Remediation: target_student_ids column
-- Spec: docs/superpowers/specs/2026-04-26-phase4-quick-click-remediation-design.md
--
-- Adds JSONB column for per-student visibility on published_content rows.
-- NULL = class-wide (existing behavior preserved); non-empty array = visible
-- only to those students. Empty array [] is invalid and rejected by the route.
--
-- Safety: ADD COLUMN with no default is metadata-only on Postgres 11+
-- (no table rewrite). Pre-existing rows get NULL → existing class-wide
-- visibility unchanged. No GIN index in MVP (deferred until EXPLAIN justifies).

ALTER TABLE published_content
  ADD COLUMN IF NOT EXISTS target_student_ids JSONB NULL;
