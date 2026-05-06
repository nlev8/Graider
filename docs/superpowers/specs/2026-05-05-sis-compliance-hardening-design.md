# SIS Compliance Hardening Sprint — Design

**Date:** 2026-05-05
**Branch:** `feature/sis-compliance-hardening`
**Tracks:** Plan A precondition for Candidate A (SettingsTab.jsx extraction sprint)

---

## Goal

Close 2 CRITICAL + 4 verified MAJOR compliance gaps in Graider's SIS integrations (Clever, ClassLink, OneRoster, LTI 1.3) so the SettingsTab extraction sprint can begin without compounding compliance debt onto a refactor.

## Why this sprint exists

A 2026-05-05 high-effort Codex audit (agentId `acaac2c384ab8da02`) of `backend/clever.py`, `backend/routes/{clever,classlink,oneroster,lti}_routes.py`, `backend/oneroster.py`, `backend/lti.py`, and the SIS UI in `frontend/src/tabs/SettingsTab.jsx` found:

- **2 CRITICAL ClassLink findings**: callback creates an authenticated session without validating the OIDC `id_token` (no signature, `iss`, `aud`, `exp` checks) — `backend/routes/classlink_routes.py:226`. State validation is skipped when expected or returned state is missing — `backend/routes/classlink_routes.py:201-207`.
- **11 MAJOR findings** across Clever / ClassLink / OneRoster / LTI 1.3.
- A second Codex pass (agentId `a12dfbfb5031a6a8a`) verified findings against published platform specs and dropped 6 MAJORs as either incorrect (Clever scope-in-URL, ClassLink scope set, OneRoster `tobedeleted` soft-delete) or out-of-scope without district config (Clever Library/Complete tier gating, OneRoster `modifiedSince` delta, OneRoster demographics minimization). See memory `project_sis_compliance_hardening_2026-05-05.md` for the full skip list and reasoning.

The remaining 2 CRITICAL + 4 MAJOR findings ship as 6 PRs.

## Architecture

Three change classes:

| Class | Meaning | Review pattern |
|---|---|---|
| **SIS-CONTRACT** | Touches OAuth/OIDC flow shape, scope strings, claim validation, or wire-level platform contracts | Extra Codex high-effort review pre-merge |
| **INTERNAL** | Observability, audit logging, frontend wiring; no contract change | One Codex review pass |
| **DOC** | Documentation reconciliation only | None |

Sequencing constraint: PR 2 depends on PR 1 (nonce validation needs id_token consumption to land first).

## In Scope — 6 PRs

### PR 1 — ClassLink OIDC id_token validation [SIS-CONTRACT]

**Problem:** `backend/routes/classlink_routes.py:226` extracts `access_token` from token response and calls userinfo endpoint with it. The OIDC `id_token` (which ClassLink returns because we already request `openid` scope at line 31) is never consumed. Bearer-token-to-userinfo authenticates the bearer of the access token, not the user identity.

**Approach:**
1. Discover ClassLink OIDC config via `https://launchpad.classlink.com/.well-known/openid-configuration` to get the authoritative `issuer` and `jwks_uri`. Cache the configuration result with a TTL of 1 hour to avoid per-callback overhead.
2. Read `id_token` from the token-exchange response alongside `access_token`. If absent, redirect with `classlink_error=no_id_token` and audit-log.
3. Validate `id_token`: RS256 signature via `PyJWKClient` (already in use at `backend/lti.py:226-227`), `iss` matches discovered issuer, `aud` matches our `client_id`, `exp` is in the future, with reasonable clock skew.
4. Extract identity (`sub`, `email`, `name`, `given_name`, `family_name`) from id_token claims as the source of truth; userinfo call becomes optional fallback for fields not in the id_token (e.g., `Role`, `TenantId`).
5. Fail closed on any validation failure with a distinct error code per failure class.

**Files:**
- Modify: `backend/routes/classlink_routes.py:226-247` (callback id_token consumption)
- Create: `backend/services/classlink_oidc.py` (discovery + JWKS caching helper)
- Modify: `tests/test_classlink_sso.py` (add id_token validation tests)

**Risk:** ClassLink may return id_token only on certain scope combos. The current scope `profile oneroster email openid` per line 31 should be sufficient. If id_token is empty, the PR fails closed (acceptable — surfaces the problem).

---

### PR 2 — ClassLink state/nonce hardening [SIS-CONTRACT]

**Problem:** `backend/routes/classlink_routes.py:201-207` allows callback when expected_state is missing OR returned state is missing. The justifying comment ("code exchange validates the OAuth flow") is incorrect — code exchange proves the redirect_uri authenticity, not request-origin CSRF protection.

