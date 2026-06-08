#!/usr/bin/env python3
"""VB10 backfill: promote `approved` from user_metadata → app_metadata.

Why
---
The approval gate (`backend/auth.py::check_auth`) and `approval_status` now read
approval from **app_metadata** (service-role-only). Previously approval lived in
`user_metadata`, which Supabase exposes as `raw_user_meta_data` — client-settable
at signUp via the PUBLIC anon key (`signUp({options:{data:{approved:true}}})`).
Trusting it let a user self-approve and bypass the manual onboarding gate.

After the code change, every teacher who was approved under the old scheme has
`user_metadata.approved == True` but **no** `app_metadata.approved`, so they would
be locked out (403 NOT_APPROVED) until this backfill runs. The admin-API stale-JWT
fallback also reads app_metadata, so it does NOT rescue them without this backfill.

This script copies `user_metadata.approved == True` → `app_metadata.approved = True`
for every existing user, using the service-role admin API. It is idempotent and
defaults to a DRY RUN.

DEPLOY ORDER (per workflow Hard Rule #8 — operator validation against the live
tenant): run this against production Supabase BEFORE or AS PART OF deploying the
VB10 code, then verify an existing approved teacher can still log in.

Usage
-----
    # dry run (default) — prints what WOULD change, mutates nothing
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python backend/scripts/backfill_approval_to_app_metadata.py

    # actually apply
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python backend/scripts/backfill_approval_to_app_metadata.py --apply

Security note
-------------
This promotes the EXISTING approved set verbatim. If you suspect a pre-VB10
self-approval occurred, audit the user list (printed in dry-run) before applying.
"""
import argparse
import os
import sys

# Allow running without installing the package: add the repo root (this file
# lives at <repo>/backend/scripts/, so go up three levels) to sys.path.
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write app_metadata.approved (default: dry run).",
    )
    args = parser.parse_args()

    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
        return 2

    # Route through the canonical accessor (NOT supabase.create_client directly —
    # enforced by tests/test_no_direct_create_client.py).
    from backend.supabase_client import get_supabase_or_raise
    from backend.utils.supabase_users import list_all_users

    sb = get_supabase_or_raise()
    users = list_all_users(sb)
    print(f"Scanned {len(users)} users.")

    to_backfill = []
    for u in users:
        user_meta = getattr(u, "user_metadata", None) or {}
        app_meta = getattr(u, "app_metadata", None) or {}
        approved_legacy = bool(user_meta.get("approved"))
        approved_app = bool(app_meta.get("approved"))
        if approved_legacy and not approved_app:
            to_backfill.append((u.id, getattr(u, "email", "?")))

    if not to_backfill:
        print("Nothing to backfill — all approved users already have app_metadata.approved.")
        return 0

    print(f"{len(to_backfill)} user(s) need app_metadata.approved = True:")
    for uid, email in to_backfill:
        print(f"  - {email} ({uid})")

    if not args.apply:
        print("\nDRY RUN — no changes written. Re-run with --apply to backfill.")
        return 0

    failures = 0
    for uid, email in to_backfill:
        try:
            sb.auth.admin.update_user_by_id(uid, {"app_metadata": {"approved": True}})
            print(f"  ✓ backfilled {email} ({uid})")
        except Exception as e:  # noqa: BLE001 — operator script, report-and-continue
            failures += 1
            print(f"  ✗ FAILED {email} ({uid}): {e}", file=sys.stderr)

    print(f"\nDone. {len(to_backfill) - failures} backfilled, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
