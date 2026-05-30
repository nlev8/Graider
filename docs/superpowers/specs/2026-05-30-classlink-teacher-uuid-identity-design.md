# ClassLink Teacher UUID Identity Resolution — Design

**Date:** 2026-05-30
**Class:** B (auth / identity — net-new behavior)
**Status:** Approved (brainstorming) → revised v2 after three-way design review (Claude/Codex/Gemini) → ready for implementation plan

> **v2 revision note.** Codex's design review surfaced three blocking issues the
> first pass missed: (1) the frontend Bearer-header suppression keys off an `id`
> prefix that becomes a UUID after this change (stale-Bearer bypass risk),
> (2) email-matched *pending* users stay frontend-blocked, (3)
> `/api/classlink/delete-data` gates on a `classlink:` prefix that no longer
> matches. Gemini added the `storage.py` file-backend prefix handler. All are
> incorporated below (§3.4–§3.7) and were verified against the live code.

---

## 1. Problem

The first ClassLink SSO **teacher** login on tenant 2284 (test user `T4957-0005`)
produced two production Sentry errors (both first seen 2026-05-30 09:40:19, release
`ea8e267`):

1. **APIError** — `invalid input syntax for type uuid: "classlink:2284:4957_T4957-0005"`
   raised in `_resilient_execute` (`backend/supabase_resilient.py`).
2. **AttributeError** — `'NoneType' object has no attribute 'get'`
   raised in `_run_classlink_roster_sync` (`backend/routes/classlink_routes.py`).

Prior testing on this tenant used a **student** (`S4957-0002`), which does not exercise
the teacher roster-sync / dashboard path, so this is a brand-new code path failing on
first exercise.

### Root cause — two distinct bugs

**Bug A (the AttributeError).** `_run_classlink_roster_sync` (`classlink_routes.py:258-261`)
calls `config = get_oneroster_config(teacher_id)` then immediately `config.get('base_url')`.
`get_oneroster_config` (`backend/oneroster.py:420`) is documented to and does return
`None` when there is no per-teacher config, no district config, and incomplete env vars.
A ClassLink teacher with no stored OneRoster config triggers the exact `NoneType.get` crash.

**Bug B (the UUID APIError).** The ClassLink callback builds a tenant-scoped composite
GUID `classlink:{tenant}:{sourcedId}` via `_classlink_guid` (`classlink_routes.py:62-80`)
and uses it **directly** as the app `teacher_id`:
- session `user_id: guid` (`classlink_routes.py:615-622`)
- `_trigger_roster_sync(guid, ...)` (`:625`)
- auth middleware copies it verbatim into `g.user_id` / `g.teacher_id` (`backend/auth.py:207-216`)

That non-UUID string then reaches `teacher_id` columns typed **UUID NOT NULL**:
`classes` (`cloud_migration.sql:161`), `students` (`:139`), `published_content` (`:195`),
`submission_confirmations` (`:244`), `behavior_sessions` (`:264`), `behavior_events` (`:298`).
Postgres rejects the string. It also breaks non-table code that expects a real Supabase
Auth user: `get_user_by_id(g.user_id)` in the approval check (`auth_routes.py:122-124`)
and Stripe metadata (`stripe_routes.py:46`).

**Why Clever does not hit Bug B (usually):** `resolve_clever_user_id` (`backend/auth.py:59-62`)
returns a **linked** Supabase UUID when one exists, else falls back to `clever:{id}`.
Linked Clever teachers therefore use a real UUID. ClassLink has **no equivalent resolver** —
it uses the raw composite GUID. (An *unlinked* Clever teacher would hit the same bug; that
is a separate, out-of-scope issue — see §8.)

### Verification

Diagnosis independently confirmed by three analyses (Claude main + Codex + Gemini), all
agreeing on root cause, on rejecting the "ALTER columns to TEXT" option (breaks RLS
`auth.uid() = teacher_id` semantics), and on the resolve-to-real-Supabase-UUID approach.

---

## 2. Goal

Resolve every ClassLink SSO teacher to a **real Supabase Auth UUID** at login, so that
`g.user_id` / `g.teacher_id` is always a valid UUID. This fixes the UUID-column queries,
roster sync, approval-status, and Stripe paths in one place. Also harden `_run_classlink_roster_sync`
against a `None`/partial OneRoster config (Bug A).

Non-goal: changing Clever behavior; migrating any pre-existing GUID-keyed data; altering
the student SSO path.

