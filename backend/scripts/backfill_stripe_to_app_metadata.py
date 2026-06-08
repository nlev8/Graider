#!/usr/bin/env python3
"""VB11 backfill: bind each user's Stripe customer into app_metadata — SAFELY.

Why
---
`backend/routes/stripe_routes.py` now stores/reads the Stripe customer binding
in **app_metadata** (service-role-only). Previously it lived in `user_metadata`,
which Supabase exposes as `raw_user_meta_data` — client-settable at signUp via
the PUBLIC anon key. Existing customers therefore have `stripe_customer_id` only
in user_metadata, and after the code change their portal / subscription-status
calls would create a new empty customer and the webhook could no longer find
them.

The trap (Codex VB11 verify, HIGH): we must NOT blindly copy
`user_metadata.stripe_customer_id` into app_metadata — that value is exactly the
client-settable field the fix distrusts. An attacker who pre-seeded
`user_metadata.stripe_customer_id = cus_VICTIM` would otherwise get that
malicious binding promoted into trusted app_metadata, reopening the hijack.

Authoritative source of truth: when the server creates a customer it stamps
`metadata.supabase_user_id = <user_id>` on the **Stripe** customer
(stripe_routes._get_or_create_customer). This script promotes a candidate
customer id into app_metadata ONLY if Stripe confirms that customer's
`metadata.supabase_user_id` equals the user's own id. Forged / mismatched
bindings are skipped and reported.

subscription_* fields are intentionally NOT copied: they re-derive live from
Stripe (the subscription-status route queries Stripe directly, and the next
webhook re-syncs them into app_metadata), and the user_metadata copies are
forgeable.

DEPLOY ORDER (workflow Hard Rule #8): run against production Supabase
BEFORE/AS PART OF deploying the VB11 code, then verify an existing subscriber's
/api/stripe/subscription-status and /api/stripe/create-portal-session still
work. Idempotent; defaults to a DRY RUN. Requires STRIPE_SECRET_KEY to validate.

Usage
-----
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... STRIPE_SECRET_KEY=... \
        python backend/scripts/backfill_stripe_to_app_metadata.py
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... STRIPE_SECRET_KEY=... \
        python backend/scripts/backfill_stripe_to_app_metadata.py --apply
"""
import argparse
import os
import sys

# Repo root on sys.path (this file is <repo>/backend/scripts/).
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write app_metadata (default: dry run).")
    args = parser.parse_args()

    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
        return 2
    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        print("ERROR: STRIPE_SECRET_KEY must be set (used to VALIDATE each binding "
              "against Stripe before promoting it).", file=sys.stderr)
        return 2

    import stripe
    stripe.api_key = stripe_key
    # Canonical accessor (NOT supabase.create_client — enforced by
    # tests/test_no_direct_create_client.py).
    from backend.supabase_client import get_supabase_or_raise
    from backend.utils.supabase_users import list_all_users

    sb = get_supabase_or_raise()
    users = list_all_users(sb)
    print(f"Scanned {len(users)} users.")

    validated = []   # (uid, email, customer_id)
    rejected = []    # (uid, email, customer_id, reason)
    for u in users:
        user_meta = getattr(u, "user_metadata", None) or {}
        app_meta = getattr(u, "app_metadata", None) or {}
        if app_meta.get("stripe_customer_id"):
            continue  # already bound in app_metadata — idempotent
        cid = user_meta.get("stripe_customer_id")
        if not cid:
            continue  # nothing to migrate for this user

        # Validate against Stripe's authoritative server-set binding.
        try:
            cust = stripe.Customer.retrieve(cid)
        except Exception as e:  # noqa: BLE001 — operator script
            rejected.append((u.id, getattr(u, "email", "?"), cid, f"retrieve failed: {e}"))
            continue
        bound_uid = (getattr(cust, "metadata", None) or {}).get("supabase_user_id")
        # Require both sides truthy so a missing supabase_user_id (None) can't
        # validate against a falsy user id via None == None.
        if u.id and bound_uid == u.id:
            validated.append((u.id, getattr(u, "email", "?"), cid))
        else:
            rejected.append((u.id, getattr(u, "email", "?"), cid,
                             f"Stripe customer bound to '{bound_uid}', not this user"))

    if rejected:
        print(f"\n⚠️  {len(rejected)} candidate(s) REJECTED (not promoted — possible "
              f"forged user_metadata binding):")
        for uid, email, cid, reason in rejected:
            print(f"  - {email} ({uid}) cid={cid}: {reason}")

    if not validated:
        print("\nNothing to backfill — no Stripe-validated bindings to promote.")
        return 0

    print(f"\n{len(validated)} Stripe-validated binding(s) to promote into app_metadata:")
    for uid, email, cid in validated:
        print(f"  - {email} ({uid}): {cid}")

    if not args.apply:
        print("\nDRY RUN — no changes written. Re-run with --apply to backfill.")
        return 0

    failures = 0
    for uid, email, cid in validated:
        try:
            sb.auth.admin.update_user_by_id(uid, {"app_metadata": {"stripe_customer_id": cid}})
            print(f"  ✓ backfilled {email} ({uid})")
        except Exception as e:  # noqa: BLE001 — operator script, report-and-continue
            failures += 1
            print(f"  ✗ FAILED {email} ({uid}): {e}", file=sys.stderr)

    print(f"\nDone. {len(validated) - failures} backfilled, {failures} failed, "
          f"{len(rejected)} rejected.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
