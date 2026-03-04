"""
Grading-Related Assistant Tools
================================
Tools for querying, analyzing, and reporting on student grades.
Includes grade queries, student summaries, class analytics,
assignment stats, feedback patterns, period comparisons,
submission folder scanning, and missing assignment detection.
"""
import os
import csv
import json
import re
import statistics
from collections import defaultdict, Counter
from datetime import datetime

from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _load_roster, _load_settings,
    _load_saved_assignments,
    _fuzzy_name_match, _safe_int_score, _normalize_period,
    _normalize_assignment_name, _get_period_assignments,
    ASSIGNMENTS_DIR,
)

# Import storage abstraction
try:
    from backend.storage import load as storage_load, save as storage_save, list_keys as storage_list_keys
except ImportError:
    try:
        from storage import load as storage_load, save as storage_save, list_keys as storage_list_keys
    except ImportError:
        storage_load = None
        storage_save = None
        storage_list_keys = None


# ═══════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════

def _match_assignment_to_config(assign_name, saved_norms, saved_display):
    """Try to match an assignment name to a saved config. Returns the matched
    norm key or None."""
    norm = _normalize_assignment_name(assign_name)
    if norm in saved_norms:
        return norm
    norm_lower = norm.lower()
    for sn in saved_norms:
        sn_lower = sn.lower()
        sd = saved_display.get(sn, sn)
        sd_norm = _normalize_assignment_name(sd).lower()
        if (norm_lower.startswith(sn_lower[:25]) or
                sn_lower.startswith(norm_lower[:25]) or
                norm_lower.startswith(sd_norm[:25]) or
                sd_norm.startswith(norm_lower[:25])):
            return sn
    return None


def _scan_submission_folder(roster_name_map, saved_norms, saved_display):
    """Scan the assignments folder for submitted files. Returns a dict of
    student_id -> set of matched saved config norm keys.
    This catches submissions that haven't been graded yet."""
    import re
    settings = _load_settings()
    folder = settings.get('config', {}).get('assignments_folder', '')
    if not folder or not os.path.isdir(folder):
        return {}

    # Build reverse lookup: lowercase (first, last) -> student_id
    # Handles both "First Last" and "Last, First Middle" roster formats
    name_to_sid = {}
    for sid, full_name in roster_name_map.items():
        if ',' in full_name or ';' in full_name:
            # "Last, First Middle" or "Last; First Middle" format
            sep = ',' if ',' in full_name else ';'
            parts = full_name.split(sep, 1)
            last_part = parts[0].strip().lower()
            after = parts[1].strip().split()
            if after:
                first_part = after[0].lower()
                name_to_sid[(first_part, last_part)] = sid
        else:
            # "First Middle Last" format
            clean = re.sub(r'[.\'"]+', ' ', full_name).split()
            if len(clean) >= 2:
                key = (clean[0].lower(), clean[-1].lower())
                name_to_sid[key] = sid

    result = defaultdict(set)
    supported = {'.docx', '.pdf', '.txt', '.jpg', '.jpeg', '.png'}

    for filename in os.listdir(folder):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported:
            continue

        # Parse filename: FirstName_LastName_AssignmentName.ext
        # Handle stray spaces: "Lillian _Scott_Cornell Notes..."
        base = os.path.splitext(filename)[0]
        parts = base.split('_', 2)
        if len(parts) < 3:
            continue

        first = parts[0].strip().lower()
        last = parts[1].strip().lower()
        assign_part = parts[2].strip()

        if not first or not last or not assign_part:
            continue

        # Match student to roster
        sid = name_to_sid.get((first, last))
        if not sid:
            # Try fuzzy: check all roster entries
            file_name_str = f"{parts[0].strip()} {parts[1].strip()}"
            for roster_sid, roster_name in roster_name_map.items():
                if _fuzzy_name_match(file_name_str, roster_name):
                    sid = roster_sid
                    break
        if not sid:
            continue

        # Match assignment to saved config
        matched_config = _match_assignment_to_config(assign_part, saved_norms, saved_display)
        if matched_config:
            result[sid].add(matched_config)

    return dict(result)


