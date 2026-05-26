#!/usr/bin/env python3
"""Verify the ClassLink SourcedId contract for a single user.

Background
----------
ClassLink SSO returns a ``SourcedId`` in the userinfo body. ClassLink's
Roster Server exposes OneRoster 1.1 endpoints, and each rostered user has
a ``sourcedId`` of their own. For the Graider ClassLink Roster Server
certification-parity feature to find a rostered student during SSO, these
two values **must be the byte-identical string** for the same person — the
contract that this script checks.

Graider's SSO student flow fails closed if the contract is broken
(`/student?classlink_error=not_provisioned` — no token minted, no session
created), but the happy path needs the contract to hold. This script is
the diagnostic you run when an SSO test against a tenant fails, to confirm
*which* side disagrees.

Usage
-----
    python scripts/verify_classlink_sourcedid_contract.py \\
        --base-url https://<tenant>.classlink-os.com/ims/oneroster/v1p1 \\
        --client-id $OR_CLIENT_ID --client-secret $OR_CLIENT_SECRET \\
        --userinfo-sourced-id "<SourcedId from ClassLink userinfo>"

When the direct ``GET /users/{sourcedId}`` returns 404, optionally pass a
fallback lookup so the script can find the user's *actual* roster sourcedId
and print the diff:

    --lookup-email student@example.edu
    # OR
    --lookup-given-name Jane --lookup-family-name Doe

Where to get the userinfo SourcedId
-----------------------------------
Two options:
  1. Have the test user log in via ClassLink SSO, then read the Sentry/Railway
     audit log for the resulting ``CLASSLINK_LOGIN`` (or, on failure,
     ``CLASSLINK_STUDENT_NOT_PROVISIONED``) event — the ``person_id`` /
     ``person_hash`` field is what we want (in the failure case the hash is
     not reversible; instead enable a one-shot debug log for the raw value).
  2. Hit the ClassLink LaunchPad userinfo endpoint
     (``https://nodeapi.classlink.com/v2/my/info``) directly with the user's
     access token and read ``SourcedId``.

Exit codes
----------
    0  Contract holds (direct GET /users/{sourcedId} returned the user).
    1  Contract broken (404, or user found by fallback with a different sourcedId).
    2  Operational error (auth, network, server).

Mirrors the OneRoster auth + retry conventions in ``backend/oneroster.py``
``OneRosterClient`` so behavior matches the production sync path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse

# Make ``backend.oneroster`` importable when running from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import httpx  # noqa: E402

from backend.oneroster import OneRosterClient  # noqa: E402


async def _fetch_user_by_sourced_id(client_obj: OneRosterClient,
                                    http_client: httpx.AsyncClient,
                                    sourced_id: str):
    """``GET /users/{sourcedId}`` — direct lookup. Returns dict or None on 404."""
    await client_obj._ensure_token(http_client)
    url = f"{client_obj.base_url}/users/{urllib.parse.quote(sourced_id, safe='')}"
    resp = await http_client.get(
        url, headers={"Authorization": f"Bearer {client_obj._token}"}
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    body = resp.json()
    # OneRoster single-resource wraps the entity under its singular key.
    return body.get("user", body)


async def _find_user_by_filter(client_obj: OneRosterClient,
                               http_client: httpx.AsyncClient,
                               filter_expr: str):
    """``GET /users?filter=<expr>`` — bulk listing; returns first match or None.

    OneRoster filter syntax is ``key='value'`` (single-quoted), combinable with
    ``AND``. Vendors implement subsets; ClassLink Roster Server supports the
    standard form.
    """
    await client_obj._ensure_token(http_client)
    url = (
        f"{client_obj.base_url}/users?filter="
        f"{urllib.parse.quote(filter_expr, safe='')}"
    )
    resp = await http_client.get(
        url, headers={"Authorization": f"Bearer {client_obj._token}"}
    )
    resp.raise_for_status()
    body = resp.json()
    users = body.get("users", [])
    return users[0] if users else None


def _summarize(user: dict) -> dict:
    """Trim a roster user to the fields a human will want in the report."""
    return {
        "sourcedId": user.get("sourcedId"),
        "role": user.get("role") or user.get("roles"),
        "givenName": user.get("givenName"),
        "familyName": user.get("familyName"),
        "email": user.get("email"),
        "status": user.get("status"),
    }


async def _main_async(args: argparse.Namespace) -> int:
    sourced_id = (args.userinfo_sourced_id or "").strip()
    if not sourced_id:
        print("ERROR: --userinfo-sourced-id must be non-empty", file=sys.stderr)
        return 2

    print("== ClassLink SourcedId contract check ==")
    print(f"  base_url:           {args.base_url}")
    print(f"  userinfo SourcedId: {sourced_id!r}")
    print()

    client_obj = OneRosterClient(
        base_url=args.base_url,
        client_id=args.client_id,
        client_secret=args.client_secret,
        token_url=args.token_url,
    )

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            user = await _fetch_user_by_sourced_id(client_obj, http_client, sourced_id)
        except httpx.HTTPStatusError as e:
            print(
                f"  [Roster Server auth/error] "
                f"{e.response.status_code}: {e.response.text[:300]}",
                file=sys.stderr,
            )
            return 2
        except httpx.HTTPError as e:
            print(f"  [network error] {e.__class__.__name__}: {e}", file=sys.stderr)
            return 2

        if user is not None:
            print(f"✓ CONTRACT HOLDS — GET /users/{sourced_id} returned 200")
            print(f"  roster user (trimmed):")
            print(json.dumps(_summarize(user), indent=2))
            return 0

        # 404 on the direct lookup. The userinfo SourcedId does not exist as a
        # roster sourcedId in this tenant. Try to find the same person by an
        # alternate identifier so we can print the diff.
        print(f"✗ CONTRACT BROKEN — GET /users/{sourced_id} returned 404")
        print(
            "  (the userinfo SourcedId does NOT exist in this tenant's "
            "Roster Server)"
        )
        print()

        filter_expr = None
        if args.lookup_email:
            filter_expr = f"email='{args.lookup_email}'"
        elif args.lookup_given_name and args.lookup_family_name:
            filter_expr = (
                f"givenName='{args.lookup_given_name}' "
                f"AND familyName='{args.lookup_family_name}'"
            )

        if not filter_expr:
            print(
                "  Pass --lookup-email OR (--lookup-given-name + --lookup-family-name)"
            )
            print("  to find the user's actual roster sourcedId for the diff report.")
            return 1

        print(f"  attempting fallback lookup by: {filter_expr}")
        try:
            roster_user = await _find_user_by_filter(client_obj, http_client, filter_expr)
        except httpx.HTTPStatusError as e:
            print(
                f"  [fallback lookup error] {e.response.status_code}: "
                f"{e.response.text[:300]}",
                file=sys.stderr,
            )
            return 1

        if roster_user is None:
            print(f"  ✗ user NOT FOUND in roster by {filter_expr}")
            print(
                "  → contract broken AND the person is missing from this roster. "
                "Possible causes: wrong tenant, wrong base_url, the user is not "
                "provisioned in this Roster Server, or the filter field name "
                "differs in this vendor implementation."
            )
            return 1

        roster_sid = roster_user.get("sourcedId", "<missing>")
        print("  ✓ user FOUND in roster — but with a DIFFERENT sourcedId")
        print(f"      userinfo SourcedId: {sourced_id!r}")
        print(f"      roster   sourcedId: {roster_sid!r}")
        print()
        print("  → ClassLink userinfo and ClassLink Roster Server disagree for "
              "the SAME person on this tenant. This breaks Graider's SSO student "
              "lookup. Recovery path:")
        print("      1. Escalate to ClassLink support with both values + the "
              "person's email/name.")
        print("      2. Confirm the tenant's identity-provisioning pipeline is "
              "the source of truth for sourcedId across both surfaces.")
        print("      3. Until fixed, ClassLink students in this tenant will land "
              "at /student?classlink_error=not_provisioned (designed fail-closed).")
        print()
        print("  roster user (trimmed):")
        print(json.dumps(_summarize(roster_user), indent=2))
        return 1


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify a ClassLink userinfo SourcedId matches the "
                    "OneRoster Roster Server sourcedId for the same person.",
        epilog="See module docstring for full usage and where to obtain the "
               "userinfo SourcedId.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base-url", required=True,
                   help="OneRoster Roster Server base URL "
                        "(e.g. https://<tenant>.classlink-os.com/ims/oneroster/v1p1)")
    p.add_argument("--client-id", required=True,
                   help="OneRoster OAuth2 client_id (Roster Server credential)")
    p.add_argument("--client-secret", required=True,
                   help="OneRoster OAuth2 client_secret (Roster Server credential)")
    p.add_argument("--token-url",
                   help="Optional OAuth2 token endpoint "
                        "(defaults to <base_url>/oauth/token)")
    p.add_argument("--userinfo-sourced-id", required=True,
                   help="The SourcedId returned by ClassLink userinfo at SSO time")
    p.add_argument("--lookup-email",
                   help="Optional fallback: email to find the user's actual "
                        "sourcedId when the direct lookup 404s")
    p.add_argument("--lookup-given-name",
                   help="Optional fallback: givenName "
                        "(use with --lookup-family-name)")
    p.add_argument("--lookup-family-name",
                   help="Optional fallback: familyName "
                        "(use with --lookup-given-name)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
