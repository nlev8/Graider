# Security Quintet — Same-Day Hardening from Dimensional Review

> **STATUS: CLOSED 2026-05-15** — Tasks 1-4b shipped in PR #372 (`11e2e69`); Task 5's deferred state/nonce items shipped in PR #374 (`ede4a5a`). Checkboxes bulk-flipped during the 2026-05-15 plan-sweep (see PR for context).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Close five concrete security findings from the 2026-05-14 dimensional review: timing-vulnerable secret compare on the periodic-sync webhook, silent `list_users()` truncation past 50 records at 3 sites, the Clever district roster leak across all 3 active exploit surfaces (manual `/api/clever/sync-roster`, periodic-sync cron, post-login background thread).

**Architecture:** Four fixes in one PR. Each fix is TDD: write the failing test that demonstrates the current bug, watch it fail, write the minimal fix, watch it pass, commit. Tasks 3 and 4 share a new `filter_roster_to_teacher()` helper extracted from the existing `own_sections` logic in clever_routes.py:495-513.

**Tech Stack:** Python 3.12 (stdlib `hmac`, `ast`), pytest, `unittest.mock`. No new dependencies.

**Source findings:**
- Dimensional review S1, S2, S4 (verified file:line 2026-05-14)
- Codex plan review (caveat on `hmac` import, test mocks, periodic-sync reachable)
- Gemini-proxy plan review (test pins mechanism not property; periodic-sync ships daily via cron `roster-sync.yml:5`)

**Out-of-scope deferrals:** 6 state/nonce timing-compare bugs in `clever_routes.py:312`, `classlink_routes.py:237,258,348`, `lti_routes.py:113,131`. Same fix pattern; filed as separate issue with file:line sketches per Rule #11. Defer reason: each is session-bound CSRF/replay defense (short-lived, single-session blast radius) — lower-leverage than the long-lived webhook secret.

---

## File Structure

| File | Status | Owner task |
|---|---|---|
| `backend/routes/sync_routes.py` | Modify (line 38-46 + line 189-196) | Task 1, Task 4 |
| `backend/routes/clever_routes.py` | Modify (line 394, line 495-536) | Task 2 (pagination), Task 3 (extract + apply helper) |
| `backend/routes/auth_routes.py` | Modify (line 160) | Task 2 |
| `backend/routes/stripe_routes.py` | Modify (line 254) | Task 2 |
| `backend/utils/supabase_users.py` | Create | Task 2 |
| `backend/services/clever_roster_scope.py` | Create | Task 3 |
| `tests/test_sync_routes.py` | Modify | Task 1, Task 4 |
| `tests/test_list_users_pagination_issue372.py` | Create | Task 2 |
| `tests/test_clever_roster_scope_issue372.py` | Create | Task 3, Task 4 |

---

## Task 1: Constant-time secret compare on periodic-sync webhook

**Vulnerability:** `backend/routes/sync_routes.py:46` does `return auth[7:] == expected`. Timing-dependent; co-tenant attackers can extract the secret byte-by-byte by measuring response latency. The webhook secret is long-lived and triggers all-teacher roster syncs — high blast radius.

**Files:**
- Modify: `backend/routes/sync_routes.py` (add `hmac` import, change `_validate_secret`)
- Modify: `tests/test_sync_routes.py` (add regression tests to `TestSyncWebhookAuth`)

- [x] **Step 1.1: Add `import hmac` to `backend/routes/sync_routes.py`**

Per Codex review: without this, the Task-1 test below will `AttributeError` at patch time instead of failing on the assertion. Add the import BEFORE writing the test. This is not "skipping the failing-test step" — the test still fails red on the real assertion in step 1.3 because the function body still uses `==`.

```bash
grep -n "^import hmac" backend/routes/sync_routes.py || true
```

If no output, add `import hmac` near the other stdlib imports at lines 10-13 (alongside `os`, `time`, `logging`, `datetime`).

- [x] **Step 1.2: Write failing test pinning the property, not the mechanism**

Per Gemini-proxy review: a `spy.called` test passes if compare_digest is referenced at all, even alongside an early-return `if len(a) != len(b)` length leak. Stronger test: assert via `inspect.getsource` that `==` does not appear in `_validate_secret`.

Add to `tests/test_sync_routes.py` inside `class TestSyncWebhookAuth`:

```python
    def test_validate_secret_uses_only_constant_time_compare(self):
        """_validate_secret must not contain any `==`/`!=` against the
        secret — only hmac.compare_digest. Prevents both the original
        timing bug and the "length leak" refactor pitfall caught by
        Gemini-proxy plan review (2026-05-14)."""
        import inspect
        from backend.routes.sync_routes import _validate_secret
        src = inspect.getsource(_validate_secret)
        assert "hmac.compare_digest" in src, (
            "_validate_secret must call hmac.compare_digest"
        )
        # Strip the `if not auth.startswith('Bearer ')` and other unrelated
        # `==` uses — none should appear except inside string literals.
        # Tokenize and assert no Eq/NotEq operators in the function AST.
        import ast
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    assert not isinstance(op, (ast.Eq, ast.NotEq)), (
                        f"_validate_secret contains a == or != compare at "
                        f"line {node.lineno}; use hmac.compare_digest only "
                        f"(2026-05-14 dimensional review S1)"
                    )

    def test_validate_secret_rejects_wrong_secret_with_correct_length(self):
        """Behavioral test: equal-length wrong secret must still be rejected.
        Catches a length-only check that would pass test_uses_only_constant_time."""
        app = _make_sync_app(sync_secret="abcdef12345")
        with app.test_client() as client:
            resp = client.post('/api/sync/periodic-roster',
                               headers={"Authorization": "Bearer xyzwvu67890"})
        assert resp.status_code == 401
```

- [x] **Step 1.3: Run tests to verify they fail**

