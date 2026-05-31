# Graider-Managed SSO Admin Designation — Design

**Date:** 2026-05-31
**Class:** B (auth / identity / privilege grant)
**Status:** Approved (brainstorming) → revised v2 after three-way design review (Claude/Codex/Gemini) → ready for implementation plan

> **v2 revision note.** Codex + Gemini both flagged one **blocker** — a school→district
> tier change left a stale `source="sso_designated"` school grant (privilege-state bug).
> Fixed in §3.3 (district branch now revokes first). Codex added two Important items:
> email-trust wording (§5) and tenant-scoping of the email key (§3.1, single-district
> invariant documented). Gemini added an immediate-revoke-on-DELETE enhancement (§3.1).
> All incorporated below.
**Supersedes:** the role-claim approach in `2026-05-30-classlink-admin-routing-design.md` (Project A), whose premise — that the ClassLink SSO `Role` claim distinguishes admins — was **disproved** for tenant 2284 (two distinct admin accounts both return `Role='Teacher'`; the tenant exposes no administrator role). Project A branch `feature/classlink-admin-routing` is **abandoned, not merged.**

---

## 1. Problem

ClassLink SSO **admins** for tenant 2284 come through with `Role='Teacher'` — ClassLink provides **no admin signal** in the SSO claim or the roster for this tenant (confirmed: 2× SSO captures = `Teacher`; the OneRoster data-sharing "Define Roles" view is unconfigured/`N/A` across all roles, including teacher/student, so it carries no role-presence information). Routing admins by the SSO role claim therefore cannot work and is fragile in general (depends on each district's roster configuration).

We need admins (district + school tier) routed to their existing Graider views (`/district` console; in-app Admin tab) **without depending on ClassLink's role data.**

## 2. Goal

A **Graider-managed** admin model: the district admin (password-gated) maintains a list of admin **emails** with a tier; on SSO login Graider email-matches against that list and routes accordingly. No dependency on the SSO role claim or the roster.

**Compliance:** orthogonal to ClassLink/OneRoster certification (SSO, roster sync, FERPA delete unchanged) — admin designation is internal Graider authorization. Clever is **not touched** (the match helper is provider-agnostic; ClassLink-only wiring now).

**Non-goals:** Clever callback hook (deferred — one-line add later); per-user district admin identity (stays the existing shared `session["district_admin"]` flag, password-bootstrapped); admin routing for any tenant whose admins must be auto-detected from ClassLink role data.

## 3. Design

### 3.1 Designation list (district-managed)

Storage (mirrors `admin_invite:` / `admin_role:`, `system` scope), **email-keyed** because at designation time only the email is known (the Graider UUID is created on first SSO login):

```
sso_admin_designation:{normalized_email}  →  {
    "tier": "district" | "school",
    "school": "<name or ''>",     # required when tier == "school"
    "created_at": "<utc iso>",
    "created_by": "district_admin",
}
```

`normalized_email` = `email.strip().lower()`. The realized grant stays UUID-keyed in `admin_role:` (§3.3) — designation = intent (by email), `admin_role` = realized grant (by uuid).

**Single-district invariant (tenant scoping).** Graider is **one district per deployment** — there is a single `district:password_hash` and a single `district:sis_config` in `system` scope, so a deployment serves exactly one ClassLink tenant's admins. The email-keyed designation is therefore tenant-safe *for this deployment model*. This invariant is load-bearing and is documented here deliberately (Codex review): if Graider ever becomes multi-tenant, the key MUST become `sso_admin_designation:{tenant_id}:{normalized_email}` so a recycled email in tenant B cannot inherit tenant A's designation. Until then, email-keyed is correct.

New endpoints, all `@_require_district_admin` (in `backend/routes/district_routes.py`):
- `GET /api/district/sso-admins` → `{"admins": [{email, tier, school, created_at}, ...]}`
- `POST /api/district/sso-admins` body `{email, tier, school?}` → validates: `email` non-empty; `tier in ("district","school")`; `school` non-empty when `tier=="school"`. Upserts `sso_admin_designation:{normalized_email}`.
- `DELETE /api/district/sso-admins` body `{email}` → deletes `sso_admin_designation:{normalized_email}`, **then best-effort immediate revoke**: resolve the email to a linked Supabase UUID (`load_classlink_links()` reverse-lookup / `list_all_users` email match) and, if found, call `_sync_sso_admin_revocation(uuid)` so school-admin access is dropped *now* rather than only on the user's next login (Gemini review — closes the lazy-revocation window). Best-effort: if the email isn't yet linked to a UUID (never logged in), the designation delete alone suffices.

### 3.2 District console UI

New "SSO Admin Access" section in `frontend/src/components/DistrictSetup.jsx` (post-auth `ConfigForm`): an email input + tier selector (**District Admin** / **School Admin**) + school-name input (shown when School Admin), an "Add" action, a list of current designations, and per-row remove. Reuses the existing district-console styling + `_require_district_admin` session; new `api.js` wrappers for the three endpoints.

### 3.3 Match helper (provider-agnostic)

New neutral module `backend/routes/sso_admin.py`:

```python
def apply_sso_admin_designation(email, teacher_id, session) -> str:
    """Apply the district-managed SSO admin designation for a freshly-resolved
    SSO login. Returns the applied tier: 'district' | 'school' | 'none'.

    Side effects:
      - district → set session['district_admin'] = True
      - school   → upsert a source='sso_designated' admin_role grant (school from the designation)
      - none     → revoke any stale source='sso_designated' grant (demotion self-heal)

    Never raises into the callback. Never grants without a designation match.
    """
```

- Looks up `sso_admin_designation:{normalize(email)}`.
- `tier == "district"` → `_sync_sso_admin_revocation(teacher_id)` **first** (clears any stale `source="sso_designated"` school grant from a prior school→district promotion — **the v2 blocker fix**), then `session["district_admin"] = True`; return `"district"`.
- `tier == "school"` → `_grant_sso_school_admin(teacher_id, rec.get("school", ""))`; return `"school"`.
- no record → `_sync_sso_admin_revocation(teacher_id)`; return `"none"`.

The revoke-before-district-grant means a tier change never leaves a stale lower-tier grant. `_sync_sso_admin_revocation` only touches `source="sso_designated"` rows, so a district admin who *also* holds an invite-claimed school grant keeps it (invite grants are never auto-revoked).

**Reused from Project A** (`backend/routes/admin_routes.py`, re-authored on this branch):
- `_grant_sso_school_admin(teacher_id, school)` — idempotent upsert of `admin_role:{teacher_id}` tagged `source="sso_designated"`; **never overwrites an invite-claimed grant** (no `source` key).
- `_sync_sso_admin_revocation(teacher_id)` — deletes only `source="sso_designated"` grants; invite-claimed grants never auto-revoked.

(The `source` value is `"sso_designated"` — provider-agnostic, since grants are no longer role/provider-specific.)

### 3.4 ClassLink callback wiring

After the existing identity resolution (`resolve_classlink_user_id`, with the `account_conflict` fail-closed guard) and `session['classlink_user']` build, replace the (Project-A) role branch with:

```python
applied = apply_sso_admin_designation(email, graider_uuid, session)

if applied == "district":
    audit_log("CLASSLINK_DISTRICT_ADMIN_LOGIN",
              f"ClassLink district admin SSO login: {redact_email(email)}",
              user="district_admin", teacher_id=graider_uuid)
    return redirect("/district")          # console auto-detects the active session

_trigger_roster_sync(graider_uuid, tenant_id)

audit_log(
    "CLASSLINK_SCHOOL_ADMIN_LOGIN" if applied == "school" else "CLASSLINK_LOGIN",
    (f"ClassLink school admin SSO login {redact_email(email)}" if applied == "school"
     else f"ClassLink SSO login: {redact_email(email)}"),
    user=("admin" if applied == "school" else "teacher"), teacher_id=graider_uuid)

return redirect("/?classlink_login=success")
```

The `account_conflict` guard runs *before* this, so no admin status is granted without a resolved Supabase UUID. District admins redirect to `/district` before roster sync (consistent; they manage config, not rosters). `session["district_admin"]=True` works with the existing `_require_district_admin` gate and the `/district` page's auth-state auto-detection (no frontend change for landing).

### 3.5 Dropped from Project A
- `backend/routes/classlink_roles.py` (role classifier) — not created on this branch.
- `_resolve_classlink_school` (roster school derivation) — **not needed**; school comes from the designation. Removes the fragile two-call OneRoster lookup from the login path.
- The #605 `DEBUG_CLASSLINK_ROLE_PROBE` (live on `main`) — **reverted** on this branch.

## 4. Data flow

```
District admin (password) → /district → adds {email, tier, school} → sso_admin_designation:{email}
                                                                          │
ClassLink SSO login ──────────────────────────────────────────────────── │
  resolve_classlink_user_id → graider_uuid (account_conflict if None)     │
  session['classlink_user'] = {... user_id: graider_uuid}                 │
  apply_sso_admin_designation(email, uuid, session) ──── looks up ────────┘
     ├─ district → session['district_admin']=True → redirect /district
     ├─ school   → _grant_sso_school_admin(uuid, school) → land in app (Admin tab)
     └─ none     → _sync_sso_admin_revocation(uuid) → land in app (teacher)
```

## 5. Error handling / security

- **Root of trust = district password.** Only a password-authed district admin edits the designation list; SSO admin status flows solely from it.
- **Email is IdP-trusted** (Codex review — precise wording): the matched email is `id_claims.get('email') or user_data.get('Email')` (`classlink_routes.py:537`). The id_token is signature/aud/iss-validated (`:436`) and the userinfo `sub` is cross-checked against the id_token `sub` (`:526`) before either is consumed — so the email, whether from the id_token or the bound userinfo, is IdP-attested and cannot be spoofed to impersonate another user. (We do not currently require an `email_verified` claim; ClassLink does not supply one, and the sub-binding makes the userinfo email trustworthy.)
- **Fail-closed:** resolver `None` → `account_conflict` *before* the hook → no grant. Missing/blank email → no match → teacher.
- **Removal self-heals + immediate revoke:** `DELETE` does a best-effort immediate `_sync_sso_admin_revocation` (§3.1); the next-login no-match path is the backstop. District flag is per-session.
- **Tier changes never strand a grant:** the district branch revokes any stale `source="sso_designated"` grant before setting the flag (§3.3 — the v2 blocker fix).
- **Never clobbers invite-claimed admins:** the `source="sso_designated"` guard in both helpers.
- **Endpoint validation:** tier whitelist; school required for school tier; email normalized identically at write and match.
- **Tenant scoping:** safe under the single-district invariant (§3.1); documented so multi-tenant deployment would key by `{tenant_id}:{email}`.

## 6. Files touched

- `backend/routes/sso_admin.py` — NEW: `apply_sso_admin_designation`.
- `backend/routes/admin_routes.py` — re-author `_grant_sso_school_admin` / `_sync_sso_admin_revocation` (source=`sso_designated`).
- `backend/routes/district_routes.py` — NEW endpoints: list/add/delete `sso-admins`.
- `backend/routes/classlink_routes.py` — callback wiring (call helper + tier branch); revert #605 probe.
- `frontend/src/components/DistrictSetup.jsx` — "SSO Admin Access" section (the new designation list is the primary management surface, showing email + tier per entry).
- `frontend/src/services/api.js` — three endpoint wrappers.
- *(Optional, Gemini review — deferred):* enrich the existing `GET /api/district/admins` (realized-grant list, currently UUID-only) to also return each grant's `source`, so a district admin can distinguish SSO-designated from invite-claimed admins in the console. Out of scope for the core feature; track as a small follow-up.
- Tests: `tests/test_sso_admin_designation.py` (helper + grant/revoke), `tests/test_district_sso_admins.py` (endpoints), `tests/test_classlink_sso.py` (callback tiers), frontend vitest for the console section.

## 7. Testing (TDD; Class B ⇒ opus review)

- Designation endpoints: auth-gated CRUD; validation (tier whitelist, school-required-for-school, email normalization); list/add/delete round-trip.
- `_grant_sso_school_admin` / `_sync_sso_admin_revocation`: source-tagged grant; never overwrite/revoke an invite-claimed grant; demotion revoke.
- `apply_sso_admin_designation`: district → flag + return; school → grant + return; none → revoke + return; missing email/record → none.
- **Tier-transition (v2 blocker):** a `school`→`district` designation change → next district login **revokes the stale `source="sso_designated"` school grant** AND sets the flag.
- **Email-change-in-IdP:** a previously-school-granted user logging in with a *new* email that has no designation → school grant revoked on that login (no-match path).
- **Userinfo-email fallback:** match works when email comes from `user_data['Email']` (id_token email absent), per the §5 trust note.
- **Single-tenant invariant:** a designation is matched by email for this deployment's tenant; covered by documenting the single-district assumption (no cross-tenant test needed under that invariant).
- `DELETE` immediate-revoke: deleting a designation for an *already-linked* email immediately removes the `admin_role` grant (best-effort).
- Callback: designated district → `/district` + `session["district_admin"]`; designated school → grant + `classlink_login=success`; non-designated → teacher + revoke; `account_conflict` (resolver None) → no grant, no flag.
- Frontend: district console SSO-admin add/list/remove (vitest).
- **Clever untouched** → `test_clever_compliance.py` + `test_clever_callback.py` stay green (no changes expected).
- Gates: full `pytest -q --ignore=tests/load`; cross-cutting grep; SIS line-pin scan (callback + probe-revert line shifts); `cd frontend && npx vitest run` + `npm run build`; ruff; bandit; opus code-quality review.

## 8. References

- Superseded design: `docs/superpowers/specs/2026-05-30-classlink-admin-routing-design.md`.
- Disproving evidence: 2× `DEBUG_CLASSLINK_ROLE_PROBE` captures (`userinfo_Role='Teacher'`, tenant 2284); Partner Portal "Define Roles" all-`N/A`.
- Reused grant/revoke pattern origin: Project A `_grant_sso_school_admin` / `_sync_sso_admin_revocation`.
- Existing admin system: `backend/routes/admin_routes.py`, `backend/routes/district_routes.py`, `frontend/src/components/DistrictSetup.jsx`, `frontend/src/tabs/AdminTab.jsx`.
- #604 (teacher UUID identity) — the `resolve_classlink_user_id` + `account_conflict` machinery this builds on. Probe #605 — reverted here.
