# District Admin Analytics View — Design

**Date:** 2026-06-01
**Class:** B (new auth-gated endpoint) + A (behavior-preserving refactor of the school overview)
**Status:** Approved (brainstorming) → **v3** after two three-way review rounds (Claude/Codex/Gemini) → ready for plan
**Closes:** #606

> **v3 note (round-2 re-review).** Gemini passed v2; Codex cleared B2 but flagged B1 as
> under-specified and B3 as still a scale risk. Resolved: **B1** — §3.1/§3.3 now explicitly
> preserve *both* school audit branches (no-data + scored) and filter internal fields
> (`scored_count`, `hit_hard_cap`) out of both JSON responses; golden test covers both
> branches (§7). **B3** — decision: v1 ships the **cached score-pull + `approximate` flag**
> (YAGNI-correct for current district sizes); the DB-side aggregate RPC (which eliminates the
> cold-request score pull entirely) is filed as the scale-up follow-up **#611**. Cache
> single-tenant assumption called out (§3.5).

> **v2 revision note.** Codex + Gemini both flagged two **blockers** in v1: (1) extracting
> `compute_overview` would break the school dashboard's `total_teachers` (which counts
> SIS/manual teachers with blank `user_id`), and (2) "all Supabase auth users = all
> teachers" is unsound — it over-counts non-teacher accounts (admins/staff → PII leak) and
> under-counts Clever teachers who own data under `clever:{id}` (no Supabase UUID). Both
> also flagged real district-scale **perf/timeout** risk (the existing aggregation pulls all
> rows into Python; `_chunked_in_rows` silently caps at `_HARD_CAP=100_000`). All addressed
> below. Per-school deferral was confirmed sound (roster sync drops school/org attribution —
> `roster_sync.py:87-94`).

---

## 1. Problem

The school-admin Admin tab (`AdminTab.jsx`) has a "School-Wide Analytics" rollup (totals, average score, A–F grade distribution, per-teacher breakdown) via `/api/admin/overview`; the **district** console (`/district`) is config-only with **no analytics**. The top admin tier sees less than the school tier.

## 2. Goal

A **district-wide rollup** of the same metrics, across the whole deployment: total teachers (with activity), total students, total assessments, average score, A–F grade distribution, and a per-teacher list. Reuse the school aggregation core where it's behavior-safe.

