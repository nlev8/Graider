"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Classification: <additive | destructive>  (set before merge)
${"# destructive: <one-line justification>" if False else ""}
${"# autocommit: <op name>" if False else ""}
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    # Default: forward-only per
    # docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md.
    # Replace only if you need local-dev reversibility; production must
    # NEVER run `alembic downgrade`.
    raise NotImplementedError("forward-only")
