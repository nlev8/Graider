"""
Planning & Classroom Tools
===========================
Tools for lesson planning, bell ringers, exit tickets, grouping, and sub plans.
Zero AI API calls — all data from local files.
"""
import os
import json
import base64
from datetime import datetime, timedelta
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_standards, _load_master_csv, _load_settings, _load_calendar,
    _normalize_period, _fuzzy_name_match, _load_roster, _safe_int_score,
    _load_saved_lessons, _normalize_assignment_name,
    CALENDAR_FILE, LESSONS_DIR, SETTINGS_FILE,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

PLANNING_TOOL_DEFINITIONS = [
    {
        "name": "suggest_remediation",
        "description": "Map student weaknesses to concrete activities using the teacher's enabled edtech tools. Suggests specific Kahoot/Blooket/Gimkit/Quizlet activities, review worksheets, and grouping strategies based on grade data. Zero cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment to analyze weaknesses from (partial match, omit for recent)"
                },
                "weak_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific weak areas to address (e.g., ['writing quality', 'vocabulary'])"
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period"
                }
            }
        }
    },
    {
        "name": "align_to_standards",
        "description": "Show which standards a topic covers and which standards remain unassessed. Helps teachers ensure full standards coverage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic or keyword to check standard alignment for"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "get_pacing_status",
        "description": "Compare calendar progress vs total standards — are you ahead, behind, or on track? Shows standards covered vs remaining and estimated completion.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "generate_bell_ringer",
        "description": "Generate a quick warm-up activity from yesterday's or today's lesson vocabulary and standards. Returns 2-3 review questions. Zero cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (default: today)"
                },
                "period": {
                    "type": "string",
                    "description": "Period for differentiation"
                }
            }
        }
    },
    {
        "name": "generate_exit_ticket",
        "description": "Generate 2-3 quick check questions from today's lesson or a specified topic. Returns questions with expected answers for quick formative assessment. Zero cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (default: today)"
                },
                "topic": {
                    "type": "string",
                    "description": "Topic override (otherwise uses today's scheduled lesson)"
                },
                "period": {
                    "type": "string",
                    "description": "Period for differentiation"
                }
            }
        }
    },
    {
        "name": "suggest_grouping",
        "description": "Create student groups by performance — heterogeneous (mixed levels) or homogeneous (similar levels). Uses grade data to form balanced or targeted groups.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Class period (required)"
                },
                "group_type": {
                    "type": "string",
                    "enum": ["heterogeneous", "homogeneous"],
                    "description": "Grouping strategy: mixed levels or similar levels"
                },
                "group_size": {
                    "type": "integer",
                    "description": "Students per group (default 4)"
                },
                "assignment_name": {
                    "type": "string",
                    "description": "Base grouping on this assignment's scores (omit for overall average)"
                }
            },
            "required": ["period", "group_type"]
        }
    },
    {
        "name": "generate_sub_plans",
        "description": "Build substitute teacher plans from the teaching calendar and saved lessons. Generates a formatted summary of what to teach, materials needed, and class procedures → Word doc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date for multi-day plans (omit for single day)"
                }
            },
            "required": ["date"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _get_lesson_for_date(cal, target_date):
    """Find a scheduled lesson for a specific date."""
    for lesson in cal.get("scheduled_lessons", []):
        if lesson.get("date") == target_date:
            return lesson
    return None


def _get_standards_for_lesson(lesson):
    """Load vocabulary and standards for a scheduled lesson from its lesson file."""
    if not lesson:
        return None
    lesson_file = lesson.get("lesson_file")
    if not lesson_file:
        return {"title": lesson.get("lesson_title", ""), "vocab": [], "standards": []}

    filepath = os.path.join(LESSONS_DIR, lesson_file)
    if not os.path.exists(filepath):
        return {"title": lesson.get("lesson_title", ""), "vocab": [], "standards": []}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "title": data.get("title", lesson.get("lesson_title", "")),
            "vocab": data.get("vocabulary", []),
            "standards": data.get("standards", []),
            "objectives": data.get("objectives", []),
            "topics": [d.get("topic", "") for d in data.get("days", [])],
        }
    except Exception:
        return {"title": lesson.get("lesson_title", ""), "vocab": [], "standards": []}


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

