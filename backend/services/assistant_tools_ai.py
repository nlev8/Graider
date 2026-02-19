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
    _fuzzy_name_match, _safe_int_score,
)


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


def _get_anthropic_client():
    """Lazy-import anthropic and return a client, or None + error message."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not configured"
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key), None
    except ImportError:
        return None, "anthropic package not installed"


def _call_haiku(prompt, max_tokens=1500):
    """Make a single Haiku call. Returns parsed JSON dict or error dict."""
    client, err = _get_anthropic_client()
    if err:
        return {"error": err}
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            first_nl = text.index("\n")
            last_fence = text.rfind("```")
            text = text[first_nl + 1:last_fence].strip()
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "AI returned non-JSON response", "raw": text}
    except Exception as e:
        return {"error": f"AI call failed: {str(e)}"}


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

def differentiate_content(args):
    """Rewrite text at multiple reading levels."""
    text = args.get("text", "").strip()
    if not text:
        return {"error": "text is required"}

    levels = args.get("levels", ["below", "on", "above"])
    grade = args.get("grade_level", "6th")

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
    return _call_haiku(prompt, max_tokens=2000)


def generate_questions_from_text(args):
    """Generate comprehension questions from a passage."""
    text = args.get("text", "").strip()
    if not text:
        return {"error": "text is required"}

    count = args.get("count", 5)
    types = args.get("types", ["recall", "inference", "analysis", "evaluation"])
    grade = args.get("grade_level", "6th")

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
    return _call_haiku(prompt, max_tokens=2000)


def generate_iep_progress_notes(args):
    """Synthesize IEP progress notes from student grade data."""
    student_name = args.get("student_name", "").strip()
    if not student_name:
        return {"error": "student_name is required"}

    goal_area = args.get("goal_area", "")

    # --- Gather local data ---
    master = _load_master_csv()
    results = _load_results()
    accommodations = _load_accommodations()

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

    prompt = (
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
    return _call_haiku(prompt, max_tokens=1500)


# ═══════════════════════════════════════════════════════
# EXPORT MAP
# ═══════════════════════════════════════════════════════

AI_TOOL_DEFINITIONS = AI_TOOL_DEFINITIONS  # re-export for clarity

AI_TOOL_HANDLERS = {
    "differentiate_content": differentiate_content,
    "generate_questions_from_text": generate_questions_from_text,
    "generate_iep_progress_notes": generate_iep_progress_notes,
}
