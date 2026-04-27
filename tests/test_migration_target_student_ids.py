"""Verify the Phase 4 migration SQL has the expected shape."""
import os
import re


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(REPO_ROOT, 'backend', 'database',
                         'migration_2026_04_26_phase4_target_student_ids.sql')
ROLLBACK = os.path.join(REPO_ROOT, 'backend', 'database',
                        'rollback_2026_04_26_phase4_target_student_ids.sql')


def test_migration_adds_target_student_ids_jsonb_nullable():
    with open(MIGRATION) as f:
        sql = f.read()
    # Must add the column.
    assert re.search(r'ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+target_student_ids\s+JSONB',
                     sql, re.IGNORECASE)
    # Must NOT include NOT NULL (column is nullable for backwards compat).
    assert not re.search(r'target_student_ids\s+JSONB\s+NOT\s+NULL', sql, re.IGNORECASE)
    # No GIN index in MVP.
    assert 'CREATE INDEX' not in sql.upper() or 'GIN' not in sql.upper()


def test_rollback_drops_column():
    with open(ROLLBACK) as f:
        sql = f.read()
    assert re.search(r'DROP\s+COLUMN\s+IF\s+EXISTS\s+target_student_ids',
                     sql, re.IGNORECASE)
