# Wave 7 Phase B — LLM Scoring Core Golden Net + Extraction Design

> Decided design for the highest-risk slice of the grader decomposition. Captures the
> 3-model consensus (Claude first-hand + Codex 5.5 high + Gemini, conservative-floor
> reconciliation) reached at the Phase-B design fork. This is a SPEC of a decided design,
> not an open brainstorm — the design questions were resolved via the consult; this records
> the answers and the verified seam facts so a fresh agent can execute without re-deriving.

**Date:** 2026-05-24
**Status:** Approved (user: "proceed with the consensus design once Codex returns")
**Scope:** Build a faithful, deterministic golden net for `assignment_grader.py`'s LLM-coupled
scoring core, then extract that core into `backend/services/` behind it — behavior-preserving.

---

## 1. Goal

Decompose the LLM-coupled scoring core of `assignment_grader.py` (currently 3,567 LOC) into
Flask-free `backend/services/` modules under a heightened golden/characterization net, with
**zero behavior change** to real student grading. This is the final, riskiest stretch of Wave 7
and the lever the unanimous Post-Wave-6 re-score named for pushing **Code Quality 9 → 9.5+**.

Functions in scope (verified line numbers, current main @ e6e56e2):
- `detect_ai_plagiarism` (569) — OpenAI structured + text fallback; short-circuits <50 chars.
- `grade_with_ensemble` (690) — fan-out over N models via `grade_assignment`; median aggregation.
- `grade_with_parallel_detection` (804) — runs detection + grading in parallel threads.
- `grade_per_question` (1028) — per-question grader; 3 providers; TransientError on retryable.
- `generate_feedback` (1254) — feedback prose; 3 providers; conditionally calls `_translate_feedback`.
- `grade_multipass` (1537) — orchestrator: extract → per-question (ThreadPoolExecutor max_workers=5)
  → aggregate/cap → feedback. Blank/near-blank short-circuit BEFORE any LLM call.
- `_translate_feedback` (1992) — ELL translation; 3 providers; returns "" on failure.
- `grade_assignment` (2072, ~1,100 LOC) — single-pass alternative; 3 providers; image support.

Shared types/state (move first): `GradingBreakdown/SkillsDemonstrated/AiDetectionResult/`
`PlagiarismDetectionResult/GradingResponse/DetectionResponse` (58–97), `QuestionGrade/`
`PerQuestionResponse/FeedbackResponse` (1004–1018), `TokenTracker` + `MODEL_PRICING` (124–191).

**Pre-Phase-B dependency (must extract first):** `update_writing_profile` (204) /
`get_writing_profile` (269) and `build_roster_from_periods` (407) are file-I/O-only (no LLM).
`grade_multipass` calls `update_writing_profile` (line 1974) and `analyze_writing_style`
(already a service import). Extracting `grade_multipass` to a service would create a back-import
to `assignment_grader` unless `update_writing_profile` already lives in a service. So these
file-I/O leaves are extracted FIRST (Phase-A-style: tmp-dir golden tests, no SDK harness needed).

---

## 2. The LLM seam (verified)

- **16 LLM calls across 3 RAW SDKs** (NOT a shared adapter): OpenAI, Anthropic, Gemini.
- Imports are **function-local** every call site: `from openai import OpenAI`,
  `import anthropic`, `import google.generativeai as genai`.
- Module-top seams (line 303/304): `from backend.api_keys import get_api_key as _get_api_key`,
  `from backend.retry import with_retry`. EVERY SDK call is wrapped
  `with_retry(lambda: <client call>, label="<feature>_<provider>")` with a UNIQUE label.
- Client construction is always `OpenAI(api_key=_get_api_key('openai'))` /
  `anthropic.Anthropic(api_key=_get_api_key('anthropic'))` / `genai.configure(api_key=...)`
  then `genai.GenerativeModel(model)`.
- **`get_api_key` env fallback** (`backend/api_keys.py`): `_ENV_MAP = {openai: OPENAI_API_KEY,
  anthropic: ANTHROPIC_API_KEY, gemini: GEMINI_API_KEY}`. With no contextvar/teacher/district
  keys set (true in unit tests), it returns the env var. `grade_assignment` GUARDS on
  `if not _get_api_key('anthropic'|'gemini')` (lines 2114/2133) and returns an ERROR dict if
  the key is falsy — so the anthropic/gemini branches REQUIRE the env key set.
