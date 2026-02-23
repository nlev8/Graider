# Multipass Grading for All Providers (Claude & Gemini)

## Overview

Currently only OpenAI uses the multipass pipeline. Claude and Gemini fall through to
the weaker single-pass `grade_assignment()`. This document contains the exact edits
to make all three providers use multipass.

**File:** `assignment_grader.py` (all changes in this one file)

---

## Change 1: Route all providers to multipass

**Lines 3378–3384** — Remove the Claude/Gemini exclusion.

```python
# BEFORE (line 3378-3384)
    # Determine grading strategy: multi-pass for OpenAI, single-pass for Claude/Gemini
    use_multipass = not ai_model.startswith("claude") and not ai_model.startswith("gemini")

    if use_multipass:
        print(f"  🔄 Running parallel detection + multi-pass grading...")
    else:
        print(f"  🔄 Running parallel detection + single-pass grading...")

# AFTER
    # Multi-pass grading for all providers
    use_multipass = True
    print(f"  🔄 Running parallel detection + multi-pass grading ({ai_model})...")
```

---

## Change 2: Add provider detection at the top of `grade_multipass()`

**Line 3948** — Insert after the docstring closing `"""`, before `content = assignment_data.get(...)`.

```python
# INSERT at line 3949 (after docstring, before content = ...)
    # Determine provider from model name
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"
```

---

## Change 3: Pass `ai_provider` to `grade_per_question()` calls

**Lines 4046–4060** — Add `ai_provider=provider` to the `executor.submit()` call.

```python
# BEFORE (lines 4046-4060)
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
                section_type=meta['section_type']
            )

# AFTER
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
                ai_provider=provider,
                response_type=resp_type,
                section_name=meta['section_name'],
                section_type=meta['section_type']
            )
```

---

## Change 4: Pass `ai_provider` to `generate_feedback()` call and use selected model

**Lines 4184–4196** — Add `ai_provider=provider` and change `ai_model` from hardcoded
`'gpt-4o-mini'` to `ai_model` so it uses the teacher's selected model.

```python
# BEFORE (lines 4184-4196)
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
        missing_sections=missing_sections
    )

# AFTER
    # Use a cost-efficient model for feedback generation
    feedback_model = ai_model
    if provider == "openai":
        feedback_model = "gpt-4o-mini"  # Cheaper for feedback text
    # Claude/Gemini: use the same model (no cheaper tier that supports long output)

    feedback_result = generate_feedback(
        question_results=question_results,
        total_score=final_score, total_possible=100,
        letter_grade=letter_grade,
        grade_level=grade_level, subject=subject,
        teacher_instructions=effective_instructions,
        ell_language=ell_language,
        ai_model=feedback_model,
        ai_provider=provider,
        student_responses=responses,
        rubric_breakdown=rubric_breakdown,
        blank_questions=blank_questions,
        missing_sections=missing_sections
    )
```

---

## Change 5: Refactor `grade_per_question()` — add `ai_provider` param and multi-provider support

**Line 3617** — Add `ai_provider` parameter to the signature.

```python
# BEFORE (line 3617-3622)
def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       teacher_instructions: str, grading_style: str,
                       ai_model: str = 'gpt-4o',
                       response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written') -> dict:

# AFTER
def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       teacher_instructions: str, grading_style: str,
                       ai_model: str = 'gpt-4o',
                       ai_provider: str = 'openai',
                       response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written') -> dict:
```

**Lines 3636–3637** — Replace the hardcoded OpenAI import+client with provider routing.
Delete these two lines:

```python
# DELETE (lines 3636-3637)
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
```

**Lines 3733–3744** — Replace the OpenAI-only API call with a provider switch.
The existing code is:

```python
# BEFORE (lines 3733-3755)
    try:
        response = client.beta.chat.completions.parse(
            model=ai_model,
            messages=[
                {"role": "system", "content": f"You are a grade {grade_level} {subject} teacher grading student work. IMPORTANT: The teacher has provided custom grading instructions in the prompt. You MUST follow them exactly — they override all default scoring rules and anchors. If the teacher says to be lenient, score generously. If the teacher says to accept basic answers, do not penalize simplicity."},
                {"role": "user", "content": prompt}
            ],
            response_format=PerQuestionResponse,
            max_tokens=300,
            temperature=0,
            seed=42
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            return parsed.model_dump()
    except Exception as e:
        print(f"    ⚠️ Per-question grading error: {e}")

    return {
        "grade": {"score": int(points * 0.7), "possible": points,
                  "reasoning": "Grading error - default score applied",
                  "is_correct": True, "quality": "adequate"},
        "excellent": False,
        "improvement_note": ""
    }
```

