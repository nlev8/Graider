import backend.auth as auth


def test_save_and_load_classlink_link(monkeypatch):
    store = {}
    monkeypatch.setattr("backend.storage.save",
                        lambda key, data, scope: store.__setitem__((key, scope), data))
    monkeypatch.setattr("backend.storage.list_keys",
                        lambda prefix, scope: [k for (k, s) in store if k.startswith(prefix)])
    monkeypatch.setattr("backend.storage.load",
                        lambda key, scope: store.get((key, scope)))

    auth.save_classlink_link("classlink:2284:abc", "uuid-1")
    links = auth.load_classlink_links()
    assert links.get("classlink:2284:abc") == "uuid-1"


def test_storage_maps_classlink_link_prefix(tmp_path, monkeypatch):
    """File backend must route classlink_link: keys to a real path."""
    from backend.storage import _key_to_filepath
    path = _key_to_filepath("classlink_link:classlink:2284:abc", teacher_id="some-teacher")
    assert path is not None
    assert "classlink_links" in path


class _FakeUser:
    def __init__(self, uid, email):
        self.id = uid
        self.email = email


class _FakeCreateResult:
    def __init__(self, uid):
        self.user = _FakeUser(uid, None)


def _patch_links(monkeypatch, initial=None):
    store = dict(initial or {})
    monkeypatch.setattr(auth, "load_classlink_links", lambda: dict(store))
    monkeypatch.setattr(auth, "save_classlink_link",
                        lambda guid, uid: store.__setitem__(guid, uid))
    return store


def test_resolve_missing_email_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: (_ for _ in ()).throw(AssertionError("no sb")))
    assert auth.resolve_classlink_user_id("classlink:2284:x", "", {"first": "A"}) is None


def test_resolve_returns_existing_link(monkeypatch):
    _patch_links(monkeypatch, {"classlink:2284:x": "uuid-existing"})
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") == "uuid-existing"


def test_resolve_single_email_match_links(monkeypatch):
    store = _patch_links(monkeypatch)
    sb = object()
    monkeypatch.setattr(auth, "_get_supabase", lambda: sb)
    monkeypatch.setattr(auth, "list_all_users", lambda _sb: [_FakeUser("uuid-match", "A@B.com")])
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com")
    assert uid == "uuid-match"
    assert store["classlink:2284:x"] == "uuid-match"


def test_resolve_multiple_matches_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: object())
    monkeypatch.setattr(auth, "list_all_users",
                        lambda _sb: [_FakeUser("u1", "a@b.com"), _FakeUser("u2", "a@b.com")])
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") is None


def test_resolve_creates_user_when_no_match(monkeypatch):
    store = _patch_links(monkeypatch)
    created = {}

    class _Admin:
        def create_user(self, attrs):
            created.update(attrs)
            return _FakeCreateResult("uuid-new")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    monkeypatch.setattr(auth, "list_all_users", lambda _sb: [])
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com", {"first": "Jo", "last": "Lee"})
    assert uid == "uuid-new"
    assert store["classlink:2284:x"] == "uuid-new"
    assert created["email"] == "a@b.com"
    assert created["email_confirm"] is True
    assert created["user_metadata"]["approved"] is True
    assert created["user_metadata"]["auth_source"] == "classlink"


def test_resolve_create_race_recovers_by_email(monkeypatch):
    store = _patch_links(monkeypatch)
    calls = {"n": 0}

    def _users(_sb):
        calls["n"] += 1
        return [] if calls["n"] == 1 else [_FakeUser("uuid-winner", "a@b.com")]

    class _Admin:
        def create_user(self, attrs):
            raise Exception("email address already registered")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    monkeypatch.setattr(auth, "list_all_users", _users)
    uid = auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com")
    assert uid == "uuid-winner"
    assert store["classlink:2284:x"] == "uuid-winner"


def test_resolve_no_supabase_fails_closed(monkeypatch):
    _patch_links(monkeypatch)
    monkeypatch.setattr(auth, "_get_supabase", lambda: None)
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") is None


def test_resolve_create_race_recheck_ambiguous_fails_closed(monkeypatch):
    """If create fails and the email recheck now finds >1 user, fail closed (None)."""
    _patch_links(monkeypatch)

    class _Admin:
        def create_user(self, attrs):
            raise Exception("boom")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    # First scan: no match (drives create). After create fails, recheck returns 2 → ambiguous.
    calls = {"n": 0}
    def _users(_sb):
        calls["n"] += 1
        return [] if calls["n"] == 1 else [_FakeUser("u1", "a@b.com"), _FakeUser("u2", "a@b.com")]
    monkeypatch.setattr(auth, "list_all_users", _users)
    assert auth.resolve_classlink_user_id("classlink:2284:x", "a@b.com") is None


def test_resolve_create_failure_log_does_not_leak_email(monkeypatch, caplog):
    """The create-failure log line must not contain the raw email (FERPA)."""
    import logging
    _patch_links(monkeypatch)

    class _Admin:
        def create_user(self, attrs):
            raise Exception("User with email secret-leak@district.org already registered")

    class _Auth:
        admin = _Admin()

    class _SB:
        auth = _Auth()

    monkeypatch.setattr(auth, "_get_supabase", lambda: _SB())
    monkeypatch.setattr(auth, "list_all_users", lambda _sb: [])  # no match, no recovery
    with caplog.at_level(logging.WARNING):
        auth.resolve_classlink_user_id("classlink:2284:x", "secret-leak@district.org")
    assert "secret-leak@district.org" not in caplog.text
