# ClassLink Teacher UUID Identity Resolution — Design

**Date:** 2026-05-30
**Class:** B (auth / identity — net-new behavior)
**Status:** Approved (brainstorming) → ready for implementation plan

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

1. **Linked?** Read link table `classlink_link:{guid}` (system scope). If a
   `supabase_user_id` is stored, return it.
2. **Email match?** `list_all_users(sb)` (`backend/utils/supabase_users.py`), filter by
   case-insensitive exact email:
   - exactly 1 match → `save_classlink_link(guid, match.id)`, return `match.id`.
   - more than 1 match → log warning, return `None` (ambiguous; do not guess — caller fails closed).
3. **No match** → `sb.auth.admin.create_user({email, email_confirm: True,
   password: <secrets.token_urlsafe(32)>, user_metadata: {approved: True,
   first_name, last_name, auth_source: 'classlink'}})`. Save link. Return new `user.id`.

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

- Resolver Supabase failures → log + Sentry capture → return `None` → callback fails closed
  with `account_conflict` (no crash, no half-provisioned state).
- Ambiguous (>1) email match → `None` → `account_conflict` (never silently merge).
- `admin.create_user` failure → caught in resolver → `None` → `account_conflict`.
- Bug A: `None`/partial config → clean `return` (skip sync), no exception.

---

## 6. Testing (TDD; Class B ⇒ opus code-quality review)

`resolve_classlink_user_id` (mock Supabase admin + `list_all_users`):
- linked hit returns stored UUID, no create call.
- single email match → links + returns that UUID.
- multiple matches → returns `None`, no create, no link.
- no match → calls `admin.create_user` with `approved=True` + `auth_source='classlink'`, links, returns new UUID.
- Supabase failure → returns `None`.

Callback:
- success stores UUID (not GUID) in `session['classlink_user']['user_id']` and passes UUID to `_trigger_roster_sync`.
- `None` resolver → `account_conflict` redirect.

Bug A (`_run_classlink_roster_sync`):
- `config is None` → returns without raising.
- partial config (missing `client_id`/`client_secret`) → returns without constructing client.

Gates: full `pytest -q --ignore=tests/load`; `grep -rln` on every modified file; line-shift
pin scan on `classlink_routes.py` / `auth.py`; spec reviewer ✅ then opus code-quality
reviewer ✅.

---

## 7. Files touched

- `backend/auth.py` — `resolve_classlink_user_id`, `load_classlink_links`, `save_classlink_link`.
- `backend/routes/classlink_routes.py` — teacher-branch wiring, Bug A guard.
- `frontend/src/App.jsx` — `account_conflict` handled by existing `classlink_error` path (verify; likely no change needed if generic).
- Tests: `tests/test_classlink_sso.py`, `tests/test_auth*.py` (or a new `tests/test_classlink_identity.py`).

---

## 8. Out of scope / follow-ups

- **Unlinked Clever auto-create** (Principle #11 follow-up): Clever's unlinked fallback
  `clever:{id}` has the identical UUID-column problem. Fix sketch: apply the same
  link-or-create resolver to `resolve_clever_user_id`'s 0-match path. Filed separately —
  it changes a live integration's behavior and deserves its own review.
- **Pre-existing GUID-keyed `teacher_data`**: none expected on the cert tenant; no migration
  in this change. If a real tenant accumulated GUID-keyed data before this fix, a one-time
  re-key migration would be needed — track if it ever applies.

---

## 9. References

- Sentry: APIError `invalid input syntax for type uuid` (`_resilient_execute`);
  AttributeError `NoneType.get` (`_run_classlink_roster_sync`). Both 2026-05-30 09:40:19, release `ea8e267`.
- Diagnosis: Claude main + Codex + Gemini three-way agreement (2026-05-30 session).
- Clever reference pattern: `backend/auth.py:19-62`, `backend/routes/clever_routes.py:503-548`.
- Schema: `cloud_migration.sql:137-298` (UUID `teacher_id` columns).
- Prior ClassLink work: handoff.md (2026-05-30), PRs #588/#595/#596/#600/#603.