---

## 3. Design

### 3.1 New resolver — `resolve_classlink_user_id(guid, email, name)` (`backend/auth.py`)

Mirrors `resolve_clever_user_id` + Clever's email-merge logic (`clever_routes.py:503-534`),
with create-if-missing:

0. **Missing email?** If `email` is empty/blank → log + return `None` (fail closed;
   create-or-merge must not proceed without a stable email — Codex review).
1. **Linked?** Read link table `classlink_link:{guid}` (system scope). If a
   `supabase_user_id` is stored, return it.
2. **Email match?** `list_all_users(sb)` (`backend/utils/supabase_users.py`), filter by
   case-insensitive exact email:
   - exactly 1 match → `save_classlink_link(guid, match.id)`, return `match.id`.
   - more than 1 match → log warning, return `None` (ambiguous; do not guess — caller fails closed).
3. **No match** → `sb.auth.admin.create_user({email, email_confirm: True,
   password: <secrets.token_urlsafe(32)>, user_metadata: {approved: True,
   first_name, last_name, auth_source: 'classlink'}})`. Save link. Return new `user.id`.
   **Concurrency recovery:** if `create_user` raises a duplicate/email-exists error
   (two concurrent first-logins both reached step 3), re-run `list_all_users`, require
   exactly one email match, `save_classlink_link`, and return that UUID. Only fall to
   `None` if the re-check is still ambiguous. (Re-check the link immediately before
   create as a cheap optimization.)

**Trust boundary (documented):** auto-creating a Supabase Auth user from the SSO email is
acceptable *because* ClassLink is the district identity provider and the callback already
verifies the id_token signature/audience/issuer (`classlink_routes.py:437-461`) and checks
userinfo `sub` consistency (`:525-530`). The email claim is therefore trusted.

`approved: True` is consistent with the existing "Clever/ClassLink users are
district-approved by definition" gate skip (`backend/auth.py:247-248`); without it,
`/api/auth/approval-status` (`auth_routes.py:101-130`) would return `approved: False`
and the frontend pending-screen would block a user the middleware already lets through.

Supporting helpers (mirror the Clever pair at `auth.py:19-56`):
- `load_classlink_links()` — `list_keys('classlink_link:', 'system')` → `{guid: uuid}`.
- `save_classlink_link(guid, supabase_user_id)` — `save('classlink_link:{guid}',
  {'supabase_user_id': ...}, 'system')`, with the same legacy-file fallback shape.

All Supabase calls wrapped defensively; on infra failure the resolver logs + captures to
Sentry and returns `None` so the caller fails closed rather than crashing.

### 3.2 Callback wiring (`classlink_routes.py`, teacher branch ~611-628)

```python
graider_uuid = resolve_classlink_user_id(guid, email, {'first': first_name, 'last': last_name})
if not graider_uuid:
    return redirect("/?classlink_error=account_conflict")

session['classlink_user'] = {
    'classlink_id': person_id,   # external identity (unchanged)
    'guid': guid,                # tenant-scoped GUID, retained for audit/debug
    'user_id': graider_uuid,     # NOW a real Supabase UUID → g.user_id / g.teacher_id
    'email': email,
    'name': {'first': first_name, 'last': last_name},
    'type': role or 'teacher',
    'tenant_id': tenant_id,
}

_trigger_roster_sync(graider_uuid, tenant_id)
audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {redact_email(email)}",
          user="teacher", teacher_id=graider_uuid)
```

`account_conflict` is a new `classlink_error` value; the frontend renders the existing
red error banner (no new UI machinery — reuses the `classlink_error` handler).

### 3.3 Bug A guard (`classlink_routes.py:259`)

```python
config = get_oneroster_config(teacher_id)
if not config or not config.get('base_url') or not config.get('client_id') or not config.get('client_secret'):
    logger.info("No usable OneRoster config for %s, skipping post-login roster sync", teacher_id)
    return
```

The added `client_id`/`client_secret` checks prevent constructing a broken
`OneRosterClient` from a partial district config (`oneroster.py:457-465` returns a dict
without validating those fields).

### 3.4 Frontend Bearer-header suppression (BLOCKER #1 — `frontend/src/services/api.js`)

