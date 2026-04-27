-- Rollback for Phase 4 target_student_ids column.
-- Drops the column entirely. Any targeting metadata is lost; rows revert
-- to class-wide visibility (since the column no longer exists).

ALTER TABLE published_content
  DROP COLUMN IF EXISTS target_student_ids;