def _build_missing_assignments_data():
    """Shared helper: build per-student submission data from master CSV + roster +
    assignments folder. Returns (student_data, saved_norms, saved_display, error)
    where student_data is dict keyed by student_id with {assigns: set, period: str, name: str}."""
    rows = _load_master_csv()

    saved_assignments = _load_saved_assignments()
    if not saved_assignments:
        return None, None, None, {"error": "No saved assignment configs found in Grading Setup"}

    saved_norms = {a["norm"] for a in saved_assignments}
    saved_display = {a["norm"]: a["title"] for a in saved_assignments}

    # Roster is authoritative for student_id -> period mapping
    roster = _load_roster()
    roster_period_map = {}
    roster_name_map = {}
    for s in roster:
        if s.get("student_id"):
            roster_period_map[s["student_id"]] = _normalize_period(s["period"])
            roster_name_map[s["student_id"]] = s["name"]

    # Build per-student data keyed by student_id
    student_data = defaultdict(lambda: {"assigns": set(), "period": "", "name": ""})

    # Pass 1: graded results from master CSV
    if rows:
        for r in rows:
            sid = r.get("student_id", "")
            name = r["student_name"]
            if not sid or sid == "UNKNOWN":
                continue
            matched = _match_assignment_to_config(r["assignment"], saved_norms, saved_display)
            if matched:
                student_data[sid]["assigns"].add(matched)
            # Set period from roster (authoritative)
            if not student_data[sid]["period"] and sid in roster_period_map:
                student_data[sid]["period"] = roster_period_map[sid]
            # Use longest name available (roster preferred)
            if sid in roster_name_map and len(roster_name_map[sid]) > len(student_data[sid]["name"]):
                student_data[sid]["name"] = roster_name_map[sid]
            elif len(name) > len(student_data[sid]["name"]):
                student_data[sid]["name"] = name

    # Pass 2: ungraded submissions from assignments folder
    folder_submissions = _scan_submission_folder(roster_name_map, saved_norms, saved_display)
    for sid, assigns in folder_submissions.items():
        student_data[sid]["assigns"].update(assigns)
        if not student_data[sid]["period"] and sid in roster_period_map:
            student_data[sid]["period"] = roster_period_map[sid]
        if sid in roster_name_map and len(roster_name_map[sid]) > len(student_data[sid]["name"]):
            student_data[sid]["name"] = roster_name_map[sid]

    # Add roster students with NO data at all
    for sid, period in roster_period_map.items():
        if sid not in student_data:
            student_data[sid]["period"] = period
            student_data[sid]["name"] = roster_name_map.get(sid, "Unknown")

    return dict(student_data), saved_norms, saved_display, None


# ═══════════════════════════════════════════════════════
# TOOL HANDLER FUNCTIONS
# ═══════════════════════════════════════════════════════

def query_grades(student_name=None, assignment=None, period=None,
                 min_score=None, max_score=None, letter_grade=None, limit=25):
    """Search and filter student grades."""
    rows = _load_master_csv(period_filter=period or 'all')
    results_json = _load_results()

    # Build a lookup from results JSON for feedback
    feedback_lookup = {}
    for r in results_json:
        key = (r.get('student_name', ''), r.get('assignment', ''))
        feedback_lookup[key] = r.get('feedback', '')

    filtered = []
    for row in rows:
        if student_name:
            if not _fuzzy_name_match(student_name, row["student_name"]):
                continue
        if assignment:
            if assignment.lower() not in row["assignment"].lower():
                continue
        if min_score is not None and row["score"] < min_score:
            continue
        if max_score is not None and row["score"] > max_score:
            continue
        if letter_grade and row["letter_grade"].upper() != letter_grade.upper():
            continue

        # Get feedback if available (truncated)
        fb = feedback_lookup.get((row["student_name"], row["assignment"]), "")
        if len(fb) > 150:
            fb = fb[:150] + "..."

        filtered.append({
            "student_name": row["student_name"],
            "student_id": row.get("student_id", ""),
            "assignment": row["assignment"],
            "score": row["score"],
            "letter_grade": row["letter_grade"],
            "period": row["quarter"],
            "date": row["date"],
            "feedback_preview": fb
        })

    total = len(filtered)
    filtered = filtered[:limit]

    return {
        "results": filtered,
        "total_matches": total,
        "showing": len(filtered)
    }


