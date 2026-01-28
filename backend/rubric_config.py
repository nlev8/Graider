"""
Shared Rubric Configuration
============================
Single source of truth for rubric point values.
Used by both assignment_grader.py and student_history.py.

If you change point values here, both grading and history tracking
will automatically use the updated values.
"""

# Maximum points per rubric category
RUBRIC_MAX_SCORES = {
    "content_accuracy": 40,
    "completeness": 25,
    "writing_quality": 20,
    "effort_engagement": 15
}

# Total possible points
RUBRIC_TOTAL = sum(RUBRIC_MAX_SCORES.values())  # 100