`getAuthHeaders()` (`api.js:15-26`) currently skips the Supabase Bearer header only when
`window.__graiderUser.id` starts with `clever:` / `classlink:`. After this change a
ClassLink user's `id` is a **UUID**, so the prefix test fails, `supabase.auth.getSession()`
runs, and a *stale* browser Bearer token would be attached. Backend `auth.py:210` only
honors the ClassLink cookie `if ... not has_bearer`, so the stale Bearer would silently
**bypass the ClassLink identity** and resolve to the wrong (or rejected) user.

Fix: stop keying off the `id` prefix. Set an explicit
`window.__graiderUser.auth_source = 'classlink'` in the ClassLink session handler
(`App.jsx:339-347`) — and `'clever'` in the Clever handler, since linked-Clever users
already have this latent bug — and change `getAuthHeaders()` to:

```js
if (currentUser && (currentUser.auth_source === 'classlink' || currentUser.auth_source === 'clever'
      || (currentUser.id && (currentUser.id.startsWith('clever:') || currentUser.id.startsWith('classlink:'))))) {
  return {}   // SSO cookie path — never send a (possibly stale) Bearer
}
```

The prefix checks remain as a fallback for unlinked-Clever (`clever:{id}`) sessions.

### 3.5 Approval-status SSO short-circuit (BLOCKER #2 — `backend/routes/auth_routes.py`)

The 1-email-match branch links but does not touch metadata, so a matched *pending* Supabase
user is backend-allowed (cookie) yet frontend-blocked: `/api/auth/approval-status`
(`auth_routes.py:122-128`) reads `user_metadata.approved`. Fix at the source, consistent
with the middleware's existing "SSO = district-approved" rule (`auth.py:247-248`): in
`approval_status`, short-circuit before the `get_user_by_id` lookup —

```python
if getattr(g, 'auth_source', None) in ('clever', 'classlink'):
    return jsonify({"approved": True, "email": getattr(g, 'user_email', '')})
```

This covers both auto-created (`approved=True`) and email-matched-pending users in one
place. `approved=True` on the created user is retained for metadata correctness.

### 3.6 `/api/classlink/delete-data` gate (BLOCKER #3 — `classlink_routes.py:673-675`)

The handler rejects non-ClassLink callers via `g.teacher_id.startswith("classlink:")`.
After the fix `g.teacher_id` is a UUID → every fixed ClassLink teacher gets a spurious 403,
breaking FERPA right-to-delete. Fix the gate to use the auth source:

```python
if getattr(g, 'auth_source', None) != 'classlink':
    return jsonify({"error": "Not a ClassLink user"}), 403
```

`delete_roster_data(teacher_id)` and the `oneroster_config` clear then operate on the
**UUID-scoped** data, which is exactly where the rows now live — correct behavior.

### 3.7 Storage file-backend prefix handler (`backend/storage.py`)

`_key_to_filepath` has a `clever_link:` branch (`storage.py:143-145`) so the file backend
(local-dev / Supabase-disabled) can persist links. Add a parallel `classlink_link:` branch
writing under a `classlink_links/` dir, so `load/save_classlink_link` work without Supabase.

---

## 4. Data flow

```
ClassLink callback (role == teacher)
  └─ guid = _classlink_guid(tenant, sourcedId)            # "classlink:2284:4957_T4957-0005"
  └─ graider_uuid = resolve_classlink_user_id(guid, email, name)
        ├─ link hit        → stored UUID
        ├─ 1 email match   → link + that UUID
        ├─ >1 email match  → None  → callback redirects account_conflict
        └─ 0 match         → admin.create_user → new UUID (+ link, approved=True)
  └─ session['classlink_user']['user_id'] = graider_uuid
        ↓ (next request)
  auth.check_auth: g.user_id = g.teacher_id = graider_uuid  # valid UUID
        ↓
  classes / students / published_content / behavior_* queries  → OK (UUID column match)
  get_user_by_id / Stripe / approval-status                    → OK (real Supabase user)
  _trigger_roster_sync(graider_uuid, ...)                      → writes UUID into classes/students
```

---

## 5. Error handling

- Missing/blank email → `None` → `account_conflict` (no create without a stable email).
- Resolver Supabase failures → log + Sentry capture → return `None` → callback fails closed
  with `account_conflict` (no crash, no half-provisioned state).
- Ambiguous (>1) email match → `None` → `account_conflict` (never silently merge).
- `admin.create_user` duplicate/email-exists (concurrency) → re-run `list_all_users`;
  exactly-1 match → link + return UUID (deterministic recovery); still ambiguous → `None`.
