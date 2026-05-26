# ClassLink Roster Server Certification Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a rostered ClassLink teacher and student both land in their provisioned accounts, with tenant-scoped identity, full multi-enrollment student SSO, and FERPA right-to-delete — so the integration can be certified for rostering.

**Architecture:** ClassLink roster data is reconciled to the OneRoster pipeline but lives in its own tenant-scoped namespace `classlink:{quote(tenant)}:{quote(sourcedId)}`. One helper builds that key for both the roster write (via a `normalize_roster` builder param) and the student-SSO read, eliminating encoding drift and closing a cross-tenant lookup FERPA hole. Student SSO mirrors the proven Clever flow (auth-code + multi-enrollment picker), fail-closed on no provisioned row. Delete reuses the shared `delete_roster_data` (with an orphan-row fix).

**Tech Stack:** Python/Flask backend, pytest (+ `unittest.mock`), React/Vite frontend, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md`

**Classification:** Class B (auth/identity + FERPA). Code review gates the merge; do NOT auto-merge with a review in flight.

---

## File Map

| File | Responsibility | Change |
|------|----------------|--------|
| `backend/oneroster.py` | OneRoster normalize | Add `external_id_for` builder param to `normalize_roster` (default-preserving) |
| `backend/roster_sync.py` | Shared roster persistence | Add `_PROVIDER_PREFIXES["classlink"]`; fix `delete_roster_data` orphan-student bug |
| `backend/routes/classlink_routes.py` | ClassLink SSO + roster | Add key helper, roster-sync builder wiring, student-session flow, 3 endpoints, callback rewrite |
| `frontend/src/components/StudentApp.jsx` | Student portal entry | Generalize Clever SSO handlers to also serve ClassLink (provider-parameterized) |
| `tests/test_normalize_roster_builder.py` | New | `normalize_roster` builder + characterization |
| `tests/test_classlink_roster.py` | New | key helper, deactivate prefix, roster-sync wiring, delete-data |
| `tests/test_classlink_student_sso.py` | New | student session create/mint/picker, fail-closed |
| `tests/test_roster_sync_delete_orphan.py` | New | `delete_roster_data` orphan regression |
| `tests/test_classlink_sso.py` | Existing | Append callback student-branch tests |
| `frontend/src/__tests__/StudentApp.classlink.test.jsx` | New | ClassLink picker + token-exchange glue |

---

## Task 1: Parameterize `normalize_roster` with an `external_id_for` builder

**Files:**
- Modify: `backend/oneroster.py:298` (`normalize_roster` signature + 5 external_id sites)
- Test: `tests/test_normalize_roster_builder.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_normalize_roster_builder.py
"""normalize_roster gains a default-preserving external_id builder.

Default (no builder) must stay byte-identical to the historical
`oneroster:{sourcedId}` behavior — OneRoster + Clever depend on it.
A custom builder must be applied to ALL five external_id sites:
class, student, enrollment.class, enrollment.student, accommodation.student.
"""
from backend.oneroster import normalize_roster

RAW = {
    "classes": [{"sourcedId": "c1", "title": "Math", "subjects": ["Math"], "grades": ["9"]}],
    "students": [{"sourcedId": "s1", "givenName": "A", "familyName": "B", "email": "a@b.edu"}],
    "enrollments": [{"role": "student", "class": {"sourcedId": "c1"}, "user": {"sourcedId": "s1"}}],
    "demographics": [{"sourcedId": "s1", "metadata": {"iep_status": "active"}}],
}


def test_default_preserves_oneroster_prefix():
    classes, students, enrollments, accommodations = normalize_roster(RAW)
    assert classes[0]["external_id"] == "oneroster:c1"
    assert students[0]["external_id"] == "oneroster:s1"
    assert enrollments[0]["class_external_id"] == "oneroster:c1"
    assert enrollments[0]["student_external_id"] == "oneroster:s1"
    assert accommodations[0]["student_external_id"] == "oneroster:s1"


def test_custom_builder_applied_to_all_sites():
    builder = lambda sid: f"classlink:dist-A:{sid}"
    classes, students, enrollments, accommodations = normalize_roster(RAW, external_id_for=builder)
    assert classes[0]["external_id"] == "classlink:dist-A:c1"
    assert students[0]["external_id"] == "classlink:dist-A:s1"
    assert enrollments[0]["class_external_id"] == "classlink:dist-A:c1"
    assert enrollments[0]["student_external_id"] == "classlink:dist-A:s1"
    assert accommodations[0]["student_external_id"] == "classlink:dist-A:s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && pytest tests/test_normalize_roster_builder.py -v`
Expected: `test_custom_builder_applied_to_all_sites` FAILS with `TypeError: normalize_roster() got an unexpected keyword argument 'external_id_for'`.

- [ ] **Step 3: Implement the builder param**

In `backend/oneroster.py`, change the signature and the 5 sites:

```python
def normalize_roster(raw, external_id_for=None):
    """Convert raw OneRoster API data to Graider's normalized format.

    Args:
        raw: dict with keys classes, students, enrollments, demographics
        external_id_for: optional callable sourcedId -> external_id. Defaults
            to ``oneroster:{sourcedId}`` (OneRoster behavior, byte-identical).
            ClassLink passes a tenant-scoped builder.

    Returns:
        tuple: (classes, students, enrollments, accommodations)
    """
    if external_id_for is None:
        def external_id_for(sid):
            return f"oneroster:{sid}"
```

Then replace each hardcoded `f"oneroster:{...}"`:
- class: `"external_id": external_id_for(c.get('sourcedId', '')),`
- student: `"external_id": external_id_for(sid),`
- enrollment: `"class_external_id": external_id_for(class_id),` and `"student_external_id": external_id_for(user_id),`
- accommodation: `"student_external_id": external_id_for(sid),`

