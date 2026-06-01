# District Admin Analytics View — Design

**Date:** 2026-06-01
**Class:** B (new auth-gated endpoint) + A (behavior-preserving refactor of the school overview)
**Status:** Approved (brainstorming) → three-way review (Claude/Codex/Gemini) → ready for implementation plan
**Closes:** #606

---

## 1. Problem

The school-admin **Admin tab** (`frontend/src/tabs/AdminTab.jsx`) renders a real "School-Wide Analytics" dashboard (total teachers/students/assessments, average score, A–F grade distribution, per-teacher breakdown, activity), scoped to one school via `/api/admin/overview` + `/api/admin/teachers`. The **district admin** console (`/district`) is **config-only** — SIS/AI keys, admin designation, teacher search — with **no analytics at all**. So the top admin tier sees *less* data than the school tier: a district admin can configure the district and decide who's an admin, but can't see district-wide numbers.

## 2. Goal

Give the district admin a **district-wide rollup** of the same metrics the school admin sees, aggregated across the **whole deployment** instead of one school: totals, average score, grade distribution, and a teacher list with per-teacher counts. Reuse the existing aggregation — this is refactor-and-reuse, not new analytics.

**Non-goals (v1):** per-school breakdown / school-vs-school comparison (needs reliable school-per-teacher attribution Graider doesn't store for regular teachers today — deferred); time-series/trends; caching (add only if measured slow); per-user district admin (#608, separate).

## 3. Design

### 3.1 Shared aggregation (`compute_overview`)

Extract the aggregation core out of `admin_overview` (`backend/routes/admin_routes.py`) into a module-level, reusable function:

```python
def compute_overview(teacher_ids):
    """Aggregate metrics across the given teacher UUIDs.

    Returns {total_teachers, total_students, total_assessments,
             average_score, grade_distribution: {A..F}}.
    Chunks Supabase .in_() queries (DEFAULT chunk) to avoid the >1000-row
    undercount. teacher_ids = [] → zeros.
    """
```

`admin_overview` becomes: `teachers = _discover_teachers(g.admin_role); return jsonify({**base, **compute_overview([t["user_id"] ...])})` — its output stays **byte-identical** (Class A refactor; the existing school path is unchanged). `compute_overview` preserves the existing chunked `.in_()` query logic verbatim (the `admin_routes.py:390` >1000-row safeguard).

### 3.2 District teacher set

District-wide "all teachers" = **all Supabase Auth users** via `list_all_users(sb)` (`backend/utils/supabase_users.py`). Rationale: every Graider teacher/admin is a Supabase auth user; students authenticate via `X-Student-Token`, not auth users — so the auth-user set is cleanly "all teachers/admins," with no student contamination. (A teacher with zero data simply contributes zero to the sums.)

### 3.3 District analytics endpoint

```python
@district_bp.route("/api/district/analytics", methods=["GET"])
@_require_district_admin
@handle_route_errors
def district_analytics():
    sb = _get_supabase()
    users = list_all_users(sb) if sb else []
    teacher_ids = [u.id for u in users if getattr(u, "id", None)]
    overview = compute_overview(teacher_ids)          # imported from admin_routes
    teachers = _district_teacher_rows(users)          # email/name + per-teacher counts (reuse _enrich_*)
    audit_log("DISTRICT_VIEW_ANALYTICS", f"teachers={overview['total_teachers']}",
              user="district_admin", teacher_id="system")
    return jsonify({"overview": overview, "teachers": teachers})
```

`_district_teacher_rows` builds the per-teacher list (email, name, classes/students/assessments counts, last_activity) by reusing the existing `_enrich_*` counters from `admin_routes` over all teacher_ids (also chunked). If the `_enrich_*` helpers are tightly coupled to the school path, extract the minimal shared piece alongside `compute_overview`.

Gated by `@_require_district_admin` (the district session), NOT `@require_admin` (the school `admin_role`) — a non-district caller gets the existing 401.

### 3.4 Frontend — "District Analytics" section

A new section in the authenticated `ConfigForm` of `frontend/src/components/DistrictSetup.jsx` (alongside SIS config / SSO Admin Access). On mount it calls `api.getDistrictAnalytics()` and renders, reusing `AdminTab`'s presentation:
- **Stat cards:** Total Teachers / Students / Assessments / Average Score.
- **Grade Distribution** bars (A–F).
- **Teacher list:** name + per-teacher counts (collapsible/scrollable if long).

Built with `React.createElement` + the district console's style objects (it doesn't use JSX). New `api.js` wrapper `getDistrictAnalytics()` → `GET /api/district/analytics`.

