import backend.auth as auth


class _U:
    def __init__(self, uid, email):
        self.id = uid
        self.email = email


def _patch(monkeypatch, links=None, users=None, sb=object()):
    monkeypatch.setattr(auth, "load_clever_links", lambda: dict(links or {}))
    saved = {}
    monkeypatch.setattr(auth, "save_clever_link", lambda cid, uid: saved.__setitem__(cid, uid))
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    monkeypatch.setattr(auth, "list_all_users", lambda s: list(users or []))
    claimed = {}
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda cid, uid: claimed.__setitem__(cid, uid))
    return saved, claimed


def test_linked_returns_uuid(monkeypatch):
    _patch(monkeypatch, links={"c1": "uuid-1"})
    assert auth.resolve_clever_user_id_or_create("c1", "t@x") == ("uuid-1", "linked")


def test_single_email_match_links(monkeypatch):
    saved, claimed = _patch(monkeypatch, users=[_U("uuid-9", "t@x")])
    out = auth.resolve_clever_user_id_or_create("c1", "T@X")
    assert out == ("uuid-9", "matched")
    assert saved == {"c1": "uuid-9"}
    assert claimed == {}                      # no claim on the match path (pre-existing UUID may collide)


def test_zero_match_creates_and_claims(monkeypatch):
    saved, claimed = _patch(monkeypatch, users=[])
    class _Res:  # noqa
        user = _U("uuid-new", "t@x")
    sb = object()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    monkeypatch.setattr(auth, "list_all_users", lambda s: [])
    monkeypatch.setattr(auth, "save_clever_link", lambda cid, uid: saved.__setitem__(cid, uid))
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda cid, uid: claimed.__setitem__(cid, uid))

    class _Admin:
        def create_user(self, payload):
            assert payload["user_metadata"]["auth_source"] == "clever"
            assert payload["user_metadata"]["approved"] is True
            return _Res()
    sb_obj = type("SB", (), {"auth": type("A", (), {"admin": _Admin()})()})()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb_obj)
    out = auth.resolve_clever_user_id_or_create("c1", "t@x", {"first": "T", "last": "X"})
    assert out == ("uuid-new", "created")
    assert saved == {"c1": "uuid-new"}
    assert claimed == {"c1": "uuid-new"}      # claim runs on create


def test_create_returns_none_id_fails_open(monkeypatch):
    # create_user succeeds but the returned object has .user.id == None.
    # Must NOT save a None link or return (None, "created") — fail open instead.
    saved, claimed = {}, {}
    monkeypatch.setattr(auth, "load_clever_links", lambda: {})
    monkeypatch.setattr(auth, "save_clever_link", lambda c, u: saved.__setitem__(c, u))
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda c, u: claimed.__setitem__(c, u))
    monkeypatch.setattr(auth, "list_all_users", lambda s: [])

    class _Res:  # noqa
        user = _U(None, "t@x")

    class _Admin:
        def create_user(self, payload): return _Res()
    sb = type("SB", (), {"auth": type("A", (), {"admin": _Admin()})()})()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    assert auth.resolve_clever_user_id_or_create("c1", "t@x") == ("clever:c1", "create_failed_legacy")
    assert saved == {} and claimed == {}


def test_ambiguous_match_fails_open(monkeypatch):
    saved, claimed = _patch(monkeypatch, users=[_U("a", "t@x"), _U("b", "t@x")])
    out = auth.resolve_clever_user_id_or_create("c1", "t@x")
    assert out == ("clever:c1", "ambiguous_legacy")
    assert saved == {} and claimed == {}      # no link, no claim, NOT blocked


def test_no_supabase_fails_open(monkeypatch):
    _patch(monkeypatch, sb=None)
    assert auth.resolve_clever_user_id_or_create("c1", "t@x") == ("clever:c1", "transient_legacy")


def test_missing_email_fails_open(monkeypatch):
    _patch(monkeypatch)
    assert auth.resolve_clever_user_id_or_create("c1", "") == ("clever:c1", "transient_legacy")


