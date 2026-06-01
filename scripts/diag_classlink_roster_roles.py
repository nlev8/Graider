#!/usr/bin/env python3
"""Diagnostic: list the ROLES present in a ClassLink/OneRoster tenant's roster.

Purpose
-------
The ClassLink SSO `Role` claim for tenant 2284 collapses staff to 'Teacher', so
SSO-claim-based admin routing can't distinguish admins. This script asks the
**Roster Server** directly: does an administrator role exist ANYWHERE in the
roster (`/users`), even when the SSO claim hides it?

OneRoster v1.1 users carry BOTH a singular `role` (the deprecated primary) and a
`roles[]` array of `{roleType, role, org}`. An admin can be `teacher` primary AND
`administrator` at an org in `roles[]` — which the SSO claim may not surface. This
prints the distribution of both so you can see what's actually there.

Usage
-----
Reuses Graider's OneRosterClient (handles the #603 dual-channel OAuth auth and the
ClassLink host-root /token quirk). Run from the repo root with the venv active:

    export ONEROSTER_BASE_URL="https://classlinkcertification3-vn-v2.rosterserver.com/ims/oneroster/v1p1"
    export ONEROSTER_CLIENT_ID="<client id>"
    export ONEROSTER_CLIENT_SECRET="<client secret>"
    export ONEROSTER_TOKEN_URL="https://classlinkcertification3-vn-v2.rosterserver.com/token"  # ClassLink quirk
    python scripts/diag_classlink_roster_roles.py

No PII is printed — only roles, counts, and sourcedIds (+ org sourcedIds).
"""

import asyncio
import os
import sys
from collections import Counter

import httpx

# Import Graider's client so the OAuth auth + pagination behave identically to prod.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.oneroster import OneRosterClient  # noqa: E402


def _norm(v):
    return str(v or "").strip().lower()


async def main():
    base_url = os.getenv("ONEROSTER_BASE_URL")
    client_id = os.getenv("ONEROSTER_CLIENT_ID")
    client_secret = os.getenv("ONEROSTER_CLIENT_SECRET")
    token_url = os.getenv("ONEROSTER_TOKEN_URL")  # optional; ClassLink uses host-root /token

    missing = [n for n, v in [
        ("ONEROSTER_BASE_URL", base_url),
        ("ONEROSTER_CLIENT_ID", client_id),
        ("ONEROSTER_CLIENT_SECRET", client_secret),
    ] if not v]
    if missing:
        print("ERROR: missing env vars: " + ", ".join(missing))
        print("Set them (see the docstring) and re-run.")
        return 2

    client = OneRosterClient(
        base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
    )

    print("== ClassLink/OneRoster roster role census ==")
    print(f"  base_url:  {client.base_url}")
    print(f"  token_url: {client.token_url}")
    print()

    async with httpx.AsyncClient(timeout=30.0) as http:
        await client._ensure_token(http)
        users = await client._get_paginated(http, "/users", "users", label="diag-users")

    if not users:
        print("No users returned from /users. Either the roster is empty for these")
        print("credentials, or the endpoint/scope is restricted. Nothing to classify.")
        return 1

    primary_roles = Counter()       # the singular top-level `role`
    array_roles = Counter()         # every roles[].role
    array_roletypes = Counter()     # every roles[].roleType
    admin_users = []                # users with any admin-ish role anywhere

    for u in users:
        if not isinstance(u, dict):
            continue
        top_role = _norm(u.get("role"))
        if top_role:
            primary_roles[top_role] += 1

        found_admin = "admin" in top_role
        for entry in (u.get("roles") or []):
            if not isinstance(entry, dict):
                continue
            r = _norm(entry.get("role"))
            rt = _norm(entry.get("roleType"))
            if r:
                array_roles[r] += 1
            if rt:
                array_roletypes[rt] += 1
            if "admin" in r:
                found_admin = True

        if found_admin:
            sid = str(u.get("sourcedId") or "")
            org_sids = [
                str((e.get("org") or {}).get("sourcedId") or "")
                for e in (u.get("roles") or []) if isinstance(e, dict)
            ]
            admin_users.append((sid, top_role,
                                [_norm(e.get("role")) for e in (u.get("roles") or []) if isinstance(e, dict)],
                                [o for o in org_sids if o]))

    print(f"Total users: {len(users)}")
    print()
    print("Top-level `role` (singular/primary) distribution:")
    for role, n in primary_roles.most_common():
        print(f"  {role:<24} {n}")
    print()
    print("`roles[].role` (v1.1 array) distribution:")
    if array_roles:
        for role, n in array_roles.most_common():
            print(f"  {role:<24} {n}")
    else:
        print("  (no roles[] arrays present — tenant only exposes the singular role)")
    print()
    print("`roles[].roleType` distribution:")
    if array_roletypes:
        for rt, n in array_roletypes.most_common():
            print(f"  {rt:<24} {n}")
    else:
        print("  (none)")
    print()

    if admin_users:
        print(f"✓ ADMIN-ROLE USERS FOUND: {len(admin_users)} (admin signal EXISTS in the roster)")
        print("  → We can route admins off the ROSTER record, not the SSO claim.")
        print("  Sample (sourcedId | primary role | roles[] | org sourcedIds):")
        for sid, top, roles, orgs in admin_users[:15]:
            print(f"    {sid} | {top or '-'} | {roles or '-'} | {orgs or '-'}")
    else:
        print("✗ NO admin-role users anywhere in the roster (neither singular nor roles[]).")
        print("  → ClassLink has NO admin signal for this tenant. Options:")
        print("    (a) get an administrator role provisioned in the tenant, or")
        print("    (b) designate admins inside Graider (district-console-managed).")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
