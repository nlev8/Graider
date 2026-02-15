"""
Analytics API routes for Graider.
Provides student performance data, charts, and statistics.
"""
import os
import csv
from collections import defaultdict
from flask import Blueprint, request, jsonify

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/api/analytics')
def get_analytics():
    """Load master CSV and return analytics data for charts."""
    # Get period filter from query params
    period_filter = request.args.get('period', 'all')

    # Try to get output folder from global settings, fallback to default
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")

    if os.path.exists(settings_file):
        try:
            import json
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                output_folder = settings.get('output_folder', output_folder)
        except:
            pass

    master_file = os.path.join(output_folder, "master_grades.csv")

    if not os.path.exists(master_file):
        return jsonify({"error": "No data yet", "students": [], "assignments": [], "trends": []})

    students = defaultdict(list)
    assignments = defaultdict(list)
    categories = defaultdict(lambda: {"content": [], "completeness": [], "writing": [], "effort": []})
    all_grades = []
    available_periods = set()

    try:
        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip corrupted rows (no student name)
                if not row.get("Student Name"):
                    continue

                # Track all available periods
                row_quarter = row.get("Quarter", "")
                if row_quarter:
                    available_periods.add(row_quarter)

                # Filter by period if specified
                if period_filter != 'all' and row_quarter != period_filter:
                    continue

                grade_data = {
                    "date": row.get("Date", ""),
                    "student_id": row.get("Student ID", ""),
                    "student_name": row.get("Student Name", ""),
                    "first_name": row.get("First Name", ""),
                    "assignment": row.get("Assignment", ""),
                    "quarter": row_quarter,
                    "score": int(float(row.get("Overall Score", 0) or 0)),
                    "letter_grade": row.get("Letter Grade", ""),
                    "content": int(float(row.get("Content Accuracy", 0) or 0)),
                    "completeness": int(float(row.get("Completeness", 0) or 0)),
                    "writing": int(float(row.get("Writing Quality", 0) or 0)),
                    "effort": int(float(row.get("Effort Engagement", 0) or 0)),
                    "api_cost": float(row.get("API Cost", 0) or 0),
                    "input_tokens": int(float(row.get("Input Tokens", 0) or 0)),
                    "output_tokens": int(float(row.get("Output Tokens", 0) or 0)),
                    "api_calls": int(float(row.get("API Calls", 0) or 0)),
                    "ai_model": row.get("AI Model", ""),
                }
                all_grades.append(grade_data)

                # Group by student
                students[grade_data["student_name"]].append(grade_data)

                # Group by assignment
                assignments[grade_data["assignment"]].append(grade_data)

                # Track category scores
                categories[grade_data["student_name"]]["content"].append(grade_data["content"])
                categories[grade_data["student_name"]]["completeness"].append(grade_data["completeness"])
                categories[grade_data["student_name"]]["writing"].append(grade_data["writing"])
                categories[grade_data["student_name"]]["effort"].append(grade_data["effort"])
    except Exception as e:
        return jsonify({"error": str(e)})

    # Calculate student progress (for line charts)
    student_progress = []
    for name, grades in students.items():
        sorted_grades = sorted(grades, key=lambda x: x["date"])
        avg = round(sum(g["score"] for g in grades) / len(grades), 1) if grades else 0

        if len(sorted_grades) >= 2:
            trend = "improving" if sorted_grades[-1]["score"] > sorted_grades[0]["score"] else \
                    "declining" if sorted_grades[-1]["score"] < sorted_grades[0]["score"] else "stable"
        else:
            trend = "stable"

        student_progress.append({
            "name": name,
            "grades": [{"date": g["date"], "assignment": g["assignment"], "score": g["score"]} for g in sorted_grades],
            "average": avg,
            "trend": trend
        })

    # Calculate assignment averages (for bar charts)
    assignment_stats = []
    for name, grades in assignments.items():
        assignment_stats.append({
            "name": name,
            "average": round(sum(g["score"] for g in grades) / len(grades), 1) if grades else 0,
            "count": len(grades),
            "highest": max(g["score"] for g in grades) if grades else 0,
            "lowest": min(g["score"] for g in grades) if grades else 0
        })

    # Calculate category averages per student (for radar charts)
    category_stats = []
    for name, cats in categories.items():
        category_stats.append({
            "name": name,
            "content": round(sum(cats["content"]) / len(cats["content"]) * 2.5, 1) if cats["content"] else 0,
            "completeness": round(sum(cats["completeness"]) / len(cats["completeness"]) * 4, 1) if cats["completeness"] else 0,
            "writing": round(sum(cats["writing"]) / len(cats["writing"]) * 5, 1) if cats["writing"] else 0,
            "effort": round(sum(cats["effort"]) / len(cats["effort"]) * 6.67, 1) if cats["effort"] else 0
        })

    # Class-wide stats
    all_scores = [g["score"] for g in all_grades]
    class_stats = {
        "total_assignments": len(all_grades),
        "total_students": len(students),
        "class_average": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
        "highest": max(all_scores) if all_scores else 0,
        "lowest": min(all_scores) if all_scores else 0,
        "grade_distribution": {
            "A": len([s for s in all_scores if s >= 90]),
            "B": len([s for s in all_scores if 80 <= s < 90]),
            "C": len([s for s in all_scores if 70 <= s < 80]),
            "D": len([s for s in all_scores if 60 <= s < 70]),
            "F": len([s for s in all_scores if s < 60])
        }
    }

    # Students needing attention (below 70 average or declining)
    attention_needed = [s for s in student_progress if s["average"] < 70 or s["trend"] == "declining"]

    # Top performers
    top_performers = sorted(student_progress, key=lambda x: x["average"], reverse=True)[:5]

    # Cost summary
    total_cost = sum(g.get("api_cost", 0) for g in all_grades)
    total_input = sum(g.get("input_tokens", 0) for g in all_grades)
    total_output = sum(g.get("output_tokens", 0) for g in all_grades)
    total_api_calls = sum(g.get("api_calls", 0) for g in all_grades)

    # Cost by model
    cost_by_model = {}
    for g in all_grades:
        model = g.get("ai_model", "") or "unknown"
        if model not in cost_by_model:
            cost_by_model[model] = {"cost": 0, "count": 0, "tokens": 0}
        cost_by_model[model]["cost"] += g.get("api_cost", 0)
        cost_by_model[model]["count"] += 1
        cost_by_model[model]["tokens"] += g.get("input_tokens", 0) + g.get("output_tokens", 0)

    # Cost by assignment
    cost_by_assignment = {}
    for g in all_grades:
        assign = g.get("assignment", "") or "unknown"
        if assign not in cost_by_assignment:
            cost_by_assignment[assign] = {"cost": 0, "count": 0}
        cost_by_assignment[assign]["cost"] += g.get("api_cost", 0)
        cost_by_assignment[assign]["count"] += 1

    cost_summary = {
        "total_cost": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_api_calls": total_api_calls,
        "avg_cost_per_student": round(total_cost / len(all_grades), 4) if all_grades else 0,
        "by_model": [{"model": m, **v} for m, v in sorted(cost_by_model.items(), key=lambda x: x[1]["cost"], reverse=True) if m != "unknown"],
        "by_assignment": [{"assignment": a, **v} for a, v in sorted(cost_by_assignment.items(), key=lambda x: x[1]["cost"], reverse=True)],
    }

    return jsonify({
        "class_stats": class_stats,
        "student_progress": sorted(student_progress, key=lambda x: x["name"]),
        "assignment_stats": assignment_stats,
        "category_stats": category_stats,
        "attention_needed": attention_needed,
        "top_performers": top_performers,
        "all_grades": all_grades,
        "available_periods": sorted(list(available_periods)),
        "cost_summary": cost_summary
    })


