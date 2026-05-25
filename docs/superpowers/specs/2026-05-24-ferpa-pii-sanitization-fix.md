# FERPA PII Sanitization Fix — Grading Prompts Sent to External LLMs

**Date:** 2026-05-24
**Status:** Spec for review (3-model reconciled). Implementation is a single dedicated PR.
**Severity:** FERPA/privacy — student PII is currently sent to third-party LLMs unsanitized.

> Planned via the 3-provider protocol (Claude superpowers + Codex 5.5 high + Gemini, advisory;
> conservative-floor reconciliation). Gemini's `--yolo` auto-edits were discarded — this is a
> clean, reviewed plan; implementation is by hand on a branch.

## 1. The bug (verified, systemic)

`backend/services/grader_text_prep.py::sanitize_pii_for_ai(student_name, content)` strips student
name variations, SSNs, 7–10-digit IDs, emails, phones, MM/DD/YYYY dates, street addresses, and
5-digit zips. It is called in **exactly one place** — `grading_pipeline.py` `grade_assignment`
(~line 1105) — where its result `sanitized_content` is used only for an audit-log diff and then
**discarded**. The actual prompt sent (~1116) is `prompt_text + extracted_responses_text`, both
built from **raw** content.

Every LLM-send path is affected (no upstream mitigation — verified: `backend/grading/pipeline.py`
and the routes call `grade_*` with raw content; `redact_*` utils are audit-log only):

| Path | Today |
|------|-------|
| `grade_assignment` (single-pass) | sanitize computed, **discarded** → raw sent |
| `grade_multipass` → `grade_per_question` + `generate_feedback` | **no sanitization** |
| `grade_with_parallel_detection` → `detect_ai_plagiarism` | `preprocess_for_ai_detection` only (not PII-stripping) |
| `portal_grading` → `grade_per_question` + `generate_feedback` (bypasses multipass) | **no sanitization** |
| feedback translation → `_translate_feedback` | **no sanitization** (another external call on student-derived text) |

The leaf callers (`grade_per_question`/`generate_feedback`/`detect_ai_plagiarism`/`_translate_feedback`)
do not currently receive `student_name`.

## 2. Design (reconciled)

### 2a. Chokepoint — sanitize the FINAL PROMPT at each send boundary (Codex; Claude concurs)
Sanitize a **copy of the assembled prompt string, immediately before each provider dispatch**.
Do NOT sanitize `assignment_data["content"]`/`extraction_result`/`responses`/result dicts (that
would corrupt extraction + grading state and still miss `portal_grading`). Send boundaries:
- `grading_pipeline.py::grade_assignment` — sanitize `full_prompt` (and the image text part) before the OpenAI/Anthropic/Gemini calls.
- `grading_leaves.py::grade_per_question` — sanitize `prompt` (and the system/json blob as needed) before dispatch.
- `grading_leaves.py::generate_feedback` — sanitize the prompt before dispatch.
- `grading_leaves.py::detect_ai_plagiarism` — sanitize `detection_prompt` before dispatch.
- `grading_leaves.py::_translate_feedback` — sanitize `prompt` before dispatch.

`student_name` is threaded as an optional `student_name: str = ""` param into the 4 leaves
(defaults keep existing callers/tests working), and propagated:
- `grade_multipass` → per-question calls + feedback call.
- `grade_with_parallel_detection` → `detect_ai_plagiarism`.
- `portal_grading.grade_written_questions` → take `student_name` (from `student_info`) → forward to both leaf calls.
- `grade_assignment` already has `student_name`.

**Boundary #6 — discovered during implementation (call-site audit, not in original consult):**
`backend/routes/assignment_player_routes.py` grades per-question via `grade_per_question`
(imported as `ai_grade_per_question`) through `grade_assignment(local) → _grade_with_ai →
ai_grade_per_question`. Without threading, the `student_name=""` default still strips structured
PII (email/SSN/phone/labeled-ID/address) but **not the student's name**. Closed by threading
`student_name` (already present in the `submit_assignment` route handler) through all three.
Also hardened the single-pass `grade_assignment::_translate_feedback` call (was the one leaf call
missing `student_name`) for defense-in-depth + consistency with the multipass path.