def suggest_remediation(assignment_name=None, weak_areas=None, period=None):
    """Map weaknesses to activities using teacher's enabled edtech tools."""
    settings = _load_settings()
    config = settings.get("config", {})
    available_tools = config.get("availableTools", [])

    rows = _load_master_csv(period_filter=period or "all")
    if not rows:
        return {"error": "No grade data found."}

    # Determine weak areas from data if not provided
    if not weak_areas:
        weak_areas = []
        cat_totals = defaultdict(list)
        target_rows = rows
        if assignment_name:
            norm = _normalize_assignment_name(assignment_name).lower()
            target_rows = [r for r in rows if norm in _normalize_assignment_name(r.get("assignment", "")).lower()]

        for r in target_rows:
            for cat in ("content", "completeness", "writing", "effort"):
                val = _safe_int_score(r.get(cat))
                if val > 0:
                    cat_totals[cat].append(val)

        cat_labels = {"content": "Content Accuracy", "completeness": "Completeness",
                      "writing": "Writing Quality", "effort": "Effort & Engagement"}
        for cat, vals in cat_totals.items():
            avg = sum(vals) / len(vals)
            if avg < 75:
                weak_areas.append(cat_labels.get(cat, cat))

    if not weak_areas:
        return {"message": "No significant weaknesses detected. Students are performing well across all categories."}

    # Map tools to activity suggestions
    tool_map = {
        "kahoot": "generate_kahoot_quiz",
        "blooket": "generate_blooket_set",
        "gimkit": "generate_gimkit_kit",
        "quizlet": "generate_quizlet_set",
        "nearpod": "generate_nearpod_questions",
        "canvas": "generate_canvas_qti",
    }

    suggestions = []
    for area in weak_areas:
        area_suggestions = {"weakness": area, "activities": []}
        area_lower = area.lower()

        # Suggest relevant tools based on weakness type
        if "content" in area_lower or "vocabulary" in area_lower or "accuracy" in area_lower:
            for tool_name in ["quizlet", "kahoot", "blooket"]:
                if tool_name in available_tools or f"custom:{tool_name}" in available_tools:
                    area_suggestions["activities"].append({
                        "tool": tool_map.get(tool_name, tool_name),
                        "activity": f"Vocabulary review on {tool_name.title()}",
                        "description": f"Generate a {tool_name.title()} set targeting content accuracy gaps",
                    })

        if "writing" in area_lower:
            area_suggestions["activities"].append({
                "tool": "generate_worksheet",
                "activity": "Writing practice worksheet",
                "description": "Short-answer or Cornell Notes worksheet focused on written expression",
            })

        if "completeness" in area_lower:
            area_suggestions["activities"].append({
                "tool": "suggest_grouping",
                "activity": "Peer accountability groups",
                "description": "Heterogeneous groups where strong completers model work habits",
            })

        if "effort" in area_lower or "engagement" in area_lower:
            for tool_name in ["gimkit", "kahoot", "blooket"]:
                if tool_name in available_tools:
                    area_suggestions["activities"].append({
                        "tool": tool_map.get(tool_name, tool_name),
                        "activity": f"Gamified review on {tool_name.title()}",
                        "description": f"Use {tool_name.title()}'s game modes to boost engagement",
                    })

        # Always suggest a bell ringer for review
        area_suggestions["activities"].append({
            "tool": "generate_bell_ringer",
            "activity": "Daily bell ringer review",
            "description": f"Start each class with 2-3 quick questions on {area.lower()}",
        })

        suggestions.append(area_suggestions)

    return {
        "weak_areas": weak_areas,
        "available_tools": available_tools,
        "suggestions": suggestions,
    }


def align_to_standards(topic):
    """Show which standards a topic covers and which remain unassessed."""
    if not topic:
        return {"error": "topic is required."}

    all_standards = _load_standards()
    if not all_standards:
        return {"error": "No standards loaded. Check Settings > Subject and State."}

    topic_lower = topic.lower()
    covered = []
    uncovered = []

    for s in all_standards:
        matches = (
            topic_lower in s.get("benchmark", "").lower()
            or topic_lower in " ".join(s.get("topics", [])).lower()
            or topic_lower in " ".join(s.get("vocabulary", [])).lower()
        )
        entry = {
            "code": s.get("code", ""),
            "benchmark": s.get("benchmark", "")[:80],
            "dok": s.get("dok", ""),
        }
        if matches:
            covered.append(entry)
        else:
            uncovered.append(entry)

    # Check which standards have been assessed (appear in graded assignments)
    rows = _load_master_csv(period_filter="all")
    assessed_topics = set()
    for r in rows:
        assign = r.get("assignment", "").lower()
        assessed_topics.add(assign)

    return {
        "topic": topic,
        "covered_standards": covered,
        "covered_count": len(covered),
        "uncovered_count": len(uncovered),
        "total_standards": len(all_standards),
        "coverage_pct": round(len(covered) / max(len(all_standards), 1) * 100, 1),
    }


