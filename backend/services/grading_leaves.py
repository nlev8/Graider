"""Leaf LLM callers for the multi-pass grading pipeline: the single-purpose functions that make
one provider call each (per-question grading, AI/plagiarism detection, feedback generation,
ELL translation). Extracted from assignment_grader.py. Wave 7 Phase B (grading-engine
decomposition).

These call the RAW openai / anthropic / google-generativeai SDKs inline (function-local
imports), each wrapped in with_retry(..., label=...). API keys resolve via backend.api_keys
(env / contextvars / per-teacher / district). Response schemas + token accounting come from
backend.services.grading_models. Diagnostic prints became _logger calls on extraction; the
RETURN VALUES (the grading contract) are unchanged and pinned by the SDK-fake golden net
(tests/test_grader_golden.py).
"""
import json
import logging

from backend.api_keys import get_api_key as _get_api_key
from backend.retry import with_retry
from backend.services.grader_json import _try_parse_json_fallback
from backend.services.grading_models import DetectionResponse, FeedbackResponse, PerQuestionResponse, TokenTracker
from backend.services.grading_prep import _is_math_subject

_logger = logging.getLogger(__name__)


def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       teacher_instructions: str, grading_style: str,
                       ai_model: str = 'gpt-4o',
                       ai_provider: str = 'openai',
                       response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written',
                       token_tracker: 'TokenTracker' = None) -> dict:
    """Grade a single question/response pair with full section-aware context.

    Args:
        teacher_instructions: FULL untruncated instructions from app.py. Contains:
            global AI notes, assignment-specific gradingNotes, rubric type overrides,
            accommodation prompts, student history, period differentiation + rubric
            weight adjustments. This is the same string the single-pass gets.
        response_type: One of 'vocab_term', 'numbered_question', 'marker_response', 'fitb_full', 'fill_in_blank'
        section_name: The marker/section this response belongs to (e.g., 'VOCABULARY', 'SUMMARY')
        section_type: The section grading type from marker_config (e.g., 'written', 'fill-in-blank')

    Returns dict with score, reasoning, quality label.
    """
    # Build section-specific grading instructions based on response type
    type_instructions = ""
    if response_type == 'vocab_term':
        type_instructions = """SECTION TYPE: VOCABULARY DEFINITION
- The student was asked to define a vocabulary term
- Grade based on whether the definition captures the correct meaning
- Accept age-appropriate paraphrasing — do NOT require textbook-exact definitions
- A definition that shows understanding of the concept = full credit
- A partially correct definition = partial credit
- A blank or completely wrong definition = 0
- IMPORTANT: Check the TEACHER'S GRADING INSTRUCTIONS below — if the teacher has modified
  how vocabulary should be scored (e.g., requesting leniency, accepting general definitions,
  going easy on vocab, relaxing requirements), follow the teacher's instructions INSTEAD of
  these defaults. The teacher knows their students and their intent overrides default rubric."""
    elif response_type == 'numbered_question':
        type_instructions = """SECTION TYPE: NUMBERED QUESTION
- The student answered a specific numbered question from the assignment
- Grade based on content accuracy and completeness of the answer
- Accept age-appropriate language and reasoning"""
    elif response_type in ('fitb_full', 'fill_in_blank'):
        type_instructions = """SECTION TYPE: FILL-IN-THE-BLANK
- The student filled in blanks in a structured worksheet
- Grade based on factual correctness of each filled-in answer
- Accept synonyms and alternate phrasings that are factually correct
- Spelling errors should NOT be penalized if the meaning is clear"""
    elif section_name and 'summary' in section_name.lower():
        type_instructions = """SECTION TYPE: SUMMARY / WRITTEN RESPONSE
- The student wrote a summary or extended response
- Grade based on: Does it capture the key ideas? Is it in their own words?
- Look for evidence of understanding, not just copying
- Evaluate completeness — did they address the main points?"""
    elif response_type == 'math_equation' or _is_math_subject(subject):
        type_instructions = """SECTION TYPE: MATH EQUATION / CALCULATION
- Accept mathematically equivalent forms (e.g., x(x+2) = x^2+2x)
- Accept equivalent fractions, decimals, and percentages (1/2 = 0.5 = 50%)
- Award partial credit for correct method with arithmetic errors
- If student shows work, evaluate the process even if final answer is wrong
- Do NOT penalize notation differences (2x vs 2*x vs 2·x)
- Evaluate mathematical correctness, not formatting"""
    elif section_type == 'written' and section_name:
        type_instructions = f"""SECTION TYPE: WRITTEN RESPONSE ({section_name})
- Grade based on quality, completeness, and demonstrated understanding
- Look for genuine engagement with the material"""

    excellent_min = int(points * 0.9)
    good_min = int(points * 0.75)
    adequate_min = int(points * 0.6)
    developing_min = int(points * 0.4)

    # Build grading style instructions (matches single-pass behavior)
    if grading_style == 'lenient':
        style_instructions = """GRADING APPROACH: LENIENT
- Prioritize EFFORT over perfection. If a student attempted this, give significant credit.
- Brief answers that show understanding should receive 70-80% of points.
- Do NOT penalize short answers if they demonstrate understanding.
- When in doubt, give the student the benefit of the doubt."""
    elif grading_style == 'strict':
        style_instructions = """GRADING APPROACH: STRICT
- Hold students to high standards for their grade level.
- Brief, underdeveloped answers should be penalized.
- Full credit requires thorough responses demonstrating deep understanding.
- Partial answers receive proportionally reduced credit."""
    else:
        style_instructions = """GRADING APPROACH: STANDARD
- Balance accuracy, completeness, and effort evenly.
- Brief answers receive partial credit proportional to quality.
- Hold to grade-level expectations."""

    section_context = f"\nSECTION: {section_name}" if section_name else ""

    prompt = f"""Grade this single student response.
{section_context}
QUESTION: {question}
STUDENT ANSWER: "{student_answer}"
{f'EXPECTED ANSWER: {expected_answer}' if expected_answer else ''}
POINTS POSSIBLE: {points}

{type_instructions}

{style_instructions}

CONTEXT: Grade {grade_level} {subject} student.

DEFAULT SCORE ANCHORS for {points} points (teacher instructions below may override these):
- Excellent ({excellent_min}-{points}): Correct, complete, shows understanding
- Good ({good_min}-{excellent_min - 1}): Mostly correct, minor gaps
- Adequate ({adequate_min}-{good_min - 1}): Partial understanding shown
- Developing ({developing_min}-{adequate_min - 1}): Minimal understanding
- Insufficient (0-{developing_min - 1}): Incorrect or no meaningful attempt

RULES:
- Accept synonyms and age-appropriate language
- Do NOT penalize spelling if meaning is clear
- Grade the CONTENT, not the writing style
- If blank/empty, score is 0
- If the student answer is template/instruction text (e.g., starts with "Summarize", "Define", "Explain", "Write in complete sentences", "Use evidence from the reading"), this is NOT a student response — it is leftover assignment directions. Score it 0.
- If the student answer BEGINS with assignment prompt/question text followed by their actual response (e.g., "Explain why X happened. The reason X happened was..."), IGNORE the prompt portion entirely. Grade ONLY the student's own response that follows the prompt. Do NOT treat the prompt text as part of their answer or credit them for restating the question.

---
TEACHER'S GRADING INSTRUCTIONS — these are the HIGHEST PRIORITY and override the score anchors above.
Read these FIRST, then score accordingly:
{teacher_instructions}
---"""

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
            client = anthropic.Anthropic(api_key=_get_api_key('anthropic'))
            claude_model_map = {
                "claude-haiku": "claude-3-5-haiku-latest",
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }
            actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")

            response = with_retry(lambda: client.messages.create(
                model=actual_model,
                max_tokens=300,
                system=system_msg + "\n\n" + json_schema,
                messages=[{"role": "user", "content": prompt}]
            ), label="grade_per_question_anthropic")
            if token_tracker:
                token_tracker.record_anthropic(response, actual_model)
            result = _try_parse_json_fallback(response.content[0].text.strip())
            if result and "grade" in result:
                return result

        elif ai_provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=_get_api_key('gemini'))
            gemini_model_map = {
                "gemini-flash": "gemini-2.0-flash",
                "gemini-pro": "gemini-2.0-pro-exp",
            }
            actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
            gemini_client = genai.GenerativeModel(actual_model)

            full_prompt = system_msg + "\n\n" + json_schema + "\n\n---\n\n" + prompt
            response = with_retry(lambda: gemini_client.generate_content(full_prompt), label="grade_per_question_gemini")
            if token_tracker:
                token_tracker.record_gemini(response, actual_model)
            result = _try_parse_json_fallback(response.text.strip())
            if result and "grade" in result:
                return result

        else:  # OpenAI — use structured output
            from openai import OpenAI
            client = OpenAI(api_key=_get_api_key('openai'))
            response = with_retry(lambda: client.beta.chat.completions.parse(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                response_format=PerQuestionResponse,
                max_tokens=300,
                temperature=0,
                seed=42
            ), label="grade_per_question_structured")
            if token_tracker:
                token_tracker.record_openai(response, ai_model)
            parsed = response.choices[0].message.parsed
            if parsed:
                return parsed.model_dump()

    except Exception as e:
        # Issue #224: don't swallow AI transients. If the provider is
        # having a 5xx storm (or network is down), bubble up as
        # TransientError so Celery's `autoretry_for=(TransientError,)`
        # in `backend/tasks/grading_tasks.py` can retry instead of
        # silently producing a 0-score "grading error" submission.
        # Non-transient errors (ValueError, schema bugs) still hit the
        # fallback so one bad question doesn't kill the whole run.
        from backend.retry import is_retryable_error
        if is_retryable_error(e):
            from backend.tasks.grading_tasks import TransientError
            raise TransientError(
                f"Transient per-question grading failure ({ai_provider}): {e}"
            ) from e
        _logger.warning("Per-question grading error (%s): %s", ai_provider, e)

    return {
        "grade": {"score": 0, "possible": points,
                  "reasoning": f"Grading error - could not evaluate response ({ai_provider})",
                  "is_correct": False, "quality": "insufficient"},
        "excellent": False,
        "improvement_note": "This response could not be evaluated due to a grading error."
    }


