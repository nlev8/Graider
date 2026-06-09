"""GH #597 — OIDC `require`-list conformance across all JWT id_token decode paths.

Hard Rule #10 (.claude/rules/workflow.md): a pyjwt `options={"require":[...]}`
list on an OIDC id_token decode must be EXACTLY the OIDC Core §2 REQUIRED
id_token claims — iss, sub, aud, exp, iat (nonce is verified SEPARATELY when
the RP sent one; see the constant-time nonce pins in
test_oauth_state_nonce_timing_issue373.py). Two failure modes this guards:

* Over-requiring an OPTIONAL claim (e.g. `nbf`) rejects spec-compliant tokens —
  the 2026-05-28 ClassLink outage: requiring `nbf` blocked 100% of SSO.
* Under-requiring drops the expiry/freshness floor (VB8 #17/#22 — a token with
  no `exp`/`iat` would otherwise be accepted).

These static-source pins lock both OIDC id_token decode paths so neither
regression can recur. (Clever SSO has no id_token — it's an OAuth code flow —
so there is no require list to pin. The Supabase access-token decode in
backend/auth.py is intentionally out of scope: it is not an OIDC id_token.)
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# OIDC Core §2 REQUIRED id_token claims (nonce verified separately when sent).
OIDC_REQUIRED = {"iss", "sub", "aud", "exp", "iat"}

# Every OIDC id_token decode path in the codebase.
OIDC_DECODE_FILES = [
    "backend/routes/classlink_routes.py",
    "backend/lti.py",
]


def _require_lists(src: str):
    """Every `"require": [ ... ]` claim-set found in the source (multi-line OK)."""
    return [set(re.findall(r'"(\w+)"', body))
            for body in re.findall(r'"require"\s*:\s*\[([^\]]*)\]', src)]


def test_every_oidc_require_list_is_exactly_oidc_core_required():
    for path in OIDC_DECODE_FILES:
        src = (ROOT / path).read_text()
        lists = _require_lists(src)
        assert lists, f"{path}: expected a JWT `require` list, found none"
        for req in lists:
            assert req == OIDC_REQUIRED, (
                f"{path}: require list {sorted(req)} != OIDC Core §2 required "
                f"{sorted(OIDC_REQUIRED)}. Over-requiring (e.g. nbf) rejects "
                f"spec-compliant tokens (Hard Rule #10 / the 2026-05-28 nbf "
                f"outage); under-requiring drops the exp/iat floor (VB8 #17/#22)."
            )


def test_no_oidc_require_list_demands_nbf():
    """`nbf` is OPTIONAL per OIDC Core §2 — requiring it caused the ClassLink SSO
    outage. Pin that it is never re-added to any require list."""
    for path in OIDC_DECODE_FILES:
        for req in _require_lists((ROOT / path).read_text()):
            assert "nbf" not in req, (
                f"{path}: 'nbf' must NOT be in the require list — it is OIDC "
                f"Core §2 OPTIONAL and demanding it rejects valid id_tokens."
            )


def test_oidc_decodes_verify_signature_audience_issuer():
    """Under-strictness is worse than over-strictness: each OIDC id_token decode
    must pin RS256 (no `none`/alg-confusion) and verify audience + issuer —
    checked on the SAME decode call (the span between `.decode(` and that call's
    `"require"`), NOT file-wide, so dropping an arg can't false-pass on a string
    that happens to appear elsewhere in the file (Codex review)."""
    for path in OIDC_DECODE_FILES:
        src = (ROOT / path).read_text()
        spans = re.findall(r'\.decode\((.*?)"require"', src, re.DOTALL)
        assert spans, f"{path}: no OIDC id_token decode-with-require call found"
        for span in spans:
            assert ('algorithms=["RS256"]' in span or "algorithms=['RS256']" in span), \
                f"{path}: this id_token decode call must pin algorithms=['RS256']"
            assert "audience=" in span, f"{path}: this decode call must verify audience="
            assert "issuer=" in span, f"{path}: this decode call must verify issuer="
