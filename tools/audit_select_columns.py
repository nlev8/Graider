"""Audit `db.table(X).select(...)` calls for column-name typos.

Today's bug pattern (PR #154): a route's SELECT used a column name that
didn't exist on the table (`publish_date` instead of `created_at`,
`name` instead of `first_name + last_name`). Tests passed because mock
fixtures used the same buggy name. The bug stayed latent for ~5 days.

This script:
  1. Walks backend/ Python files for `db.table('X').select('A, B, C')`
     and `sb.table('X').select(...)` patterns.
  2. Builds {table: {column: [(file, line), ...]}}.
  3. (--live) Fetches one sample row per table from Supabase to get the
     authoritative column list. Compares code references against actual
     DB columns. Reports MISMATCHES (likely bugs).
  4. Without --live, just prints frequency counts so a human can spot
     anomalies.

Usage:
    python tools/audit_select_columns.py              # static frequency report
    python tools/audit_select_columns.py --live       # validate against live DB
    python tools/audit_select_columns.py --live --strict  # exit 1 on mismatch

Designed to be wired in CI as a pytest test (tests/test_schema_audit.py).
The CI version uses --live with cached credentials.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

TABLE_SELECT_RE = re.compile(
    r"""(?:db|sb|self\.sb|self\._sb|self\.db|self\._db|client|sb_admin)
        \.table\(\s*["']([a-z_][a-z0-9_]*)["']\s*\)
        \.select\(\s*\n?\s*["']([^"']+?)["']
    """,
    re.VERBOSE | re.MULTILINE,
)

SKIP_DIRS = {"__pycache__", ".pytest_cache", "static", "migrations"}


def find_select_calls(root: Path) -> list[tuple[Path, int, str, str]]:
    out: list[tuple[Path, int, str, str]] = []
    for p in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            text = p.read_text()
        except Exception:
            continue
        for m in TABLE_SELECT_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            out.append((p, line, m.group(1), m.group(2).strip()))
    return out


def parse_columns(raw_select: str) -> list[str]:
    """Parse a PostgREST select string into base-table column names.

    Drops PostgREST relationship hints like `students(id, name)` — those
    are JOINs, not columns of the source table. The relationship NAME
    (`students` here) is also dropped because it's not a real column on
    the source either.

    Drops aggregate-style entries (`students(count)`).

    Drops alias hints (`name:full_name` -> `full_name`).
    """
    cols: list[str] = []
    # Strip parenthesized chunks first: `students(id, name)` → drop entirely.
    # Repeat to handle nested. Then split on commas.
    cleaned = raw_select
    while True:
        new = re.sub(r"[a-z_][a-z0-9_]*\([^()]*\)", "", cleaned)
        if new == cleaned:
            break
        cleaned = new
    for raw in cleaned.split(","):
        c = raw.strip()
        if not c:
            continue
        if ":" in c:
            # PostgREST alias: `alias:real_col`. Real column is on the right.
            c = c.split(":")[1].strip()
        if c == "*":
            cols.append("*")
            continue
        if not re.match(r"^[a-z_][a-z0-9_]*$", c):
            continue
        cols.append(c)
    return cols


def build_table_map(
    calls: list[tuple[Path, int, str, str]],
) -> dict[str, dict[str, list[tuple[Path, int]]]]:
    by_table: dict[str, dict[str, list[tuple[Path, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for path, line, table, raw in calls:
        for col in parse_columns(raw):
            if col == "*":
                continue
            by_table[table][col].append((path, line))
    return by_table


def fetch_live_schema(
    tables: list[str],
) -> tuple[dict[str, set[str]], list[str]]:
    """Sample one row per table; use response keys as the column list.

    Returns (columns_by_table, indeterminate_tables) where
    indeterminate_tables had no rows we could sample.
    """
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv(REPO_ROOT / ".env", override=True)
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    columns_by_table: dict[str, set[str]] = {}
    indeterminate: list[str] = []
    for table in sorted(tables):
        try:
            r = client.table(table).select("*").limit(1).execute()
        except Exception as exc:
            print(f"    ! could not sample {table}: {exc}", file=sys.stderr)
            indeterminate.append(table)
            continue
        rows = r.data or []
        if not rows:
            indeterminate.append(table)
            continue
        columns_by_table[table] = set(rows[0].keys())
    return columns_by_table, indeterminate


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="Fetch one sample row per table to validate cols")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any mismatch (--live)")
    parser.add_argument("--quiet", action="store_true",
                        help="Hide per-column frequency listing")
    args = parser.parse_args(argv)

    calls = find_select_calls(BACKEND_DIR)
    by_table = build_table_map(calls)

    print(f"Scanned {len(calls)} select() calls across {len(by_table)} tables.\n")

    columns_by_table_live: dict[str, set[str]] = {}
    indeterminate: list[str] = []
    if args.live:
        print("Fetching live schema (one sample row per table)...")
        columns_by_table_live, indeterminate = fetch_live_schema(
            list(by_table.keys())
        )
        print(f"  resolved: {len(columns_by_table_live)} tables; "
              f"indeterminate (empty): {len(indeterminate)}\n")

    mismatches: list[tuple[str, str, list[tuple[Path, int]]]] = []
    for table in sorted(by_table):
        cols = by_table[table]
        live_cols = columns_by_table_live.get(table)
        live_status = ""
        if args.live:
            if live_cols is None:
                live_status = "(no rows — indeterminate)"
            else:
                live_status = f"(live: {len(live_cols)} cols)"
        if not args.quiet:
            print(f"  {table} ({len(cols)} cols referenced) {live_status}")
        for col in sorted(cols):
            sites = cols[col]
            mismatch = (
                live_cols is not None and col not in live_cols
            )
            mark = ""
            if mismatch:
                mark = "  ✗ NOT IN LIVE SCHEMA"
                mismatches.append((table, col, sites))
            if not args.quiet:
                print(f"    {col:30s} {len(sites):4d}× {mark}")
                if mismatch:
                    for path, line in sites[:5]:
                        rel = path.relative_to(REPO_ROOT)
                        print(f"        at {rel}:{line}")
        if not args.quiet:
            print()

    print("\n=== SUMMARY ===")
    if args.live:
        print(f"  Mismatches: {len(mismatches)}")
        if mismatches:
            print("  Detail:")
            for table, col, sites in mismatches:
                print(f"    {table}.{col} ({len(sites)} site(s))")
                for path, line in sites:
                    rel = path.relative_to(REPO_ROOT)
                    print(f"        {rel}:{line}")
        if indeterminate:
            print(f"  Indeterminate (no sample row): {indeterminate}")
            print("    (re-run after seeding data, or use a static schema map)")
    else:
        print("  Run with --live to validate against actual Supabase schema.")

    if args.strict and mismatches:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
