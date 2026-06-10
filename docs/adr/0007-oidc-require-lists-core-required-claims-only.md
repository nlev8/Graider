# ADR 0007 — OIDC `require` lists may contain only OIDC Core §2 REQUIRED claims

- **Status:** Accepted (born from the 2026-05-28 ClassLink SSO outage)
- **Date recorded:** 2026-06-10 (rule adopted 2026-05-28)

## Context

On 2026-05-28, 100% of ClassLink SSO logins failed with `oidc_invalid`. Root
cause: our `pyjwt.decode(..., options={"require": [...]})` list demanded an
`nbf` claim. `nbf` is *optional* per OIDC Core §2 — ClassLink's
standards-compliant id_tokens simply omit it, and pyjwt raised
`MissingRequiredClaimError: Token is missing the "nbf" claim` for every
login. The over-requirement had read as "harmless defense-in-depth."

The load-bearing distinction: `options["require"]` means **must be
PRESENT**; `options["verify_*"]` means **verify when present** (the library
default). Demanding presence is a strictly stronger, separate choice.

## Decision

Any entry in a JWT `require` list MUST be either:

(a) an OIDC Core §2 REQUIRED id_token claim — `iss`, `sub`, `aud`, `exp`,
    `iat` (plus `nonce` when the relying party sent one) — OR
(b) accompanied by an inline comment citing the spec section / RFC clause /
    tenant contract that justifies the extra requirement.

Verification of optional claims (`nbf`, etc.) is done via `verify_*`
options, which validate the claim *when present* without rejecting
spec-compliant tokens that omit it.

The rule is enforced two ways:

- **Workflow:** `.claude/rules/workflow.md` Hard Rule #10 (with the
  anti-pattern entry "Adding a claim to `require` is harmless
  defense-in-depth").
- **Code:** a conformance test (`tests/test_oidc_require_conformance.py`)
  scans every OIDC `require` list in the backend and fails if any list is
  not exactly the OIDC Core required set (and specifically that none
  demands `nbf`).

## Consequences

- Both live `require` lists conform: `backend/lti.py` (LTI 1.3 launch) and
  `backend/routes/classlink_routes.py` (ClassLink OIDC) require exactly
  `iss, sub, aud, exp, iat`.
- Future IdP integrations inherit the rule for free via the conformance
  test — an over-strict list is a red CI, not a production outage.
- Tenants that genuinely mandate a non-standard claim can still be served,
  but the justification must be written at the call site (option (b)).

## Evidence

- `docs/workflow-incidents.md` — "2026-05-28 (follow-up) — Over-strict
  `require` list rejected standards-compliant id_tokens"
- `.claude/rules/workflow.md` Hard Rule #10
- `backend/lti.py` (`require": ["iss", "sub", "aud", "exp", "iat"]`),
  `backend/routes/classlink_routes.py` (same set)
- `tests/test_oidc_require_conformance.py`