**Non-goals (v1):** per-school breakdown (school-per-teacher attribution is not stored — confirmed); time-series/trends; per-user district admin (#608).

## 3. Design

### 3.1 Shared aggregation core (`compute_overview`) — **metrics only, no `total_teachers`**

Extract the row-aggregation from `admin_overview` into:

```python
def compute_overview(teacher_ids):
    """Aggregate metrics across the given teacher ids. Returns:
      {total_students, total_assessments, average_score,
       grade_distribution: {A..F}, scored_count}
    NOTE: deliberately does NOT return total_teachers — the caller owns that
    (the school path counts discovered teachers incl. blank-user_id SIS/manual
    teachers; the district path counts data-owning teacher_ids). Preserves the
    existing chunked .in_() logic (incl. _HARD_CAP) verbatim. [] → zeros.
    """
```

`admin_overview` becomes (output **byte-identical** — Class A):
```python
teachers = _discover_teachers(g.admin_role)
teacher_ids = [t["user_id"] for t in teachers if t.get("user_id")]
# Preserve the EXISTING no-data early-audit branch (admin_routes.py:574) exactly:
sb = _get_supabase()
if not sb or not teacher_ids:
    audit_log("ADMIN_VIEW_OVERVIEW", "Viewed overview (no data)", user="admin", teacher_id=g.teacher_id)
    return jsonify({"total_teachers": len(teachers), "total_students": 0, "total_assessments": 0,
                    "average_score": None, "grade_distribution": {"A":0,"B":0,"C":0,"D":0,"F":0}})
metrics = compute_overview(teacher_ids)
audit_log("ADMIN_VIEW_OVERVIEW", f"... {metrics['scored_count']} scores", ...)   # scored branch (admin_routes.py:669) preserved
# Build the response with the EXACT existing public keys only — never spread internal
# fields (scored_count, hit_hard_cap) into the JSON:
return jsonify({"total_teachers": len(teachers),
                "total_students": metrics["total_students"],
                "total_assessments": metrics["total_assessments"],
                "average_score": metrics["average_score"],
                "grade_distribution": metrics["grade_distribution"]})
```
**B1 invariants (Codex):** (a) both audit branches — the no-data early line *and* the scored line — are preserved verbatim; (b) `total_teachers = len(teachers)` (incl. blank-`user_id` SIS/manual teachers) stays in `admin_overview`; (c) internal fields (`scored_count`, `hit_hard_cap`) are **never** included in the school JSON — the response uses explicit public keys, not `**metrics`. The golden test (§7) pins both branches + the response shape. Note: `compute_overview`'s totals use `count='exact'` (§3.5), which is byte-identical to the old row-pull for any school below `_HARD_CAP` (i.e. every realistic school) and merely more accurate for a pathological >100k-row school — a latent-bug fix, not a regression.

### 3.2 District teacher set — **data-owners, not auth users** (Blocker 2 fix)

The district teacher set = **distinct `teacher_id`s that own data**, unioned across the teacher-scoped tables:
```python
def _district_teacher_ids(sb) -> set[str]:
    """Distinct teacher_id across classes + published_content + published_assessments.
    Provider-agnostic: includes UUID teachers AND clever:{id}/legacy teachers who
    own data; excludes admin/staff-only accounts that never taught (no PII leak,
    no over-count). Chunked/paginated select of the teacher_id column only."""
```
This is the set we aggregate over, so it's both correct and the natural scope. `total_teachers` (district) = `len(_district_teacher_ids)` = "teachers with activity."

**Names for the teacher list:** build a best-effort `id → {email, name}` map from `list_all_users(sb)` (used *only* to annotate, not as the set). `clever:{id}`/unmapped ids show no name (`"—"`). Emails shown are teacher emails to an authorized district admin — same as the school AdminTab.

### 3.3 District analytics endpoint (cached)

```python
@district_bp.route("/api/district/analytics", methods=["GET"])
@_require_district_admin
@handle_route_errors
def district_analytics():
    return jsonify(_district_analytics_cached())   # short-TTL cache, see §3.5
```
The cached builder:
```python
sb = _get_supabase()
ids = sorted(_district_teacher_ids(sb)) if sb else []
metrics = compute_overview(ids)                    # imported from admin_routes
teachers = _district_teacher_rows(ids, sb)         # per-teacher counts + best-effort name
audit_log("DISTRICT_VIEW_ANALYTICS", f"teachers={len(ids)}", user="district_admin", teacher_id="system")
return {
    "overview": {  # explicit public keys only — do NOT spread **metrics (Codex: keeps scored_count/hit_hard_cap internal)
        "total_teachers": len(ids),
        "total_students": metrics["total_students"],
        "total_assessments": metrics["total_assessments"],
        "average_score": metrics["average_score"],
        "grade_distribution": metrics["grade_distribution"],
    },
    "teachers": teachers,
    "approximate": metrics.get("hit_hard_cap", False),   # the only internal flag promoted (intentional UX signal)
}
```
`_district_teacher_rows` reuses the existing `_enrich_*` counters (chunked) over the data-owner ids. Gated by `@_require_district_admin` only (NOT `@require_admin`).

### 3.4 Frontend — "District Analytics" section (district-console style)

New section in the authenticated `ConfigForm` of `DistrictSetup.jsx`, **built in the district console's own style** (`React.createElement` + its `styles` objects — it does NOT use AdminTab's `glass-card` CSS classes, so the presentation is rebuilt, not imported). On mount → `api.getDistrictAnalytics()`. Renders: stat cards (Teachers/Students/Assessments/Average Score), A–F grade-distribution bars, and a scrollable teacher list (name/email + counts). Shows an "approximate" note when `approximate` is true. New `api.js` wrapper `getDistrictAnalytics()`.

### 3.5 Performance (Important — both reviewers)

