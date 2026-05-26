# ClassLink Roster Server Certification Parity — Design Spec

**Date:** 2026-05-25
**Status:** Approved (brainstorm complete) — ready for implementation plan
**Author:** Claude (3-AI consult: Codex gpt-5.5-high + Gemini, both decisional/converged)
**Scope phase:** Roster Server fast-follow (SSO already certified — see
`2026-05-25-classlink-sso-certification-readiness-design.md`)
**Classification:** **Class B** (auth/identity + FERPA right-to-delete) per CLAUDE.md Principle #13 —
a code review **gates** the merge; no auto-merge with a review in flight.

---

## 1. Goal

Build **ClassLink Roster Server certification parity** (cert-minimum scope) so a rostered ClassLink
**teacher and student** both land in their provisioned accounts and the integration can be certified
for rostering. Four code areas, all reusing existing infrastructure:

1. **Identity/prefix correctness** for ClassLink roster data (tenant-scoped, fail-closed).
2. **ClassLink student SSO flow** — currently a dead-end — with full multi-enrollment parity.
3. **`/api/classlink/delete-data`** (FERPA right-to-delete), plus a shared-function orphan-row fix.
4. **Frontend** student-portal mirror so the student SSO round-trip actually completes.

This does **not** block ClassLink SSO certification (already done). It is a deferred fast-follow.

## 2. Background & the defect

ClassLink's Roster Server exposes **OneRoster 1.1** endpoints, so ClassLink roster sync reuses the
OneRoster client + `normalize_roster` (`backend/oneroster.py:298`). But `normalize_roster` hardcodes
an `oneroster:` prefix on every `external_id`. ClassLink's login-triggered sync
(`backend/routes/classlink_routes.py:97` `_trigger_roster_sync`) calls it unchanged and passes
`provider="classlink"` for logging only.

**Net effect today:** a ClassLink-rostered student is stored as
`students.student_id_number = "oneroster:" + sourcedId`, under
`teacher_id = "classlink:{tenant}:{sourcedId}"`, sharing the OneRoster namespace. The
`provider="classlink"` tag is cosmetic.

Two consequences:

- **Student SSO is a dead-end.** The callback sets `session['classlink_student']`
  (`classlink_routes.py:392`) but **nothing reads it** (grep-verified — only write + the logout
  pop). A rostered ClassLink student cannot reach their provisioned record.
- **Cross-tenant collision risk.** ClassLink `sourcedId` is unique only *within a tenant* (the exact
  reason the teacher GUID is tenant-scoped, `_classlink_guid`). The Clever-style student lookup
  queries `student_id_number` **globally** (`clever_routes.py:260`, `.eq(..., clever_id)` with no
  teacher scope) before it knows the class. A non-tenant-scoped student key would let two districts
  sharing a `sourcedId` surface **each other's classes in the picker** — a FERPA hole.

## 3. The 3-AI consult outcome (design fork resolved)

The consult (`/tmp/classlink_roster_consult.md`) put the identity/prefix fork to Codex gpt-5.5-high
and Gemini. **Both independently converged**, rejecting both the handoff's bare-`classlink:` Approach
2 and Approach 1 (live in `oneroster:` namespace):

> **Verdict: Approach 2, tenant-scoped.** The roster key must be
> `classlink:{quote(tenant_id)}:{quote(sourcedId)}` — matching the teacher GUID convention — applied
> to ClassLink roster students, classes, enrollments, and accommodations, **and** to the student-SSO
> lookup. OneRoster keeps `oneroster:{sourcedId}` byte-identical via a default arg.

