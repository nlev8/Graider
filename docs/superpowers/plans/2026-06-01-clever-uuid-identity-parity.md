# Clever → Supabase UUID Identity Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve unlinked Clever teachers to a real Supabase Auth UUID at the OAuth callback (link-or-create, **fail-open** to `clever:{id}`), so they stop crashing on UUID `teacher_id` columns — without ever blocking a currently-working login.

**Architecture:** Mirror the proven ClassLink #604 pattern but **fail open**: a new `resolve_clever_user_id_or_create` returns `(id, outcome)` and falls back to today's `clever:{id}` on any non-resolution (Clever has live unlinked users; `clever:{id}` is an isolated namespace, so falling back never blocks or mis-merges). Only UUID outcomes get the session `user_id`, the DB roster sync, and an idempotent data-claim (create-path only). `check_auth` reads the session-stored UUID; the delete-data gate and `/api/clever/session` are updated to be id-shape-agnostic.

**Tech Stack:** Python/Flask, Supabase, pytest.

**Spec:** `docs/superpowers/specs/2026-06-01-clever-uuid-identity-parity-design.md`
**Class:** B (auth/identity) ⇒ **opus** code-quality reviewer; manual merge after clean review.
**Branch:** `feature/clever-uuid-identity`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/auth.py` | identity resolution | NEW `resolve_clever_user_id_or_create`, NEW `_claim_clever_text_data`; `check_auth` Clever branch reads session `user_id` + sets `g.teacher_id` |
| `backend/routes/clever_routes.py` | OAuth callback, session, delete | callback uses new resolver + UUID-only roster sync; delete-data gate id-shape-agnostic; `/api/clever/session` returns `user_id` |
| `tests/test_clever_identity.py` | resolver + claim unit tests | Create |
| `tests/test_clever_callback.py` / `tests/test_clever_compliance.py` | regression | run unchanged |

Order: resolver → claim → callback wiring → check_auth → delete gate → session endpoint. Each task independently committable.

**Read before starting:** `backend/auth.py` lines 1-162 (the Clever/ClassLink link helpers + `resolve_classlink_user_id`, the proven twin) and `check_auth` ~297-317; `backend/routes/clever_routes.py` the teacher-callback success path (the `session["clever_user"] = {...}` block, the account-merge block, and the roster-sync block), `clever_session_check` (~558-600), `clever_delete_data` (~762-790).

---

### Task 1: `resolve_clever_user_id_or_create` (fail-open resolver)

**Files:**
- Modify: `backend/auth.py` (add after `resolve_classlink_user_id`)
- Test: `tests/test_clever_identity.py` (Create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_clever_identity.py`:

```python
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
```

(All six outcomes are now pinned: `linked`, `matched`, `created`, `ambiguous_legacy`, `transient_legacy` (no-supabase + missing-email), `create_failed_legacy`, plus the create-race success path and the non-None fail-open contract.)

- [ ] **Step 2: Run → FAIL**

Run: `source venv/bin/activate && pytest tests/test_clever_identity.py -v`
Expected: FAIL — `AttributeError: module 'backend.auth' has no attribute 'resolve_clever_user_id_or_create'`.

- [ ] **Step 3: Implement** — add to `backend/auth.py` after `resolve_classlink_user_id`:

