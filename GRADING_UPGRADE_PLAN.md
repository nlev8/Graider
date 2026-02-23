# Graider AI Grading Upgrade Plan
## From Single-Pass to Multi-Pass Structured Grading

---

## Overview

Replace the current single-pass monolithic grading prompt (~4,000+ tokens of competing instructions) with a focused multi-pass pipeline. Each pass has a single responsibility, uses the cheapest model that can handle it, and produces structured output.

**Current flow:**
```
Student doc → extract responses → ONE massive GPT call (grade + detect AI + detect plagiarism + generate feedback + format JSON) → parse JSON with fix_claude_json()
```

**New flow:**
```
Student doc → extract responses → Pass 1: Per-question grading (GPT-4o, structured output)
                                → Pass 2: Feedback generation (GPT-4o-mini)
                                → Parallel: AI/plagiarism detection (writing style baseline, advisory only)
                                → Aggregate: Calibrate scores, build final result
```

**Cost estimate per class of 30:** ~$0.35 (vs current ~$0.23 single-pass, but far more consistent)

---

## Phase 1: Structured Outputs (Eliminate JSON Parsing Errors)

**File:** `assignment_grader.py`

### 1A. Add Pydantic models for grading response

**Insert at line ~30** (after existing imports):

```python
# Structured output models for reliable JSON responses
from pydantic import BaseModel
from typing import List, Optional

class GradingBreakdown(BaseModel):
    content_accuracy: int
    completeness: int
    writing_quality: int
    effort_engagement: int

class SkillsDemonstrated(BaseModel):
    strengths: List[str]
    developing: List[str]

class AiDetectionResult(BaseModel):
    flag: str  # "none", "unlikely", "possible", "likely"
    confidence: int
    reason: str

class PlagiarismDetectionResult(BaseModel):
    flag: str  # "none", "possible", "likely"
    reason: str

class GradingResponse(BaseModel):
    score: int
    letter_grade: str
    breakdown: GradingBreakdown
    student_responses: List[str]
    unanswered_questions: List[str]
    excellent_answers: List[str]
    needs_improvement: List[str]
    skills_demonstrated: SkillsDemonstrated
    ai_detection: AiDetectionResult
    plagiarism_detection: PlagiarismDetectionResult
    feedback: str

class DetectionResponse(BaseModel):
    ai_detection: AiDetectionResult
    plagiarism_detection: PlagiarismDetectionResult
```

### 1B. Replace OpenAI API call with structured output

**Replace lines 3954-3962** (the OpenAI API call block):

```python
        else:
            # OpenAI API call with structured output
            response = openai_client.beta.chat.completions.parse(
                model=ai_model,
                messages=messages,
                response_format=GradingResponse,
                max_tokens=2000,
                temperature=0,
                seed=42
            )
            parsed = response.choices[0].message.parsed
            if parsed:
                result = parsed.model_dump()
                # Skip all JSON parsing below — go straight to post-processing
                # (see 1C for the refactored flow)
            else:
                # Fallback: model refused or failed to parse
                response_text = response.choices[0].message.content or ""
                # Fall through to existing JSON parsing logic below
```

### 1C. Replace detection API call with structured output

**Replace lines 2714-2735** (in `detect_ai_plagiarism`):

```python
    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": detection_prompt}],
            response_format=DetectionResponse,
            max_tokens=500,
            temperature=0.1,
            seed=42
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            return parsed.model_dump()

        # Fallback to text parsing if structured output fails
        response_text = response.choices[0].message.content or ""
```

### 1D. Set temperature=0 and seed=42 globally

**Replace line 3960:**
```python
# OLD:
                temperature=0.3

# NEW:
                temperature=0,
                seed=42
```

**Also replace line 2719:**
```python
# OLD:
            temperature=0.1

# NEW:
            temperature=0,
            seed=42
```

**Note:** Claude and Gemini don't support `seed`, so only apply to OpenAI calls. Claude/Gemini calls keep existing temperature settings. The `fix_claude_json()` function and regex fallback remain as fallbacks for non-OpenAI providers only.