- `admin.create_user` other failure → caught in resolver → `None` → `account_conflict`.
- Bug A: `None`/partial config → clean `return` (skip sync), no exception.

---

## 6. Testing (TDD; Class B ⇒ opus code-quality review)

`resolve_classlink_user_id` (mock Supabase admin + `list_all_users`):
- linked hit returns stored UUID, no create call.
- single email match → links + returns that UUID.
- multiple matches → returns `None`, no create, no link.
- **missing/blank email → returns `None`, no create, no list lookup.**
- no match → calls `admin.create_user` with `approved=True` + `auth_source='classlink'`, links, returns new UUID.
- **duplicate-create race → on email-exists, re-resolves via `list_all_users` to the now-existing UUID + links.**
- Supabase failure → returns `None`.

Callback:
- success stores UUID (not GUID) in `session['classlink_user']['user_id']` and passes UUID to `_trigger_roster_sync`.
- `None` resolver → `account_conflict` redirect.

Approval-status (§3.5):
- ClassLink/Clever `g.auth_source` → `approved: True` without calling `get_user_by_id`.

delete-data (§3.6):
- ClassLink-session (UUID `g.teacher_id`, `auth_source='classlink'`) → deletes UUID-scoped data (no 403); non-ClassLink → 403.

Frontend (§3.4):
- `getAuthHeaders()` returns `{}` (no Bearer) when `auth_source` is `classlink`/`clever`, even with a UUID id and a stale Supabase session present.

Bug A (`_run_classlink_roster_sync`):
- `config is None` → returns without raising.
- partial config (missing `client_id`/`client_secret`) → returns without constructing client.

Gates: full `pytest -q --ignore=tests/load`; `cd frontend && npx vitest run` (for §3.4);
`grep -rln` on every modified file; line-shift pin scan on `classlink_routes.py` /
`auth.py` / `auth_routes.py`; spec reviewer ✅ then opus code-quality reviewer ✅.

---

## 7. Files touched

- `backend/auth.py` — `resolve_classlink_user_id`, `load_classlink_links`, `save_classlink_link`.
- `backend/routes/classlink_routes.py` — teacher-branch wiring, Bug A guard, delete-data gate (§3.6).
- `backend/routes/auth_routes.py` — approval-status SSO short-circuit (§3.5).
- `backend/storage.py` — `classlink_link:` file-backend prefix handler (§3.7).
- `frontend/src/services/api.js` — `getAuthHeaders()` keys off `auth_source` not `id` prefix (§3.4).
- `frontend/src/App.jsx` — set `auth_source` on `window.__graiderUser` in the ClassLink (and Clever) session handlers; add `account_conflict` to the error-message map.
- Tests: new `tests/test_classlink_identity.py` (resolver), `tests/test_classlink_sso.py` (callback, delete-data), `tests/test_auth*.py` (approval-status), `frontend` vitest for `getAuthHeaders`.

---

## 8. Out of scope / follow-ups

- **Unlinked Clever auto-create** (Principle #11 follow-up): Clever's unlinked fallback
  `clever:{id}` has the identical UUID-column problem. Fix sketch: apply the same
  link-or-create resolver to `resolve_clever_user_id`'s 0-match path. Filed separately —
  it changes a live integration's behavior and deserves its own review.
- **Pre-existing GUID-keyed `teacher_data`**: none expected on the cert tenant; no migration
  in this change. If a real tenant accumulated GUID-keyed data before this fix, a one-time
  re-key migration would be needed — track if it ever applies. Concretely:
  `get_oneroster_config(teacher_id)` now reads **UUID-scoped** config (`oneroster.py:430-442`),
  so any `oneroster_config` previously stored under the GUID is neither found nor cleared by
  delete-data. Acceptable for the cert tenant (no prior config); flagged so it's a conscious
  scope decision, not an oversight.

---

## 9. References

- Sentry: APIError `invalid input syntax for type uuid` (`_resilient_execute`);
  AttributeError `NoneType.get` (`_run_classlink_roster_sync`). Both 2026-05-30 09:40:19, release `ea8e267`.
- Diagnosis: Claude main + Codex + Gemini three-way agreement (2026-05-30 session).
- Clever reference pattern: `backend/auth.py:19-62`, `backend/routes/clever_routes.py:503-548`.
- Schema: `cloud_migration.sql:137-298` (UUID `teacher_id` columns).
- Prior ClassLink work: handoff.md (2026-05-30), PRs #588/#595/#596/#600/#603.
