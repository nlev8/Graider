# Student Progress Tracking Implementation Plan

## Overview
Add a student history tracking system that keeps detailed records of each student's strengths and weaknesses over time, enabling personalized feedback with historical insights like "You're on a streak! Your reading comprehension has gotten better over the last three assignments."

## Architecture

### New Files
1. `backend/student_history.py` - Student history manager

### Modified Files
1. `assignment_grader.py` - Pass history context to AI, update prompt
2. `backend/app.py` - Load/save history, pass to grading thread
3. `frontend/src/App.jsx` - Display student progress in results (optional enhancement)

---

## File 1: Create `backend/student_history.py`

```python
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

HISTORY_DIR = os.path.expanduser("~/.graider_data/student_history")


def ensure_history_dir():
    """Create history directory if it doesn't exist."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def get_student_history_path(student_id: str) -> str:
    """Get path to student's history file."""
    ensure_history_dir()
    safe_id = student_id.replace('/', '_').replace('\\', '_')
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
    skills = ["content_accuracy", "completeness", "writing_quality", "effort_engagement"]

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
                # Normalize to percentage of max
                max_scores = {
                    "content_accuracy": 40,
                    "completeness": 25,
                    "writing_quality": 20,
                    "effort_engagement": 15
                }
                max_score = max_scores.get(skill, 100)
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

    # Recent performance
    if len(assignments) >= 2:
        recent_scores = [a.get("score", 0) for a in assignments[-3:]]
        avg_recent = sum(recent_scores) / len(recent_scores)
        context_parts.append(f"Recent average score: {avg_recent:.0f}/100")

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

    # Previous excellent answers (for continuity)
    all_excellent = []
    for a in assignments[-3:]:
        all_excellent.extend(a.get("excellent_answers", [])[:1])

    if all_excellent:
        context_parts.append(f"Previous excellent work examples: {all_excellent[0][:100]}...")

    if not context_parts:
        return ""

    return "\n".join([
        "---",
        "STUDENT HISTORY CONTEXT (for personalized feedback):",
        *context_parts,
        "",
        "Use this history to personalize feedback:",
        "- Reference improvements or streaks when relevant",
        "- Acknowledge consistent strengths",
        "- Gently address recurring weaknesses with specific guidance",
        "- Connect current work to past achievements when possible",
        "---"
    ])
```

---

## File 2: Modify `assignment_grader.py`

### Edit 1: Add import at top (after line 31)
**Location:** After `from dotenv import load_dotenv`

```python
# Add after line 31:
try:
    from backend.student_history import build_history_context, add_assignment_to_history
except ImportError:
    # Fallback if running standalone
    def build_history_context(student_id):
        return ""
    def add_assignment_to_history(student_id, result):
        return None
```

### Edit 2: Update `grade_assignment()` function signature (line 636)
**Current:**
```python
def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini') -> dict:
```

**New:**
```python
def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini', student_id: str = None) -> dict:
```

### Edit 3: Build history context in `grade_assignment()` (after line 680, after custom_section)
**Location:** After the custom_section is built, add:

```python
    # Build student history context for personalized feedback
    history_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            history_context = build_history_context(student_id)
        except Exception as e:
            print(f"  Note: Could not load student history: {e}")
```

### Edit 4: Insert history_context into prompt (around line 693)
**Location:** After `{custom_section}` in prompt_text, add `{history_context}`

So it becomes:
```python
    prompt_text = f"""
{GRADING_RUBRIC}

{ASSIGNMENT_INSTRUCTIONS}
{custom_section}
{history_context}
---

STUDENT CONTEXT:
...
```

### Edit 5: Update the feedback instruction in JSON format (around line 770)
Find this line in prompt_text:
```python
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback...
```

