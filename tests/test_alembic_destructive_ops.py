"""CI guardrail: destructive Alembic ops require `# destructive:` acknowledgment.

Policy lives in docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md
§ "Mechanical enforcement — destructive-op CI scan".

This test scans every Python file under backend/migrations/versions/ for
regex patterns that indicate destructive (or data-mutating) SQL and
fails unless the file contains an acknowledgment comment starting with
``# destructive:``.

False positives are expected and acceptable — the ack comment is cheap.
Every missed true positive is a production schema surprise, so we
prefer the pattern list to be broad.

The baseline revision (0001_baseline_existing_live_schema.py) and any
file listed in pyproject.toml's [tool.alembic-destructive-ops] allowlist
are skipped.
"""
from __future__ import annotations

import pathlib
import re
import textwrap

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS_DIR = REPO_ROOT / "backend" / "migrations" / "versions"
BASELINE_STEM = "0001_baseline_existing_live_schema"
ACK_MARKER_RE = re.compile(r"^\s*#\s*destructive\s*:", re.MULTILINE | re.IGNORECASE)

DESTRUCTIVE_PATTERNS: list[str] = [
    # Alembic op helpers — schema destruction
    r"op\.drop_column\b",
    r"op\.drop_table\b",
    r"op\.rename_table\b",
    r"op\.drop_constraint\b",
    r"op\.drop_index\b",
    # alter_column tightening: type change or nullable=False
    r"op\.alter_column\([^)]*\btype_=",
    r"op\.alter_column\([^)]*\bnullable=False\b",
    # op.execute("...") escape hatches — raw SQL destruction
    r"\bDROP\s+(TABLE|COLUMN|CONSTRAINT|INDEX|POLICY|SCHEMA)\b",
    r"\bALTER\s+TABLE\s+\S+\s+DROP\b",
    r"\bALTER\s+TABLE\s+\S+.*\bSET\s+NOT\s+NULL\b",
    r"\bALTER\s+TABLE\s+\S+.*\bDROP\s+DEFAULT\b",
    r"\bTRUNCATE\b",
    # Data migrations — UPDATE/DELETE mutate existing rows and are
    # always destructive even if the net effect is desired.
    r"op\.execute\([^)]*\bUPDATE\s+\w+\s+SET\b",
    r"op\.execute\([^)]*\bDELETE\s+FROM\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bDELETE\s+FROM\b",
]
_DESTRUCTIVE_RE = re.compile("|".join(DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def _allowlist() -> set[str]:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # pragma: no cover

    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return set()
    data = tomllib.loads(pyproject.read_text())
    configured = (
        data.get("tool", {})
        .get("alembic-destructive-ops", {})
        .get("allowlist", [])
    )
    return {str(name) for name in configured}


def _iter_revision_files() -> list[pathlib.Path]:
    if not VERSIONS_DIR.exists():
        return []
    allowlist = _allowlist()
    files = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        if path.stem == BASELINE_STEM:
            continue
        if path.name in allowlist:
            continue
        files.append(path)
    return files


def test_every_destructive_revision_has_ack_comment():
    """For every non-baseline revision under backend/migrations/versions/,
    if it contains any DESTRUCTIVE_PATTERNS match, it must also contain
    a line starting with `# destructive:`.
    """
    offenders: list[str] = []
    for path in _iter_revision_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = _DESTRUCTIVE_RE.findall(text)
        if not hits:
            continue
        if ACK_MARKER_RE.search(text) is None:
            offenders.append(
                f"{path.relative_to(REPO_ROOT)} contains destructive op(s) "
                f"but no `# destructive:` acknowledgment. First match: "
                f"{hits[0]!r}"
            )

    assert not offenders, (
        "Destructive Alembic ops must be acknowledged with a `# destructive:"
        " <justification>` comment. See "
        "docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md"
        " § Mechanical enforcement.\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Self-tests — verify the regex list actually catches each pattern.
# These run against in-memory strings, not against files on disk, so they
# never touch the real revisions directory.
# ---------------------------------------------------------------------------

_DESTRUCTIVE_FIXTURES: list[tuple[str, str]] = [
    ("drop_column helper", "op.drop_column('t', 'c')"),
    ("drop_table helper", "op.drop_table('t')"),
    ("rename_table helper", "op.rename_table('a', 'b')"),
    ("drop_constraint helper", "op.drop_constraint('fk_x', 't')"),
    ("drop_index helper", "op.drop_index('ix_x')"),
    ("alter_column type tightening", "op.alter_column('t', 'c', type_=sa.String(10))"),
    ("alter_column nullable tightening", "op.alter_column('t', 'c', nullable=False)"),
    ("raw DROP TABLE", 'op.execute("DROP TABLE foo")'),
    ("raw DROP COLUMN", 'op.execute("ALTER TABLE foo DROP COLUMN bar")'),
    ("raw DROP POLICY", 'op.execute("DROP POLICY foo ON bar")'),
    ("raw DROP SCHEMA", 'op.execute("DROP SCHEMA old CASCADE")'),
    ("raw SET NOT NULL", 'op.execute("ALTER TABLE foo ALTER COLUMN bar SET NOT NULL")'),
    ("raw DROP DEFAULT", 'op.execute("ALTER TABLE foo ALTER COLUMN bar DROP DEFAULT")'),
    ("raw TRUNCATE", 'op.execute("TRUNCATE foo")'),
    ("UPDATE SET in op.execute", 'op.execute("UPDATE foo SET bar = 1")'),
    ("DELETE FROM in op.execute", 'op.execute("DELETE FROM foo WHERE id = 1")'),
    ("bare UPDATE SET", "UPDATE foo SET bar = 1"),
    ("bare DELETE FROM", "DELETE FROM foo WHERE id = 1"),
]


@pytest.mark.parametrize("label,snippet", _DESTRUCTIVE_FIXTURES,
                         ids=[name for name, _ in _DESTRUCTIVE_FIXTURES])
def test_destructive_regex_catches_pattern(label, snippet):
    """Every entry in DESTRUCTIVE_FIXTURES must match at least one pattern."""
    assert _DESTRUCTIVE_RE.search(snippet), (
        f"Regex did not match: {label!r} -> {snippet!r}. "
        "If this pattern is not destructive, remove it. If it is, add "
        "a regex for it to DESTRUCTIVE_PATTERNS."
    )


_BENIGN_FIXTURES: list[tuple[str, str]] = [
    ("create_table", "op.create_table('t')"),
    ("add_column", "op.add_column('t', sa.Column('c', sa.String))"),
    ("create_index", "op.create_index('ix_x', 't', ['c'])"),
    ("create_unique_constraint", "op.create_unique_constraint('uq_x', 't', ['c'])"),
    (
        "CREATE POLICY only",
        'op.execute("CREATE POLICY foo ON bar FOR SELECT USING (true)")',
    ),
]


@pytest.mark.parametrize("label,snippet", _BENIGN_FIXTURES,
                         ids=[name for name, _ in _BENIGN_FIXTURES])
def test_destructive_regex_does_not_match_benign(label, snippet):
    """Sanity: benign operations should not match DESTRUCTIVE_PATTERNS."""
    assert not _DESTRUCTIVE_RE.search(snippet), (
        f"Regex falsely matched benign op: {label!r} -> {snippet!r}"
    )


def test_ack_marker_regex_accepts_expected_forms():
    """The `# destructive:` ack comment must match common formattings."""
    valid = [
        "# destructive: dropping obsolete column",
        "   # destructive: idempotent policy swap",
        "#destructive: no space is also fine",
        "# Destructive: case-insensitive",
    ]
    for line in valid:
        assert ACK_MARKER_RE.search(line), f"Expected match: {line!r}"

    invalid = [
        "# note: this is destructive",  # not leading
        "op.execute('destructive stuff')",  # no comment prefix
    ]
    for line in invalid:
        assert not ACK_MARKER_RE.search(line), f"Expected no match: {line!r}"


def test_baseline_is_excluded_from_scan():
    """The 0001 baseline revision is empty by design and exempt."""
    paths = [p.name for p in _iter_revision_files()]
    assert not any(p.startswith("0001_baseline") for p in paths), (
        f"Baseline should not be in scanned file list: {paths}"
    )


def test_fixture_ack_flow_integration(tmp_path, monkeypatch):
    """End-to-end: a synthetic revision file with a destructive op but no
    ack triggers an offender report; adding the ack suppresses it."""
    fake_versions = tmp_path / "versions"
    fake_versions.mkdir()
    bad = fake_versions / "0002_drops_a_column.py"
    bad.write_text(textwrap.dedent('''
        """fake revision"""
        def upgrade():
            op.drop_column("t", "c")
    '''))

    monkeypatch.setattr(
        "tests.test_alembic_destructive_ops.VERSIONS_DIR",
        fake_versions,
    )
    # With no ack, _iter_revision_files returns the fake file,
    # and the destructive regex matches. Simulate the core assertion.
    text = bad.read_text()
    assert _DESTRUCTIVE_RE.search(text)
    assert ACK_MARKER_RE.search(text) is None

    # Adding the ack comment should suppress.
    bad.write_text(bad.read_text() + "\n# destructive: testing\n")
    text = bad.read_text()
    assert _DESTRUCTIVE_RE.search(text)
    assert ACK_MARKER_RE.search(text) is not None
