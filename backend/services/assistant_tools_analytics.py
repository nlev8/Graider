"""
Analytics Tools
===============
Advanced analytics tools for grade trends, risk flags, rubric weakness, and assignment comparison.
Zero AI API calls — all data from local files.
"""
import statistics
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _normalize_period,
    _fuzzy_name_match, _safe_int_score, _normalize_assignment_name,
    _load_accommodations,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

ANALYTICS_TOOL_DEFINITIONS = [
    {
        "name": "get_grade_trends",
        "description": "Track scores over time for a student or entire class. Shows direction (improving/declining/stable) with per-assignment data points. Compact output to minimize tokens.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name for individual trend (omit for class-wide)"
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period"
                },
                "num_assignments": {
                    "type": "integer",
                    "description": "Max recent assignments to include (default 10)"
                }
            }
        }
    },
    {
        "name": "get_rubric_weakness",
        "description": "Find the consistently weakest rubric categories across ALL assignments. Aggregates content, completeness, writing, effort scores to identify systemic gaps. Use when teacher asks 'what do my students struggle with most?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Filter by period (omit for all)"
                }
            }
        }
    },
    {
        "name": "flag_at_risk_students",
        "description": "Combine declining trends, missing work, and low rubric categories into a risk score. Returns students sorted by risk level. Use when teacher asks 'who should I be worried about?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Filter by period (omit for all)"
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum risk score to include (0-100, default 30)"
                }
            }
        }
    },
    {
        "name": "compare_assignments",
        "description": "Side-by-side comparison of two assignments — mean, median, grade distribution, category averages. Use when teacher asks 'how did they do on X vs Y?'",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment_a": {
                    "type": "string",
                    "description": "First assignment name (partial match)"
                },
                "assignment_b": {
                    "type": "string",
                    "description": "Second assignment name (partial match)"
                }
            },
            "required": ["assignment_a", "assignment_b"]
        }
    },
    {
        "name": "get_grade_distribution",
        "description": "Histogram-ready A/B/C/D/F counts and percentages per assignment or period. Use when teacher needs grade distribution for admin reports, report cards, or data meetings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment": {
                    "type": "string",
                    "description": "Assignment name to filter (partial match). Omit for all assignments combined."
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period. Omit for all periods."
                },
                "group_by": {
                    "type": "string",
                    "enum": ["assignment", "period", "none"],
                    "description": "Group results by assignment, period, or combined (default 'none')"
                }
            }
        }
    },
    {
        "name": "detect_score_outliers",
        "description": "Flag scores more than 2 standard deviations from class mean — possible mis-grades, cheating, or data entry errors. Use before publishing grades or when teacher asks about suspicious scores.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assignment": {
                    "type": "string",
                    "description": "Assignment name (partial match). Omit to scan all assignments."
                },
                "period": {
                    "type": "string",
                    "description": "Filter by period. Omit for all periods."
                },
                "threshold": {
                    "type": "number",
                    "description": "Number of standard deviations for outlier cutoff (default 2.0)"
                }
            }
        }
    },
]


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _compute_trend_direction(scores):
    """Given a list of scores in chronological order, return 'improving', 'declining', or 'stable'."""
    if len(scores) < 2:
        return "insufficient_data"
    first_half = scores[:len(scores) // 2] or scores[:1]
    second_half = scores[len(scores) // 2:] or scores[-1:]
    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    diff = second_avg - first_avg
    if diff >= 3:
        return "improving"
    elif diff <= -3:
        return "declining"
    return "stable"


def _assignment_stats(rows):
    """Compute compact stats for a set of grade rows."""
    scores = [_safe_int_score(r.get("score")) for r in rows]
    if not scores:
        return None
    cats = {}
    for cat in ("content", "completeness", "writing", "effort"):
        vals = [_safe_int_score(r.get(cat)) for r in rows if r.get(cat)]
        if vals:
            cats[cat] = round(sum(vals) / len(vals), 1)
    dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for s in scores:
        if s >= 90:
            dist["A"] += 1
        elif s >= 80:
            dist["B"] += 1
        elif s >= 70:
            dist["C"] += 1
        elif s >= 60:
            dist["D"] += 1
        else:
            dist["F"] += 1
    return {
        "count": len(scores),
        "mean": round(sum(scores) / len(scores), 1),
        "median": round(statistics.median(scores), 1),
        "min": min(scores),
        "max": max(scores),
        "stdev": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
        "distribution": dist,
        "categories": cats,
    }


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

def get_grade_trends(student_name=None, period=None, num_assignments=None):
    """Track scores over time with direction indicators."""
    num_assignments = num_assignments or 10
    rows = _load_master_csv(period_filter=period or 'all')
    if not rows:
        return {"error": "No grade data found."}

    # Group by student, sort by date
    student_data = defaultdict(list)
    for r in rows:
        student_data[r.get("student_name", "unknown")].append(r)

    # If specific student requested, filter
    if student_name:
        matched = {}
        for name, entries in student_data.items():
            if _fuzzy_name_match(student_name, name):
                matched[name] = entries
                break
        if not matched:
            return {"error": f"No grades found for '{student_name}'."}
        student_data = matched

    # Get unique assignments sorted by earliest date
    all_assigns = {}
    for entries in student_data.values():
        for r in entries:
            a = r.get("assignment", "")
            d = r.get("date", "")
            if a and (a not in all_assigns or d < all_assigns[a]):
                all_assigns[a] = d
    sorted_assigns = sorted(all_assigns.keys(), key=lambda a: all_assigns[a])
    recent_assigns = sorted_assigns[-num_assignments:]

    trends = []
    for name, entries in sorted(student_data.items()):
        entries.sort(key=lambda r: r.get("date", ""))
        # Filter to recent assignments
        recent = [r for r in entries if r.get("assignment") in recent_assigns]
        if not recent:
            continue
        scores = [_safe_int_score(r.get("score")) for r in recent]
        direction = _compute_trend_direction(scores)
        avg = round(sum(scores) / len(scores), 1)

        # Compact: just assignment name + score pairs
        points = [{"a": r.get("assignment", "")[:40], "s": _safe_int_score(r.get("score"))}
                  for r in recent]

        trends.append({
            "student": name,
            "avg": avg,
            "direction": direction,
            "points": points,
        })

    # Sort: declining first, then by average ascending
    order = {"declining": 0, "improving": 2, "stable": 1, "insufficient_data": 3}
    trends.sort(key=lambda t: (order.get(t["direction"], 3), t["avg"]))

    return {
        "student_count": len(trends),
        "assignments_tracked": len(recent_assigns),
        "trends": trends[:30],  # Cap output for token efficiency
    }


def get_rubric_weakness(period=None):
    """Aggregate rubric categories across ALL assignments to find systemic weaknesses."""
    rows = _load_master_csv(period_filter=period or 'all')
    if not rows:
        return {"error": "No grade data found."}

    cat_labels = {
        "content": "Content Accuracy",
        "completeness": "Completeness",
        "writing": "Writing Quality",
        "effort": "Effort & Engagement",
    }

    # Aggregate per category across all assignments
    cat_totals = defaultdict(list)
    per_assign_cats = defaultdict(lambda: defaultdict(list))

    for r in rows:
        assign = r.get("assignment", "")
        for cat in cat_labels:
            val = _safe_int_score(r.get(cat))
            if val > 0:
                cat_totals[cat].append(val)
                per_assign_cats[assign][cat].append(val)

    if not cat_totals:
        return {"error": "No rubric category data found."}

    # Overall category averages
    cat_avgs = {}
    for cat, vals in cat_totals.items():
        cat_avgs[cat] = round(sum(vals) / len(vals), 1)

    sorted_cats = sorted(cat_avgs.items(), key=lambda x: x[1])
    weakest = sorted_cats[0]
    strongest = sorted_cats[-1]

    # Per-assignment breakdown for weakest category
    weakest_by_assign = []
    for assign, cats in per_assign_cats.items():
        vals = cats.get(weakest[0], [])
        if vals:
            weakest_by_assign.append({
                "assignment": assign[:40],
                "avg": round(sum(vals) / len(vals), 1),
                "count": len(vals),
            })
    weakest_by_assign.sort(key=lambda x: x["avg"])

    return {
        "category_averages": {cat_labels.get(c, c): v for c, v in sorted_cats},
        "weakest": {"category": cat_labels.get(weakest[0], weakest[0]), "avg": weakest[1]},
        "strongest": {"category": cat_labels.get(strongest[0], strongest[0]), "avg": strongest[1]},
        "gap": round(strongest[1] - weakest[1], 1),
        "weakest_by_assignment": weakest_by_assign[:5],
        "total_data_points": sum(len(v) for v in cat_totals.values()),
    }


def flag_at_risk_students(period=None, threshold=None):
    """Combine signals to produce risk scores: declining trend + low scores + missing work."""
    threshold = threshold if threshold is not None else 30
    rows = _load_master_csv(period_filter=period or 'all')
    if not rows:
        return {"error": "No grade data found."}

    # Group by student
    student_data = defaultdict(list)
    for r in rows:
        student_data[r.get("student_name", "unknown")].append(r)

    # Count total unique assignments
    all_assigns = set(r.get("assignment", "") for r in rows if r.get("assignment"))

    risk_list = []
    for name, entries in student_data.items():
        entries.sort(key=lambda r: r.get("date", ""))
        scores = [_safe_int_score(r.get("score")) for r in entries]
        if not scores:
            continue

        avg = round(sum(scores) / len(scores), 1)
        direction = _compute_trend_direction(scores)

        # Risk signals
        risk_score = 0

        # Signal 1: Low average (0-40 points)
        if avg < 60:
            risk_score += 40
        elif avg < 70:
            risk_score += 25
        elif avg < 75:
            risk_score += 10

        # Signal 2: Declining trend (0-25 points)
        if direction == "declining":
            risk_score += 25
        elif direction == "stable" and avg < 70:
            risk_score += 10

        # Signal 3: Missing assignments (0-20 points)
        student_assigns = set(r.get("assignment", "") for r in entries)
        missing = len(all_assigns - student_assigns)
        if missing > 0:
            missing_pct = missing / max(len(all_assigns), 1) * 100
            if missing_pct > 50:
                risk_score += 20
            elif missing_pct > 25:
                risk_score += 10

        # Signal 4: Weak rubric categories (0-15 points)
        cat_avgs = {}
        for cat in ("content", "completeness", "writing", "effort"):
            vals = [_safe_int_score(r.get(cat)) for r in entries if r.get(cat)]
            if vals:
                cat_avgs[cat] = round(sum(vals) / len(vals), 1)
        weak_cats = [c for c, v in cat_avgs.items() if v < 65]
        if len(weak_cats) >= 3:
            risk_score += 15
        elif len(weak_cats) >= 2:
            risk_score += 10
        elif len(weak_cats) >= 1:
            risk_score += 5

        if risk_score >= threshold:
            risk_flags = []
            if direction == "declining":
                risk_flags.append("declining")
            if avg < 70:
                risk_flags.append(f"avg {avg}%")
            if missing > 0:
                risk_flags.append(f"{missing} missing")
            if weak_cats:
                risk_flags.append(f"weak: {', '.join(weak_cats)}")

            risk_list.append({
                "student": name,
                "risk_score": min(risk_score, 100),
                "avg": avg,
                "direction": direction,
                "assignments_completed": len(student_assigns),
                "assignments_missing": missing,
                "flags": risk_flags,
            })

    risk_list.sort(key=lambda x: -x["risk_score"])

    return {
        "at_risk_count": len(risk_list),
        "total_students": len(student_data),
        "total_assignments": len(all_assigns),
        "threshold": threshold,
        "students": risk_list[:20],  # Cap for token efficiency
    }


def compare_assignments(assignment_a, assignment_b):
    """Side-by-side stats for two assignments."""
    if not assignment_a or not assignment_b:
        return {"error": "Both assignment_a and assignment_b are required."}

    rows = _load_master_csv(period_filter='all')
    if not rows:
        return {"error": "No grade data found."}

    norm_a = _normalize_assignment_name(assignment_a).lower()
    norm_b = _normalize_assignment_name(assignment_b).lower()

    rows_a = [r for r in rows if norm_a in _normalize_assignment_name(r.get("assignment", "")).lower()]
    rows_b = [r for r in rows if norm_b in _normalize_assignment_name(r.get("assignment", "")).lower()]

    if not rows_a:
        return {"error": f"No grades found for '{assignment_a}'."}
    if not rows_b:
        return {"error": f"No grades found for '{assignment_b}'."}

    stats_a = _assignment_stats(rows_a)
    stats_b = _assignment_stats(rows_b)

    # Per-student comparison for students who completed both
    students_a = {r.get("student_name"): _safe_int_score(r.get("score")) for r in rows_a}
    students_b = {r.get("student_name"): _safe_int_score(r.get("score")) for r in rows_b}
    common = set(students_a.keys()) & set(students_b.keys())
    improved = 0
    declined = 0
    for s in common:
        diff = students_b[s] - students_a[s]
        if diff > 0:
            improved += 1
        elif diff < 0:
            declined += 1

    # Find the display names
    name_a = rows_a[0].get("assignment", assignment_a)
    name_b = rows_b[0].get("assignment", assignment_b)

    return {
        "assignment_a": {"name": name_a, **stats_a},
        "assignment_b": {"name": name_b, **stats_b},
        "comparison": {
            "mean_diff": round(stats_b["mean"] - stats_a["mean"], 1),
            "students_in_both": len(common),
            "improved": improved,
            "declined": declined,
            "same": len(common) - improved - declined,
        }
    }


def get_grade_distribution(assignment=None, period=None, group_by=None):
    """Histogram-ready A/B/C/D/F counts and percentages."""
    group_by = group_by or "none"
    rows = _load_master_csv(period_filter=period or "all")
    if not rows:
        return {"error": "No grade data found."}

    if assignment:
        norm = _normalize_assignment_name(assignment).lower()
        rows = [r for r in rows if norm in _normalize_assignment_name(r.get("assignment", "")).lower()]
        if not rows:
            return {"error": f"No grades found for '{assignment}'."}

    def _dist(score_list):
        """Build distribution from a list of scores."""
        total = len(score_list)
        if total == 0:
            return None
        buckets = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for s in score_list:
            if s >= 90:
                buckets["A"] += 1
            elif s >= 80:
                buckets["B"] += 1
            elif s >= 70:
                buckets["C"] += 1
            elif s >= 60:
                buckets["D"] += 1
            else:
                buckets["F"] += 1
        pcts = {g: round(c / total * 100, 1) for g, c in buckets.items()}
        avg = round(sum(score_list) / total, 1)
        pass_rate = round((buckets["A"] + buckets["B"] + buckets["C"]) / total * 100, 1)
        return {
            "count": total,
            "mean": avg,
            "pass_rate": pass_rate,
            "counts": buckets,
            "percentages": pcts,
        }

    if group_by == "assignment":
        groups = defaultdict(list)
        for r in rows:
            groups[r.get("assignment", "unknown")].append(_safe_int_score(r.get("score")))
        results = []
        for name, scores in sorted(groups.items()):
            d = _dist(scores)
            if d:
                results.append({"assignment": name, **d})
        return {"group_by": "assignment", "distributions": results}

    if group_by == "period":
        groups = defaultdict(list)
        for r in rows:
            groups[r.get("period", "unknown")].append(_safe_int_score(r.get("score")))
        results = []
        for name, scores in sorted(groups.items()):
            d = _dist(scores)
            if d:
                results.append({"period": name, **d})
        return {"group_by": "period", "distributions": results}

    # Default: combined
    scores = [_safe_int_score(r.get("score")) for r in rows]
    d = _dist(scores)
    if not d:
        return {"error": "No valid scores found."}
    return {"group_by": "none", **d}


def detect_score_outliers(assignment=None, period=None, threshold=None):
    """Flag scores more than N standard deviations from the assignment mean."""
    threshold = threshold if threshold is not None else 2.0
    rows = _load_master_csv(period_filter=period or "all")
    if not rows:
        return {"error": "No grade data found."}

    # Group by assignment
    assign_groups = defaultdict(list)
    for r in rows:
        assign_groups[r.get("assignment", "unknown")].append(r)

    if assignment:
        norm = _normalize_assignment_name(assignment).lower()
        filtered = {a: rs for a, rs in assign_groups.items()
                    if norm in _normalize_assignment_name(a).lower()}
        if not filtered:
            return {"error": f"No grades found for '{assignment}'."}
        assign_groups = filtered

    outliers = []
    for assign_name, assign_rows in assign_groups.items():
        scores = [_safe_int_score(r.get("score")) for r in assign_rows]
        if len(scores) < 3:
            continue  # Need enough data for meaningful std dev
        mean = sum(scores) / len(scores)
        stdev = statistics.stdev(scores)
        if stdev == 0:
            continue  # All identical scores — no outliers possible
        cutoff_low = mean - (threshold * stdev)
        cutoff_high = mean + (threshold * stdev)

        for r in assign_rows:
            score = _safe_int_score(r.get("score"))
            if score < cutoff_low or score > cutoff_high:
                z_score = round((score - mean) / stdev, 2)
                outliers.append({
                    "student": r.get("student_name", "unknown"),
                    "assignment": assign_name,
                    "score": score,
                    "class_mean": round(mean, 1),
                    "class_stdev": round(stdev, 1),
                    "z_score": z_score,
                    "direction": "above" if score > mean else "below",
                })

    outliers.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    return {
        "outlier_count": len(outliers),
        "threshold_stdev": threshold,
        "assignments_scanned": len(assign_groups),
        "outliers": outliers[:30],  # Cap for token efficiency
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

ANALYTICS_TOOL_HANDLERS = {
    "get_grade_trends": get_grade_trends,
    "get_rubric_weakness": get_rubric_weakness,
    "flag_at_risk_students": flag_at_risk_students,
    "compare_assignments": compare_assignments,
    "get_grade_distribution": get_grade_distribution,
    "detect_score_outliers": detect_score_outliers,
}