def get_pacing_status():
    """Compare calendar progress vs total standards."""
    all_standards = _load_standards()
    if not all_standards:
        return {"error": "No standards loaded. Check Settings > Subject and State."}

    cal = _load_calendar()
    lessons = cal.get("scheduled_lessons", [])

    today = datetime.now().strftime("%Y-%m-%d")
    past_lessons = [l for l in lessons if l.get("date", "") <= today]
    future_lessons = [l for l in lessons if l.get("date", "") > today]

    # Count unique standards covered by lessons
    covered_standards = set()
    for lesson in past_lessons:
        lesson_data = _get_standards_for_lesson(lesson)
        if lesson_data:
            for s in lesson_data.get("standards", []):
                covered_standards.add(s)

    total = len(all_standards)
    covered = len(covered_standards)
    remaining = total - covered

    # Estimate pacing
    settings = _load_settings()
    config = settings.get("config", {})

    # Simple heuristic: if we've covered X% of standards and are Y% through the year
    # Assume ~180 school days, estimate position
    days_scheduled = len(past_lessons) + len(future_lessons)
    days_completed = len(past_lessons)

    if days_scheduled > 0:
        pct_time = round(days_completed / days_scheduled * 100, 1)
    else:
        pct_time = 0

    pct_standards = round(covered / max(total, 1) * 100, 1)

    if pct_standards >= pct_time + 5:
        status = "ahead"
    elif pct_standards <= pct_time - 5:
        status = "behind"
    else:
        status = "on_track"

    return {
        "status": status,
        "total_standards": total,
        "standards_covered": covered,
        "standards_remaining": remaining,
        "pct_standards_covered": pct_standards,
        "lessons_completed": days_completed,
        "lessons_scheduled": len(future_lessons),
        "pct_calendar_elapsed": pct_time,
        "covered_standard_codes": list(covered_standards)[:20],
    }


