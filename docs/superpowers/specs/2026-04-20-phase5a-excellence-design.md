# Phase 5a — Excellence Tier (First Slice) Design

**Date:** 2026-04-20
**Status:** Specified, awaiting user review then implementation plan
**Review history:** Brainstorm → Codex round-1 review (swapped pybreaker for LLM adapter) → Codex round-2 review (revised adapter shape, split PRs, added missing items) → this document
**Supersedes:** Phase 5 roadmap item list in `memory/project_codebase_improvement_roadmap.md` (that list is preserved for future phases, but Phase 5a picks 4 of the 10 items)

---

## Goal

Close a measurable subset of the Phase 5 excellence-tier quality gap by shipping seven small-to-medium PRs. Each PR is independently reviewable, revertable, and improves one or two specific dimensions without structural upheaval. Clever/ClassLink/OneRoster contracts are NOT touched.

**Dimensions targeted:** Security (→8), Error handling (→7.5), Observability (→9), Operational safety (→9), Code quality (→6.5).

**Non-goal:** reaching the 9+/9 "excellence" average in a single phase. Remaining Phase 5 items (mypy strict, Pydantic migration, APM tracing, circuit breakers, RFC 7807, OpenAPI, mutmut) are deferred to Phase 5b and later.

---

## Scope — what's IN and what's OUT

**In Phase 5a (7 PRs):**

| PR | Item | Primary dimension(s) |
|---|---|---|
| A | Bandit + trufflehog in CI + README coverage-floor fix | Security |
| B1 | Dependency ownership audit (clean up runtime/dev mixing, dual Gemini SDKs, `py2app` placement) | Code quality |
| B2 | pip-tools lockfile workflow + drift-check CI job + `docs/dependencies.md` | Security, Data integrity |
| C1 | Logging payload contract (formatter strategy decision + tests) | Observability |
| C2 | `print()` migration in runtime paths + Ruff T20 lint rule + explicit allow-list for CLI/protocol/test-harness prints | Observability |
| D1 | LLM provider adapter for **non-streaming** call sites (~22 sites) | Error handling, Operational safety |
| D2 | LLM adapter extension for **streaming/tool-use** in `assistant_routes` (~8 sites) | Error handling, Operational safety |

**Explicitly deferred to Phase 5b:**
- Circuit breakers (`pybreaker`) layered onto the D1/D2 adapter seam
- Gemini image generation in `backend/services/slide_generator.py` — uses the separate `google.genai` SDK, not chat-shaped
- OpenAI TTS in `backend/services/openai_tts_service.py` — also not chat-shaped
- APM tracing enablement (requires Sentry billing decision)

**Explicitly deferred to later phases:**
- Mypy strict on critical modules
- Pydantic models for API payloads and Supabase records
- RFC 7807 error responses
- OpenAPI/Swagger generation
- Mutation testing (mutmut)

---

## Current-state inventory (verified 2026-04-20)

