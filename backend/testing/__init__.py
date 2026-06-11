"""Test-only support code for Graider.

Modules in this package are ONLY activated through explicit, env-gated
test hooks (e.g. GRAIDER_FAKE_SUPABASE=1 + FLASK_ENV=development). They
must never run in production; every gate is fail-closed.
"""