def detect_ai_plagiarism(student_responses: str, grade_level: str = '6', token_tracker: 'TokenTracker' = None) -> dict:
    """
    Dedicated AI/Plagiarism detection using GPT-4o-mini.
    Runs in parallel with grading for speed.

    Returns:
        {
            "ai_detection": {"flag": "none/unlikely/possible/likely", "confidence": 0-100, "reason": "..."},
            "plagiarism_detection": {"flag": "none/possible/likely", "reason": "..."}
        }
    """
    # Skip detection if no substantial content to analyze
    # (e.g., fill-in-the-blank only assignments with short factual answers)
    if not student_responses or len(student_responses.strip()) < 50:
        return {
            "ai_detection": {"flag": "none", "confidence": 0, "reason": "Fill-in-the-blank or short-answer only - exempt from AI detection"},
            "plagiarism_detection": {"flag": "none", "reason": "Fill-in-the-blank or short-answer only - exempt from plagiarism detection"}
        }

    try:
        from openai import OpenAI
    except ImportError:
        return {"ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                "plagiarism_detection": {"flag": "none", "reason": ""}}

    client = OpenAI(api_key=_get_api_key('openai'))

    age_range = "11-12" if grade_level == "6" else "12-13" if grade_level == "7" else "13-14"

    detection_prompt = f"""You are an expert at detecting AI-generated content and plagiarism in student work.
Analyze this grade {grade_level} student's responses ({age_range} years old) for signs of AI use or copy-paste.

DETECTION CRITERIA:

1. AI-GENERATED CONTENT - Flag as "likely" if you see:
- Sophisticated vocabulary a {age_range} year old wouldn't use: "ideology", "emphasizing", "implementing", "interconnected", "fostering", "trajectory"
- Perfect grammar and sentence structure throughout
- Academic/formal tone: "This demonstrates...", "It is important to note...", "Furthermore..."
- Phrases like: "transforming a limited mission", "securing vital trade routes", "fundamentally altered"

2. PLAGIARISM/COPY-PASTE - Flag as "likely" if you see:
- Dictionary-perfect definitions (e.g., "exclusive possession or control of the supply of or trade in a commodity or service" for monopoly)
- Wikipedia-style language that doesn't match a child's writing
- Textbook phrases copied verbatim
- Sudden shifts between simple spelling errors and sophisticated paragraphs

3. CONTRAST CHECK (MOST IMPORTANT):
- If student writes simple answers like "it made the US bigger", "idk", misspells words
- BUT also writes "an ideology emphasizing intense loyalty to one's nation"
- That is 100% copy-paste - flag PLAGIARISM as "likely"

REAL {age_range} YEAR OLD WRITES:
- "when one company controls everything" (for monopoly)
- "it helped them trade stuff"
- "so boats could go there"

AI/COPIED TEXT LOOKS LIKE:
- "exclusive possession or control of the supply of or trade in a commodity or service"
- "government-provided financial incentives"
- "implementing three interconnected policies"

STUDENT RESPONSES TO ANALYZE:
{student_responses}

Respond ONLY with this JSON (no other text):
{{
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <0-100>,
        "reason": "<specific phrases that triggered the flag, or empty string if none>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<specific copied phrases found, or empty string if none>"
    }}
}}"""

    try:
        # Use structured output for guaranteed schema
        try:
            response = with_retry(lambda: client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": detection_prompt}],
                response_format=DetectionResponse,
                max_tokens=500,
                temperature=0,
                seed=42
            ), label="detection_structured")
            if token_tracker:
                token_tracker.record_openai(response, "gpt-4o-mini")
            parsed = response.choices[0].message.parsed
            if parsed:
                return parsed.model_dump()
        except Exception:
            pass  # Fall through to text fallback

        # Text fallback if structured output fails
        response = with_retry(lambda: client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": detection_prompt}],
            max_tokens=500,
            temperature=0,
            seed=42
        ), label="detection_fallback")
        if token_tracker:
            token_tracker.record_openai(response, "gpt-4o-mini")
        response_text = response.choices[0].message.content.strip()
        result = _try_parse_json_fallback(response_text)
        if result:
            return result

        return json.loads(response_text)

    except Exception as e:
        _logger.warning("Detection error: %s", e)
        return {
            "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
            "plagiarism_detection": {"flag": "none", "reason": ""}
        }


