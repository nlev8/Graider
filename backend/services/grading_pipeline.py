"""Single-pass grading: grade_assignment — the ~1,100-line alternative to the multi-pass
pipeline. Sends the whole submission (text or image) to one LLM call per provider and
post-processes the structured result (caps, effort, rubric weights, AI/plagiarism flags,
optional ELL translation). Extracted from assignment_grader.py. Wave 7 Phase B
(grading-engine decomposition).

Calls the RAW openai / anthropic / google-generativeai SDKs inline (function-local imports),
each wrapped in with_retry(..., label=...). Diagnostic prints became _logger.info on extraction
(behavior-preserving — return values unchanged, pinned by the SDK-fake golden net
tests/test_grader_golden.py). GRADING_RUBRIC (the default rubric) moves here with grade_assignment,
its only user; re-exported via assignment_grader.
"""
import json
import logging
import os

from backend.api_keys import get_api_key as _get_api_key
from backend.retry import with_retry
from backend.services.grader_json import _try_parse_json_fallback
from backend.services.grader_text_prep import sanitize_pii_for_ai
from backend.services.grading_leaves import _translate_feedback
from backend.services.grading_models import GradingResponse, TokenTracker
from backend.services.grading_prep import build_section_rubric
from backend.services.response_extraction import (
    extract_student_responses,
    filter_questions_from_response,
    format_extracted_for_grading,
)
from backend.services.submission_parsing import extract_from_graider_text
from backend.services.writing_profile import get_writing_profile, update_writing_profile
from backend.services.writing_style import analyze_writing_style, compare_writing_styles

# Optional personalized-context helpers (FERPA) — same fallback pattern as assignment_grader.
try:
    from backend.student_history import build_history_context
except ImportError:
    def build_history_context(student_id):
        return ""
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    def build_accommodation_prompt(student_id):
        return ""

_logger = logging.getLogger(__name__)


GRADING_RUBRIC = """
You are grading 6th grade Social Studies assignments. Be ENCOURAGING and GENEROUS.
These are 11-12 year old students - grade with appropriate expectations for their age.

IMPORTANT GRADING GUIDELINES:
- For FILL-IN-THE-BLANK exercises: Accept any answer that is factually correct or very close. Spelling mistakes should NOT reduce the grade if the intent is clear.
- Accept reasonable synonyms, alternate phrasings, and partial answers that demonstrate understanding.
- If a student gets the main idea right but uses slightly different wording, give FULL CREDIT.
- Minor spelling errors (like "piler" instead of "pillar") should NOT be penalized.
- Be GENEROUS - when in doubt, give the student the benefit of the doubt.

GRADING SCALE (out of 100 points):

1. CONTENT ACCURACY (40 points)
   - Are the answers factually correct or demonstrate understanding?
   - For fill-in-the-blank: Is the completed statement essentially true?
   - 40 pts: Most answers correct (90%+)
   - 35 pts: Good understanding (80-89% correct)
   - 30 pts: Solid effort (70-79% correct)
   - 25 pts: Some understanding (60-69% correct)
   - 20 pts: Partial understanding (50-59% correct)
   - Below 20: Less than half correct

2. COMPLETENESS (25 points)
   - Did the student attempt ALL questions/blanks?
   - 25 pts: All questions attempted
   - 20 pts: Nearly all attempted (90%+)
   - 15 pts: Most attempted (75%+)
   - 10 pts: About half attempted
   - 5 pts: Less than half attempted

3. WRITING QUALITY (20 points)
   - Is the writing legible and understandable?
   - For fill-in-blank, this is less important - be generous
   - 20 pts: Clear and readable
   - 15 pts: Minor issues but understandable
   - 10 pts: Some difficulty but can figure out meaning
   - 5 pts: Hard to understand

4. EFFORT & ENGAGEMENT (15 points)
   - Did the student put in genuine effort?
   - Are answers thoughtful (not random guesses)?
   - 15 pts: Clear effort shown
   - 10 pts: Good effort
   - 5 pts: Minimal effort
   - 0 pts: No real effort

GRADE RANGES:
- A: 90-100 (Great job!)
- B: 80-89 (Good work!)
- C: 70-79 (Solid effort)
- D: 60-69 (Needs improvement)
- F: Below 60 (Significant concerns)

REMEMBER: These are 6th graders. Be kind, encouraging, and generous with grading.
A student who attempts all questions and gets most right should get an A or B.
"""


ASSIGNMENT_INSTRUCTIONS = """
Grade the student's work based on what they were asked to do.
Focus on the content they provided, not on sections that may not apply to this assignment type.
"""