def generate_bell_ringer(date=None, period=None):
    """Quick warm-up from yesterday's or today's lesson vocab/standards."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    cal = _load_calendar()

    # Try yesterday's lesson first (review), then today's
    yesterday = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    lesson = _get_lesson_for_date(cal, yesterday) or _get_lesson_for_date(cal, date)

    if not lesson:
        # Fall back to most recent lesson before the date
        past_lessons = [l for l in cal.get("scheduled_lessons", []) if l.get("date", "") < date]
        past_lessons.sort(key=lambda l: l.get("date", ""), reverse=True)
        lesson = past_lessons[0] if past_lessons else None

    if not lesson:
        return {"error": "No recent lessons found on the calendar. Schedule lessons first."}

    lesson_data = _get_standards_for_lesson(lesson)
    title = lesson_data.get("title", lesson.get("lesson_title", "")) if lesson_data else lesson.get("lesson_title", "")
    vocab = lesson_data.get("vocab", []) if lesson_data else []
    standard_codes = lesson_data.get("standards", []) if lesson_data else []

    # Build bell ringer questions from vocab and standards
    questions = []

    # Vocab review questions
    all_standards = _load_standards()
    standard_vocab = {}
    for s in all_standards:
        for code in standard_codes:
            if s.get("code", "") == code:
                for term in s.get("vocabulary", []):
                    standard_vocab[term] = s.get("benchmark", "")[:80]

    # Use lesson vocab if available, otherwise standard vocab
    target_vocab = vocab or list(standard_vocab.keys())

    for term in target_vocab[:2]:
        questions.append({
            "question": f"Define '{term}' in your own words.",
            "expected_answer": standard_vocab.get(term, f"Key term from {title}"),
            "type": "vocab_review",
        })

    # Add a recall question
    if title:
        questions.append({
            "question": f"Name one key concept from yesterday's lesson on '{title}'.",
            "expected_answer": f"Any concept from {title}",
            "type": "recall",
        })

    return {
        "date": date,
        "source_lesson": title,
        "source_date": lesson.get("date", ""),
        "questions": questions[:3],
        "vocabulary": target_vocab[:5],
        "standards": standard_codes,
    }


def generate_exit_ticket(date=None, topic=None, period=None):
    """2-3 quick check questions from today's lesson/standard."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    cal = _load_calendar()
    lesson = _get_lesson_for_date(cal, date)

    lesson_title = topic or ""
    lesson_vocab = []
    standard_codes = []

    if lesson and not topic:
        lesson_data = _get_standards_for_lesson(lesson)
        if lesson_data:
            lesson_title = lesson_data.get("title", lesson.get("lesson_title", ""))
            lesson_vocab = lesson_data.get("vocab", [])
            standard_codes = lesson_data.get("standards", [])

    if not lesson_title and not topic:
        return {"error": "No lesson scheduled for this date and no topic provided."}

    search_topic = topic or lesson_title
    all_standards = _load_standards()

    # Find matching standards
    matched_standards = []
    topic_lower = search_topic.lower()
    for s in all_standards:
        if (topic_lower in s.get("benchmark", "").lower()
                or topic_lower in " ".join(s.get("topics", [])).lower()
                or s.get("code", "") in standard_codes):
            matched_standards.append(s)

    questions = []

    # Question 1: Key concept check
    if matched_standards:
        s = matched_standards[0]
        eq = s.get("essential_questions", [])
        if eq:
            questions.append({
                "question": eq[0],
                "expected_answer": s.get("benchmark", "")[:100],
                "standard": s.get("code", ""),
                "type": "essential_question",
            })

    # Question 2: Vocabulary
    target_vocab = lesson_vocab or []
    if not target_vocab and matched_standards:
        for s in matched_standards:
            target_vocab.extend(s.get("vocabulary", []))

    if target_vocab:
        term = target_vocab[0]
        questions.append({
            "question": f"Explain the significance of '{term}' in today's lesson.",
            "expected_answer": f"Connection to {search_topic}",
            "type": "vocab_application",
        })

    # Question 3: Application/reflection
    questions.append({
        "question": f"What is one thing you learned about {search_topic} that you found interesting or surprising?",
        "expected_answer": "Open-ended reflection",
        "type": "reflection",
    })

    return {
        "date": date,
        "topic": search_topic,
        "source_lesson": lesson_title,
        "questions": questions[:3],
        "standards": standard_codes,
    }


