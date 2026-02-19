"""
Communication & Reporting Tools
================================
Tools for generating progress reports, report card comments, feedback, and conference notes.
Zero AI API calls — template-based output from local grade data.
"""
import json
import os
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _load_settings, _load_roster,
    _load_accommodations, _fuzzy_name_match, _safe_int_score,
    _normalize_period, _extract_first_name, PARENT_CONTACTS_FILE,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

COMMUNICATION_TOOL_DEFINITIONS = [
    {
        "name": "generate_progress_report",
        "description": "Generate a printable progress report for a student or all students in a period. Returns structured data suitable for generate_document to create a Word doc. Zero cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name for individual report (omit for full class)"
                },
                "period": {
                    "type": "string",
                    "description": "Period filter"
                }
            }
        }
    },
    {
        "name": "generate_report_card_comments",
        "description": "Generate template-based report card comments from score patterns. NOT AI-generated — uses deterministic templates filled with actual data. Returns comments for each student.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Period filter (omit for all)"
                },
                "student_name": {
                    "type": "string",
                    "description": "Generate for a specific student only"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Max characters per comment (default 200)"
                }
            }
        }
    },
    {
        "name": "draft_student_feedback",
        "description": "Generate structured feedback for a student: strengths, growth areas, specific examples, and next steps. Built from full grade history — no AI API call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (required, fuzzy match)"
                }
            },
            "required": ["student_name"]
        }
    },
    {
        "name": "generate_parent_conference_notes",
        "description": "Generate a parent conference agenda with data, talking points, and action items for a specific student. Structured for generate_document to create a Word doc. Zero cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (required, fuzzy match)"
                }
            },
            "required": ["student_name"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _letter_grade(score):
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    return "F"


def _trend_word(scores):
    """Return a human-readable trend description."""
    if len(scores) < 2:
        return "insufficient data"
    first_half = scores[:len(scores) // 2] or scores[:1]
    second_half = scores[len(scores) // 2:] or scores[-1:]
    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    diff = second_avg - first_avg
    if diff >= 5:
        return "showing strong improvement"
    elif diff >= 2:
        return "improving"
    elif diff <= -5:
        return "declining significantly"
    elif diff <= -2:
        return "declining slightly"
    return "performing consistently"


def _comment_template(first_name, avg, trend, strongest_cat, weakest_cat, max_length):
    """Generate a report card comment from templates."""
    cat_labels = {"content": "content accuracy", "completeness": "completeness",
                  "writing": "writing quality", "effort": "effort and engagement"}
    strong_label = cat_labels.get(strongest_cat, strongest_cat)
    weak_label = cat_labels.get(weakest_cat, weakest_cat)

    # Templates based on score range
    if avg >= 90:
        template = f"{first_name} demonstrates excellent understanding of course material, particularly in {strong_label}. {first_name} is {trend}."
    elif avg >= 80:
        template = f"{first_name} shows solid performance with a {avg}% average. Strongest area is {strong_label}. To reach the next level, focus on {weak_label}."
    elif avg >= 70:
        template = f"{first_name} is meeting grade-level expectations with a {avg}% average. {first_name} is {trend}. Continued focus on {weak_label} will support growth."
    elif avg >= 60:
        template = f"{first_name} is working toward grade-level proficiency ({avg}% avg). {first_name} shows strength in {strong_label} but needs support with {weak_label}."
    else:
        template = f"{first_name} needs significant support to reach grade-level expectations ({avg}% avg). Priority area: {weak_label}. {first_name} is {trend}."

    if len(template) > max_length:
        template = template[:max_length - 3] + "..."
    return template


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

def generate_progress_report(student_name=None, period=None):
    """Generate structured progress report data."""
    rows = _load_master_csv(period_filter=period or "all")
    if not rows:
        return {"error": "No grade data found."}

    settings = _load_settings()
    config = settings.get("config", {})
    teacher_name = config.get("teacher_name", "Teacher")
    subject = config.get("subject", "")
    school = config.get("school_name", "")
    grading_period = config.get("grading_period", "")

    # Group by student
    student_data = defaultdict(list)
    for r in rows:
        name = r.get("student_name", "")
        if student_name and not _fuzzy_name_match(student_name, name):
            continue
        student_data[name].append(r)

    if not student_data:
        return {"error": f"No grades found for '{student_name}'." if student_name else "No grade data found."}

    reports = []
    for name, entries in sorted(student_data.items()):
        scores = [_safe_int_score(r.get("score")) for r in entries]
        avg = round(sum(scores) / len(scores), 1) if scores else 0

        # Category averages
        cats = {}
        for cat in ("content", "completeness", "writing", "effort"):
            vals = [_safe_int_score(r.get(cat)) for r in entries if r.get(cat)]
            if vals:
                cats[cat] = round(sum(vals) / len(vals), 1)

        # Assignment details (compact)
        assignments = [{"name": r.get("assignment", "")[:30], "score": _safe_int_score(r.get("score")),
                        "date": r.get("date", "")} for r in entries]
        assignments.sort(key=lambda a: a["date"])

        reports.append({
            "student_name": name,
            "period": entries[0].get("period", "") if entries else "",
            "overall_avg": avg,
            "letter_grade": _letter_grade(avg),
            "trend": _trend_word(scores),
            "assignments_completed": len(entries),
            "categories": cats,
            "assignments": assignments,
        })

    return {
        "teacher": teacher_name,
        "subject": subject,
        "school": school,
        "grading_period": grading_period,
        "report_count": len(reports),
        "reports": reports[:30],  # Cap for token efficiency
    }


def generate_report_card_comments(period=None, student_name=None, max_length=None):
    """Generate template-based report card comments."""
    max_length = max_length or 200
    rows = _load_master_csv(period_filter=period or "all")
    if not rows:
        return {"error": "No grade data found."}

    # Group by student
    student_data = defaultdict(list)
    for r in rows:
        name = r.get("student_name", "")
        if student_name and not _fuzzy_name_match(student_name, name):
            continue
        student_data[name].append(r)

    if not student_data:
        return {"error": f"No grades found for '{student_name}'." if student_name else "No grade data found."}

    comments = []
    for name, entries in sorted(student_data.items()):
        first_name = _extract_first_name(name)
        scores = [_safe_int_score(r.get("score")) for r in entries]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        trend = _trend_word(scores)

        # Find strongest/weakest categories
        cat_avgs = {}
        for cat in ("content", "completeness", "writing", "effort"):
            vals = [_safe_int_score(r.get(cat)) for r in entries if r.get(cat)]
            if vals:
                cat_avgs[cat] = sum(vals) / len(vals)

        sorted_cats = sorted(cat_avgs.items(), key=lambda x: x[1])
        weakest = sorted_cats[0][0] if sorted_cats else "content"
        strongest = sorted_cats[-1][0] if sorted_cats else "effort"

        comment = _comment_template(first_name, avg, trend, strongest, weakest, max_length)
        comments.append({
            "student_name": name,
            "avg": avg,
            "comment": comment,
        })

    return {
        "comment_count": len(comments),
        "max_length": max_length,
        "comments": comments[:30],
    }


def draft_student_feedback(student_name):
    """Structured feedback with strengths, growth areas, examples from history."""
    if not student_name:
        return {"error": "student_name is required."}

    rows = _load_master_csv(period_filter="all")
    results = _load_results()

    # Find student data
    student_rows = []
    student_results = []
    matched_name = None
    for r in rows:
        if _fuzzy_name_match(student_name, r.get("student_name", "")):
            if not matched_name:
                matched_name = r.get("student_name", "")
            student_rows.append(r)

    for r in results:
        if matched_name and _fuzzy_name_match(student_name, r.get("student_name", "")):
            student_results.append(r)

    if not student_rows:
        return {"error": f"No grades found for '{student_name}'."}

    first_name = _extract_first_name(matched_name)
    scores = [_safe_int_score(r.get("score")) for r in student_rows]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    student_rows.sort(key=lambda r: r.get("date", ""))

    # Category analysis
    cat_avgs = {}
    for cat in ("content", "completeness", "writing", "effort"):
        vals = [_safe_int_score(r.get(cat)) for r in student_rows if r.get(cat)]
        if vals:
            cat_avgs[cat] = round(sum(vals) / len(vals), 1)

    sorted_cats = sorted(cat_avgs.items(), key=lambda x: x[1])
    strengths_cats = [c for c, v in sorted_cats if v >= 80]
    growth_cats = [c for c, v in sorted_cats if v < 75]

    # Extract specific strengths and developing skills from results
    strength_skills = defaultdict(int)
    developing_skills = defaultdict(int)
    for r in student_results:
        skills = r.get("skills_demonstrated", {})
        if isinstance(skills, dict):
            for s in (skills.get("strengths", []) or []):
                strength_skills[s] += 1
            for s in (skills.get("developing", []) or []):
                developing_skills[s] += 1

    # Best and worst assignment examples
    best = max(student_rows, key=lambda r: _safe_int_score(r.get("score")))
    worst = min(student_rows, key=lambda r: _safe_int_score(r.get("score")))

    cat_labels = {"content": "Content Accuracy", "completeness": "Completeness",
                  "writing": "Writing Quality", "effort": "Effort & Engagement"}

    # Check accommodations
    accommodations = _load_accommodations()
    student_id = student_rows[0].get("student_id", "") if student_rows else ""
    accomm = accommodations.get(student_id)

    feedback = {
        "student_name": matched_name,
        "first_name": first_name,
        "overall_avg": avg,
        "trend": _trend_word(scores),
        "assignments_graded": len(student_rows),
        "strengths": {
            "categories": [cat_labels.get(c, c) for c in strengths_cats],
            "skills": [s for s, _ in sorted(strength_skills.items(), key=lambda x: -x[1])[:4]],
            "best_assignment": {"name": best.get("assignment", ""), "score": _safe_int_score(best.get("score"))},
        },
        "growth_areas": {
            "categories": [cat_labels.get(c, c) for c in growth_cats],
            "skills": [s for s, _ in sorted(developing_skills.items(), key=lambda x: -x[1])[:4]],
            "lowest_assignment": {"name": worst.get("assignment", ""), "score": _safe_int_score(worst.get("score"))},
        },
        "next_steps": [],
    }

    # Generate next steps
    if growth_cats:
        weakest = growth_cats[0]
        feedback["next_steps"].append(f"Focus on improving {cat_labels.get(weakest, weakest).lower()}")
    if developing_skills:
        top_dev = sorted(developing_skills.items(), key=lambda x: -x[1])[0][0]
        feedback["next_steps"].append(f"Practice: {top_dev}")
    if avg < 70:
        feedback["next_steps"].append("Consider tutoring or additional support")
    if accomm:
        feedback["has_accommodations"] = True
        feedback["next_steps"].append("Continue implementing IEP/504 accommodations")

    return feedback


def generate_parent_conference_notes(student_name):
    """Conference agenda with data, talking points, action items."""
    if not student_name:
        return {"error": "student_name is required."}

    # Get student feedback first (reuse logic)
    feedback = draft_student_feedback(student_name)
    if feedback.get("error"):
        return feedback

    settings = _load_settings()
    config = settings.get("config", {})
    teacher_name = config.get("teacher_name", "Teacher")
    subject = config.get("subject", "")
    school = config.get("school_name", "")

    # Load parent contact info
    contacts = {}
    if os.path.exists(PARENT_CONTACTS_FILE):
        try:
            with open(PARENT_CONTACTS_FILE, "r") as f:
                contacts = json.load(f)
        except Exception:
            pass

    # Find parent info
    parent_name = "Parent/Guardian"
    rows = _load_master_csv(period_filter="all")
    student_id = None
    for r in rows:
        if _fuzzy_name_match(student_name, r.get("student_name", "")):
            student_id = r.get("student_id", "")
            break
    if student_id and student_id in contacts:
        parent_name = contacts[student_id].get("primary_contact_name", parent_name)

    # Accommodation info
    accomm_note = ""
    if feedback.get("has_accommodations"):
        accomm_note = "Student has IEP/504 accommodations — discuss implementation effectiveness."

    return {
        "student_name": feedback["student_name"],
        "teacher": teacher_name,
        "subject": subject,
        "school": school,
        "parent_name": parent_name,
        "agenda": {
            "overview": {
                "overall_avg": feedback["overall_avg"],
                "trend": feedback["trend"],
                "assignments_graded": feedback["assignments_graded"],
            },
            "strengths": feedback["strengths"],
            "growth_areas": feedback["growth_areas"],
            "talking_points": [
                f"Overall performance: {feedback['overall_avg']}% average ({feedback['trend']})",
                f"Strongest area: {', '.join(feedback['strengths']['categories'][:2]) or 'N/A'}",
                f"Priority growth area: {', '.join(feedback['growth_areas']['categories'][:2]) or 'N/A'}",
            ],
            "action_items": feedback["next_steps"],
            "accommodation_note": accomm_note,
        },
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

COMMUNICATION_TOOL_HANDLERS = {
    "generate_progress_report": generate_progress_report,
    "generate_report_card_comments": generate_report_card_comments,
    "draft_student_feedback": draft_student_feedback,
    "generate_parent_conference_notes": generate_parent_conference_notes,
}
