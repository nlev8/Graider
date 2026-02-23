# Token Cost Tracking — Implementation Plan

## Overview

Track actual API token usage and cost for every grading operation. Currently, all three providers (OpenAI, Claude, Gemini) return token usage data in their responses, but Graider ignores it completely. This plan adds:

1. A `TokenTracker` utility to accumulate tokens across multi-call pipelines
2. Token capture at every API call site
3. Cost calculation using per-model pricing tables
4. Cost data attached to each grading result
5. Session-level cost summary in the grading status
6. Frontend display of actual costs per student and per batch

---

## Provider Token Data Formats

Each provider returns usage data differently:

```python
# OpenAI (both .parse() and .create())
response.usage.prompt_tokens      # int
response.usage.completion_tokens  # int

# Claude (Anthropic)
response.usage.input_tokens       # int
response.usage.output_tokens      # int

# Gemini (Google)
response.usage_metadata.prompt_token_count      # int
response.usage_metadata.candidates_token_count  # int
```

---

## Pricing Table (per 1M tokens, as of Feb 2026)

```python
MODEL_PRICING = {
    # OpenAI
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    # Claude
    "claude-3-5-haiku-latest":    {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-20250514":   {"input": 3.00,  "output": 15.00},
    "claude-opus-4-20250514":     {"input": 15.00, "output": 75.00},
    # Gemini
    "gemini-2.0-flash":    {"input": 0.10,  "output": 0.40},
    "gemini-2.0-pro-exp":  {"input": 1.25,  "output": 5.00},
}
```

---

## Changes

### Change 1: Add `TokenTracker` class — `assignment_grader.py` (after imports, ~line 40)

Add a simple accumulator class that each grading call uses:

```python
# =============================================================================
# TOKEN / COST TRACKING
# =============================================================================

MODEL_PRICING = {
    # OpenAI — price per 1M tokens
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    # Claude
    "claude-3-5-haiku-latest":    {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-20250514":   {"input": 3.00,  "output": 15.00},
    "claude-opus-4-20250514":     {"input": 15.00, "output": 75.00},
    # Gemini
    "gemini-2.0-flash":    {"input": 0.10,  "output": 0.40},
    "gemini-2.0-pro-exp":  {"input": 1.25,  "output": 5.00},
}

class TokenTracker:
    """Accumulates token usage across multiple API calls for a single student grading."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls = []  # list of {"model", "input_tokens", "output_tokens", "cost"}

    def record_openai(self, response, model: str):
        """Extract tokens from an OpenAI response."""
        if not response or not hasattr(response, 'usage') or not response.usage:
            return
        inp = response.usage.prompt_tokens or 0
        out = response.usage.completion_tokens or 0
        self._add(model, inp, out)

    def record_anthropic(self, response, model: str):
        """Extract tokens from a Claude response."""
        if not response or not hasattr(response, 'usage') or not response.usage:
            return
        inp = response.usage.input_tokens or 0
        out = response.usage.output_tokens or 0
        self._add(model, inp, out)

    def record_gemini(self, response, model: str):
        """Extract tokens from a Gemini response."""
        if not response or not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            return
        inp = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
        out = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
        self._add(model, inp, out)

    def _add(self, model: str, input_tokens: int, output_tokens: int):
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6)
        })

    def summary(self) -> dict:
        total_cost = sum(c["cost"] for c in self.calls)
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": round(total_cost, 6),
            "total_cost_display": f"${total_cost:.4f}",
            "api_calls": len(self.calls),
            "calls": self.calls
        }
```

---

### Change 2: Wire tracker into `grade_per_question()` — line 3617

Add `token_tracker=None` parameter to the function signature. After each API call, record the response.

**Current signature (~line 3617):**
```python
def grade_per_question(question: str, student_answer: str, expected_answer: str = '',
                       points: int = 10, grade_level: str = '6', subject: str = 'Social Studies',
                       teacher_instructions: str = '', grading_style: str = 'standard',
                       ai_model: str = 'gpt-4o-mini', response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written') -> dict:
```

**New signature:**
```python
def grade_per_question(question: str, student_answer: str, expected_answer: str = '',
                       points: int = 10, grade_level: str = '6', subject: str = 'Social Studies',
                       teacher_instructions: str = '', grading_style: str = 'standard',
                       ai_model: str = 'gpt-4o-mini', response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written',
                       token_tracker: 'TokenTracker' = None) -> dict:
```

**After line 3744** (the `response = client.beta.chat.completions.parse(...)` call), add:
```python
        if token_tracker:
            token_tracker.record_openai(response, ai_model)
```

---

### Change 3: Wire tracker into `generate_feedback()` — line 3760

