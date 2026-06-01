# Clever → Supabase UUID Identity Parity — Design Spec

**Date:** 2026-06-01
**Class:** B (auth / identity) → opus reviewer, manual merge after clean review.
**Status:** Design approved (Codex three-way review folded in; Gemini unavailable this session — GCP billing/dunning 403).
**Closes:** the unlinked-Clever arm of handoff §6 risk #3.
**Sibling:** PR #604 (`resolve_classlink_user_id`) — the proven pattern this mirrors.

---

## 1. Problem

`classes`, `students`, `published_content`, and `behavior_*` have `teacher_id UUID NOT NULL`. An unlinked Clever teacher's id is the non-UUID string `clever:{id}`, so any insert into those tables raises `invalid input syntax for type uuid`. PR #604 fixed this for ClassLink by resolving to a real Supabase Auth UUID at the OAuth callback. Clever has the **identical latent bug** for the **0-email-match** case.

### Current Clever flow (the gap)
- `backend/auth.py::resolve_clever_user_id(clever_id)` (lines 61-64): unlinked → returns `clever:{id}`.
- `check_auth` (auth.py:299-304): resolves `g.user_id` **per request** from the cookie session; sets `g.user_id`, `g.auth_source='clever'`, but **not** `g.teacher_id`.
- Clever teacher callback (`clever_routes.py:506-535`) already does **half** of link-or-create: exactly 1 email match → `save_clever_link` (link); >1 → skip (logs, stays unlinked); **0 → does nothing** → `clever:{id}` → crash on class/student creation.

### Who is affected & what data exists
A 0-match Clever teacher (Clever-first, no pre-existing Graider account by that email) can accumulate rows on **TEXT** `teacher_id` columns — `teacher_data` (settings/assignments/rubric/resources), `published_assessments` (+ `submissions` via `join_code`), and `student_history` — but **cannot** have `classes`/`students`/`published_content` (those crash). Whether any such teachers exist in prod is unknown without a DB query; the design is **safe regardless** (see §4).

---

## 2. Key decision: hybrid **fail-open**, not fail-closed

ClassLink fails **closed** (block → `account_conflict`) because it had **no live users**. Clever has **live unlinked teachers working under `clever:{id}` today**. Blocking them on a `>1`-match or a Supabase outage would be an **availability regression**. And it is unnecessary: `clever:{id}` is an **isolated namespace** (not a wrong-account merge), so falling back to it is safe — it never merges into someone else's account.

**Therefore Clever resolution is a best-effort _upgrade_, never a block.** The resolver returns a **structured outcome**, and only UUID outcomes trigger session persistence, the DB roster sync, and the data-claim. Legacy outcomes preserve today's exact behavior (works for TEXT features; still crashes on class-creation — *no worse than now*).

| Outcome | Trigger | Effect |
|---|---|---|
| `linked_uuid` | `clever_link` already exists | use linked UUID (unchanged) |
| `matched_uuid` | exactly 1 email match | `save_clever_link` + use UUID (no claim — §4) |
| `created_uuid` | 0 email matches | `create_user` (approved, `auth_source=clever`) + link + **claim** + use UUID |
| `ambiguous_legacy` | >1 email match | fall back to `clever:{id}`; WARNING + Sentry; **no block** |
| `transient_legacy` | no Supabase client / list outage | fall back to `clever:{id}`; **no block** |
| `create_failed_legacy` | `create_user` raised; race re-resolve found 0/>1 | fall back to `clever:{id}`; **no block** |

Security note: fail-open is safe specifically because the legacy value is the teacher's *own* isolated `clever:{id}` namespace. We **never** auto-merge into a matched account on ambiguity (>1) — that path stays legacy.

---

## 3. Components

### 3.1 `backend/auth.py` — resolver
New `resolve_clever_user_id_or_create(clever_id, email, name=None) -> (id, outcome)`:
- Mechanics mirror `resolve_classlink_user_id` (1-match link, 0-match create with `secrets.token_urlsafe(32)` password + `email_confirm` + `approved:True` + `auth_source:"clever"` + first/last name, deterministic create-race re-resolve).
- **Differs by failing open**: missing email / no Supabase / list error / >1 match / unrecoverable create → return `(f"clever:{clever_id}", <legacy outcome>)`, not `None`.
- Keep the existing cheap `resolve_clever_user_id(clever_id)` (no email) unchanged for read-only/backward-compat sites.

New `_claim_clever_text_data(clever_id, uuid)` (best-effort, non-fatal, logged + Sentry):
- Re-key `teacher_data`, `published_assessments`, `student_history` `teacher_id` from `clever:{id}` → `uuid` via Supabase `update().eq("teacher_id", f"clever:{clever_id}")`.
- **Called on the `created_uuid` path only.** The created UUID is brand-new, so a blind UPDATE cannot collide with a pre-existing `(teacher_id, data_key)` PK. (`submissions` is NOT in the set — it has no `teacher_id`, it follows `join_code`.)

