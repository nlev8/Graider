"""Baseline — existing live schema at Alembic introduction.

Revision ID: 0001_baseline_existing_live_schema
Revises:
Create Date: 2026-04-18

Classification: additive (no-op — documents the anchor only)

This revision does NOT replay the pre-cutoff raw SQL migrations under
backend/database/. It exists only to provide a named anchor for the
Alembic revision graph.

Tradeoff accepted: Alembic becomes authoritative for forward schema
changes only, not for historical reconstruction. If a fresh-environment
bootstrap requirement arises later, we rebaseline then (see the spec
at docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md).

Operator step (run once against live before the PR that introduces
Alembic is merged; also safe to run again because `alembic stamp` is
idempotent):

    export ALEMBIC_DATABASE_URL='<session-pooler-url>'
    alembic stamp 0001_baseline_existing_live_schema
"""
from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0001_baseline_existing_live_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty. Live schema at the cutoff date is represented
    # by the raw SQL artifacts under backend/database/ — see CUTOFF.md.
    pass


def downgrade() -> None:
    raise NotImplementedError("forward-only")