Per-question consensus: tenant-scope the student key (**#1 risk**); fail closed on
SourcedId↔roster mismatch; `teacher_id`-scoped delete; add the `classlink:` prefix-table entry but
**defer wiring** ClassLink deactivation. The one disagreement — Gemini allowed a prefix-validated
email fallback; Codex said drop it entirely — is resolved in favor of **Codex (no email fallback)**:
for a Class B FERPA path, a global email lookup is the exact cross-tenant match we are eliminating.

## 4. Design

### 4.1 Identity model — one shared key helper

The single rule that makes everything else correct: **the roster-write key and the student-SSO-read
key are produced by one function.** Encoding mismatch between write and read is the only silent
failure mode; one helper eliminates it.

New helper in `classlink_routes.py`, next to `_classlink_guid`, same percent-encoding:

```python
def _classlink_roster_external_id(tenant_id, sourced_id):
    """Tenant-scoped roster external_id for ClassLink rows.

    Format: ``classlink:{quote(tenant)}:{quote(sourced_id)}`` — same encoding as
    ``_classlink_guid`` so a ':' inside a component cannot create a colliding key.
    Always returns a string (tolerant of empty components, matching normalize_roster).
    """
    tenant = urllib.parse.quote(str(tenant_id or "").strip(), safe="")
    sid = urllib.parse.quote(str(sourced_id or "").strip(), safe="")
    return f"classlink:{tenant}:{sid}"
```

Used on **both** sides — write (Section 4.2) and read (Section 4.3).

### 4.2 `normalize_roster` parameterization (write side, shared function)

Change the signature to a **default-preserving callable** (a builder, not a prefix-string, so it can
encode the per-id `sourcedId`):

```python
def normalize_roster(raw, external_id_for=None):
    if external_id_for is None:
        external_id_for = lambda sid: f"oneroster:{sid}"   # OneRoster default — byte-identical
```

Every hardcoded `f"oneroster:{sid}"` becomes `external_id_for(sid)` — in **all five** sites: class
external_id, student external_id, enrollment `class_external_id`, enrollment `student_external_id`,
and accommodation `student_external_id`. **OneRoster and any caller passing nothing get
byte-identical output** (locked by a characterization test, Section 4.5).

`_trigger_roster_sync` (which already has `tenant_id` in scope) passes:

```python
classes, students_norm, enrollments, _acc = normalize_roster(
    raw, external_id_for=lambda sid: _classlink_roster_external_id(tenant_id, sid)
)
```

Add to `backend/roster_sync.py`:

```python
_PROVIDER_PREFIXES = {
    "clever": "",
    "oneroster": "oneroster:",
    "manual": "manual-",
    "classlink": "classlink:",   # NEW — keys start with "classlink:" so the prefix matches
}
```

This entry alone closes the regression Gemini flagged: with `classlink:` in the map,
`deactivate_missing_students(provider="clever")` now **skips** ClassLink rows (they land in
`other_prefixes`) instead of deactivating them. Sole consumer of `_PROVIDER_PREFIXES` is
`deactivate_missing_students`; `sync_roster_to_db` uses external_ids verbatim and is unaffected.

### 4.3 ClassLink student SSO flow (read side — full multi-enrollment parity)

Mirror Clever's proven path (`clever_routes.py:126,233,442,888,934`), tenant-scoped:

- **`_create_classlink_student_session(tenant_id, person_id)`** — build the lookup key via
  `_classlink_roster_external_id(tenant_id, person_id)`; query `students` by `student_id_number ==
  key`; enumerate enrollments across all matching rows into `(student_row, class)` candidates.
  Exactly one → mint; more than one → return `needs_class_selection` + selection token.
- **Session mint** — reuse the existing `_mint_clever_student_session` pattern (insert hashed
  `student_sessions` row, 8h expiry, return raw `X-Student-Token`). Factor a provider-neutral mint
  if cleaner, but do not change the Clever mint's behavior.
- **New endpoints:**
  - `POST /api/classlink/student-token` — exchange short-lived auth code for the session token
    (mirror `exchange_student_auth_code`).
  - `GET/POST /api/classlink/select-class` — multi-enrollment picker (mirror `select_clever_class`);
    GET lists candidates without consuming the token, POST mints on a valid choice (single-use on
    success only).
- **Callback change** (`classlink_routes.py:386-399`): replace the dead-end
  `redirect("/student?classlink_login=success")` with the Clever-style result:
  `/student?classlink=1&code=<auth_code>` for a single match, or
  `/student?classlink_select=1&sel=<selection_token>` for multi-enrollment. Remove the unused
  `session['classlink_student']` write.
- **Frontend** (`StudentApp.jsx`): add `classlink` / `classlink_select` URL-param handlers that
  mirror the existing `clever` / `clever_select` ones, hitting `/api/classlink/student-token` and
  `/api/classlink/select-class`. No new UI — the existing picker/loading components are reused.

**Fail-closed (Codex's stricter call):** if no tenant-scoped row matches, do **not** create a student
row, do **not** fall back to a global email lookup, do **not** mint a token. Redirect to a
"not provisioned — ask your teacher to sync the roster" state and log `tenant_id` + hashed
`person_id`.

### 4.4 `/api/classlink/delete-data` + shared orphan fix

- **New endpoint** mirroring OneRoster `delete_data` (`oneroster_routes.py:302`): guard on
  `g.teacher_id.startswith("classlink:")` (mirrors `clever_delete_data`'s provider guard), call
  `delete_roster_data(g.teacher_id)`, clear the stored `oneroster_config` for that teacher
  (ClassLink roster uses the OneRoster config slot), and audit-log. Auth via `@require_teacher`
  (ClassLink session resolves `g.teacher_id` to the `classlink:` GUID at `auth.py:212`).
- **Shared orphan fix (approved):** in `delete_roster_data` (`roster_sync.py:254`), move the student
  +`student_sessions` deletion **out of** the `if class_ids:` branch so a teacher with students but
  no classes does not leave orphan rows. Strictly more-complete deletion for **all three** consumers
  (ClassLink, OneRoster `delete_data`, Clever via `clever.py:581`) — can only delete *more* of the
  target teacher's own rows, never another teacher's (still `teacher_id`-scoped). Add a regression
  test.

**Delete is `teacher_id`-scoped, not prefix-scoped** (consult consensus): `students`/`classes` are
already per-teacher; a student shared across two ClassLink teachers is two separate rows, so
prefix-scoped delete would risk another teacher's rows.

### 4.5 Testing (Class B — review gates the merge)

Shared functions (`normalize_roster`, `deactivate_missing_students`, `delete_roster_data`) are live
under OneRoster + Clever — the priority is **no regression**.

- **Characterization:** `normalize_roster(raw)` with no `external_id_for` == current output
  (locks OneRoster byte-identical). Pin both classes and students/enrollments/accommodations.
- **New unit:** `external_id_for` builder produces tenant-scoped `classlink:{tenant}:{sid}` keys
  across classes, students, enrollments (both refs), and accommodations.
- **FERPA cross-tenant:** two tenants sharing a `sourcedId` produce **distinct** keys; the SSO
  lookup with tenant A's key never returns tenant B's rows.
- **Encoding parity:** the write-side key (via `normalize_roster` builder) and the read-side key
  (SSO lookup) are byte-identical for the same `(tenant, sourcedId)`, including special-char
  `sourcedId`s.
- **Student SSO:** single-enrollment mint; multi-enrollment picker; fail-closed no-match — and an
  explicit assertion that **no email fallback** occurs.
- **Deactivation:** adding the `classlink:` prefix does not change OneRoster/Clever deactivation
  outcomes, and a Clever sync no longer deactivates `classlink:` rows.
- **Delete:** `teacher_id`-scoped delete; orphan-student regression (teacher with students but no
  classes → students deleted).

### 4.6 Scope boundaries

**In scope:** Sections 4.1–4.5 (the four code areas + frontend mirror + tests).

**Out of scope (deferred, per consult consensus):**

- **Wiring** ClassLink into `deactivate_missing_students` *calls*. A login-triggered sync can be
  partial or fail midway; accidental deactivation is higher-risk than stale rows. We only add the
  prefix-table entry (defensive). ClassLink deactivation belongs on a deliberate full-sync path with
  its own tests, later.
- **Periodic cron sync** for ClassLink (`sync_routes.py` keeps `classlink` excluded).
- **Roster-config provisioning UI** — `_trigger_roster_sync` already reads the OneRoster config slot;
  how it gets populated is unchanged from today.

**Live dependency to verify (the same #1 pre-cert blocker from the SSO spec):** confirm that the
ClassLink userinfo `SourcedId` used as `person_id` equals the OneRoster roster `sourcedId` for the
same person. If they diverge, SSO-id ≠ roster-external-id and the student finds no row — the design
**fails closed** (Section 4.3), but the reconciliation contract must hold for the happy path. Codex
explicitly flagged the `_extract_person_id` `UserId` fallback as a known divergence source.

## 5. Risks & mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Cross-tenant student-SSO lookup collision | **Critical** | Tenant-scoped key (4.1); FERPA cross-tenant test (4.5) |
| Regressing OneRoster/Clever via shared `normalize_roster` | High | Default arg keeps callers byte-identical; characterization test |
| Clever sync deactivating ClassLink rows | High | `_PROVIDER_PREFIXES["classlink"]` entry (4.2) + test |
| Write/read key encoding drift | High | Single `_classlink_roster_external_id` helper on both sides; parity test |
| SourcedId ↔ roster sourcedId mismatch | Medium | Fail closed, no row creation / no email fallback (4.3); verify live |
| `delete_roster_data` orphan rows | Medium | Move student delete out of `if class_ids:` (4.4) + regression test |

## 6. References

- **Consult:** `/tmp/classlink_roster_consult.md` (prompt); Codex + Gemini outputs captured this
  session. Both converged on tenant-scoped Approach 2.
- **SSO spec (predecessor):** `docs/superpowers/specs/2026-05-25-classlink-sso-certification-readiness-design.md`.
- **Handoff:** `handoff.md` (§6 design fork, §7 next steps) — this spec resolves §6.1 toward the
  tenant-scoped variant.
- **Key code:**
  - `backend/oneroster.py:298-397` — `normalize_roster` (hardcoded `oneroster:` prefix).
  - `backend/roster_sync.py:26-30` (`_PROVIDER_PREFIXES`), `:210-251`
    (`deactivate_missing_students`), `:254` (`delete_roster_data` orphan bug).
  - `backend/routes/classlink_routes.py:58-95` (`_classlink_guid`/`_extract_person_id`), `:97-148`
    (`_trigger_roster_sync`), `:386-399` (student callback dead-end), `:445-450` (logout).
  - `backend/routes/clever_routes.py:126` (mint), `:233` (`_create_clever_student_session`), `:442`
    (callback student branch), `:759` (delete), `:888` (select-class), `:934` (student-token).
  - `backend/routes/oneroster_routes.py:302` (`delete_data` pattern).
  - `frontend/src/components/StudentApp.jsx:12-105` (clever/clever_select handlers to mirror).
