#!/usr/bin/env python3
"""Set (or reset) the Graider district-admin password.

The /district console is password-gated. If a `DISTRICT_ADMIN_PASSWORD` env var
was set on the server, Graider bootstraps a stored hash from it on first use, so
the console shows "Login" (not "Create Password") with a password you may not
know. This script writes the stored `district:password_hash` directly — and the
stored hash takes PRECEDENCE over the env var (`_get_district_password_hash`
checks storage first), so the password you set here works immediately, no Railway
change required.

Writes to whatever Supabase the local `.env` points at (system scope). If that's
your production Supabase, this sets the PRODUCTION district password.

Usage (interactive — password never touches your shell history):
    cd /Users/alexc/Downloads/Graider && source venv/bin/activate
    python scripts/set_district_password.py

Or non-interactive:
    NEW_DISTRICT_PASSWORD='your-strong-password' python scripts/set_district_password.py
"""

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env the same way the backend does, so SUPABASE_* are available.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
                override=False)
except Exception:
    pass

from werkzeug.security import generate_password_hash  # noqa: E402
from backend.storage import save as storage_save, load as storage_load  # noqa: E402

_KEY = "district:password_hash"


def main():
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        print("WARNING: SUPABASE_URL / SUPABASE_SERVICE_KEY not set — the write may go to a")
        print("local file backend instead of Supabase. Check your .env if you expect Supabase.")

    pw = os.getenv("NEW_DISTRICT_PASSWORD")
    if not pw:
        pw = getpass.getpass("New district admin password (min 8 chars): ")
        confirm = getpass.getpass("Confirm: ")
        if pw != confirm:
            print("ERROR: passwords do not match.")
            return 1
    if len(pw) < 8:
        print("ERROR: password must be at least 8 characters.")
        return 1

    existing = storage_load(_KEY, "system")
    action = "Reset" if (existing and isinstance(existing, dict) and existing.get("hash")) else "Set"

    storage_save(_KEY, {"hash": generate_password_hash(pw)}, "system")

    # Read back to confirm the write landed.
    check = storage_load(_KEY, "system")
    if check and isinstance(check, dict) and check.get("hash"):
        print(f"✓ {action} district admin password. Log in at /district with the password you just entered.")
        print("  (The stored hash overrides any DISTRICT_ADMIN_PASSWORD env var.)")
        return 0
    print("ERROR: write did not persist — check Supabase connectivity / credentials.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