- **Response shapes the callers read** (provider-specific):
  - OpenAI structured: `client.beta.chat.completions.parse(response_format=<Model>)` →
    `response.choices[0].message.parsed` (Pydantic instance). Fallback when `.parsed` is None:
    `response.choices[0].message.content` (raw JSON str). Token usage off `response.usage`
    (`prompt_tokens`/`completion_tokens`).
  - OpenAI text: `client.chat.completions.create()` → `response.choices[0].message.content.strip()`.
  - Anthropic: `client.messages.create()` → `response.content[0].text.strip()` →
    `_try_parse_json_fallback(...)`. Token usage off `response.usage`
    (`input_tokens`/`output_tokens`).
  - Gemini: `genai.GenerativeModel(...).generate_content(prompt | [prompt, image_part])` →
    `response.text.strip()` → `_try_parse_json_fallback(...)`. Token usage off
    `response.usage_metadata` (`prompt_token_count`/`candidates_token_count`).

---

## 3. Consensus design (3-model reconciled)

### Q1 — Stub seam → **Patch the 3 SDK entrypoints; keep `with_retry` real.**
Patch `openai.OpenAI`, `anthropic.Anthropic`, `google.generativeai.GenerativeModel`, and
`google.generativeai.configure` with provider-shaped fakes. Do NOT patch `with_retry` (stays
real → exercises the true call + parse + `_try_parse_json_fallback` path; a regression there is
caught). Do NOT patch `assignment_grader._get_api_key` — that name MOVES on extraction. Instead
`monkeypatch.setenv` the three env keys so the real `get_api_key` returns truthy. This seam is
**extraction-stable**: the function-local `from openai import OpenAI` re-reads the patched module
attribute after the function moves to a service.

### Q2 — Granularity → **Hybrid.**
End-to-end full-result-dict goldens on `grade_multipass` + `grade_with_parallel_detection` +
`grade_assignment`, PLUS per-function leaf goldens (`grade_per_question`, `detect_ai_plagiarism`,
`generate_feedback`, `_translate_feedback`). Assert **structured fields exactly** (score,
letter_grade, breakdown dict, ai_detection/plagiarism_detection flags, token_usage summary,
per_question_scores) and **stable substrings** for feedback prose (the fake returns fixed prose,
so the substring is deterministic — but assert containment, not full-string identity, to avoid
brittleness if surrounding assembly adds audit/translation suffixes).

### Q3 — Multi-call orchestration → **Content-match keyed, thread-safe, distinct per question.**
`grade_multipass` makes N per-question calls (parallel, ThreadPoolExecutor max_workers=5) + 1
feedback call. Key fake responses by `(label, provider, normalized_question_text)` — NOT by
call-sequence (threads complete out of order). Return DISTINCT responses per question so
aggregation math is exercised (not a single canned score). The fake holds a `threading.Lock`
around its call-log append (parallel-safe). Assert per-label call counts.

### Q4 — Extraction order & cohesion.
0. **Pre-step (Phase A leftover):** extract `update_writing_profile`/`get_writing_profile` →
   `backend/services/writing_profile.py`; `build_roster_from_periods` → append to
   `backend/services/grader_roster.py`. Tmp-dir golden tests (HOME-isolation). No SDK harness.
   `as`-shim if any `backend/grading/` strict module imports them.
1. **Build the SDK-fake golden harness** (`tests/grading_fakes.py` + golden tests), green
   against CURRENT `assignment_grader.py`, BEFORE any LLM-core extraction.
2. **Move shared types/state** → `backend/services/grading_models.py` (the 9 Pydantic models +
   provider model-maps) and confirm `TokenTracker`/`MODEL_PRICING` placement (likely
   `backend/services/token_tracker.py`). Re-export shims in the grader.
3. **Extract leaves cohesively:** `grade_per_question`; `detect_ai_plagiarism`; and
   `generate_feedback` + `_translate_feedback` TOGETHER (feedback conditionally calls translate).
4. **Extract `grade_multipass`** (after its leaves + `update_writing_profile` are services).
5. **Extract `grade_assignment`** alone (~1,100 LOC).
6. **Extract entry points last:** `grade_with_ensemble` + `grade_with_parallel_detection`.
   `assignment_grader.py` stays a thin re-export facade.

### Q5 — Landmines (preserve each EXACTLY).
- **Non-uniform `.parsed`-None behavior:** `grade_assignment` falls back to `.content` text parse;
  `grade_per_question`/`generate_feedback` fall THROUGH to their error/default return when
  `.parsed` is falsy and no `"grade"`/`"feedback"` key is found. Do NOT unify these.
- **TransientError propagation:** `grade_per_question`/`generate_feedback` re-raise
  `is_retryable_error(e)` as `backend.tasks.grading_tasks.TransientError` (Celery autoretry).
  Non-transient → encouraging fallback dict. Golden must cover BOTH a clean success and a
  fallback path (force the fake to return malformed JSON for one case).
