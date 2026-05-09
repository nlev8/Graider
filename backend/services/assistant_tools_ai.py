"""
AI-Powered Assistant Tools
==========================
Tools that require AI generation via Claude Haiku.
These complement the zero-cost local-data tools with content
that cannot be produced from templates or local data alone.
"""
import json
import os

from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _load_accommodations,
    _load_roster, _fuzzy_name_match, _safe_int_score,
)
from backend.utils.compliance import anonymize_for_ai, deanonymize, audit_tool_action, require_teacher_id


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

AI_TOOL_DEFINITIONS = [
    {
        "name": "differentiate_content",
        "description": "Rewrite text at multiple reading levels (below/on/above grade). Uses AI to adapt vocabulary, sentence complexity, and detail. Use when teacher asks to differentiate a passage for varied learners.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The passage or content to differentiate"
                },
                "levels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Reading levels to generate (default: ['below', 'on', 'above'])"
                },
                "grade_level": {
                    "type": "string",
                    "description": "Target grade level (e.g. '5th', '8th', '11th')"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "generate_questions_from_text",
        "description": "Generate comprehension and analysis questions from a text passage. Returns questions with answer keys. Use when teacher needs quick formative assessment items from reading material.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The passage to generate questions from"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of questions to generate (default 5)"
                },
                "types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["recall", "inference", "analysis", "evaluation"]
                    },
                    "description": "Question types to include (default: all four)"
                },
                "grade_level": {
                    "type": "string",
                    "description": "Target grade level for question complexity"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "generate_iep_progress_notes",
        "description": "Synthesize IEP progress monitoring narratives from a student's grade history and accommodations. Produces compliant progress notes with trends and recommendations. Use when teacher needs IEP updates or progress reports.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to look up"
                },
                "goal_area": {
                    "type": "string",
                    "description": "Specific goal area to focus on (e.g. 'reading comprehension', 'written expression'). Omit for all areas."
                }
            },
            "required": ["student_name"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

HAIKU_MODEL = "claude-haiku-4-5-20251001"


def _call_haiku(prompt, max_tokens=1500, teacher_id=None):
    """Make a single Haiku call via AnthropicAdapter. Returns parsed JSON dict or error dict."""
    from backend.api_keys import get_api_key
    from backend.services.llm_adapter import AnthropicAdapter, LLMRequest, Message, TextPart
    api_key = get_api_key('anthropic', teacher_id or 'local-dev')
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}
    # Adapter call. Any exception here (including a JSONDecodeError raised
    # inside the adapter chain itself, e.g. mangled wire response) is an
    # adapter-side failure — classify as "AI call failed" and never reach
    # the response-text parser. Splitting this from the parse try/except
    # also prevents an UnboundLocalError on `text` if the adapter raises
    # before line 119 executes.
    try:
        adapter = AnthropicAdapter(api_key=api_key)
        response = adapter.chat(LLMRequest(
            model=HAIKU_MODEL,
            max_tokens=max_tokens,
            messages=[Message(role="user", content=[TextPart(text=prompt)])],
            metadata={"feature_label": "assistant_tools_ai"},
        ))
        text = (response.content_parts[0].text if response.content_parts else "").strip()
    except Exception as e:
        return {"error": f"AI call failed: {str(e)}"}

    # Response-text parse. Try direct JSON parse FIRST: this handles
    # (a) JSON whose string values legitimately contain backticks
    # (`{"description": "use ``` to escape"}`), and (b) the common happy
    # path where the AI returned no fences at all.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass  # fall through to fence-strip retry

    # Strip markdown fences. Search for the first fence anywhere in the
    # text (not just at position 0) so a preamble like
    # "Here's the result:\n```json\n{...}\n```" still parses. Three
    # post-strip shapes:
    #   1. Single-line fence (no newline): strip backticks
    #   2. Multi-line fence with closing: take content between newline
    #      and last fence
    #   3. Multi-line fence with NO closing (labeled or bare): take
    #      everything after the first newline
    if "```" in text:
        first_fence = text.find("```")
        first_nl = text.find("\n", first_fence)
        if first_nl == -1:
            text = text.strip("`").strip()
        else:
            last_fence = text.rfind("```")
            if last_fence > first_nl:
                text = text[first_nl + 1:last_fence].strip()
            else:
                text = text[first_nl + 1:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "AI returned non-JSON response", "raw": text}


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