Replace with:

```python
# AFTER
    system_msg = f"You are a grade {grade_level} {subject} teacher grading student work. IMPORTANT: The teacher has provided custom grading instructions in the prompt. You MUST follow them exactly — they override all default scoring rules and anchors. If the teacher says to be lenient, score generously. If the teacher says to accept basic answers, do not penalize simplicity."

    json_schema = '''Respond with ONLY valid JSON in this exact format:
{
    "grade": {
        "score": <integer 0 to ''' + str(points) + '''>,
        "possible": ''' + str(points) + ''',
        "reasoning": "<1-2 sentence explanation>",
        "is_correct": <true or false>,
        "quality": "<excellent|good|adequate|developing|insufficient>"
    },
    "excellent": <true if score >= ''' + str(int(points * 0.9)) + '''>,
    "improvement_note": "<suggestion if not full credit, else empty string>"
}'''

    try:
        if ai_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            claude_model_map = {
                "claude-haiku": "claude-3-5-haiku-latest",
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }
            actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")

            response = client.messages.create(
                model=actual_model,
                max_tokens=300,
                system=system_msg + "\n\n" + json_schema,
                messages=[{"role": "user", "content": prompt}]
            )
            result = _try_parse_json_fallback(response.content[0].text.strip())
            if result and "grade" in result:
                return result

        elif ai_provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            gemini_model_map = {
                "gemini-flash": "gemini-2.0-flash",
                "gemini-pro": "gemini-2.0-pro-exp",
            }
            actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
            gemini_client = genai.GenerativeModel(actual_model)

            full_prompt = system_msg + "\n\n" + json_schema + "\n\n---\n\n" + prompt
            response = gemini_client.generate_content(full_prompt)
            result = _try_parse_json_fallback(response.text.strip())
            if result and "grade" in result:
                return result

        else:  # OpenAI — use structured output
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.beta.chat.completions.parse(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                response_format=PerQuestionResponse,
                max_tokens=300,
                temperature=0,
                seed=42
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                return parsed.model_dump()

    except Exception as e:
        print(f"    ⚠️ Per-question grading error ({ai_provider}): {e}")

    return {
        "grade": {"score": int(points * 0.7), "possible": points,
                  "reasoning": f"Grading error - default score applied ({ai_provider})",
                  "is_correct": True, "quality": "adequate"},
        "excellent": False,
        "improvement_note": ""
    }
```

---

## Change 6: Refactor `generate_feedback()` — add `ai_provider` param and multi-provider support

**Line 3760** — Add `ai_provider` to the signature.

```python
# BEFORE (line 3760-3767)
def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str, subject: str,
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini',
                      student_responses: list = None,
                      rubric_breakdown: dict = None,
                      blank_questions: list = None,
                      missing_sections: list = None) -> dict:

# AFTER
def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str, subject: str,
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini',
                      ai_provider: str = 'openai',
                      student_responses: list = None,
                      rubric_breakdown: dict = None,
                      blank_questions: list = None,
                      missing_sections: list = None) -> dict:
```

**Lines 3781–3782** — Delete the hardcoded OpenAI import+client:

```python
# DELETE (lines 3781-3782)
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
```

**Lines 3904–3932** — Replace the OpenAI-only API call with a provider switch.
The existing code is:

```python
# BEFORE (lines 3904-3932)
    try:
        response = client.beta.chat.completions.parse(
            model=ai_model,
            messages=[
                {"role": "system", "content": f"You are an encouraging grade {grade_level} {subject} teacher writing specific, actionable feedback focused on helping the student improve. Always reference actual student answers. Scale the balance of praise vs improvement guidance based on the grade, but every grade level should focus primarily on what the student needs to do to get better."},
                {"role": "user", "content": prompt}
            ],
            response_format=FeedbackResponse,
            max_tokens=3500,
            temperature=0,
            seed=42
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            result = parsed.model_dump()
            if ell_language and result.get("feedback"):
                translated = _translate_feedback(result["feedback"], ell_language, ai_model)
                if translated:
                    result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
            return result
    except Exception as e:
        print(f"  ⚠️ Feedback generation error: {e}")

    return {
        "feedback": "Good effort on this assignment. Keep working hard!",
        "excellent_answers": [],
        "needs_improvement": [],
        "skills_demonstrated": {"strengths": [], "developing": []}
    }
```

Replace with:

