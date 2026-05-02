"""One-shot tool: dump live Supabase column schema to tools/supabase_schema.json.

Reads SUPABASE_URL + SUPABASE_SERVICE_KEY from .env, queries
information_schema.columns via the Supabase REST API, and writes a
canonical {table_name: [column_name, ...]} JSON file.

Run when:
- A new table or column is added (re-snapshot after the migration applies)
- The audit script (tools/audit_select_columns.py) reports false positives
  due to staleness

Usage:
    python tools/extract_supabase_schema.py [--out tools/supabase_schema.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Same env-loader as backend.app.
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "tools" / "supabase_schema.json"
DEFAULT_DOTENV = REPO_ROOT / ".env"


def fetch_schema(supabase_url: str, service_key: str) -> dict[str, list[str]]:
    """Query information_schema.columns via the Supabase REST API.

    Returns a dict keyed by table name, value is a sorted list of column names.
    Only includes the public schema (Supabase default); skips system tables
    that start with underscore (e.g., supabase internals).
    """
    import httpx

    url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/columns_in_public_schema"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    # Try the RPC first (cleanest); fall back to direct query if not present.
    try:
        resp = httpx.post(url, headers=headers, json={}, timeout=15)
        if resp.status_code == 404:
            raise RuntimeError("RPC fallback")
        resp.raise_for_status()
        rows = resp.json()
    except Exception:
        # Fallback: PostgREST exposes information_schema if the role has
        # SELECT on it. Use a direct GET on a view we'll have to create OR
        # just enumerate via a known list of tables. Here we try to use the
        # `pg_meta` introspection RPC if available.
        rows = _fetch_via_introspection_rpc(supabase_url, service_key)

    by_table: dict[str, list[str]] = {}
    for row in rows or []:
        tbl = row.get("table_name") or row.get("table")
        col = row.get("column_name") or row.get("column")
        if not tbl or not col:
            continue
        if tbl.startswith("_"):
            continue
        by_table.setdefault(tbl, []).append(col)
    for tbl in by_table:
        by_table[tbl] = sorted(set(by_table[tbl]))
    return by_table


def _fetch_via_introspection_rpc(supabase_url: str, service_key: str) -> list[dict]:
    """Last-resort: POST a raw SQL query via Supabase's `query` RPC.

    Requires a SECURITY DEFINER RPC function in the project. If that's not
    set up, raises RuntimeError so the caller can guide the operator.
    """
    import httpx

    url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/exec_sql"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": (
            "SELECT table_name, column_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "ORDER BY table_name, ordinal_position"
        ),
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Cannot introspect Supabase schema. RPC `exec_sql` returned "
            f"{resp.status_code}. Either:\n"
            f"  1. Create a SECURITY DEFINER RPC `exec_sql(query text)`, OR\n"
            f"  2. Manually query information_schema.columns and write the\n"
            f"     result to tools/supabase_schema.json by hand.\n"
            f"\n"
            f"Response: {resp.text[:500]}"
        )
    return resp.json() or []


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    parser.add_argument("--dotenv", default=str(DEFAULT_DOTENV), help=".env path")
    args = parser.parse_args(argv)

    load_dotenv(args.dotenv, override=True)
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not supabase_url or not service_key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env",
            file=sys.stderr,
        )
        return 2

    try:
        schema = fetch_schema(supabase_url, service_key)
    except Exception as e:
        print(f"Schema fetch failed: {e}", file=sys.stderr)
        return 3

    if not schema:
        print(
            "WARNING: schema is empty. Verify the Supabase introspection "
            "RPC is reachable.",
            file=sys.stderr,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(schema)} tables × "
          f"{sum(len(c) for c in schema.values())} columns -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