**Approach:**
1. Distinguish self-initiated from LaunchPad-initiated flows by setting a session marker `classlink_oauth_initiated_by_us = True` in `/api/classlink/login-url`.
2. In callback:
   - If `classlink_oauth_initiated_by_us` is set → require state match (no exception). Reject with `state_mismatch`.
   - If not set → treat as LaunchPad-initiated. Rely on id_token signature (from PR 1) for authenticity.
3. Add nonce: include a fresh `nonce` query param in `/login-url`, store in session, validate the id_token's `nonce` claim matches in callback (only for self-initiated flows).
4. Audit-log every rejection.

**Files:**
- Modify: `backend/routes/classlink_routes.py:163-180` (`/login-url` adds nonce)
- Modify: `backend/routes/classlink_routes.py:185-291` (callback enforces state + nonce based on flow type)
- Modify: `tests/test_classlink_sso.py:136` (the test that currently pins the wrong direction — explicitly allows missing state. Replace with strict-self-initiated test + permissive-LaunchPad test)

**Depends on:** PR 1 (nonce check requires id_token consumption).

---

### PR 3 — SSO PII log redaction [INTERNAL]

**Problem:**
- `backend/clever.py:107` logs `resp.text` from token endpoint failure (may contain access_token, refresh_token, full bodies).
- `backend/routes/clever_routes.py:338,351` log raw emails and Clever IDs at login + student-session paths.