def differentiate_content(text="", levels=None, grade_level="6th", **kwargs):
    """Rewrite text at multiple reading levels."""
    teacher_id = kwargs.get('teacher_id', 'local-dev')
    require_teacher_id(teacher_id)
    text = (text or "").strip()
    if not text:
        return {"error": "text is required"}

    levels = levels or ["below", "on", "above"]
    grade = grade_level

    prompt = (
        "You are an expert reading specialist. Rewrite the following passage at "
        f"each of these reading levels for a {grade}-grade classroom: {', '.join(levels)}.\n\n"
        "Rules:\n"
        "- 'below' = simpler vocabulary, shorter sentences, fewer details\n"
        "- 'on' = grade-appropriate vocabulary and complexity\n"
        "- 'above' = richer vocabulary, more complex sentences, deeper detail\n"
        "- Keep the same core meaning and facts in every version\n"
        "- Each version should be roughly the same length as the original\n\n"
        f"Original text:\n{text}\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        '{"versions": [{"level": "<level>", "text": "<rewritten text>"}]}'
    )
    return _call_haiku(prompt, max_tokens=2000, teacher_id=teacher_id)


def generate_questions_from_text(text="", count=5, types=None, grade_level="6th", **kwargs):
    """Generate comprehension questions from a passage."""
    teacher_id = kwargs.get('teacher_id', 'local-dev')
    require_teacher_id(teacher_id)
    text = (text or "").strip()
    if not text:
        return {"error": "text is required"}

    types = types or ["recall", "inference", "analysis", "evaluation"]
    grade = grade_level

    prompt = (
        "You are an expert teacher creating assessment questions. Generate "
        f"{count} questions from the following passage for {grade}-grade students.\n\n"
        f"Question types to include: {', '.join(types)}\n"
        "- recall: fact-based, directly stated in text\n"
        "- inference: requires reading between the lines\n"
        "- analysis: break down structure, cause/effect, compare/contrast\n"
        "- evaluation: judge, critique, form opinions with evidence\n\n"
        "Distribute questions across the requested types as evenly as possible.\n\n"
        f"Passage:\n{text}\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        '{"questions": [{"question": "...", "type": "recall|inference|analysis|evaluation", "answer_key": "..."}]}'
    )
    return _call_haiku(prompt, max_tokens=2000, teacher_id=teacher_id)