def _translate_feedback(feedback: str, target_language: str, ai_model: str = 'gpt-4o-mini', token_tracker: 'TokenTracker' = None) -> str:
    """
    Translate grading feedback into the target language using a dedicated API call.
    This is a separate, focused call that produces consistent results because
    translation is the ONLY task — no competing grading instructions.

    Returns the translated text, or empty string on failure.
    """
    if not feedback or not target_language:
        return ""

    prompt = f"""Translate the following teacher feedback into {target_language}.
Keep the same warm, encouraging tone. Do not add or remove content — translate everything faithfully.
Do not include any English text in your response — only the {target_language} translation.

FEEDBACK TO TRANSLATE:
{feedback}"""

    try:
        if ai_model.startswith("claude"):
            import anthropic
            client = anthropic.Anthropic(api_key=_get_api_key('anthropic'))
            claude_model_map = {
                "claude-haiku": "claude-3-5-haiku-latest",
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }
            model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")
            response = with_retry(lambda: client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            ), label="translate_anthropic")
            if token_tracker:
                token_tracker.record_anthropic(response, model)
            return response.content[0].text.strip()

        elif ai_model.startswith("gemini"):
            import google.generativeai as genai
            genai.configure(api_key=_get_api_key('gemini'))
            gemini_model_map = {
                "gemini-flash": "gemini-2.0-flash",
                "gemini-pro": "gemini-2.0-pro-exp",
            }
            model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
            client = genai.GenerativeModel(model)
            response = with_retry(lambda: client.generate_content(prompt), label="translate_gemini")
            if token_tracker:
                token_tracker.record_gemini(response, model)
            return response.text.strip()

        else:
            from openai import OpenAI
            client = OpenAI(api_key=_get_api_key('openai'))
            response = with_retry(lambda: client.chat.completions.create(
                model=ai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.3
            ), label="translate_openai")
            if token_tracker:
                token_tracker.record_openai(response, ai_model)
            return response.choices[0].message.content.strip()

    except Exception as e:
        _logger.warning("Translation to %s failed: %s", target_language, e)
        return ""