### 3.2 `backend/auth.py` — `check_auth` Clever branch (299-304)
- Read `clever_user['user_id']` when present (set at callback); else fall back to `resolve_clever_user_id(clever_user['clever_id'])` (old sessions — unchanged behavior).
- **Set `g.teacher_id = g.user_id`** (Codex: `clever_delete_data` reads `g.teacher_id`; the ClassLink branch already does this at line 313, the Clever branch was missing it).
- `g.user_email`, `g.auth_source='clever'`, `g.district_id` unchanged.

### 3.3 `backend/routes/clever_routes.py` — teacher callback (replaces 506-535)
- Call `resolve_clever_user_id_or_create(clever_id, clever_email, clever_user.get("name"))`.
- On a **UUID** outcome: store `session["clever_user"]["user_id"] = uuid`; the `created_uuid` path's claim runs inside the resolver.
- **Roster sync (line 541): start the background DB sync only on a UUID outcome, and pass the resolved UUID directly** (not `resolve_clever_user_id(clever_id)`). Never sync a `clever:{id}` legacy session into UUID columns.
- Audit uses the resolved id.
- No `account_conflict` redirect — Clever never blocks.

### 3.4 `backend/routes/clever_routes.py` — `clever_delete_data` (770)
- Gate on `g.auth_source == 'clever'`, **not** `g.teacher_id.startswith("clever:")` (Codex blocker: a UUID-linked Clever teacher must be able to delete; mirrors #604's ClassLink delete-data fix). The downstream `delete_clever_data(teacher_id)` + `.eq('teacher_id', teacher_id)` deletes then correctly target the UUID rows.

### 3.5 `backend/routes/clever_routes.py` — `/api/clever/session` (565)
- Return `user_id` (the session-stored UUID when present, else the cheap-resolved id) so `App.jsx` stores the real id. Minor correctness; `auth_source`-based `isSsoUser` already prevents stale-Bearer.

### 3.6 Frontend
- **No change needed.** #604 made `isSsoUser` (`api.js:16-19`) and OnboardingWizard (`OnboardingWizard.jsx:153`) `auth_source`-based; both already cover Clever. Verified, not assumed.

---

## 4. Deferred (documented follow-up, NOT in this PR)

**1-match link-path orphan + PK-conflict handling.** The existing 1-match merge (and our `matched_uuid` path) links a Clever teacher to a **pre-existing** Supabase account that may already hold its own `teacher_data`/`student_history` under its UUID. Re-keying `clever:{id}` rows there risks a `(teacher_id, data_key)` PK collision, so we do **not** claim on the match path. This orphan is **pre-existing** (the current merge code never claimed either). Follow-up will add conflict-aware claim (skip/merge colliding keys) for the match path. Fix sketch: `INSERT ... ON CONFLICT (teacher_id, data_key) DO NOTHING` semantics, or per-key existence check before re-key.

---

## 5. Error handling & backward-compat

- Already-linked teachers → `linked_uuid`, unchanged.
- Old sessions without `user_id` → `check_auth` falls back to the cheap resolver — unchanged.
- Data-claim failures are non-fatal (logged + Sentry); identity resolution is the load-bearing step.
- `>1` match never auto-merges (stays legacy) — same safety stance as ClassLink, achieved without blocking.

---

## 6. Testing

Unit (`tests/test_clever_identity.py`, new):
- `resolve_clever_user_id_or_create` outcomes: `linked_uuid`, `matched_uuid` (links, no claim), `created_uuid` (creates + links + claims), `ambiguous_legacy` (>1, returns `clever:{id}`, no link/claim), `transient_legacy` (no Supabase), `create_failed_legacy` (create raises, race re-resolve fails).
- `_claim_clever_text_data` re-keys all three tables on create; is a no-op when empty; non-fatal on error.
- `check_auth` Clever branch sets `g.teacher_id == g.user_id` from session `user_id`; falls back for old sessions.
- `clever_delete_data` returns 200 for a UUID-linked Clever session (`g.auth_source=='clever'`), 403 for non-Clever.
- Roster sync is **not** started on a legacy outcome; started with the UUID on a UUID outcome.

Regression: full Clever compliance suite (38) + `tests/test_clever_callback.py` green; full backend suite (`pytest -q --ignore=tests/load`).

---

## 7. Review provenance

- **Codex** (read-only): returned BLOCKED-as-written; caught the `delete-data` prefix gate, roster-sync-on-legacy, missing `g.teacher_id`, `student_history` in the claim set, and recommended the structured fail-open outcome. All folded in above.
- **Self-review**: confirmed fail-open over fail-closed (live users + isolated namespace) and create-only claim (PK-collision avoidance).
- **Gemini**: unavailable this session (GCP billing/dunning 403). Optional third pass against this committed spec once billing is resolved.