def get_student_summary(student_name):
    """Get comprehensive summary for a specific student."""
    rows = _load_master_csv()

    # Find matching student (fuzzy word match — handles compound names)
    student_rows = [r for r in rows if _fuzzy_name_match(student_name, r["student_name"])]

    if not student_rows:
        return {"error": f"No student found matching '{student_name}'"}

    # Get the actual full name and student ID from the first match
    actual_name = student_rows[0]["student_name"]
    actual_id = student_rows[0].get("student_id", "")
    # Re-filter: match by student_id (preferred) or exact name
    # This catches rows with truncated names but the same student_id
    if actual_id and actual_id != "UNKNOWN":
        student_rows = [r for r in rows if r.get("student_id") == actual_id]
        # Use the longest name variant as the display name
        for r in student_rows:
            if len(r["student_name"]) > len(actual_name):
                actual_name = r["student_name"]
    else:
        student_rows = [r for r in rows if r["student_name"] == actual_name]

    sorted_rows = sorted(student_rows, key=lambda x: x["date"])
    scores = [r["score"] for r in student_rows]
    avg = round(sum(scores) / len(scores), 1) if scores else 0

    # Trend calculation
    if len(sorted_rows) >= 2:
        first_half = sorted_rows[:len(sorted_rows) // 2]
        second_half = sorted_rows[len(sorted_rows) // 2:]
        first_avg = sum(r["score"] for r in first_half) / len(first_half)
        second_avg = sum(r["score"] for r in second_half) / len(second_half)
        diff = second_avg - first_avg
        if diff > 3:
            trend = "improving"
        elif diff < -3:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "insufficient data"

    # Category averages
    cat_scores = {"content": [], "completeness": [], "writing": [], "effort": []}
    for r in student_rows:
        cat_scores["content"].append(r["content"])
        cat_scores["completeness"].append(r["completeness"])
        cat_scores["writing"].append(r["writing"])
        cat_scores["effort"].append(r["effort"])

    cat_avgs = {}
    for cat, vals in cat_scores.items():
        cat_avgs[cat] = round(sum(vals) / len(vals), 1) if vals else 0

    # Determine strengths/weaknesses
    sorted_cats = sorted(cat_avgs.items(), key=lambda x: x[1], reverse=True)
    strengths = [c[0] for c in sorted_cats[:2] if c[1] > 0]
    weaknesses = [c[0] for c in sorted_cats[-2:] if c[1] > 0]

    # Grade history
    grade_history = [
        {"assignment": r["assignment"], "score": r["score"],
         "letter_grade": r["letter_grade"], "date": r["date"]}
        for r in sorted_rows
    ]

    # Determine student's period and find missing assignments
    student_period = ""
    for r in student_rows:
        p = _normalize_period(r.get("period", "") or r.get("quarter", ""))
        if p:
            student_period = p
            break

    missing_assignments = []
    all_period_assigns = set()
    if student_period:
        period_assigns, assign_display, merge_map = _get_period_assignments(rows)
        all_period_assigns = period_assigns.get(student_period, set())
        student_has = set(merge_map.get(_normalize_assignment_name(r["assignment"]), _normalize_assignment_name(r["assignment"])) for r in student_rows)
        missing_norms = all_period_assigns - student_has
        missing_assignments = sorted(assign_display.get(n, n) for n in missing_norms)

    return {
        "student_name": actual_name,
        "period": student_period,
        "total_assignments_graded": len(student_rows),
        "total_assignments_in_period": len(all_period_assigns) if student_period else 0,
        "missing_assignments": missing_assignments,
        "missing_count": len(missing_assignments),
        "average_score": avg,
        "trend": trend,
        "highest_score": max(scores) if scores else 0,
        "lowest_score": min(scores) if scores else 0,
        "category_averages": cat_avgs,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "grade_history": grade_history
    }


def get_class_analytics(period=None):
    """Get class-wide analytics."""
    rows = _load_master_csv(period_filter=period or 'all')

    if not rows:
        return {"error": "No grading data available"}

    students = defaultdict(list)
    assignments = defaultdict(list)

    for row in rows:
        students[row["student_name"]].append(row)
        assignments[row["assignment"]].append(row)

    all_scores = [r["score"] for r in rows]
    class_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

    # Get roster count for the requested period (authoritative student count)
    roster = _load_roster()
    if period and period != 'all':
        norm_p = _normalize_period(period)
        roster_for_period = [s for s in roster if _normalize_period(s["period"]) == norm_p]
    else:
        roster_for_period = roster
    roster_student_count = len(roster_for_period) if roster_for_period else None

    # Grade distribution by unique student averages, not raw submissions
    student_avg_scores = []
    for name, grades in students.items():
        s_scores = [g["score"] for g in grades]
        student_avg_scores.append(round(sum(s_scores) / len(s_scores), 1))

    grade_dist = {
        "A": len([s for s in student_avg_scores if s >= 90]),
        "B": len([s for s in student_avg_scores if 80 <= s < 90]),
        "C": len([s for s in student_avg_scores if 70 <= s < 80]),
        "D": len([s for s in student_avg_scores if 60 <= s < 70]),
        "F": len([s for s in student_avg_scores if s < 60])
    }

    # Student averages for ranking
    student_avgs = []
    for name, grades in students.items():
        s_scores = [g["score"] for g in grades]
        avg = round(sum(s_scores) / len(s_scores), 1)
        sorted_grades = sorted(grades, key=lambda x: x["date"])
        if len(sorted_grades) >= 2:
            trend = "improving" if sorted_grades[-1]["score"] > sorted_grades[0]["score"] \
                else "declining" if sorted_grades[-1]["score"] < sorted_grades[0]["score"] \
                else "stable"
        else:
            trend = "stable"
        student_avgs.append({"name": name, "average": avg, "trend": trend,
                             "assignments_count": len(grades)})

    student_avgs.sort(key=lambda x: x["average"], reverse=True)
    top_performers = student_avgs[:5]
    attention_needed = [s for s in student_avgs if s["average"] < 70 or s["trend"] == "declining"]

    # Use roster count when available, fall back to graded student count
    total_students = roster_student_count if roster_student_count else len(students)
    students_not_graded = max(0, total_students - len(students)) if roster_student_count else 0

    return {
        "class_average": class_avg,
        "total_students": total_students,
        "students_with_grades": len(students),
        "students_not_graded": students_not_graded,
        "total_grades": len(rows),
        "grade_distribution": grade_dist,
        "top_performers": top_performers,
        "attention_needed": attention_needed,
        "period": period or "all"
    }


def get_assignment_stats(assignment_name):
    """Get statistics for a specific assignment."""
    rows = _load_master_csv()

    # Partial match on assignment name
    matched = [r for r in rows if assignment_name.lower() in r["assignment"].lower()]

    if not matched:
        return {"error": f"No assignment found matching '{assignment_name}'"}

    # Get exact assignment name from first match
    actual_name = matched[0]["assignment"]
    matched = [r for r in rows if r["assignment"] == actual_name]

    scores = [r["score"] for r in matched]

    grade_dist = {
        "A": len([s for s in scores if s >= 90]),
        "B": len([s for s in scores if 80 <= s < 90]),
        "C": len([s for s in scores if 70 <= s < 80]),
        "D": len([s for s in scores if 60 <= s < 70]),
        "F": len([s for s in scores if s < 60])
    }

    return {
        "assignment_name": actual_name,
        "count": len(scores),
        "mean": round(sum(scores) / len(scores), 1) if scores else 0,
        "median": round(statistics.median(scores), 1) if scores else 0,
        "min": min(scores) if scores else 0,
        "max": max(scores) if scores else 0,
        "std_dev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
        "grade_distribution": grade_dist
    }


def list_assignments_tool():
    """List all graded assignments with counts and averages."""
    rows = _load_master_csv()

    assignments = defaultdict(list)
    for row in rows:
        assignments[row["assignment"]].append(row)

    result = []
    for name, items in sorted(assignments.items()):
        scores = [r["score"] for r in items]
        unique_students = set(r["student_name"] for r in items)
        result.append({
            "assignment": name,
            "student_count": len(unique_students),
            "submission_count": len(scores),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0
        })

    # Also check saved assignment configs
    saved_configs = []
    if os.path.exists(ASSIGNMENTS_DIR):
        for f in os.listdir(ASSIGNMENTS_DIR):
            if f.endswith('.json'):
                saved_configs.append(f.replace('.json', ''))

    return {
        "graded_assignments": result,
        "saved_configs": saved_configs,
        "total_graded": len(result)
    }


def analyze_grade_causes(assignment_name, period=None, score_threshold=None):
    """Deep analysis of what caused grades on an assignment."""
    results = _load_results()

    # Filter by assignment (partial match)
    matched = [r for r in results if assignment_name.lower() in r.get('assignment', '').lower()]
    if not matched:
        return {"error": f"No results found matching '{assignment_name}'"}

    actual_name = matched[0].get('assignment', '')
    matched = [r for r in results if r.get('assignment', '') == actual_name]

    if period:
        matched = [r for r in matched if r.get('period', '') == period]

    if score_threshold is not None:
        matched = [r for r in matched if _safe_int_score(r.get('score')) < score_threshold]

    if not matched:
        return {"error": "No results match the specified filters"}

    total = len(matched)
    scores = [_safe_int_score(r.get('score')) for r in matched]

    # Category breakdown analysis
    cat_totals = defaultdict(list)
    for r in matched:
        bd = r.get('breakdown', {})
        if bd:
            for cat, val in bd.items():
                cat_totals[cat].append(val)

    category_analysis = {}
    for cat, vals in cat_totals.items():
        avg = round(sum(vals) / len(vals), 1) if vals else 0
        zeros = sum(1 for v in vals if v == 0)
        category_analysis[cat] = {
            "average": avg,
            "zeros": zeros,
            "zero_pct": round(zeros / len(vals) * 100, 1) if vals else 0,
            "min": min(vals) if vals else 0,
            "max": max(vals) if vals else 0,
        }

    # Unanswered/omitted questions analysis
    unanswered_counts = defaultdict(int)
    students_with_unanswered = 0
    total_unanswered = 0
    for r in matched:
        uq = r.get('unanswered_questions')
        if uq and isinstance(uq, list) and len(uq) > 0:
            students_with_unanswered += 1
            total_unanswered += len(uq)
            for q in uq:
                unanswered_counts[q] += 1

    # Sort by frequency
    most_skipped = sorted(unanswered_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Score impact of unanswered questions
    scores_with_unanswered = [_safe_int_score(r.get('score')) for r in matched
                              if r.get('unanswered_questions') and len(r.get('unanswered_questions', [])) > 0]
    scores_without_unanswered = [_safe_int_score(r.get('score')) for r in matched
                                 if not r.get('unanswered_questions') or len(r.get('unanswered_questions', [])) == 0]

    unanswered_impact = {}
    if scores_with_unanswered and scores_without_unanswered:
        avg_with = round(sum(scores_with_unanswered) / len(scores_with_unanswered), 1)
        avg_without = round(sum(scores_without_unanswered) / len(scores_without_unanswered), 1)
        unanswered_impact = {
            "students_with_omissions": len(scores_with_unanswered),
            "students_without_omissions": len(scores_without_unanswered),
            "avg_score_with_omissions": avg_with,
            "avg_score_without_omissions": avg_without,
            "score_gap": round(avg_without - avg_with, 1),
            "omission_pct": round(len(scores_with_unanswered) / total * 100, 1),
        }

    # Identify weakest category
    weakest_cat = None
    if category_analysis:
        weakest_cat = min(category_analysis.items(), key=lambda x: x[1]["average"])
        weakest_cat = {"name": weakest_cat[0], **weakest_cat[1]}

    return {
        "assignment_name": actual_name,
        "students_analyzed": total,
        "score_filter": f"below {score_threshold}" if score_threshold else "all students",
        "score_summary": {
            "mean": round(sum(scores) / len(scores), 1) if scores else 0,
            "median": round(statistics.median(scores), 1) if scores else 0,
        },
        "category_breakdown": category_analysis,
        "weakest_category": weakest_cat,
        "unanswered_questions": {
            "students_with_omissions": students_with_unanswered,
            "total_omissions": total_unanswered,
            "avg_omissions_per_student": round(total_unanswered / students_with_unanswered, 1) if students_with_unanswered else 0,
            "most_skipped_questions": [{"question": q, "times_skipped": c,
                                        "pct_students": round(c / total * 100, 1)}
                                       for q, c in most_skipped],
        },
        "omission_score_impact": unanswered_impact,
    }


def get_feedback_patterns(assignment_name, period=None):
    """Analyze feedback patterns across an assignment."""
    results = _load_results()

    matched = [r for r in results if assignment_name.lower() in r.get('assignment', '').lower()]
    if not matched:
        return {"error": f"No results found matching '{assignment_name}'"}

    actual_name = matched[0].get('assignment', '')
    matched = [r for r in results if r.get('assignment', '') == actual_name]

    if period:
        matched = [r for r in matched if r.get('period', '') == period]

    if not matched:
        return {"error": "No results match the specified filters"}

    # Aggregate strengths and developing skills
    all_strengths = []
    all_developing = []
    for r in matched:
        skills = r.get('skills_demonstrated', {})
        if isinstance(skills, dict):
            s = skills.get('strengths', [])
            d = skills.get('developing', [])
            if isinstance(s, list):
                all_strengths.extend(s)
            if isinstance(d, list):
                all_developing.extend(d)

    # Count frequency of skill mentions
    strength_freq = defaultdict(int)
    for s in all_strengths:
        strength_freq[s.strip()] += 1

    developing_freq = defaultdict(int)
    for d in all_developing:
        developing_freq[d.strip()] += 1

    top_strengths = sorted(strength_freq.items(), key=lambda x: x[1], reverse=True)[:8]
    top_developing = sorted(developing_freq.items(), key=lambda x: x[1], reverse=True)[:8]

    # Feedback content sampling (common phrases from low and high scorers)
    low_scorers = sorted(matched, key=lambda r: _safe_int_score(r.get('score')))[:5]
    high_scorers = sorted(matched, key=lambda r: _safe_int_score(r.get('score')), reverse=True)[:5]

    low_feedback_samples = []
    for r in low_scorers:
        fb = r.get('feedback', '')
        if fb:
            low_feedback_samples.append({
                "student": r.get('student_name', '').split()[0] if r.get('student_name') else 'Unknown',
                "score": _safe_int_score(r.get('score')),
                "feedback_preview": fb[:250] + "..." if len(fb) > 250 else fb,
                "unanswered_count": len(r.get('unanswered_questions', []) or []),
            })

    high_feedback_samples = []
    for r in high_scorers:
        fb = r.get('feedback', '')
        if fb:
            high_feedback_samples.append({
                "student": r.get('student_name', '').split()[0] if r.get('student_name') else 'Unknown',
                "score": _safe_int_score(r.get('score')),
                "feedback_preview": fb[:250] + "..." if len(fb) > 250 else fb,
            })

    # Marker status distribution
    marker_dist = defaultdict(int)
    for r in matched:
        marker_dist[r.get('marker_status', 'unknown')] += 1

    return {
        "assignment_name": actual_name,
        "total_students": len(matched),
        "common_strengths": [{"skill": s, "count": c, "pct": round(c / len(matched) * 100, 1)}
                             for s, c in top_strengths],
        "common_areas_for_growth": [{"skill": d, "count": c, "pct": round(c / len(matched) * 100, 1)}
                                     for d, c in top_developing],
        "lowest_scoring_feedback": low_feedback_samples,
        "highest_scoring_feedback": high_feedback_samples,
        "marker_status": dict(marker_dist),
    }


def compare_periods(assignment_name=None):
    """Compare performance across class periods."""
    results = _load_results()

    if assignment_name:
        results = [r for r in results if assignment_name.lower() in r.get('assignment', '').lower()]
        if results:
            actual_name = results[0].get('assignment', '')
            results = [r for r in results if r.get('assignment', '') == actual_name]
        else:
            return {"error": f"No results found matching '{assignment_name}'"}

    if not results:
        return {"error": "No grading results available"}

    # Load roster for authoritative student counts per period
    roster = _load_roster()
    roster_by_period = defaultdict(list)
    for s in roster:
        roster_by_period[_normalize_period(s["period"])].append(s)

    # Group by period
    by_period = defaultdict(list)
    for r in results:
        p = r.get('period', 'Unknown')
        by_period[p].append(r)

    period_data = []
    for p, items in sorted(by_period.items()):
        scores = [_safe_int_score(r.get('score')) for r in items]

        # Count unique graded students and compute grade dist from per-student averages
        period_students = defaultdict(list)
        for r in items:
            sname = r.get('student_name', r.get('name', 'Unknown'))
            period_students[sname].append(_safe_int_score(r.get('score')))

        student_avg_scores = []
        for sname, s_scores in period_students.items():
            student_avg_scores.append(round(sum(s_scores) / len(s_scores), 1))

        grade_dist = {
            "A": len([s for s in student_avg_scores if s >= 90]),
            "B": len([s for s in student_avg_scores if 80 <= s < 90]),
            "C": len([s for s in student_avg_scores if 70 <= s < 80]),
            "D": len([s for s in student_avg_scores if 60 <= s < 70]),
            "F": len([s for s in student_avg_scores if s < 60])
        }

        # Category averages
        cat_totals = defaultdict(list)
        for r in items:
            bd = r.get('breakdown', {})
            if bd:
                for cat, val in bd.items():
                    cat_totals[cat].append(val)

        cat_avgs = {}
        for cat, vals in cat_totals.items():
            cat_avgs[cat] = round(sum(vals) / len(vals), 1) if vals else 0

        # Unanswered rate
        with_omissions = sum(1 for r in items
                             if r.get('unanswered_questions') and len(r.get('unanswered_questions', [])) > 0)

        # Use roster count (authoritative) if available, else graded count
        roster_match = roster_by_period.get(_normalize_period(p), [])
        total_students = len(roster_match) if roster_match else len(period_students)

        period_data.append({
            "period": p,
            "student_count": total_students,
            "students_with_grades": len(period_students),
            "submission_count": len(items),
            "average": round(sum(scores) / len(scores), 1) if scores else 0,
            "median": round(statistics.median(scores), 1) if scores else 0,
            "grade_distribution": grade_dist,
            "category_averages": cat_avgs,
            "omission_rate": round(with_omissions / len(items) * 100, 1) if items else 0,
        })

    # Rank periods
    period_data.sort(key=lambda x: x["average"], reverse=True)

    return {
        "assignment": assignment_name or "all assignments",
        "periods": period_data,
        "best_period": period_data[0]["period"] if period_data else None,
        "lowest_period": period_data[-1]["period"] if period_data else None,
    }


def scan_submissions_folder(top_n=None, assignment_filter=None):
    """Scan the assignments folder for submitted files. Shows top assignments
    by submission count, unique students, graded/ungraded status.
    Deduplicates multiple uploads per student (OneDrive duplicates)."""
    import re

    # Read from ~/.graider_settings.json (where the UI saves config)
    folder = ''
    settings_path = os.path.expanduser("~/.graider_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            folder = settings_data.get('config', {}).get('assignments_folder', '')
        except Exception:
            pass
    if not folder:
        # Fallback: try _load_settings() (global settings) then default
        gs = _load_settings()
        folder = gs.get('config', {}).get('assignments_folder', '')
    if not folder:
        folder = os.path.expanduser("~/Downloads/Graider/Assignments")
    if not os.path.isdir(folder):
        return {"error": f"Assignments folder not found: {folder}. Configure it in Settings > General."}

    top_n = min(max(int(top_n or 10), 1), 25)
    supported = {'.docx', '.pdf', '.txt', '.jpg', '.jpeg', '.png'}

    # Phase 1: Scan all files and parse filenames
    raw_files = []  # list of (filename, first, last, assign_part, mtime)
    unparseable = []

    for filename in os.listdir(folder):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported:
            continue

        filepath = os.path.join(folder, filename)
        if not os.path.isfile(filepath):
            continue

        base = os.path.splitext(filename)[0]
        parts = base.split('_', 2)
        if len(parts) < 3 or not parts[0].strip() or not parts[1].strip() or not parts[2].strip():
            unparseable.append(filename)
            continue

        first = parts[0].strip()
        last = parts[1].strip()
        assign_part = parts[2].strip()

        try:
            mtime = os.stat(filepath).st_mtime
        except OSError:
            mtime = 0

        raw_files.append((filename, first, last, assign_part, mtime))

    total_files = len(raw_files) + len(unparseable)

    # Phase 2: Deduplicate — strip OneDrive suffixes, keep newest per (student, assignment)
    deduped = {}  # (student_key, assignment_norm) -> (filename, first, last, assign_part, mtime)

    for filename, first, last, assign_part, mtime in raw_files:
        student_key = f"{first.lower()}_{last.lower()}"

        # Strip OneDrive duplicate suffixes from assignment part
        clean_assign = assign_part
        clean_assign = re.sub(r'\s*\(\d+\)\s*$', '', clean_assign)        # "Notes (1)" -> "Notes"
        clean_assign = re.sub(r'\s+\d{1,2}\s*$', '', clean_assign)        # "Notes 1" -> "Notes"
        clean_assign = re.sub(r'\s*-\s*[Cc]opy\s*(\d*)\s*$', '', clean_assign)  # "Notes - Copy" -> "Notes"

        assignment_norm = _normalize_assignment_name(clean_assign)

        key = (student_key, assignment_norm)
        existing = deduped.get(key)
        if existing is None or mtime > existing[4]:
            deduped[key] = (filename, first, last, assign_part, mtime)

    duplicates_removed = len(raw_files) - len(deduped)

    # Phase 3: Group deduplicated files by assignment
    assignment_groups = defaultdict(list)  # assignment_norm -> [(student_display, filename)]
    for (student_key, assignment_norm), (filename, first, last, assign_part, mtime) in deduped.items():
        student_display = f"{first} {last[0].upper()}." if last else first
        assignment_groups[assignment_norm].append((student_display, filename))

    # Phase 4: Cross-reference with graded results
    results = _load_results()
    graded_keys = set()
    for r in results:
        fname = r.get('filename', r.get('file', ''))
        if fname:
            graded_keys.add(fname.lower())

    # Phase 5: Filter by assignment name if requested
    if assignment_filter:
        filter_norm = _normalize_assignment_name(assignment_filter)
        assignment_groups = {
            k: v for k, v in assignment_groups.items()
            if filter_norm in k
        }

    # Phase 6: Build output sorted by submission count
    # Find display name: use most common raw assignment part for each group
    all_students = set()
    top_assignments = []
    for assignment_norm, entries in sorted(assignment_groups.items(), key=lambda x: len(x[1]), reverse=True)[:top_n]:
        graded = sum(1 for _, fn in entries if fn.lower() in graded_keys)
        students = sorted(set(s for s, _ in entries))
        all_students.update(students)

        # Pick most common raw assignment part for display name
        raw_parts = []
        for (sk, an), (fn, first, last, ap, mt) in deduped.items():
            if an == assignment_norm:
                raw_parts.append(ap)
        if raw_parts:
            from collections import Counter
            display_name = Counter(raw_parts).most_common(1)[0][0]
            # Clean up display name
            display_name = re.sub(r'\s*\(\d+\)\s*$', '', display_name)
            display_name = re.sub(r'\s+\d{1,2}\s*$', '', display_name)
            display_name = re.sub(r'\s*-\s*[Cc]opy\s*(\d*)\s*$', '', display_name)
        else:
            display_name = assignment_norm

        entry = {
            "assignment": display_name,
            "submissions": len(entries),
            "graded": graded,
            "ungraded": len(entries) - graded,
            "student_count": len(students),
        }
        # Only include full student list when filtering to a specific assignment
        # to keep the summary response compact
        if assignment_filter:
            entry["students"] = students
        top_assignments.append(entry)

    # Count unique students across all groups (not just top N)
    all_unique_students = set()
    for entries in assignment_groups.values():
        for s, _ in entries:
            all_unique_students.add(s)

    return {
        "folder": folder,
        "total_files": total_files,
        "duplicates_removed": duplicates_removed,
        "unique_students": len(all_unique_students),
        "unique_assignments": len(assignment_groups),
        "top_assignments": top_assignments,
        "unparseable_files": unparseable[:20]  # Cap at 20 to avoid huge output
    }


def get_missing_assignments(student_name=None, period=None, assignment_name=None):
    """Find missing/unsubmitted assignments.

    Compares student submissions against saved assignment configs
    (the assignments the teacher set up to grade), NOT against what
    other students submitted.

    Four modes:
    1. student_name -> list saved assignments this student hasn't submitted
    2. period -> list all students in that period with missing work
    3. period="all" -> summary of ALL periods (zero-submission students highlighted)
    4. assignment_name -> list students who are missing that specific assignment

    If no params provided, defaults to period="all" (all-periods summary).
    """
    student_data, saved_norms, saved_display, err = _build_missing_assignments_data()
    if err:
        return err

    # Mode 1: Specific student
    if student_name:
        matches = [(sid, d) for sid, d in student_data.items() if _fuzzy_name_match(student_name, d["name"])]
        if not matches:
            return {"error": f"No student found matching '{student_name}'"}
        sid, data = matches[0]
        submitted_saved = data["assigns"] & saved_norms
        missing = saved_norms - data["assigns"]
        return {
            "student_name": data["name"],
            "period": data["period"],
            "submitted_count": len(submitted_saved),
            "total_assignments": len(saved_norms),
            "missing_count": len(missing),
            "submitted": sorted(saved_display.get(n, n) for n in submitted_saved),
            "missing": sorted(saved_display.get(n, n) for n in missing),
        }

    # Mode 2: By period — students missing work in ONE period (compact response)
    if period and _normalize_period(period) != "all":
        period_norm = _normalize_period(period)
        students_missing = []
        for sid, data in student_data.items():
            if data["period"] != period_norm:
                continue
            missing = saved_norms - data["assigns"]
            submitted_saved = data["assigns"] & saved_norms
            if missing:
                students_missing.append({
                    "student_name": data["name"],
                    "missing_count": len(missing),
                    "submitted_count": len(submitted_saved),
                })
        students_missing.sort(key=lambda x: -x["missing_count"])

        return {
            "period": period_norm,
            "total_assignments": len(saved_norms),
            "students_with_missing": len(students_missing),
            "students": students_missing[:25],
        }

    # Mode 3: All periods — summary across all periods (default when no params)
    if not assignment_name:
        period_summaries = defaultdict(lambda: {"total": 0, "zero_submissions": [], "some_missing": 0})
        for sid, data in student_data.items():
            p = data["period"]
            if not p:
                continue
            period_summaries[p]["total"] += 1
            submitted_saved = data["assigns"] & saved_norms
            missing = saved_norms - data["assigns"]
            if len(submitted_saved) == 0 and len(missing) > 0:
                period_summaries[p]["zero_submissions"].append(data["name"])
            elif len(missing) > 0:
                period_summaries[p]["some_missing"] += 1

        result_periods = []
        all_zero = []
        for p in sorted(period_summaries.keys()):
            info = period_summaries[p]
            result_periods.append({
                "period": p,
                "total_students": info["total"],
                "zero_submissions": len(info["zero_submissions"]),
                "some_missing": info["some_missing"],
                "all_complete": info["total"] - len(info["zero_submissions"]) - info["some_missing"],
            })
            for name in info["zero_submissions"]:
                all_zero.append({"student_name": name, "period": p})

        return {
            "total_assignments": len(saved_norms),
            "period_summary": result_periods,
            "zero_submission_students": all_zero,
            "zero_submission_count": len(all_zero),
        }

    # Mode 4: By assignment — which students are missing it
    target_norm = None
    for sa in _load_saved_assignments():
        if assignment_name.lower() in sa["title"].lower() or assignment_name.lower() in sa["norm"].lower():
            target_norm = sa["norm"]
            break
    if not target_norm:
        return {"error": f"No saved assignment found matching '{assignment_name}'"}

    display_name = saved_display.get(target_norm, assignment_name)
    missing_students = []
    submitted_count = 0
    for sid, data in student_data.items():
        if not data["period"]:
            continue
        if target_norm in data["assigns"]:
            submitted_count += 1
        else:
            missing_students.append({"student_name": data["name"], "period": data["period"]})

    missing_students.sort(key=lambda x: (x["period"], x["student_name"]))
    return {
        "assignment": display_name,
        "submitted_count": submitted_count,
        "missing_count": len(missing_students),
        "missing_students": missing_students,
    }


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

GRADING_TOOL_DEFINITIONS = [
    {
        "name": "query_grades",
        "description": "Search and filter student grades. Use this when the teacher asks about specific students, assignments, score ranges, or periods.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to search for (partial match, case-insensitive)"
                },
                "assignment": {
                    "type": "string",
                    "description": "Assignment name to filter by (partial match)"
                },
                "period": {
                    "type": "string",
                    "description": "Grading period/quarter to filter by"
                },
                "min_score": {
                    "type": "number",
                    "description": "Minimum score threshold"
                },
                "max_score": {
                    "type": "number",
                    "description": "Maximum score threshold"
                },
                "letter_grade": {
                    "type": "string",
                    "description": "Letter grade to filter by (A, B, C, D, F)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 25)"
                }
            }
        }
    },
    {
        "name": "get_student_summary",
        "description": "Get a comprehensive summary of a specific student's performance including all grades, average, trend, category breakdowns, and strengths/weaknesses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to look up (partial match)"
                }
            },
            "required": ["student_name"]
        }
    },
    {
        "name": "get_class_analytics",
        "description": "Get class-wide analytics including average, grade distribution, top/bottom performers, and students needing attention. Optionally filter by period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Grading period/quarter to filter by (omit for all periods)"
                }
            }
        }
    },
    {
        "name": "get_assignment_stats",
        "description": "Get statistics for a specific assignment including count, mean, median, min, max, standard deviation, and grade distribution.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment name to look up (partial match)"
                }
            },
            "required": ["assignment_name"]
        }
    },
    {
        "name": "list_assignments",
        "description": "List all graded assignments with their student count and average score.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "scan_submissions_folder",
        "description": "Scan the assignments folder to see what files students have submitted. Shows top assignments by submission count, unique students, graded/ungraded counts. Deduplicates multiple uploads per student. Use for 'what's been turned in?', 'most submitted assignments?', or to preview before grading.",
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "Top N assignments to return (default 10, max 25)"
                },
                "assignment_filter": {
                    "type": "string",
                    "description": "Filter to assignments matching this name (partial, case-insensitive)"
                }
            }
        }
    },
    {
        "name": "analyze_grade_causes",
        "description": "Deep analysis of WHY students got the grades they did on an assignment. Shows rubric category breakdown averages, most commonly missed/unanswered questions, score distribution by category, and identifies which sections or skills caused the most point loss. Use this when the teacher asks about causes of low grades, common mistakes, or what students struggled with.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment name (partial match)"
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period (optional)"
                },
                "score_threshold": {
                    "type": "number",
                    "description": "Only analyze students below this score (optional, e.g. 70 for failing students)"
                }
            },
            "required": ["assignment_name"]
        }
    },
    {
        "name": "get_feedback_patterns",
        "description": "Analyze feedback text across an assignment to find common themes, recurring issues, and patterns in what students did well or poorly. Extracts strengths and developing skills aggregated across all students. Use when teacher asks about common mistakes, patterns, or what feedback was given.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment name (partial match)"
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period (optional)"
                }
            },
            "required": ["assignment_name"]
        }
    },
    {
        "name": "compare_periods",
        "description": "Compare performance across class periods for a specific assignment or overall. Shows average scores, grade distributions, and category breakdowns per period. Use when teacher asks how different classes compared or which period did best/worst.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment name to compare across periods (optional, omit for overall)"
                }
            }
        }
    },
    {
        "name": "get_missing_assignments",
        "description": "Find missing/unsubmitted assignments. Four modes: (1) by student_name \u2014 which assignments are they missing? (2) by period \u2014 who in that period has missing work? (3) NO params or period='all' \u2014 compact summary of ALL periods with zero-submission students. Use this when asked 'who hasn't submitted anything' across all classes. (4) by assignment_name \u2014 who hasn't turned in X? IMPORTANT: For 'students with no submissions' across all periods, call with NO parameters \u2014 do NOT call once per period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to check missing work for (fuzzy match)"
                },
                "period": {
                    "type": "string",
                    "description": "Period to check (e.g., 'Period 2', '2'). Use 'all' or omit for all-periods summary."
                },
                "assignment_name": {
                    "type": "string",
                    "description": "Assignment name to check (partial match). Shows which students haven't submitted it."
                }
            }
        }
    },
]


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

GRADING_TOOL_HANDLERS = {
    "query_grades": query_grades,
    "get_student_summary": get_student_summary,
    "get_class_analytics": get_class_analytics,
    "get_assignment_stats": get_assignment_stats,
    "list_assignments": list_assignments_tool,
    "scan_submissions_folder": scan_submissions_folder,
    "analyze_grade_causes": analyze_grade_causes,
    "get_feedback_patterns": get_feedback_patterns,
    "compare_periods": compare_periods,
    "get_missing_assignments": get_missing_assignments,
}
