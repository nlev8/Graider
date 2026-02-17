"""
Analytics API routes for Graider.
Provides student performance data, charts, and statistics.
"""
import os
import re
import csv
import json
from collections import defaultdict
from flask import Blueprint, request, jsonify

analytics_bp = Blueprint('analytics', __name__)


def _normalize_assignment_name(name):
    """Normalize assignment name for comparison: lowercase, strip extensions, versions, whitespace."""
    n = name.strip()
    n = re.sub(r'\s*\(\d+\)\s*$', '', n)
    n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
    n = n.replace('_', ' ')
    return n.strip().lower()


def _load_valid_assignment_names():
    """Load all saved assignment config titles and aliases as a normalized set."""
    valid_names = set()
    assignments_dir = os.path.expanduser("~/.graider_assignments")
    if not os.path.exists(assignments_dir):
        return valid_names

    for f in os.listdir(assignments_dir):
        if not f.endswith('.json'):
            continue
        try:
            with open(os.path.join(assignments_dir, f), 'r') as cf:
                config = json.load(cf)
                title = config.get('title', '')
                if title:
                    valid_names.add(_normalize_assignment_name(title))
                # Also add the config filename as a valid name
                config_name = f.replace('.json', '')
                valid_names.add(_normalize_assignment_name(config_name))
                # Add any aliases
                for alias in config.get('aliases', []):
                    if alias:
                        valid_names.add(_normalize_assignment_name(alias))
        except Exception:
            pass

    return valid_names


def _assignment_matches_config(assignment_name, valid_names):
    """Check if an assignment name matches any saved config (normalized comparison)."""
    norm = _normalize_assignment_name(assignment_name)
    if norm in valid_names:
        return True
    # Partial match: config name is contained in or contains the assignment name
    for valid in valid_names:
        if len(valid) >= 10 and (valid in norm or norm in valid):
            return True
    return False