@analytics_bp.route('/api/export-district-report')
def export_district_report():
    """
    Export anonymized aggregate data for district reporting.
    Contains NO student names or PII - only aggregate statistics.
    Principals can collect these from teachers for school-wide analysis.
    """
    import json
    from datetime import datetime

    # Get output folder from settings
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    teacher_name = "Unknown Teacher"
    school_name = "Unknown School"
    subject = "Social Studies"

    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                output_folder = settings.get('output_folder', output_folder)
                teacher_name = settings.get('teacher_name', teacher_name)
                school_name = settings.get('school_name', school_name)
                subject = settings.get('subject', subject)
        except:
            pass

    master_file = os.path.join(output_folder, "master_grades.csv")

    if not os.path.exists(master_file):
        return jsonify({"error": "No grading data available to export"})

    # Collect anonymized aggregate data
    all_grades = []
    students = set()
    assignments = defaultdict(list)
    quarters = defaultdict(list)
    categories = {"content": [], "completeness": [], "writing": [], "effort": []}

    try:
        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                score = int(float(row.get("Overall Score", 0) or 0))
                all_grades.append(score)
                students.add(row.get("Student ID", row.get("Student Name", "unknown")))

                assignment = row.get("Assignment", "Unknown")
                assignments[assignment].append(score)

                quarter = row.get("Quarter", "")
                if quarter:
                    quarters[quarter].append(score)

                # Category scores
                categories["content"].append(int(float(row.get("Content Accuracy", 0) or 0)))
                categories["completeness"].append(int(float(row.get("Completeness", 0) or 0)))
                categories["writing"].append(int(float(row.get("Writing Quality", 0) or 0)))
                categories["effort"].append(int(float(row.get("Effort Engagement", 0) or 0)))
    except Exception as e:
        return jsonify({"error": f"Error reading grades: {str(e)}"})

    if not all_grades:
        return jsonify({"error": "No grades found in data"})

    # Calculate grade distribution
    grade_distribution = {
        "A (90-100)": len([s for s in all_grades if s >= 90]),
        "B (80-89)": len([s for s in all_grades if 80 <= s < 90]),
        "C (70-79)": len([s for s in all_grades if 70 <= s < 80]),
        "D (60-69)": len([s for s in all_grades if 60 <= s < 70]),
        "F (0-59)": len([s for s in all_grades if s < 60])
    }

    # Calculate assignment breakdown
    assignment_stats = []
    for name, scores in sorted(assignments.items()):
        assignment_stats.append({
            "assignment": name,
            "submissions": len(scores),
            "average": round(sum(scores) / len(scores), 1),
            "highest": max(scores),
            "lowest": min(scores)
        })

    # Calculate quarterly breakdown
    quarter_stats = []
    for qtr, scores in sorted(quarters.items()):
        quarter_stats.append({
            "quarter": qtr,
            "submissions": len(scores),
            "average": round(sum(scores) / len(scores), 1)
        })

    # Calculate category averages (normalized to percentage)
    category_averages = {
        "Content Accuracy": round(sum(categories["content"]) / len(categories["content"]) * 2.5, 1) if categories["content"] else 0,
        "Completeness": round(sum(categories["completeness"]) / len(categories["completeness"]) * 4, 1) if categories["completeness"] else 0,
        "Writing Quality": round(sum(categories["writing"]) / len(categories["writing"]) * 5, 1) if categories["writing"] else 0,
        "Effort & Engagement": round(sum(categories["effort"]) / len(categories["effort"]) * 6.67, 1) if categories["effort"] else 0
    }

    # Build the report
    report = {
        "report_metadata": {
            "report_type": "District Analytics Export",
            "generated_at": datetime.now().isoformat(),
            "teacher_name": teacher_name,
            "school_name": school_name,
            "subject": subject,
            "data_period": f"{min(quarters.keys()) if quarters else 'N/A'} - {max(quarters.keys()) if quarters else 'N/A'}",
            "ferpa_notice": "This report contains AGGREGATE DATA ONLY. No individual student information is included."
        },
        "summary_statistics": {
            "total_students": len(students),
            "total_submissions_graded": len(all_grades),
            "total_assignments": len(assignments),
            "class_average": round(sum(all_grades) / len(all_grades), 1),
            "highest_score": max(all_grades),
            "lowest_score": min(all_grades),
            "median_score": sorted(all_grades)[len(all_grades) // 2]
        },
        "grade_distribution": grade_distribution,
        "category_performance": category_averages,
        "assignment_breakdown": assignment_stats,
        "quarterly_trends": quarter_stats,
        "students_at_risk": {
            "below_70_average_count": len([s for s in all_grades if s < 70]),
            "below_60_count": len([s for s in all_grades if s < 60]),
            "percentage_at_risk": round(len([s for s in all_grades if s < 70]) / len(all_grades) * 100, 1)
        }
    }

    return jsonify(report)