```python
def resolve_clever_user_id_or_create(clever_id, email, name=None):
    """Resolve a Clever id to a real Supabase Auth UUID (link-or-create), but
    FAIL OPEN to the legacy clever:{id} namespace on any non-resolution. Unlike
    resolve_classlink_user_id (which fails closed), Clever has live unlinked
    users and clever:{id} is an isolated namespace, so falling back never blocks
    login or merges into a wrong account. Returns (id, outcome) where outcome is
    one of: 'linked' | 'matched' | 'created' | 'ambiguous_legacy' |
    'transient_legacy' | 'create_failed_legacy'. UUID outcomes -> real UUID;
    *_legacy outcomes -> f'clever:{clever_id}'. The 'created' path also re-keys
    the teacher's TEXT-keyed data via _claim_clever_text_data."""
    legacy = f"clever:{clever_id}"

    linked = load_clever_links().get(clever_id)
    if linked:
        return linked, "linked"

    email = (email or "").strip()
    if not email:
        logger.warning("Clever resolve: missing email; failing open to legacy")
        return legacy, "transient_legacy"

    name = name or {}
    try:
        sb = _get_supabase()
        if not sb:
            logger.warning("Clever resolve: no Supabase client; failing open to legacy")
            return legacy, "transient_legacy"

        def _email_matches():
            return [
                u for u in list_all_users(sb)
                if getattr(u, 'email', None) and u.email.lower() == email.lower()
            ]

        matches = _email_matches()
        if len(matches) == 1:
            save_clever_link(clever_id, matches[0].id)
            return matches[0].id, "matched"
        if len(matches) > 1:
            logger.warning("Clever resolve: %d users match email — failing open to legacy", len(matches))
            return legacy, "ambiguous_legacy"

        try:
            res = sb.auth.admin.create_user({
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": {
                    "approved": True,
                    "first_name": name.get('first', ''),
                    "last_name": name.get('last', ''),
                    "auth_source": "clever",
                },
            })
            new_id = res.user.id
            save_clever_link(clever_id, new_id)
            _claim_clever_text_data(clever_id, new_id)
            return new_id, "created"
        except Exception as create_err:
            logger.warning("Clever resolve: create_user failed (%s); re-resolving by email",
                           type(create_err).__name__)
            recheck = _email_matches()
            if len(recheck) == 1:
                save_clever_link(clever_id, recheck[0].id)
                return recheck[0].id, "matched"
            return legacy, "create_failed_legacy"
    except Exception as e:
        logger.warning("Clever resolve failed (non-fatal): %s", type(e).__name__)
        sentry_sdk.capture_exception(e)
        return legacy, "transient_legacy"
```

