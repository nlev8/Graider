"""CI guardrail: freeze backend/database/ against new or modified files.

Once this test lands on main, backend/database/ becomes a historical
archive. All forward schema work is an Alembic revision under
backend/migrations/versions/.

The test compares the HEAD tree to origin/main. It checks only files
under backend/database/ (any extension). A failure indicates that either:
  - a new file was added (policy violation — use Alembic instead), or
  - an existing file was modified (policy violation — historical
    artifacts are frozen), or
  - an existing file was deleted (policy violation — historical
    artifacts are not removable).

Rationale lives in:
  backend/database/CUTOFF.md
  docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md

Local runs (with no origin/main to diff against) skip gracefully so
developers who check out a branch without a remote can still run pytest.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
FROZEN_DIR = "backend/database"
ALLOWED_NEW = {f"{FROZEN_DIR}/CUTOFF.md"}


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def _origin_main_available() -> bool:
    out = _git("rev-parse", "--verify", "--quiet", "origin/main")
    return bool(out.strip())


@pytest.fixture(scope="module")
def changed_paths() -> list[str]:
    if not _origin_main_available():
        pytest.skip(
            "origin/main not available — cutoff policy only enforced in "
            "CI and when the branch tracks a remote main."
        )
    # A..B: changes on B since it diverged from A.
    diff = _git("diff", "--name-status", "origin/main...HEAD")
    rows = [line.split("\t") for line in diff.splitlines() if line.strip()]
    return [
        f"{status}\t{path}"
        for status, *rest in rows
        for path in rest
    ]


def test_no_new_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("A\t")
        and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
        and row.split("\t")[1] not in ALLOWED_NEW
    ]
    assert not offenders, (
        f"New files added under {FROZEN_DIR}/ — this directory is frozen. "
        "All forward schema changes must be Alembic revisions under "
        "backend/migrations/versions/. See backend/database/CUTOFF.md.\n"
        + "\n".join(offenders)
    )


def test_no_modified_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("M\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
    assert not offenders, (
        f"Files under {FROZEN_DIR}/ were modified — historical artifacts "
        "are frozen. Forward-fix via an Alembic revision instead.\n"
        + "\n".join(offenders)
    )


def test_no_deleted_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("D\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
    assert not offenders, (
        f"Files under {FROZEN_DIR}/ were deleted — historical artifacts "
        "are permanent.\n"
        + "\n".join(offenders)
    )


def test_cutoff_marker_exists():
    """The CUTOFF.md readme is the human entry point — must stay present."""
    path = REPO_ROOT / FROZEN_DIR / "CUTOFF.md"
    assert path.exists(), (
        f"{path} must exist to document the directory freeze. If you "
        "genuinely need to relocate the freeze marker, update "
        "tests/test_cutoff_policy.py at the same time."
    )