Add `token_tracker=None` parameter.

**Current signature (~line 3760):**
```python
def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str = '6', subject: str = 'Social Studies',
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini', student_responses: list = None,
                      rubric_breakdown: dict = None, blank_questions: list = None,
                      missing_sections: list = None) -> dict:
```

**New signature:**
```python
def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str = '6', subject: str = 'Social Studies',
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini', student_responses: list = None,
                      rubric_breakdown: dict = None, blank_questions: list = None,
                      missing_sections: list = None,
                      token_tracker: 'TokenTracker' = None) -> dict:
```

**After line 3915** (the `response = client.beta.chat.completions.parse(...)` call), add:
```python
        if token_tracker:
            token_tracker.record_openai(response, ai_model)
```

---

### Change 4: Wire tracker into `_translate_feedback()` — line 4323

Add `token_tracker=None` parameter. Record after each provider call.

**After line 4355** (Claude `response = client.messages.create(...)`):
```python
            if token_tracker:
                token_tracker.record_anthropic(response, model)
```

**After line 4367** (Gemini `response = client.generate_content(prompt)`):
```python
            if token_tracker:
                token_tracker.record_gemini(response, model)
```

**After line 4378** (OpenAI `response = client.chat.completions.create(...)`):
```python
            if token_tracker:
                token_tracker.record_openai(response, ai_model)
```

---

### Change 5: Wire tracker into `grade_assignment()` (single-pass) — line ~5220

Add `token_tracker=None` parameter to `grade_assignment()` signature.

Record after each provider call:

**After line 5287** (Claude `response = claude_client.messages.create(...)`):
```python
            if token_tracker:
                token_tracker.record_anthropic(response, actual_model)
```

**After line 5309** (Gemini `response = gemini_client.generate_content(text_content)`):
```python
            if token_tracker:
                token_tracker.record_gemini(response, actual_model)
```

**After line 5330** (OpenAI structured `response = openai_client.beta.chat.completions.parse(...)`):
```python
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
```

**After line 5351** (OpenAI fallback `response = openai_client.chat.completions.create(...)`):
```python
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
```

---

### Change 6: Wire tracker into AI/plagiarism detection — line ~3170

Add `token_tracker=None` parameter to `detect_ai_and_plagiarism()` (or whichever function wraps lines 3173-3200).

**After line 3180** (structured detection `response = client.beta.chat.completions.parse(...)`):
```python
            if token_tracker:
                token_tracker.record_openai(response, "gpt-4o-mini")
```

**After line 3194** (text fallback `response = client.chat.completions.create(...)`):
```python
            if token_tracker:
                token_tracker.record_openai(response, "gpt-4o-mini")
```

---

### Change 7: Create and return tracker in `grade_multipass()` — line 3935

**After line 3949** (`content = assignment_data.get("content", "")`), add:
```python
    tracker = TokenTracker()
```

**At line 4046-4060** (the `executor.submit(grade_per_question, ...)` call), add `token_tracker=tracker`:
```python
            f = executor.submit(
                grade_per_question,
                question=question,
                student_answer=answer,
                expected_answer=expected,
                points=meta['points'],
                grade_level=grade_level,
                subject=subject,
                teacher_instructions=effective_instructions,
                grading_style=grading_style,
                ai_model=grading_model,
                response_type=resp_type,
                section_name=meta['section_name'],
                section_type=meta['section_type'],
                token_tracker=tracker          # <-- ADD
            )
```

**At line 4184-4196** (the `generate_feedback(...)` call), add `token_tracker=tracker`:
```python
    feedback_result = generate_feedback(
        question_results=question_results,
        total_score=final_score, total_possible=100,
        letter_grade=letter_grade,
        grade_level=grade_level, subject=subject,
        teacher_instructions=effective_instructions,
        ell_language=ell_language,
        ai_model='gpt-4o-mini',
        student_responses=responses,
        rubric_breakdown=rubric_breakdown,
        blank_questions=blank_questions,
        missing_sections=missing_sections,
        token_tracker=tracker              # <-- ADD
    )
```

**At line 4201-4226** (the `result = { ... }` dict), add the tracker summary:
```python
    result = {
        "score": final_score,
        "letter_grade": letter_grade,
        # ... existing fields ...
        "token_usage": tracker.summary(),   # <-- ADD
    }
```

---

### Change 8: Return tracker from `grade_assignment()` (single-pass)

Same pattern — create `tracker = TokenTracker()` at the start, pass to each call, include `"token_usage": tracker.summary()` in the return dict.

---

### Change 9: Pass cost data through `backend/app.py` result — lines 1384-1408