- [ ] **Step 4: Run new test + the existing roster/oneroster suite (no regression)**

Run: `source venv/bin/activate && pytest tests/test_normalize_roster_builder.py tests/test_oneroster.py tests/test_oneroster_routes_unit.py tests/test_roster_sync.py tests/test_roster_sync_unit.py tests/test_sync_routes.py -q`
Expected: all PASS (default behavior unchanged; new builder test green).

- [ ] **Step 5: Commit**

```bash
git add backend/oneroster.py tests/test_normalize_roster_builder.py
git commit -m "feat(roster): add default-preserving external_id builder to normalize_roster"
```

---

## Task 2: ClassLink roster key helper + `_PROVIDER_PREFIXES` entry

**Files:**
- Modify: `backend/routes/classlink_routes.py` (add `_classlink_roster_external_id` after `_classlink_guid`, ~line 77)
- Modify: `backend/roster_sync.py:26-30` (add `"classlink"` entry)
- Test: `tests/test_classlink_roster.py` (create), `tests/test_classlink_roster.py` deactivate section

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_classlink_roster.py
"""ClassLink roster identity + shared-function safety."""
from unittest.mock import MagicMock, patch

from backend.routes.classlink_routes import _classlink_roster_external_id


def test_key_is_tenant_scoped():
    assert _classlink_roster_external_id("dist-A", "s1") == "classlink:dist-A:s1"


def test_key_percent_encodes_colon_in_components():
    # a ':' inside a component must not create a colliding key
    assert _classlink_roster_external_id("a:b", "c:d") == "classlink:a%3Ab:c%3Ad"


def test_key_tolerates_empty_components():
    assert _classlink_roster_external_id("", "") == "classlink::"


def _deactivate_sb(active_rows, captured_deactivations):
    """Fake Supabase for deactivate_missing_students."""
    sb = MagicMock()

    def _table(name):
        q = MagicMock()
        if name == "students":
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(active_rows))

            def _update(payload):
                upd = MagicMock()

                def _eq(col, val):
                    eqd = MagicMock()
                    eqd.execute.return_value = MagicMock(data=[])
                    captured_deactivations.append(val)
                    return eqd

                upd.eq.side_effect = _eq
                return upd

            q.update.side_effect = _update
        return q

    sb.table.side_effect = _table
    return sb


def test_clever_sync_does_not_deactivate_classlink_rows():
    from backend import roster_sync
    rows = [
        {"id": "row-cl", "student_id_number": "classlink:dist-A:s1"},  # protected
        {"id": "row-cv", "student_id_number": "cv-123"},               # clever, eligible
    ]
    captured = []
    with patch.object(roster_sync, "_get_supabase", return_value=_deactivate_sb(rows, captured)):
        roster_sync.deactivate_missing_students("t1", set(), provider="clever")
    assert "row-cl" not in captured       # classlink row NOT deactivated
    assert "row-cv" in captured           # clever row deactivated
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py -v`
Expected: import error / `AttributeError: ... has no attribute '_classlink_roster_external_id'` and `test_clever_sync_does_not_deactivate_classlink_rows` FAILS (classlink row currently deactivated).

- [ ] **Step 3: Implement helper + prefix entry**

In `backend/routes/classlink_routes.py`, after `_classlink_guid` (the file already has `import urllib.parse`):

```python
def _classlink_roster_external_id(tenant_id, sourced_id):
    """Tenant-scoped roster external_id for ClassLink rows.

    Format: ``classlink:{quote(tenant)}:{quote(sourced_id)}`` — same encoding as
    ``_classlink_guid`` so a ':' inside a component cannot create a colliding key.
    Used on BOTH sides: the roster write (via normalize_roster builder) and the
    student-SSO lookup. Always returns a string (tolerant of empty components,
    matching normalize_roster).
    """
    tenant = urllib.parse.quote(str(tenant_id or "").strip(), safe="")
    sid = urllib.parse.quote(str(sourced_id or "").strip(), safe="")
    return f"classlink:{tenant}:{sid}"
```

In `backend/roster_sync.py`:

```python
_PROVIDER_PREFIXES = {
    "clever": "",
    "oneroster": "oneroster:",
    "manual": "manual-",
    "classlink": "classlink:",
}
```

- [ ] **Step 4: Run to verify pass + deactivation regression net**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py tests/test_roster_sync.py tests/test_roster_sync_unit.py tests/test_sync_routes.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py backend/roster_sync.py tests/test_classlink_roster.py
git commit -m "feat(classlink): tenant-scoped roster key helper + classlink prefix entry"
```

---

## Task 3: Wire the tenant-scoped builder into ClassLink roster sync

**Files:**
- Modify: `backend/routes/classlink_routes.py:97-148` (extract testable `_run_classlink_roster_sync`, pass the builder)
- Test: `tests/test_classlink_roster.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_classlink_roster.py
from unittest.mock import AsyncMock


def test_roster_sync_writes_tenant_scoped_keys():
    from backend.routes import classlink_routes
    raw = {
        "classes": [{"sourcedId": "c1", "title": "Math", "subjects": ["Math"], "grades": ["9"]}],
        "students": [{"sourcedId": "s1", "givenName": "A", "familyName": "B", "email": "a@b.edu"}],
        "enrollments": [{"role": "student", "class": {"sourcedId": "c1"}, "user": {"sourcedId": "s1"}}],
        "demographics": [],
    }
    fake_client = MagicMock()
    fake_client.fetch_roster = AsyncMock(return_value=raw)
    captured = {}

    def _capture_sync(classes, students, enrollments, teacher_id, provider="manual"):
        captured["students"] = students
        captured["enrollments"] = enrollments
        captured["provider"] = provider
        return {"classes": 1, "students": 1, "enrollments": 1}

    with patch("backend.oneroster.get_oneroster_config",
               return_value={"base_url": "https://sis/x", "client_id": "i", "client_secret": "s"}), \
         patch("backend.oneroster.OneRosterClient", return_value=fake_client), \
         patch("backend.roster_sync.sync_roster_to_db", side_effect=_capture_sync):
        classlink_routes._run_classlink_roster_sync("classlink:dist-A:teach1", "dist-A")

    assert captured["provider"] == "classlink"
    assert captured["students"][0]["external_id"] == "classlink:dist-A:s1"
    assert captured["enrollments"][0] == ("classlink:dist-A:c1", "classlink:dist-A:s1")
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py::test_roster_sync_writes_tenant_scoped_keys -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_run_classlink_roster_sync'`.