def suggest_grouping(period, group_type, group_size=None, assignment_name=None):
    """Create student groups by performance."""
    if not period:
        return {"error": "period is required."}
    if group_type not in ("heterogeneous", "homogeneous"):
        return {"error": "group_type must be 'heterogeneous' or 'homogeneous'."}

    group_size = group_size or 4

    rows = _load_master_csv(period_filter=period)
    if not rows:
        return {"error": f"No grade data found for {period}."}

    # Calculate per-student averages
    student_scores = defaultdict(list)
    for r in rows:
        name = r.get("student_name", "")
        if assignment_name:
            norm = _normalize_assignment_name(assignment_name).lower()
            if norm not in _normalize_assignment_name(r.get("assignment", "")).lower():
                continue
        student_scores[name].append(_safe_int_score(r.get("score")))

    if not student_scores:
        return {"error": "No matching grade data for grouping."}

    # Sort students by average
    ranked = sorted(
        [(name, round(sum(scores) / len(scores), 1)) for name, scores in student_scores.items()],
        key=lambda x: -x[1]
    )

    groups = []
    if group_type == "heterogeneous":
        # Zigzag assignment: top with bottom
        num_groups = max(1, len(ranked) // group_size)
        groups = [[] for _ in range(num_groups)]
        direction = 1
        group_idx = 0
        for student, avg in ranked:
            groups[group_idx].append({"student": student, "avg": avg})
            group_idx += direction
            if group_idx >= num_groups:
                group_idx = num_groups - 1
                direction = -1
            elif group_idx < 0:
                group_idx = 0
                direction = 1
    else:
        # Homogeneous: sequential chunks
        for i in range(0, len(ranked), group_size):
            chunk = ranked[i:i + group_size]
            groups.append([{"student": name, "avg": avg} for name, avg in chunk])

    # Format output
    formatted_groups = []
    for i, g in enumerate(groups, 1):
        if not g:
            continue
        avgs = [m["avg"] for m in g]
        formatted_groups.append({
            "group_number": i,
            "members": g,
            "group_avg": round(sum(avgs) / len(avgs), 1),
        })

    return {
        "period": period,
        "group_type": group_type,
        "group_size": group_size,
        "total_students": len(ranked),
        "total_groups": len(formatted_groups),
        "groups": formatted_groups,
    }


def generate_sub_plans(date, end_date=None):
    """Build substitute teacher plans from calendar + saved lessons."""
    if not date:
        return {"error": "date is required."}

    if not end_date:
        end_date = date

    cal = _load_calendar()
    settings = _load_settings()
    config = settings.get("config", {})
    teacher_name = config.get("teacher_name", "Teacher")
    subject = config.get("subject", "")
    school = config.get("school_name", "")

    # Collect lessons for the date range
    current = datetime.strptime(date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    daily_plans = []

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        day_name = current.strftime("%A, %B %d")

        # Check for holidays
        is_holiday = False
        for h in cal.get("holidays", []):
            h_start = h.get("date", "")
            h_end = h.get("end_date") or h_start
            if h_start <= date_str <= h_end:
                daily_plans.append({"date": day_name, "holiday": h.get("name", "Holiday")})
                is_holiday = True
                break

        if not is_holiday and current.weekday() < 5:  # Skip weekends
            lesson = _get_lesson_for_date(cal, date_str)
            if lesson:
                lesson_data = _get_standards_for_lesson(lesson)
                daily_plans.append({
                    "date": day_name,
                    "lesson_title": lesson.get("lesson_title", ""),
                    "unit": lesson.get("unit", ""),
                    "day_number": lesson.get("day_number", ""),
                    "objectives": lesson_data.get("objectives", []) if lesson_data else [],
                    "vocabulary": lesson_data.get("vocab", []) if lesson_data else [],
                    "topics": lesson_data.get("topics", []) if lesson_data else [],
                })
            else:
                daily_plans.append({"date": day_name, "lesson_title": "No lesson scheduled", "note": "Plan independent work or review"})

        current += timedelta(days=1)

    # Try to generate a Word doc
    try:
        from backend.services.document_generator import generate_document

        blocks = [
            {"type": "heading", "text": f"Substitute Plans — {teacher_name}", "level": 1},
            {"type": "paragraph", "text": f"**Subject:** {subject} | **School:** {school}"},
            {"type": "paragraph", "text": f"**Date(s):** {date}" + (f" to {end_date}" if end_date != date else "")},
        ]

        for plan in daily_plans:
            blocks.append({"type": "heading", "text": plan["date"], "level": 2})
            if plan.get("holiday"):
                blocks.append({"type": "paragraph", "text": f"*No school — {plan['holiday']}*"})
                continue
            blocks.append({"type": "paragraph", "text": f"**Lesson:** {plan.get('lesson_title', 'N/A')}"})
            if plan.get("unit"):
                blocks.append({"type": "paragraph", "text": f"**Unit:** {plan['unit']}, Day {plan.get('day_number', '')}"})
            if plan.get("objectives"):
                blocks.append({"type": "heading", "text": "Objectives", "level": 3})
                blocks.append({"type": "bullet_list", "items": plan["objectives"]})
            if plan.get("vocabulary"):
                blocks.append({"type": "heading", "text": "Key Vocabulary", "level": 3})
                blocks.append({"type": "bullet_list", "items": plan["vocabulary"]})

        # General info
        blocks.append({"type": "heading", "text": "General Procedures", "level": 2})
        blocks.append({"type": "bullet_list", "items": [
            "Take attendance at the start of each period",
            "Students should work quietly and raise hands for questions",
            "Emergency plans are posted by the door",
            "Please leave notes on how each period went",
        ]})

        result = generate_document(
            title=f"Sub Plans - {date}",
            content=blocks,
        )
        result["daily_plans"] = daily_plans
        return result

    except ImportError:
        # Fallback: return structured data without doc
        return {
            "teacher": teacher_name,
            "subject": subject,
            "school": school,
            "date_range": f"{date} to {end_date}" if end_date != date else date,
            "daily_plans": daily_plans,
            "message": "Sub plans generated (document generator not available for Word export).",
        }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

PLANNING_TOOL_HANDLERS = {
    "suggest_remediation": suggest_remediation,
    "align_to_standards": align_to_standards,
    "get_pacing_status": get_pacing_status,
    "generate_bell_ringer": generate_bell_ringer,
    "generate_exit_ticket": generate_exit_ticket,
    "suggest_grouping": suggest_grouping,
    "generate_sub_plans": generate_sub_plans,
}