### 2b. Content-preserving sanitizer (Codex + Claude; the Q2 crux — Gemini missed it)
Add `sanitize_grading_prompt_for_ai(student_name, text) -> str` in `grader_text_prep.py`. It:
- **Always redacts:** non-common-word student-name parts (len>2, word-boundary, case-insensitive) → `[STUDENT]`; emails; phones; SSNs (`XXX-XX-XXXX` literal + labeled bare-9-digit); street addresses.
- **Common-word names** (Grace/May/Mark/Hope/Will/Rose/… — names that are also ordinary English words) are redacted **only in Capitalized/ALL-CAPS form**, so their lowercase use as words in an answer survives ("founded in may", "grace under pressure"). Code-review C1: case-insensitive redaction of these corrupts grading.
- **Redacts only when context-labeled** (so legitimate answers survive): IDs (any length)/DOB/zip/SSN preceded by a label and `:`/`#`/`-` separator, e.g. `Student ID: 1234567`, `DOB - 02/15/2025`, `Zip: 33101`, `SSN: 123456789`.
- **Preserves** naked numeric/date answers: `8280000`, `828,000`, `1803`, `2/15/1861`, math, etc.

`sanitize_pii_for_ai` stays as-is (still used by its tests + the audit-diff); the new function is
the one used on prompts. (Rationale: what's sent == what's graded; over-redacting naked numbers
would corrupt scores.)

## 3. Tests (Codex)
New `tests/test_grading_pii_sanitization.py` (or extend the snapshot test), asserting across
**all** paths — `grade_assignment`, `grade_multipass`, `grade_with_parallel_detection`, direct
`grade_per_question`/`generate_feedback`/`detect_ai_plagiarism`, and the portal
`grade_written_questions` + feedback — using the prompt-capture harness:
1. **PII-removal:** no captured LLM prompt contains `Maria`, `Garcia`, `Maria Garcia`, an email,
   phone, SSN, street address, or labeled student ID/DOB/zip (use a fixture seeded with these).
2. **Numeric preservation:** prompts STILL contain legitimate answer values (`8280000`,
   `828,000`, `1803`, an unlabeled date) — guards against "fixing FERPA" by breaking grading.
3. **Fix the existing snapshot:** `tests/test_grader_prompt_snapshots.py` currently passes
   `student_name="T"` (not `"Maria Garcia"` from the fixture) — so it doesn't prove name removal.
   Change to `student_name="Maria Garcia"` and **re-baseline** the sha256 hashes (the captured
   prompts now contain `[STUDENT]` instead of `Maria`/`Garcia`).

## 4. Rollout
- **One PR:** code + new sanitizer + tests + intentional snapshot re-baseline.
- **Result dicts unchanged** — only the prompt TEXT sent externally changes; the SDK-fake golden
  tests stay green (the fakes route on response_format type + coarse markers, not exact wording,
  and content-preserving sanitization keeps the routed substrings).
- Keep audit logging narrow (log that sanitization occurred + categories, not values).

## 5. Out of scope (follow-ups)
- **Image submissions** send pixels to vision models (`grade_assignment` image path) — text
  sanitization cannot remove handwritten PII; needs a separate image-redaction policy.
- **`anon_id` wiring** — currently computed + unused; a separate PR if product wants stable
  anonymous identifiers in audit metadata.
- **Pre-existing F821 `questions` at `portal_grading.py:594`** (in `grade_portal_submission_sync`,
  a function untouched by this PR; present on `origin/main`). It's a swallowed NameError inside a
  `try/except Exception` that silently disables correction-context building in that path. Fix needs
  tracing the submission-context data flow to determine the correct `questions` source — separate
  focused PR. Repro: `ruff check --select F821 backend/services/portal_grading.py`.

## 6. References
- 3-model consult: `/tmp/pii_fix_consult.md` (prompt); Codex/Gemini/Claude legs reconciled above.
- Bug sites: `grading_pipeline.py:1105/1116`; leaves `grading_leaves.py`; `portal_grading.py:171/778`.