- [ ] **Step 3: Refactor `_trigger_roster_sync` and pass the builder**

In `backend/routes/classlink_routes.py`, replace the body of `_trigger_roster_sync` so the sync work lives in a module-level, testable function and the normalize call uses the tenant-scoped builder:

```python
def _run_classlink_roster_sync(teacher_id, tenant_id):
    """Synchronous ClassLink roster sync (OneRoster 1.1 endpoints).

    Writes tenant-scoped external_ids so ClassLink roster rows never collide
    with OneRoster rows or across tenants. Extracted from _trigger_roster_sync
    so it is unit-testable without a thread.
    """
    from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
    from backend.roster_sync import sync_roster_to_db
    import asyncio

    config = get_oneroster_config(teacher_id)
    if not config.get('base_url'):
        logger.info("No OneRoster config for %s, skipping post-login roster sync", teacher_id)
        return

    client = OneRosterClient(
        base_url=config['base_url'],
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        token_url=config.get('token_url'),
    )
    loop = asyncio.new_event_loop()
    try:
        raw = loop.run_until_complete(client.fetch_roster(
            school_id=config.get('school_id'),
            teacher_sourced_id=config.get('teacher_sourced_id'),
        ))
    finally:
        loop.close()

    classes, students_norm, enrollments, _accommodations = normalize_roster(
        raw, external_id_for=lambda sid: _classlink_roster_external_id(tenant_id, sid)
    )
    enrollment_tuples = [
        (e["class_external_id"], e["student_external_id"]) for e in enrollments
    ]
    sync_roster_to_db(classes, students_norm, enrollment_tuples, teacher_id, provider="classlink")
    logger.info("Post-login ClassLink roster sync complete for %s", teacher_id)


def _trigger_roster_sync(teacher_id, tenant_id):
    """Trigger background ClassLink roster sync after login (OneRoster 1.1)."""
    import threading

    def _bg_sync():
        try:
            _run_classlink_roster_sync(teacher_id, tenant_id)
        except Exception as e:
            logger.warning("Post-login ClassLink roster sync failed for %s: %s", teacher_id, e)
            sentry_sdk.capture_exception(e)

    thread = threading.Thread(target=_bg_sync, daemon=True)
    thread.start()
```

- [ ] **Step 4: Run to verify pass + classlink SSO suite unaffected**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py tests/test_classlink_sso.py tests/test_classlink_routes_gaps.py -q`
Expected: all PASS (`_run_callback` patches `_trigger_roster_sync`, so SSO tests stay green).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_roster.py
git commit -m "feat(classlink): tenant-scoped roster sync wiring (testable _run_classlink_roster_sync)"
```

---

## Task 4: Fix the shared `delete_roster_data` orphan-student bug

**Files:**
- Modify: `backend/roster_sync.py:254` (`delete_roster_data` — move student deletion out of `if class_ids:`)
- Test: `tests/test_roster_sync_delete_orphan.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_roster_sync_delete_orphan.py
"""delete_roster_data must delete a teacher's student rows even when the
teacher has no class rows (orphan students). Previously student deletion
was gated inside `if class_ids:`, leaving orphans behind — an incomplete
FERPA right-to-delete. Still teacher_id-scoped (never touches other teachers)."""
from unittest.mock import MagicMock, patch

from backend import roster_sync


def _delete_sb(class_ids, student_ids, deletes):
    """Fake Supabase recording which tables had .delete() executed."""
    sb = MagicMock()

    def _table(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        if name == "classes":
            q.execute.return_value = MagicMock(data=[{"id": c} for c in class_ids])
        elif name == "students":
            q.execute.return_value = MagicMock(data=[{"id": s} for s in student_ids])
        else:
            q.execute.return_value = MagicMock(data=[])

        def _delete():
            deletes.append(name)
            d = MagicMock()
            d.eq.return_value = d
            d.in_.return_value = d
            d.execute.return_value = MagicMock(data=[])
            return d

        q.delete.side_effect = _delete
        return q

    sb.table.side_effect = _table
    return sb


def test_deletes_orphan_students_with_no_classes():
    deletes = []
    sb = _delete_sb(class_ids=[], student_ids=["st1", "st2"], deletes=deletes)
    with patch("backend.supabase_client.get_supabase", return_value=sb):
        result = roster_sync.delete_roster_data("classlink:dist-A:teach1")
    assert "students" in deletes        # students deleted despite zero classes
    assert result["students"] == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_roster_sync_delete_orphan.py -v`
Expected: FAIL — `students` never appears in `deletes` (deletion gated behind `if class_ids:`), `result["students"] == 0`.

- [ ] **Step 3: Move student deletion out of the `if class_ids:` branch**

In `backend/roster_sync.py` `delete_roster_data`, restructure the Supabase block so class-scoped deletes stay gated but student deletes always run:

