"""
Student Progress History Manager
================================
Tracks student performance over time for personalized feedback.
FERPA Compliant: Data stored locally, no PII sent to AI.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Import shared rubric config
try:
    from backend.rubric_config import RUBRIC_MAX_SCORES
except ImportError:
    try:
        from rubric_config import RUBRIC_MAX_SCORES
    except ImportError:
        # Fallback if config not available
        RUBRIC_MAX_SCORES = {
            "content_accuracy": 40,
            "completeness": 25,
            "writing_quality": 20,
            "effort_engagement": 15
        }

HISTORY_DIR = os.path.expanduser("~/.graider_data/student_history")


def ensure_history_dir():
    """Create history directory if it doesn't exist."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def get_student_history_path(student_id: str) -> str:
    """Get path to student's history file."""
    ensure_history_dir()
    safe_id = str(student_id).replace('/', '_').replace('\\', '_')
    return os.path.join(HISTORY_DIR, f"{safe_id}.json")


def load_student_history(student_id: str) -> dict:
    """
    Load a student's complete grading history.

    Returns dict with:
    - assignments: list of past assignment results
    - skill_scores: running averages by category
    - streaks: detected improvement patterns
    - last_updated: timestamp
    """
    if not student_id or student_id == "UNKNOWN":
        return None

    path = get_student_history_path(student_id)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            pass

    return {
        "student_id": student_id,
        "assignments": [],
        "skill_scores": {},
        "streaks": {},
        "patterns": [],
        "last_updated": None
    }


def save_student_history(student_id: str, history: dict):
    """Save student's history to file."""
    if not student_id or student_id == "UNKNOWN":
        return

    history["last_updated"] = datetime.now().isoformat()
    path = get_student_history_path(student_id)

    try:
        with open(path, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving student history: {e}")


def add_assignment_to_history(student_id: str, result: dict) -> dict:
    """
    Add a graded assignment to student's history and analyze patterns.

    Args:
        student_id: The student's ID
        result: The grading result dict with score, breakdown, feedback, etc.

    Returns:
        Updated history dict with new patterns detected
    """
    history = load_student_history(student_id)
    if not history:
        return None

    # Extract skills from result
    skills_data = result.get("skills_demonstrated", {})
    strength_skills = skills_data.get("strengths", []) if isinstance(skills_data, dict) else []
    developing_skills = skills_data.get("developing", []) if isinstance(skills_data, dict) else []

    # Create compact assignment record
    assignment_record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "assignment": result.get("assignment", "Unknown"),
        "score": result.get("score", 0),
        "letter_grade": result.get("letter_grade", ""),
        "breakdown": result.get("breakdown", {}),
        "excellent_answers": result.get("excellent_answers", []),
        "needs_improvement": result.get("needs_improvement", []),
        "student_responses": result.get("student_responses", [])[:5],  # Keep top 5
        "skills_strengths": strength_skills,
        "skills_developing": developing_skills,
    }

    history["assignments"].append(assignment_record)

    # Keep last 20 assignments max
    if len(history["assignments"]) > 20:
        history["assignments"] = history["assignments"][-20:]

    # Update skill scores (rolling averages)
    history["skill_scores"] = calculate_skill_averages(history["assignments"])

    # Detect streaks and patterns
    history["streaks"] = detect_streaks(history["assignments"])
    history["patterns"] = detect_patterns(history["assignments"])

    # Detect skill-based patterns (beyond rubric)
    history["skill_patterns"] = detect_skill_patterns(history["assignments"])

    save_student_history(student_id, history)
    return history


