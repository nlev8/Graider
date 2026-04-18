"""Phase 4.2 PR1 — static RLS policy coverage test.

Uses pglast (libpg_query Python wrapper) to parse all Supabase schema SQL
files plus the Phase 4.2 migration. Asserts that every tenant-owned table
in the PR1 scope has:

  1. An ALTER TABLE ... ENABLE ROW LEVEL SECURITY statement somewhere
  2. At least one CREATE POLICY ... ON <table> statement
  3. Every policy's USING / WITH CHECK clause references auth.uid() or EXISTS
     (shape check — catches "policy with no auth check")

This is a STATIC test — it does not execute SQL. It catches:
  - Missing RLS enable on a table
  - Missing policy on a table
  - Policy with no auth scoping (e.g., USING (true))
  - Typo in table name (policy on non-existent table won't ALTER TABLE that table)

What it does NOT catch (requires Phase 4.5 integration test suite):
  - Policy semantic correctness (does the auth check actually restrict the
    right set of rows?)
  - Multi-hop subquery correctness

If you add a new tenant-owned table to the schema, add it to
PR1_SCOPE_TABLES below. This list is the source of truth for "tables
that must have RLS policies" in Phase 4.2 PR1.
"""
from __future__ import annotations

import pathlib
import re

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every schema SQL file the migration depends on for parent-table
# definitions + the PR1 migration itself. Order matters for parsing
# parent tables before policies reference them.
SCHEMA_FILES = [
    "backend/database/supabase_schema.sql",
    "backend/database/supabase_teacher_schema.sql",
    "supabase_student_portal_schema.sql",
    "supabase_roster_rls.sql",
    "supabase_submission_confirmations.sql",
    "backend/database/migration_2026_04_17_phase4.2_rls.sql",
]

# Tables covered by Phase 4.2 PR1. Maintainers must update this list
# when adding a new tenant-owned table to the schema.
PR1_SCOPE_TABLES = {
    # Re-verify (existing RLS)
    "teacher_data",
    "student_history",
    "classes",
    "students",
    "class_students",
    # Tighten existing
    "submissions",
    "published_assessments",
    # New RLS
    "published_content",
    "student_submissions",
    "student_sessions",
    "submission_confirmations",
}


def _all_sql() -> str:
    """Concatenate all schema SQL files into a single string for parsing."""
    chunks = []
    for rel in SCHEMA_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            pytest.fail(f"Required schema file missing: {rel}")
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _parse_policies(sql: str) -> list[dict]:
    """Parse all CREATE POLICY statements using pglast.

    Returns a list of dicts with keys: policy_name, table_name, using_clause,
    with_check_clause (strings — raw SQL fragments).

    Simulates Postgres runtime ordering: if a (policy_name, table_name)
    pair is DROPped later in the concatenated stream without a subsequent
    re-CREATE, the earlier CREATE is omitted from the returned list. This
    matches what pg_policies would contain after replaying the SQL in
    source order — so we don't flag the PR1 migration for "inheriting"
    broad policies from the base schema that it explicitly drops.
    """
    try:
        import pglast
    except ImportError:
        pytest.skip("pglast not installed; run `pip install -r requirements-dev.txt`")

    raw_events: list[tuple[str, str, str, int]] = []
    try:
        parsed = pglast.parse_sql(sql)
    except Exception as e:
        pytest.fail(f"pglast failed to parse combined SQL: {e}")

    for idx, stmt_wrapper in enumerate(parsed):
        stmt = stmt_wrapper.stmt
        t = type(stmt).__name__
        if t == "CreatePolicyStmt":
            raw_events.append((
                "create",
                stmt.policy_name,
                stmt.table.relname if stmt.table else "",
                idx,
            ))
        elif t == "DropStmt":
            # pglast parses DROP POLICY as a generic DropStmt with
            # removeType = OBJECT_POLICY. Each item of stmt.objects is a
            # tuple(String, String) with the FIRST element the table name
            # and the SECOND element the policy name.
            remove_type = getattr(stmt, "removeType", None)
            remove_name = getattr(remove_type, "name", str(remove_type)) if remove_type else ""
            if "POLICY" not in remove_name:
                continue
            for obj in (stmt.objects or []):
                if not isinstance(obj, tuple) or len(obj) < 2:
                    continue
                tname = getattr(obj[0], "sval", "") or ""
                pname = getattr(obj[1], "sval", "") or ""
                if pname and tname:
                    raw_events.append(("drop", pname, tname, idx))

    # Replay events: create adds, drop removes.
    live: dict[tuple[str, str], int] = {}
    for kind, pname, tname, idx in raw_events:
        key = (pname, tname)
        if kind == "create":
            live[key] = idx
        elif kind == "drop":
            live.pop(key, None)

    policies: list[dict] = []
    for (pname, tname), idx in live.items():
        policy = {
            "policy_name": pname,
            "table_name": tname,
            "using_clause": "",
            "with_check_clause": "",
        }
        m = re.search(
            rf"CREATE\s+POLICY\s+[\"']?{re.escape(pname)}[\"']?\s+ON\s+\S+"
            r"(?:\s+FOR\s+\w+)?"
            r"(?:\s+USING\s*\((?P<using>[\s\S]+?)\))?"
            r"(?:\s+WITH\s+CHECK\s*\((?P<check>[\s\S]+?)\))?"
            r"\s*;",
            sql,
            flags=re.IGNORECASE,
        )
        if m:
            policy["using_clause"] = (m.group("using") or "").strip()
            policy["with_check_clause"] = (m.group("check") or "").strip()
        policies.append(policy)
    return policies


