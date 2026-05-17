"""Forward-only submission dedup keys + partial unique indexes.

Revision ID: 0002_subm_dedup
Revises: 0001_baseline
Create Date: 2026-05-16

Classification: additive, forward-only, reversible.

Adds a nullable `dedup_key` to `submissions` and `student_submissions`
and a partial UNIQUE index `WHERE dedup_key IS NOT NULL`. All existing
rows have dedup_key = NULL, so the index build cannot fail on historical
duplicates and rewrites nothing (the spec's forward-only requirement).
Routes populate the key for new writes only.

downgrade() is implemented (unlike 0001's forward-only stance) because
this change is purely additive — dropping the index + column fully and
safely reverses it (spec requires reversibility).

CONCURRENTLY DDL cannot run in a transaction; env.py uses
transaction_per_migration, so each statement runs inside
op.get_context().autocommit_block().
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_subm_dedup"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATEMENTS_UP = [
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS dedup_key TEXT",
    "ALTER TABLE student_submissions ADD COLUMN IF NOT EXISTS dedup_key TEXT",
    "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_submissions_dedup_key "
    "ON submissions (dedup_key) WHERE dedup_key IS NOT NULL",
    "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_student_submissions_dedup_key "
    "ON student_submissions (dedup_key) WHERE dedup_key IS NOT NULL",
]

_STATEMENTS_DOWN = [
    "DROP INDEX CONCURRENTLY IF EXISTS uq_submissions_dedup_key",
    "DROP INDEX CONCURRENTLY IF EXISTS uq_student_submissions_dedup_key",
    "ALTER TABLE submissions DROP COLUMN IF EXISTS dedup_key",
    "ALTER TABLE student_submissions DROP COLUMN IF EXISTS dedup_key",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for stmt in _STATEMENTS_UP:
            op.execute(stmt)


# destructive: downgrade() only — DROP INDEX / DROP COLUMN reverses this
# purely additive migration. No existing-row data is lost: dedup_key was
# forward-only (NULL for all legacy rows), so dropping it discards only
# the new dedup keys written after this migration. upgrade() is
# non-destructive (ADD COLUMN IF NOT EXISTS + CREATE UNIQUE INDEX).
def downgrade() -> None:
    with op.get_context().autocommit_block():
        for stmt in _STATEMENTS_DOWN:
            op.execute(stmt)