@analytics_bp.route('/api/analytics')
def get_analytics():
    """Load master CSV and return analytics data for charts."""
    # Get filters from query params
    period_filter = request.args.get('period', 'all')
    approval_filter = request.args.get('approval', 'all')  # 'all', 'approved', 'pending', 'rejected'
    include_unmatched = request.args.get('include_unmatched', 'false').lower() == 'true'

    # Try to get output folder from global settings, fallback to default
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")

    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                output_folder = settings.get('output_folder', output_folder)
        except Exception:
            pass

    master_file = os.path.join(output_folder, "master_grades.csv")

    if not os.path.exists(master_file):
        return jsonify({"error": "No data yet", "students": [], "assignments": [], "trends": []})

    # Load valid assignment names from saved configs
    valid_names = _load_valid_assignment_names()

    students = defaultdict(list)
    assignments = defaultdict(list)
    categories = defaultdict(lambda: {"content": [], "completeness": [], "writing": [], "effort": []})
    all_grades = []
    available_periods = set()
    skipped_unmatched = 0
    skipped_approval = 0

    # Track ALL cost data before filtering (you pay for API calls regardless of approval)
    all_costs = []  # list of {"api_cost", "input_tokens", "output_tokens", "api_calls", "ai_model", "assignment"}

    try:
        with open(master_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip corrupted rows (no student name, or feedback text in name column)
                student_name = row.get("Student Name", "").strip()
                if not student_name:
                    continue
                if len(student_name) > 40 or any(w in student_name.lower() for w in ['you ', 'your ', 'which ', 'where ', 'focus on']):
                    continue

                # Always collect cost data from every valid row before filtering
                row_cost = float(row.get("API Cost", 0) or 0)
                if row_cost > 0:
                    all_costs.append({
                        "api_cost": row_cost,
                        "input_tokens": int(float(row.get("Input Tokens", 0) or 0)),
                        "output_tokens": int(float(row.get("Output Tokens", 0) or 0)),
                        "api_calls": int(float(row.get("API Calls", 0) or 0)),
                        "ai_model": row.get("AI Model", ""),
                        "assignment": row.get("Assignment", ""),
                    })

                # Filter by saved config match
                row_assignment = row.get("Assignment", "")
                if not include_unmatched and valid_names and not _assignment_matches_config(row_assignment, valid_names):
                    skipped_unmatched += 1
                    continue

                # Filter by approval status
                row_approval = row.get("Approved", "").strip().lower()
                if approval_filter != 'all':
                    if not row_approval:
                        row_approval = 'pending'  # Legacy rows without Approved column
                    if row_approval != approval_filter.lower():
                        skipped_approval += 1
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
                    "approved": row.get("Approved", ""),
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
            # Compare first-half avg vs second-half avg for a more robust trend
            mid = max(1, len(sorted_grades) // 2)
            first_half_avg = sum(g["score"] for g in sorted_grades[:mid]) / mid
            second_half_avg = sum(g["score"] for g in sorted_grades[mid:]) / max(1, len(sorted_grades) - mid)
            diff = second_half_avg - first_half_avg
            if diff >= 3:
                trend = "improving"
            elif diff <= -3:
                trend = "declining"
            else:
                trend = "stable"
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

    # Class-wide stats — grade distribution uses per-student averages
    all_scores = [g["score"] for g in all_grades]
    student_avg_scores = []
    for name, grades in students.items():
        s_scores = [g["score"] for g in grades]
        student_avg_scores.append(round(sum(s_scores) / len(s_scores), 1))

    class_stats = {
        "total_assignments": len(all_grades),
        "total_students": len(students),
        "class_average": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
        "highest": max(all_scores) if all_scores else 0,
        "lowest": min(all_scores) if all_scores else 0,
        "grade_distribution": {
            "A": len([s for s in student_avg_scores if s >= 90]),
            "B": len([s for s in student_avg_scores if 80 <= s < 90]),
            "C": len([s for s in student_avg_scores if 70 <= s < 80]),
            "D": len([s for s in student_avg_scores if 60 <= s < 70]),
            "F": len([s for s in student_avg_scores if s < 60])
        }
    }

    # Minimum assignments to qualify for top performers / attention lists
    MIN_ASSIGNMENTS = 3

    # Students needing attention:
    # - Below 70 average (regardless of trend), with at least 1 graded assignment
    # - Below 80 average AND declining, with enough data to be meaningful
    attention_needed = [
        s for s in student_progress
        if len(s["grades"]) >= 1 and (
            s["average"] < 70
            or (s["average"] < 80 and s["trend"] == "declining" and len(s["grades"]) >= 2)
        )
    ]
    attention_names = {s["name"] for s in attention_needed}

    # Top performers: exclude attention students, require minimum assignments
    top_performers = sorted(
        [s for s in student_progress
         if s["name"] not in attention_names and len(s["grades"]) >= MIN_ASSIGNMENTS],
        key=lambda x: x["average"], reverse=True
    )[:5]

    # Cost summary — uses ALL rows (unfiltered) since API cost is incurred regardless of approval
    total_cost = sum(c["api_cost"] for c in all_costs)
    total_input = sum(c["input_tokens"] for c in all_costs)
    total_output = sum(c["output_tokens"] for c in all_costs)
    total_api_calls = sum(c["api_calls"] for c in all_costs)

    # Cost by model (all rows)
    cost_by_model = {}
    for c in all_costs:
        model = c.get("ai_model", "") or "unknown"
        if model not in cost_by_model:
            cost_by_model[model] = {"cost": 0, "count": 0, "tokens": 0}
        cost_by_model[model]["cost"] += c["api_cost"]
        cost_by_model[model]["count"] += 1
        cost_by_model[model]["tokens"] += c["input_tokens"] + c["output_tokens"]

    # Cost by assignment (all rows)
    cost_by_assignment = {}
    for c in all_costs:
        assign = c.get("assignment", "") or "unknown"
        if assign not in cost_by_assignment:
            cost_by_assignment[assign] = {"cost": 0, "count": 0}
        cost_by_assignment[assign]["cost"] += c["api_cost"]
        cost_by_assignment[assign]["count"] += 1

    # Filtered cost (only what's visible in current analytics view)
    filtered_cost = sum(g.get("api_cost", 0) for g in all_grades)

    cost_summary = {
        "total_cost": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_api_calls": total_api_calls,
        "total_graded": len(all_costs),
        "avg_cost_per_student": round(total_cost / len(all_costs), 4) if all_costs else 0,
        "filtered_cost": round(filtered_cost, 4),
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
        "cost_summary": cost_summary,
        "filters": {
            "period": period_filter,
            "approval": approval_filter,
            "include_unmatched": include_unmatched,
            "skipped_unmatched": skipped_unmatched,
            "skipped_approval": skipped_approval,
            "valid_configs_count": len(valid_names)
        }
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


@analytics_bp.route('/api/analytics/cleanup', methods=['POST'])
def cleanup_master_csv():
    """
    One-time cleanup of master_grades.csv:
    1. Fix assignment names (strip student name prefixes)
    2. Populate Approved column from ~/.graider_results.json
    3. Add Approved column to header if missing
    """
    # Get output folder
    settings_file = os.path.expanduser("~/.graider_global_settings.json")
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")

    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                output_folder = settings.get('output_folder', output_folder)
        except Exception:
            pass

    master_file = os.path.join(output_folder, "master_grades.csv")
    results_file = os.path.expanduser("~/.graider_results.json")

    if not os.path.exists(master_file):
        return jsonify({"error": "No master_grades.csv found"}), 404

    # Load parse_filename for name stripping
    try:
        from assignment_grader import parse_filename
    except ImportError:
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from assignment_grader import parse_filename
        except ImportError:
            parse_filename = None

    # Load existing results for approval status lookup
    approval_lookup = {}  # (student_name, normalized_assignment) -> approval_status
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                results = json.load(f)
                for r in results:
                    student = r.get('student_name', '')
                    assignment = _normalize_assignment_name(r.get('assignment', ''))
                    approval = r.get('email_approval', '')
                    if student and assignment and approval:
                        approval_lookup[(student.lower(), assignment)] = approval
        except Exception:
            pass

    # Read all rows
    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = list(reader)
    except Exception as e:
        return jsonify({"error": f"Could not read CSV: {str(e)}"}), 500

    # Add Approved column if missing
    added_column = False
    if 'Approved' not in header:
        feedback_idx = header.index('Feedback') if 'Feedback' in header else -1
        if feedback_idx >= 0:
            header.insert(feedback_idx + 1, 'Approved')
        else:
            header.append('Approved')
        added_column = True

    names_fixed = 0
    approvals_populated = 0
    corrupted_removed = 0
    seen_keys = set()  # For dedup: (student_id, normalized_assignment)
    cleaned_rows = []

    def _is_corrupted_row(r):
        """Detect rows where feedback text leaked into name/ID columns."""
        name = r.get('Student Name', '').strip()
        score = r.get('Overall Score', '').strip()
        assignment = r.get('Assignment', '').strip()
        if len(name) > 40:
            return True
        if any(w in name.lower() for w in ['you ', 'your ', 'the ', 'which ', 'where ', 'focus on', 'continue']):
            return True
        if not name and not score and not assignment:
            return True
        if score:
            try:
                float(score)
            except ValueError:
                return True
        return False

    for row in rows:
        # Remove corrupted rows (feedback text in name columns)
        if _is_corrupted_row(row):
            corrupted_removed += 1
            continue
        # Ensure Approved key exists
        if 'Approved' not in row:
            row['Approved'] = ''

        # Fix assignment name: strip student name prefix
        assignment = row.get('Assignment', '')
        student_name = row.get('Student Name', '')
        original_assignment = assignment

        if parse_filename and assignment:
            # Check if assignment looks like it has a student name prefix
            # (contains underscores that match FirstName_LastName pattern)
            if '_' in assignment:
                parsed = parse_filename(assignment + '.docx')
                cleaned = parsed.get('assignment_part', '')
                if cleaned:
                    cleaned = re.sub(r'\s*\(\d+\)\s*$', '', cleaned).strip()
                    cleaned = re.sub(r'\.docx?\s*$', '', cleaned, flags=re.IGNORECASE).strip()
                    cleaned = re.sub(r'\.pdf\s*$', '', cleaned, flags=re.IGNORECASE).strip()
                    cleaned = cleaned.replace('_', ' ').strip()
                    if cleaned and cleaned.lower() != _normalize_assignment_name(assignment):
                        row['Assignment'] = cleaned
                        names_fixed += 1

        # Populate Approved from results if empty
        if not row.get('Approved'):
            lookup_key = (student_name.lower(), _normalize_assignment_name(row.get('Assignment', '')))
            if lookup_key in approval_lookup:
                row['Approved'] = approval_lookup[lookup_key]
                approvals_populated += 1

        # Dedup: keep last occurrence for same student+assignment
        student_id = row.get('Student ID', '')
        norm_assign = _normalize_assignment_name(row.get('Assignment', ''))
        dedup_key = (student_id, norm_assign)
        if dedup_key in seen_keys and student_id:
            # Replace the previous row with this one (keep latest)
            cleaned_rows = [r for r in cleaned_rows
                           if not (r.get('Student ID', '') == student_id
                                   and _normalize_assignment_name(r.get('Assignment', '')) == norm_assign)]
        seen_keys.add(dedup_key)
        cleaned_rows.append(row)

    deduped = len(rows) - len(cleaned_rows) - corrupted_removed

    # Write back
    try:
        with open(master_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(cleaned_rows)
    except Exception as e:
        return jsonify({"error": f"Could not write CSV: {str(e)}"}), 500

    return jsonify({
        "status": "success",
        "original_rows": len(rows),
        "cleaned_rows": len(cleaned_rows),
        "names_fixed": names_fixed,
        "approvals_populated": approvals_populated,
        "duplicates_removed": deduped,
        "corrupted_removed": corrupted_removed,
        "approved_column_added": added_column
    })
