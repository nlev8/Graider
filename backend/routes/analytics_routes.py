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
            "name": name[:30],
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

    return jsonify({
        "class_stats": class_stats,
        "student_progress": sorted(student_progress, key=lambda x: x["name"]),
        "assignment_stats": assignment_stats,
        "category_stats": category_stats,
        "attention_needed": attention_needed,
        "top_performers": top_performers,
        "all_grades": all_grades,
        "available_periods": sorted(list(available_periods))
    })