## 4. Data flow

```
District admin (password/SSO) → /district console → "District Analytics" section
  └─ GET /api/district/analytics  (@_require_district_admin)
       ├─ teacher_ids = [u.id for u in list_all_users(sb)]        # all teachers
       ├─ overview = compute_overview(teacher_ids)                # shared w/ school path, chunked
       └─ teachers = _district_teacher_rows(users)                # per-teacher counts
  → render stat cards + grade bars + teacher list
```

## 5. Error handling / security / perf

- **Auth:** `@_require_district_admin` only; non-district callers get 401 (no exposure of district-wide data to a school admin or teacher).
- **No Supabase / no users:** returns zeros + empty teacher list (no crash).
- **PII:** audit log records only a count, not emails/names. The response carries teacher names/emails to the *district admin* (authorized) — consistent with the school AdminTab response.
- **Perf:** on-demand admin dashboard; chunked `.in_()` queries bound each round-trip. v1 has no cache; a short-TTL cache is a noted later add if measured slow at large districts. (Flag in the PR what scale this was/wasn't tested at — no silent caps.)

## 6. Files touched

- `backend/routes/admin_routes.py` — extract `compute_overview` (+ minimal shared enrich piece); `admin_overview` calls it (behavior-preserving).
- `backend/routes/district_routes.py` — new `district_analytics` endpoint + `_district_teacher_rows`.
- `frontend/src/components/DistrictSetup.jsx` — "District Analytics" section.
- `frontend/src/services/api.js` — `getDistrictAnalytics()` wrapper.
- Tests: `tests/test_admin_routes.py` (compute_overview unit + school-overview-unchanged golden), `tests/test_district_analytics.py` (endpoint auth + rollup + empty), frontend vitest for the section.

## 7. Testing (TDD; mixed A/B ⇒ opus review)

- `compute_overview(teacher_ids)`: totals, average_score, A–F distribution with mocked Supabase; the >1000-id chunking boundary; `[]` → zeros.
- **School overview byte-identical** after the refactor — existing `test_admin_routes` overview assertions stay green (Class A golden proof).
- `GET /api/district/analytics`: non-district session → 401; district session → `{overview, teachers}` with correct rollup (mocked `list_all_users` + Supabase); no-Supabase / no-users → zeros + `[]`.
- Frontend: District Analytics section renders stat cards + grade bars + teacher list (vitest, mocked api).
- Gates: full `pytest -q --ignore=tests/load`; **Clever non-regression** (`test_clever_compliance` + `test_clever_callback` — untouched); cross-cutting grep; ruff; bandit; `cd frontend && npx vitest run` + `npm run build`; opus code-quality review (Class B endpoint).

## 8. References

- Origin: #606. Related follow-ups: #608 (per-user district admin), #609 (Clever hook).
- School analytics reference: `backend/routes/admin_routes.py::admin_overview` + `_enrich_*`; `frontend/src/tabs/AdminTab.jsx` ("School-Wide Analytics" panel).
- District console: `frontend/src/components/DistrictSetup.jsx` (`ConfigForm`); `backend/routes/district_routes.py` (`_require_district_admin`).
- Teacher set source: `backend/utils/supabase_users.py::list_all_users`.