```python
            classes_res = sb.table("classes").select("id").eq("teacher_id", teacher_id).execute()
            class_ids = [c["id"] for c in (classes_res.data or [])]

            if class_ids:
                # Class-scoped deletes (content, submissions, enrollments, classes)
                content_res = sb.table("published_content").select("id").in_("class_id", class_ids).execute()
                content_ids = [c["id"] for c in (content_res.data or [])]
                if content_ids:
                    sb.table("student_submissions").delete().in_("content_id", content_ids).execute()
                    sb.table("published_content").delete().in_("id", content_ids).execute()
                for cid in class_ids:
                    sb.table("class_students").delete().eq("class_id", cid).execute()

            # Always delete this teacher's students + their sessions — including
            # orphan students with no class rows (FERPA right-to-delete must be
            # complete). Still teacher_id-scoped: never another teacher's rows.
            students_res = sb.table("students").select("id").eq("teacher_id", teacher_id).execute()
            student_ids = [s["id"] for s in (students_res.data or [])]
            if student_ids:
                for sid in student_ids:
                    sb.table("student_sessions").delete().eq("student_id", sid).execute()
                sb.table("students").delete().eq("teacher_id", teacher_id).execute()

            if class_ids:
                sb.table("classes").delete().eq("teacher_id", teacher_id).execute()

            deleted["classes"] = len(class_ids)
            deleted["students"] = len(student_ids)
            deleted["enrollments"] = len(class_ids)  # approximation
```

- [ ] **Step 4: Run to verify pass + existing roster delete tests**

Run: `source venv/bin/activate && pytest tests/test_roster_sync_delete_orphan.py tests/test_roster_sync.py tests/test_roster_sync_unit.py tests/test_oneroster_routes_unit.py tests/test_clever_compliance.py -q`
Expected: all PASS (the non-orphan path is unchanged; existing OneRoster/Clever delete tests stay green).

- [ ] **Step 5: Commit**

```bash
git add backend/roster_sync.py tests/test_roster_sync_delete_orphan.py
git commit -m "fix(roster): delete orphan students with no classes in delete_roster_data"
```

---

## Task 5: ClassLink student-session core (mint, stores, create-session)

**Files:**
- Modify: `backend/routes/classlink_routes.py` (add `import hashlib`; supabase import; auth-code + selection stores; `_mint_classlink_student_session`; `_create_classlink_student_session`)
- Test: `tests/test_classlink_student_sso.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_classlink_student_sso.py
"""ClassLink student SSO — provisioned-row lookup, mint, multi-enrollment
picker, and FAIL-CLOSED behavior (no row / no email fallback). Supabase mocked."""
from unittest.mock import MagicMock, patch

from backend.routes.classlink_routes import _create_classlink_student_session

KEY = "classlink:dist-A:s1"


def _make_sb(student_rows, enroll_rows, capture=None):
    sb = MagicMock()

    def _table(name):
        if name == "students":
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(student_rows))
            return q
        if name == "class_students":
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(enroll_rows))
            return q
        if name == "student_sessions":
            q = MagicMock()

            def _insert(payload):
                if capture is not None:
                    capture["inserted"] = payload
                ins = MagicMock()
                ins.execute.return_value = MagicMock(data=[payload])
                return ins

            q.insert.side_effect = _insert
            return q
        return MagicMock()

    sb.table.side_effect = _table
    return sb


def test_single_enrollment_mints_session():
    student_rows = [{"id": "row1", "student_id_number": KEY, "first_name": "A", "last_name": "B"}]
    enroll_rows = [{"class_id": "cls1", "classes": {"id": "cls1", "name": "Math", "subject": "math"}}]
    capture = {}
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb(student_rows, enroll_rows, capture)):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result and result.get("token")
    assert capture["inserted"]["student_id"] == "row1"
    assert capture["inserted"]["class_id"] == "cls1"


def test_multi_enrollment_returns_needs_selection():
    student_rows = [{"id": "row1", "student_id_number": KEY, "first_name": "A", "last_name": "B"}]
    enroll_rows = [
        {"class_id": "cls1", "classes": {"id": "cls1", "name": "Math", "subject": "math"}},
        {"class_id": "cls2", "classes": {"id": "cls2", "name": "Sci", "subject": "sci"}},
    ]
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb(student_rows, enroll_rows)):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result["status"] == "needs_class_selection"
    assert result.get("selection_token")
    # public candidates must NOT leak the server-only _student_row
    assert all("_student_row" not in c for c in result["classes"])


def test_no_row_fails_closed_no_email_fallback():
    # Students lookup by the tenant-scoped key returns nothing. Even though a
    # row with a matching EMAIL exists elsewhere, the flow must NOT find it.
    with patch("backend.routes.classlink_routes.get_supabase",
               return_value=_make_sb([], [])):
        result = _create_classlink_student_session("dist-A", "s1")
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_classlink_student_sso.py -v`
Expected: FAIL — `ImportError: cannot import name '_create_classlink_student_session'`.

- [ ] **Step 3: Implement the stores, mint, and create-session**

In `backend/routes/classlink_routes.py`: add `import hashlib` to the imports, and add `from backend.supabase_client import get_supabase` near the other backend imports. Then add (after `_classlink_roster_external_id`):

