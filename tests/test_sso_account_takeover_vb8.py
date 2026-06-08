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
    def __init__(self, uid, email, auth_source=None, forged_user_metadata=False):
        self.id = uid
        self.email = email
        # SSO-provisioned users carry auth_source in APP_metadata (service-role-
        # only; see resolve_*_or_create create paths). `forged_user_metadata=True`
        # models an attacker who set auth_source in USER_metadata via the public
        # anon key — it must NOT be trusted (the reverse-takeover bypass Codex found).
        self.user_metadata = {"auth_source": auth_source} if (auth_source and forged_user_metadata) else {}
        self.app_metadata = {"auth_source": auth_source} if (auth_source and not forged_user_metadata) else {}


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


def test_forged_user_metadata_auth_source_does_not_link(monkeypatch):
    """Reverse-takeover bypass (Codex VB8 verify): auth_source in USER_metadata is
    client-settable via the PUBLIC anon key, so an attacker self-provisions a
    password account tagged 'clever' for the victim's email. It must NOT be treated
    as SSO-provisioned — only app_metadata (service-role-set) is trusted — so the
    real victim's later Clever login does NOT link to the attacker's account."""
    saved, claimed = _patch(
        monkeypatch,
        users=[_U("attacker-uuid", "victim@school.edu",
                  auth_source="clever", forged_user_metadata=True)],
    )
    out = auth.resolve_clever_user_id_or_create("real-clever-id", "victim@school.edu")
    assert out == ("clever:real-clever-id", "unverified_email_legacy")
    assert saved == {}   # never linked to the attacker's forged account
    assert claimed == {}