def test_create_race_reresolves_to_matched(monkeypatch):
    # create_user raises, but a parallel login already created the user;
    # the re-resolve finds exactly 1 → 'matched' (links to the racer's UUID).
    saved = {}
    seq = [[], [_U("uuid-race", "t@x")]]   # 1st match-check empty, 2nd finds the racer
    monkeypatch.setattr(auth, "load_clever_links", lambda: {})
    monkeypatch.setattr(auth, "save_clever_link", lambda c, u: saved.__setitem__(c, u))
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda c, u: None)
    monkeypatch.setattr(auth, "list_all_users", lambda s: seq.pop(0))

    class _Admin:
        def create_user(self, payload): raise RuntimeError("duplicate")
    sb = type("SB", (), {"auth": type("A", (), {"admin": _Admin()})()})()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    assert auth.resolve_clever_user_id_or_create("c1", "t@x") == ("uuid-race", "matched")
    assert saved == {"c1": "uuid-race"}


def test_create_failed_no_race_fails_open(monkeypatch):
    # create_user raises AND re-resolve finds nothing → fail open (NOT blocked).
    monkeypatch.setattr(auth, "load_clever_links", lambda: {})
    monkeypatch.setattr(auth, "save_clever_link", lambda c, u: None)
    monkeypatch.setattr(auth, "_claim_clever_text_data", lambda c, u: None)
    monkeypatch.setattr(auth, "list_all_users", lambda s: [])   # always empty

    class _Admin:
        def create_user(self, payload): raise RuntimeError("boom")
    sb = type("SB", (), {"auth": type("A", (), {"admin": _Admin()})()})()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    assert auth.resolve_clever_user_id_or_create("c1", "t@x") == ("clever:c1", "create_failed_legacy")


def test_all_legacy_outcomes_return_non_none_id(monkeypatch):
    # Fail-open contract: callers branch on `not id.startswith("clever:")`,
    # so the id must NEVER be None for any outcome.
    _patch(monkeypatch, sb=None)
    rid, _outcome = auth.resolve_clever_user_id_or_create("c1", "t@x")
    assert rid is not None and rid.startswith("clever:")


def test_claim_rekeys_text_tables(monkeypatch):
    calls = []

    class _Q:
        def __init__(self, table): self.table = table
        def update(self, payload): self._payload = payload; return self
        def eq(self, col, val): calls.append((self.table, self._payload, col, val)); return self
        def execute(self): return type("R", (), {"data": []})()

    class _SB:
        def table(self, name): return _Q(name)

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    auth._claim_clever_text_data("c1", "uuid-1")
    tables = {c[0] for c in calls}
    assert tables == {"teacher_data", "published_assessments", "student_history"}
    for table, payload, col, val in calls:
        assert payload == {"teacher_id": "uuid-1"}
        assert (col, val) == ("teacher_id", "clever:c1")


def test_claim_no_supabase_is_noop(monkeypatch):
    monkeypatch.setattr(auth, "_get_supabase", lambda: None)
    auth._claim_clever_text_data("c1", "uuid-1")   # must not raise


# ---------------------------------------------------------------------------
# Task 4: check_auth reads session user_id + sets g.teacher_id
# ---------------------------------------------------------------------------
# check_auth is nested inside init_auth(app), so it is NOT directly callable.
# Register it via init_auth and invoke the before_request hook (the pattern the
# existing auth tests use). Use an /api/... path with FLASK_ENV=production and
# no Authorization header so the Clever branch runs (not the dev-shim or
# public-prefix skip).


def test_check_auth_clever_prefers_session_user_id(monkeypatch):
    from flask import Flask, g, session
    monkeypatch.setenv("FLASK_ENV", "production")
    app = Flask(__name__); app.secret_key = "t"
    from backend.auth import init_auth
    init_auth(app)
    with app.test_request_context("/api/x"):
        session["clever_user"] = {"clever_id": "c1", "email": "t@x",
                                  "user_id": "uuid-1", "district": "d1"}
        for fn in app.before_request_funcs.get(None, []):
            fn()
        assert g.user_id == "uuid-1"
        assert g.teacher_id == "uuid-1"
        assert g.auth_source == "clever"


def test_check_auth_clever_falls_back_for_old_session(monkeypatch):
    from flask import Flask, g, session
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setattr(auth, "resolve_clever_user_id", lambda cid: f"clever:{cid}")
    app = Flask(__name__); app.secret_key = "t"
    from backend.auth import init_auth
    init_auth(app)
    with app.test_request_context("/api/x"):
        session["clever_user"] = {"clever_id": "c1", "email": "t@x", "district": "d1"}
        for fn in app.before_request_funcs.get(None, []):
            fn()
        assert g.user_id == "clever:c1"
        assert g.teacher_id == "clever:c1"