- **TokenTracker shared across parallel threads:** same instance passed to every per-question
  call; fakes must carry realistic `usage`/`usage_metadata` so the summary totals are exercised.
- **Score determinism:** `int(round(...))` aggregation, completeness caps by grading_style,
  effort-point tiers, custom `rubric_weights` override — all post-LLM, deterministic. Golden
  pins them.
- **Blank/near-blank short-circuit BEFORE any LLM call:** `submission_blank.txt` golden needs
  NO stub (asserts the no-LLM path: score 0, letter_grade INCOMPLETE).
- **Feedback model upgrade:** `grade_multipass` uses `gpt-4o` for feedback even when grading
  used `gpt-4o-mini` (openai provider only). The fake must key feedback on `gpt-4o`/the
  `generate_feedback_*` label.
- **ELL translation:** only fires when an `~/.graider_data/ell_students.json` entry exists for
  `student_id`. Use `student_id=None` (or HOME-isolation) to keep the base goldens single-call;
  add ONE dedicated ELL golden with HOME-mocked ell file + a `translate_*` fake.
- **Provider routing:** cover all 3 branches (`ai_model.startswith("claude"|"gemini")` else
  openai) for `grade_per_question` and `grade_assignment`.
- **`sanitize_pii_for_ai`** stays coupled to its LLM call (already a service helper; the grader
  calls it before sending content).

---

## 4. The fake harness (concrete)

`tests/grading_fakes.py` exposes a context manager `patched_llm(responses)` that:
1. `monkeypatch.setenv` `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GEMINI_API_KEY` = "test-...".
2. Patches `openai.OpenAI` → `FakeOpenAI`, `anthropic.Anthropic` → `FakeAnthropic`,
   `google.generativeai.GenerativeModel` → `FakeGeminiModel`, `google.generativeai.configure`
   → no-op.
3. Each fake routes on the call kwargs it receives (model, response_format presence,
   message/prompt content) to a canned, provider-shaped response object, keyed by
   `(label-ish, provider, normalized_question_text)`. Records every call under a `Lock`.
4. `FakeOpenAI` exposes `.beta.chat.completions.parse` (returns obj with
   `.choices[0].message.parsed` = a real Pydantic instance of the requested `response_format`,
   plus `.usage`) and `.chat.completions.create` (returns obj with
   `.choices[0].message.content` + `.usage`).
5. `FakeAnthropic.messages.create` returns obj with `.content[0].text` + `.usage`
   (`input_tokens`/`output_tokens`).
6. `FakeGeminiModel(model).generate_content(...)` returns obj with `.text` + `.usage_metadata`.

Goldens captured by running the REAL grader once under the fakes and hardcoding the asserted
fields (NOT a live API call). Fixtures: `tests/fixtures/grading/submission_{ela,math,science,`
`social_studies,blank}.txt` + `config_*.json` + `rubric_*.json`.

---

## 5. Per-slice protocol (heightened — live scoring engine)

Per the handoff §3, unchanged: golden-char-test baselined green BEFORE extraction (import via
`assignment_grader` so the shim keeps it valid) → broad grading sweep green before AND after
(`pytest tests/ -k "grad or grader or pipeline or writing or detection or feedback or multipass
or portal_grading or factor or ensemble" --ignore=tests/load --ignore=tests/e2e`) → verbatim
re-export shim (service must NOT import assignment_grader) → verify (AST function-source
byte-identical vs origin/main except print→logger; ruff incl. `--select F401,F841`; CI mypy cmd
if a `backend/grading/` strict module imports the symbol → use explicit `as` shim) → local
pre-checks (`bandit -q -ll <file>`, `ruff check <file>`) → two-stage review → squash-auto-merge
→ robust watcher. One slice = one PR, strictly sequential on `assignment_grader.py`.

Linter lessons (services/ is ruff-T20 + Bandit + Mypy-Strict scanned): print()→`_logger.*`
(%-formatted); `hashlib.md5(..., usedforsecurity=False)`; explicit `as` re-export for strict
importers; `# nosec B311` on `random` for non-crypto.

---

## 6. References
- Scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Handoff: `handoff.md` (Wave 7 state; update after this lands).
- Wave 7 PRs #520–#539 (all merged): pure helpers + file-reader cluster + roster/CSV export.
- Existing (extraction-fragile) pattern to AVOID: `tests/test_grading_pipeline.py` patches
  `assignment_grader._get_api_key` + leaf functions directly.