```python
# Short-lived auth codes for student ClassLink SSO (code -> {token, expires})
_pending_classlink_student_auth_codes = {}
_CLASSLINK_AUTH_CODE_TTL = 60  # seconds


def _create_classlink_student_auth_code(raw_token):
    """Mint a short-lived code the SPA exchanges for the real session token."""
    code = secrets.token_urlsafe(32)
    _pending_classlink_student_auth_codes[code] = {
        "token": raw_token, "expires": time.time() + _CLASSLINK_AUTH_CODE_TTL,
    }
    now = time.time()
    for k in [k for k, v in _pending_classlink_student_auth_codes.items() if v["expires"] < now]:
        del _pending_classlink_student_auth_codes[k]
    return code


# Short-lived selection tokens for the multi-enrollment picker.
_pending_classlink_class_selections = {}
_CLASSLINK_CLASS_SELECTION_TTL = 120  # seconds


def _public_classlink_candidates(candidates):
    """Browser-safe projection — strips the server-only `_student_row` (PII)."""
    return [
        {"class_id": c["class_id"], "name": c.get("name", ""), "subject": c.get("subject", "")}
        for c in candidates
    ]


def _create_classlink_class_selection(candidates):
    """Mint a short-lived token the student exchanges (with a chosen class_id)."""
    code = secrets.token_urlsafe(32)
    _pending_classlink_class_selections[code] = {
        "candidates": candidates, "expires": time.time() + _CLASSLINK_CLASS_SELECTION_TTL,
    }
    now = time.time()
    for k in [k for k, v in _pending_classlink_class_selections.items() if v["expires"] < now]:
        del _pending_classlink_class_selections[k]
    return code


def _mint_classlink_student_session(sb, student_row, chosen):
    """Insert a hashed student_sessions row and return {token, student, class}.

    Mirrors the Clever mint; duplicated (not shared) to keep the certified
    Clever path byte-identical (Class B blast-radius discipline)."""
    from datetime import datetime, timezone, timedelta

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

    sb.table("student_sessions").insert({
        "student_id": student_row["id"],
        "class_id": chosen["class_id"],
        "session_token": token_hash,
        "expires_at": expires.isoformat(),
    }).execute()

    return {
        "token": raw_token,
        "student": {
            "first_name": student_row.get("first_name", ""),
            "last_name": student_row.get("last_name", ""),
            "email": student_row.get("email", ""),
            "student_id": student_row.get("student_id_number", ""),
            "period": student_row.get("period", ""),
        },
        "class": {"name": chosen.get("name", ""), "subject": chosen.get("subject", "")},
    }


def _create_classlink_student_session(tenant_id, person_id):
    """Resolve a rostered ClassLink student to their provisioned record and
    mint a session, tenant-scoped and FAIL-CLOSED.

    Returns {token,...} for a single enrollment, a needs_class_selection payload
    for multiple, or None when no provisioned row matches the tenant-scoped key
    (NO email fallback — that would risk a cross-tenant match)."""
    sb = get_supabase()
    if sb is None:
        logger.debug("Supabase not configured — cannot create ClassLink student session")
        return None

    try:
        key = _classlink_roster_external_id(tenant_id, person_id)
        res = sb.table("students").select("*").eq("student_id_number", key).execute()
        student_rows = list(res.data) if res and res.data else []
        if not student_rows:
            return None  # fail closed — no email fallback

        candidates = []
        seen = set()
        for srow in student_rows:
            srow_id = srow.get("id")
            if not srow_id:
                continue
            enroll = (
                sb.table("class_students")
                .select("class_id, classes(id, name, subject)")
                .eq("student_id", srow_id)
                .execute()
            )
            for er in (enroll.data if enroll and enroll.data else []):
                ci = er.get("classes") or {}
                cid = ci.get("id") or er.get("class_id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                candidates.append({
                    "class_id": cid, "name": ci.get("name", ""),
                    "subject": ci.get("subject", ""), "_student_row": srow,
                })

        if not candidates:
            return None
        if len(candidates) > 1:
            selection_token = _create_classlink_class_selection(candidates)
            return {
                "status": "needs_class_selection",
                "classes": _public_classlink_candidates(candidates),
                "selection_token": selection_token,
            }
        chosen = candidates[0]
        return _mint_classlink_student_session(sb, chosen["_student_row"], chosen)
    except Exception as e:
        logger.warning("Failed to create ClassLink student session: %s", str(e))
        sentry_sdk.capture_exception(e)
        return None
```

- [ ] **Step 4: Run to verify pass**

Run: `source venv/bin/activate && pytest tests/test_classlink_student_sso.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_student_sso.py
git commit -m "feat(classlink): student-session core — tenant-scoped lookup, mint, picker, fail-closed"
```

---

## Task 6: Student endpoints + callback rewrite

**Files:**
- Modify: `backend/routes/classlink_routes.py` (add `/api/classlink/student-token` and `/api/classlink/select-class`; rewrite the `role == 'student'` branch of `classlink_callback`)
- Test: `tests/test_classlink_student_sso.py` (append endpoint tests), `tests/test_classlink_sso.py` (append callback-branch tests)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_classlink_student_sso.py
from flask import Flask


def _make_app():
    from backend.routes.classlink_routes import classlink_bp
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(classlink_bp)
    return app


def test_student_token_exchange_roundtrip():
    from backend.routes import classlink_routes
    code = classlink_routes._create_classlink_student_auth_code("real-token-xyz")
    app = _make_app()
    with app.test_client() as c:
        r = c.post("/api/classlink/student-token", json={"code": code})
        assert r.status_code == 200
        assert r.get_json()["token"] == "real-token-xyz"
        # single-use: a second exchange fails
        r2 = c.post("/api/classlink/student-token", json={"code": code})
        assert r2.status_code == 401