def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini', student_id: str = None, assignment_template: str = None, rubric_prompt: str = None, custom_markers: list = None, exclude_markers: list = None, marker_config: list = None, effort_points: int = 15, extraction_mode: str = 'structured', grading_style: str = 'standard', token_tracker: 'TokenTracker' = None, rubric_weights: list = None) -> dict:
    """
    Use OpenAI GPT to grade a student assignment.

    FERPA COMPLIANCE: Student name is NOT sent to OpenAI.
    We use "Student" as a placeholder to protect privacy.

    Supports both text and image inputs.

    Parameters:
    - student_name: Name of the student (kept local, not sent to API)
    - assignment_data: dict with "type" ("text" or "image") and "content"
    - custom_ai_instructions: Additional grading instructions from the teacher
    - grade_level: The student's grade level (e.g., '6', '7', '8')
    - subject: The subject being graded (e.g., 'Social Studies', 'English/ELA')
    - ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')
    - assignment_template: The original assignment template with all questions (for context)

    Returns dict with:
    - score: numeric grade (0-100)
    - letter_grade: A, B, C, D, or F
    - feedback: detailed feedback for the student
    - breakdown: points for each rubric category
    - authenticity_flag: 'clean', 'review', or 'flagged'
    - authenticity_reason: Explanation for flagged or review status
    """
    # Determine which API to use based on model name
    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"

    # Initialize the appropriate client
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError:
            _logger.info("❌ anthropic not installed. Run: pip install anthropic")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API not available - pip install anthropic"}

        if not _get_api_key('anthropic'):
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Anthropic API key not configured"}

        claude_client = anthropic.Anthropic(api_key=_get_api_key('anthropic'))
        claude_model_map = {
            "claude-haiku": "claude-3-5-haiku-latest",
            "claude-sonnet": "claude-sonnet-4-20250514",
            "claude-opus": "claude-opus-4-20250514",
        }
        actual_model = claude_model_map.get(ai_model, "claude-3-5-haiku-latest")
        _logger.info(f"  🤖 Using Claude model: {actual_model}")

    elif provider == "gemini":
        try:
            import google.generativeai as genai
        except ImportError:
            _logger.info("❌ google-generativeai not installed. Run: pip install google-generativeai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Google AI not available - pip install google-generativeai"}

        if not _get_api_key('gemini'):
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Gemini API key not configured"}

        genai.configure(api_key=_get_api_key('gemini'))
        gemini_model_map = {
            "gemini-flash": "gemini-2.0-flash",
            "gemini-pro": "gemini-2.0-pro-exp",
        }
        actual_model = gemini_model_map.get(ai_model, "gemini-2.0-flash")
        gemini_client = genai.GenerativeModel(actual_model)
        _logger.info(f"  🤖 Using Gemini model: {actual_model}")

    else:  # OpenAI
        try:
            from openai import OpenAI
        except ImportError:
            _logger.info("❌ openai not installed. Run: pip install openai")
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "OpenAI API not available"}

        openai_client = OpenAI(api_key=_get_api_key('openai'))

    content = assignment_data.get("content", "")

    # Strip embedded answer key from generated worksheets (handles -- and --- variants)
    if content and "GRAIDER_ANSWER_KEY_START" in content:
        content = content.split("GRAIDER_ANSWER_KEY_START")[0].rstrip().rstrip('-')
        assignment_data = {**assignment_data, "content": content}
        _logger.info(f"  🧹 Stripped embedded answer key from document")

    # Check for empty/blank student submissions before sending to API
    if assignment_data.get("type") == "text" and content:
        import re

        # Method 1: Check for filled-in blanks (text between underscores like ___answer___)
        filled_blanks = re.findall(r'_{2,}([^_\n]+)_{2,}', content)
        filled_blanks = [b.strip() for b in filled_blanks if b.strip() and len(b.strip()) > 1]

        # Method 2: Check for content after colons that isn't just blanks
        # e.g., "Nationalism: the belief that..." vs "Nationalism: ___"
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        # Filter out template instruction text that isn't student writing
        _instruction_patterns = re.compile(
            r'^(define|summarize|explain|describe|write|use|answer|identify|list|compare|analyze|discuss|'
            r'read|complete|fill|circle|match|select|choose|highlight|underline|review|include)\b',
            re.IGNORECASE
        )
        after_colons = [
            a.strip() for a in after_colons
            if a.strip()
            and not a.strip().startswith('_')
            and not _instruction_patterns.match(a.strip())
            and not a.strip().endswith('?')
            and 'complete sentences' not in a.lower()
            and 'using evidence' not in a.lower()
            and 'in your own words' not in a.lower()
            and 'from the reading' not in a.lower()
            and 'pp ' not in a.strip()[:5]  # page references like "pp 348-349"
        ]

        # Method 3: Look for paragraph-length responses (likely written answers)
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        # Filter out paragraphs that are mostly underscores
        real_paragraphs = [p for p in paragraphs if p.count('_') < len(p) * 0.3]

        # Method 4: Count lines that are JUST underscores (blank response lines)
        blank_lines = len(re.findall(r'^[\s_]+$', content, re.MULTILINE))
        total_lines = len([l for l in content.split('\n') if l.strip()])
        blank_ratio = blank_lines / max(total_lines, 1)

        # Method 5: Check for questions followed by no response
        # Look for question patterns and check if there's content after them
        lines = content.split('\n')
        unanswered_questions = []
        question_indices = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Check if line is a question (ends with ? or starts with number/bullet or is a vocab term with colon)
            is_question = (
                line_stripped.endswith('?') or
                re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*\d+[\.\)]\s*\w', line_stripped) or  # "• 1. Question" or "1) Question"
                re.match(r'^[•\*\-\u2022\u2023\u25E6\u2043\u2219\s]*[a-zA-Z][\.\)]\s*\w', line_stripped) or  # "• a. Question" or "a) Question"
                (line_stripped.endswith(':') and len(line_stripped) > 5 and '_' not in line_stripped)  # "Nationalism:"
            )
            if is_question and len(line_stripped) > 5:
                question_indices.append(i)

        # Check content between consecutive questions
        for idx, q_idx in enumerate(question_indices):
            line_stripped = lines[q_idx].strip()
            # Determine where the next question starts (or end of document)
            next_q_idx = question_indices[idx + 1] if idx + 1 < len(question_indices) else len(lines)

            # Get content between this question and the next
            content_between = []
            for j in range(q_idx + 1, min(next_q_idx, q_idx + 6)):  # Check up to 5 lines after
                if j < len(lines):
                    between_line = lines[j].strip()
                    # Skip empty lines and lines that are just underscores
                    if between_line and not re.match(r'^[_\s\-\.]+$', between_line):
                        # Check if this line has actual content (not just template markers)
                        if len(between_line) > 3 and between_line.count('_') < len(between_line) * 0.5:
                            content_between.append(between_line)

            # If no substantive content found after this question, mark as unanswered
            if not content_between:
                unanswered_questions.append(line_stripped[:60] + "..." if len(line_stripped) > 60 else line_stripped)

        # Determine if submission is blank
        has_filled_blanks = len(filled_blanks) >= 2
        has_written_responses = len(after_colons) >= 2 or len(real_paragraphs) >= 1
        mostly_blank_lines = blank_ratio > 0.4
        many_unanswered = len(unanswered_questions) >= 3

        is_blank = (not has_filled_blanks and not has_written_responses and mostly_blank_lines) or \
                   (many_unanswered and not has_filled_blanks and not has_written_responses)

        if is_blank:
            _logger.info(f"  ⚠️  BLANK/EMPTY SUBMISSION DETECTED")
            _logger.info(f"      Filled blanks: {len(filled_blanks)}, Written responses: {len(after_colons)}")
            _logger.info(f"      Blank line ratio: {blank_ratio:.1%}, Unanswered questions: {len(unanswered_questions)}")
            return {
                "score": 0,
                "letter_grade": "INCOMPLETE",
                "breakdown": {
                    "content_accuracy": 0,
                    "completeness": 0,
                    "critical_thinking": 0,
                    "communication": 0
                },
                "feedback": "You submitted a blank assignment with no responses. Please complete all sections and resubmit.",
                "student_responses": [],
                "unanswered_questions": unanswered_questions[:10],
                "ai_detection": {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."},
                "plagiarism_detection": {"flag": "none", "reason": "Blank submission — no content to evaluate."},
                "authenticity_flag": "clean",
                "authenticity_reason": "",
                "skills_demonstrated": {}
            }

    # FERPA: Use anonymous placeholder instead of real student name
    
    # Build custom instructions section if provided
    custom_section = ''
    if custom_ai_instructions:
        custom_section = f"""
---
TEACHER'S GRADING INSTRUCTIONS (FOLLOW THESE CAREFULLY):
{custom_ai_instructions}
---
"""

    # Build student history context for personalized feedback
    history_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            history_context = build_history_context(student_id)
        except Exception as e:
            _logger.info(f"  Note: Could not load student history: {e}")

    # Build accommodation context for IEP/504 students (FERPA compliant)
    # NOTE: Only accommodation TYPE is sent to AI - no student identifying info
    accommodation_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            accommodation_context = build_accommodation_prompt(student_id)
            if accommodation_context:
                _logger.info(f"  Applying accommodations for student")
        except Exception as e:
            _logger.info(f"  Note: Could not load accommodations: {e}")

    # Check if this is a fill-in-the-blank assignment
    is_fitb = False
    content_lower = content.lower() if content else ''
    if 'fill-in' in content_lower or 'fill in the blank' in content_lower or 'fillintheblank' in content_lower.replace(' ', '').replace('-', ''):
        is_fitb = True
    # Also check custom AI instructions for FITB rubric type
    if 'FILL-IN-THE-BLANK' in (custom_ai_instructions or '').upper():
        is_fitb = True
    # Also detect FITB by timestamp pattern (e.g., "1. (0:00)" format common in video worksheets)
    if not is_fitb and content:
        import re as _re
        has_timestamps = bool(_re.search(r'\d+\.\s*\(\d+:\d+', content))
        has_filled_underscores = len(_re.findall(r'_{2,}([^_\n]+)_{2,}', content)) >= 2
        if has_timestamps and has_filled_underscores:
            is_fitb = True
            _logger.info(f"  📝 FITB detected via timestamps + filled underscores")

    # PRE-EXTRACT student responses to prevent AI hallucination
    extraction_result = None
    extracted_responses_text = ''
    # If teacher set up custom markers, use marker-based extraction even if FITB was detected.
    # Markers mean the teacher explicitly defined which sections to grade — that takes priority.
    has_real_markers = custom_markers and len(custom_markers) > 0
    if is_fitb and has_real_markers:
        _logger.info(f"  📝 FITB detected but custom markers present — using marker extraction instead")
        is_fitb = False
    if assignment_data.get("type") == "text" and content:
        if is_fitb:
            # FITB assignment — send full content for grading (works with or without markers)
            _logger.info(f"  📝 FITB assignment - sending full content for grading")
            extracted_responses_text = f"""
==================================================
FILL-IN-THE-BLANK SUBMISSION
==================================================

STUDENT'S COMPLETED DOCUMENT:
{content}

==================================================
Grade based on:
1. ACCURACY: Did the student fill in the blanks correctly?
2. COMPLETENESS: Did the student attempt all blanks?
Do NOT penalize for AI/plagiarism - these are factual answers.
==================================================
"""
            extraction_result = {
                "extracted_responses": [{"question": "Fill-in-the-blank", "answer": content, "type": "fitb_full"}],
                "blank_questions": [],
                "total_questions": 1,
                "answered_questions": 1,
                "extraction_summary": "FITB - full content submitted for grading"
            }
        else:
            # Normal extraction for non-FITB assignments
            # Priority: GRAIDER tag plain-text fallback > custom marker extraction
            if '[GRAIDER:' in content:
                extraction_result = extract_from_graider_text(content, exclude_markers)

            if not extraction_result or not extraction_result.get("extracted_responses"):
                # Debug: Log markers being used
                marker_count = len(custom_markers) if custom_markers else 0
                _logger.info(f"  🔍 Extraction using {marker_count} markers")
                if custom_markers and marker_count > 0:
                    for i, m in enumerate(custom_markers[:3]):  # Show first 3
                        marker_text = m.get('start', m) if isinstance(m, dict) else m
                        _logger.info(f"      Marker {i+1}: {marker_text[:50]}...")

                extraction_result = extract_student_responses(content, custom_markers, exclude_markers, assignment_template)
            if extraction_result:
                # Filter question/prompt text from extracted answers before grading.
                # If filtering empties a response, move it to blank_questions so
                # completeness caps apply (e.g., primary source quotes that survive extraction).
                filtered_out = []
                for resp in extraction_result.get("extracted_responses", []):
                    answer = resp.get("answer", "")
                    if answer and resp.get("type") != "fitb":
                        cleaned = filter_questions_from_response(answer)
                        if cleaned and len(cleaned.strip()) >= 3:
                            resp["answer"] = cleaned
                        else:
                            # Response was entirely template/prompt text — mark as blank
                            q_label = resp.get("question", "Unknown")
                            _logger.info(f"      ⚠️ Response for '{q_label[:50]}' was only template text — marking blank")
                            extraction_result.setdefault("blank_questions", []).append(q_label)
                            filtered_out.append(resp)
                # Remove blanked-out responses from extracted list
                if filtered_out:
                    extraction_result["extracted_responses"] = [
                        r for r in extraction_result["extracted_responses"] if r not in filtered_out
                    ]
                    extraction_result["answered_questions"] = len(extraction_result["extracted_responses"])

                extracted_responses_text = format_extracted_for_grading(extraction_result, marker_config, extraction_mode)
                answered = extraction_result.get("answered_questions", 0)
                total = extraction_result.get("total_questions", 0)
                blank_qs = extraction_result.get("blank_questions", [])
                missing_secs = extraction_result.get("missing_sections", [])
                _logger.info(f"  📋 Pre-extracted {answered}/{total} responses, {len(blank_qs)} blank, {len(missing_secs)} missing")
                if blank_qs:
                    _logger.info(f"      Blank questions: {blank_qs}")
                if missing_secs:
                    _logger.info(f"      Missing sections: {missing_secs}")

                # DEBUG: Show what was extracted
                for i, resp in enumerate(extraction_result.get("extracted_responses", [])):
                    q_label = resp.get("question", "?")[:60]
                    ans_preview = resp.get("answer", "")[:100].replace('\n', ' ')
                    _logger.info(f"      [{i+1}] {q_label}...")
                    _logger.info(f"          Answer: {ans_preview}...")

                # If no responses found, return early with 0 score
                if answered == 0:
                    _logger.info(f"  ⚠️  NO RESPONSES EXTRACTED - Document is blank or markers don't match")
                    return {
                        "score": 0,
                        "letter_grade": "INCOMPLETE",
                        "breakdown": {
                            "content_accuracy": 0,
                            "completeness": 0,
                            "critical_thinking": 0,
                            "communication": 0
                        },
                        "feedback": "You submitted a blank assignment with no responses. Please complete all sections and resubmit.",
                        "student_responses": [],
                        "unanswered_questions": extraction_result.get("blank_questions", []) + extraction_result.get("missing_sections", []),
                        "ai_detection": {"flag": "none", "confidence": 0, "reason": "Blank submission — no content to evaluate."},
                        "plagiarism_detection": {"flag": "none", "reason": "Blank submission — no content to evaluate."},
                        "authenticity_flag": "clean",
                        "authenticity_reason": "",
                        "skills_demonstrated": {},
                        "extraction_result": extraction_result
                    }

    # Analyze current submission's writing style for AI detection
    writing_style_context = ''
    current_writing_style = None
    style_comparison = None
    if assignment_data.get("type") == "text" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            # Get student's historical writing profile
            historical_profile = get_writing_profile(student_id) if student_id and student_id != "UNKNOWN" else None

            if historical_profile and historical_profile.get("sample_count", 0) >= 2:
                # Compare current vs historical style
                style_comparison = compare_writing_styles(current_writing_style, historical_profile)

                if style_comparison.get("ai_likelihood") in ["likely", "possible"]:
                    _logger.info(f"  ⚠️  Writing style deviation detected: {style_comparison.get('deviation')}")
                    writing_style_context = f"""
---
WRITING STYLE ANALYSIS (COMPARE TO STUDENT'S HISTORY):
This student's historical writing profile (based on {historical_profile.get('sample_count', 0)} previous assignments):
- Average complexity score: {historical_profile.get('avg_complexity_score', 'N/A')}/10
- Average sentence length: {historical_profile.get('avg_sentence_length', 'N/A')} words
- Average word length: {historical_profile.get('avg_word_length', 'N/A')} characters
- Typical academic vocabulary: {historical_profile.get('avg_academic_words', 0):.1f} words per submission

Current submission analysis:
- Complexity score: {current_writing_style.get('complexity_score', 'N/A')}/10
- Sentence length: {current_writing_style.get('avg_sentence_length', 'N/A')} words
- Word length: {current_writing_style.get('avg_word_length', 'N/A')} characters
- Academic vocabulary count: {current_writing_style.get('academic_word_count', 0)}

DEVIATION ALERT: {'; '.join(style_comparison.get('deviations', []))}
This suggests possible AI use - be extra vigilant in your authenticity check!
---
"""

    # Map grade level to age range for context
    grade_age_map = {
        'K': '5-6', '1': '6-7', '2': '7-8', '3': '8-9', '4': '9-10', '5': '10-11',
        '6': '11-12', '7': '12-13', '8': '13-14', '9': '14-15', '10': '15-16',
        '11': '16-17', '12': '17-18'
    }
    age_range = grade_age_map.get(str(grade_level), '11-12')

    # Build extracted responses section for the prompt
    extracted_responses_section = ""
    if extracted_responses_text:
        extracted_responses_section = f"""
---
{extracted_responses_text}
---
"""

    # Build assignment template section (provides question context)
    assignment_template_section = ""
    if assignment_template:
        # Truncate if very long to save tokens
        template_text = assignment_template[:8000] if len(assignment_template) > 8000 else assignment_template
        assignment_template_section = f"""
---
ASSIGNMENT TEMPLATE (The questions/prompts the student was asked to answer):
{template_text}
---
"""

    # Use custom rubric if provided, otherwise use default
    # If marker_config is provided, build a section-based rubric
    section_rubric = ""
    if marker_config:
        section_rubric = build_section_rubric(marker_config, effort_points)

    effective_rubric = rubric_prompt if rubric_prompt else GRADING_RUBRIC

    # Build extraction mode-specific instructions
    if extraction_mode == 'ai':
        extraction_instructions = """
CRITICAL - AI EXTRACTION MODE:
The content above contains RAW section content that includes BOTH prompts/questions AND student responses.
YOUR JOB is to identify what is a prompt/question vs what the student actually wrote.

IDENTIFYING STUDENT RESPONSES:
- Questions end with "?" - anything AFTER the "?" on the same line is the student's answer
- Vocabulary format "Term:" - anything after the ":" is the student's definition
- Prompts like "Write your answer:", "Explain...", etc. are instructions, not student content
- Look for the actual student-written text, which is usually less formal and may have spelling errors
- If a section has only a prompt with no student response, mark it as BLANK/UNANSWERED

For example:
- "1. What year was the Louisiana Purchase? 1803" → Student answer is "1803"
- "Antebellum: the period before the war" → Student answer is "the period before the war"
- "Antebellum:" with nothing after → BLANK, student didn't answer
- "Write your answer:" with nothing after → BLANK

Be thorough in separating prompts from responses. Students often write answers on the same line as questions.
"""
    else:
        extraction_instructions = """
CRITICAL - PRE-EXTRACTED RESPONSES:
The student responses have been PRE-EXTRACTED from the document and listed above.
DO NOT invent or hallucinate any responses that are not in the VERIFIED STUDENT RESPONSES section.
ONLY grade the responses that were explicitly extracted and shown to you.
If a question is listed as "UNANSWERED", it means the student left it blank - do not imagine an answer.
"""

    # Build grading style instructions
    if grading_style == 'lenient':
        grading_style_instructions = """
GRADING APPROACH: LENIENT
- Prioritize EFFORT over perfection. If a student attempted a section, they deserve significant credit.
- Brief answers that show understanding should receive 70-80% credit even if not fully developed.
- Do NOT penalize short answers if they demonstrate the student understood the material.
- A student who attempts ALL sections with genuine effort should receive at minimum a B (80+).
- Writing quality expectations should be relaxed - focus on content understanding, not eloquence.
- One-sentence answers to open-ended questions are acceptable if they show comprehension.
- Reserve grades below C only for students who clearly did not try or left sections truly blank/missing.
"""
    elif grading_style == 'strict':
        grading_style_instructions = """
GRADING APPROACH: STRICT
- Hold students to high standards for their grade level.
- Brief, underdeveloped answers to open-ended questions should be penalized.
- Writing quality matters - expect complete sentences and proper grammar.
- Full credit requires thorough, well-developed responses that demonstrate deep understanding.
- Partial answers receive proportionally reduced credit.
"""
    else:
        grading_style_instructions = """
GRADING APPROACH: STANDARD
- Balance accuracy, completeness, writing quality, and effort evenly per the rubric.
- Brief answers should receive partial credit proportional to their quality.
- Students should be encouraged but held to grade-level expectations.
"""

    # Build authenticity/detection section — per-section FITB awareness
    if is_fitb and not custom_markers:
        # Pure FITB (no markers) — skip all detection
        fitb_authenticity_section = f"""AUTHENTICITY CHECKS - FILL-IN-THE-BLANK EXEMPTION:
This is a fill-in-the-blank assignment. Students are expected to write short factual answers (names, dates, places, vocabulary terms).
These answers will naturally match textbook/source material — that is the CORRECT behavior, NOT plagiarism or AI use.
DO NOT flag any answers for AI use or plagiarism. Set ai_detection to "none" and plagiarism_detection to "none".
Focus ONLY on whether the answers are factually correct and complete.

HARD CAPS FOR INCOMPLETE WORK (MANDATORY - each skipped section = one letter grade drop):
Count the number of skipped/unanswered blanks or sections:
- 0 skipped = eligible for A (up to 100)
- 1 skipped = MAXIMUM 89 (B) - NO EXCEPTIONS
- 2 skipped = MAXIMUM 79 (C) - NO EXCEPTIONS
- 3 skipped = MAXIMUM 69 (D) - NO EXCEPTIONS
- 4+ skipped = MAXIMUM 59 (F)
- 5+ skipped = MAXIMUM 49 (F)
- 6+ skipped = MAXIMUM 39 (F)

NEARLY BLANK SUBMISSIONS - Score based on effort shown:
- If student answered only 1-2 blanks out of 5+ = score 10-25 (F)
- If student answered only 3-4 blanks out of 10+ = score 25-40 (F)
- Empty or nearly empty = score in the 0-30 range"""
    else:
        # Full detection — with FITB exemption note for hybrid assignments
        fitb_exemption_note = ""
        if is_fitb:
            fitb_exemption_note = """IMPORTANT - FILL-IN-THE-BLANK EXEMPTION:
This assignment contains fill-in-the-blank sections mixed with written response sections.
Fill-in-the-blank answers (short factual responses like names, dates, places, vocabulary terms) are EXEMPT from AI/plagiarism detection.
These answers are EXPECTED to match textbook/source material — that is correct behavior, NOT cheating.
ONLY apply AI/plagiarism checks to WRITTEN responses (paragraphs, reflections, summaries, explanations).
Do NOT use fill-in-the-blank answers as evidence of AI use or plagiarism.

"""
        fitb_authenticity_section = f"""{fitb_exemption_note}CRITICAL - AUTHENTICITY CHECKS (YOU MUST CHECK THIS CAREFULLY!):

1. AI DETECTION - Compare the student's simple answers to their written paragraphs:
STEP 1: Look at their short answers (fill-in-blanks, one-word responses). Note the vocabulary level.
STEP 2: Look at their paragraph responses. Compare the vocabulary and complexity.
STEP 3: If there's a MISMATCH (simple short answers but sophisticated paragraphs), flag as "likely" AI.

AUTOMATIC "likely" AI FLAGS - if you see ANY of these phrases, it's 100% AI:
- "transformed the nation into a continental power"
- "transforming a limited mission"
- "historic deal that doubled"
- "fueling westward expansion"
- "triggered intense political debates"
- "spurred exploration"
- "fundamentally altered the trajectory"
- "establishing the precedent for"
- "constitutional questions regarding federal authority"
- "resonate through subsequent decades"
- "vital for trade and growth"
- "securing vital trade routes"
- "manifest destiny"
- "territorial expansion"
- "abundant natural resources"
- Any phrase starting with "Transforming...", "Establishing...", "Securing..."
- Any phrase a {age_range} year old would NEVER write

CRITICAL CONTRAST CHECK - THIS IS THE MOST IMPORTANT CHECK:
Look at the student's spelling and grammar in simple answers. If they write:
- Misspellings like "Tomas Jefferson", "the u's", "france" (lowercase)
- Simple phrases like "It doubled in size", "idk"
- Basic vocabulary and short sentences

BUT THEN write sophisticated phrases like:
- "Transforming a limited mission to buy New Orleans into a historic deal"
- Any sentence with words like "vital", "securing", "expanding", "historic deal"

That is 100% AI or copied - flag as "likely" IMMEDIATELY. A student who misspells "Thomas" does NOT write "transforming a limited mission into a historic deal."

Real grade {grade_level} students write: "it made the US bigger", "they needed the river for boats", "so ships could go there"
AI writes: "it transformed the nation into a continental power", "securing vital trade routes"

OBVIOUS COPY-PASTE DEFINITIONS (flag as PLAGIARISM "likely" IMMEDIATELY):
- "exclusive possession or control of the supply of or trade in a commodity or service" = Google definition of monopoly
- "an ideology emphasizing intense loyalty to one's nation" = textbook definition
- "government-provided financial incentives" = too sophisticated
- "implementing three interconnected policies" = not student language
- "authority not explicitly stated in the U.S. Constitution but deemed necessary" = textbook definition of implied powers
- ANY definition that sounds like it was copied from a dictionary or Wikipedia = PLAGIARISM

A real {age_range} year old defines monopoly as: "when one company controls everything" or "only one person sells something"
NOT: "exclusive possession or control of the supply of or trade in a commodity or service"

2. PLAGIARISM DETECTION - Look for:
- SUDDEN SHIFTS in writing quality (simple answers + sophisticated paragraphs = copied/AI)
- Textbook-perfect definitions that don't match the student's other answers
- Phrases that sound memorized or copied verbatim
- Statistics or specific numbers not in the reading (like "828,000 square miles")
- DICTIONARY DEFINITIONS - If a vocabulary definition sounds like it was copied from Google/dictionary (e.g., "exclusive possession or control of the supply of or trade in a commodity or service" for monopoly), flag as PLAGIARISM "likely"
- SOPHISTICATED VOCABULARY MISMATCH - Words like "ideology", "emphasizing", "fostering", "interconnected", "implementing" are NOT how grade {grade_level} students write definitions
- FRAGMENT ANSWERS that are clearly pasted (no complete sentence, just a definition dump)
- If student writes simple answers for some questions but sophisticated definitions for vocabulary = COPY/PASTE from Google

HARD CAPS FOR AI USE / PLAGIARISM (apply FIRST, before other caps):
- AI flag "likely" = MAX score is 50 (F) - this is cheating
- AI flag "possible" = MAX score is 65 (D) - suspicious, needs verification
- Plagiarism flag "likely" = MAX score is 50 (F) - this is cheating
- Plagiarism flag "possible" = MAX score is 65 (D) - suspicious
- If BOTH AI and plagiarism are flagged = MAX score is 40 (F)

In feedback for AI/plagiarism flags:
- Clearly state the work appears to be AI-generated or copied
- Explain that academic integrity is important
- Recommend the student redo the assignment in their own words
- Note this will be reviewed by the teacher

THEN apply HARD CAPS FOR INCOMPLETE WORK (MANDATORY - each skipped section = one letter grade drop):
Count the number of skipped/unanswered written sections (Student Task, Reflection, Explain, etc.):
- 0 skipped = eligible for A (up to 100)
- 1 skipped = MAXIMUM 89 (B) - NO EXCEPTIONS
- 2 skipped = MAXIMUM 79 (C) - NO EXCEPTIONS
- 3 skipped = MAXIMUM 69 (D) - NO EXCEPTIONS
- 4+ skipped = MAXIMUM 59 (F)
- 5+ skipped = MAXIMUM 49 (F)
- 6+ skipped = MAXIMUM 39 (F)

NEARLY BLANK SUBMISSIONS - Score based on effort shown:
- If student answered only 1-2 questions out of 5+ = score 10-25 (F)
- If student answered only 3-4 questions out of 10+ = score 25-40 (F)
- A single poor answer like "idk" or "going again" does NOT earn 50 points
- The score should reflect ACTUAL WORK DONE, not a default minimum
- Empty or nearly empty = score in the 0-30 range

YOU MUST APPLY THESE CAPS. If a student skipped 2 written sections, their score CANNOT be above 79 even if their fill-in-the-blanks were perfect.

The LOWEST cap wins. Example: AI "likely" (cap 50) + 6 sections skipped (cap 39) = final cap is 39."""

    # Load ELL designation for this student (teacher-controlled bilingual feedback)
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

    # Always grade in English only — bilingual translation is handled as a separate post-grading step
    ell_instruction = "Write feedback in English only."

    # Repeat teacher instructions at end of prompt — placed here so the AI sees them LAST
    # before generating its response. Earlier placement gets buried under 80+ lines of default rules.
    teacher_override_section = ""
    if custom_ai_instructions and custom_ai_instructions.strip():
        teacher_override_section = f"""

FINAL AUTHORITY — TEACHER'S GRADING INSTRUCTIONS (repeated here because they override ALL defaults above):
{custom_ai_instructions}

^^^ THESE INSTRUCTIONS OVERRIDE the default scoring rules. If the teacher says to be lenient, be lenient.
If the teacher says to accept general definitions, accept them. Do NOT contradict the teacher's instructions
in your scoring or feedback. The teacher knows their students better than any rubric."""

    prompt_text = f"""
{effective_rubric}

{section_rubric}

{ASSIGNMENT_INSTRUCTIONS}
{custom_section}
{grading_style_instructions}
{accommodation_context}
{history_context}
{writing_style_context}
{assignment_template_section}
---

STUDENT CONTEXT:
- Grade Level: {grade_level}
- Subject: {subject}
- Expected Age Range: {age_range} years old

{extracted_responses_section}

{extraction_instructions}

IMPORTANT: Assess ALL sections that appear in the EXTRACTED RESPONSES, UNANSWERED QUESTIONS, and MISSING SECTIONS above.
If a section appears in MISSING SECTIONS, the student entirely omitted a required part of the assignment — penalize accordingly.
If a section appears in UNANSWERED QUESTIONS, the student left a required section blank — penalize accordingly.
Only the extracted/marked sections, unanswered questions, and missing sections count toward the grade.

Your "student_responses" field MUST contain ONLY the raw answer text from each "STUDENT ANSWER:" line above.
Do NOT include question numbers, section names, or labels like "[1] Summary:" - just the student's actual written text.
Example: If the verified response shows 'STUDENT ANSWER: "The treaty was signed in 1803"', your student_responses should contain "The treaty was signed in 1803" - not "Summary: The treaty was signed in 1803".
If no responses were extracted, the student gets a 0.

For MATCHING exercises specifically:
- Look for numbers placed next to vocabulary terms in the extracted responses
- The number indicates which definition the student chose
- Grade whether they matched correctly

GRADING GUIDELINES:
- Assess EVERY answer the student provided.
- For fill-in-the-blank: check if the answer is factually correct or close enough.
- Accept multiple valid answers and synonyms.
- DO NOT penalize spelling mistakes if the meaning is clear.
- Be age-appropriate - these are grade {grade_level} students ({age_range} years old).
- IMPORTANT: If the teacher provided custom grading instructions above, follow them carefully.

CRITICAL - COMPLETENESS REQUIREMENTS:
- Check the EXTRACTED RESPONSES, UNANSWERED QUESTIONS, and MISSING SECTIONS lists above.
- MISSING SECTIONS are sections the teacher REQUIRED but the student ENTIRELY OMITTED from their submission.
  Each missing section must be treated the SAME as a skipped section — it lowers the grade by one full letter.
- UNANSWERED QUESTIONS are sections the student included but left blank — also penalize.
- IMPORTANT: Individual vocabulary terms or bullet points WITHIN a section that HAS a student answer are NOT unanswered questions. Only count items explicitly listed in the UNANSWERED QUESTIONS section above.
- For the sections that WERE extracted, check if the student answered them adequately, especially:
  * "Explain in your own words" sections - these require written responses, not blank
  * "Reflection" or "Final Reflection" questions - these MUST be answered
  * "Student Task" sections - these are major components requiring written responses
  * Any prompt asking students to "Write a few sentences" or "Describe" or "Explain"
  * Summary sections
  * Primary source analysis tasks
- Skipping or omitting written sections shows AVOIDANCE OF EFFORT and must be penalized!
- Count total skipped = UNANSWERED QUESTIONS + MISSING SECTIONS.
{f"""- LENIENT PENALTY SCALE (teacher selected lenient grading):
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = eligible for A/B (85-95) - minor deduction only
  * 2 sections skipped/missing = maximum B (80-89)
  * 3 sections skipped/missing = maximum C (70-79)
  * 4+ sections skipped/missing = maximum D (60-69)
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who attempt most sections with genuine effort should receive at minimum a C (70+).
- An "A" grade (90+) is possible if ALL answered sections show genuine effort and understanding.""" if grading_style == 'lenient' else f"""- STRICT PENALTY SCALE (teacher selected strict grading):
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = maximum B- (80-85) - dropped one letter
  * 2 sections skipped/missing = maximum C (70-75) - dropped two letters
  * 3 sections skipped/missing = maximum D (60-65) - dropped three letters
  * 4+ sections skipped/missing = F (below 60) - shows no effort
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who ONLY do fill-in-the-blanks and skip ALL written responses = maximum D (65)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with thorough, well-developed responses.""" if grading_style == 'strict' else """- STANDARD PENALTY SCALE:
  * 0 sections skipped/missing = eligible for A (90-100)
  * 1 section skipped/missing = maximum B (80-89) - dropped one letter
  * 2 sections skipped/missing = maximum C (70-79) - dropped two letters
  * 3 sections skipped/missing = maximum D (60-69) - dropped three letters
  * 4+ sections skipped/missing = F (below 60) - shows no effort on written work
  * ALL or nearly all sections blank = 0 (INCOMPLETE) - student did not attempt the assignment
- Students who ONLY do fill-in-the-blanks and skip ALL written responses = maximum C (75)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with quality responses."""}
- This applies to ALL assignments - skipping reflections, explanations, or analysis tasks is unacceptable
- In the "unanswered_questions" field, ONLY list items from the UNANSWERED QUESTIONS and MISSING SECTIONS lists above — do NOT invent new unanswered items from individual vocab terms or bullet points within answered sections

{fitb_authenticity_section}
{teacher_override_section}
Provide your response in the following JSON format ONLY (no other text):
{{
    "score": <FIRST calculate raw score, THEN apply the caps above. If 2 sections skipped, max is 79>,
    "letter_grade": "<A, B, C, D, or F - must match the capped score>",
    "breakdown": {{
        "content_accuracy": <points out of 40 - correctness of answers>,
        "completeness": <points out of 25 - ALL sections must be attempted. MISSING SECTIONS and UNANSWERED QUESTIONS both count as skipped. Written responses (reflections, explanations, Student Tasks) count heavily! 0-5 if 2+ major sections skipped/missing, 6-12 if 1 major section skipped/missing, 13-20 if minor gaps only, 21-25 only if ALL parts fully completed>,
        "writing_quality": <points out of 20>,
        "effort_engagement": <points out of 15>
    }},
    "student_responses": ["<EXTRACT ONLY the actual answer text that appears after 'STUDENT ANSWER:' in the verified responses above. Do NOT include the question/section name, number, or label. WRONG: 'Summary: The treaty was...' or '[1] Summary: The treaty...' - RIGHT: 'The treaty was signed in 1803 and...' - just the raw answer text the student wrote>"],
    "unanswered_questions": ["<ONLY list sections/questions from the UNANSWERED QUESTIONS and MISSING SECTIONS lists above. Do NOT list individual vocab terms or bullet points that appear WITHIN a section the student completed — those are part of the student's response, not separate unanswered questions. If a section has a STUDENT ANSWER with content, it is NOT unanswered even if individual terms within it seem brief.>"],
    "excellent_answers": ["<Quote 2-4 specific answers that were particularly strong, accurate, or showed great understanding. Include the exact text the student wrote.>"],
    "needs_improvement": ["<Quote 1-3 specific answers that were incorrect or incomplete, along with what the correct/better answer would be. Format: 'You wrote [X] but [correct info]' or 'For the question about [topic], [guidance]'>"],
    "skills_demonstrated": {{
        "strengths": ["<List 2-4 specific skills the student showed strength in. Go BEYOND the rubric categories - identify skills like: reading comprehension, critical thinking, source analysis, making connections, vocabulary usage, following directions, organization, creativity, historical thinking, cause-and-effect reasoning, comparing/contrasting, using evidence, drawing conclusions, summarizing, note-taking, attention to detail, etc. Only include skills clearly demonstrated in THIS assignment.>"],
        "developing": ["<List 1-2 skills the student is still developing or struggled with. Same skill types as above. Be specific about what skill needs work based on their answers.>"]
    }},
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <number 0-100 representing confidence in the assessment>,
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback that sounds like a real teacher wrote it - warm, encouraging, and specific. IMPORTANT GUIDELINES: 1) VARY your sentence structure and openings - don't start every sentence the same way. Mix short punchy sentences with longer ones. 2) QUOTE specific answers from the student's work when praising them (e.g., 'I loved how you explained that [quote their answer]' or 'Your answer about [topic] - '[their exact words]' - shows real understanding'). 3) When mentioning areas to improve, be gentle and constructive - reference specific questions they struggled with and give them a hint or the right direction. 4) Sound HUMAN - use contractions (you're, that's, I'm), occasional casual phrases ('Nice!', 'Great thinking here'), and vary your enthusiasm. 5) End with genuine encouragement that connects to something specific they did well. 6) Do NOT use the student's name - say 'you' or 'your'. 7) Avoid repetitive phrases like 'Great job!' at the start of every paragraph - mix it up! 8) IF STUDENT HISTORY IS PROVIDED ABOVE: Reference their progress! Mention streaks, acknowledge CONSISTENT SKILLS (e.g., 'Your reading comprehension continues to be a real strength!'), celebrate IMPROVING SKILLS (e.g., 'I notice your critical thinking is getting sharper - great progress!'), and gently encourage SKILLS TO DEVELOP (e.g., 'Keep working on making connections between ideas'). Connect current work to past achievements when relevant. 9) BILINGUAL FEEDBACK: {ell_instruction}>"
}}
"""

    _logger.info(f"  🤖 Grading with AI...")

    try:
        # FERPA COMPLIANCE: Sanitize PII from text content before sending to AI
        if assignment_data["type"] == "text":
            original_content = assignment_data['content']
            anon_id, sanitized_content = sanitize_pii_for_ai(student_name, original_content)

            # Log if any PII was removed (for audit trail)
            if sanitized_content != original_content:
                _logger.info(f"  🔒 PII sanitized from submission before AI processing")

            # HARD BLOCK: Only send extracted responses to prevent hallucination
            # If extraction succeeded, use ONLY extracted responses (not raw content)
            if extracted_responses_text:
                # Send only the pre-extracted verified responses
                _logger.info(f"  ✅ Using ONLY pre-extracted responses (hallucination prevention)")
                full_prompt = prompt_text + f"\n\nSTUDENT'S VERIFIED RESPONSES (extracted from document):\n{extracted_responses_text}"
            else:
                # Extraction failed or found nothing - REQUIRES MANUAL REVIEW
                _logger.info(f"  ⚠️  HARD BLOCK: No responses extracted - flagging for manual review")
                return {
                    "score": 0,
                    "letter_grade": "MANUAL REVIEW",
                    "breakdown": {
                        "content_accuracy": 0,
                        "completeness": 0,
                        "critical_thinking": 0,
                        "communication": 0
                    },
                    "feedback": "⚠️ MANUAL REVIEW REQUIRED: The automated extraction could not find student responses in this document. This could mean:\n\n1. The document is blank or nearly blank\n2. The formatting is unusual\n3. The student wrote in unexpected locations\n\nPlease open the original document and grade manually to prevent AI hallucination.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "authenticity_flag": "manual_review",
                    "authenticity_reason": "Extraction failed - cannot verify responses",
                    "skills_demonstrated": {},
                    "requires_manual_review": True
                }
            messages = [{"role": "user", "content": full_prompt}]

        elif assignment_data["type"] == "image":
            # Image-based assignment - use vision
            # WARNING: Cannot extract/verify responses from images - higher hallucination risk
            _logger.info(f"  ⚠️  IMAGE SUBMISSION: Cannot pre-extract responses - recommend spot-checking")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{assignment_data['media_type']};base64,{assignment_data['content']}"
                        }
                    }
                ]
            }]
            # Flag that this is an unverified image submission
            extraction_result = {"type": "image", "verified": False}
        else:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Unknown content type"}

        # Make API call based on provider
        if provider == "anthropic":
            # Claude API call
            if assignment_data.get("type") == "image":
                claude_content = [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": assignment_data['media_type'],
                            "data": assignment_data['content']
                        }
                    }
                ]
            else:
                claude_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]

            response = with_retry(lambda: claude_client.messages.create(
                model=actual_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": claude_content}]
            ), label="grade_assignment_anthropic")
            if token_tracker:
                token_tracker.record_anthropic(response, actual_model)
            response_text = response.content[0].text.strip()

        elif provider == "gemini":
            if assignment_data.get("type") == "image":
                import base64
                image_data = base64.b64decode(assignment_data['content'])
                image_part = {
                    "mime_type": assignment_data['media_type'],
                    "data": image_data
                }
                full_prompt = prompt_text + "\n\nSTUDENT'S WORK (see attached image):\nIMPORTANT: Only grade what you can CLEARLY see in the image. If text is unclear or cut off, mark as incomplete rather than guessing."
                response = with_retry(
                    lambda: gemini_client.generate_content([full_prompt, image_part]),
                    label="grade_assignment_gemini_image",
                )
            else:
                text_content = messages[0]["content"] if isinstance(messages[0]["content"], str) else messages[0]["content"][0]["text"]
                response = with_retry(
                    lambda: gemini_client.generate_content(text_content),
                    label="grade_assignment_gemini_text",
                )
            if token_tracker:
                token_tracker.record_gemini(response, actual_model)
            response_text = response.text.strip()

        else:
            # OpenAI API call with structured output for guaranteed schema
            try:
                response = with_retry(lambda: openai_client.beta.chat.completions.parse(
                    model=ai_model,
                    messages=messages,
                    response_format=GradingResponse,
                    max_tokens=2000,
                    temperature=0,
                    seed=42
                ), label="grade_assignment_structured")
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
                parsed = response.choices[0].message.parsed
                if parsed:
                    result = parsed.model_dump()
                    original_text = json.dumps(result)
                    _logger.info(f"  ✅ Structured output parsed successfully")
                    # Skip all JSON cleanup — jump straight to post-processing below
                else:
                    # Model refused or structured parse failed — fall back to text
                    response_text = response.choices[0].message.content or ""
                    _logger.info(f"  ⚠️  Structured output empty, falling back to text parse")
                    result = None
            except Exception as structured_err:
                # Structured output not supported for this model — fall back to standard call
                _logger.info(f"  ⚠️  Structured output failed ({structured_err}), falling back to standard API")
                response = with_retry(lambda: openai_client.chat.completions.create(
                    model=ai_model,
                    messages=messages,
                    max_tokens=2000,
                    temperature=0,
                    seed=42
                ), label="grade_assignment_fallback")
                if token_tracker:
                    token_tracker.record_openai(response, ai_model)
                response_text = response.choices[0].message.content.strip()
                result = None

            # If structured output succeeded, skip text parsing
            if result is not None:
                pass  # result already set from parsed.model_dump()
            else:
                # Text fallback: clean up and parse JSON manually
                if response_text.startswith("```"):
                    lines = response_text.split('\n')
                    start = 1 if lines[0].startswith("```") else 0
                    end = len(lines)
                    for i in range(len(lines)-1, -1, -1):
                        if lines[i].strip() == "```":
                            end = i
                            break
                    response_text = '\n'.join(lines[start:end])
                response_text = response_text.strip()
                original_text = response_text

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # Try basic JSON repair for text fallback
                    result = _try_parse_json_fallback(response_text)
                    if result is None:
                        raise

        # For Claude/Gemini providers, parse their text response
        if provider in ("anthropic", "gemini"):
            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```"):
                lines = response_text.split('\n')
                start = 1 if lines[0].startswith("```") else 0
                end = len(lines)
                for i in range(len(lines)-1, -1, -1):
                    if lines[i].strip() == "```":
                        end = i
                        break
                response_text = '\n'.join(lines[start:end])
            response_text = response_text.strip()
            original_text = response_text

            result = _try_parse_json_fallback(response_text)
            if result is None:
                raise json.JSONDecodeError("Failed to parse response", response_text, 0)

        # Post-processing: fix double-escaped newlines from some AI providers
        feedback = result.get("feedback", "")
        if "\\n" in feedback:
            feedback = feedback.replace("\\n", "\n")
            result["feedback"] = feedback

        # Strip any accidental bilingual sections from grading response
        if "\n---\n" in feedback:
            feedback = feedback.split("\n---\n")[0].strip()
            result["feedback"] = feedback

        # Two-pass bilingual feedback: translate via separate dedicated API call
        if ell_language and result.get("feedback"):
            _logger.info(f"  🌐 Translating feedback to {ell_language}...")
            translated = _translate_feedback(result["feedback"], ell_language, ai_model, token_tracker=token_tracker)
            if translated:
                result["feedback"] = result["feedback"] + "\n\n---\n\n" + translated
                _logger.info(f"  ✅ Bilingual feedback added ({ell_language})")
            else:
                _logger.info(f"  ⚠️  Translation failed, feedback remains English only")

        # === APPLY CUSTOM RUBRIC WEIGHTS (single-pass) ===
        # rubric_weights is a list of 4 weights [content, completeness, writing, effort]
        if rubric_weights and len(rubric_weights) == 4:
            breakdown = result.get("breakdown", {})
            cat_pcts = [
                breakdown.get("content_accuracy", 0) / 40,
                breakdown.get("completeness", 0) / 25,
                breakdown.get("writing_quality", 0) / 20,
                breakdown.get("effort_engagement", 0) / 15,
            ]
            total_weight = sum(rubric_weights) or 100
            weighted_score = sum(
                pct * (w / total_weight)
                for pct, w in zip(cat_pcts, rubric_weights)
            )
            result["score"] = int(round(weighted_score * 100))
            result["score"] = max(0, min(100, result["score"]))
            s = result["score"]
            result["letter_grade"] = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 60 else "F"
            _logger.info(f"  📊 Rubric-weighted score: {result['score']} ({result['letter_grade']}) [weights: {rubric_weights}]")

        # === DETERMINISTIC COMPLETENESS CAPS (single-pass) ===
        # The AI prompt asks it to penalize blank sections, but it doesn't reliably do so.
        # Apply the same deterministic caps as grade_multipass() based on actual extraction data.
        if extraction_result:
            extraction_blanks = extraction_result.get("blank_questions", [])
            extraction_missing = extraction_result.get("missing_sections", [])
            blank_count = len(extraction_blanks) + len(extraction_missing)

            # Override AI's unanswered_questions with deterministic extraction data.
            # The AI often misses blank/missing sections even when told about them.
            if blank_count > 0:
                deterministic_unanswered = extraction_blanks + extraction_missing
                ai_unanswered = result.get("unanswered_questions", [])
                # Merge: keep AI's list but ensure extraction-detected items are included
                merged = list(ai_unanswered)
                for item in deterministic_unanswered:
                    if not any(item.lower() in existing.lower() or existing.lower() in item.lower() for existing in merged):
                        merged.append(item)
                if merged != ai_unanswered:
                    _logger.info(f"  🔧 Overriding unanswered_questions: AI had {len(ai_unanswered)}, extraction found {len(deterministic_unanswered)}, merged to {len(merged)}")
                result["unanswered_questions"] = merged

            if blank_count > 0:
                if grading_style == 'strict':
                    caps = {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
                elif grading_style == 'lenient':
                    caps = {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
                else:
                    caps = {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}
                cap = caps.get(blank_count, 0) if blank_count < len(caps) else 0
                old_score = result["score"]
                if old_score > cap:
                    result["score"] = cap
                    s = result["score"]
                    result["letter_grade"] = "A" if s >= 90 else "B" if s >= 80 else "C" if s >= 70 else "D" if s >= 60 else "F"
                    blank_names = extraction_blanks + extraction_missing
                    _logger.info(f"  📉 Completeness cap: {blank_count} blank/missing → capped {old_score} to {cap} ({result['letter_grade']})")
                    _logger.info(f"      Blank sections: {blank_names}")

        # Update student's writing profile (only if not flagged as AI)
        # This builds their baseline for future AI detection
        if student_id and student_id != "UNKNOWN" and current_writing_style:
            ai_flag = result.get("ai_detection", {}).get("flag", "none")
            if ai_flag not in ["likely", "possible"]:
                try:
                    update_writing_profile(student_id, current_writing_style, student_name)
                    _logger.info(f"  📊 Updated writing profile for {student_name}")
                except Exception as e:
                    _logger.info(f"  Note: Could not update writing profile: {e}")

        # Add style comparison info to result for transparency
        if style_comparison and style_comparison.get("ai_likelihood") in ["likely", "possible"]:
            result["writing_style_deviation"] = style_comparison

        # Add audit trail data
        result["_audit"] = {
            "ai_input": extracted_responses_section,
            "ai_response": original_text
        }

        # Add token usage tracking
        if token_tracker:
            result["token_usage"] = token_tracker.summary()

        return result

    except json.JSONDecodeError as e:
        _logger.info(f"  ⚠️  Error parsing AI response: {e}")
        # Try to show response content for debugging
        try:
            raw_preview = response_text[:800] if len(response_text) > 800 else response_text
            _logger.info(f"  ⚠️  Raw response preview:\n{raw_preview}")
            # Write full response to temp file for debugging
            import tempfile
            debug_file = tempfile.NamedTemporaryFile(mode='w', suffix='_graider_debug.json', delete=False)
            debug_file.write(response_text)
            debug_file.close()
            _logger.info(f"  ⚠️  Full response saved to: {debug_file.name}")
        except Exception:
            _logger.info(f"  ⚠️  Could not display response")

        # Try to extract key fields with regex as fallback
        try:
            score_match = re.search(r'"score":\s*(\d+)', response_text)
            grade_match = re.search(r'"letter_grade":\s*"([A-F])"', response_text)
            feedback_match = re.search(r'"feedback":\s*"([^"]{20,500})', response_text)

            if score_match and grade_match:
                _logger.info(f"  ✅ Recovered score/grade from malformed JSON")
                return {
                    "score": int(score_match.group(1)),
                    "letter_grade": grade_match.group(1),
                    "breakdown": {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0},
                    "feedback": feedback_match.group(1) + "..." if feedback_match else "Grading completed but response was malformed.",
                    "student_responses": [],
                    "unanswered_questions": [],
                    "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
                    "plagiarism_detection": {"flag": "none", "reason": ""},
                    "skills_demonstrated": {"strengths": [], "developing": []},
                    "json_recovery": True
                }
        except Exception:
            pass

        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"Error grading - AI returned invalid JSON. Please review manually."
        }
    except Exception as e:
        _logger.info(f"  ⚠️  API error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": f"API error: {e}"
        }
