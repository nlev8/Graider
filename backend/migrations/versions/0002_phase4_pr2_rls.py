"""Phase 4.2 PR2 — finish RLS sweep (behavior + audit_log).

Revision ID: 0002_phase4_pr2
Revises: 0001_baseline
Create Date: 2026-04-19

Classification: destructive

# destructive: renames "Teachers manage own sessions"/"Teachers manage own
# events" to canonical behavior_sessions_own / behavior_events_own. The
# DROP POLICY IF EXISTS … ; CREATE POLICY … pair happens inside a single
# transaction (transaction_per_migration=True), so the intermediate
# no-policy state is never observable by concurrent queries.
# Net semantic change: zero (same auth.uid() = teacher_id check, now
# spelled in the canonical auth.uid()::text = teacher_id::text form).
# audit_log gets a brand-new SELECT-only teacher policy — no destructive
# change there, bundled here for atomicity.
# See docs/superpowers/specs/2026-04-19-phase4.2-pr2-rls-design.md.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0002_phase4_pr2"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------
    # Section 1: behavior_sessions canonicalization
    # -------------------------------------------------------------------
    op.execute(
        'DROP POLICY IF EXISTS "Teachers manage own sessions" ON behavior_sessions;'
    )
    op.execute("DROP POLICY IF EXISTS behavior_sessions_own ON behavior_sessions;")
    op.execute(
        """
        CREATE POLICY behavior_sessions_own ON behavior_sessions
            FOR ALL
            TO authenticated
            USING (auth.uid()::text = teacher_id::text)
            WITH CHECK (auth.uid()::text = teacher_id::text);
        """
    )

    # -------------------------------------------------------------------
    # Section 2: behavior_events canonicalization
    # -------------------------------------------------------------------
    op.execute(
        'DROP POLICY IF EXISTS "Teachers manage own events" ON behavior_events;'
    )
    op.execute("DROP POLICY IF EXISTS behavior_events_own ON behavior_events;")
    op.execute(
        """
        CREATE POLICY behavior_events_own ON behavior_events
            FOR ALL
            TO authenticated
            USING (auth.uid()::text = teacher_id::text)
            WITH CHECK (auth.uid()::text = teacher_id::text);
        """
    )

    # -------------------------------------------------------------------
    # Section 3: audit_log SELECT-only teacher policy (net-new)
    # -------------------------------------------------------------------
    # No INSERT/UPDATE/DELETE policies. Audit is append-only; the only
    # writer is the backend's service-role Supabase client which
    # bypasses RLS entirely. Teachers get read-only self-service
    # visibility for Phase 4.5 — never the ability to erase evidence.
    op.execute("DROP POLICY IF EXISTS audit_log_select_teacher ON audit_log;")
    op.execute(
        """
        CREATE POLICY audit_log_select_teacher ON audit_log
            FOR SELECT
            TO authenticated
            USING (teacher_id = auth.uid()::text);
        """
    )


def downgrade() -> None:
    raise NotImplementedError("forward-only")