```bash
source venv/bin/activate
python -m pytest tests/test_sync_routes.py::TestSyncWebhookAuth::test_validate_secret_uses_only_constant_time_compare tests/test_sync_routes.py::TestSyncWebhookAuth::test_validate_secret_rejects_wrong_secret_with_correct_length -v
```

Expected: first FAILS (current source contains `auth[7:] == expected`), second PASSES (existing `==` correctly rejects wrong secret of correct length — this test pins a property that should continue to hold AFTER the fix).

- [x] **Step 1.4: Apply the fix**

In `backend/routes/sync_routes.py`, change `_validate_secret`:

Current (lines 38-46):
```python
def _validate_secret():
    """Validate the Authorization: Bearer <secret> header."""
    expected = os.environ.get('PERIODIC_SYNC_SECRET')
    if not expected:
        return False
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return auth[7:] == expected
```

After:
```python
def _validate_secret():
    """Validate the Authorization: Bearer <secret> header.

    Uses hmac.compare_digest for a constant-time compare. The prior
    `==` operator was timing-dependent and vulnerable to byte-by-byte
    secret extraction by an attacker measuring response latency
    (closed 2026-05-14, dimensional review S1).
    """
    expected = os.environ.get('PERIODIC_SYNC_SECRET')
    if not expected:
        return False
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return hmac.compare_digest(auth[7:].encode('utf-8'),
                               expected.encode('utf-8'))
```

- [x] **Step 1.5: Run all sync_routes tests**

```bash
python -m pytest tests/test_sync_routes.py -v 2>&1 | tail -15
```

Expected: All pass (both new + existing 4 tests in TestSyncWebhookAuth).

- [x] **Step 1.6: Commit**

```bash
git add backend/routes/sync_routes.py tests/test_sync_routes.py
git commit -m "$(cat <<'EOF'
fix(security): use hmac.compare_digest on periodic-sync secret

The webhook secret comparison at sync_routes.py:46 used `==`, which is
short-circuit and timing-dependent. An attacker measuring response
latency can extract the secret byte-by-byte. Railway TLS bounds
network-level attacks but co-tenant scenarios remain.

Switch to hmac.compare_digest. Two regression tests pin the contract:
one AST-based test that asserts `==` is never used in _validate_secret
(catches the length-leak refactor pitfall flagged by Gemini-proxy plan
review), one behavioral test that pins rejection of an equal-length
wrong secret.

Source: 2026-05-14 dimensional review S1 (Codex + Gemini-proxy both
verified).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Paginate `list_users()` at 3 sites

**Vulnerability:** `sb.auth.admin.list_users()` defaults to 50 users per page. Three call sites assume the unpaginated call returns the full user list. Past 50 teachers, OAuth merges silently fail for users on page 2+, orphaning their data.

**Files:**
- Create: `backend/utils/supabase_users.py`
- Modify: `backend/routes/clever_routes.py:394`, `backend/routes/auth_routes.py:160`, `backend/routes/stripe_routes.py:254`
- Create: `tests/test_list_users_pagination_issue372.py`

**Design notes from reviews:**
- Codex: SDK signature confirmed as `list_users(page=N, per_page=K)` at `venv/.../supabase_auth/_sync/gotrue_admin_api.py:134`; returns a plain list, not an object.
- Gemini-proxy: original plan had `try/except TypeError` fallback → silent regression risk if SDK changes. **Remove the fallback.** If kwargs are rejected, that's a deploy-blocking error, not a silent degrade.
- Gemini-proxy: existing tests use `.return_value` (returns same list every call). With my pagination helper, if a test ever has 50+ users, the helper loops forever. Mitigation: hard cap at 100 pages (5,000 users) — well above any plausible deployment, but bounded.

- [x] **Step 2.1: Write failing tests**

Create `tests/test_list_users_pagination_issue372.py`:

```python
"""Regression tests for unpaginated list_users(). Issue tracked in PR body.
Source: 2026-05-14 dimensional review S4."""
from unittest.mock import MagicMock
import pytest


def _users(prefix, n):
    return [MagicMock(id=f"{prefix}{i}", email=f"{prefix}{i}@s.edu") for i in range(n)]