def _parse_rls_enabled_tables(sql: str) -> set[str]:
    """Find every table with ALTER TABLE ... ENABLE ROW LEVEL SECURITY."""
    try:
        import pglast
    except ImportError:
        pytest.skip("pglast not installed")

    enabled: set[str] = set()
    parsed = pglast.parse_sql(sql)
    for stmt_wrapper in parsed:
        stmt = stmt_wrapper.stmt
        if type(stmt).__name__ != "AlterTableStmt":
            continue
        if not stmt.relation or not stmt.cmds:
            continue
        for cmd in stmt.cmds:
            # AlterTableCmd with subtype AT_EnableRowSecurity
            subtype = getattr(cmd, "subtype", None)
            subtype_name = getattr(subtype, "name", str(subtype)) if subtype else ""
            if "EnableRowSecurity" in subtype_name or "AT_EnableRowSecurity" in str(subtype):
                enabled.add(stmt.relation.relname)
    return enabled


def test_every_pr1_table_has_rls_enabled():
    """Every table in PR1_SCOPE_TABLES must have ALTER TABLE ... ENABLE ROW LEVEL SECURITY."""
    sql = _all_sql()
    enabled = _parse_rls_enabled_tables(sql)
    missing = PR1_SCOPE_TABLES - enabled
    assert not missing, (
        f"Tables missing ENABLE ROW LEVEL SECURITY: {sorted(missing)}. "
        f"Every tenant-owned table in PR1 must have RLS enabled in one of: {SCHEMA_FILES}"
    )


def test_every_pr1_table_has_at_least_one_policy():
    """Every table in PR1_SCOPE_TABLES must have at least one CREATE POLICY."""
    sql = _all_sql()
    policies = _parse_policies(sql)
    tables_with_policies = {p["table_name"] for p in policies if p["table_name"]}
    missing = PR1_SCOPE_TABLES - tables_with_policies
    assert not missing, (
        f"Tables with RLS enabled but no policy: {sorted(missing)}. "
        f"Every table needs at least one CREATE POLICY."
    )


def test_every_policy_has_auth_check():
    """Every CREATE POLICY on a PR1 table must reference auth.uid() or EXISTS.

    A policy with `USING (true)` or `WITH CHECK (true)` is a bug — it
    means "anyone can see/write this row" which defeats RLS. Only the
    service-role-preserved policies are exceptions, and those use role-based
    matching (auth.jwt() ->> 'role' = 'service_role') rather than the
    bare-true pattern.
    """
    sql = _all_sql()
    policies = _parse_policies(sql)

    offenders: list[str] = []
    for p in policies:
        if p["table_name"] not in PR1_SCOPE_TABLES:
            continue
        # Combine both clauses for the check
        combined = (p["using_clause"] + " " + p["with_check_clause"]).lower()
        has_auth = "auth.uid()" in combined or "auth.jwt()" in combined
        has_exists = "exists" in combined and "select" in combined
        has_role_check = "service_role" in combined or "auth.role()" in combined
        if not (has_auth or has_exists or has_role_check):
            offenders.append(
                f"{p['policy_name']} on {p['table_name']}: "
                f"USING=({p['using_clause'][:80]}...) "
                f"WITH CHECK=({p['with_check_clause'][:80]}...)"
            )
    assert not offenders, (
        "Policies without auth.uid() / EXISTS / service_role check:\n"
        + "\n".join(offenders)
    )


def test_dropped_broad_policies_are_not_recreated_in_migration():
    """The PR1 migration explicitly drops 'Anyone can read' style policies.

    This test verifies that migration SQL does NOT contain a CREATE POLICY
    statement matching those names (catches "accidentally re-added the broad
    policy" regression).
    """
    migration_path = REPO_ROOT / "backend/database/migration_2026_04_17_phase4.2_rls.sql"
    content = migration_path.read_text(encoding="utf-8")
    forbidden_recreations = [
        'CREATE POLICY "Anyone can read active assessments"',
        'CREATE POLICY "Anyone can insert submissions"',
        'CREATE POLICY "Anyone can read submissions"',
    ]
    for forbidden in forbidden_recreations:
        assert forbidden not in content, (
            f"Migration re-creates a broad policy that was supposed to be tightened: "
            f"{forbidden}. Remove it."
        )


def test_rollback_file_exists_and_drops_every_pr1_policy():
    """The paired rollback file must drop every policy the migration adds."""
    migration = (REPO_ROOT / "backend/database/migration_2026_04_17_phase4.2_rls.sql").read_text()
    rollback = (REPO_ROOT / "backend/database/rollback_2026_04_17_phase4.2_rls.sql").read_text()

    created = set(re.findall(r"CREATE\s+POLICY\s+([\w_]+)\s+ON", migration, re.IGNORECASE))
    dropped = set(re.findall(r"DROP\s+POLICY\s+IF\s+EXISTS\s+([\w_]+)\s+ON", rollback, re.IGNORECASE))

    missing_drops = created - dropped
    assert not missing_drops, (
        f"Rollback missing DROP POLICY for: {sorted(missing_drops)}. "
        f"Every policy the migration creates must have a paired drop in the rollback."
    )
