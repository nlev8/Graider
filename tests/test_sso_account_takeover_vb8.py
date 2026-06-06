"""VB8 #13 — Clever SSO account-takeover regression.

`resolve_clever_user_id_or_create` used to auto-link a Clever login to ANY
pre-existing Supabase account whose email matched the Clever-asserted email —
with NO verification that the matched account was itself created via SSO. That
let an attacker who signed into Clever with a victim's email take over the
victim's *password* (non-SSO) Graider account.

Secure behavior (fix): a single email match only auto-links when the matched
account is itself an SSO-provisioned account (user_metadata.auth_source in
{clever, classlink}). A match against a NON-SSO account (e.g. a password
signup) does NOT link — it fails OPEN to the isolated clever:{id} legacy
namespace (new outcome 'unverified_email_legacy'), exactly like an ambiguous
match. First-time Clever provisioning (zero matches → create) is unaffected.
"""
import backend.auth as auth


class _U:
    def __init__(self, uid, email, auth_source=None):
        self.id = uid
        self.email = email
        # Mirror the supabase-py user shape: SSO-provisioned users carry
        # auth_source in user_metadata (see resolve_*_or_create create paths).
        self.user_metadata = {"auth_source": auth_source} if auth_source else {}


def _patch(monkeypatch, users=None):
    monkeypatch.setattr(auth, "load_clever_links", lambda: {})
    saved = {}
    monkeypatch.setattr(auth, "save_clever_link", lambda cid, uid: saved.__setitem__(cid, uid))
    monkeypatch.setattr(auth, "_get_supabase", lambda: object())
    monkeypatch.setattr(auth, "list_all_users", lambda s: list(users or []))
    claimed = {}
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda cid, uid: claimed.__setitem__(cid, uid))
    return saved, claimed


def test_match_against_non_sso_account_does_not_link(monkeypatch):
    """Account-takeover guard: a single email match to a password (non-SSO)
    account MUST NOT auto-link. Fails open to the isolated legacy namespace."""
    saved, claimed = _patch(monkeypatch, users=[_U("victim-uuid", "victim@school.edu")])
    out = auth.resolve_clever_user_id_or_create("attacker-clever-id", "victim@school.edu")
    assert out == ("clever:attacker-clever-id", "unverified_email_legacy")
    # CRITICAL: never persisted a link into the victim's account.
    assert saved == {}
    assert claimed == {}


def test_match_against_sso_account_still_links(monkeypatch):
    """Legitimate re-link: a single email match to an SSO-provisioned account
    (auth_source set) still auto-links — that account is trusted."""
    saved, _ = _patch(
        monkeypatch,
        users=[_U("sso-uuid", "teacher@school.edu", auth_source="clever")],
    )
    out = auth.resolve_clever_user_id_or_create("clever-id", "TEACHER@school.edu")
    assert out == ("sso-uuid", "matched")
    assert saved == {"clever-id": "sso-uuid"}


def test_match_against_classlink_account_links(monkeypatch):
    """An account first provisioned via ClassLink SSO is also trusted to link
    from a Clever login of the same identity (both are district-trusted SSO)."""
    saved, _ = _patch(
        monkeypatch,
        users=[_U("cl-uuid", "teacher@school.edu", auth_source="classlink")],
    )
    out = auth.resolve_clever_user_id_or_create("clever-id", "teacher@school.edu")
    assert out == ("cl-uuid", "matched")
    assert saved == {"clever-id": "cl-uuid"}