```python
# AFTER
    system_msg = f"You are an encouraging grade {grade_level} {subject} teacher writing specific, actionable feedback focused on helping the student improve. Always reference actual student answers. Scale the balance of praise vs improvement guidance based on the grade, but every grade level should focus primarily on what the student needs to do to get better."

    json_schema = '''Respond with ONLY valid JSON in this exact format:
{
    "feedback": "<3-4 paragraphs of personalized feedback>",
    "excellent_answers": ["<specific student answers that earned high marks>"],
    "needs_improvement": ["<specific answers that lost points, with corrections>"],
    "skills_demonstrated": {
        "strengths": ["<specific skill demonstrated>"],
        "developing": ["<specific skill to work on>"]
    }
}'''

    try:
        if ai_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            claude_model_map = {
                "claude-haiku": "claude-3-5-haiku-latest",
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }
            actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")

            response = client.messages.create(
                model=actual_model,
                max_tokens=3500,
                system=system_msg + "\n\n" + json_schema,
                messages=[{"role": "user", "content": prompt}]
            )
            result = _try_parse_json_fallback(response.content[0].text.strip())
            if result and "feedback" in result:
                # Ensure skills_demonstrated has correct structure
                if "skills_demonstrated" not in result or not isinstance(result["skills_demonstrated"], dict):
                    result["skills_demonstrated"] = {"strengths": [], "developing": []}
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

        elif ai_provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            gemini_model_map = {
                "gemini-flash": "gemini-2.0-flash",
                "gemini-pro": "gemini-2.0-pro-exp",
            }
            actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
            gemini_client = genai.GenerativeModel(actual_model)

            full_prompt = system_msg + "\n\n" + json_schema + "\n\n---\n\n" + prompt
            response = gemini_client.generate_content(full_prompt)
            result = _try_parse_json_fallback(response.text.strip())
            if result and "feedback" in result:
                if "skills_demonstrated" not in result or not isinstance(result["skills_demonstrated"], dict):
                    result["skills_demonstrated"] = {"strengths": [], "developing": []}
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

        else:  # OpenAI — use structured output
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.beta.chat.completions.parse(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                response_format=FeedbackResponse,
                max_tokens=3500,
                temperature=0,
                seed=42
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                result = parsed.model_dump()
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

    except Exception as e:
        print(f"  ⚠️ Feedback generation error ({ai_provider}): {e}")

    return {
        "feedback": "Good effort on this assignment. Keep working hard!",
        "excellent_answers": [],
        "needs_improvement": [],
        "skills_demonstrated": {"strengths": [], "developing": []}
    }
```

---

## Summary of all changes

| # | Location | What |
|---|----------|------|
| 1 | Line 3378–3384 | Set `use_multipass = True` for all providers |
| 2 | Line 3949 | Add provider detection in `grade_multipass()` |
| 3 | Line 4046–4060 | Pass `ai_provider=provider` to `grade_per_question()` |
| 4 | Line 4184–4196 | Pass `ai_provider=provider` to `generate_feedback()`, use selected model |
| 5 | Line 3617–3755 | Add `ai_provider` param to `grade_per_question()`, replace OpenAI-only call with provider switch |
| 6 | Line 3760–3932 | Add `ai_provider` param to `generate_feedback()`, replace OpenAI-only call with provider switch |

## Key design decisions

- **OpenAI keeps structured output** (`response_format=PerQuestionResponse`) — it's more
  reliable than JSON-in-prompt and already works.
- **Claude/Gemini use JSON-in-system-prompt** with `_try_parse_json_fallback()` for parsing.
  This helper already exists (line 4390) and handles markdown fences, missing commas, etc.
- **`generate_feedback` was hardcoded to `gpt-4o-mini`** even when the teacher selected
  Claude/Gemini. Change 4 fixes this — OpenAI still uses `gpt-4o-mini` (cheaper for text
  generation), but Claude/Gemini use the teacher's selected model.
- **`_translate_feedback` already supports all three providers** (line 4323) — no changes needed.
- **Fallback**: If multipass extraction finds zero responses, it already falls back to
  single-pass `grade_assignment()` (line 3982), which supports all three providers. This
  safety net is unchanged.

## Cost considerations

- **OpenAI**: No change — same multipass behavior as before.
- **Claude Haiku**: ~$0.001/question (300 tokens output). A 10-question assignment ≈ $0.01
  for grading + $0.005 for feedback. Comparable to `gpt-4o-mini`.
- **Gemini Flash**: Free tier covers most usage. Paid tier is cheaper than OpenAI.
- **Claude Sonnet/Opus**: More expensive per call but produces better quality. A 10-question
  assignment with Sonnet ≈ $0.05. Teachers choosing Sonnet/Opus already accept higher cost.
