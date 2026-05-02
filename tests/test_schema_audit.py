"""Pytest wrapper for tools/audit_select_columns.py.

Runs the schema audit in --live mode when SUPABASE_URL +
SUPABASE_SERVICE_KEY are present. Fails the test if any
`db.table(X).select(Y)` reference uses a column that doesn't exist on
the live table.

Skips when credentials are missing (CI without DB secrets) so that
local-only access doesn't make CI flaky.

Background: today (2026-05-02) two routes 500'd for ~5 days because
their SELECT used column names that didn't exist on Supabase
(`publish_date`, `name` on `students`). Tests passed because mock
fixtures used the buggy names too. This audit script + test catches
that class of bug at PR time.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = REPO_ROOT / "tools" / "audit_select_columns.py"


def _live_credentials_available() -> bool:
    # Load .env if present so local dev runs pick up credentials too.
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    return bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_KEY")
    )


@pytest.mark.skipif(
    not _live_credentials_available(),
    reason="SUPABASE_URL + SUPABASE_SERVICE_KEY not set; live audit skipped",
)
def test_no_schema_mismatches_against_live_supabase():
    """Audit script must report 0 column mismatches against live Supabase.

    If this fails, the message printed by the audit names the
    (table, column) pairs and the file:line where the bad reference lives.
    Two ways to fix:
      1. Code bug — update the route to use the correct column name.
      2. Schema drift — apply the missing migration in the reference DB.
    """
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--live", "--strict", "--quiet"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        pytest.fail(
            "Schema audit found mismatches:\n\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