def calculate_skill_averages(assignments: list) -> dict:
    """Calculate rolling averages for each skill category."""
    if not assignments:
        return {}

    # Use last 5 assignments for current average
    recent = assignments[-5:]

    skill_totals = defaultdict(list)
    for a in recent:
        breakdown = a.get("breakdown", {})
        for skill, score in breakdown.items():
            if isinstance(score, (int, float)):
                skill_totals[skill].append(score)

    averages = {}
    for skill, scores in skill_totals.items():
        averages[skill] = {
            "current_avg": round(sum(scores) / len(scores), 1),
            "count": len(scores)
        }

    # Calculate overall trend using all assignments
    if len(assignments) >= 3:
        first_half = assignments[:len(assignments)//2]
        second_half = assignments[len(assignments)//2:]

        first_avg = sum(a.get("score", 0) for a in first_half) / len(first_half)
        second_avg = sum(a.get("score", 0) for a in second_half) / len(second_half)

        if second_avg > first_avg + 5:
            averages["_overall_trend"] = "improving"
        elif second_avg < first_avg - 5:
            averages["_overall_trend"] = "declining"
        else:
            averages["_overall_trend"] = "stable"

    return averages


def detect_streaks(assignments: list) -> dict:
    """Detect improvement streaks in specific skills."""
    if len(assignments) < 3:
        return {}

    streaks = {}
    recent = assignments[-5:]

    # Check each skill category
    skills = list(RUBRIC_MAX_SCORES.keys())

    for skill in skills:
        scores = []
        for a in recent:
            breakdown = a.get("breakdown", {})
            if skill in breakdown:
                scores.append(breakdown[skill])

        if len(scores) >= 3:
            # Check for improvement streak (last 3+ scores increasing)
            improving = all(scores[i] <= scores[i+1] for i in range(len(scores)-3, len(scores)-1))
            declining = all(scores[i] >= scores[i+1] for i in range(len(scores)-3, len(scores)-1))

            if improving and scores[-1] > scores[-3]:
                streaks[skill] = {
                    "type": "improving",
                    "length": 3,
                    "latest_score": scores[-1]
                }
            elif declining and scores[-1] < scores[-3]:
                streaks[skill] = {
                    "type": "declining",
                    "length": 3,
                    "latest_score": scores[-1]
                }

    # Check overall grade streak
    grades = [a.get("score", 0) for a in recent]
    if len(grades) >= 3:
        last_three = grades[-3:]
        if all(g >= 90 for g in last_three):
            streaks["_grade_streak"] = {"type": "A_streak", "length": 3}
        elif all(g >= 80 for g in last_three):
            streaks["_grade_streak"] = {"type": "B_or_better", "length": 3}
        elif last_three[-1] > last_three[0]:
            streaks["_grade_streak"] = {"type": "improving", "length": 3}

    return streaks


def detect_patterns(assignments: list) -> list:
    """Detect recurring patterns (strengths/weaknesses) across assignments."""
    if len(assignments) < 2:
        return []

    patterns = []
    recent = assignments[-5:]

    # Analyze skill consistency
    skill_performance = defaultdict(list)
    for a in recent:
        breakdown = a.get("breakdown", {})
        for skill, score in breakdown.items():
            if isinstance(score, (int, float)):
                # Normalize to percentage of max using shared config
                max_score = RUBRIC_MAX_SCORES.get(skill, 100)
                pct = (score / max_score) * 100
                skill_performance[skill].append(pct)

    # Find consistent strengths (>85% on average)
    for skill, pcts in skill_performance.items():
        if len(pcts) >= 2:
            avg = sum(pcts) / len(pcts)
            if avg >= 85:
                skill_name = skill.replace("_", " ").title()
                patterns.append({
                    "type": "strength",
                    "skill": skill,
                    "description": f"Consistently strong in {skill_name}"
                })
            elif avg <= 60:
                skill_name = skill.replace("_", " ").title()
                patterns.append({
                    "type": "weakness",
                    "skill": skill,
                    "description": f"Needs support in {skill_name}"
                })

    # Look for excellent answer themes
    all_excellent = []
    for a in recent:
        all_excellent.extend(a.get("excellent_answers", []))

    if len(all_excellent) >= 3:
        patterns.append({
            "type": "strength",
            "skill": "detailed_responses",
            "description": "Consistently provides thoughtful, detailed responses"
        })

    return patterns


def detect_skill_patterns(assignments: list) -> dict:
    """
    Detect patterns in specific skills BEYOND the rubric categories.

    Tracks skills like: reading comprehension, critical thinking, source analysis,
    making connections, vocabulary usage, following directions, organization, etc.
    """
    if len(assignments) < 2:
        return {"consistent_strengths": [], "improving": [], "needs_focus": []}

    recent = assignments[-5:]

    # Count skill occurrences
    strength_counts = defaultdict(int)
    developing_counts = defaultdict(int)

    for a in recent:
        for skill in a.get("skills_strengths", []):
            if isinstance(skill, str):
                # Normalize skill name (lowercase, strip)
                normalized = skill.lower().strip()
                strength_counts[normalized] += 1

        for skill in a.get("skills_developing", []):
            if isinstance(skill, str):
                normalized = skill.lower().strip()
                developing_counts[normalized] += 1

    result = {
        "consistent_strengths": [],
        "improving": [],
        "needs_focus": []
    }

    # Find consistent strengths (appears in 2+ of last 5 assignments)
    for skill, count in strength_counts.items():
        if count >= 2:
            result["consistent_strengths"].append({
                "skill": skill,
                "count": count,
                "description": f"Strong in {skill} ({count} of last {len(recent)} assignments)"
            })

    # Find skills that were developing but now showing as strength (improving)
    for skill in strength_counts:
        if skill in developing_counts:
            # Skill appeared in both - check if recent trend is positive
            # (more recent assignments show it as strength)
            recent_as_strength = 0
            recent_as_developing = 0
            for a in recent[-3:]:  # Last 3 assignments
                if skill in [s.lower().strip() for s in a.get("skills_strengths", []) if isinstance(s, str)]:
                    recent_as_strength += 1
                if skill in [s.lower().strip() for s in a.get("skills_developing", []) if isinstance(s, str)]:
                    recent_as_developing += 1

            if recent_as_strength > recent_as_developing:
                result["improving"].append({
                    "skill": skill,
                    "description": f"Improving in {skill}!"
                })

    # Find persistent developing areas (appears in 2+ assignments as developing)
    for skill, count in developing_counts.items():
        if count >= 2 and skill not in [s["skill"] for s in result["improving"]]:
            result["needs_focus"].append({
                "skill": skill,
                "count": count,
                "description": f"Still developing {skill} ({count} assignments)"
            })

    return result


def calculate_student_baseline(assignments: list) -> dict:
    """
    Calculate a student's baseline performance metrics.

    Used to detect significant deviations that may indicate plagiarism or AI use.

    Returns:
        - overall_avg: Average overall score
        - overall_std: Standard deviation of overall scores
        - category_baselines: Per-rubric-category averages and std devs
        - typical_skills: Skills the student typically demonstrates
        - assignment_count: Number of assignments used for baseline
    """
    import statistics

    if len(assignments) < 3:
        # Need at least 3 assignments to establish a meaningful baseline
        return None

    # Use all assignments for baseline (more data = better baseline)
    scores = [a.get("score", 0) for a in assignments]

    baseline = {
        "overall_avg": round(statistics.mean(scores), 1),
        "overall_std": round(statistics.stdev(scores), 1) if len(scores) > 1 else 10,
        "category_baselines": {},
        "typical_skills": [],
        "assignment_count": len(assignments)
    }

    # Calculate per-category baselines
    category_scores = defaultdict(list)
    for a in assignments:
        breakdown = a.get("breakdown", {})
        for cat, score in breakdown.items():
            if isinstance(score, (int, float)):
                category_scores[cat].append(score)

    for cat, cat_scores in category_scores.items():
        if len(cat_scores) >= 2:
            baseline["category_baselines"][cat] = {
                "avg": round(statistics.mean(cat_scores), 1),
                "std": round(statistics.stdev(cat_scores), 1) if len(cat_scores) > 1 else 5,
                "max_seen": max(cat_scores),
                "min_seen": min(cat_scores)
            }

    # Determine typical skills (appear in at least 30% of assignments)
    skill_counts = defaultdict(int)
    for a in assignments:
        for skill in a.get("skills_strengths", []):
            if isinstance(skill, str):
                skill_counts[skill.lower().strip()] += 1

    threshold = len(assignments) * 0.3
    baseline["typical_skills"] = [
        skill for skill, count in skill_counts.items()
        if count >= threshold
    ]

    return baseline


def detect_baseline_deviation(student_id: str, current_result: dict) -> dict:
    """
    Check if current submission deviates significantly from student's baseline.

    Returns:
        - flag: 'normal', 'review', or 'significant_deviation'
        - reasons: List of specific deviations detected
        - details: Detailed deviation metrics
    """
    history = load_student_history(student_id)
    if not history:
        return {"flag": "normal", "reasons": [], "details": {}}

    assignments = history.get("assignments", [])
    baseline = calculate_student_baseline(assignments)

    if not baseline:
        # Not enough history to establish baseline
        return {
            "flag": "normal",
            "reasons": ["Insufficient history for baseline comparison"],
            "details": {"baseline_assignments": len(assignments)}
        }

    current_score = current_result.get("score", 0)
    current_breakdown = current_result.get("breakdown", {})
    current_skills = current_result.get("skills_demonstrated", {})
    current_strengths = current_skills.get("strengths", []) if isinstance(current_skills, dict) else []

    deviations = []
    details = {
        "baseline_avg": baseline["overall_avg"],
        "baseline_std": baseline["overall_std"],
        "current_score": current_score,
        "baseline_assignments": baseline["assignment_count"]
    }

    # Check overall score deviation (more than 2 standard deviations above baseline)
    score_deviation = current_score - baseline["overall_avg"]
    std_deviations = score_deviation / baseline["overall_std"] if baseline["overall_std"] > 0 else 0
    details["score_std_deviations"] = round(std_deviations, 2)

    if std_deviations > 2.5:
        deviations.append(f"Overall score ({current_score}) is {std_deviations:.1f} std devs above baseline ({baseline['overall_avg']:.0f})")

    # Check per-category deviations
    category_flags = []
    for cat, cat_baseline in baseline["category_baselines"].items():
        if cat in current_breakdown:
            current_cat_score = current_breakdown[cat]
            cat_deviation = current_cat_score - cat_baseline["avg"]
            cat_std_devs = cat_deviation / cat_baseline["std"] if cat_baseline["std"] > 0 else 0

            # Flag if score is significantly above their max OR more than 2 std devs above avg
            if current_cat_score > cat_baseline["max_seen"] + 5 or cat_std_devs > 2.5:
                cat_name = cat.replace("_", " ").title()
                category_flags.append(f"{cat_name}: {current_cat_score} vs baseline avg {cat_baseline['avg']:.0f}")

    if category_flags:
        deviations.append(f"Category deviations: {'; '.join(category_flags)}")

    # Check for sudden appearance of new sophisticated skills
    if current_strengths and baseline["typical_skills"]:
        new_skills = []
        for skill in current_strengths:
            if isinstance(skill, str):
                skill_lower = skill.lower().strip()
                if skill_lower not in baseline["typical_skills"]:
                    new_skills.append(skill)

        if len(new_skills) >= 3:
            deviations.append(f"Multiple new skills not previously demonstrated: {', '.join(new_skills[:3])}")

    # Check for dramatic improvement (jump of 20+ points from recent average)
    recent_scores = [a.get("score", 0) for a in assignments[-3:]]
    if recent_scores:
        recent_avg = sum(recent_scores) / len(recent_scores)
        if current_score - recent_avg >= 20:
            deviations.append(f"Sudden improvement: {current_score} vs recent avg {recent_avg:.0f} (+{current_score - recent_avg:.0f} points)")

    # Determine flag level
    if len(deviations) >= 2 or (len(deviations) == 1 and std_deviations > 3):
        flag = "significant_deviation"
    elif len(deviations) >= 1:
        flag = "review"
    else:
        flag = "normal"

    return {
        "flag": flag,
        "reasons": deviations,
        "details": details
    }


def get_baseline_summary(student_id: str) -> dict:
    """Get a summary of a student's baseline for display purposes."""
    history = load_student_history(student_id)
    if not history:
        return None

    baseline = calculate_student_baseline(history.get("assignments", []))
    if not baseline:
        return None

    return {
        "overall_avg": baseline["overall_avg"],
        "overall_std": baseline["overall_std"],
        "assignment_count": baseline["assignment_count"],
        "typical_skills": baseline["typical_skills"][:5],
        "category_averages": {
            cat: data["avg"]
            for cat, data in baseline["category_baselines"].items()
        }
    }


def build_history_context(student_id: str) -> str:
    """
    Build a context string about student's history for AI prompt.

    Returns a concise summary suitable for including in grading prompt.
    Does NOT include any PII - only performance patterns.
    """
    history = load_student_history(student_id)
    if not history or not history.get("assignments"):
        return ""

    context_parts = []
    assignments = history.get("assignments", [])
    skill_scores = history.get("skill_scores", {})
    streaks = history.get("streaks", {})
    patterns = history.get("patterns", [])

    # Assignment count
    context_parts.append(f"This student has {len(assignments)} previous assignments graded.")

    # --- Section A: Previous assignment scores with names and dates ---
    recent_assignments = assignments[-5:][::-1]  # Last 5, most recent first
    if recent_assignments:
        context_parts.append("")
        context_parts.append("PREVIOUS ASSIGNMENTS (most recent first):")
        for a in recent_assignments:
            name = a.get("assignment", "Unknown Assignment")
            score = a.get("score", 0)
            letter = a.get("letter_grade", "")
            date = a.get("date", "")
            date_str = f" — {date}" if date else ""
            grade_str = f" ({letter})" if letter else ""
            context_parts.append(f"- {name}: {score}/100{grade_str}{date_str}")

    # Recent average (kept for quick reference)
    if len(assignments) >= 2:
        recent_scores = [a.get("score", 0) for a in assignments[-3:]]
        avg_recent = sum(recent_scores) / len(recent_scores)
        context_parts.append(f"Recent average score: {avg_recent:.0f}/100")

    # --- Section B: Previous needs_improvement items ---
    most_recent = assignments[-1] if assignments else {}
    prev_needs_improvement = most_recent.get("needs_improvement", [])
    if prev_needs_improvement:
        context_parts.append("")
        context_parts.append("AREAS STUDENT WAS TOLD TO IMPROVE LAST TIME:")
        for item in prev_needs_improvement[:3]:
            truncated = item[:150] if isinstance(item, str) else str(item)[:150]
            context_parts.append(f'- "{truncated}"')

    # Overall trend
    overall_trend = skill_scores.get("_overall_trend")
    if overall_trend == "improving":
        context_parts.append("TREND: Student's grades have been IMPROVING over time.")
    elif overall_trend == "declining":
        context_parts.append("TREND: Student's grades have been declining - may need encouragement.")

    # Streaks
    for skill, streak_info in streaks.items():
        if skill.startswith("_"):
            if skill == "_grade_streak":
                if streak_info.get("type") == "A_streak":
                    context_parts.append("STREAK: 3+ consecutive A grades! Acknowledge this achievement!")
                elif streak_info.get("type") == "improving":
                    context_parts.append("STREAK: Grades have improved over the last 3 assignments!")
        else:
            skill_name = skill.replace("_", " ").title()
            if streak_info.get("type") == "improving":
                context_parts.append(f"STREAK: {skill_name} has been improving for 3+ assignments!")
            elif streak_info.get("type") == "declining":
                context_parts.append(f"CONCERN: {skill_name} scores have been declining.")

    # Patterns (strengths/weaknesses)
    strengths = [p for p in patterns if p.get("type") == "strength"]
    weaknesses = [p for p in patterns if p.get("type") == "weakness"]

    if strengths:
        strength_names = [s.get("description", "") for s in strengths[:2]]
        context_parts.append(f"STRENGTHS: {'; '.join(strength_names)}")

    if weaknesses:
        weakness_names = [w.get("description", "") for w in weaknesses[:2]]
        context_parts.append(f"AREAS FOR GROWTH: {'; '.join(weakness_names)}")

    # Skill patterns (beyond rubric categories)
    skill_patterns = history.get("skill_patterns", {})

    # Consistent skill strengths
    consistent_skills = skill_patterns.get("consistent_strengths", [])
    if consistent_skills:
        skill_names = [s.get("skill", "") for s in consistent_skills[:3]]
        context_parts.append(f"CONSISTENT SKILLS: Student regularly shows strength in: {', '.join(skill_names)}")

    # Improving skills
    improving_skills = skill_patterns.get("improving", [])
    if improving_skills:
        skill_names = [s.get("skill", "") for s in improving_skills[:2]]
        context_parts.append(f"IMPROVING SKILLS: Student is getting better at: {', '.join(skill_names)} - acknowledge this progress!")

    # Skills needing focus
    focus_skills = skill_patterns.get("needs_focus", [])
    if focus_skills:
        skill_names = [s.get("skill", "") for s in focus_skills[:2]]
        context_parts.append(f"SKILLS TO ENCOURAGE: Student is still developing: {', '.join(skill_names)}")

    # Previous excellent answers (for continuity)
    all_excellent = []
    for a in assignments[-3:]:
        all_excellent.extend(a.get("excellent_answers", [])[:1])

    if all_excellent:
        context_parts.append(f"Previous excellent work examples: {all_excellent[0][:100]}...")

    if not context_parts:
        return ""

    # --- Section C: Mandatory referencing instructions ---
    context_parts.append("")
    context_parts.append("YOU MUST reference this history in your feedback:")
    context_parts.append("- Compare this assignment's score to their recent scores listed above")
    context_parts.append('- Check if they improved on the "AREAS TO IMPROVE" from last time — call it out either way')
    context_parts.append("- Acknowledge continued strengths from their history")
    context_parts.append("- If score is declining, address the trend with encouragement and specific guidance")

    return "\n".join([
        "---",
        "STUDENT PERFORMANCE HISTORY (MANDATORY -- you MUST reference this):",
        *context_parts,
        "---"
    ])
