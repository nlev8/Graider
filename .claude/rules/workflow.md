# Workflow Discipline — How To Work Here

> **Read this before any multi-task subagent-driven execution.** It complements
> `CLAUDE.md` (project facts) and the `superpowers:*` skills (process guides) by
> codifying the local guardrails that prevent errors CI catches *expensively*
> from being caught cheaply, by you, before you push.
>
> CI is the **final** safety net (nine status checks gate every merge). This
> file is the **first** safety net — the per-task hygiene that keeps a red CI
> run from being your first signal.

---

## Per-Task Checklist (mandatory before marking a task done)

Run through this every time, even on "simple" tasks. The checklist is short
because each item exists because *something burned us before*.

- [ ] **TDD red** — failing test runs and fails for the right reason (not import error, not missing file).
- [ ] **TDD green** — same test runs and passes after the implementation.
- [ ] **`pytest -q --ignore=tests/load`** — FULL backend suite, not just files you named. (Inner-loop tests on named files are fast iteration; full-suite is the gate.)
- [ ] **`grep -rln '<every file you modified>' tests/`** — run any test that mentions your files. Catches cross-cutting consumers (contract tests, golden tests, observability pins).
- [ ] **Line-shift scan** — if you extracted, restructured, or inserted lines anywhere in an existing function, scan for tests that pin line numbers in your files (e.g., `test_sis_alerting`). Update pins explicitly with documenting comments.
- [ ] **Spec reviewer says ✅** — scope compliant: nothing missing, nothing extra. (Always dispatched BEFORE the code-quality reviewer.)
- [ ] **Code-quality reviewer says ✅** — `opus` for Class B (auth / identity / FERPA); `sonnet` is acceptable for Class A.
- [ ] **Reviewer issues handled** — every Minor/Important/Critical issue is either fixed inline OR captured as a tracked follow-up with a fix sketch (per CLAUDE.md Principle #11; never "I'll track it" without the sketch).
- [ ] **Commit scope clean** — only the files this task intentionally touched; no AGENTS.md/CLAUDE.md/handoff.md gitnexus noise, no `.claude/scheduled_tasks.lock`, no `flask_session/`.

---

## Hard Rules (non-negotiable)

1. **"Pre-existing failure" claims require proof.** Format:
   ```bash
   git checkout <base-sha> -- <files-under-test>
   source venv/bin/activate && pytest <failing-test> -v
   ```
   Show the pass/fail output. No proof → it's your failure until proven
   otherwise. (Cost of proof: ~10 seconds. Cost of misclassification: a red PR
   and a debug round-trip.)
2. **`pytest -q` is the floor, not the ceiling.** Per-task named-file pytest is
   for fast iteration; the full suite is the gate before marking done. Defer at
   your peril — Layer 3 catches what scoped review can't see.
3. **Line-shifting refactors require pin-test grep.** Function extraction, block
   restructure, or insertion of lines before existing code may move pinned
   `(file, line)` assertions out of their window. `grep -rn '"<your_file>"' tests/`
   and verify every pin still finds the intended capture.
4. **Class B ⇒ opus code-quality reviewer.** Mandatory, not optional. (Class B =
   auth / identity / FERPA right-to-delete / billing / anything outward-facing
   that's hard to roll back.)
5. **Subagent reports are evidence-bearing or rejected.** Actual stdout tails
   (test counts, lint output, build line). "All green" without numbers is not
   evidence — it's a vibe.
6. **Spec compliance review precedes code-quality review.** Always. A code that
   doesn't match the spec isn't worth reviewing for quality.
7. **No `gh pr merge --auto` with a review in flight on a Class B PR.** Per
   CLAUDE.md Principle #13: for Class B, merge manually AFTER the review returns
   clean.
8. **Pre-deploy verification ≠ deploy verification.** A green CI run + a green
   reviewer says "the code in this branch is correct against the cases we
   imagined." It does NOT say "the deployed system works against the live
   third-party tenant." For any change to an external-IO path (SIS / SSO /
   payment / LMS), the per-branch DoD is not met until an *operator* has
   re-executed the originally-failing user flow against the deployed image
   and reported the observable outcome. CI + reviewers cannot do this for you.
9. **Generic wrapper-exception classes are not root-cause evidence.** When
   the failing exception is `*ConnectionError`, `*WrapperError`, `*Error`,
   or any class the library uses as an umbrella for multiple underlying
   failure modes, you MUST read the wrapped `err:` / `__cause__` payload
   before designing the fix. Class names alone are vibes, not evidence.
   Reproduce locally with the smallest possible client (raw `urllib`, raw
   `httpx`, `curl`) and inspect the actual HTTP status / exception args /
   network-layer error before patching. (See `Lessons From Incidents`
   2026-05-28 for the cost of skipping this — a clean-CI, clean-review fix
   that didn't fix anything.)
10. **OIDC `require` lists cite the spec.** Any entry in a `pyjwt.decode(...
    options={"require": [...]})` (or equivalent in another JWT library) MUST
    be either:
    (a) an OIDC Core §2 *REQUIRED* id_token claim — `iss`, `sub`, `aud`,
        `exp`, `iat`, plus `nonce` when the relying party sent one — OR
    (b) accompanied by an inline comment citing the spec section / RFC
        clause that justifies the additional requirement (e.g., a tenant
        contract that mandates a non-standard claim).
    Anything else is over-strict and will reject standards-compliant tokens
    from any IdP that follows the spec literally. (See `Lessons From
    Incidents` 2026-05-28 follow-up — `MissingRequiredClaimError: Token is
    missing the "nbf" claim` blocked 100 % of ClassLink SSO because we
    over-required `nbf`, which is optional per OIDC Core §2.) The
    distinction between "require to be PRESENT" (`options["require"]`) and
    "verify when PRESENT" (`options["verify_*"]`) is load-bearing: most JWT
    libraries verify-when-present by default; demanding presence is a
    separate, stricter choice that needs its own justification.

---

## Anti-Patterns (the red-flag table)

These thoughts mean STOP and re-check:

| Thought | Reality |
|---|---|
| "This failure is pre-existing on main" (no proof shown) | It's yours until proven otherwise — proof takes 10 seconds. |
| "All tests in `{named files}` pass" | ≠ "all tests pass." Cross-cutting consumers stay invisible. |
| "The reviewer approved, ship it" | Reviewer reviewed the diff, not the full-suite impact. Run `pytest -q` anyway. |
| "Subagent says DONE, mark complete" | Spot-check the load-bearing claim. Did the test actually run? What were the counts? |
| "Refactor was behavior-preserving" | Line numbers are part of behavior to tests that pin them. |
| "Small follow-up — I'll file an issue" | If it's <15 min in this PR's scope, fix it now. Otherwise file WITH a fix sketch. |
| "Mock makes the test pass" | Did the mock prove behavior or just suppress the error? |
| "It's a `*ConnectionError`, so it's a network/TLS issue" | The class is generic. Read the wrapped `err:` payload — HTTP 401 wraps the same way. |
| "Green CI proves the fix works in prod" | CI proves the *code* matches your test imagination. Prod against a live external tenant proves nothing about CI. Re-test the original user flow against the deploy. |
| "Adding a claim to `require` is harmless defense-in-depth" | `require` is "must be PRESENT", not "verify when present". Anything beyond OIDC Core §2's required set rejects spec-compliant tokens. Use `verify_*` for verification; cite the spec for any extra `require` entry. |
| "Code-quality reviewer ran — done" | Spec compliance review must come FIRST. |
| "I'll just commit the noise this once" | The gitnexus stats / lock files / flask_session noise is NEVER part of a feature commit. |
| "CI will catch it" | CI is the *final* safety net. Catching it locally is ~100x faster + cheaper. |

---

## Verification Loop (the 4 layers)

```
Layer 1 — per-step (inside a task)
  red → green → commit, with actual test output shown

Layer 2 — per-task (subagent loop)
  implementer → spec reviewer → code-quality reviewer → fix loop → mark done
  (Always spec FIRST, then quality. Never quality first.)

Layer 3 — per-task verification gates  ← THE LAYER MOST OFTEN SKIPPED
  pytest -q --ignore=tests/load
  grep -rln '<modified files>' tests/
  pin-test scan if line numbers shifted
  ⇒ catches cross-cutting failures that scoped per-task review cannot see

Layer 4 — per-branch (pre-push)
  final whole-branch code review (opus for Class B)
  local CI mirror: pytest -q + ruff + bandit + frontend test + frontend build
  GitNexus reindex
  evidence ledger in PR body
```

**Layer 3 is the layer that would have caught the SIS_CAPTURES incident in T3,
not T9.** Don't skip it. The cost is seconds; the savings is a CI round-trip.

---

## Universal Definition of Done

### Per task

A task is **DONE** only when ALL of these are true:

1. All TDD steps in the plan are checked off with shown green test output.
2. Full `pytest -q --ignore=tests/load` is green (or any failure is *proven* pre-existing via the Hard Rule #1 protocol).
3. Every test file that `grep -rln '<modified file>' tests/` surfaces is green.
4. If lines shifted in any modified file: pin-test scan run, results clean.
5. Spec reviewer: ✅ (scope compliant, nothing missing, nothing extra).
6. Code-quality reviewer: ✅ (opus for Class B).
7. Every reviewer issue: fixed OR tracked with a fix sketch.
8. Only the task's intended files in the commit (no noise, no scope creep).
9. Working tree clean of unrelated modifications relative to the commit being made.

### Per branch (before push / before opening PR)

1. Every task's per-task DoD is met.
2. Final whole-branch code review (opus for Class B).
3. Local CI mirror passes:
   - `source venv/bin/activate && pytest -q --ignore=tests/load`
   - `ruff check backend/ tests/` (or just on changed files for fast)
   - `bandit -q -r <files-you-changed>`
   - `cd frontend && npx vitest run`
   - `cd frontend && npm run build`
   - Alembic migrations smoke if any migration file changed
   - Mypy strict on critical modules if any of those changed
4. GitNexus index refreshed: `npx gitnexus analyze --embeddings`.
5. PR classification (A vs B) is called out explicitly in the PR body.
6. PR body includes: spec ref, plan ref, the test commands the reviewer can
   run to verify, list of known follow-ups (with severity).
7. Branch protection respected — no admin bypass without explicit, documented
   reason.
8. **Class B specifically:** no `gh pr merge --auto` until review returns clean.

---

## Class A vs Class B (CLAUDE.md Principle #13 reference)

| Class | What it means | Review posture |
|---|---|---|
| **A** — behavior-preserving refactor | Golden net (results) + prompt-snapshot net (wording) + AST byte-identity vs `main` prove behavior is unchanged. | Green CI ≈ provably correct → squash-auto-merge on green is earned. |
| **B** — net-new behavior OR compliance/security/FERPA | Green CI only covers cases you imagined to test. | Code review is a HARD pre-gate. **Create PR → review → fix to clean → THEN merge manually.** No auto-merge with review in flight. |

The tell that forces the classification: **"am I adding logic, or just moving
it?"** Adding/changing logic (especially regexes, scoring, redaction, auth) ⇒
Class B. Moving code verbatim ⇒ Class A.

---

## How This File Integrates With Existing Process

| Layer | Source | This file's role |
|---|---|---|
| Project facts | `CLAUDE.md` | Pointer at top — points readers here. |
| Universal preferences | `~/.claude/CLAUDE.md` | Complementary; this file is project-scoped. |
| Process skills | `superpowers:brainstorming`, `superpowers:writing-plans`, `superpowers:subagent-driven-development`, etc. | This file *enforces* the verification gates those skills assume but don't always check. |
| Subagent dispatch | controller-authored prompts | Include `Read .claude/rules/workflow.md before starting` in every dispatch prompt for multi-task work. |
| CI | `.github/workflows/ci.yml` (9 status checks) | This file's gates *mirror* CI locally so you catch fast, not slow. |

---

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