def generate_iep_progress_notes(student_name="", goal_area="", **kwargs):
    """Synthesize IEP progress notes from student grade data."""
    teacher_id = kwargs.get('teacher_id', 'local-dev')
    require_teacher_id(teacher_id)
    student_name = (student_name or "").strip()
    if not student_name:
        return {"error": "student_name is required"}

    # --- Gather local data ---
    master = _load_master_csv(teacher_id=teacher_id)
    results = _load_results(teacher_id)
    accommodations = _load_accommodations(teacher_id)
    roster = _load_roster(teacher_id)

    # Find student scores from master CSV
    student_scores = []
    for row in master:
        name_field = row.get("Student Name", row.get("student_name", ""))
        if _fuzzy_name_match(student_name, name_field):
            score = _safe_int_score(row.get("Score", row.get("score")))
            assignment = row.get("Assignment", row.get("assignment", "Unknown"))
            if score is not None:
                student_scores.append({"assignment": assignment, "score": score})

    # Find student results (detailed rubric data)
    student_results = []
    for r in results:
        r_name = r.get("student_name", r.get("name", ""))
        if _fuzzy_name_match(student_name, r_name):
            student_results.append({
                "assignment": r.get("assignment", "Unknown"),
                "score": r.get("score"),
                "content": r.get("content_score"),
                "completeness": r.get("completeness_score"),
                "writing": r.get("writing_score"),
            })

    # Find accommodations
    student_accom = None
    for sid, accom in accommodations.items():
        if _fuzzy_name_match(student_name, sid):
            student_accom = accom
            break

    if not student_scores and not student_results:
        return {"error": f"No grade data found for '{student_name}'"}

    # --- Build prompt with summarized data ---
    data_summary = f"Student: {student_name}\n"
    if student_accom:
        data_summary += f"Accommodations: {', '.join(student_accom.get('presets', []))}\n"
        if student_accom.get("notes"):
            data_summary += f"Accommodation notes: {student_accom['notes']}\n"

    if student_scores:
        scores_only = [s["score"] for s in student_scores]
        data_summary += f"\nGrade history ({len(student_scores)} assignments):\n"
        for s in student_scores[-10:]:  # Last 10 for context
            data_summary += f"  - {s['assignment']}: {s['score']}%\n"
        data_summary += f"Average: {sum(scores_only) / len(scores_only):.1f}%\n"
        if len(scores_only) >= 3:
            recent = scores_only[-3:]
            earlier = scores_only[:3]
            trend_dir = "improving" if sum(recent) / len(recent) > sum(earlier) / len(earlier) else "declining"
            data_summary += f"Trend: {trend_dir}\n"

    if student_results:
        data_summary += "\nRubric category breakdowns (recent):\n"
        for r in student_results[-5:]:
            parts = [f"{r['assignment']}: overall={r.get('score', 'N/A')}"]
            if r.get("content") is not None:
                parts.append(f"content={r['content']}")
            if r.get("completeness") is not None:
                parts.append(f"completeness={r['completeness']}")
            if r.get("writing") is not None:
                parts.append(f"writing={r['writing']}")
            data_summary += f"  - {', '.join(parts)}\n"

    goal_filter = ""
    if goal_area:
        goal_filter = f"\nFocus specifically on the goal area: {goal_area}\n"

    prompt_text = (
        "You are a special education specialist writing IEP progress monitoring notes. "
        "Using the student data below, write professional progress notes suitable for "
        "an IEP progress report.\n\n"
        f"{data_summary}\n{goal_filter}\n"
        "Rules:\n"
        "- Use objective, data-driven language\n"
        "- Reference specific scores and trends\n"
        "- Include current performance level, trend direction, and recommendation\n"
        "- Keep language IEP-compliant and professional\n"
        "- If accommodations are listed, note whether they appear effective\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        '{"student_name": "...", "progress_notes": [{"goal_area": "...", '
        '"current_level": "...", "trend": "improving|stable|declining", '
        '"narrative": "...", "recommendation": "..."}]}'
    )

    # Anonymize student PII before sending to external AI
    roster_for_anon = [{"student_name": s.get("name", "")} for s in roster] if roster else []
    anon_prompt, name_mapping = anonymize_for_ai(prompt_text, roster_for_anon)

    audit_tool_action(teacher_id, 'generate_iep_progress_notes', 'SEND_AI')

    result = _call_haiku(anon_prompt, max_tokens=1500, teacher_id=teacher_id)

    # Deanonymize the response to restore student names
    if isinstance(result, dict) and name_mapping:
        result_str = json.dumps(result)
        result_str = deanonymize(result_str, name_mapping)
        try:
            result = json.loads(result_str)
        except json.JSONDecodeError:
            pass  # Keep original result if deanonymized string isn't valid JSON

    return result


# ═══════════════════════════════════════════════════════
# EXPORT MAP
# ═══════════════════════════════════════════════════════

AI_TOOL_DEFINITIONS = AI_TOOL_DEFINITIONS  # re-export for clarity

AI_TOOL_HANDLERS = {
    "differentiate_content": differentiate_content,
    "generate_questions_from_text": generate_questions_from_text,
    "generate_iep_progress_notes": generate_iep_progress_notes,
}