- **Short-TTL cache** (module-level, ~5 min): the expensive scan/aggregation runs at most once per window regardless of refreshes/multiple admins. **Single-tenant assumption (Codex):** the cache is keyed on nothing because a deployment serves one district and the response is identical for every district admin — safe under the single-`district:password_hash` model (same invariant as the SSO-designation feature). If Graider ever goes multi-tenant, the cache must be keyed by tenant. Invalidated by TTL only (v1 — no event invalidation).
- **Cheap counts where possible:** `total_students`/`total_assessments` via Supabase `count='exact'` head requests rather than pulling rows; only `average_score`/`grade_distribution` pull the score column.
- **`_HARD_CAP` disclosure (contract change):** `_chunked_in_rows` currently returns rows without metadata, so `compute_overview` detects a cap hit by checking whether any chunk returned **exactly** `_HARD_CAP=100_000` rows, and returns `hit_hard_cap: bool`. (If that heuristic is fragile, add a thin parallel helper that returns `(rows, capped)` — do NOT change the existing `_chunked_in_rows` signature, to avoid disturbing the school path.) The response promotes this as `approximate: true` and the UI shows "approximate above 100k rows" — **no silent undercount**.
- **B3 decision (cached score-pull now; RPC later — #611):** the cache *amortizes* the cost, but the first request after each TTL expiry still pulls all score rows into Python. For current district sizes (sub-second on tens-of-thousands of score numbers, then cached) this is acceptable for v1. The cold-request pull is **eliminated** by the DB-side aggregate RPC tracked in **#611** — the bulletproof scale-up when a district gets large. v1 PR must document the teacher/row scale it was actually tested at (no silent scale assumptions).

## 4. Data flow

```
District admin → /district → "District Analytics" → GET /api/district/analytics (@_require_district_admin)
  └─ _district_analytics_cached()  (≤ once / 5 min)
       ├─ ids = _district_teacher_ids(sb)        # distinct teacher_id across data tables (data-owners)
       ├─ metrics = compute_overview(ids)         # shared core, chunked, _HARD_CAP-aware
       ├─ teachers = _district_teacher_rows(ids)  # per-teacher counts + best-effort name (list_all_users map)
       └─ {overview:{total_teachers:len(ids), **metrics}, teachers, approximate}
```

## 5. Error handling / security

- **Auth:** `@_require_district_admin` only. School admins / teachers / anonymous cannot reach it.
- **No PII over-exposure:** the data-owner set excludes admin/staff-only accounts, so the teacher list won't surface non-teacher staff emails. Teacher emails to the district admin are authorized (parity with AdminTab).
- **No Supabase / no data:** zeros + empty teacher list, no crash.
- **No silent caps:** `approximate` flag (vs the `_HARD_CAP`); PR documents tested scale.
- **Audit:** `DISTRICT_VIEW_ANALYTICS` records only a teacher count.

## 6. Files touched

- `backend/routes/admin_routes.py` — extract `compute_overview` (metrics-only, `_HARD_CAP`-aware) + the minimal shared `_enrich_*` piece; `admin_overview` keeps `total_teachers`/audit score-count.
- `backend/routes/district_routes.py` — `_district_teacher_ids`, `_district_teacher_rows`, `_district_analytics_cached`, `district_analytics` endpoint.
- `frontend/src/components/DistrictSetup.jsx` — "District Analytics" section (district style).
- `frontend/src/services/api.js` — `getDistrictAnalytics()` wrapper (+ default-export entry).
- Tests: `tests/test_admin_routes.py` (compute_overview unit + **school-overview-unchanged golden, incl. blank-user_id `total_teachers`**), `tests/test_district_analytics.py` (endpoint auth + data-owner set + clever:{id} inclusion + cache + approximate flag + empty), frontend vitest.

## 7. Testing (TDD; mixed A/B ⇒ opus review)

- **School overview byte-identical (B1):** golden tests covering **both** audit branches — (1) the **no-data** branch (no Supabase / no teacher_ids → "Viewed overview (no data)" audit + zeros payload) and (2) the **scored** branch (audit carries the score-count). Plus: `_discover_teachers` returns a teacher with **blank `user_id`** → `total_teachers` still counts it; and the response JSON has **exactly** the 5 public keys (no `scored_count`/`hit_hard_cap` leaked).
- `compute_overview(teacher_ids)`: totals/avg/A–F with mocked Supabase; `[]` → zeros; a chunk returning exactly `_HARD_CAP` rows → `hit_hard_cap: True` (and the endpoint's `approximate: true`).
- **District teacher set (Blocker 2):** `_district_teacher_ids` unions distinct `teacher_id` across the 3 tables; **includes a `clever:{id}` owner**; **excludes** an admin-only auth user with no data; mocked.
- `GET /api/district/analytics`: non-district → 401; district → `{overview, teachers, approximate}` with correct rollup; no-Supabase → zeros; **cache** returns the same object within TTL without re-querying (assert query count).
- Frontend: section renders stat cards + grade bars + teacher list + the approximate note (vitest, mocked api).
- Gates: full `pytest -q --ignore=tests/load`; **Clever non-regression** (`test_clever_compliance` + `test_clever_callback`, untouched); cross-cutting grep; ruff; bandit; `npx vitest run` + `npm run build`; opus review.

## 8. References

- Origin #606; related #608, #609. School analytics: `admin_routes.py::admin_overview`/`_enrich_*`, `AdminTab.jsx`. District console: `DistrictSetup.jsx`, `district_routes.py::_require_district_admin`. Per-school blocker evidence: `roster_sync.py:87-94`, `student_account_routes.py:207-214`. Chunking/`_HARD_CAP`: `admin_routes.py:380-397`.
