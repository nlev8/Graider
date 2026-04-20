"""Baseline — existing live schema at Alembic introduction.

Revision ID: 0001_baseline
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

Note on revision ID length: Alembic's default alembic_version.version_num
column is VARCHAR(32). The short "0001_baseline" ID (13 chars) fits with
margin. The filename slug keeps the descriptive long form for
discoverability. Do NOT change the ``revision`` literal below without
verifying the target DB's alembic_version column is wide enough.

Operator step (run once against live before the PR that introduces
Alembic is merged; also safe to run again because `alembic stamp` is
idempotent):

    export ALEMBIC_DATABASE_URL='<session-pooler-url>'
    alembic stamp 0001_baseline
"""
from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty. Live schema at the cutoff date is represented
    # by the raw SQL artifacts under backend/database/ — see CUTOFF.md.
    pass


def downgrade() -> None:
    raise NotImplementedError("forward-only")