**Add to the result dict (~line 1407):**
```python
                grading_state["results"].append({
                    "student_name": student_info['student_name'],
                    # ... existing fields ...
                    "ai_input": grade_result.get('_audit', {}).get('ai_input', ''),
                    "ai_response": grade_result.get('_audit', {}).get('ai_response', ''),
                    "token_usage": grade_result.get('token_usage', {}),   # <-- ADD
                })
```

---

### Change 10: Add session-level cost aggregation — `backend/app.py`

**Add to `grading_state` (line 236):**
```python
grading_state = {
    "is_running": False,
    "stop_requested": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "log": [],
    "results": load_saved_results(),
    "complete": False,
    "error": None,
    "session_cost": {                        # <-- ADD
        "total_cost": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_api_calls": 0
    }
}
```

**After appending each result (~line 1408), accumulate session cost:**
```python
                # Accumulate session cost
                usage = grade_result.get('token_usage', {})
                if usage:
                    grading_state["session_cost"]["total_cost"] += usage.get("total_cost", 0)
                    grading_state["session_cost"]["total_input_tokens"] += usage.get("total_input_tokens", 0)
                    grading_state["session_cost"]["total_output_tokens"] += usage.get("total_output_tokens", 0)
                    grading_state["session_cost"]["total_api_calls"] += usage.get("api_calls", 0)
```

**In `reset_state()` (line 249), reset session cost:**
```python
    grading_state.update({
        # ... existing resets ...
        "session_cost": {"total_cost": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_api_calls": 0}
    })
```

---

### Change 11: Include session cost in status endpoint

The `/api/status` endpoint already returns `grading_state` fields. Add `session_cost`:

```python
return jsonify({
    # ... existing fields ...
    "session_cost": grading_state.get("session_cost", {})
})
```

---

### Change 12: Frontend — show per-student cost in Results tab — `frontend/src/App.jsx`

In the results table row for each student, add a cost column:

```jsx
{/* In results table header */}
<th>Cost</th>

{/* In results table row */}
<td style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
  {r.token_usage?.total_cost_display || "—"}
</td>
```

---

### Change 13: Frontend — show session cost summary during/after grading

In the grading progress section (or results summary header), display the running total:

```jsx
{status.session_cost && status.session_cost.total_cost > 0 && (
  <div style={{
    display: "flex", gap: "16px", fontSize: "0.85rem",
    color: "var(--text-secondary)", marginTop: "8px"
  }}>
    <span>API Cost: ${status.session_cost.total_cost.toFixed(4)}</span>
    <span>Tokens: {(status.session_cost.total_input_tokens + status.session_cost.total_output_tokens).toLocaleString()}</span>
    <span>API Calls: {status.session_cost.total_api_calls}</span>
  </div>
)}
```

---

### Change 14: Frontend — replace hardcoded cost estimates with actual data

The model picker (line 10535-10540) shows hardcoded `cost: "$0.001"` etc. After implementing tracking, these can be replaced with actual per-student averages from grading history. For now, update the static estimates to match current pricing and add a tooltip: "Estimated cost per student".

---

## Thread Safety Note

`TokenTracker` is used per-student (one instance per `grade_multipass` or `grade_assignment` call). The `grade_per_question` calls run in a `ThreadPoolExecutor` with `max_workers=5`. The `_add()` method appends to a list and increments integers — these should be made thread-safe:

```python
import threading

class TokenTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls = []

    def _add(self, model, input_tokens, output_tokens):
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.calls.append({
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": round(cost, 6)
            })
```

---

## Files Changed

| File | Change |
|------|--------|
| `assignment_grader.py` | Add `TokenTracker` class, `MODEL_PRICING` dict |
| `assignment_grader.py` | Add `token_tracker` param to `grade_per_question()`, `generate_feedback()`, `_translate_feedback()`, `grade_assignment()`, detection function |
| `assignment_grader.py` | Record tokens after every API call (OpenAI, Claude, Gemini) |
| `assignment_grader.py` | Create tracker in `grade_multipass()` and `grade_assignment()`, include `token_usage` in result |
| `backend/app.py` | Add `session_cost` to `grading_state`, accumulate per-student, include in status endpoint |
| `frontend/src/App.jsx` | Show per-student cost in results table, session cost during grading |

## Verification

1. **Token capture**: Grade a single file, check `token_usage` in the result — should show non-zero tokens and a cost like `$0.0012`
2. **Session totals**: Grade a batch of 5 files, check `session_cost` — should be sum of individual costs
3. **Thread safety**: Grade with multipass (5 parallel questions) — token counts should equal sum of individual calls
4. **All providers**: Test with OpenAI, Claude, and Gemini — each should capture tokens correctly
5. **Frontend**: Results table shows cost column, grading progress shows running total