---

## Phase 2: Multi-Pass Grading Architecture

**File:** `assignment_grader.py`

### 2A. New function: `grade_per_question()`

**Insert after `grade_with_parallel_detection()` (~line 3008):**

This replaces the monolithic prompt with individual per-question grading. Each question gets its own focused API call.

```python
class QuestionGrade(BaseModel):
    score: int
    possible: int
    reasoning: str
    is_correct: bool
    quality: str  # "excellent", "good", "adequate", "developing", "insufficient"

class PerQuestionResponse(BaseModel):
    grade: QuestionGrade
    excellent: bool  # Whether this is a standout answer
    improvement_note: str  # Specific guidance if not excellent


def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       custom_instructions: str, accommodation_context: str,
                       grading_style: str, ai_model: str = 'gpt-4o') -> dict:
    """Grade a single question/response pair with focused prompt.

    Returns dict with score, reasoning, quality label, etc.
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    style_note = {
        'lenient': 'Be generous — accept partial understanding and alternate phrasings.',
        'strict': 'Grade precisely against the expected answer. Partial credit for partial understanding.',
        'standard': 'Give credit for demonstrated understanding. Accept reasonable synonyms.'
    }.get(grading_style, '')

    # Score anchors based on point value
    excellent_min = int(points * 0.9)
    good_min = int(points * 0.75)
    adequate_min = int(points * 0.6)
    developing_min = int(points * 0.4)

    prompt = f"""Grade this single student response.

QUESTION: {question}
STUDENT ANSWER: "{student_answer}"
{f'EXPECTED ANSWER: {expected_answer}' if expected_answer else ''}
POINTS POSSIBLE: {points}

CONTEXT: Grade {grade_level} {subject} student.
{custom_instructions}
{accommodation_context}
{style_note}

SCORE ANCHORS for {points} points:
- Excellent ({excellent_min}-{points}): Correct, complete, shows understanding
- Good ({good_min}-{excellent_min - 1}): Mostly correct, minor gaps
- Adequate ({adequate_min}-{good_min - 1}): Partial understanding shown
- Developing ({developing_min}-{adequate_min - 1}): Minimal understanding
- Insufficient (0-{developing_min - 1}): Incorrect or no meaningful attempt

RULES:
- Accept synonyms and age-appropriate language
- Do NOT penalize spelling if meaning is clear
- Grade the CONTENT, not the writing style
- If blank/empty, score is 0"""

    try:
        response = client.beta.chat.completions.parse(
            model=ai_model,
            messages=[
                {"role": "system", "content": f"You are a fair, encouraging grade {grade_level} {subject} teacher."},
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

    # Fallback: return neutral score
    return {
        "grade": {"score": int(points * 0.7), "possible": points,
                  "reasoning": "Grading error - default score applied",
                  "is_correct": True, "quality": "adequate"},
        "excellent": False,
        "improvement_note": ""
    }
```

### 2B. New function: `generate_feedback()`

**Insert after `grade_per_question()`:**

Dedicated feedback generation using cheaper model, with per-question results as context.