class TestListAllUsersPagination:
    def test_single_short_page_returns_all_users(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = _users("u", 10)
        assert len(list_all_users(sb)) == 10

    def test_multiple_full_pages_concatenated(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.side_effect = [
            _users("a", 50), _users("b", 25),
        ]
        assert len(list_all_users(sb)) == 75

    def test_two_full_pages_then_empty(self):
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.side_effect = [
            _users("a", 50), _users("b", 50), [],
        ]
        assert len(list_all_users(sb)) == 100

    def test_hard_cap_prevents_infinite_loop(self):
        """If a misconfigured mock returns a full page forever (like
        existing tests' .return_value pattern), the helper must hard-cap
        rather than loop indefinitely."""
        from backend.utils.supabase_users import list_all_users, _MAX_PAGES
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = _users("u", 50)
        result = list_all_users(sb)
        assert len(result) == 50 * _MAX_PAGES, (
            f"Expected hard cap at {_MAX_PAGES} pages × 50 = {50 * _MAX_PAGES}, "
            f"got {len(result)}"
        )

    def test_called_with_page_kwargs(self):
        """Helper must request specific pages — not the no-arg form."""
        from backend.utils.supabase_users import list_all_users
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = []
        list_all_users(sb)
        sb.auth.admin.list_users.assert_called_with(page=1, per_page=50)
```

- [x] **Step 2.2: Run tests to verify they fail**

```bash
python -m pytest tests/test_list_users_pagination_issue372.py -v
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'backend.utils.supabase_users'`.

- [x] **Step 2.3: Create the helper**

Create `backend/utils/supabase_users.py`:

```python
"""Pagination helper for Supabase Auth list_users().

The supabase-py SDK defaults to page_size=50 (verified at
venv/.../supabase_auth/_sync/gotrue_admin_api.py:134). Call sites that
need to scan ALL users (account merge, approval lookup, Stripe linking)
must iterate.

Regression tests: tests/test_list_users_pagination_issue372.py
Source: 2026-05-14 dimensional review S4.
"""
from typing import List

_PAGE_SIZE = 50
_MAX_PAGES = 100  # Hard cap: 5,000 users. Well above any plausible
                  # deployment; protects against mock-induced infinite
                  # loops in tests that use .return_value (Gemini-proxy
                  # plan review caught this risk pattern).


def list_all_users(sb) -> List:
    """Return ALL users from sb.auth.admin.list_users(), iterating pages.

    Calls list_users(page=N, per_page=50) until a page returns fewer than
    50 records (or we hit the hard cap). The SDK is expected to accept
    these kwargs; if it doesn't, this raises rather than silently
    falling back to single-page (Gemini-proxy plan review S5 — silent
    fallback is a security regression vector).
    """
    all_users = []
    for page in range(1, _MAX_PAGES + 1):
        resp = sb.auth.admin.list_users(page=page, per_page=_PAGE_SIZE)
        page_users = list(resp or [])
        all_users.extend(page_users)
        if len(page_users) < _PAGE_SIZE:
            break
    return all_users
```

- [x] **Step 2.4: Run the helper tests**

```bash
python -m pytest tests/test_list_users_pagination_issue372.py -v
```

Expected: All 5 tests PASS.

- [x] **Step 2.5: Swap call site 1 — `backend/routes/clever_routes.py:394`**

Read `clever_routes.py:385-405` first to capture context. Add import near other backend.utils imports:

```python
from backend.utils.supabase_users import list_all_users
```

Replace:
```python
res = sb.auth.admin.list_users()
matches = [
    u for u in (res or [])
    if getattr(u, 'email', None) and u.email.lower() == clever_email.lower()
]
```
With:
```python
res = list_all_users(sb)
matches = [
    u for u in res
    if getattr(u, 'email', None) and u.email.lower() == clever_email.lower()
]
```

- [x] **Step 2.6: Swap call site 2 — `backend/routes/auth_routes.py:160`**

Read `auth_routes.py:155-170`. Apply same import + replacement.

- [x] **Step 2.7: Swap call site 3 — `backend/routes/stripe_routes.py:254`**

Read `stripe_routes.py:250-265`. Apply same import + replacement.

- [x] **Step 2.8: Run all affected test files**

```bash
python -m pytest tests/test_clever_callback.py tests/test_auth_routes_unit.py tests/test_stripe_routes_unit.py tests/test_list_users_pagination_issue372.py -v 2>&1 | tail -20
```

Expected: All pass. Existing tests use `.return_value=[<list of N users>]` with N < 50, so the helper loop terminates on the first iteration (short page).

If any existing test fails because it asserts the EXACT call args (e.g., `assert_called_with()` with no args), update to `assert_called_with(page=1, per_page=50)`. Codex review notes most existing tests use `assert_called` or `.return_value` patterns that are robust to kwarg additions.

- [x] **Step 2.9: Commit**

```bash
git add backend/utils/supabase_users.py tests/test_list_users_pagination_issue372.py \
  backend/routes/clever_routes.py backend/routes/auth_routes.py backend/routes/stripe_routes.py
git commit -m "$(cat <<'EOF'
fix(security): paginate Supabase list_users() at 3 sites

supabase-py admin.list_users() defaults to 50 results per page. Three
call sites assumed the unpaginated default is the full user list:

  backend/routes/clever_routes.py:394  (OAuth account merge)
  backend/routes/auth_routes.py:160    (approval status lookup)
  backend/routes/stripe_routes.py:254  (customer linking)

Past 50 teachers, users on page 2+ would silently fail to merge with
existing accounts: fresh signup → new Supabase user → prior data
orphaned. Same shape for Stripe.

Extract list_all_users() helper in backend/utils/supabase_users.py
that iterates with explicit page/per_page kwargs. No silent fallback
on TypeError (per Gemini-proxy plan review S5 — silent degrade
re-introduces the bug). Hard cap at 100 pages = 5,000 users prevents
mock-induced infinite loops in tests that use .return_value.

Regression tests pin all 4 contracts: single page, multi-page, two
full pages then empty, hard-cap.

Source: 2026-05-14 dimensional review S4 (Codex + Gemini-proxy both
verified at the same 3 sites).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extract `filter_roster_to_teacher` helper + apply at manual `/api/clever/sync-roster`

**Vulnerability:** `backend/routes/clever_routes.py:528-536` filters the `students` list only when `selected_section_ids is not None`. A teacher syncing with no body receives the FULL district roster persisted under their `teacher_id` — Clever-compliance and FERPA-relevant violation. The `sections` filter at lines 495-513 is already unconditional and correct.

The fix extracts the existing `own_sections` logic into a reusable helper and applies it unconditionally to `students` as well. Task 4 reuses the same helper for the periodic-sync path.

**Files:**
- Create: `backend/services/clever_roster_scope.py`
- Modify: `backend/routes/clever_routes.py:495-540`
- Create: `tests/test_clever_roster_scope_issue372.py`

**Design notes from reviews:**
- Codex: route reads `os.getenv("CLEVER_DISTRICT_TOKEN")` at line 481, not via `get_clever_config`. Test must patch the env var, not the config.
- Codex: route calls `_run_async(sync_roster(...))` not `sync_roster` directly. Test must patch `_run_async` (pattern at `tests/test_clever_routes_gaps.py:177-180`).
- Codex: existing happy-path tests also patch `_sync_classes_to_db`, `extract_student_accommodations`, `map_sections_to_periods` (at `tests/test_clever_routes_gaps.py:190-197`). Add those mocks.

- [x] **Step 3.1: Write failing test for the helper**

Create `tests/test_clever_roster_scope_issue372.py`:

```python
"""Regression tests for the Clever district-roster leak.

Source: 2026-05-14 dimensional review S2.
Pinned by both Codex + Gemini-proxy plan reviews.
"""
import pytest


def _roster():
    """Teacher 'T' owns section S1 (students A, B).
    Other teacher 'OTHER' owns S2 (students C, D)."""
    return {
        "sections": [
            {"data": {"id": "S1", "teachers": ["T"],
                      "students": ["A", "B"], "name": "Period 1"}},
            {"data": {"id": "S2", "teachers": ["OTHER"],
                      "students": ["C", "D"], "name": "Period 2"}},
        ],
        "students": [
            {"data": {"id": x, "name": x}} for x in ["A", "B", "C", "D"]
        ],
    }


class TestFilterRosterToTeacher:
    def test_returns_only_teachers_own_sections(self):
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        sections, students = filter_roster_to_teacher(_roster(), "T")
        section_ids = [s.get("data", s).get("id") for s in sections]
        student_ids = sorted(s.get("data", s).get("id") for s in students)
        assert section_ids == ["S1"]
        assert student_ids == ["A", "B"], (
            f"Expected only [A, B] (T's section students); got "
            f"{student_ids}. District-roster leak."
        )

    def test_returns_empty_when_teacher_owns_no_sections(self):
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        sections, students = filter_roster_to_teacher(_roster(), "GHOST")
        assert sections == []
        assert students == []

    def test_handles_teacher_id_as_dict_form(self):
        """Clever sometimes returns teachers as [{id: '...'}] not [str]."""
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        roster = _roster()
        roster["sections"][0]["data"]["teachers"] = [{"id": "T"}]
        sections, students = filter_roster_to_teacher(roster, "T")
        assert [s.get("data", s).get("id") for s in sections] == ["S1"]

    def test_section_with_no_enrolled_students(self):
        """A section in the teacher's set but with no students attribute
        should not crash."""
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        roster = _roster()
        del roster["sections"][0]["data"]["students"]
        sections, students = filter_roster_to_teacher(roster, "T")
        assert [s.get("data", s).get("id") for s in sections] == ["S1"]
        assert students == []
```

- [x] **Step 3.2: Run tests to verify they fail**

```bash
python -m pytest tests/test_clever_roster_scope_issue372.py -v
```

Expected: All 4 FAIL with `ModuleNotFoundError`.

- [x] **Step 3.3: Create the helper**

Create `backend/services/clever_roster_scope.py`:

```python
"""Scope a Clever roster response to a single teacher's own sections.

Extracted from the existing logic at backend/routes/clever_routes.py:495-536
so both the manual sync route AND the periodic-sync cron path
(backend/routes/sync_routes.py:189-196) share one tenancy filter.

Source: 2026-05-14 dimensional review S2.
"""
from typing import List, Tuple


def _section_teacher_ids(section_data):
    """Extract teacher IDs from a section's `teachers` field.

    Clever returns this as a list of strings OR a list of dicts with
    'id'. Handle both shapes.
    """
    teachers = section_data.get("teachers", [])
    out = []
    for t in teachers:
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, dict):
            tid = t.get("id", "")
            if tid:
                out.append(tid)
    return out


def filter_roster_to_teacher(
    roster: dict, teacher_clever_id: str,
) -> Tuple[List[dict], List[dict]]:
    """Return (own_sections, own_students) for the given Clever teacher ID.

    own_sections: sections where the teacher is listed in the `teachers`
                  field. Empty list if the teacher_clever_id is falsy
                  or doesn't own any section in this roster.

    own_students: students enrolled in own_sections (deduplicated by
                  Clever student id). Excludes students from sections
                  the teacher doesn't own.
    """
    if not teacher_clever_id:
        return [], []

    all_sections = roster.get("sections", [])
    own_sections = []
    own_student_ids = set()
    for section in all_sections:
        sd = section.get("data", section)
        if teacher_clever_id in _section_teacher_ids(sd):
            own_sections.append(section)
            own_student_ids.update(sd.get("students", []))

    own_students = [
        s for s in roster.get("students", [])
        if s.get("data", s).get("id", "") in own_student_ids
    ]
    return own_sections, own_students
```

- [x] **Step 3.4: Run helper tests**

```bash
python -m pytest tests/test_clever_roster_scope_issue372.py -v
```

Expected: All 4 PASS.

- [x] **Step 3.5: Apply the helper at `backend/routes/clever_routes.py`**

Read `clever_routes.py:485-545` to capture context. Add import:
```python
from backend.services.clever_roster_scope import filter_roster_to_teacher
```

Then replace the block at approximately lines 495-536 (`# SECURITY: Server-side section filtering` through the existing `students = ...` block):

Current logic (495-536) builds `own_sections` inline, then conditionally filters students. Replace with:
```python
    # SECURITY: scope roster to this teacher's own sections + their
    # students. Previously, students was only filtered when
    # `selected_section_ids` was provided — a teacher syncing without
    # a section filter received the full district roster
    # (2026-05-14 dimensional review S2).
    clever_user = session.get("clever_user", {})
    teacher_clever_id = clever_user.get("clever_id", "")
    own_sections, own_students = filter_roster_to_teacher(roster, teacher_clever_id)
    # Mutate roster["sections"] so downstream map_sections_to_periods at
    # line ~567 sees only own sections in the response payload, not
    # the full district list (Codex revised-plan review Q4).
    roster["sections"] = own_sections

    # Audit-log the scoping outcome
    logger.info(
        "Filtered roster for teacher_hash=%s: %d sections, %d students "
        "(district had %d sections total)",
        hashlib.sha256(str(teacher_clever_id).encode()).hexdigest()[:8],
        len(own_sections),
        len(own_students),
        len(roster.get("sections", [])),
    )

    # Optional secondary filter: teacher selected a subset of their own sections
    sections = own_sections
    students = own_students
    if selected_section_ids is not None:
        selected_set = set(selected_section_ids)
        sections = [s for s in sections if s.get("data", s).get("id", "") in selected_set]
        section_student_ids = set()
        for s in sections:
            sd = s.get("data", s)
            section_student_ids.update(sd.get("students", []))
        students = [
            st for st in own_students
            if st.get("data", st).get("id", "") in section_student_ids
        ]
```

- [x] **Step 3.6: Write an integration test for the manual /api/clever/sync-roster route**

Append to `tests/test_clever_roster_scope_issue372.py`:

```python
class TestSyncRosterEndpointScopesToTeacher:
    """Integration: hits the actual route end-to-end with mocks for
    upstream Clever calls and downstream persistence. Test setup
    pattern mirrors tests/test_clever_routes_gaps.py:177-197 (per Codex
    plan review)."""

    def test_manual_sync_no_section_filter_does_not_leak_other_teachers(self):
        import os
        from unittest.mock import patch, MagicMock
        from flask import Flask, session
        from backend.routes.clever_routes import clever_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(clever_bp)

        persisted = {"students": None, "sections": None}
        def fake_persist_students(students, teacher_id):
            persisted["students"] = students
        def fake_persist_sections(sections, teacher_id):
            persisted["sections"] = sections

        # Match real env-var path at clever_routes.py:481
        env = {"CLEVER_CLIENT_ID": "cid", "CLEVER_CLIENT_SECRET": "csec",
               "CLEVER_DISTRICT_TOKEN": "tok",
               "CLEVER_REDIRECT_URI": "http://x/cb"}

        roster = _roster()  # T owns S1; OTHER owns S2

        with app.test_client() as client, \
             patch.dict(os.environ, env, clear=False), \
             patch('backend.routes.clever_routes._run_async',
                   return_value=roster), \
             patch('backend.routes.clever_routes.persist_roster_as_csv',
                   side_effect=fake_persist_students), \
             patch('backend.routes.clever_routes.persist_sections_as_periods',
                   side_effect=fake_persist_sections), \
             patch('backend.routes.clever_routes._sync_classes_to_db',
                   return_value={"classes": 1, "students": 2, "enrollments": 2}), \
             patch('backend.routes.clever_routes.extract_student_accommodations',
                   return_value={}), \
             patch('backend.routes.clever_routes.map_sections_to_periods',
                   return_value={}):
            with client.session_transaction() as sess:
                sess["clever_user"] = {"clever_id": "T", "user_id": "T"}
            resp = client.post('/api/clever/sync-roster', json={})

        assert resp.status_code == 200, (
            f"expected 200, got {resp.status_code}: {resp.data!r}"
        )
        assert persisted["students"] is not None, (
            "persist_roster_as_csv was never called — route short-circuited"
        )
        persisted_student_ids = sorted(
            s.get("data", s).get("id", "") for s in persisted["students"]
        )
        assert persisted_student_ids == ["A", "B"], (
            f"District-roster leak. Teacher T's persisted students: "
            f"{persisted_student_ids}; expected [A, B] only."
        )
```

- [x] **Step 3.7: Run the integration test (expect pass post-fix)**

```bash
python -m pytest tests/test_clever_roster_scope_issue372.py -v
```

Expected: All 5 tests PASS (4 helper unit tests + 1 integration).

- [x] **Step 3.8: Run all clever-route tests to catch regressions**

```bash
python -m pytest tests/test_clever_routes_gaps.py tests/test_clever_routes_remaining_gaps.py tests/test_clever_classes.py tests/test_clever_callback.py tests/test_clever_compliance.py -v 2>&1 | tail -15
```

Expected: All pass. If any breaks because it asserted the pre-bug "full district persisted" behavior — that test was pinning the bug; update it with a comment referencing this commit.

- [x] **Step 3.9: Commit**

```bash
git add backend/services/clever_roster_scope.py tests/test_clever_roster_scope_issue372.py \
  backend/routes/clever_routes.py
git commit -m "$(cat <<'EOF'
fix(security): scope Clever roster to teacher's own sections always

The students filter at clever_routes.py:528-536 was conditional on
selected_section_ids being provided in the request body. A teacher
hitting POST /api/clever/sync-roster with no body received the FULL
district roster persisted under their teacher_id — Clever-compliance
and FERPA-relevant violation. The sections filter at 495-513 was
already unconditional and correct; students was the gap.

Extract filter_roster_to_teacher() helper into
backend/services/clever_roster_scope.py so both this route AND the
periodic-sync cron (Task 4 below) share one tenancy filter. Apply
unconditionally to both sections and students; the optional
selected_section_ids only further narrows the already-scoped set.

Tests: 4 helper unit tests + 1 integration test that hits the route
end-to-end with the real env-var auth path (per Codex plan review,
the route reads os.getenv("CLEVER_DISTRICT_TOKEN") not
get_clever_config).

Source: 2026-05-14 dimensional review S2 (Codex + Gemini-proxy both
verified).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Apply `filter_roster_to_teacher` to periodic-sync cron path

**Vulnerability:** `backend/routes/sync_routes.py:189-196` fetches the full Clever roster (`clever_sync_roster(district_token)`) and passes `sections + students` to `_sync_classes_to_db(...)` with ZERO teacher filtering. This cron runs daily at 09:00 UTC weekdays via `.github/workflows/roster-sync.yml`. Same data-leak shape as Task 3 but **actively shipping in production today**.

Periodic sync runs without a session, so the teacher's Clever ID must be derived from the Graider `teacher_id`. Resolution path:
- If `teacher_id` starts with `clever:`, the Clever ID is the suffix
- Else (Supabase-UUID-linked Clever account), reverse-lookup via `load_clever_links()` (`{clever_id → graider_teacher_id}` map; iterate to find matching value)

**Files:**
- Modify: `backend/routes/sync_routes.py:166-200`
- Modify: `tests/test_sync_routes.py` (add tenancy test)

- [x] **Step 4.1: Write failing tenancy test**

Append to `tests/test_sync_routes.py`:

```python
class TestPeriodicSyncTenancy:
    """Regression for the periodic-sync district-roster leak.
    Same bug shape as the manual /api/clever/sync-roster path (Task 3
    in 2026-05-14-security-trio plan) but ships daily via
    .github/workflows/roster-sync.yml. Sourced from Gemini-proxy plan
    review."""

    def test_periodic_sync_filters_to_teachers_own_sections(self):
        from unittest.mock import patch
        import os
        from backend.routes.sync_routes import _sync_one_teacher

        # Teacher T owns S1 (students A, B); other teacher owns S2 (C, D)
        roster = {
            "sections": [
                {"data": {"id": "S1", "teachers": ["T"],
                          "students": ["A", "B"], "name": "Pd 1"}},
                {"data": {"id": "S2", "teachers": ["OTHER"],
                          "students": ["C", "D"], "name": "Pd 2"}},
            ],
            "students": [
                {"data": {"id": x, "name": x}} for x in ["A", "B", "C", "D"]
            ],
        }

        captured = {"sections": None, "students": None}
        def fake_sync_classes(sections, students, teacher_id):
            captured["sections"] = sections
            captured["students"] = students
            return {"classes": 1, "students": 2, "enrollments": 2}

        teacher = {
            "teacher_id": "clever:T",  # prefix form — Clever ID = T
            "provider": "clever",
            "config": {"district_token": "tok"},
        }

        with patch('backend.clever.sync_roster',
                   new_callable=lambda: __make_async_returning(roster)), \
             patch('backend.routes.clever_routes._sync_classes_to_db',
                   side_effect=fake_sync_classes), \
             patch('backend.roster_sync.deactivate_missing_students',
                   return_value=0):
            result = _sync_one_teacher(teacher)

        assert result["status"] != "skipped", f"Sync was skipped: {result}"
        assert captured["sections"] is not None, "sections were never passed"
        section_ids = [s.get("data", s).get("id") for s in captured["sections"]]
        student_ids = sorted(s.get("data", s).get("id") for s in captured["students"])
        assert section_ids == ["S1"], (
            f"Periodic sync passed cross-teacher sections to _sync_classes_to_db. "
            f"Got: {section_ids}; expected [S1] (T's only own section)."
        )
        assert student_ids == ["A", "B"], (
            f"District-roster leak in periodic sync. Got students: "
            f"{student_ids}; expected [A, B]."
        )


def __make_async_returning(value):
    """Build an async function that returns the given value, for mocking
    sync_roster which is `async def`."""
    async def _f(*args, **kwargs):
        return value
    return _f
```

- [x] **Step 4.2: Run test to verify it fails**

```bash
python -m pytest tests/test_sync_routes.py::TestPeriodicSyncTenancy -v
```

Expected: FAIL. The captured `students` will contain A+B+C+D (or sections will contain S1+S2).

- [x] **Step 4.3: Apply the fix**

In `backend/routes/sync_routes.py`, modify `_sync_one_teacher` (lines 166-200 area). After the existing `roster_data = loop.run_until_complete(...)` block at line 189, insert a tenancy filter:

```python
            sections = roster_data.get('sections', [])
            students = roster_data.get('students', [])

            # Tenancy filter: scope roster to this teacher's own sections.
            # Closes the periodic-sync copy of the manual-sync leak
            # (2026-05-14 dimensional review S2, periodic-sync variant
            # flagged by Gemini-proxy plan review). Without this, the
            # daily cron writes the FULL district roster to each
            # eligible teacher's teacher_id.
            from backend.services.clever_roster_scope import filter_roster_to_teacher
            from backend.auth import load_clever_links
            if teacher_id.startswith("clever:"):
                teacher_clever_id = teacher_id[len("clever:"):]
            else:
                links = load_clever_links()  # {clever_id: graider_teacher_id}
                teacher_clever_id = next(
                    (cid for cid, tid in links.items() if tid == teacher_id),
                    None,
                )
            if not teacher_clever_id:
                return {"teacher_id": teacher_id, "provider": provider,
                        "status": "skipped",
                        "error": "Could not resolve Clever ID for teacher",
                        "duration_s": round(time.time() - start, 1)}
            sections, students = filter_roster_to_teacher(
                {"sections": sections, "students": students},
                teacher_clever_id,
            )

            counts = _sync_classes_to_db(sections, students, teacher_id)
```

- [x] **Step 4.4: Run the tenancy test + all sync_routes tests**

```bash
python -m pytest tests/test_sync_routes.py -v 2>&1 | tail -15
```

Expected: All pass.

- [x] **Step 4.5: Commit**

```bash
git add backend/routes/sync_routes.py tests/test_sync_routes.py
git commit -m "$(cat <<'EOF'
fix(security): scope periodic-sync roster to each teacher's own sections

The periodic-sync cron at sync_routes.py:189-196 fetched the full
Clever district roster and passed it unfiltered to _sync_classes_to_db,
which wrote every district student under each eligible teacher's
teacher_id. Same bug shape as Task 3 (manual /api/clever/sync-roster),
but actively shipping daily at 09:00 UTC weekdays via
.github/workflows/roster-sync.yml.

Reuse the filter_roster_to_teacher() helper extracted in Task 3.
Periodic-sync derives the teacher's Clever ID from either the
"clever:" prefix on teacher_id, or a reverse-lookup of
load_clever_links() (clever_id → graider_teacher_id map) for
Supabase-linked Clever accounts. If neither resolves, the teacher
is skipped with a clear error rather than getting any cross-teacher
data.

Tenancy regression test in tests/test_sync_routes.py
TestPeriodicSyncTenancy.

Source: 2026-05-14 dimensional review S2 (periodic-sync variant
identified by Gemini-proxy plan review at workflow file
.github/workflows/roster-sync.yml:5 cron schedule).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4b: Apply `filter_roster_to_teacher` to post-login `_background_roster_sync`

**Vulnerability:** `backend/routes/clever_routes.py:247-257` runs in a background thread after every Clever OAuth callback when `CLEVER_DISTRICT_TOKEN` is set. Fetches `sync_roster(district_token)` (full district) and passes raw `students` + `sections` to `persist_roster_as_csv`, `persist_sections_as_periods`, and `_sync_classes_to_db`. Third site of the same bug; surfaced by Codex revised-plan review.

The function receives `teacher_id` as a parameter — Clever ID resolution uses the same prefix-or-reverse-lookup pattern as Task 4.

**Files:**
- Modify: `backend/routes/clever_routes.py:247-267`

- [x] **Step 4b.1: Apply the helper**

Modify `_background_roster_sync`:

```python
def _background_roster_sync(district_token, teacher_id):
    """Run roster sync in a background thread so OAuth callback returns immediately."""
    try:
        roster = _run_async(sync_roster(district_token))

        # Scope to this teacher's sections (2026-05-14 dimensional
        # review S2, background-sync variant per Codex review). Same
        # helper as the manual route + periodic cron.
        if teacher_id.startswith("clever:"):
            teacher_clever_id = teacher_id[len("clever:"):]
        else:
            links = load_clever_links()
            teacher_clever_id = next(
                (cid for cid, tid in links.items() if tid == teacher_id),
                None,
            )
        if not teacher_clever_id:
            logger.warning(
                "Background roster sync skipped: could not resolve "
                "Clever ID for teacher %s",
                hashlib.sha256(str(teacher_id).encode()).hexdigest()[:8],
            )
            return
        own_sections, own_students = filter_roster_to_teacher(
            roster, teacher_clever_id,
        )
        students = own_students
        sections = own_sections

        if students:
            persist_roster_as_csv(students, teacher_id)
        if sections:
            persist_sections_as_periods(sections, teacher_id)
            _sync_classes_to_db(sections, students, teacher_id)
        contacts = roster.get("contacts", [])
        if contacts and students:
            contact_map = extract_parent_contacts(contacts, students)
            if contact_map:
                persist_parent_contacts(contact_map, teacher_id)
        logger.info("Background roster sync complete: %d students, %d sections, %d contacts",
                    len(students), len(sections), len(contacts))
    except Exception as e:
        logger.warning("Background roster sync failed: %s", str(e))
        sentry_sdk.capture_exception(e)
```

Required imports (verify present at top of file; add if missing):
```python
from backend.services.clever_roster_scope import filter_roster_to_teacher
from backend.auth import load_clever_links  # already imported per line 30
```

- [x] **Step 4b.2: Run all clever-route tests**

```bash
python -m pytest tests/test_clever_routes_gaps.py tests/test_clever_routes_remaining_gaps.py tests/test_clever_classes.py tests/test_clever_callback.py -v 2>&1 | tail -15
```

Expected: all pass. Existing background-sync tests (search for `_background_roster_sync` in test files) typically mock the upstream pieces; the new filter is a no-op when the test's roster has only the test teacher's sections.

If a test specifically pinned the "background sync persists full roster" pre-bug behavior — update it with a comment referencing this commit.

- [x] **Step 4b.3: Commit**

```bash
git add backend/routes/clever_routes.py
git commit -m "$(cat <<'EOF'
fix(security): scope post-login _background_roster_sync to own teacher

Third site of the Clever district-roster leak (2026-05-14 dimensional
review S2, background-sync variant per Codex revised-plan review).
The function runs in a daemon thread after every Clever OAuth callback
when CLEVER_DISTRICT_TOKEN is set — fetches full district roster and
passes it unfiltered to persist_roster_as_csv, persist_sections_as_periods,
and _sync_classes_to_db.

Reuse filter_roster_to_teacher() from backend.services.clever_roster_scope
(extracted in Task 3) + the same Clever-ID resolver pattern from Task 4
(clever: prefix then load_clever_links reverse-lookup).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Full suite + PR + tracking issue for deferred state/nonce compares

- [x] **Step 5.1: Run the full backend suite**

```bash
python -m pytest tests/ --ignore=tests/e2e --ignore=tests/load -q 2>&1 | tail -5
```

Expected: ~4790-4800 passed (4786 baseline + new regression tests), 11 skipped.

- [x] **Step 5.2: Branch and push**

If not already on the branch:
```bash
git checkout -b fix/security-quartet-dimensional-review
git push -u origin fix/security-quartet-dimensional-review
```

- [x] **Step 5.3: File the deferred-scope tracking issue**

```bash
gh issue create --title "Constant-time compares missing on OAuth state/nonce (4 sites)" --body "$(cat <<'EOF'
Follow-up to PR <number-from-step-5.4-after-creation>. The same timing-vulnerable string compare closed on the periodic-sync webhook secret (sync_routes.py:46) exists at 4 more sites — OAuth state + nonce CSRF/replay defenses:

- backend/routes/clever_routes.py:312 — Clever OAuth state
- backend/routes/classlink_routes.py:237 — ClassLink state
- backend/routes/classlink_routes.py:258 — ClassLink nonce
- backend/routes/classlink_routes.py:348 — ClassLink (third check)
- backend/routes/lti_routes.py:113 — LTI state
- backend/routes/lti_routes.py:131 — LTI nonce

All are short-lived single-session CSRF/replay tokens — lower blast radius than a long-lived webhook secret (which is why these were deferred from the quartet PR), but same vulnerability class. A single dedicated PR closing all 5-6 sites should be a one-session effort.

Fix sketch (per site):
\`\`\`python
# Before
if state != expected_state:
    return jsonify({"error": "Invalid state"}), 400
# After
import hmac
if not hmac.compare_digest(state.encode("utf-8"),
                           expected_state.encode("utf-8")):
    return jsonify({"error": "Invalid state"}), 400
\`\`\`

Each site needs:
- Replace \`==\`/\`!=\` with \`hmac.compare_digest(... .encode(), ... .encode())\`
- One regression test per site asserting the AST has no \`Eq/NotEq\` against the compared token (same pattern as test_validate_secret_uses_only_constant_time_compare in tests/test_sync_routes.py)

Source: 2026-05-14 dimensional review (Gemini-proxy plan review of PR <number>).
EOF
)"
```

- [x] **Step 5.4: Open the PR**

```bash
gh pr create --title "fix(security): quartet — hmac.compare_digest + list_users pagination + Clever roster scope (manual + periodic)" --body "$(cat <<'EOF'
## Summary

Closes 4 security findings from the 2026-05-14 dimensional review (Claude + Codex + Gemini-proxy three-way reconciliation). Each fix is TDD with a focused regression test; each can be reverted individually.

## Fixes

### S1 — Constant-time secret compare on periodic-sync webhook
Switched \`auth[7:] == expected\` to \`hmac.compare_digest\` at \`backend/routes/sync_routes.py:46\`. Stronger AST-based regression test pins that \`==\`/\`!=\` are never reintroduced in \`_validate_secret\` (catches the length-leak refactor pitfall Gemini-proxy flagged).

### S4 — \`list_users()\` pagination at 3 sites
Helper \`list_all_users(sb)\` in new \`backend/utils/supabase_users.py\`. Applied at \`clever_routes.py:394\` (OAuth merge), \`auth_routes.py:160\` (approval lookup), \`stripe_routes.py:254\` (Stripe linking). No silent \`TypeError\` fallback (per Gemini-proxy review S5). Hard-cap at 5000 users protects against mock-induced infinite loops.

### S2 — Clever district roster scope (manual sync)
Filter at \`clever_routes.py:528-536\` was conditional on \`selected_section_ids\` being set. Teacher syncing with no body received the FULL district roster. Extracted shared helper \`filter_roster_to_teacher()\` in new \`backend/services/clever_roster_scope.py\`. Applied unconditionally.

### S2-periodic — Same leak shape in periodic-sync cron
\`sync_routes.py:189-196\` shipped the same leak daily via cron at \`.github/workflows/roster-sync.yml\`. Reused the helper from S2. Periodic-sync derives the teacher's Clever ID from either the \`clever:\` teacher_id prefix or \`load_clever_links()\` reverse-lookup; skips teachers it can't resolve rather than risk cross-tenant data.

## Out of scope (tracked)

The same constant-time vulnerability class exists at 6 OAuth state/nonce check sites (\`clever_routes.py:312\`, \`classlink_routes.py:237,258,348\`, \`lti_routes.py:113,131\`). Lower blast radius (session-bound CSRF tokens) — separate issue with file:line fix sketches per Rule #11.

## Test plan

- [x] All new regression tests fail BEFORE fix, pass AFTER
- [x] Full backend suite green (~4790-4800 passed, 11 skipped)
- [x] All 9 required CI checks green
- [x] E2e-nightly green (newly required gate as of PR #369)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [x] **Step 5.5: Once PR is open, edit the tracking issue body**

After PR creation, the issue body has a `<number>` placeholder. Edit the issue to reference the actual PR number:

```bash
gh issue edit <issue-number> --body-file <(gh issue view <issue-number> --json body -q .body | sed "s|<number-from-step-5.4-after-creation>|#$PR_NUMBER|g; s|<number>|#$PR_NUMBER|g")
```

- [x] **Step 5.6: Wait for CI + verify mergeable + merge**

```bash
gh pr checks  # all 9 must pass
gh pr view --json mergeable,mergeStateStatus -q '{mergeable, mergeStateStatus}'
# Expected: MERGEABLE / CLEAN
gh pr merge --squash --delete-branch
```

---

## Self-review

**Spec coverage:** ✓ S1, S2, S2-periodic, S4 all have dedicated tasks with regression tests. Deferred state/nonce items are tracked in their own issue with file:line sketches per Rule #11.

**Placeholder scan:** Two intentional placeholders remain (`<number-from-step-5.4-after-creation>` and `<issue-number>` / `$PR_NUMBER`) that are filled in at issue/PR creation time by gh CLI. These are not "TODO" — they're variables for the executor.

**Type consistency:** `filter_roster_to_teacher(roster, teacher_clever_id) -> (own_sections, own_students)` consistent across Task 3 helper definition, Task 3 manual-route call, Task 4 periodic-sync call. `list_all_users(sb) -> List` consistent. `_PAGE_SIZE = 50` referenced in tests and helper.

**Test reach:** Task 1 has source-AST test + behavioral test (rejection of equal-length wrong secret). Task 2 has 5 contracts pinned. Task 3 has 4 helper unit tests + 1 route integration test using the correct env-var auth path. Task 4 has 1 tenancy test using async-mock for `sync_roster`.

**Risk:** Largest risk is Task 4's Clever-ID resolution path failing for some pre-existing teacher whose teacher_id is neither `clever:`-prefixed nor present in `load_clever_links()`. Mitigation: skip with a clear error message rather than silently sync wrong data.
