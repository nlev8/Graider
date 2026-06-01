# District Admin Analytics View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the district admin a district-wide analytics rollup (totals, average score, A–F grade distribution, per-teacher list) in the `/district` console, reusing the school-admin aggregation.

**Architecture:** Extract the school overview's score/count aggregation into a shared `compute_overview(teacher_ids)` (metrics only; `admin_overview` keeps `total_teachers` + audit, byte-identical). A new `@_require_district_admin` endpoint computes the rollup over the **data-owner** teacher set (distinct `teacher_id` across `classes`/`published_content`/`published_assessments` — provider-agnostic, no PII over-exposure), behind a short-TTL cache, surfacing an `approximate` flag when the `_HARD_CAP` is hit. Frontend: a "District Analytics" section in the district console.

> **Deliberate deviation from spec §3.5 (count='exact'):** this plan does a **verbatim** lift of the existing row-pull aggregation into `compute_overview` (no `count='exact'` switch). Reason: a verbatim lift is *provably* byte-identical for the school path (Class A), whereas swapping totals to `count='exact'` is only identical below `_HARD_CAP`. The cache already covers v1 perf, so the `count='exact'` + DB-side aggregation optimization is folded into the scale-up follow-up **#611** — not v1.

**Tech Stack:** Python/Flask, Supabase, pytest, React/Vite, vitest.

**Spec:** `docs/superpowers/specs/2026-06-01-district-analytics-design.md` (v3)
**Class:** B (new endpoint) + A (behavior-preserving school refactor) ⇒ opus review.
**Branch:** `feature/district-analytics`. **Closes #606.** Scale-up follow-up: #611 (DB-side RPC).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/routes/admin_routes.py` | shared aggregation | `_chunked_in_rows_capped` + extract `compute_overview`; `admin_overview` delegates (byte-identical) |
| `backend/routes/district_routes.py` | district analytics endpoint | `_district_teacher_ids`, `district_analytics` + cache |
| `frontend/src/components/DistrictSetup.jsx` | console section | "District Analytics" section |
| `frontend/src/services/api.js` | api wrapper | `getDistrictAnalytics()` |
| tests | unit + integration + vitest | Create/modify |

Order: shared refactor → district teacher set → endpoint+cache → frontend. Each task independently committable.

---

### Task 1: Extract `compute_overview` (byte-identical school path)

**Files:**
- Modify: `backend/routes/admin_routes.py` (`_chunked_in_rows` delegate + new `_chunked_in_rows_capped` + `compute_overview`; `admin_overview` rewrite tail)
- Test: `tests/test_admin_routes.py`

- [ ] **Step 1: Write the failing/golden tests**

