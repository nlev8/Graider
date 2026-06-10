"""SSO-parity hardening (audit follow-up to VB8): VB12 + VB13.

VB12 — Clever student-session must NOT fall back to an unscoped email match.
  _create_clever_student_session looked up the student by Clever id and, on a
  miss, fell back to a GLOBAL `students.email` match with no tenant/teacher
  scope — so a Clever student whose id matched no roster row could be matched
  by a shared/reused email into a DIFFERENT teacher's class. ClassLink fails
  closed here (no email fallback); Clever should too.

VB13 — the LTI 1.3 launch-JWT decode must enforce the OIDC-required claims.
  validate_launch_jwt's jwt.decode had no `require` list, so an id_token with
  no `exp`/`iat` was accepted (no expiry/freshness floor). Add the OIDC Core §2
  required set to `require` (NOT nbf — VB8 lesson).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.routes.clever_routes import _create_clever_student_session


# ──────────────────────────────────────────────────────────────────
# VB12 — Clever student session: no unscoped email fallback
# ──────────────────────────────────────────────────────────────────

def _sb_clever(by_id_rows, by_email_rows, enroll_rows):
    """Supabase mock that returns DIFFERENT students rows depending on whether
    the query filtered by student_id_number or by email."""
    sb = MagicMock()

    def _table(name):
        if name == "students":
            q = MagicMock()
            state = {}
            q.select.return_value = q

            def _eq(col, _val):
                state["col"] = col
                return q

            q.eq.side_effect = _eq

            def _execute():
                col = state.get("col")
                if col == "student_id_number":
                    rows = by_id_rows
                elif col == "email":
                    rows = by_email_rows
                else:
                    rows = []
                return MagicMock(data=list(rows))

            q.execute.side_effect = _execute
            return q
        if name == "class_students":
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.limit.return_value = q
            q.execute.return_value = MagicMock(data=list(enroll_rows))
            return q
        if name == "student_sessions":
            q = MagicMock()
            q.insert.return_value = q
            q.execute.return_value = MagicMock(data=[{"id": "sess-1"}])
            return q
        return MagicMock()

    sb.table.side_effect = _table
    return sb


_STUDENT = {
    "id": "db-stu-1", "first_name": "Sam", "last_name": "One",
    "email": "shared@school.edu", "student_id_number": "clever-X", "period": "3",
}
_ENROLL = [{"class_id": "c1", "classes": {"id": "c1", "name": "Math", "subject": "math"}}]


def test_clever_session_does_not_fall_back_to_unscoped_email():
    # Clever id matches NO students row, but the email collides with another
    # tenant's student. The session must NOT be minted (fail closed).
    sb = _sb_clever(by_id_rows=[], by_email_rows=[_STUDENT], enroll_rows=_ENROLL)
    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
        result = _create_clever_student_session("clever-X", "shared@school.edu")
    assert result == {"status": "not_found"}, (
        "Clever student session fell back to an unscoped email match "
        "(cross-tenant exposure)"
    )


def test_clever_session_by_clever_id_still_works():
    # Control: a genuine Clever-id match with a single enrollment still mints.
    sb = _sb_clever(by_id_rows=[_STUDENT], by_email_rows=[], enroll_rows=_ENROLL)
    with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
        result = _create_clever_student_session("clever-X", "x@school.edu")
    assert result is not None


# ──────────────────────────────────────────────────────────────────
# VB13 — LTI launch JWT must require exp/iat (+ iss/aud/sub)
# ──────────────────────────────────────────────────────────────────

def _platform_config():
    return {
        "jwks_uri": "https://platform.example/.well-known/jwks.json",
        "client_id": "test-client",
        "issuer": "https://platform.example",
    }


def _mint(claims):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = pyjwt.encode(claims, priv, algorithm="RS256")
    return token, priv.public_key()


def test_lti_launch_jwt_missing_exp_is_rejected():
    from backend.lti import validate_launch_jwt
    # Signature-valid token that is MISSING exp/iat (and message_type).
    token, pub = _mint({
        "iss": "https://platform.example", "aud": "test-client", "sub": "u1",
    })
    with patch("jwt.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = MagicMock(key=pub)
        # Post-fix: the `require` list makes the missing exp fail INSIDE
        # jwt.decode → wrapped as "JWT validation failed". Pre-fix the decode
        # succeeds and it instead fails later on message_type — so matching the
        # decode-wrapper message is what makes this red→green.
        with pytest.raises(ValueError, match="JWT validation failed"):
            validate_launch_jwt(token, _platform_config())


def test_lti_launch_jwt_with_required_claims_passes_the_require_check():
    from backend.lti import validate_launch_jwt
    # Has all OIDC-required claims → must get PAST the require check and fail
    # only later (on message_type), proving the require list doesn't over-reject.
    token, pub = _mint({
        "iss": "https://platform.example", "aud": "test-client", "sub": "u1",
        "exp": 9999999999, "iat": 1000000000,
    })
    with patch("jwt.PyJWKClient") as mock_cls:
        mock_cls.return_value.get_signing_key_from_jwt.return_value = MagicMock(key=pub)
        with pytest.raises(ValueError, match="message_type"):
            validate_launch_jwt(token, _platform_config())