**Already exists (don't re-build):**
- `JsonFormatter` at `backend/utils/logging_utils.py:21-43` — production JSON logging bootstrap in `backend/app.py:183-185`. **However, the formatter serializes only `timestamp`, `level`, `logger`, `request_id`, `message`, and optional `exception` — `extra={...}` fields are dropped.** This is why `backend/observability/db_mode.py:63-75` uses JSON-in-message instead.
- Retry primitive `with_retry()` at `backend/retry.py:100-167` with status/keyword classification.
- Token/cost accounting for planner and assistant at `backend/services/assignment_post_processing.py:23-40` and `backend/routes/assistant_routes.py:1070-1135`, `1853-1861`.
- Slow-request timing at `backend/utils/logging_utils.py:46-96`.
- CI safety rail: `--cov-fail-under=32` in `.github/workflows/ci.yml:40-50`. README states 40% — stale.

**`print()` inventory (160 calls across 18 backend files):**

Top four hotspots:
- `backend/grading/pipeline.py` — 28 calls (lines 183, 215, 217, 222, 225, 239, 777-780, 800-801, 861, 864, 923, 926, 942, 944, 953, 976, 994, 1007, 1020, 1028, 1161, 1197, 1200, 1205, 1215)
- `backend/services/email_service.py` — 22 calls (lines 23, 85, 103, 107, 127, 130, 134, 150, 192, 228-231, 238, 242, 248, 279-281, 290, 294, 296)
- `backend/app.py` — 21 calls (lines 187, 193, 203, 231, 275, 348, 630, 690, 745, 1271, 1495, 1908-1917)
- `backend/routes/planner_routes.py` — 12 calls (lines 102, 480, 572, 794, 1289, 1945, 2318, 2320, 2499, 3725, 4244, 5098)

Print classes (for C2 allow-list):
- **Runtime request-path prints** — migrate to logger
- **Startup banner prints** in `backend/app.py:1908-1917` — migrate to logger at INFO level
- **CLI / setup / test-harness prints** in `backend/services/email_service.py:262-299`, `backend/services/visualization.py:1164-1195` — keep
- **Subprocess-protocol prints** in `backend/services/outlook_sender.py:17-18,36-38` (emits JSON lines to stdout as an IPC channel) — **MUST keep**, breaking this breaks the subprocess handshake
- **Hard-fail CLI errors to stderr** in `backend/migrations/env.py:29-35,77-82` — keep

**Direct LLM provider invocation sites (30 total, for D1/D2 migration):**

- `backend/routes/planner_routes.py` — 14 sites (464, 556, 775, 1209, 1252, 1539, 1916, 4196, 5072, 5210, 5318, 5414, 5527, 5789)
- `backend/routes/assistant_routes.py` — 3 sites (1461, 1508, 1620) — streaming/tool-use, all D2
- `backend/app.py` — 2 sites (1560, 1626)
- Single-call files (13 sites total, all D1):
  - `backend/routes/assignment_routes.py:148`
  - `backend/routes/assignment_player_routes.py:344`
  - `backend/routes/grading_routes.py:768`
  - `backend/routes/lesson_routes.py:463`
  - `backend/services/grading_service.py:235`
  - `backend/services/assistant_tools_behavior.py:599`
  - `backend/services/assistant_tools_ai.py:123`
  - `backend/services/seo_service.py:38`
  - `backend/services/assignment_post_processing.py:1929`
  - `backend/services/slide_generator.py:155, 258` — **excluded from Phase 5a** (image gen, not chat)

---

## PR A — Bandit + trufflehog in CI

**Goal:** block secret leaks and security anti-patterns in PRs before they land on main.

**Changes:**
- New file `.github/workflows/security-scan.yml`.
- New file `.bandit.yaml` baseline at repo root.
- Update `README.md` coverage-floor reference from 40% to 32% (same PR — trivial doc fix).

**Bandit config:**
- Scan root: `backend/` (NOT `backend/scripts/`, NOT `backend/migrations/`).
- Severity floor: `-l` plus `-iii` (skip low severity, skip anything below HIGH confidence). Effective: medium+ severity AND high confidence only.
- Baseline file `.bandit.yaml` allow-lists pre-existing findings to produce a clean green signal on day 1.
- **Baseline governance:** two-line comment at top of `.bandit.yaml` states the allow-list review cadence ("review quarterly" or "every phase-N plan") and the refresh command (`bandit -r backend/ --exclude ... -o .bandit.yaml -f yaml --baseline`). Without governance, the baseline becomes permanent debt concealment.

**trufflehog config:**
- Uses `trufflesecurity/trufflehog@main` action.
- **Explicit base-SHA fetch step** before the scan: the current `actions/checkout@v4` in `.github/workflows/ci.yml:25` uses default shallow depth, which breaks `--since-commit` diff mode. Add `fetch-depth: 0` OR a targeted `git fetch origin $BASE_SHA` step.
- `--only-verified` mode (confirmed secrets only, verified by probing the provider).
- Scan scope: PR diff range `$BASE..$HEAD`, NOT full history.
- Failure action: block merge.

**Triggers:** `pull_request` against main AND `push` to main (so a direct-to-main hotfix also gets scanned).

**Out of scope:** pre-commit hooks, SaaS SAST (Snyk/Semgrep Cloud), automated secret rotation.

**Test plan:**
- Verify workflow runs on a PR with a test benign change.
- Verify workflow FAILS on a test PR that adds a known verified secret pattern (revert immediately).
- Verify Bandit ignores files outside `backend/`.

---

## PR B1 — Dependency ownership audit

**Goal:** separate runtime from non-runtime tooling before pip-compile freezes the current mess into a lockfile. Codex's review flagged: `py2app` (Mac packaging), `pytest-cov`, `playwright`, `selenium`, dual Gemini SDKs all currently co-mingled in `requirements.txt`.

**Changes:**
- Move out of `requirements.txt` into `requirements-dev.txt`:
  - `pytest-cov` (currently in main, also installed ad-hoc in `.github/workflows/ci.yml:33-38`)
  - `py2app` (Mac packaging, never loaded at runtime)
  - `playwright`, `selenium` (E2E testing, never hit by gunicorn)
- Remove the ad-hoc `pip install pytest-cov` from `ci.yml:33-38` once it's in dev requirements.
- Dual Gemini SDK decision: keep both (`google-generativeai` for chat and `google.genai` for slide image gen) but document in a comment at the top of `requirements.txt` WHY both are needed. Phase 5b can unify after slide-generator migration.

**Test plan:**
- `pip install -r requirements.txt` followed by running the app in isolation should succeed.
- `pip install -r requirements-dev.txt` must pull pytest-cov, playwright, selenium, py2app.
- CI `backend-tests` job still passes with the `pytest-cov` install step removed (because dev requirements now include it).

**Out of scope:** actual lockfile generation (that's B2).

---

## PR B2 — pip-tools lockfile workflow

**Goal:** reproducible, hash-verified dependency installs. Prevent silent CVE drift.

**Changes:**
- Rename `requirements.txt` → `requirements.in`. Same for dev. `requirements.in` is the loose human-edited input (what B1 produced).
- Generate `requirements.txt` via `pip-compile --generate-hashes requirements.in`. Commit both.
- Generate `requirements-dev.txt` via `pip-compile --generate-hashes requirements-dev.in`. Commit both.
- Update `.github/workflows/ci.yml` install steps to use `pip install --require-hashes -r requirements.txt` and `-r requirements-dev.txt`.
- New CI job `lockfile-drift-check`: runs `pip-compile --dry-run requirements.in && pip-compile --dry-run requirements-dev.in`, fails if non-empty diff. Prevents `.in` edits without a corresponding `.txt` refresh.
- New doc `docs/dependencies.md` — add a package, upgrade a package, resolve conflicts, regenerate locally, handle hash mismatches.

**Budget:** 3-4 days realistic (Codex-revised upward from my half-day guess). The first compile will surface resolver conflicts given dual Gemini SDKs + Playwright + Selenium + py2app + supabase + anthropic + openai all interacting.

**Rollback:** revert the PR. `requirements.in`/`requirements.txt` go back to the single pre-split `requirements.txt`.

**Test plan:**
- Fresh venv: `pip install --require-hashes -r requirements.txt -r requirements-dev.txt` succeeds.
- `pytest` full suite passes on the locked deps.
- `lockfile-drift-check` fails when .in is edited without regenerating .txt.

---

## PR C1 — Logging payload contract

**Goal:** decide how structured-event logs are serialized so C2's migration can produce machine-parsable output. Blocks C2 and D1's metrics emission.

**Decision required:** one of two options, documented in `backend/utils/logging_utils.py` module docstring:

1. **Extend `JsonFormatter` to serialize selected extras.** Add a class-level `EXTRA_ALLOW` set; when `extra={...}` fields are in that set, include them in the JSON output. Adds formatter complexity but preserves standard `logger.info(msg, extra={...})` ergonomics.

2. **Standardize on JSON-in-message for structured events.** Keep `JsonFormatter` narrow; use the `backend/observability/db_mode.py:63-75` pattern (`logger.info(json.dumps(event))`) for machine-parsed events; reserve `logger.info/warning/exception` for human-readable text.

**Recommendation: option 2** (JSON-in-message). Reasons:
- Already working in production for `request.db_mode` events.
- Zero formatter changes — lowest risk.
- Keeps a clean mental model: human messages go via `logger.X(msg)`, machine events go via `logger.X(json.dumps(event))`.
- Trivial to parse in BetterStack.

Option 1 would be justified if we had many independent event types each needing different keys. Today we have ~2 (db_mode, future llm.call.*).

**Changes in C1:**
- Add a helper `backend/observability/events.py` exposing `emit(event_name: str, level: str = "info", **fields)` that wraps `logger.log(level, json.dumps({...}))` with `event_name` as a top-level key.
- Update `backend/observability/db_mode.py` to use the helper (refactor, no behavior change).
- Add tests verifying the helper's output shape.
- Document the convention in `docs/observability.md`.

**Test plan:**
- Unit test: `emit('llm.call.start', model='gpt-4', tokens=0)` produces a JSON line with `event='llm.call.start'`, `model='gpt-4'`, `tokens=0`, plus standard `timestamp`, `level`, `logger`, `request_id` from the existing formatter.
- Unit test: `db_mode` refactor produces byte-identical output to pre-refactor (snapshot test).

**Out of scope:** migrating any `print()` call (that's C2). Extending `JsonFormatter` (option 1 was not chosen).

---

## PR C2 — `print()` migration + Ruff T20 lint rule

**Goal:** remove noisy unstructured `print()` from production paths; block future regressions with linting.

**Scope:** 160 `print()` calls across 18 backend files. Migration classified by print type:

| Class | Action | Examples |
|---|---|---|
| Runtime request-path | Migrate to `logger.X(msg)` | `backend/grading/pipeline.py:215-1215`, `backend/routes/planner_routes.py:480-5098` |
| Startup banners | Migrate to `logger.info(msg)` | `backend/app.py:187-203`, `backend/app.py:1908-1917` |
| CLI / setup / test-harness | Keep + add to allow-list | `backend/services/email_service.py:262-299`, `backend/services/visualization.py:1164-1195` |
| Subprocess-protocol (IPC) | Keep + add to allow-list | `backend/services/outlook_sender.py:17-18,36-38` |
| Hard-fail stderr | Keep + add to allow-list | `backend/migrations/env.py:29-35,77-82` |

**Changes:**
- Migration of all runtime and startup-banner prints to `logger.X(msg)`. Level inferred from content (success→info, deprecation→warning, failure→error).
- For events with structured fields (usage stats, cost data), use C1's `emit()` helper instead of `logger.info`.
- Add `ruff` to `requirements-dev.in` (this is the first Ruff addition to the repo; B2's lockfile must regenerate on this PR).
- New `pyproject.toml` entries:
  ```toml
  [tool.ruff]
  lint.select = ["T20"]  # flake8-print
  lint.per-file-ignores = {
    "backend/services/email_service.py" = ["T20"],
    "backend/services/visualization.py" = ["T20"],
    "backend/services/outlook_sender.py" = ["T20"],
    "backend/migrations/env.py" = ["T20"],
    "backend/scripts/**" = ["T20"],
  }
  ```
- New CI job `ruff-lint` runs `ruff check backend/`.

**Test plan:**
- Full test suite passes.
- `ruff check backend/` returns zero findings.
- `ruff check` FAILS if a test PR adds a new `print()` in a non-allow-listed file.
- BetterStack log pipeline ingests the new JSON lines correctly (spot-check).

**Ordering:** MUST ship after C1 (so structured events have a contract) and after B2 (so adding `ruff` as a dep doesn't break the lockfile rule).

---

## PR D1 — LLM provider adapter (non-streaming)

**Goal:** normalize non-streaming LLM calls behind a single testable seam. Creates the architectural ground floor that Phase 5b's circuit breakers and future observability will stand on.

**Inventory (~22 non-streaming sites):**
- `backend/routes/planner_routes.py` — 14 sites
- `backend/app.py` — 2 sites
- `backend/routes/assignment_routes.py:148`
- `backend/routes/assignment_player_routes.py:344`
- `backend/routes/grading_routes.py:768`
- `backend/routes/lesson_routes.py:463`
- `backend/services/grading_service.py:235`
- `backend/services/assistant_tools_behavior.py:599`
- `backend/services/assistant_tools_ai.py:123`
- `backend/services/seo_service.py:38`
- `backend/services/assignment_post_processing.py:1929`

**Explicitly excluded:**
- `backend/routes/assistant_routes.py` (3 sites) — all streaming+tool-use, migrated in D2
- `backend/services/slide_generator.py:155, 258` — image generation via `google.genai`, not chat-shaped, deferred to Phase 5b

**New module:** `backend/services/llm_adapter.py`

**Request model (`LLMRequest`) — first-class fields:**
```python
@dataclass
class LLMRequest:
    model: str
    messages: list[ContentPart]          # structured, not plain strings
    system_prompt: str | None = None     # dedicated field, not messages[0]
    tools: list[ToolDef] | None = None   # tool-use is first-class
    response_format: ResponseFormat | None = None   # JSON-mode, etc.
    max_tokens: int | None = None
    temperature: float | None = None
    timeout: float = DEFAULT_TIMEOUT
    metadata: dict = field(default_factory=dict)   # only non-semantic tags (request_id, teacher_id, feature_label)
```

`ContentPart` is a union: `TextPart`, `ImagePart` (URL-based or base64), future `ToolResultPart` for tool round-trips.

**Response model (`LLMResponse`):**
```python
@dataclass
class LLMResponse:
    content_parts: list[ContentPart]     # rich content, not just text
    tool_calls: list[ToolCall]           # if any
    usage: Usage                         # prompt_tokens, completion_tokens, cost_usd
    finish_reason: str                   # stop, length, tool_use, content_filter
    provider: str                        # "openai" | "anthropic" | "gemini"
    model: str                           # echo of request
```

**Protocol:**
```python
class LLMAdapter(Protocol):
    def chat(self, request: LLMRequest) -> LLMResponse: ...
```

**Implementations:**
- `OpenAIAdapter` — maps to `openai.chat.completions.create`. Maps `system_prompt` to a system-role message (OpenAI convention).
- `AnthropicAdapter` — maps to `anthropic.messages.create`. Maps `system_prompt` to top-level `system=` (Anthropic convention).
- `GeminiAdapter` — maps to `google.generativeai.GenerativeModel.generate_content`. Maps `system_prompt` to `system_instruction=`, `messages` to `contents=`.

**Standard hooks every call goes through:**
- Timeout (per-provider default in `DEFAULT_TIMEOUT`, overridable).
- Retry via **existing `backend.retry.with_retry()` primitive** (reuses status/keyword classification from Phase 2). NOT a new `TransientExternalError`.
- Metrics: `emit('llm.call.start', ...)`, `emit('llm.call.complete', ...)`, `emit('llm.call.error', ...)` using C1's helper. Include model, provider, duration_ms, usage, cost_usd.
- Sentry breadcrumb on error (existing `sentry_sdk.add_breadcrumb` pattern).
- Consolidate the existing planner/assistant token-cost accounting into the adapter's usage fields (don't add a parallel system).

**Migration strategy:**
- **Additive first:** introduce adapter module; old direct calls still work.
- Migrate one call site per commit with a unit test per site (can mock `LLMAdapter`).
- Delete direct `openai`/`anthropic`/`google.generativeai` imports from migrated files only after the site is migrated.
- The 14 `planner_routes.py` sites land in a series of small commits within PR D1 to keep diffs reviewable.

**Test plan:**
- Unit tests: each adapter's request-mapping (Python dict → provider-specific call) is snapshot-tested.
- Unit tests: response-mapping (provider-specific response → `LLMResponse`) is snapshot-tested.
- Integration test: one full round-trip per provider using VCR-style cassettes (mock the HTTP call, replay cassettes).
- Full suite stays green after each call-site migration.

**Out of scope:**
- Streaming (D2).
- Tool-use round-trips (D2 — `assistant_routes` has the tool-call reconstruction logic).
- Circuit breakers (Phase 5b).
- Image generation (Phase 5b).

---

## PR D2 — LLM adapter streaming + tool-use (assistant_routes)

**Goal:** extend the D1 adapter to cover the 3 `assistant_routes.py` sites at lines 1461, 1508, 1620 — the streaming/tool-use chat loop.

**New Protocol method:**
```python
class LLMAdapter(Protocol):
    def chat(self, request: LLMRequest) -> LLMResponse: ...                 # D1
    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]: ... # D2
```

**`StreamEvent` types (discriminated union):**
- `TextDelta(text: str)` — incremental text chunk
- `ToolCallDelta(tool_call_id: str, name: str | None, args_delta: str)` — incremental tool-call args assembly
- `ToolCallComplete(tool_call: ToolCall)` — tool-call fully assembled
- `Usage(usage: Usage)` — final usage report
- `FinishEvent(finish_reason: str)` — end of stream

Each provider's native stream shape (OpenAI deltas, Anthropic events, Gemini chunks) is normalized into this event stream.

**Changes:**
- Extend each adapter with `stream_chat()`.
- Migrate `assistant_routes.py:1461-1499` (Anthropic), `1508-1557` (OpenAI), `1620-1655` (Gemini).
- Migrate tool-schema conversion and tool-call reconstruction from the route into per-adapter helpers (currently route-level at `assistant_routes.py:95-192, 1455-1657`).

**Test plan:**
- Replay-style tests using captured real-provider event streams per provider.
- Assistant route-level integration test confirming end-to-end streaming + tool execution round-trip works unchanged.
- Full suite green.

**Risk:** this is the highest-risk PR in Phase 5a because `assistant_routes.py` is the only place three-provider streaming semantics live, and the existing code has accumulated tool-call reconstruction logic that's intricate. Budget 4-5 days.

**Out of scope:** image generation (slide_generator), TTS (openai_tts_service), circuit breakers.

---

## Sequencing, dependencies, and hidden blockers

**Merge order:** A → B1 → B2 → C1 → C2 → D1 → D2

**Hard dependencies:**
- **C2 blocked by C1:** C2's migration uses C1's `emit()` helper. Without C1, C2 falls back to the formatter-drops-extras bug.
- **C2 blocked by B2:** C2 adds `ruff` as a dep. After B2 lands, adding a dep requires editing `.in` and regenerating lockfiles. Landing C2 before B2 means C2 adds `ruff` to the old `requirements.txt` and B2 later absorbs it.
- **D1 metrics blocked by C1:** D1's `emit('llm.call.*', ...)` events need C1's helper.
- **D2 blocked by D1:** D2 extends D1's Protocol. Cannot ship without D1.

**Soft dependencies:**
- A before everything: its green signal protects later PRs from secret leaks. Not a blocker, but the cost of moving it is near zero.
- B1 before B2: B1 cleans up the source material B2 freezes.

**No cross-PR dependency:** B2 ↔ C1, B2 ↔ D1. These can ship in either order as long as the dependencies above are respected.

**Parallel-session safety:** each PR is on its own branch; worktrees are fine. Subagent-driven development can handle one PR per session.

---

## Testing strategy

**Per-PR:**
- All PRs maintain CI `backend-tests`, `frontend-build`, `migrations-smoke` green.
- Coverage floor stays at 32% (CI) — these PRs are NOT expected to raise it. Any new code has ≥80% line coverage by its own unit tests.
- Each PR adds its own targeted tests (see per-PR test plans above).

**Cross-PR:**
- After the full Phase 5a sprint ships, do a clean-env install (`pip install --require-hashes -r requirements.txt -r requirements-dev.txt`) + full suite run as a final safety check.

**No Clever/ClassLink/OneRoster contract touched — no SIS-specific regression testing needed.**

---

## Rollout and risks

**Rollout:**
- Each PR merged independently. Railway auto-deploys on merge to main.
- Operator checks BetterStack for startup log health after each deploy (same process used after Phase 4.5 and PR #106 deploys).
- No flag-gated rollouts required — none of these changes have branching runtime behavior. (Phase 5b circuit breakers WILL need flag gating, designed in that spec.)

**Risks per PR:**

| PR | Risk | Mitigation |
|---|---|---|
| A | Bandit false positives blocking PRs | Baseline allow-list at merge; governance comment on refresh policy |
| A | trufflehog missing `$BASE` fetch → scan errors | Explicit `fetch-depth: 0` or targeted base fetch step |
| B1 | Dev tests fail if pytest-cov not installed | Test locally + verify CI step change before merge |
| B2 | Resolver conflicts on first compile | Budget 3-4 days, not half-day |
| B2 | Hash mismatches on Railway | Test Railway build against new lockfile in pre-merge branch first |
| C1 | Wrong formatter choice entrenches a bad pattern | Recommendation (JSON-in-message) is the already-working pattern; low risk |
| C2 | Accidentally migrating a subprocess-protocol print | Explicit allow-list + Ruff per-file-ignores; visualization and outlook_sender are caught |
| D1 | Missing a call site → runtime AttributeError after import cleanup | Keep direct imports until ALL sites are migrated; delete imports only at end |
| D1 | Response-mapping drops fields some caller relied on | Snapshot tests per-provider catch this before commit |
| D2 | Stream-event abstraction misses a provider-specific case | Capture real event streams per provider into test cassettes first; drive design from captured data, not imagination |

**Rollback:** each PR is a single squash commit — `git revert` is the rollback path. No stateful changes (DB schema, RLS policies, etc.) in Phase 5a.

---

## Effort estimate

| PR | Days |
|---|---|
| A | 1 |
| B1 | 1 |
| B2 | 3-4 |
| C1 | 1 |
| C2 | 2-3 |
| D1 | 5-6 |
| D2 | 4-5 |
| **Total (sequential)** | **17-21 days (~3-4 weeks)** |

Compressible to ~2.5 weeks with parallel worktrees for non-dependent PRs (A ‖ B1 ‖ C1 at the start; D1 and D2 serial at the end).

---

## Deviations from Phase 5 roadmap

The original Phase 5 roadmap ( `project_codebase_improvement_roadmap.md`) listed 10 items. Phase 5a picks 4 and reshapes them:

| Roadmap item | Phase 5a treatment |
|---|---|
| Mypy strict on critical modules | **Deferred to later phase** — too much type-cleanup needed first |
| Pydantic for API payloads + Supabase records | **Deferred to later phase** — huge refactor, conflicts with current module shape |
| SAST (Bandit) + secret scanning (trufflehog) in CI | **PR A** (Codex-refined scope) |
| Dependency pinning (pip-tools) | **PR B1 + PR B2** (split per Codex feedback) |
| APM tracing (enable traces_sample_rate) | **Deferred to Phase 5b** — needs Sentry billing decision |
| Structured JSON logging (replace print()) | **PR C1 + PR C2** (split per Codex feedback — formatter decision first) |
| Circuit breakers for LLM APIs (pybreaker) | **Deferred to Phase 5b** — Codex correctly argued for adapter seam first |
| RFC 7807 error responses | **Deferred** |
| OpenAPI/Swagger generation | **Deferred** |
| Mutation testing (mutmut) | **Deferred** |

**Added to Phase 5a beyond the original roadmap:**
- **PR D1 + PR D2: LLM provider adapter layer** — not in the original roadmap but required as the seam that Phase 5b's circuit breakers and future tooling will stand on. Derived from Codex's round-1 argument that sprinkling `pybreaker` across 30 direct provider calls would be architecturally wrong.

---

## Expected outcome (dimension deltas after Phase 5a)

| Dimension | Current | After Phase 5a | Gap to 9+ |
|---|---|---|---|
| Security | 7 | 7.5–8 | small (Phase 5b: APM + RFC 7807 + Pydantic input validation) |
| Error handling | 5 | 7–7.5 | medium (Phase 5b: pybreaker, RFC 7807) |
| Code quality | 5 | 6–6.5 | medium (later: mypy, Pydantic, OpenAPI) |
| Observability | 8 | 9 | small (Phase 5b: APM tracing flip) |
| Operational safety | 8 | 8.5–9 | small (Phase 5b: pybreaker) |
| **Others unchanged** | | | |

Average movement: 6.8 → ~7.3 on Phase 5a alone. Phase 5b closes the gap to ~8.5, subsequent phases to 9+.

---

## Self-review (2026-04-20, post-Codex round-2)

**Placeholder scan:** none. All sections have concrete content; code examples are compilable Python; file paths verified against repo state today.

**Internal consistency:** architecture section matches PR descriptions. Sequencing rationale matches dependency list. Dimension deltas match item selection.

**Scope check:** spec covers 7 PRs forming a single coherent phase with tight coupling between PRs (not 7 independent subsystems). Plan-writing can proceed.

**Ambiguity check:**
- C1's "recommendation: option 2" is explicit enough for the plan — plan writer picks option 2 unless the user objects.
- D1's `ContentPart` union is a type, not an implementation — plan will specify `@dataclass(frozen=True)` per member.
- D2's `StreamEvent` discriminated union is similar — plan specifies tagged dataclasses.