Add to `tests/test_admin_routes.py` (reuse the file's existing Supabase-mock pattern; if it has a fake-supabase fixture, use it — otherwise mock `backend.routes.admin_routes._get_supabase`):

```python
import backend.routes.admin_routes as ar


def test_compute_overview_empty_is_zeros(monkeypatch):
    monkeypatch.setattr(ar, "_get_supabase", lambda: object())
    out = ar.compute_overview([])
    assert out == {"total_students": 0, "total_assessments": 0, "average_score": None,
                   "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                   "scored_count": 0, "hit_hard_cap": False}


def test_compute_overview_aggregates_scores(monkeypatch):
    monkeypatch.setattr(ar, "_get_supabase", lambda: object())
    # published_assessments → join_codes; submissions → scores; classes/content/student_submissions
    def fake_capped(sb, table, column, values, select_cols, order=None, limit=None):
        if table == "published_assessments":
            return ([{"join_code": "JC1", "teacher_id": "t1"}], False)
        if table == "submissions":
            return ([{"score": 95}, {"score": 72}], False)
        if table == "classes":
            return ([{"id": "c1", "teacher_id": "t1"}], False)
        if table == "class_students":
            return ([{"class_id": "c1", "student_id": "s1"}], False)
        if table == "published_content":
            return ([{"id": "pc1", "class_id": "c1"}], False)
        if table == "student_submissions":
            return ([{"score": 60}], False)
        return ([], False)
    monkeypatch.setattr(ar, "_chunked_in_rows_capped", fake_capped)
    out = ar.compute_overview(["t1"])
    assert out["total_students"] == 1
    assert out["total_assessments"] == 2          # 1 join-code assessment + 1 published_content
    assert out["scored_count"] == 3               # 95, 72, 60
    assert out["average_score"] == round((95 + 72 + 60) / 3, 1)
    assert out["grade_distribution"] == {"A": 1, "B": 0, "C": 1, "D": 1, "F": 0}
    assert out["hit_hard_cap"] is False


def test_compute_overview_flags_hard_cap(monkeypatch):
    monkeypatch.setattr(ar, "_get_supabase", lambda: object())
    def fake_capped(sb, table, column, values, select_cols, order=None, limit=None):
        if table == "published_assessments":
            return ([{"join_code": "JC1", "teacher_id": "t1"}], False)
        if table == "submissions":
            return ([{"score": 90}], True)        # this pull hit the cap
        return ([], False)
    monkeypatch.setattr(ar, "_chunked_in_rows_capped", fake_capped)
    assert ar.compute_overview(["t1"])["hit_hard_cap"] is True


def test_admin_overview_no_data_branch_unchanged(monkeypatch, <app-client fixture>):
    # No supabase → existing "Viewed overview (no data)" audit + zeros, total_teachers from len(teachers)
    monkeypatch.setattr(ar, "_discover_teachers", lambda role: [{"user_id": None, "name": "X"}])  # blank user_id
    monkeypatch.setattr(ar, "_get_supabase", lambda: None)
    # drive GET /api/admin/overview as a school admin (reuse the file's admin-auth helper)
    resp = <drive>
    body = resp.get_json()
    assert body["total_teachers"] == 1            # blank-user_id teacher still counted
    assert body["total_students"] == 0 and body["average_score"] is None
    assert set(body.keys()) == {"total_teachers", "total_students", "total_assessments",
                                "average_score", "grade_distribution"}   # no scored_count/hit_hard_cap leaked
```

READ `tests/test_admin_routes.py` first to wire the `<app-client fixture>` / admin-auth + the existing supabase mock the same way its current `admin_overview` tests do. The load-bearing assertions are the ones shown.

- [ ] **Step 2: Run → confirm FAIL**

Run: `source venv/bin/activate && pytest tests/test_admin_routes.py -k "compute_overview or no_data_branch" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'compute_overview'`.

- [ ] **Step 3: Implement**

In `backend/routes/admin_routes.py`:

(a) Make `_chunked_in_rows` delegate to a new cap-aware `_chunked_in_rows_capped` (byte-identical rows; the `capped` flag is the only addition):

```python
def _chunked_in_rows_capped(sb, table, column, values, select_cols, order=None, limit=None):
    """Same as _chunked_in_rows but also returns whether any chunk hit the
    per-chunk `_HARD_CAP` (i.e. paginated up to `target` without a short page
    → the result is truncated). Returns (rows, capped)."""
    if not values:
        return [], False
    out: list = []
    capped = False
    target = limit if limit is not None else _HARD_CAP
    for i in range(0, len(values), _IN_CHUNK_SIZE):
        chunk = values[i:i + _IN_CHUNK_SIZE]
        offset = 0
        while offset < target:
            page_size = min(_PAGE_SIZE, target - offset)
            q = sb.table(table).select(select_cols).in_(column, chunk)
            if order is not None:
                col, desc = order
                q = q.order(col, desc=desc)
            q = q.range(offset, offset + page_size - 1)
            rows = q.execute().data or []
            out.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
        else:
            capped = True   # while-loop exhausted `target` without a short page → hit the cap
    return out, capped


def _chunked_in_rows(sb, table, column, values, select_cols, order=None, limit=None):
    rows, _ = _chunked_in_rows_capped(sb, table, column, values, select_cols, order, limit)
    return rows
```
(Replace the existing `_chunked_in_rows` body with the two functions above; keep the existing docstring on `_chunked_in_rows`. Behavior of `_chunked_in_rows` is unchanged — same rows.)

(b) Add `compute_overview` — a verbatim lift of `admin_overview`'s steps 1-6, returning metrics + `scored_count` + `hit_hard_cap` (uses `_chunked_in_rows_capped` so it can OR the cap flags):

```python
def compute_overview(teacher_ids):
    """Aggregate score/count metrics across the given teacher ids.
    Returns {total_students, total_assessments, average_score,
             grade_distribution: {A..F}, scored_count, hit_hard_cap}.
    Does NOT return total_teachers — callers own it. [] / no-supabase → zeros."""
    metrics = {"total_students": 0, "total_assessments": 0, "average_score": None,
               "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
               "scored_count": 0, "hit_hard_cap": False}
    sb = _get_supabase()
    if not sb or not teacher_ids:
        return metrics
    all_scores: list = []
    capped = False
    try:
        pa_rows, c1 = _chunked_in_rows_capped(sb, "published_assessments", "teacher_id", teacher_ids, "join_code, teacher_id")
        capped = capped or c1
        join_codes = [r["join_code"] for r in pa_rows if r.get("join_code")]
        metrics["total_assessments"] += len(join_codes)
        if join_codes:
            sub_rows, c2 = _chunked_in_rows_capped(sb, "submissions", "join_code", join_codes, "score")
            capped = capped or c2
            for s in sub_rows:
                if s.get("score") is not None:
                    try: all_scores.append(float(s["score"]))
                    except (ValueError, TypeError): pass
        classes_rows, c3 = _chunked_in_rows_capped(sb, "classes", "teacher_id", teacher_ids, "id, teacher_id")
        capped = capped or c3
        class_ids = [c["id"] for c in classes_rows if c.get("id")]
        if class_ids:
            cs_rows, c4 = _chunked_in_rows_capped(sb, "class_students", "class_id", class_ids, "class_id, student_id")
            capped = capped or c4
            metrics["total_students"] = len(cs_rows)
            pc_rows, c5 = _chunked_in_rows_capped(sb, "published_content", "class_id", class_ids, "id, class_id")
            capped = capped or c5
            metrics["total_assessments"] += len(pc_rows)
            content_ids = [c["id"] for c in pc_rows if c.get("id")]
            if content_ids:
                ss_rows, c6 = _chunked_in_rows_capped(sb, "student_submissions", "content_id", content_ids, "score")
                capped = capped or c6
                for s in ss_rows:
                    if s.get("score") is not None:
                        try: all_scores.append(float(s["score"]))
                        except (ValueError, TypeError): pass
    except Exception as e:
        logger.warning("compute_overview aggregation error: %s", e)
        sentry_sdk.capture_exception(e)
    metrics["hit_hard_cap"] = capped
    metrics["scored_count"] = len(all_scores)
    if all_scores:
        metrics["average_score"] = round(sum(all_scores) / len(all_scores), 1)
        for score in all_scores:
            if score >= 90: metrics["grade_distribution"]["A"] += 1
            elif score >= 80: metrics["grade_distribution"]["B"] += 1
            elif score >= 70: metrics["grade_distribution"]["C"] += 1
            elif score >= 60: metrics["grade_distribution"]["D"] += 1
            else: metrics["grade_distribution"]["F"] += 1
    return metrics
```

(c) Rewrite `admin_overview` to use it while preserving BOTH audit branches + `total_teachers` + the exact public response keys:

```python
def admin_overview():
    """Aggregate metrics across admin's teachers."""
    teachers = _discover_teachers(g.admin_role)
    teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]
    sb = _get_supabase()
    if not sb or not teacher_ids:
        audit_log("ADMIN_VIEW_OVERVIEW", "Viewed overview (no data)", user="admin", teacher_id=g.teacher_id)
        return jsonify({"total_teachers": len(teachers), "total_students": 0, "total_assessments": 0,
                        "average_score": None, "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}})
    m = compute_overview(teacher_ids)
    audit_log("ADMIN_VIEW_OVERVIEW", f"Viewed overview: {len(teachers)} teachers, {m['scored_count']} scores",
              user="admin", teacher_id=g.teacher_id)
    return jsonify({"total_teachers": len(teachers), "total_students": m["total_students"],
                    "total_assessments": m["total_assessments"], "average_score": m["average_score"],
                    "grade_distribution": m["grade_distribution"]})   # explicit keys; no scored_count/hit_hard_cap leak
```

- [ ] **Step 4: Run → PASS**

Run: `pytest tests/test_admin_routes.py -v` (all green — the new tests + the **existing** `admin_overview` tests, which prove byte-identical school behavior). Then `pytest tests/ -k "admin or overview" -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/admin_routes.py tests/test_admin_routes.py
git commit -m "refactor(admin): extract compute_overview (+ cap flag); admin_overview byte-identical [Class A]"
```

---

### Task 2: District data-owner teacher set (`_district_teacher_ids`)

**Files:**
- Modify: `backend/routes/district_routes.py`
- Test: `tests/test_district_analytics.py` (Create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_district_analytics.py`:

```python
import backend.routes.district_routes as dr


class _FakeQuery:
    def __init__(self, rows): self._rows = rows
    def select(self, *a, **k): return self
    def range(self, *a, **k): return self
    def execute(self): return type("R", (), {"data": self._rows})()


class _FakeSB:
    def __init__(self, by_table): self._by_table = by_table
    def table(self, name): return _FakeQuery(self._by_table.get(name, []))


def test_district_teacher_ids_unions_and_includes_clever(monkeypatch):
    sb = _FakeSB({
        "classes": [{"teacher_id": "uuid-1"}, {"teacher_id": "uuid-1"}],
        "published_content": [{"teacher_id": "uuid-2"}],
        "published_assessments": [{"teacher_id": "clever:abc"}, {"teacher_id": "uuid-1"}],
    })
    ids = dr._district_teacher_ids(sb)
    assert ids == {"uuid-1", "uuid-2", "clever:abc"}   # distinct union; clever:{id} owner included


def test_district_teacher_ids_empty(monkeypatch):
    assert dr._district_teacher_ids(_FakeSB({})) == set()
```

(If `_district_teacher_ids` paginates via `.range`, the fake returns all rows on the first page — fine for the test. If your real impl uses `_chunked_in_rows`-style pagination over a single un-filtered select, adapt the fake to return `[]` on the second page; keep the assertion.)

- [ ] **Step 2: Run → FAIL**

Run: `pytest tests/test_district_analytics.py -k teacher_ids -v` — expect `AttributeError: ... no attribute '_district_teacher_ids'`.

- [ ] **Step 3: Implement**

In `backend/routes/district_routes.py`, add:

```python
def _district_teacher_ids(sb):
    """Distinct teacher_id across the teacher-owner tables (classes,
    published_content, published_assessments). Provider-agnostic: includes
    UUID teachers AND clever:{id}/legacy owners; excludes admin/staff-only
    accounts that never owned data. Paginates each table by _PAGE rows."""
    if not sb:
        return set()
    ids: set = set()
    _PAGE = 1000
    for table in ("classes", "published_content", "published_assessments"):
        offset = 0
        while True:
            rows = sb.table(table).select("teacher_id").range(offset, offset + _PAGE - 1).execute().data or []
            for r in rows:
                tid = r.get("teacher_id")
                if tid:
                    ids.add(str(tid))
            if len(rows) < _PAGE:
                break
            offset += _PAGE
    return ids
```

- [ ] **Step 4: Run → PASS**

Run: `pytest tests/test_district_analytics.py -k teacher_ids -v` (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/district_routes.py tests/test_district_analytics.py
git commit -m "feat(district): _district_teacher_ids — data-owner teacher set [Class B]"
```

---

### Task 3: District analytics endpoint + cache

**Files:**
- Modify: `backend/routes/district_routes.py`
- Test: `tests/test_district_analytics.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_district_analytics.py` (reuse the district-admin client + `_patch_store`-style setup from `tests/test_district_sso_admins.py`):

```python
import pytest
from flask import Flask


@pytest.fixture
def client():
    app = Flask(__name__); app.config["TESTING"] = True; app.config["SECRET_KEY"] = "t"
    from backend.routes.district_routes import district_bp
    app.register_blueprint(district_bp)
    return app.test_client()


def _as_district_admin(client):
    with client.session_transaction() as s:
        s["district_admin"] = True


@pytest.fixture(autouse=True)
def _clear_analytics_cache():
    # The endpoint caches in a module global; clear before each test to avoid
    # cross-test pollution from the persistent cache.
    dr._district_analytics_cache_clear()
    yield


def test_analytics_requires_district_admin(client):
    assert client.get("/api/district/analytics").status_code in (401, 403)


def test_analytics_returns_rollup(client, monkeypatch):
    monkeypatch.setattr(dr, "_get_supabase", lambda: object())
    monkeypatch.setattr(dr, "_district_teacher_ids", lambda sb: {"uuid-1", "clever:abc"})
    import backend.routes.admin_routes as ar
    monkeypatch.setattr(ar, "compute_overview",
                        lambda ids: {"total_students": 5, "total_assessments": 3, "average_score": 88.0,
                                     "grade_distribution": {"A": 2, "B": 1, "C": 0, "D": 0, "F": 0},
                                     "scored_count": 3, "hit_hard_cap": True})
    monkeypatch.setattr(dr, "_district_teacher_rows", lambda ids, sb: [{"user_id": "uuid-1", "name": "T", "email": "t@x"}])
    dr._district_analytics_cache_clear()   # ensure no stale cache
    _as_district_admin(client)
    body = client.get("/api/district/analytics").get_json()
    assert body["overview"]["total_teachers"] == 2
    assert body["overview"]["average_score"] == 88.0
    assert body["approximate"] is True
    assert set(body["overview"].keys()) == {"total_teachers", "total_students", "total_assessments",
                                            "average_score", "grade_distribution"}   # no internal fields
    assert body["teachers"][0]["name"] == "T"


def test_analytics_cache_serves_within_ttl(client, monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(dr, "_get_supabase", lambda: object())
    def _count_ids(sb): calls["n"] += 1; return set()
    monkeypatch.setattr(dr, "_district_teacher_ids", _count_ids)
    dr._district_analytics_cache_clear()
    _as_district_admin(client)
    client.get("/api/district/analytics")
    client.get("/api/district/analytics")
    assert calls["n"] == 1   # second hit served from cache, no re-query
```

- [ ] **Step 2: Run → FAIL**

Run: `pytest tests/test_district_analytics.py -k "analytics" -v` — expect 404 / AttributeError.

- [ ] **Step 3: Implement**

In `backend/routes/district_routes.py` add the cache + endpoint (`_require_district_admin`, `handle_route_errors`, `jsonify`, `audit_log`, `logger` already imported; add `import time`):

```python
_ANALYTICS_TTL = 300  # seconds (single-tenant — see spec §3.5)
_analytics_cache = {"at": 0.0, "data": None}


def _district_analytics_cache_clear():
    _analytics_cache["at"] = 0.0
    _analytics_cache["data"] = None


def _district_teacher_rows(ids, sb):
    """Per-teacher rows: name/email (best-effort from auth users) + counts via
    _enrich_teachers. ids = data-owner teacher_id set."""
    from backend.utils.supabase_users import list_all_users
    from backend.routes.admin_routes import _enrich_teachers
    name_by_id = {}
    try:
        for u in (list_all_users(sb) or []):
            uid = getattr(u, "id", None)
            if uid:
                name_by_id[str(uid)] = {"email": getattr(u, "email", "") or "",
                                        "name": (getattr(u, "user_metadata", {}) or {}).get("first_name", "") or ""}
    except Exception as e:
        logger.warning("district teacher name lookup failed (non-fatal): %s", type(e).__name__)
    teachers = [{"user_id": tid, "email": name_by_id.get(tid, {}).get("email", ""),
                 "name": name_by_id.get(tid, {}).get("name", "") or "—"} for tid in sorted(ids)]
    _enrich_teachers(teachers)   # adds classes_count/students_count/assessments_count/last_activity
    return teachers


def _build_district_analytics():
    from backend.routes.admin_routes import compute_overview
    sb = _get_supabase()
    ids = _district_teacher_ids(sb) if sb else set()
    m = compute_overview(sorted(ids)) if ids else {
        "total_students": 0, "total_assessments": 0, "average_score": None,
        "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}, "scored_count": 0, "hit_hard_cap": False}
    teachers = _district_teacher_rows(ids, sb) if ids else []
    return {
        "overview": {"total_teachers": len(ids), "total_students": m["total_students"],
                     "total_assessments": m["total_assessments"], "average_score": m["average_score"],
                     "grade_distribution": m["grade_distribution"]},
        "teachers": teachers,
        "approximate": bool(m.get("hit_hard_cap")),
    }


@district_bp.route("/api/district/analytics", methods=["GET"])
@_require_district_admin
@handle_route_errors
def district_analytics():
    now = time.time()
    if _analytics_cache["data"] is None or (now - _analytics_cache["at"]) > _ANALYTICS_TTL:
        _analytics_cache["data"] = _build_district_analytics()
        _analytics_cache["at"] = now
    audit_log("DISTRICT_VIEW_ANALYTICS",
              f"teachers={_analytics_cache['data']['overview']['total_teachers']}",
              user="district_admin", teacher_id="system")
    return jsonify(_analytics_cache["data"])
```

Note: the audit fires on every request (even cache hits) so views are tracked; the expensive build is what's cached.

- [ ] **Step 4: Run → PASS**

Run: `pytest tests/test_district_analytics.py -v` (all). Then `pytest tests/ -k district -q` (existing district tests green). Then `python -c "import backend.app" && echo OK` (no circular import: district_routes imports admin_routes helpers at call-time inside the functions — confirm).

- [ ] **Step 5: Commit**

```bash
git add backend/routes/district_routes.py tests/test_district_analytics.py
git commit -m "feat(district): /api/district/analytics endpoint + short-TTL cache [Class B]"
```

---

### Task 4: District console "District Analytics" section + api wrapper

**Files:**
- Modify: `frontend/src/services/api.js`, `frontend/src/components/DistrictSetup.jsx`
- Test: `frontend/src/__tests__/DistrictAnalytics.test.jsx` (Create)

- [ ] **Step 1: Write the failing test**

READ `DistrictSetup.jsx` (the `SsoAdminSection` added recently is a good template for an exported section component + the `styles`/`React.createElement` conventions). Create `frontend/src/__tests__/DistrictAnalytics.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('../services/api', () => ({
  __esModule: true,
  getDistrictAnalytics: vi.fn(async () => ({
    overview: { total_teachers: 4, total_students: 120, total_assessments: 30, average_score: 87.5,
                grade_distribution: { A: 10, B: 8, C: 5, D: 2, F: 1 } },
    teachers: [{ user_id: 'u1', name: 'Jane', email: 'j@x', classes_count: 3, students_count: 40, assessments_count: 9 }],
    approximate: false,
  })),
}))

import * as api from '../services/api'
import { DistrictAnalyticsSection } from '../components/DistrictSetup'

describe('DistrictAnalyticsSection', () => {
  beforeEach(() => vi.clearAllMocks())
  it('renders the rollup + a teacher row', async () => {
    render(<DistrictAnalyticsSection isDark={true} />)
    await waitFor(() => expect(screen.getByText(/120/)).toBeTruthy())   // total students
    expect(screen.getByText(/87.5/)).toBeTruthy()                       // average score
    expect(screen.getByText(/Jane/)).toBeTruthy()
  })
})
```
Adapt assertions to your rendered text; if jest-dom isn't configured, use `.toBeTruthy()` (the repo convention — see `DistrictSsoAdmins.test.jsx`). Include any other api exports `DistrictSetup` imports in the `vi.mock` so the import resolves.

- [ ] **Step 2: Run → FAIL**

Run: `cd frontend && npx vitest run src/__tests__/DistrictAnalytics.test.jsx` — expect FAIL (export/wrapper missing).

- [ ] **Step 3: Implement**

In `frontend/src/services/api.js`, add (and register in the default-export object):
```js
export async function getDistrictAnalytics() {
  return fetchApi('/api/district/analytics')
}
```

In `frontend/src/components/DistrictSetup.jsx`, add and EXPORT a `DistrictAnalyticsSection` (mirror `SsoAdminSection`'s structure + `React.createElement` + `styles`). On mount → `api.getDistrictAnalytics()`. Render: four stat cards (Teachers/Students/Assessments/Average Score `… + "%"` or "—" when null), A–F grade-distribution bars, a scrollable teacher list (name/email + classes/students/assessments counts), and — when `approximate` is true — a small note "Counts are approximate above 100k rows." Render it in the authenticated `ConfigForm` (alongside the SSO Admin Access section). Follow the file's style objects; no `glass-card` classes (those are AdminTab's, not this file's).

- [ ] **Step 4: Run tests + build**

Run: `cd frontend && npx vitest run src/__tests__/DistrictAnalytics.test.jsx` (pass), then `npx vitest run` (full suite, no regression), then `npm run build`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.js frontend/src/components/DistrictSetup.jsx frontend/src/__tests__/DistrictAnalytics.test.jsx
git commit -m "feat(district): District Analytics console section [Class B]"
```

---

## Per-Branch Verification (before PR)

- [ ] Full backend suite: `source venv/bin/activate && pytest -q --ignore=tests/load` — green (proves the school refactor is byte-identical: all existing `admin_overview` tests pass unchanged).
- [ ] Cross-cutting grep: `for f in backend/routes/admin_routes.py backend/routes/district_routes.py; do grep -rln "$f" tests/; done` — run every surfaced test.
- [ ] **Clever non-regression:** `pytest tests/test_clever_compliance.py tests/test_clever_callback.py -q` (untouched).
- [ ] `ruff check backend/routes/admin_routes.py backend/routes/district_routes.py`; `bandit -q -r` the same.
- [ ] `cd frontend && npx vitest run && npm run build`.
- [ ] No circular import: `python -c "import backend.app" && echo OK` (admin_routes helpers imported at call-time in district_routes).
- [ ] Spec reviewer ✅ then **opus** code-quality reviewer ✅.
- [ ] GitNexus reindex: `npx gitnexus analyze --embeddings`.
- [ ] PR body: Class B+A; spec/plan refs; **the teacher/row scale it was tested at** (no silent scale assumption); follow-up #611 (DB-side RPC); closes #606.

## Manual / Operator Verification

After deploy: log into `/district`, open "District Analytics" → confirm non-zero totals/average/grade-distribution and a teacher list that matches reality; cross-check the average against a known school's AdminTab. Confirm a non-district session can't reach `/api/district/analytics` (401).
