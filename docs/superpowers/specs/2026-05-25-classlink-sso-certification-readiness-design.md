# ClassLink SSO Certification-Readiness — Design Spec

**Date:** 2026-05-25
**Status:** Approved (brainstorm complete) — ready for implementation plan
**Author:** Claude (3-AI consult: Codex 5.5-high decisional + Gemini advisory)
**Scope phase:** SSO now; Roster Server a fast-follow (separate spec)

---

## 1. Goal

Make Graider's **ClassLink OAuth2/OIDC SSO connection certification-ready** for ClassLink's
official partner certification, by fixing the identity model to ClassLink's recommended
**TenantId + SourcedId** globally-unique identifier (GUID), fail-closed, eliminating the
cross-tenant identity collision that exists today.

This unblocks a *certification-grade* LaunchPad test (board step "Test SSO app on the ClassLink
LaunchPad") and the subsequent "Request Certification" call, on which ClassLink probes the
multi-school / multi-class edge case.

## 2. Background & the defect

ClassLink's `SourcedId` is unique **only within a tenant** (school system), not globally — which
is exactly why ClassLink's partner docs recommend `TenantId + SourcedId` as the GUID. Our Clever
integration uses a flat `clever:{id}` because Clever IDs *are* globally unique; **that assumption
does not hold for ClassLink.**

Today (`backend/auth.py:208-215`, `backend/routes/classlink_routes.py:111-122`):

- Teacher identity = `classlink:{sub}` with **no tenant component**.
- `tenant_id` is captured into `g.district_id` (`auth.py:215`) but never used for identity.
- `_link_classlink_account` (`classlink_routes.py:57`) **auto-links by email across all teachers**,
  with no tenant scoping — ClassLink lists email as the *last-resort* identifier.

**Consequence:** two teachers in different districts sharing a SourcedId collide into one Graider
account → cross-tenant data bleed (a FERPA defect), and the multi-school cert probe fails.

### ClassLink requirements (verbatim, partner portal — "Next Steps for Integrating With ClassLink")

> 💡 "...we recommend using the **TenantID** (an identifier unique to the school system) and user
> **SourcedId** (an identifier unique to each person...) as the primary authentication fields, as
> these fields create the best globally unique identifier (GUID)... Secondarily, use LoginId +
> TenantId, or use Email."

> "Applications are designed to be generic... ClassLink does **not** support custom login pages."

> "...you may notice you're redirected to the generic ClassLink sign-in page. This is the expected
> behavior..." (LaunchPad-initiated launches must work)

Certification is a live ~1-hour call with no published pass/fail checklist; the team probes
"if users can be in multiple classes or multiple schools." Any change to the SSO connection
(redirect URI, scopes, initiation type, domains) requires **re-certification**.

## 3. Decisions (from brainstorming)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Scope: SSO now, roster fast-follow** | Unblocks the cert call on the already-wired connection; rostering carries the FERPA weight and gets its own spec. |
| D2 | **Clean break — no migration code** | No live ClassLink users exist (pre-launch), so identity can change freely. |
| D3 | **No auto-linking** | ClassLink identity is always its own standalone account, keyed by TenantId+SourcedId. Eliminates cross-tenant email-match risk entirely. |
| D4 | **Approach 1: composite string GUID** | `classlink:{tenant}:{person}` mirrors the readable `clever:{id}` convention; all `startswith("classlink:")` guards keep working. (Rejected: opaque hash — not debuggable; mapping table — YAGNI given D2/D3.) |

## 4. 3-AI consult — reconciled amendments (conservative floor)

Both models unanimously confirmed the tenant-scoped GUID is correct and complete for the
collision. Reconciliation took Codex's stricter line where they split (lowest risk wins):

- **A1 — Fail closed; never fall back to `sub`.** Person component = userinfo `SourcedId` →
  `UserId` *only if* ClassLink confirms it is the user sourcedId → otherwise **reject** with a
  stable error. (Original draft's "fall back to `sub`" was the top flagged risk — `sub` creates an
  identity that cannot reconcile with roster data later.)
- **A2 — `_resolve_classlink_user_id` must fail closed.** Today it returns the unsafe non-scoped id
  on a missing link and swallows exceptions into the unsafe form.
- **A3 — Defensive GUID format.** URL-encode each component; parse with `split(":", 2)` after the
  `classlink:` prefix; reject empty tenant or person id.
- **A4 — OIDC correctness.** When userinfo returns a `sub`, verify it equals the id_token `sub`
  before trusting userinfo claims (OIDC Core requirement).
- **A5 — Role may be a list / comma-separated.** Normalize before the `== 'student'` check.
- **A6 — Frontend double-prefix fix (verified).** `App.jsx:340,347` rebuild
  `id: 'classlink:' + data.classlink_id`. With the composite GUID this would produce a *different*
  id than the backend uses, silently breaking auth. `/api/classlink/session` must return the
  canonical id and the frontend must use it verbatim. (`startsWith('classlink:')` checks in
  `OnboardingWizard.jsx:150` and `services/api.js:18` remain correct — only *construction* breaks.)

**#1 pre-cert blocker (unanimous, NOT a code task):** prove against the **live test account** that
the userinfo person field used equals OneRoster `sourcedId`. The tenant-scoped *shape* is correct;
the residual risk is picking the wrong person field. Confirm before booking the cert call.

## 5. Design

### 5.1 Identity format

```
classlink:{quote(tenant_id)}:{quote(person_id)}
```

- `tenant_id` — from userinfo `TenantId` (ClassLink-specific; not an id_token claim).
- `person_id` — userinfo `SourcedId` (preferred) → `UserId` (only if confirmed equivalent) → reject.
- Both components `urllib.parse.quote(..., safe='')`-encoded so a literal `:` can never break parsing.
- Parse (where needed): strip `classlink:` prefix, `split(":", 2)`, `unquote` each part.
- Empty tenant **or** empty person ⇒ invalid ⇒ reject (fail closed).

### 5.2 Components & changes

1. **`classlink_routes.py` — identity helpers**
   - New `_classlink_guid(tenant_id, person_id) -> str` (encode + assemble; raises/returns sentinel
     on empty component).
   - New `_extract_person_id(user_data) -> str | None` implementing the
     SourcedId → UserId → None precedence (A1).
   - **Delete `_link_classlink_account`** and its call site (D3).
   - With auto-linking gone there is no link lookup left, so `_resolve_classlink_user_id`
     collapses into the GUID builder: it no longer reads `classlink_links` — it returns the
     composite GUID directly (or is removed and callers read the GUID stored in session). Either
     way it must fail closed (A2): no unsafe non-scoped fallback, no exception-swallow.

2. **`classlink_routes.py` — `classlink_callback`**
   - After id_token validation + userinfo fetch:
     - Verify `userinfo.sub == id_token.sub` when userinfo carries a `sub` (A4).
     - Normalize `role` (handle list/comma-separated) before the student/teacher branch (A5).
     - Compute `tenant_id`; reject (fail-closed redirect) if missing/empty.
     - Compute `person_id` via `_extract_person_id`; reject if `None`.
     - Build the composite GUID; store identity in session for **both** the student and teacher
       paths (student path currently sets only raw fields — must get the same GUID).

3. **`auth.py:208-215`** — build `g.user_id` / `g.teacher_id` from the composite GUID (tenant +
   person from `session['classlink_user']`), not `classlink:{sub}`. Keep `g.district_id = tenant_id`.

4. **`classlink_routes.py` — `classlink_session` (`:434`)** — return the canonical `user_id`
   (composite GUID) so the frontend can use it verbatim (A6).

5. **Frontend `App.jsx:340,347`** — consume the canonical id from `/api/classlink/session` directly;
   remove the `'classlink:' + data.classlink_id` reconstruction.

### 5.3 Data flow

LaunchPad or self-initiated login → `/api/classlink/callback` validates id_token (sig/iss/aud/exp/
iat/nonce, already implemented) → fetch userinfo → verify sub-match → extract `tenant_id` +
`person_id` → `_classlink_guid` → store in session → `auth.py` resolves the **same** GUID on every
request. Identity is formed **once** at the callback and used everywhere.

### 5.4 Error handling (all fail-closed, stable codes, never 500, never unsafe identity)

| Condition | Result |
|-----------|--------|
| `tenant_id` missing/empty | redirect `/?classlink_error=missing_tenant` |
| person id missing (no SourcedId/UserId) | redirect `/?classlink_error=missing_identity` |
| `userinfo.sub` ≠ `id_token.sub` | redirect `/?classlink_error=identity_mismatch` |
| unknown/empty role | treat as teacher default (existing behavior) — documented, not an error |
| userinfo fetch failure | existing `userinfo_failed` / `userinfo_error` paths (unchanged) |

### 5.5 Testing

- **Unit — `_classlink_guid`**: encoding round-trip; empty-component rejection; `:` in a component
  cannot corrupt parse.
- **Cross-tenant collision (the core regression)**: same `SourcedId`, two different `TenantId` →
  two distinct `teacher_id` values. (Existing fixtures in `tests/test_classlink_sso.py` already use
  `TenantId` values — extend them.)
- **Fail-closed**: missing SourcedId → `missing_identity`; missing tenant → `missing_tenant`;
  userinfo sub mismatch → `identity_mismatch`.
- **Student-path parity**: student session gets the composite GUID too.
- **Role normalization**: list / comma-separated role resolves correctly.
- **Regression**: keep `tests/test_classlink_sso.py` + `tests/test_classlink_sso_contract.py` +
  `tests/test_classlink_routes_gaps.py` green (some identity pins will shift — expected and
  intentional; update them to the composite GUID).
- **Frontend**: session id is used verbatim (no double-prefix).

## 6. Out of scope (Roster Server fast-follow — separate spec)

OneRoster 1.1 conformance; "SSO users land in their provisioned (rostered) accounts" against Tenant
2284 sample data; `/api/classlink/delete-data` (FERPA right-to-delete); accommodations apply;
periodic-sync inclusion (`sync_routes.py` provider list currently `('clever','oneroster')`).
These carry the bulk of the FERPA/compliance weight and will be specced after SSO certifies.

## 7. Non-code action items (owner: user — required before cert call)

1. **Confirm the live userinfo person field == OneRoster `sourcedId`** against the test account
   (the #1 pre-cert blocker). If only `UserId` is returned, confirm with ClassLink whether it is
   the user sourcedId before using it.
2. **Set `CLASSLINK_CLIENT_ID` / `CLASSLINK_CLIENT_SECRET` / `CLASSLINK_REDIRECT_URI`** in the
   production (Railway) env and, for local testing, in `.env` (currently absent locally — the flow
   cannot be exercised locally until then).
3. Complete the **Certified Partner MOU** (data-use agreement) — its data-handling clauses should
   be cross-checked against the roster fast-follow's deletion/audit scope.
4. After implementation, **re-test on LaunchPad**, then click **Request Certification**.

## 8. Open questions / confirm-live

- Exact userinfo field name for SourcedId (`SourcedId` vs `sourcedId`) and presence of `sub` in
  the `nodeapi.classlink.com/v2/my/info` response — gated doc; confirm against test account.
- Whether `Role` is ever returned as a list (drives the A5 normalization shape).

## 9. References

- ClassLink partner portal: "Next Steps for Integrating With ClassLink", "Request App Certification".
- Code: `backend/routes/classlink_routes.py`, `backend/auth.py:199-215`,
  `frontend/src/App.jsx:335-347`, `tests/test_classlink_sso*.py`, `tests/test_classlink_routes_gaps.py`.
- Identity precedent (Clever): `backend/auth.py:59-62` (`resolve_clever_user_id`), Clever Task C
  (`docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md:173-205`).
- 3-AI consult prompt: `/tmp/classlink_consult.md` (this session).