```python
class FeedbackResponse(BaseModel):
    feedback: str
    excellent_answers: List[str]
    needs_improvement: List[str]
    skills_demonstrated: SkillsDemonstrated


def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str, subject: str,
                      history_context: str, ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini') -> dict:
    """Generate warm, personalized teacher feedback from per-question grades.

    Uses the cheaper model since this is creative writing, not evaluation.
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build summary of graded questions
    summary_lines = []
    for i, qr in enumerate(question_results, 1):
        g = qr.get("grade", {})
        summary_lines.append(
            f"Q{i}: {g.get('score', 0)}/{g.get('possible', 10)} "
            f"({g.get('quality', 'unknown')}) - {g.get('reasoning', '')[:100]}"
        )

    prompt = f"""Write 3-4 paragraphs of warm, personalized teacher feedback for a grade {grade_level} {subject} student.

SCORE: {total_score}/{total_possible} ({letter_grade})

PER-QUESTION RESULTS:
{chr(10).join(summary_lines)}

{history_context}

REQUIREMENTS:
- Sound like a real teacher — warm, encouraging, specific
- Quote specific strong answers when praising
- For weak areas, be gentle and give hints toward the right answer
- Use contractions, casual phrases ("Nice!", "Great thinking here")
- Vary sentence structure — don't start every sentence the same way
- Do NOT use the student's name — say "you" or "your"
- End with genuine encouragement tied to something specific they did well
- If student history is provided, reference their progress and streaks

Also identify:
- 2-4 excellent answers (quote specific student text)
- 1-3 areas needing improvement (with constructive guidance)
- 2-4 specific skills demonstrated as strengths
- 1-2 skills that are developing"""

    try:
        response = client.beta.chat.completions.parse(
            model=ai_model,
            messages=[
                {"role": "system", "content": f"You are an encouraging grade {grade_level} {subject} teacher writing personalized feedback."},
                {"role": "user", "content": prompt}
            ],
            response_format=FeedbackResponse,
            max_tokens=1000,
            temperature=0.4,  # Slightly creative for natural feedback
            seed=42
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            result = parsed.model_dump()
            # Handle bilingual translation as post-step (unchanged from current)
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

### 2C. New orchestrator function: `grade_multipass()`

**Insert after `generate_feedback()`:**

This is the new entry point that replaces `grade_assignment()` for OpenAI models.

```python
def grade_multipass(student_name: str, assignment_data: dict, custom_ai_instructions: str = '',
                    grade_level: str = '6', subject: str = 'Social Studies',
                    ai_model: str = 'gpt-4o-mini', student_id: str = None,
                    assignment_template: str = None, rubric_prompt: str = None,
                    custom_markers: list = None, exclude_markers: list = None,
                    marker_config: list = None, effort_points: int = 15,
                    extraction_mode: str = 'structured', grading_style: str = 'standard') -> dict:
    """Multi-pass grading pipeline for consistent, robust scoring.

    Pass 1: Extract responses (already done by caller)
    Pass 2: Grade each question individually (GPT-4o, parallel)
    Pass 3: Generate feedback (GPT-4o-mini)
    Parallel: AI/plagiarism detection (writing style baseline)
    Final: Aggregate scores, apply caps, build result
    """
    content = assignment_data.get("content", "")

    # === EXTRACTION (same as current — reuse existing logic) ===
    extraction_result = None
    extracted_responses_text = ""
    if assignment_data.get("type") == "text" and content:
        extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
        if extraction_result:
            extracted_responses_text = format_extracted_for_grading(extraction_result, marker_config, extraction_mode)
            answered = extraction_result.get("answered_questions", 0)
            total = extraction_result.get("total_questions", 0)
            print(f"  📋 Extracted {answered}/{total} responses")

            if answered == 0:
                return {
                    "score": 0, "letter_grade": "INCOMPLETE",
                    "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                    "feedback": "This assignment appears to be blank or incomplete. No student responses were found.",
                    "student_responses": [], "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                    "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                    "plagiarism_detection": {"flag": "none", "reason": ""},
                    "skills_demonstrated": {"strengths": [], "developing": []},
                    "excellent_answers": [], "needs_improvement": []
                }

    if not extraction_result or not extraction_result.get("extracted_responses"):
        # Fall back to single-pass for edge cases (images, extraction failure)
        return grade_assignment(student_name, assignment_data, custom_ai_instructions,
                               grade_level, subject, ai_model, student_id, assignment_template,
                               rubric_prompt, custom_markers, exclude_markers, marker_config,
                               effort_points, extraction_mode, grading_style)

    responses = extraction_result["extracted_responses"]

    # Build expected answers lookup from gradingNotes in custom_ai_instructions
    expected_answers = _parse_expected_answers(custom_ai_instructions)

    # Build accommodation context
    accommodation_context = ""
    if student_id and student_id != "UNKNOWN":
        accommodation_context = build_accommodation_prompt(student_id)

    # Build history context
    history_context = ""
    if student_id and student_id != "UNKNOWN":
        history_context = build_history_context(student_id)

    # === PASS 2: PER-QUESTION GRADING (parallel) ===
    print(f"  🔄 Grading {len(responses)} questions individually...")

    # Determine points per question from marker_config or distribute evenly
    total_content_points = 100 - effort_points  # Reserve effort points
    question_points = _distribute_points(responses, marker_config, total_content_points)

    # Use the more expensive model for actual grading
    grading_model = ai_model if 'mini' not in ai_model else ai_model.replace('-mini', '')

    question_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for i, resp in enumerate(responses):
            question = resp.get("question", f"Question {i+1}")
            answer = resp.get("answer", "")
            expected = expected_answers.get(i) or expected_answers.get(question, "")
            pts = question_points[i] if i < len(question_points) else 10

            futures.append(executor.submit(
                grade_per_question,
                question=question,
                student_answer=answer,
                expected_answer=expected,
                points=pts,
                grade_level=grade_level,
                subject=subject,
                custom_instructions=custom_ai_instructions[:500],  # Truncate for per-Q prompt
                accommodation_context=accommodation_context[:300],
                grading_style=grading_style,
                ai_model=grading_model
            ))

        for future in concurrent.futures.as_completed(futures):
            question_results.append(future.result())

    # Reorder results to match original question order
    # (as_completed returns in completion order, not submission order)
    # Use indexed submission instead:
    question_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_idx = {}
        for i, resp in enumerate(responses):
            question = resp.get("question", f"Question {i+1}")
            answer = resp.get("answer", "")
            expected = expected_answers.get(i) or expected_answers.get(question, "")
            pts = question_points[i] if i < len(question_points) else 10

            f = executor.submit(
                grade_per_question, question, answer, expected, pts,
                grade_level, subject, custom_ai_instructions[:500],
                accommodation_context[:300], grading_style, grading_model
            )
            future_to_idx[f] = i

        indexed_results = [None] * len(responses)
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            indexed_results[idx] = future.result()
        question_results = indexed_results

    # === AGGREGATE SCORES ===
    total_earned = sum(qr.get("grade", {}).get("score", 0) for qr in question_results if qr)
    total_possible = sum(qr.get("grade", {}).get("possible", 10) for qr in question_results if qr)

    # Add effort points based on completion
    blank_count = len(extraction_result.get("blank_questions", [])) + len(extraction_result.get("missing_sections", []))
    if blank_count == 0:
        effort_earned = effort_points
    elif blank_count == 1:
        effort_earned = int(effort_points * 0.7)
    elif blank_count == 2:
        effort_earned = int(effort_points * 0.4)
    else:
        effort_earned = int(effort_points * 0.2)

    raw_score = int(round((total_earned / max(total_possible, 1)) * (100 - effort_points) + effort_earned))
    raw_score = max(0, min(100, raw_score))

    # Apply completeness caps (same logic as current)
    if grading_style == 'strict':
        caps = {0: 100, 1: 85, 2: 75, 3: 65}
    elif grading_style == 'lenient':
        caps = {0: 100, 1: 95, 2: 89, 3: 79}
    else:
        caps = {0: 100, 1: 89, 2: 79, 3: 69}
    cap = caps.get(min(blank_count, 3), 60 if blank_count >= 4 else 69)
    final_score = min(raw_score, cap)

    # Letter grade
    if final_score >= 90: letter_grade = "A"
    elif final_score >= 80: letter_grade = "B"
    elif final_score >= 70: letter_grade = "C"
    elif final_score >= 60: letter_grade = "D"
    else: letter_grade = "F"

    print(f"  📊 Per-question scores: {[qr.get('grade', {}).get('score', 0) for qr in question_results if qr]}")
    print(f"  📊 Raw: {raw_score}, Cap: {cap}, Final: {final_score} ({letter_grade})")

    # === PASS 3: FEEDBACK GENERATION (cheap model, parallel with detection) ===
    # Load ELL language
    ell_language = None
    if student_id and student_id != "UNKNOWN":
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        if os.path.exists(ell_file):
            try:
                with open(ell_file, 'r', encoding='utf-8') as f:
                    ell_data = json.load(f)
                ell_entry = ell_data.get(student_id, {})
                lang = ell_entry.get("language")
                if lang and lang != "none":
                    ell_language = lang
            except Exception:
                pass

    feedback_result = generate_feedback(
        question_results=question_results,
        total_score=final_score,
        total_possible=100,
        letter_grade=letter_grade,
        grade_level=grade_level,
        subject=subject,
        history_context=history_context,
        ell_language=ell_language,
        ai_model='gpt-4o-mini'
    )

    # === BUILD BREAKDOWN ===
    content_pts = int(round((total_earned / max(total_possible, 1)) * 40))
    completeness_pts = max(0, 25 - (blank_count * 6))
    writing_pts = 15  # Default — multi-pass doesn't separately assess writing quality
    # Adjust writing quality based on question quality distribution
    qualities = [qr.get("grade", {}).get("quality", "adequate") for qr in question_results if qr]
    if qualities.count("excellent") + qualities.count("good") > len(qualities) * 0.7:
        writing_pts = 18
    elif qualities.count("developing") + qualities.count("insufficient") > len(qualities) * 0.5:
        writing_pts = 10

    # === BUILD FINAL RESULT ===
    student_response_texts = [resp.get("answer", "")[:500] for resp in responses if resp.get("answer")]

    result = {
        "score": final_score,
        "letter_grade": letter_grade,
        "breakdown": {
            "content_accuracy": min(content_pts, 40),
            "completeness": min(completeness_pts, 25),
            "writing_quality": min(writing_pts, 20),
            "effort_engagement": effort_earned
        },
        "student_responses": student_response_texts,
        "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
        "excellent_answers": feedback_result.get("excellent_answers", []),
        "needs_improvement": feedback_result.get("needs_improvement", []),
        "skills_demonstrated": feedback_result.get("skills_demonstrated", {"strengths": [], "developing": []}),
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
        "feedback": feedback_result.get("feedback", ""),
        "multipass_grading": True,
        "per_question_scores": [
            {"question": responses[i].get("question", "")[:60],
             "score": qr.get("grade", {}).get("score", 0),
             "possible": qr.get("grade", {}).get("possible", 10),
             "quality": qr.get("grade", {}).get("quality", "")}
            for i, qr in enumerate(question_results) if qr
        ]
    }

    # Update writing profile
    if student_id and student_id != "UNKNOWN" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            try:
                update_writing_profile(student_id, current_writing_style, student_name)
            except Exception:
                pass

    return result