Replace the entire feedback instruction with:
```python
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback that sounds like a real teacher wrote it - warm, encouraging, and specific. IMPORTANT GUIDELINES: 1) VARY your sentence structure and openings - don't start every sentence the same way. Mix short punchy sentences with longer ones. 2) QUOTE specific answers from the student's work when praising them (e.g., 'I loved how you explained that [quote their answer]' or 'Your answer about [topic] - '[their exact words]' - shows real understanding'). 3) When mentioning areas to improve, be gentle and constructive - reference specific questions they struggled with and give them a hint or the right direction. 4) Sound HUMAN - use contractions (you're, that's, I'm), occasional casual phrases ('Nice!', 'Great thinking here'), and vary your enthusiasm. 5) End with genuine encouragement that connects to something specific they did well. 6) Do NOT use the student's name - say 'you' or 'your'. 7) Avoid repetitive phrases like 'Great job!' at the start of every paragraph - mix it up! 8) IF STUDENT HISTORY IS PROVIDED: Reference their progress! Mention streaks ('You're on a 3-assignment improvement streak in writing quality!'), acknowledge consistent strengths ('Your attention to detail continues to shine'), encourage growth in weak areas ('I see you're working on completeness - keep at it!'), and connect current work to past achievements when relevant.>"
```

---

## File 3: Modify `backend/app.py`

### Edit 1: Add import at top (after line 19)
```python
from backend.student_history import add_assignment_to_history, load_student_history
```

### Edit 2: Update `run_grading_thread()` - pass student_id to grade_assignment (line 359)
**Current:**
```python
grade_result = grade_assignment(student_info['student_name'], grade_data, file_ai_notes, grade_level, subject, ai_model)
```

**New:**
```python
grade_result = grade_assignment(student_info['student_name'], grade_data, file_ai_notes, grade_level, subject, ai_model, student_info.get('student_id'))
```

### Edit 3: Save to student history after grading (line 416, after `all_grades.append(grade_record)`)
Add this block right after `all_grades.append(grade_record)`:
```python
            # Save to student history for progress tracking
            if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                try:
                    add_assignment_to_history(student_info['student_id'], grade_record)
                except Exception as e:
                    print(f"  Note: Could not update student history: {e}")
```

### Edit 4: Update individual grading endpoint (line 626)
**Current:**
```python
grade_result = grade_assignment(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model)
```

**New:**
```python
# Get student ID for history tracking
individual_student_id = student_info.get('id', '') if student_info else None
grade_result = grade_assignment(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model, individual_student_id)
```

### Edit 5: Save individual upload to history (after line 678, before `return jsonify(result)`)
Add before `return jsonify(result)`:
```python
        # Save to student history for progress tracking
        if result.get('student_id'):
            try:
                add_assignment_to_history(result['student_id'], result)
            except Exception as e:
                print(f"  Note: Could not update student history: {e}")
```

### Edit 6: Add new API endpoint for viewing student history (after line 912)
Add this new route:
```python
# ══════════════════════════════════════════════════════════════
# STUDENT PROGRESS HISTORY
# ══════════════════════════════════════════════════════════════

@app.route('/api/student-history/<student_id>', methods=['GET'])
def get_student_history_api(student_id):
    """Get a student's grading history and progress patterns."""
    from backend.student_history import load_student_history

    history = load_student_history(student_id)
    if not history:
        return jsonify({"error": "No history found"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_HISTORY", f"Viewed history for student ID: {student_id[:6]}...")

    return jsonify(history)
```

---

## Verification Steps

1. **Start the backend:**
   ```bash
   cd /Users/alexc/Downloads/Graider
   python backend/app.py
   ```

2. **Grade a few assignments** for the same student to build history

3. **Check history file created:**
   ```bash
   ls ~/.graider_data/student_history/
   cat ~/.graider_data/student_history/<student_id>.json
   ```

4. **Verify personalized feedback** - Grade another assignment for the same student and check:
   - Feedback references past performance
   - Streaks are mentioned when applicable
   - Strengths/weaknesses are acknowledged

5. **Test API endpoint:**
   ```bash
   curl http://localhost:3000/api/student-history/<student_id>
   ```

---

## Summary of Changes

| File | Changes |
|------|---------|
| `backend/student_history.py` | NEW - History manager with pattern detection |
| `assignment_grader.py` | Add history context to AI prompt, update feedback instructions |
| `backend/app.py` | Pass student_id to grading, save results to history |

## Data Storage

- History files: `~/.graider_data/student_history/{student_id}.json`
- Each student gets their own file with last 20 assignments
- Includes: scores, breakdowns, streaks, patterns, skill averages
- FERPA compliant: No PII sent to AI, data stored locally
