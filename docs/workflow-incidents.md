# Workflow Incidents — The Changelog of Pain

> Extracted from `.claude/rules/workflow.md` so this audit trail no longer loads into per-turn
> agent memory (it is reference material — read it on demand). The *actionable* rules these
> incidents produced still live in workflow.md's **Hard Rules** and **Anti-Patterns** sections;
> Hard Rules #8/#9/#10 cite these entries by date. When you add a new incident here (newest
> first), also add the rule it produced to workflow.md.

## Lessons From Incidents (the changelog of pain)

Each entry: date, one-sentence summary, root cause, rule(s) the entry produced.

### 2026-05-28 (follow-up) — Over-strict `require` list rejected standards-compliant id_tokens

**What happened.** PR #595 deployed `7917bb3` to prod at `05:23 UTC`. Operator
ran the live ClassLink SSO test against the deployed image (Hard Rule #8 — the
very rule we'd just added). SSO still failed with the same surface symptom
`oidc_invalid`. **But** within minutes Better Stack surfaced the wrapped
payload from the new Sentry capture commit `8c3cd25` added (Recommendation #1
from the opus reviewer on #595):

```
MissingRequiredClaimError: Token is missing the "nbf" claim
```

Rule #9 working as designed — the wrapped payload, not the umbrella class name,
was the diagnostic.

**Root cause.** `classlink_callback` called `pyjwt.decode(...)` with
`options={"require": ["iat", "nbf", "exp", "iss", "aud", "sub"], ...}`. The
`require` list is "must be PRESENT to accept", not "verify when present".
Real ClassLink id_tokens omit `nbf`. [OIDC Core §2](https://openid.net/specs/openid-connect-core-1_0.html#IDToken)
lists the REQUIRED id_token claims as `iss, sub, aud, exp, iat` (+ `nonce`
when the RP sent one); `nbf` is OPTIONAL. We were over-requiring `nbf` as
defense-in-depth without checking the spec — that over-strictness blocked
100 % of ClassLink tokens.

**The distinction the previous fix missed.** pyjwt has TWO separate concepts:
- `options["require"]` — claims that MUST be PRESENT (else
  `MissingRequiredClaimError`).
- `options["verify_*"]` (e.g., `verify_nbf`, `verify_exp`) — claims that, when
  present, MUST be VALID (else `ImmatureSignatureError`, `ExpiredSignatureError`,
  etc.).

The two are not interchangeable. `verify_nbf` defaults to `True`, so removing
`nbf` from `require` is a PRESENCE relaxation only — tokens that include `nbf`
still get rejected if their `nbf` is in the future. The new test
`test_callback_rejects_immature_nbf` (`tests/test_classlink_sso.py`) pins
that property so the security argument cannot regress silently.

**Why this was the second `oidc_invalid` fix in 24 hours.** PR #594
misdiagnosed (Rule #9: wrapper class read as load-bearing). PR #595 fixed
the JWKS-fetch leg correctly (real WAF UA filter) and added Rule #9 itself.
But the operator-validation step on #595 surfaced a SECOND, independent
failure mode (Rule #8: green CI ≠ green deploy) because we'd never run a
real ClassLink id_token through our `pyjwt.decode` call. The two-PR loop
isn't a process failure — it's exactly the loop Rules #8 + #9 prescribe.
The cost was ~30 minutes of one operator's evening to drive the live tests.

**Rule produced.** Added to the Hard Rules section above as **Rule #10**:
> OIDC `require` lists cite the spec. Anything beyond `iss/sub/aud/exp/iat`
> (+ `nonce` when sent) MUST come with an inline comment citing the RFC /
> spec section that justifies the extra requirement.

**Operational follow-up.** Hotfix PR (the one this entry ships in) drops
`"nbf"` from the `require` list. Filed follow-up issue (link TBD) for a
broader OIDC-conformance audit of the other JWT-decoding paths in the
codebase (Clever, LTI 1.3) — diff sketch included in the issue body per
CLAUDE.md Principle #11.

**Outcome / lesson cost.** Two ClassLink SSO PRs (#595 and #596) shipped
in ~6 hours total, both clean-CI + clean-review at merge. The operator
validation step caught the residual failure both times. Rules #8 + #9 +
the new #10 should make the next `oidc_invalid` debug session a single PR
with no surprise residual.

### 2026-05-28 — Generic-wrapper-exception misdiagnosis (#594 didn't fix ClassLink SSO)

**What happened.** Production ClassLink SSO failed with `oidc_invalid`. Railway
logs showed:
```
backend.routes.classlink_routes WARNING: ClassLink id_token validation failed: PyJWKClientConnectionError
```
PR #594 inferred from the class name `PyJWKClientConnectionError` plus the
fact that the discovery doc fetched OK via httpx (~17ms before the JWKS fetch
failed via urllib) that the root cause was a CA-bundle mismatch — httpx uses
certifi by default, urllib uses the OS bundle, and the Railway nixpacks image's
OS bundle was assumed to be missing intermediates. Fix shipped: pass an explicit
certifi-backed `ssl_context` to `PyJWKClient`. CI green, deploy succeeded, SSO
**still failed identically**.

The actual root cause: ClassLink's WAF returns **HTTP 401** specifically when
the request's `User-Agent` header matches `Python-urllib/X.Y` (urllib's default).
Every other UA — empty, `Mozilla/5.0`, `curl/8.0`, any custom string, the
implicit `python-httpx/<ver>` httpx sets — returns 200. PyJWKClient uses
urllib internally (not httpx), so its requests got rejected, and pyjwt wrapped
the resulting `HTTPError(401)` in `PyJWKClientConnectionError` — the **same
class** it would use for a TLS error, a DNS error, a connection reset, anything.
The wrapped `err:` payload in the Railway log would have read
`"HTTP Error 401: Unauthorized"` — and that single string would have ruled out
the CA-bundle hypothesis instantly.

**Root cause of the misdiagnosis.** Reading the exception **class name** as
load-bearing signal when the class is in fact a generic wrapper. `PyJWKClientConnectionError`
is to pyjwt what `requests.exceptions.RequestException` is to requests —
a catch-all umbrella. Inferring root cause from the umbrella, without reading
the wrapped `err:` payload, is how you ship a "fix" that doesn't fix anything.

The certifi context isn't harmful (it's a legitimate defensive belt for image
CA-bundle drift) — but it wasn't the load-bearing change. Kept in the
follow-up fix; documented as "defensive, not load-bearing" both in code
comments and in the test docstrings, so the next person reading
`backend/services/classlink_oidc.py` sees the actual history.

**Rule produced.** Added to the Hard Rules section above:

> **9. Generic wrapper-exception classes are not root-cause evidence.** When
> the failing exception is `*ConnectionError`, `*WrapperError`, `*Error`, or
> any class that the library uses as a catch-all for multiple underlying
> failure modes, you MUST read the wrapped `err:` / `__cause__` payload
> before designing the fix. Class names alone are vibes, not evidence.
> Reproduce locally with the smallest possible client (raw `urllib`, raw
> `httpx`, `curl`) and inspect the actual HTTP status, exception args, or
> network-layer error before patching.

**Operational follow-up.** Hotfix PR (the one this entry ships in)
adds an explicit `headers={"User-Agent": "Graider/1.0 ..."}` kwarg to
`PyJWKClient(...)`. New test
`test_jwks_client_sets_non_python_urllib_user_agent` asserts the kwarg
is present AND the UA does not start with `Python-urllib`. Operator
validation post-merge: rostered ClassLink student logs into test tenant
LaunchPad and clicks the Graider tile; should land at `/student` (or
`/student?classlink_select=…`) instead of `/?classlink_error=oidc_invalid`.

**Outcome / lesson cost.** Cost of misdiagnosis: PR #594 shipped (clean
CI, clean review), Railway deployed, SSO stayed broken in production
overnight. Cost of applying the rule next time: ~30 seconds to read the
wrapped err payload from logs. The asymmetry is the whole point of
codifying the rule.

### 2026-05-26 — PR opened with auto-merge armed never triggered CI

**What happened.** Opened PR #591 (Class A docs — handoff rewrite) targeting `main`,
armed `gh pr merge --auto --squash` immediately. CI never started. The PR sat at
`mergeStateStatus: BLOCKED` for 9+ minutes with zero workflow runs in the GitHub
Actions API for the head SHA. Tried an empty-commit retrigger
(`git commit --allow-empty`); the new SHA *also* got zero runs after another wait.
Other workflow events on the repo (scheduled periodic-sync, nightly E2E) ran fine
in the same window — so it wasn't a repo-wide Actions outage. Eventually closed +
reopened the PR via `gh pr close 591 && gh pr reopen 591`; this fired the
`pull_request` event freshly and CI immediately picked up the same SHA. Auto-merge
had to be re-armed (closing clears it). PR landed at `f418f82`.

**Cause (GitHub side, not our discipline).** The combination of *(opening a PR)* and
*(arming auto-merge moments later, before GitHub had finished initial CI dispatch
for the PR)* appears to leave the PR in a state where the `pull_request` workflow
trigger is dropped silently. The workflow file's `on: pull_request: branches: [main]`
config is correct; the workflow file is unchanged from PRs that ran normally. The
only thing visibly different was the timing of the auto-merge arming.

**Runbook (this entry itself — the workflow rulebook's Anti-Patterns table is
for red-flag *thoughts*, not operational GitHub-edge-case fixes):**
- If a PR is `BLOCKED` with **zero** runs in `gh api .../actions/runs?head_sha=…`
  after 2-3 minutes despite a valid `pull_request` trigger:
  1. **First try:** `gh pr close <n> && gh pr reopen <n>`. Re-arm auto-merge after
     reopen (closing clears it).
  2. **Do NOT bother** with `git commit --allow-empty && git push` to retrigger —
     it didn't help here. (Documented so the next agent skips that step.)
  3. **Last resort** for genuinely-stuck Class A docs PRs: `gh pr merge --admin`.
     Never for Class B.

**Outcome.** Lesson costs ~30 seconds to apply next time it surfaces. Cost of NOT
having this codified: 15 minutes of speculative debugging during the next agent's
session, since the symptom (CI never fired) is easy to misattribute to repo
configuration or workflow-file bugs.

### 2026-05-25 — SIS_CAPTURES pin misclassification

**What happened.** Tasks 3 and 4 of the ClassLink Roster Server cert-parity
branch shifted line numbers in `backend/routes/classlink_routes.py` and
`backend/roster_sync.py`. The cross-cutting test
`tests/test_sis_alerting.py::test_every_flagged_sis_catch_captures_to_sentry`
pins `(file, line)` tuples in those files and broke when the captures moved
outside the window=8 search range. The T9 cleanup subagent ran the full suite,
saw the failure, and reported it as *"fails identically on main"* — which the
controller almost accepted at face value. (Verified by manual spot-check that
it was actually introduced by Tasks 3 and 4.) A subsequent fix subagent
re-pointed one pin to the wrong meaning (line 223 covers
`_create_classlink_student_session`'s capture, not `_bg_sync`'s). The final
whole-branch review caught the meaning-drift; the real fix landed two commits
later.

**Root causes (three layers).**

1. **Per-task verification scope was too narrow.** Spec and code-quality
   reviewers ran only the test files I named in their dispatch prompts. The SIS
   alerting test wasn't named in T3 or T4 because nothing in those tasks' diffs
   referenced it — but it pinned line numbers in files those tasks shifted.
   Cross-cutting consumers are invisible to scoped review.
2. **No "pre-existing failure" verification protocol.** The cleanup subagent's
   "fails identically on main" claim was accepted on instinct rather than on
   evidence. The proof (`git checkout <base> -- <files>; pytest <test>`) takes
   10 seconds.
3. **Full-suite gate deferred to T9.** A line-shift regression caught in T3 or
   T4 would have been a 2-minute fix; caught in T9 it required a debug detour
   plus a pin-meaning correction.

**Rules added (codified above):**
- Hard Rule #1: "Pre-existing failure" claims require `git checkout <base>` proof.
- Hard Rule #2: `pytest -q` is the floor for per-task verification, not the ceiling.
- Hard Rule #3: Line-shifting refactors require pin-test grep.
- Per-Task Checklist items 3, 4, 5 (full-suite, grep for cross-cutting, line-shift scan).
- Anti-pattern table: "This failure is pre-existing on main" and "All tests in
  `{named files}` pass."

**Outcome.** The PR (#588) shipped clean. The lesson costs one extra checklist
step on every future task; the missed catch would cost a red PR every time a
refactor shifts a pinned line.

---

*Add new incident entries above this footer, newest first. Keep each entry short
— the rules go in the body above; this section is the audit trail.*