```

### 2D. Helper functions for multi-pass

**Insert before `grade_multipass()`:**

```python
def _parse_expected_answers(custom_instructions: str) -> dict:
    """Parse expected answers from gradingNotes/custom instructions.

    Returns dict mapping question index (int) or question text (str) to expected answer.
    """
    answers = {}
    if not custom_instructions:
        return answers

    # Parse "Q1: answer" or "- Q1: answer" patterns
    for match in re.finditer(r'(?:^|\n)\s*-?\s*Q(\d+)\s*:\s*(.+)', custom_instructions):
        idx = int(match.group(1)) - 1  # 0-indexed
        answers[idx] = match.group(2).strip()

    # Parse "VOCABULARY EXPECTED DEFINITIONS:" section
    in_vocab = False
    for line in custom_instructions.split('\n'):
        line = line.strip()
        if 'EXPECTED' in line.upper() and ('DEFINITION' in line.upper() or 'ANSWER' in line.upper()):
            in_vocab = True
            continue
        if in_vocab and line.startswith('- '):
            # "- Term: expected definition"
            parts = line[2:].split(':', 1)
            if len(parts) == 2:
                answers[parts[0].strip()] = parts[1].strip()
        elif in_vocab and not line:
            in_vocab = False

    return answers


def _distribute_points(responses: list, marker_config: list, total_points: int) -> list:
    """Distribute point values across extracted responses.

    Uses marker_config if available, otherwise distributes evenly.
    """
    if not responses:
        return []

    # Build marker points lookup
    marker_points = {}
    if marker_config:
        for m in marker_config:
            if isinstance(m, dict):
                marker_points[m.get('start', '').lower()] = m.get('points', 10)

    points = []
    for resp in responses:
        question = resp.get("question", "").lower()
        assigned = None
        for marker_key, pts in marker_points.items():
            if marker_key in question:
                assigned = pts
                break
        if assigned:
            points.append(assigned)
        else:
            # Default: distribute evenly
            points.append(total_points // len(responses))

    return points
```

### 2E. Wire multi-pass into `grade_with_parallel_detection()`

**Replace lines 2912-2920** (the ThreadPoolExecutor block):

```python
    # Determine grading strategy
    provider = "openai"
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"

    # Multi-pass grading for OpenAI models; single-pass for Claude/Gemini
    use_multipass = provider == "openai"

    print(f"  🔄 Running parallel detection + {'multi-pass' if use_multipass else 'single-pass'} grading...")

    # Preprocess text for AI detection
    detection_text = preprocess_for_ai_detection(extracted_text)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        detection_future = executor.submit(detect_ai_plagiarism, detection_text, grade_level)

        if use_multipass:
            grading_future = executor.submit(grade_multipass, student_name, assignment_data,
                                             custom_ai_instructions, grade_level, subject,
                                             ai_model, student_id, assignment_template, rubric_prompt,
                                             custom_markers, exclude_markers, marker_config, effort_points,
                                             extraction_mode, grading_style)
        else:
            grading_future = executor.submit(grade_assignment, student_name, assignment_data,
                                             custom_ai_instructions, grade_level, subject,
                                             ai_model, student_id, assignment_template, rubric_prompt,
                                             custom_markers, exclude_markers, marker_config, effort_points,
                                             extraction_mode, grading_style)

        detection_result = detection_future.result()
        grading_result = grading_future.result()
```

---

## Phase 3: AI Detection → Advisory Only

**File:** `assignment_grader.py`

### 3A. Remove automatic score caps

**Replace lines 2949-2987** (the score cap block in `grade_with_parallel_detection`):

```python
    # AI/plagiarism detection is ADVISORY — flag for teacher review, don't auto-penalize
    ai_flag = grading_result.get("ai_detection", {}).get("flag", "none")
    plag_flag = grading_result.get("plagiarism_detection", {}).get("flag", "none")

    if ai_flag in ["possible", "likely"] or plag_flag in ["possible", "likely"]:
        grading_result["academic_integrity_review"] = True
        grading_result["detection_advisory"] = {
            "ai": {"flag": ai_flag, "reason": grading_result.get("ai_detection", {}).get("reason", "")},
            "plagiarism": {"flag": plag_flag, "reason": grading_result.get("plagiarism_detection", {}).get("reason", "")}
        }
        print(f"  ⚠️  Advisory: AI={ai_flag}, Plagiarism={plag_flag} — flagged for teacher review")

    # DO NOT auto-cap scores. Teacher reviews and decides.
    # Original score preserved. Teacher can manually adjust in Results tab.
```

### 3B. Remove feedback replacement for detection flags

**Replace lines 2989-3006** (the feedback replacement block):

```python
    # Blank submission handling (keep this)
    student_responses = grading_result.get("student_responses", [])
    is_blank = not student_responses and not grading_result.get("json_recovery")

    if is_blank:
        grading_result["feedback"] = "You submitted a blank assignment. Please resubmit a completed version."
        grading_result["score"] = 0
        grading_result["letter_grade"] = "F"
        print(f"  📝 Blank submission detected")
    # Advisory note appended to feedback (not replacing it)
    elif grading_result.get("academic_integrity_review"):
        grading_result["feedback"] += "\n\n⚠️ Note for teacher: This submission has been flagged for academic integrity review. Please check the AI/plagiarism detection details before finalizing this grade."
```

### 3C. Frontend: Show advisory banner in Results tab

**File:** `frontend/src/App.jsx`

In the Results table row rendering, add a visual indicator when `academic_integrity_review` is true:

```javascript
// In the results row where detection flags are displayed:
// Replace the automatic "FLAGGED" badge with a teacher-review badge

{result.academic_integrity_review && (
    <span style={{
        background: '#FEF3C7', color: '#92400E', padding: '2px 8px',
        borderRadius: '4px', fontSize: '11px', fontWeight: 600
    }}>
        🔍 REVIEW
    </span>
)}
```

This replaces any existing hard "FLAGGED" styling that implies guilt. The teacher clicks to see details and decides whether to adjust the grade.

---

## Phase 4: Few-Shot Score Anchors

**File:** `assignment_grader.py`

### 4A. Auto-generate score anchors from gradingNotes

**Add to `grade_per_question()` prompt, after the SCORE ANCHORS section:**

```python
    # Build example anchors from expected answer if available
    anchor_section = ""
    if expected_answer:
        anchor_section = f"""
REFERENCE ANSWER (use to calibrate scoring):
- Full credit answer: "{expected_answer}"
- Partial credit: Any response that captures the main idea, even with different wording
- No credit: Blank, completely off-topic, or copied the question back"""
```

This is already handled in Phase 2's `grade_per_question()` via the `EXPECTED ANSWER` field. The score anchors (excellent/good/adequate/developing/insufficient) with exact point ranges provide the calibration.

### 4B. Add calibration examples to single-pass prompt (for Claude/Gemini fallback)

**In the existing `grade_assignment()` prompt_text, add after line 3757 ("GRADING GUIDELINES:"):**

```python
    # Build calibration examples from gradingNotes
    calibration_section = ""
    if custom_ai_instructions and "EXPECTED ANSWERS:" in custom_ai_instructions:
        calibration_section = f"""
CALIBRATION - USE THESE TO ANCHOR YOUR SCORING:
- An answer that matches or closely paraphrases the expected answer = full credit for that question
- An answer that captures the main idea but misses details = 70-85% credit
- An answer that shows minimal understanding = 40-60% credit
- A blank or completely wrong answer = 0% credit
"""
```

---

## Phase 5: Post-Batch Calibration

**File:** `backend/app.py`

### 5A. Add calibration check after grading completes

In the grading loop completion handler (where all students have been graded), add:

```python
def check_batch_calibration(results: list, assignment_name: str) -> dict:
    """Check if grading results have anomalous distribution.

    Returns advisory dict with any concerns.
    """
    scores = [r.get("score", 0) for r in results if r.get("letter_grade") not in ("ERROR", "MANUAL REVIEW")]
    if len(scores) < 5:
        return {"calibrated": True}

    import statistics
    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    ai_flagged = sum(1 for r in results if r.get("academic_integrity_review"))

    concerns = []
    if mean > 95:
        concerns.append(f"Mean score is {mean:.0f} — unusually high, grading may be too lenient")
    elif mean < 55:
        concerns.append(f"Mean score is {mean:.0f} — unusually low, check rubric or extraction")

    if stdev < 5 and len(scores) > 10:
        concerns.append(f"Standard deviation is only {stdev:.1f} — scores are suspiciously uniform")

    if ai_flagged > len(results) * 0.3:
        concerns.append(f"{ai_flagged}/{len(results)} flagged for AI — detection may be oversensitive")

    return {
        "calibrated": len(concerns) == 0,
        "mean": round(mean, 1),
        "stdev": round(stdev, 1),
        "concerns": concerns,
        "ai_flagged_count": ai_flagged
    }
```

Call this at the end of the grading loop and append to `grading_state`:

```python
# After all students graded:
calibration = check_batch_calibration(grading_state["results"], assignment_name)
if not calibration["calibrated"]:
    grading_state["log"].append(f"⚠️ CALIBRATION WARNING: {'; '.join(calibration['concerns'])}")
    grading_state["calibration"] = calibration
```

---

## Phase 6: Template Diffing for All Types

**File:** `assignment_grader.py`

### 6A. Generalize template diffing beyond FITB

The existing `extract_fitb_by_template_comparison()` (line 299) already diffs template vs student doc. Extend this approach:

**Add new function after `extract_fitb_by_template_comparison()`:**

```python
def extract_by_template_diff(student_text: str, template_text: str) -> list:
    """Extract student responses by diffing against the assignment template.

    Compares student document against the original template line-by-line.
    Any content in the student doc that differs from the template is a student response.

    Returns list of {"question": template_line, "answer": student_content, "type": "template_diff"}
    """
    if not template_text or not student_text:
        return []

    import difflib

    template_lines = [l.strip() for l in template_text.split('\n') if l.strip()]
    student_lines = [l.strip() for l in student_text.split('\n') if l.strip()]

    # Use SequenceMatcher to align template and student lines
    matcher = difflib.SequenceMatcher(None, template_lines, student_lines)

    responses = []
    current_question = ""

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Lines match template — these are prompts/headers
            # Use the last template line as context for the next response
            if i2 > i1:
                current_question = template_lines[i2 - 1]
        elif tag == 'insert':
            # Lines in student doc NOT in template — these are student responses
            student_content = '\n'.join(student_lines[j1:j2])
            # Skip blank lines and underscore-only lines
            if student_content.strip() and student_content.replace('_', '').strip():
                responses.append({
                    "question": current_question or f"Section at line {j1}",
                    "answer": student_content,
                    "type": "template_diff"
                })
        elif tag == 'replace':
            # Template line was replaced with different content — student filled in
            template_content = '\n'.join(template_lines[i1:i2])
            student_content = '\n'.join(student_lines[j1:j2])
            if student_content.strip() and student_content != template_content:
                responses.append({
                    "question": template_content[:200],
                    "answer": student_content,
                    "type": "template_diff"
                })

    return responses
```

**In `extract_student_responses()`, add template diff as a fallback** when marker-based extraction finds few results:

```python
    # After marker extraction, if few responses found and template available:
    if assignment_template and len(extracted) < 2:
        diff_responses = extract_by_template_diff(content, assignment_template)
        if len(diff_responses) > len(extracted):
            print(f"  📄 Template diff found {len(diff_responses)} responses (marker extraction found {len(extracted)})")
            extracted = diff_responses
```

---

## Implementation Order

| Phase | Effort | Impact | Dependencies |
|-------|--------|--------|-------------|
| 1: Structured Outputs | Small | High | None — standalone improvement |
| 2: Multi-Pass Grading | Large | High | Phase 1 (structured outputs) |
| 3: Advisory Detection | Small | Medium | None — standalone |
| 4: Score Anchors | Small | Medium | Phase 2 (per-question prompts) |
| 5: Batch Calibration | Small | Medium | None — standalone |
| 6: Template Diffing | Medium | Medium | None — standalone |

**Recommended order:** Phase 1 → Phase 3 → Phase 5 → Phase 2 → Phase 4 → Phase 6

Start with quick wins (1, 3, 5) that don't change the grading architecture, then tackle the multi-pass rewrite (2, 4, 6).

---

## Rollback Strategy

The `grade_multipass()` function falls back to `grade_assignment()` for:
- Non-OpenAI models (Claude, Gemini) — they don't support structured outputs
- Image submissions — can't do per-question grading on images
- Extraction failures — no structured responses to grade individually

The `use_multipass` flag in `grade_with_parallel_detection()` controls the switch. To rollback, simply set `use_multipass = False`.

---

## Testing Plan

1. **Phase 1**: Grade 5 students with current prompt, verify JSON parses without `fix_claude_json()` ever being called
2. **Phase 2**: Grade same 5 students with multi-pass, compare scores to single-pass (should be within 5 points)
3. **Phase 3**: Verify detection flags appear as advisory badges, not auto-caps
4. **Phase 5**: Grade a full class, verify calibration check runs and catches anomalies
5. **Regression**: Ensure FITB, Cornell Notes, vocabulary, short-answer all still work correctly