def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str, subject: str,
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini',
                      ai_provider: str = 'openai',
                      student_responses: list = None,
                      rubric_breakdown: dict = None,
                      blank_questions: list = None,
                      missing_sections: list = None,
                      token_tracker: 'TokenTracker' = None,
                      student_history: str = '',
                      grading_style: str = 'standard') -> dict:
    """Generate encouraging, improvement-focused teacher feedback from per-question grades.

    Args:
        question_results: Per-question grading results with scores and reasoning.
        student_responses: List of dicts with 'question' and 'answer' keys — the actual
            student text, so the AI can quote specific answers in feedback.
        teacher_instructions: FULL untruncated custom_ai_instructions from app.py.
            Contains student history, accommodations, period differentiation, etc.
        rubric_breakdown: Dict with rubric category scores (content_accuracy, completeness,
            writing_quality, effort_engagement) so feedback can reference rubric performance.
        blank_questions: List of questions the student left blank/unanswered.
        missing_sections: List of required sections entirely missing from submission.
    """

    summary_lines = []
    responses_list = student_responses or []
    for i, qr in enumerate(question_results, 1):
        if not qr:
            continue
        g = qr.get("grade", {})
        # Include the student's actual answer so the AI can quote it
        student_answer = ""
        if i - 1 < len(responses_list):
            resp = responses_list[i - 1]
            student_answer = resp.get("answer", "")
        line = f"Q{i}: {g.get('score', 0)}/{g.get('possible', 10)} ({g.get('quality', 'unknown')})"
        line += f"\n  Reasoning: {g.get('reasoning', '')}"
        if student_answer:
            line += f"\n  Student wrote: \"{student_answer}\""
        summary_lines.append(line)

    # Build grade-scaled feedback instructions
    # ALL grades: encouraging tone, always focused on what the student needs to improve.
    # Higher grades = more time on strengths, but still point to growth areas.
    # Lower grades = more time on improvement guidance, but still acknowledge effort.
    if letter_grade == 'A':
        tone_instructions = """FEEDBACK STRUCTURE FOR AN A (90-100):
Paragraph 1: Celebrate specific strong answers — highlight 2-3 answers that were excellent and explain WHY (e.g., "Your definition of Treaty of Moultrie Creek showed you understood not just what it was, but why it mattered — that's higher-level thinking!").
Paragraph 2: Even A students need growth targets. Identify 1-2 specific areas where they could push deeper or refine their work. Quote their answer and show what a next-level response would look like. Focus on helping them develop more advanced skills (analysis, connections between events, stronger evidence use).
Paragraph 3: If student history is available, connect this to their trajectory and set a challenge for next time.
BALANCE: ~40% strengths, ~60% improvement guidance. An A student should leave knowing exactly what to work on next."""
    elif letter_grade == 'B':
        tone_instructions = """FEEDBACK STRUCTURE FOR A B (80-89):
Paragraph 1: Acknowledge solid work with 1-2 specific strong answers. Quote what they wrote and explain what made it good.
Paragraph 2: Focus here — identify 2-3 specific answers where points were lost. Quote what the student wrote, explain what was missing or incomplete, and tell them exactly what a full-credit answer would have included. Be specific: "You wrote that the Treaty was 'an agreement between the US and Seminoles,' but to earn full credit you needed to mention it was supposed to give them control of millions of acres of Florida land in exchange for allowing roads."
Paragraph 3: Give 1-2 concrete goals for next time. Reference history if available ("You've been hovering around a B — here's what will push you to an A").
BALANCE: ~30% strengths, ~70% improvement guidance."""
    elif letter_grade == 'C':
        tone_instructions = """FEEDBACK STRUCTURE FOR A C (70-79):
Paragraph 1: Briefly acknowledge 1-2 things the student did right. Quote a specific answer that showed some understanding.
Paragraph 2: Main focus — walk through 3-4 specific answers that lost significant points. For each: quote what they wrote, explain what was wrong or missing, and provide the correct information. Example: "For the question about Andrew Jackson's role, you wrote 'he was a president,' but the answer needed to explain that he led troops into Florida during the First Seminole War and later pressured the Seminoles to relocate as president."
Paragraph 3: Give 2-3 specific, actionable steps to improve (re-read specific pages, focus on cause-and-effect, use details from the text). Reference history if available.
BALANCE: ~20% strengths, ~80% improvement guidance. The student needs to understand exactly where they went wrong and what to do differently."""
    elif letter_grade == 'D':
        tone_instructions = """FEEDBACK STRUCTURE FOR A D (60-69):
Paragraph 1: Acknowledge the effort of attempting the assignment, then identify the 2-3 biggest gaps — incomplete answers, missing sections, or incorrect content. Quote specific answers and explain what the correct response should have been.
Paragraph 2: Walk through the most important questions they missed. For each: show what they wrote (or that it was blank), then teach them the answer. This feedback should help them actually learn the material: "The question asked about the causes of the First Seminole War. The key causes were attacks on white settlers, alliances with escaped enslaved people, and southern plantation owners' anger over the Seminole practice of harboring runaways."
Paragraph 3: Give specific recovery steps — re-read certain pages, redo specific questions, come in for help. If history shows a declining trend, address it encouragingly ("I know you can do better — your [previous grade] on [previous assignment] showed you're capable of stronger work").
BALANCE: ~10% strengths, ~90% improvement guidance. Be warm but make sure they leave with the knowledge they were missing."""
    else:  # F or INCOMPLETE
        tone_instructions = """FEEDBACK STRUCTURE FOR AN F (below 60):
Paragraph 1: Identify what went wrong — blank sections, incorrect answers, or missing content. Quote 2-3 specific answers that were wrong or missing and teach the correct answer for each one. The student should learn from reading this feedback.
Paragraph 2: If there is anything the student got partially right, acknowledge it and build on it. Use it as a bridge: "You mentioned 'U.S. efforts to reclaim runaway slaves' as a cause of the First Seminole War — that's a start. To complete the picture, you also needed to include the border conflicts with white settlers and the anger over the Seminole practice of harboring escaped enslaved people."
Paragraph 3: Provide a clear, specific study plan. What pages to re-read, what questions to retry, what concepts to focus on. Make it feel achievable, not overwhelming.
Paragraph 4: If history shows a pattern, address it with care and a path forward ("I've noticed the last few assignments have been tough. Let's figure out what's getting in the way — I'm here to help you turn this around").
BALANCE: ~5% strengths, ~95% improvement guidance. Every sentence should either teach the student something they missed or give them a concrete step to improve. Be encouraging — but the encouragement comes from showing them exactly HOW to do better, not from empty praise."""

    # Adjust tone for grading style
    if grading_style == 'lenient':
        tone_instructions += """

LENIENT GRADING STYLE OVERRIDE:
The teacher has selected LENIENT grading. You MUST adjust your feedback accordingly:
- Do NOT criticize answers for lacking detail if the student demonstrated basic understanding. Brief answers that show they understood the concept are ACCEPTABLE.
- Do NOT say "a full-credit answer would include..." or "to earn full credit you needed to mention..." for answers that already received most of their points. The lenient standard accepts general understanding.
- Focus improvement suggestions on answers that were WRONG or LEFT BLANK, not answers that were correct but brief.
- Shift the balance toward MORE praise and LESS criticism. Add ~20% more strengths to the balance above.
- Use warm, encouraging language appropriate for the grade level. These are young students — the tone should feel supportive, not demanding.
- Only flag genuinely missing or incorrect content, not missing elaboration on otherwise correct answers."""
    elif grading_style == 'strict':
        tone_instructions += """

STRICT GRADING STYLE NOTE:
The teacher has selected STRICT grading. Hold answers to a higher standard in your feedback. Incomplete or shallow answers should be clearly flagged with what was expected."""

    # Build rubric performance summary
    rubric_summary = ""
    if rubric_breakdown:
        rb = rubric_breakdown
        rubric_summary = f"""
RUBRIC BREAKDOWN (address each area in your feedback):
- Content Accuracy: {rb.get('content_accuracy', {}).get('score', 0)}/{rb.get('content_accuracy', {}).get('possible', 40)} — How factually correct were the answers?
- Completeness: {rb.get('completeness', {}).get('score', 0)}/{rb.get('completeness', {}).get('possible', 25)} — Did the student attempt all sections?
- Writing Quality: {rb.get('writing_quality', {}).get('score', 0)}/{rb.get('writing_quality', {}).get('possible', 20)} — Was the writing clear and well-developed?
- Effort & Engagement: {rb.get('effort_engagement', {}).get('score', 0)}/{rb.get('effort_engagement', {}).get('possible', 15)} — Did the student show genuine effort?
"""

    # Build blank/missing sections summary
    blanks_list = blank_questions or []
    missing_list = missing_sections or []
    missing_summary = ""
    if blanks_list or missing_list:
        missing_parts = []
        if missing_list:
            missing_parts.append("MISSING SECTIONS (entire sections not found in submission):")
            for s in missing_list:
                missing_parts.append(f"  - {s}")
        if blanks_list:
            missing_parts.append("BLANK/UNANSWERED QUESTIONS (student left these empty):")
            for q in blanks_list:
                missing_parts.append(f"  - {q}")
        missing_summary = "\n" + "\n".join(missing_parts) + "\n"

    # Build dedicated history section (kept separate from teacher_instructions for prominence)
    history_section = ""
    if student_history:
        history_section = f"\n---\nSTUDENT PERFORMANCE HISTORY (MANDATORY -- you MUST reference this):\n{student_history}\n---\n"

    prompt = f"""Write personalized, encouraging teacher feedback for a grade {grade_level} {subject} student. Focus on what the student needs to know to improve.

SCORE: {total_score}/{total_possible} ({letter_grade})
{rubric_summary}{missing_summary}
PER-QUESTION RESULTS (with the student's actual answers):
{chr(10).join(summary_lines)}

---
TEACHER'S INSTRUCTIONS & GRADING CONTEXT:
{teacher_instructions}
---
{history_section}
NOTE ON TEACHER LENIENCY: If the per-question reasoning above says "Teacher accepts general definitions"
for vocabulary terms, do NOT criticize those vocab answers as "too basic" or "lacking context" in your
feedback. Briefly acknowledge them positively, then move on to the questions and sections that actually
need improvement. The teacher's leniency applies ONLY to vocabulary — you must STILL provide full,
detailed constructive feedback on all other sections (questions, summary, missing work, etc.).

{tone_instructions}

UNIVERSAL RULES:
- Quote or paraphrase the student's SPECIFIC answers — never give generic feedback
- IMPORTANT: If a student's answer text begins with the assignment question/prompt (e.g., "Explain why X happened. The reason was..."), ignore the prompt portion. Only quote and discuss the student's OWN words that follow the prompt. Do not credit or reference the restated question as part of their answer.
- For every wrong answer you mention, explain what the correct answer is or what was missing
- MISSING WORK: If there are blank questions or missing sections listed above, you MUST call them out specifically in your feedback. Name the exact questions or sections that were left blank and explain what the student should have written. Example: "You left the SUMMARY section blank — this section asked you to summarize the key events of the Seminole Wars in 4-5 sentences. To complete it, you'd want to cover the three wars (1817-1858), the role of Andrew Jackson, and the eventual forced relocation to Indian Territory."
- Reference the actual assignment content (topic, questions, vocabulary terms)
- You MUST reference the STUDENT PERFORMANCE HISTORY section above if present. Compare this score to previous scores. Check if the student improved on previously flagged areas. If no history section is provided, skip this
- RUBRIC PERFORMANCE: Address the student's performance on ALL aspects of the rubric — content accuracy, completeness, writing quality, and effort/engagement. For each rubric area, note whether it was a strength or weakness and explain why. Example: "Your content accuracy was strong — most of your answers were factually correct. But your completeness needs work — you left two questions blank, which cost you a full letter grade."
- Do NOT use the student's name — say "you" or "your"
- Sound like a real teacher — use contractions, natural language
- Write feedback in English only
- The feedback must be USEFUL — a parent reading this should understand exactly what their child got right, what they got wrong, and what they need to do to improve
- NEVER write vague transitions like "there are several areas where you can improve" or "however, improvements can be made" without IMMEDIATELY listing the specific areas. If you say improvements are needed, you MUST list each one with the specific question, what the student wrote, and what the correct answer is. Generic "areas to improve" statements with no details are UNACCEPTABLE.
- Do NOT include teacher sign-offs, signatures, or closing lines like "Warm Regards, Mr. Smith" — those are added separately by the system

Also identify:
- Excellent answers: Quote 1-4 specific student answers that earned high marks (fewer for low grades)
- Areas needing improvement: Quote 1-4 specific answers that lost points, with what the correct answer should include
- Strengths: 1-4 specific skills the student demonstrated (tied to rubric areas)
- Developing: 1-3 specific skills the student needs to work on (tied to rubric areas)"""

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
            client = anthropic.Anthropic(api_key=_get_api_key('anthropic'))
            claude_model_map = {
                "claude-haiku": "claude-3-5-haiku-latest",
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
            }
            actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")

            response = with_retry(lambda: client.messages.create(
                model=actual_model,
                max_tokens=3500,
                system=system_msg + "\n\n" + json_schema,
                messages=[{"role": "user", "content": prompt}]
            ), label="generate_feedback_anthropic")
            if token_tracker:
                token_tracker.record_anthropic(response, actual_model)
            result = _try_parse_json_fallback(response.content[0].text.strip())
            if result and "feedback" in result:
                if "skills_demonstrated" not in result or not isinstance(result["skills_demonstrated"], dict):
                    result["skills_demonstrated"] = {"strengths": [], "developing": []}
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model, token_tracker=token_tracker)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

        elif ai_provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=_get_api_key('gemini'))
            gemini_model_map = {
                "gemini-flash": "gemini-2.0-flash",
                "gemini-pro": "gemini-2.0-pro-exp",
            }
            actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
            gemini_client = genai.GenerativeModel(actual_model)

            full_prompt = system_msg + "\n\n" + json_schema + "\n\n---\n\n" + prompt
            response = with_retry(lambda: gemini_client.generate_content(full_prompt), label="generate_feedback_gemini")
            if token_tracker:
                token_tracker.record_gemini(response, actual_model)
            result = _try_parse_json_fallback(response.text.strip())
            if result and "feedback" in result:
                if "skills_demonstrated" not in result or not isinstance(result["skills_demonstrated"], dict):
                    result["skills_demonstrated"] = {"strengths": [], "developing": []}
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model, token_tracker=token_tracker)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

        else:  # OpenAI — use structured output
            from openai import OpenAI
            client = OpenAI(api_key=_get_api_key('openai'))
            response = with_retry(lambda: client.beta.chat.completions.parse(
                model=ai_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                response_format=FeedbackResponse,
                max_tokens=3500,
                temperature=0,
                seed=42
            ), label="generate_feedback_structured")
            if token_tracker:
                token_tracker.record_openai(response, ai_model)
            parsed = response.choices[0].message.parsed
            if parsed:
                result = parsed.model_dump()
                if ell_language and result.get("feedback"):
                    translated = _translate_feedback(result["feedback"], ell_language, ai_model, token_tracker=token_tracker)
                    if translated:
                        result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                return result

    except Exception as e:
        # Issue #224 (same pattern as `grade_per_question` above): if
        # the provider is transient-down, propagate as TransientError
        # so Celery's autoretry sees it. Non-transient errors fall
        # through to the encouraging fallback below.
        from backend.retry import is_retryable_error
        if is_retryable_error(e):
            from backend.tasks.grading_tasks import TransientError
            raise TransientError(
                f"Transient feedback generation failure ({ai_provider}): {e}"
            ) from e
        _logger.warning("Feedback generation error (%s): %s", ai_provider, e)

    return {
        "feedback": "Good effort on this assignment. Keep working hard!",
        "excellent_answers": [],
        "needs_improvement": [],
        "skills_demonstrated": {"strengths": [], "developing": []}
    }
