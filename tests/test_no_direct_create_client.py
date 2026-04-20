"""Regression guard: no module outside the approved Supabase client factories
may call supabase.create_client directly. All Supabase access must route
through the canonical get_supabase()/get_supabase_or_raise() helpers (or, for
per-user JWT requests, get_request_supabase()) so the ResilientClient wrapper
is applied.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
ALLOWED = {
    BACKEND / "supabase_client.py",
    BACKEND / "supabase_client_scoped.py",
}


def _python_files():
    for path in BACKEND.rglob("*.py"):
        if path in ALLOWED:
            continue
        yield path


def test_no_direct_create_client_calls():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "create_client(" in text and "from supabase import" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
        elif "supabase.create_client(" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        "Direct supabase.create_client() calls found outside "
        "backend/supabase_client.py. These bypass the ResilientClient "
        "wrapper and lose retry protection. Migrate them to "
        "backend.supabase_client.get_supabase() or get_supabase_or_raise():\n  - "
        + "\n  - ".join(offenders)
    )