(`_claim_clever_text_data` is defined in Task 2; the import order is fine — it's resolved at call time. To keep Task 1's tests green standalone, the tests monkeypatch `_claim_clever_text_data`, so define a stub now if running Task 1 in isolation, or do Task 2 first. Recommended: implement Task 2's function in the same edit pass.)

- [ ] **Step 4: Run → PASS**

Run: `pytest tests/test_clever_identity.py -v` (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py tests/test_clever_identity.py
git commit -m "feat(clever): resolve_clever_user_id_or_create — fail-open link-or-create [Class B]"
```

---

### Task 2: `_claim_clever_text_data` (idempotent re-key, create-path only)

**Files:**
- Modify: `backend/auth.py`
- Test: `tests/test_clever_identity.py`

- [ ] **Step 1: Write the failing test** — append:

```python
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
```

- [ ] **Step 2: Run → FAIL**

Run: `pytest tests/test_clever_identity.py -k claim -v` — FAIL (no attribute `_claim_clever_text_data`).

- [ ] **Step 3: Implement** — add to `backend/auth.py` (place ABOVE `resolve_clever_user_id_or_create` so it's defined first):

```python
def _claim_clever_text_data(clever_id, uuid):
    """Re-key the teacher's TEXT-keyed rows from clever:{id} -> uuid. Called
    ONLY on the create path (the UUID is brand-new, so a blind UPDATE cannot
    collide with a pre-existing (teacher_id, data_key) PK). Best-effort,
    non-fatal. NOTE: submissions has no teacher_id (it follows join_code), so
    it is intentionally excluded."""
    legacy = f"clever:{clever_id}"
    try:
        sb = _get_supabase()
        if not sb:
            return
        for table in ("teacher_data", "published_assessments", "student_history"):
            try:
                sb.table(table).update({"teacher_id": uuid}).eq("teacher_id", legacy).execute()
            except Exception as e:
                logger.warning("Clever data-claim on %s failed (non-fatal): %s", table, type(e).__name__)
    except Exception as e:
        logger.warning("Clever data-claim failed (non-fatal): %s", type(e).__name__)
        sentry_sdk.capture_exception(e)
```

- [ ] **Step 4: Run → PASS**

Run: `pytest tests/test_clever_identity.py -v` (8 passed — Task 1 + Task 2).

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py tests/test_clever_identity.py
git commit -m "feat(clever): _claim_clever_text_data — re-key TEXT tables on create [Class B]"
```

---

### Task 3: Wire resolver into the Clever teacher callback (UUID-only roster sync)

**Files:**
- Modify: `backend/routes/clever_routes.py` (teacher-callback success path)
- Test: `tests/test_clever_callback.py` (add) — or `tests/test_clever_identity.py` if the callback test harness lives there; READ `tests/test_clever_callback.py` first for the existing callback-drive pattern.

- [ ] **Step 1: Write the failing test**

Add a test that drives the teacher callback with a stubbed `resolve_clever_user_id_or_create` and asserts: (a) on a UUID outcome, `session['clever_user']['user_id']` is set and `_background_roster_sync` is started with the UUID; (b) on a legacy outcome, `user_id` is NOT set and roster sync is NOT started. Mirror the existing callback test's monkeypatching (it already stubs the Clever token exchange + user fetch). Concretely, patch `clever_routes.resolve_clever_user_id_or_create` to return `("uuid-7", "created")` then assert; and `("clever:c1", "ambiguous_legacy")` then assert no sync. Capture sync starts by monkeypatching `clever_routes._background_roster_sync` and `threading.Thread` (or assert on a recorded call list).

READ the existing `tests/test_clever_callback.py` and reuse its fixtures; the load-bearing assertions are the two above.

- [ ] **Step 2: Run → FAIL** (callback still calls the old merge/`resolve_clever_user_id` path).

- [ ] **Step 3: Implement** — in `backend/routes/clever_routes.py`, in the teacher-callback success path:

  (a) Add import at top: `from backend.auth import ... , resolve_clever_user_id_or_create` (extend the existing `from backend.auth import` line).

  (b) **Replace the account-merge block** (the `existing_links = load_clever_links()` block that does the 1-match `save_clever_link`) AND the line `teacher_id = resolve_clever_user_id(clever_id)` in the roster-sync block with:

```python
    # Resolve to a real Supabase UUID (link-or-create), failing OPEN to clever:{id}
    # so a >1-match / outage never blocks a currently-working teacher.
    resolved_id, outcome = resolve_clever_user_id_or_create(
        clever_id, clever_email, clever_user.get("name"))
    is_uuid = not str(resolved_id).startswith("clever:")
    if is_uuid:
        session["clever_user"]["user_id"] = resolved_id
    logger.info("Clever teacher resolve: outcome=%s linked=%s", outcome, is_uuid)
```

  (c) In the roster-sync block, gate the sync on `is_uuid` and pass `resolved_id`:

```python
    from backend.api_keys import resolve_clever_district_token
    district_token = resolve_clever_district_token(clever_user.get("district", "") or None)
    if district_token and is_uuid:
        thread = threading.Thread(
            target=_background_roster_sync,
            args=(district_token, resolved_id),
            daemon=True,
        )
        thread.start()
```

(`clever_email` is already defined earlier in the callback; if not, set `clever_email = clever_user.get("email", "")` just above.) Keep the existing AUDIT log line; it can keep using `clever_user`.

- [ ] **Step 4: Run → PASS** — the new test + `pytest tests/test_clever_callback.py -v`.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clever_routes.py tests/test_clever_callback.py
git commit -m "feat(clever): callback resolves to UUID; roster sync UUID-only [Class B]"
```

---

### Task 4: `check_auth` reads session `user_id` + sets `g.teacher_id`

**Files:**
- Modify: `backend/auth.py` (`check_auth` Clever branch, ~line 297-304)
- Test: `tests/test_clever_identity.py`

- [ ] **Step 1: Write the failing test** — append (drive `check_auth` via a Flask test request context; mirror how `tests/test_auth_*.py` builds a request context, or use the app fixture):

```python
def test_check_auth_clever_prefers_session_user_id(monkeypatch):
    from flask import Flask, g
    app = Flask(__name__)
    monkeypatch.setattr(auth, "_get_jwks_client", lambda: None)
    with app.test_request_context("/api/x"):
        from flask import session
        session["clever_user"] = {"clever_id": "c1", "email": "t@x",
                                  "user_id": "uuid-1", "district": "d1"}
        auth.check_auth()
        assert g.user_id == "uuid-1"
        assert g.teacher_id == "uuid-1"
        assert g.auth_source == "clever"


def test_check_auth_clever_falls_back_for_old_session(monkeypatch):
    from flask import Flask, g
    app = Flask(__name__)
    monkeypatch.setattr(auth, "resolve_clever_user_id", lambda cid: f"clever:{cid}")
    with app.test_request_context("/api/x"):
        from flask import session
        session["clever_user"] = {"clever_id": "c1", "email": "t@x", "district": "d1"}
        auth.check_auth()
        assert g.user_id == "clever:c1"
        assert g.teacher_id == "clever:c1"
```

(If `check_auth` early-returns for non-`/api/` paths or dev-shim, use an `/api/...` path and ensure `FLASK_ENV` isn't `development`; set `monkeypatch.setenv("FLASK_ENV", "production")` and ensure no `Authorization` header.)

- [ ] **Step 2: Run → FAIL** (current branch always calls `resolve_clever_user_id` and never sets `g.teacher_id`).

- [ ] **Step 3: Implement** — replace the Clever branch in `check_auth`:

```python
        # Clever SSO session (cookie-based, set during OAuth callback).
        # Prefer the UUID resolved + stored at callback (clever_user['user_id']);
        # fall back to the cheap resolver for pre-existing sessions.
        clever_user = session.get('clever_user') if hasattr(session, 'get') else None
        if clever_user and not has_bearer:
            g.user_id = clever_user.get('user_id') or resolve_clever_user_id(clever_user['clever_id'])
            g.teacher_id = g.user_id
            g.user_email = clever_user.get('email', '')
            g.auth_source = 'clever'
            g.district_id = clever_user.get('district', '')
            return None
```

- [ ] **Step 4: Run → PASS** — `pytest tests/test_clever_identity.py -v` + `pytest tests/ -k "auth and clever" -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py tests/test_clever_identity.py
git commit -m "feat(clever): check_auth reads session user_id + sets g.teacher_id [Class B]"
```

---

### Task 5: Delete-data gate id-shape-agnostic + legacy-file cleanup (FERPA)

**Files:**
- Modify: `backend/routes/clever_routes.py` (`clever_delete_data`, ~line 762-790)
- Test: **`tests/test_clever_routes_gaps.py`** (`TestDeleteData`) — this file **pins the bug** and MUST be updated (Codex review).

> **CROSS-CUTTING (Codex finding):** `tests/test_clever_routes_gaps.py::TestDeleteData::test_non_clever_user_returns_403` currently asserts a **UUID-linked Clever user gets 403** — it pins the *bug* as correct behavior. The fix flips that, so this test MUST be rewritten, not just added to. (This is the "existing test pins old behavior" trap from `workflow.md`.)

- [ ] **Step 1: Rewrite the bug-pinning test + add the cleanup test** in `tests/test_clever_routes_gaps.py` (`TestDeleteData`). Replace `test_non_clever_user_returns_403` (which wrongly 403s a linked Clever user) with the correct semantics, and add a legacy-file-cleanup assertion. Reuse the file's existing `_make_app` / `_logged_in_session` / Supabase-mock helpers:

```python
    def test_linked_clever_uuid_user_can_delete(self):
        # A UUID-LINKED Clever teacher (g.teacher_id is a UUID, but the session
        # IS a Clever session) must be allowed to delete — NOT 403.
        from backend.routes.clever_routes import clever_bp
        from flask import g, session as flask_session
        app = Flask(__name__); app.secret_key = "t"
        app.register_blueprint(clever_bp)

        @app.before_request
        def _linked_uid():
            if flask_session.get("clever_user"):
                g.user_id = "supabase-uuid-1"
                g.teacher_id = "supabase-uuid-1"
                g.clever_user = flask_session["clever_user"]
        with app.test_client() as client:
            _logged_in_session(client)
            resp = client.post("/api/clever/delete-data")
        assert resp.status_code != 403          # linked Clever user CAN delete

    def test_non_clever_session_returns_403(self):
        # No clever_user in session → genuinely not a Clever user → 403.
        from backend.routes.clever_routes import clever_bp
        app = Flask(__name__); app.secret_key = "t"
        app.register_blueprint(clever_bp)
        with app.test_client() as client:
            resp = client.post("/api/clever/delete-data")
        # @require_clever_session rejects (401/403) when there's no clever session.
        assert resp.status_code in (401, 403)
```

(If `@require_clever_session` returns 401 for no-session, the second test asserts that; the load-bearing change is that a **linked UUID** Clever session is no longer 403'd.)

- [ ] **Step 2: Run → FAIL** — `pytest tests/test_clever_routes_gaps.py::TestDeleteData -v` (the new linked-user test fails: current gate 403s it).

- [ ] **Step 3: Implement** — in `clever_delete_data`, replace the gate AND add legacy-file cleanup:

```python
    # @require_clever_session already guarantees a Clever session; gate on its
    # presence (NOT the id prefix — UUID-linked Clever teachers have a non-
    # 'clever:' teacher_id but are still Clever users entitled to delete).
    if not g.get("clever_user"):
        return jsonify({"error": "Not a Clever user"}), 403
    teacher_id = g.teacher_id
    clever_id = g.clever_user.get("clever_id", "")

    try:
        result = delete_clever_data(teacher_id)
        # FERPA: also clean any legacy clever:{id}-keyed local files written
        # BEFORE this teacher was linked to a UUID (delete_clever_data keys
        # files by teacher_id.replace(':','_'), so UUID-keyed deletion misses
        # the old clever_{id} files). No-op when none exist.
        if clever_id and not str(teacher_id).startswith("clever:"):
            try:
                result["legacy_cleanup"] = delete_clever_data(f"clever:{clever_id}")
            except Exception as e:
                logger.warning("Legacy Clever file cleanup failed (non-fatal): %s", type(e).__name__)
```

(Keep the existing Supabase-deletion block below unchanged — it already deletes by `teacher_id` (the UUID), which is correct, since `_claim_clever_text_data` already migrated the TEXT-keyed Supabase rows on create.)

- [ ] **Step 4: Run → PASS** — `pytest tests/test_clever_routes_gaps.py -v` + `pytest tests/ -k "clever and delete" -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clever_routes.py tests/test_clever_routes_gaps.py
git commit -m "fix(clever): delete-data gate id-shape-agnostic + legacy-file cleanup; fix bug-pinning test [Class B]"
```

---

### Task 6: `/api/clever/session` returns `user_id`

**Files:**
- Modify: `backend/routes/clever_routes.py` (`clever_session_check`, ~line 558-600)
- Test: `tests/test_clever_callback.py`

- [ ] **Step 1: Write the failing test** — call `GET /api/clever/session` with `session['clever_user']={'clever_id':'c1','user_id':'uuid-1', 'type':'teacher', ...}` and assert the JSON includes `"user_id": "uuid-1"` and `"account_linked": True`. Reuse the existing session-check test harness.

- [ ] **Step 2: Run → FAIL** (response has no `user_id`).

- [ ] **Step 3: Implement** — in `clever_session_check`, change the resolver line and add the field:

```python
    resolved_id = clever_user.get("user_id") or resolve_clever_user_id(clever_user["clever_id"])
```

and add to the returned `jsonify({...})`:

```python
        "user_id": resolved_id,
```

(Keep `"account_linked": not resolved_id.startswith("clever:")` — still correct.)

- [ ] **Step 4: Run → PASS** — the new test + `pytest tests/ -k "clever and session" -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/clever_routes.py tests/test_clever_callback.py
git commit -m "feat(clever): /api/clever/session returns resolved user_id [Class B]"
```

---

## Per-Branch Verification (before PR)

- [ ] Full suite: `source venv/bin/activate && pytest -q --ignore=tests/load` — green (or any failure *proven* pre-existing via `git checkout main -- <file>` per workflow.md Hard Rule #1).
- [ ] Cross-cutting grep: `for f in backend/auth.py backend/routes/clever_routes.py; do grep -rln "$f" tests/; done` — run each surfaced test (esp. `tests/test_sis_alerting.py` if line numbers shifted in clever_routes — pin scan per Hard Rule #3).
- [ ] **Clever compliance non-regression:** `pytest tests/test_clever_compliance.py tests/test_clever_callback.py tests/test_clever_routes_gaps.py -q` (Task 5 rewrote a `TestDeleteData` case — confirm the whole file is green).
- [ ] **Periodic-sync confirmation (Codex finding):** `backend/routes/sync_routes.py:218-228` reverse-resolves UUID→clever_id via `load_clever_links()`. A `created`/`matched` teacher now HAS a link, so the daily cron resolves them (previously 0-match unlinked teachers were skipped with "Could not resolve Clever ID"). Run `pytest tests/ -k "sync" -q` to confirm no regression; this is a net improvement, not a break.
- [ ] **ClassLink non-regression** (shared `auth.py`): `pytest tests/test_classlink_identity.py tests/test_classlink_sso.py -q`.
- [ ] `ruff check backend/auth.py backend/routes/clever_routes.py`; `bandit -q -r` the same.
- [ ] No circular import: `python -c "import backend.app" && echo OK`.
- [ ] Spec reviewer ✅ then **opus** code-quality reviewer ✅ (Class B).
- [ ] GitNexus reindex: `npx gitnexus analyze --embeddings`.
- [ ] PR body: Class B; spec/plan refs; the **fail-open** decision called out; deferred 1-match-link orphan (with fix sketch) noted; Codex review provenance.

## Deferred follow-up (documented, NOT in this PR)
1-match link-path orphan + `(teacher_id, data_key)` PK-conflict handling (claim on the `matched` path). Fix sketch: per-key existence check or `ON CONFLICT DO NOTHING` semantics before re-key. Pre-existing (the current merge never claimed either).

## Manual / Operator Verification (Hard Rule #8 — external-IO path)
After deploy: an unlinked Clever teacher (0 email matches) logs in via Clever SSO → lands clean, can create a class (no `invalid input syntax for type uuid`), and their prior `clever:{id}` assignments/settings followed them. A >1-match teacher still logs in (fails open). Confirm in Sentry: no uuid-cast errors for the test login.