**Approach:**
1. `backend/clever.py:107`: log only `resp.status_code` and a static failure marker. Drop `resp.text`. Drop `redirect_uri` from log message (it's already in env config — no audit value).
2. Login PII paths: log only event type + teacher_id (already hashed). Replace raw email with `_redact_email("user@example.com") -> "u***@example.com"` helper for cases where partial signal is genuinely useful (e.g., support debugging). Drop raw Clever IDs from logs entirely.
3. Add tests asserting log capture contains no email + no token strings on failure paths.

**Files:**
- Modify: `backend/clever.py:107` (token-failure log)
- Modify: `backend/routes/clever_routes.py:338,351` (login PII)
- Create: `backend/utils/redaction.py` (`_redact_email` helper)
- Modify: `tests/test_clever_compliance.py` (add log-redaction tests)

---

### PR 4 — ClassLink frontend logout wiring [INTERNAL]

**Problem:** `frontend/src/App.jsx:466` logout handler calls `/api/clever/logout` for Clever users but not `/api/classlink/logout` for ClassLink users. ClassLink Flask sessions persist after frontend logout.

**Approach:**
1. Extend logout handler to detect ClassLink-backed users (the existing `window.__graiderUser` is set during ClassLink session resolution; check if it starts with `classlink:` or has a `classlink_id` field).
2. Call `/api/classlink/logout` in addition to existing flow. Both endpoints are idempotent — safe to call regardless of detected provider.
3. Cleanest implementation: call all SSO logout endpoints unconditionally; each is a no-op when the user isn't authenticated through that provider. Saves provider detection logic.

**Files:**
- Modify: `frontend/src/App.jsx:466` (logout handler)
- Modify: `frontend/src/__tests__/App.test.jsx` (if such tests exist) or add focused logout test.

---

### PR 5 — LTI deployment_id allowlist [SIS-CONTRACT]

**Problem:** `backend/lti.py:254-256` only validates `deployment_id` presence; `backend/routes/lti_routes.py:237-244` platform config schema omits `deployment_id`. An attacker who acquires platform credentials could launch from any deployment.

**Approach:**
1. Extend platform config to include `deployment_ids: list[str]` (multi-deployment support — common for K-12 LMS deployments).
2. `backend/routes/lti_routes.py` POST `/api/lti/config`: accept `deployment_ids` in payload (optional but encouraged), persist.
3. `backend/lti.py` `validate_launch_jwt` (after line 254): look up platform config by `iss`, check `deployment_ids` list, reject if non-empty list and claim's `deployment_id` not in list.
4. **TOFU migration**: if existing config has empty `deployment_ids`, log warning + accept once + record observed `deployment_id`. Subsequent launches with different deployment_id rejected unless config explicitly updated. Documents migration path for prod registrations that pre-date this change.
5. UI: SettingsTab LTI registration form gains a "Deployment IDs (comma-separated)" field. **NOTE:** SettingsTab UI lives at `frontend/src/tabs/SettingsTab.jsx:2326-2747` (LTI block per audit) — this is the only frontend touch needed; deferred extraction sprint will move the panel later.

**Files:**
- Modify: `backend/lti.py:220-258` (validate_launch_jwt — deployment_id enforcement)
- Modify: `backend/routes/lti_routes.py:227-249` (`POST /api/lti/config` accepts `deployment_ids`)
- Modify: `backend/lti.py` (`save_platform_config` shape — wherever schema is defined)
- Modify: `frontend/src/tabs/SettingsTab.jsx` LTI form — single field add
- Modify: `tests/test_lti.py`, `tests/test_lti_routes.py` (allowlist + TOFU paths)

---

### PR 6 — SIS audit coverage pass [INTERNAL]

**Problem:** `backend/clever.py:123` (`/me` read) and `backend/clever.py:136` (`/users/{id}` read) touch PII but are not routed through `_clever_audit()`/`audit_log`. Doc claims audit covers all PII reads.

**Approach:**
1. `backend/clever.py:123-152`: after successful `/me` and `/users/{id}` reads, call `audit_log("CLEVER_USER_READ", ...)` with teacher_id only (no PII payload).
2. `backend/roster_sync.py`: emit `ROSTER_SYNC_START` and `ROSTER_SYNC_COMPLETE` events (not per-row — avoids log explosion).
3. Verify ClassLink callback already audit-logs (it does — line 287-289). Verify OneRoster sync flows are audited.

**Files:**
- Modify: `backend/clever.py` (audit calls)
- Modify: `backend/roster_sync.py` (sync entry/exit events)
- Modify: `tests/test_clever_compliance.py` (assert audit_log called per PII read)

---

### Doc reconciliation [DOC]

Standalone commit (not a separate PR — bundled with PR 6 or filed last).

- `docs/CLEVER_COMPLIANCE_STATUS.md:5`: change "Production-ready for Clever Library certification" → "Compliance hardening in progress (PRs landing 2026-05-05)" while sprint is in flight; restore on completion with reference to landed PRs.
- `docs/CLEVER_COMPLIANCE_STATUS.md:94`: mark "Periodic roster sync (24h)" as **shipped** (cite `backend/routes/sync_routes.py:269` + `.github/workflows/roster-sync.yml`).
- `CLEVER_INTEGRATION.md:1287`: same treatment as above.

## Out of Scope (skip list)

These findings were filed during the audit but explicitly dropped after Codex verification. **Do not re-tackle without new evidence.**

| Finding | Reason |
|---|---|
| Clever scopes in authorize URL | Clever docs: scopes are app-registration-assigned, not URL-required. Current code is spec-correct. |
| ClassLink scope-set change | Code already uses approved scope set; "minimal" is district-app specific. |
| OneRoster `tobedeleted` → forced soft-delete | OneRoster v1.1 §3.3: deletion timing "implementation dependent." Current skip is defensible. |
| Clever Library-tier IEP/ELL overfetch gating | Needs district tier signal we don't have wired. Defer. |
| OneRoster `modifiedSince` delta sync | Performance, not compliance. Filed as product hardening. |
| OneRoster demographics minimization | Needs config-backed consent gate, not a rushed compliance fix. |

## Testing Strategy

- Each PR ships with tests in the same commit.
- ClassLink mock fixtures (token endpoint returning `access_token` + `id_token`, JWKS endpoint returning RS256 keypair, userinfo endpoint) live in `tests/test_classlink_sso.py` — extend, don't duplicate.
- LTI tests already use platform-config fixtures — extend `tests/test_lti.py` allowlist scenarios.
- Audit assertions extend `tests/test_clever_compliance.py`.
- No backend-test coverage drop: CI floor is `--cov-fail-under=32` (per `CLAUDE.md` says 40 — separate doc-drift item, fixing in doc reconciliation).

## Risks + Mitigations

| Risk | Mitigation |
|---|---|
| ClassLink id_token format / claims unverified | Implementation reads ClassLink developer docs + .well-known/openid-configuration first. If id_token is missing or unsupported by the platform tier, escalate before merging PR 1. |
| Existing prod LTI registrations lack `deployment_ids` | TOFU migration (record first-seen, require match thereafter). Audit-log warning on TOFU acceptance. |
| Audit-log volume blocks request paths | Already async-safe in current implementation. Per-call (not per-row) granularity. |
| Frontend logout race / partial logout | Call all logout endpoints in parallel + tolerate individual failures (logout is idempotent). |
| State/nonce sequencing breaks LaunchPad-initiated flows | PR 2 explicitly preserves LaunchPad path via the `classlink_oauth_initiated_by_us` session marker. Tested both directions. |

## Definition of Done

- 6 PRs merged to `main`; CI green on each (Backend Tests, Frontend Build, Bandit SAST, Secret Scan, Migrations Smoke, Lockfile Drift, Ruff Lint, Mypy Strict).
- Doc reconciliation lands in same sprint.
- Codex high-effort post-sprint verification confirms the 2 CRITICAL + 4 MAJOR findings closed; skip-list items remain explicitly out-of-scope.
- Memory `project_sis_compliance_hardening_2026-05-05.md` updated with completion status and PR numbers.
- Resume Candidate A (SettingsTab extraction sprint) in subsequent session with clean SIS surface.
