"""
Shared fixtures for ClassLink OIDC/id_token tests.

Used by:
  - tests/test_classlink_sso.py   (Task 2 — id_token validation)
  - tests/test_classlink_sso.py   (Task 3 — state/nonce hardening)

RSA keypair is generated once per test session (2048-bit, RS256).
The public key is exposed as `classlink_public_key` so tests can wire it
into mock JWKS clients without a real network call.
"""

import time
import pytest
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa


# ── RSA keypair (session-scoped — expensive to generate) ─────────────────────

@pytest.fixture(scope="session")
def classlink_rsa_keypair():
    """Return (private_key, public_key) RSAPrivateKey/RSAPublicKey pair."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    return priv, pub


@pytest.fixture(scope="session")
def classlink_private_key(classlink_rsa_keypair):
    return classlink_rsa_keypair[0]


@pytest.fixture(scope="session")
def classlink_public_key(classlink_rsa_keypair):
    return classlink_rsa_keypair[1]


# ── id_token factory ──────────────────────────────────────────────────────────

def make_id_token(
    private_key,
    *,
    iss="https://launchpad.classlink.com",
    aud="test-client-id",
    sub="cl-user-123",
    email="teacher@example.com",
    given_name="Jane",
    family_name="Smith",
    role="teacher",
    exp_offset=3600,
    kid="test-kid",
    nonce=None,
    extra_claims=None,
):
    """Build and sign a ClassLink-style id_token (RS256).

    Args:
        private_key: cryptography RSAPrivateKey
        exp_offset: seconds from now for exp claim (negative = expired)
        nonce: optional nonce claim (omitted from token when None)
        extra_claims: dict merged on top of defaults
    """
    now = int(time.time())
    claims = {
        "iss": iss,
        "aud": aud,
        "exp": now + exp_offset,
        "iat": now,
        "nbf": now,
        "sub": sub,
        "email": email,
        "given_name": given_name,
        "family_name": family_name,
        "Role": role,
    }
    if nonce is not None:
        claims["nonce"] = nonce
    if extra_claims:
        claims.update(extra_claims)
    return pyjwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid, "alg": "RS256"},
    )


@pytest.fixture
def make_classlink_id_token(classlink_private_key):
    """Return a factory function that produces signed id_tokens.

    Usage in tests:
        token = make_classlink_id_token(exp_offset=-1)   # expired
        token = make_classlink_id_token(extra_claims={"nonce": "abc"})
    """
    def _factory(**kwargs):
        return make_id_token(classlink_private_key, **kwargs)
    return _factory