def test_select_class_get_lists_then_post_mints():
    from backend.routes import classlink_routes
    candidates = [
        {"class_id": "cls1", "name": "Math", "subject": "math",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
        {"class_id": "cls2", "name": "Sci", "subject": "sci",
         "_student_row": {"id": "row1", "student_id_number": KEY}},
    ]
    token = classlink_routes._create_classlink_class_selection(candidates)
    app = _make_app()
    capture = {}
    with app.test_client() as c:
        g = c.get(f"/api/classlink/select-class?selection_token={token}")
        names = [x["name"] for x in g.get_json()["classes"]]
        assert names == ["Math", "Sci"]
        with patch("backend.routes.classlink_routes.get_supabase",
                   return_value=_make_sb([{"id": "row1", "student_id_number": KEY}], [], capture)):
            p = c.post("/api/classlink/select-class",
                       json={"selection_token": token, "class_id": "cls2"})
        assert p.status_code == 200 and p.get_json()["token"]
        assert capture["inserted"]["class_id"] == "cls2"
```

```python
# append to tests/test_classlink_sso.py (reuses make_id_token / _mock_jwks_client / _mock_oidc_config)
class TestClassLinkStudentCallback:
    STU = {"FirstName": "S", "LastName": "T", "Email": "s@school.edu", "Role": "student"}

    def _run_student(self, client, priv, pub, session_result):
        id_token = make_id_token(priv, aud="test-client-id", sub="stu",
                                 email="s@school.edu", role="student")
        tok = MagicMock(); tok.status_code = 200
        tok.json.return_value = {"access_token": "tok", "id_token": id_token}
        usr = MagicMock(); usr.status_code = 200
        usr.json.return_value = {**self.STU, "SourcedId": "s1", "TenantId": "dist-A"}
        with client.session_transaction() as sess:
            sess['classlink_oauth_state'] = 'valid-state'
        with patch('backend.routes.classlink_routes.requests.post', return_value=tok), \
             patch('backend.routes.classlink_routes.requests.get', return_value=usr), \
             patch('backend.routes.classlink_routes.get_classlink_oidc_config', return_value=_mock_oidc_config()), \
             patch('backend.routes.classlink_routes.get_classlink_jwks_client', return_value=_mock_jwks_client(pub)), \
             patch('backend.routes.classlink_routes._create_classlink_student_session', return_value=session_result):
            return client.get('/api/classlink/callback?code=c&state=valid-state')

    def test_single_enrollment_redirects_with_auth_code(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = self._run_student(client, priv, pub, {"token": "t-abc"})
            assert "classlink=1" in resp.location and "code=" in resp.location

    def test_multi_enrollment_redirects_to_picker(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = self._run_student(client, priv, pub,
                                     {"status": "needs_class_selection", "selection_token": "seltok"})
            assert "classlink_select=1" in resp.location and "sel=seltok" in resp.location

    def test_unprovisioned_student_fails_closed(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = self._run_student(client, priv, pub, None)
            assert "classlink_error=not_provisioned" in resp.location
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_classlink_student_sso.py tests/test_classlink_sso.py::TestClassLinkStudentCallback -v`
Expected: FAIL — endpoints 404 (not registered) and callback still redirects to `classlink_login=success`.

- [ ] **Step 3: Add endpoints + rewrite the callback student branch**

In `backend/routes/classlink_routes.py`, replace the `if role == 'student':` block in `classlink_callback` (currently sets `session['classlink_student']` and redirects to `classlink_login=success`):

```python
    # Student login → resolve provisioned record, hand off to the student portal.
    if role == 'student':
        # Clear OAuth-flow markers (single-use enforcement on success).
        session.pop('classlink_oauth_state', None)
        session.pop('classlink_oauth_nonce', None)
        session.pop('classlink_oauth_initiated_by_us', None)

        student_session = _create_classlink_student_session(tenant_id, person_id)
        if student_session and student_session.get("status") == "needs_class_selection":
            params = urlencode({"classlink_select": "1", "sel": student_session["selection_token"]})
            return redirect("/student?" + params)
        if student_session:
            auth_code = _create_classlink_student_auth_code(student_session["token"])
            params = urlencode({"classlink": "1", "code": auth_code})
            return redirect("/student?" + params)

        # Fail closed — no provisioned row for this tenant-scoped identity.
        audit_log(
            "CLASSLINK_STUDENT_NOT_PROVISIONED",
            "ClassLink student has no provisioned roster row: "
            f"tenant={tenant_id} person_hash={hashlib.sha256(person_id.encode()).hexdigest()[:8]}",
            user="anonymous", teacher_id="",
        )
        return redirect("/student?classlink_error=not_provisioned")
```

Then add the two endpoints (e.g. after `classlink_logout`):

```python
@classlink_bp.route("/api/classlink/student-token", methods=["POST"])
def classlink_exchange_student_auth_code():
    """Exchange a short-lived auth code for a student session token."""
    data = request.json or {}
    code = data.get("code", "")
    if not code or code not in _pending_classlink_student_auth_codes:
        return jsonify({"error": "Invalid or expired code"}), 401
    entry = _pending_classlink_student_auth_codes.pop(code)
    if time.time() > entry["expires"]:
        return jsonify({"error": "Code expired"}), 401
    return jsonify({"token": entry["token"]})


@classlink_bp.route("/api/classlink/select-class", methods=["GET", "POST"])
def classlink_select_class():
    """Multi-enrollment finalize. GET lists candidates (does not consume the
    token); POST mints the scoped session (single-use on success only)."""
    if request.method == "GET":
        token = request.args.get("selection_token", "")
    else:
        data = request.json or {}
        token = data.get("selection_token", "")
        class_id = data.get("class_id", "")

    entry = _pending_classlink_class_selections.get(token)
    if not entry:
        return jsonify({"error": "Invalid or expired selection"}), 401
    if time.time() > entry["expires"]:
        _pending_classlink_class_selections.pop(token, None)
        return jsonify({"error": "Selection expired"}), 401

    if request.method == "GET":
        return jsonify({"classes": _public_classlink_candidates(entry["candidates"])})

    chosen = next((c for c in entry["candidates"] if c["class_id"] == class_id), None)
    if chosen is None:
        return jsonify({"error": "Class not among offered choices"}), 400

    sb = get_supabase()
    if sb is None:
        return jsonify({"error": "Supabase not configured"}), 503

    session_info = _mint_classlink_student_session(sb, chosen["_student_row"], chosen)
    _pending_classlink_class_selections.pop(token, None)  # single-use, success only
    return jsonify({"token": session_info["token"]})
```

Also update `classlink_logout` to drop the now-unused `classlink_student` pop (harmless either way — leave it; it no longer corresponds to a write).

- [ ] **Step 4: Run to verify pass**

Run: `source venv/bin/activate && pytest tests/test_classlink_student_sso.py tests/test_classlink_sso.py -q`
Expected: all PASS (new endpoint + callback tests green; existing teacher-callback tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_student_sso.py tests/test_classlink_sso.py
git commit -m "feat(classlink): student SSO endpoints + fail-closed callback hand-off"
```

---

## Task 7: `/api/classlink/delete-data` endpoint

**Files:**
- Modify: `backend/routes/classlink_routes.py` (import `require_teacher`, `handle_route_errors`, `g`; add endpoint)
- Test: `tests/test_classlink_roster.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_classlink_roster.py
import pytest


@pytest.fixture
def app_client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


def test_delete_data_calls_roster_delete_for_classlink_teacher(app_client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    captured = {}
    with patch("backend.roster_sync.delete_roster_data",
               return_value={"classes": 1, "students": 2, "enrollments": 1}) as mock_del, \
         patch("backend.storage.save") as mock_save:
        r = app_client.post(
            "/api/classlink/delete-data",
            headers={"X-Test-Teacher-Id": "classlink:dist-A:teach1", "Content-Type": "application/json"},
        )
        assert r.status_code == 200
        assert r.get_json()["counts"]["students"] == 2
        mock_del.assert_called_once_with("classlink:dist-A:teach1")
        mock_save.assert_called_once_with("oneroster_config", None, "classlink:dist-A:teach1")


def test_delete_data_rejects_non_classlink_teacher(app_client, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    r = app_client.post(
        "/api/classlink/delete-data",
        headers={"X-Test-Teacher-Id": "clever:abc", "Content-Type": "application/json"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py -k delete_data -v`
Expected: FAIL — 404 (endpoint not registered).

- [ ] **Step 3: Implement the endpoint**

In `backend/routes/classlink_routes.py`, add imports near the top (`g` is already imported from flask):

```python
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
```

Add the endpoint:

```python
@classlink_bp.route("/api/classlink/delete-data", methods=["POST"])
@require_teacher
@handle_route_errors
def classlink_delete_data():
    """Delete all ClassLink-sourced roster data for the current teacher and
    clear stored roster config (FERPA right-to-delete). teacher_id-scoped."""
    from backend.roster_sync import delete_roster_data
    from backend.storage import save as _storage_save

    teacher_id = g.teacher_id
    if not teacher_id.startswith("classlink:"):
        return jsonify({"error": "Not a ClassLink user"}), 403

    deleted = delete_roster_data(teacher_id)
    _storage_save("oneroster_config", None, teacher_id)
    audit_log(
        "CLASSLINK_DATA_DELETED",
        f"Deleted {deleted.get('classes', 0)} classes, {deleted.get('students', 0)} students",
        teacher_id=teacher_id,
    )
    return jsonify({"status": "deleted", "counts": deleted})
```

- [ ] **Step 4: Run to verify pass + full classlink suite**

Run: `source venv/bin/activate && pytest tests/test_classlink_roster.py tests/test_classlink_student_sso.py tests/test_classlink_sso.py tests/test_classlink_routes_gaps.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/classlink_routes.py tests/test_classlink_roster.py
git commit -m "feat(classlink): /api/classlink/delete-data (FERPA right-to-delete)"
```

---

## Task 8: Frontend — generalize the student SSO handlers to serve ClassLink

**Files:**
- Modify: `frontend/src/components/StudentApp.jsx:12-170` (provider-parameterize the Clever handlers + picker)
- Test: `frontend/src/__tests__/StudentApp.classlink.test.jsx` (create)

- [ ] **Step 1: Write the failing test**

```jsx
// frontend/src/__tests__/StudentApp.classlink.test.jsx
/**
 * ClassLink student SSO glue — mirrors StudentApp.cleverSelect.test.jsx.
 * Backend security is unit-tested in Python; this guards the SPA wiring:
 * /student?classlink_select=1&sel=… renders the picker and finalizes against
 * /api/classlink/select-class.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StudentApp from '../components/StudentApp';

function mockFetch() {
  return vi.fn((url, opts) => {
    const u = String(url);
    if (u.indexOf('/api/classlink/select-class') === 0 && (!opts || opts.method !== 'POST')) {
      return Promise.resolve({ json: () => Promise.resolve({ classes: [
        { class_id: 'cl-1', name: 'History 10', subject: 'history' },
        { class_id: 'cl-2', name: 'Bio 10', subject: 'bio' },
      ] }) });
    }
    if (u.indexOf('/api/classlink/select-class') === 0 && opts && opts.method === 'POST') {
      return Promise.resolve({ json: () => Promise.resolve({ token: 'cl-final' }) });
    }
    if (u.indexOf('/api/student/session') === 0) {
      return Promise.resolve({ json: () => Promise.resolve({
        valid: true, student: { first_name: 'Sam' }, class_info: { name: 'Bio 10' },
      }) });
    }
    return Promise.resolve({ json: () => Promise.resolve({}) });
  });
}

describe('StudentApp ClassLink multi-enrollment picker', () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.pushState({}, '', '/student?classlink_select=1&sel=cltok-1');
  });

  it('renders candidate classes from the ClassLink selection token', async () => {
    global.fetch = mockFetch();
    render(<StudentApp />);
    expect(await screen.findByText('History 10')).toBeTruthy();
    expect(await screen.findByText('Bio 10')).toBeTruthy();
  });

  it('finalizes against /api/classlink/select-class with the chosen class', async () => {
    const fetchMock = mockFetch();
    global.fetch = fetchMock;
    render(<StudentApp />);
    fireEvent.click(await screen.findByText('Bio 10'));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (c) => String(c[0]).indexOf('/api/classlink/select-class') === 0 &&
               c[1] && c[1].method === 'POST'
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post[1].body)).toEqual({ selection_token: 'cltok-1', class_id: 'cl-2' });
    });
    await waitFor(() => expect(localStorage.getItem('student_token')).toBe('cl-final'));
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/__tests__/StudentApp.classlink.test.jsx`
Expected: FAIL — picker never renders (no `classlink_select` handler); POST never hits `/api/classlink/select-class`.

- [ ] **Step 3: Provider-parameterize the handlers**

In `frontend/src/components/StudentApp.jsx`, replace the Clever-specific param parsing at the top of the `useEffect` (lines ~13-19) so it detects the provider:

```jsx
    var params = new URLSearchParams(window.location.search);
    // SSO callbacks: clever|classlink single-enrollment (code) or multi (select).
    var ssoProvider = params.get("clever") === "1" ? "clever"
                    : params.get("classlink") === "1" ? "classlink" : null;
    var ssoCode = params.get("code");
    var selectProvider = params.get("clever_select") === "1" ? "clever"
                       : params.get("classlink_select") === "1" ? "classlink" : null;
    var selToken = params.get("sel");

    if (selectProvider && selToken) {
      window.history.replaceState({}, document.title, "/student");
      fetch("/api/" + selectProvider + "/select-class?selection_token=" + encodeURIComponent(selToken))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data && data.classes && data.classes.length) {
            setClassPicker({ provider: selectProvider, selectionToken: selToken, classes: data.classes });
          }
        })
        .catch(function(err) { console.error("SSO class options failed:", err); })
        .finally(function() { setChecking(false); });
      return;
    }

    if (ssoProvider && ssoCode) {
      window.history.replaceState({}, document.title, "/student");
      fetch("/api/" + ssoProvider + "/student-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: ssoCode }),
      })
```

Leave the rest of that `.then(...)` chain (token → `/api/student/session`) unchanged, and change its `.catch` message from `"Clever student auth failed:"` to `"SSO student auth failed:"`. Keep the `} else {` localStorage branch as-is.

Then replace `chooseCleverClass` (lines ~119-151) with a provider-aware version that reads `classPicker.provider`:

```jsx
  function chooseClass(classId) {
    setChecking(true);
    fetch("/api/" + classPicker.provider + "/select-class", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection_token: classPicker.selectionToken, class_id: classId }),
    })
```

(the rest of that chain is unchanged) and update the picker button onClick (line ~161) from `onClick={function() { chooseCleverClass(c.class_id); }}` to `onClick={function() { chooseClass(c.class_id); }}`.

- [ ] **Step 4: Run new test + the Clever regression test**

Run: `cd frontend && npx vitest run src/__tests__/StudentApp.classlink.test.jsx src/__tests__/StudentApp.cleverSelect.test.jsx`
Expected: BOTH files PASS (Clever path provably unchanged via its existing test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StudentApp.jsx frontend/src/__tests__/StudentApp.classlink.test.jsx
git commit -m "feat(classlink): student-portal SSO glue (provider-generalized handlers)"
```

---

## Task 9: Full verification, lint, and finalize

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `source venv/bin/activate && pytest -q`
Expected: all PASS, coverage ≥ 60% floor (CI gate). If any pre-existing unrelated failure, note it; do not mask new failures.

- [ ] **Step 2: Lint + SAST gates that CI enforces**

Run: `source venv/bin/activate && ruff check backend/ tests/ && bandit -q -r backend/routes/classlink_routes.py backend/roster_sync.py backend/oneroster.py`
Expected: clean (no new findings).

- [ ] **Step 3: Frontend build + test count gate**

Run: `cd frontend && npm run build && npx vitest run`
Expected: build succeeds; all frontend tests PASS.

- [ ] **Step 4: Refresh the GitNexus index (post-code-change)**

Run: `npx gitnexus analyze --embeddings`
Expected: index updated (preserves embeddings).

- [ ] **Step 5: Push branch + open PR (Class B — review gates merge)**

```bash
git push -u origin feature/classlink-roster-cert-parity
gh pr create --title "feat(classlink): Roster Server certification parity (tenant-scoped identity + student SSO + delete)" \
  --body "Implements docs/superpowers/specs/2026-05-25-classlink-roster-certification-parity-design.md. Class B (auth/identity + FERPA) — request a code review BEFORE merge; do NOT arm auto-merge with a review in flight."
```

Then request a code review (superpowers:requesting-code-review). Merge only after the review returns clean.

---

## Self-Review (completed during authoring)

- **Spec coverage:** §4.1 → T2; §4.2 → T1+T2; §4.3 → T5+T6+T8; §4.4 → T4+T7; §4.5 testing → woven into every task; §4.6 scope (defer deactivation wiring / periodic cron) → respected (only the prefix entry is added, never a deactivate *call* for classlink).
- **Placeholders:** none — every code/test step has complete content.
- **Type/name consistency:** `_classlink_roster_external_id`, `_create_classlink_student_session`, `_mint_classlink_student_session`, `_create_classlink_student_auth_code`, `_create_classlink_class_selection`, `_public_classlink_candidates`, `_run_classlink_roster_sync`, and the `classlink`/`classlink_select`/`code`/`sel` URL params are used identically across backend, frontend, and tests.
- **Known external dependency (from spec §4.6):** the happy path requires ClassLink userinfo `SourcedId` == OneRoster roster `sourcedId` for the same person; the design fails closed if not (T5 `test_no_row_fails_closed`, T6 `test_unprovisioned_student_fails_closed`). Verify against the live test tenant before cert.
