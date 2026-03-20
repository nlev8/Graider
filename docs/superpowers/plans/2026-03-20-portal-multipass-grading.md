# Portal Multipass Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect portal student submissions to Graider's full 18-factor multipass grading pipeline (grade_per_question + generate_feedback) so written responses get writing style analysis, historical feedback, accommodations, and rubric-aware scoring — with teacher approval before students see results.

**Architecture:** Create a new `portal_grading.py` service that: (1) builds the same `file_ai_notes` instruction string used by folder-based grading, (2) calls `grade_per_question()` for each written question, (3) calls `generate_feedback()` for overall feedback, (4) writes results in the standard format to both Supabase and teacher results storage. The submission endpoints spawn this as a background thread for assignments with written questions. MC/TF/matching are still graded instantly via a new `grade_instant_only()` function that skips the AI path entirely.

**Tech Stack:** Python/Flask (backend), assignment_grader.py (grading engine), Supabase (storage), React (frontend)

**Spec:** `docs/superpowers/specs/2026-03-20-portal-multipass-grading-design.md`

## GITNEXUS FINDINGS — THREE SEPARATE GRADING PATHS

GitNexus + code review revealed THREE inconsistent grading systems that must be unified:

### Path 1: Join-code submission (`student_portal_routes.py:461`)
- `submit_assessment()` → calls `grade_student_submission()` → inserts into `submissions` table
- Answer keys: `f"{sIdx}-{qIdx}"`, matching: `f"{sIdx}-{qIdx}-match-{tIdx}"`
- Runs OpenAI for SA/ER immediately (double-grading problem)

### Path 2: Class-based submission (`student_account_routes.py:729`)
- `submit_student_work()` → inserts into `student_submissions` with `status: "submitted"` and NO grading
- No instant MC/TF scores — student sees nothing until teacher triggers grading
- **THIS IS THE CLEVER PATH — students get zero feedback on submission**

### Path 3: Teacher re-grade (`student_account_routes.py:438`)
- `grade_portal_submission()` → reads from `student_submissions`, grades, updates in place
- Uses `str(i)` sequential keys AND different field names (`question_type` vs `type`)
- Will overwrite multipass results if teacher clicks regrade

### What the plan must handle:
1. **Path 2 (Clever) needs instant MC grading** — call `grade_instant_only()` and write partial results into `student_submissions.results` on submission
2. **Path 3 must be updated** to either invoke multipass or respect existing multipass results
3. **All three paths must use the same answer key format** — `f"{sIdx}-{qIdx}"`

## CRITICAL DESIGN DECISIONS (from plan review)

1. **Answer key format**: Portal submissions key answers as `f"{sectionIdx}-{questionIdx}"` (e.g., "0-1", "1-3"). Matching questions use `f"{sIdx}-{qIdx}-match-{tIdx}"`. All grading code must use this format, NOT sequential indices.

2. **No double AI grading**: The existing `grade_student_submission()` runs basic OpenAI calls for SA/ER questions. For mixed assignments, we must NOT call this function. Instead, create `grade_instant_only()` that ONLY handles MC/TF/matching deterministically, and let the multipass pipeline handle all written questions.

3. **Table-aware Supabase updates**: Join-code submissions use the `submissions` table. Class-based submissions use `student_submissions`. The grading thread must accept a `table_name` parameter and update the correct table.

4. **Student history in AI notes**: `build_portal_ai_notes()` must append the `student_history` string to the prompt — this is the core differentiation of portal grading.

5. **Matching question scoring**: Must iterate terms with `f"{sIdx}-{qIdx}-match-{tIdx}"` keys and compare letter-by-letter against the correct_matches dict, matching the existing logic in `grade_student_submission`.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/services/portal_grading.py` | Create | Orchestrates multipass grading for portal submissions |
| `backend/routes/student_portal_routes.py` | Modify | Add `grade_instant_only()`, spawn background grading thread |
| `backend/routes/student_account_routes.py` | Modify | Same for class-based submissions |
| `backend/routes/analytics_routes.py` | Modify | Fix district report export to read from results storage |
| `frontend/src/components/StudentPortal.jsx` | Modify | Show partial results (MC scores + "pending review" for written) |
| `tests/test_portal_grading.py` | Create | Tests for the new grading service |

---

### Task 1: Create `portal_grading.py` — the core grading orchestrator

**Files:**
- Create: `backend/services/portal_grading.py`
- Create: `tests/test_portal_grading.py`

This is the most important task. It creates a new service that bridges portal submissions to the multipass grading pipeline.

- [ ] **Step 1: Write the failing test**

Create `tests/test_portal_grading.py`:

```python
"""Tests for portal multipass grading service."""
import pytest
from unittest.mock import patch, MagicMock, ANY


class TestHasWrittenQuestions:
    """Test the auto-detection logic for written vs MC-only assignments."""

    def test_mc_only_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1"},
                    {"type": "true_false", "question": "Q2"},
                    {"type": "matching", "question": "Q3"},
                ]
            }]
        }
        assert has_written_questions(assessment) is False

    def test_short_answer_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1"},
                    {"type": "short_answer", "question": "Q2"},
                ]
            }]
        }
        assert has_written_questions(assessment) is True

    def test_extended_response_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "extended_response", "question": "Q1"},
                ]
            }]
        }
        assert has_written_questions(assessment) is True

    def test_empty_assessment_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assert has_written_questions({}) is False
        assert has_written_questions({"sections": []}) is False


class TestBuildPortalAINotes:
    """Test that AI instruction string is built correctly for portal grading."""

    def test_includes_global_ai_notes(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            global_ai_notes="Be encouraging",
            assignment_title="Test Assignment",
            grade_level="8",
            subject="US History",
        )
        assert "Be encouraging" in result

    def test_includes_grade_and_subject(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            grade_level="8",
            subject="US History",
        )
        assert "8" in result
        assert "US History" in result


class TestGradeWrittenQuestions:
    """Test the written question grading orchestrator."""

    @patch("backend.services.portal_grading.grade_per_question")
    def test_calls_grade_per_question_for_each_written(self, mock_gpq):
        from backend.services.portal_grading import grade_written_questions
        mock_gpq.return_value = {
            "grade": {"score": 8, "possible": 10, "quality": "good", "reasoning": "Solid answer"}
        }
        # Use realistic portal answer key format: "{sectionIdx}-{questionIdx}"
        questions = [
            {"type": "short_answer", "question": "Explain X", "answer": "Expected", "points": 10, "_answer_key": "0-1"},
            {"type": "extended_response", "question": "Analyze Y", "answer": "Expected", "points": 20, "_answer_key": "1-0"},
        ]
        answers = {"0-1": "Student answer 1", "1-0": "Student answer 2"}

        results = grade_written_questions(
            questions=questions,
            answers=answers,
            ai_notes="Be encouraging",
            grade_level="8",
            subject="US History",
            grading_style="standard",
            ai_model="gpt-4o-mini",
        )

        assert mock_gpq.call_count == 2
        assert len(results) == 2
        assert results[0]["grade"]["score"] == 8

    @patch("backend.services.portal_grading.grade_per_question")
    def test_uses_answer_key_not_sequential_index(self, mock_gpq):
        """Verify answers are looked up by section-question key, not sequential index."""
        from backend.services.portal_grading import grade_written_questions
        mock_gpq.return_value = {
            "grade": {"score": 5, "possible": 10, "quality": "ok", "reasoning": "Partial"}
        }
        questions = [
            {"type": "short_answer", "question": "Q", "answer": "A", "points": 10, "_answer_key": "2-3"},
        ]
        # Only key "2-3" has an answer; sequential key "0" does NOT
        answers = {"0": "WRONG KEY", "2-3": "Correct student answer"}

        grade_written_questions(
            questions=questions, answers=answers,
            ai_notes="", grade_level="8", subject="History",
            grading_style="standard",
        )

        # Verify grade_per_question received the correct answer, not "WRONG KEY"
        call_args = mock_gpq.call_args
        assert call_args[1]["student_answer"] == "Correct student answer" or call_args[0][1] == "Correct student answer"


class TestBuildResultRecord:
    """Test that result records match the analytics-expected format."""

    def test_builds_correct_format(self):
        from backend.services.portal_grading import build_result_record
        record = build_result_record(
            student_name="Jane Doe",
            student_id="stu_123",
            assignment_title="Colonial America",
            score=85,
            total_possible=100,
            period="Q3",
            feedback="Good work",
            breakdown={"content_accuracy": 88, "completeness": 90, "writing_quality": 78, "effort_engagement": 85},
            per_question_scores=[],
        )
        assert record["student_name"] == "Jane Doe"
        assert record["score"] == 85
        assert record["email_approval"] == "pending"
        assert record["source"] == "portal"
        assert record["breakdown"]["content_accuracy"] == 88
        assert record["letter_grade"] == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_portal_grading.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.portal_grading'`

- [ ] **Step 3: Write the implementation**

Create `backend/services/portal_grading.py`:

```python
"""
Portal Multipass Grading Service.

Bridges portal student submissions to Graider's full 18-factor grading pipeline.
Skips Pass 1 (extraction) since portal answers are already structured JSON.
Calls grade_per_question (Pass 2) + generate_feedback (Pass 3) from assignment_grader.py.
"""
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Written question types that need AI grading
WRITTEN_TYPES = {"short_answer", "extended_response", "essay", "written"}
# Instant question types (deterministic grading)
INSTANT_TYPES = {"multiple_choice", "true_false", "matching", "fill_in_blank"}


def has_written_questions(assessment):
    """Check if an assessment has any written/essay questions that need AI grading.

    Returns True if any question requires the multipass pipeline.
    Returns False if all questions can be graded instantly (MC/TF/matching only).
    """
    for section in assessment.get("sections", []):
        for q in section.get("questions", []):
            if q.get("type", "multiple_choice") in WRITTEN_TYPES:
                return True
    return False


def build_portal_ai_notes(global_ai_notes="", assignment_title="",
                          grade_level="", subject="", grading_style="standard",
                          rubric=None, accommodation_prompt="",
                          student_history="", class_period=""):
    """Build the AI instruction string for portal grading.

    Mirrors the file_ai_notes accumulation logic in app.py but for portal context.
    CRITICAL: student_history MUST be included — this is the core differentiator
    that enables personalized, historically-aware feedback.
    """
    notes = ""

    if global_ai_notes:
        notes += global_ai_notes

    if assignment_title:
        notes += f"\n\nASSIGNMENT: {assignment_title}"

    if grade_level:
        notes += f"\nGRADE LEVEL: {grade_level}"

    if subject:
        notes += f"\nSUBJECT: {subject}"

    if grading_style:
        notes += f"\nGRADING STYLE: {grading_style}"

    if rubric and rubric.get("categories"):
        rubric_text = "\n\nRUBRIC CATEGORIES:\n"
        for cat in rubric["categories"]:
            name = cat.get("name", "Unknown")
            weight = cat.get("weight", 0)
            desc = cat.get("description", "")
            rubric_text += f"- {name} ({weight}%): {desc}\n"
        notes += rubric_text

    if accommodation_prompt:
        notes += f"\n{accommodation_prompt}"

    if student_history:
        notes += f"\n\nSTUDENT HISTORY:\n{student_history}"

    if class_period:
        notes += f"\nCLASS PERIOD: {class_period}"

    return notes


def grade_written_questions(questions, answers, ai_notes, grade_level, subject,
                            grading_style, ai_model="gpt-4o-mini",
                            token_tracker=None):
    """Grade written questions using the multipass per-question grader.

    Args:
        questions: List of question dicts with type, question, answer (expected), points
        answers: Dict mapping answer_key to student's answer text
        ai_notes: Full AI instruction string (from build_portal_ai_notes)

    Returns list of grade results from grade_per_question.
    """
    from assignment_grader import grade_per_question

    if ai_model.startswith("claude"):
        provider = "anthropic"
    elif ai_model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "openai"

    results = []
    for i, q in enumerate(questions):
        q_type = q.get("type", "multiple_choice")
        if q_type not in WRITTEN_TYPES:
            continue

        # Use the portal answer key format: "{sectionIdx}-{questionIdx}"
        answer_key = q.get("_answer_key", "")
        student_answer = answers.get(answer_key, "")
        if not student_answer:
            student_answer = ""

        try:
            result = grade_per_question(
                question=q.get("question", ""),
                student_answer=student_answer,
                expected_answer=q.get("answer", ""),
                points=q.get("points", 10),
                grade_level=grade_level,
                subject=subject,
                teacher_instructions=ai_notes,
                grading_style=grading_style,
                ai_model=ai_model,
                ai_provider=provider,
                response_type="marker_response",
                section_name=q.get("section_name", ""),
                section_type="written",
                token_tracker=token_tracker,
            )
            results.append(result)
        except Exception as e:
            logger.error("Failed to grade question %d (key=%s): %s", i, answer_key, str(e))
            results.append({
                "grade": {
                    "score": 0,
                    "possible": q.get("points", 10),
                    "quality": "error",
                    "reasoning": "Grading failed — teacher will review manually",
                }
            })

    return results


def _score_to_letter(score):
    """Convert numeric score to letter grade."""
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def build_result_record(student_name, student_id, assignment_title, score,
                        total_possible, period, feedback, breakdown,
                        per_question_scores):
    """Build a result record in the exact format analytics expects.

    This format matches what the folder-based grading produces so Results tab
    and Analytics work without modification.
    """
    percentage = round((score / total_possible * 100) if total_possible > 0 else 0)
    return {
        "student_name": student_name,
        "student_id": student_id,
        "assignment": assignment_title,
        "score": percentage,
        "letter_grade": _score_to_letter(percentage),
        "period": period,
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "email_approval": "pending",
        "filename": "",
        "source": "portal",
        "feedback": feedback,
        "per_question_scores": per_question_scores,
        "breakdown": breakdown,
    }


def run_portal_grading_thread(submission_id, assessment, answers, student_info,
                              teacher_config, teacher_id,
                              supabase_table="student_submissions"):
    """Background thread that runs the full multipass grading pipeline on a portal submission.

    Args:
        submission_id: Supabase ID of the submission record
        assessment: The published assessment/assignment content
        answers: Student's answers dict (keys are "{sIdx}-{qIdx}" format)
        student_info: Dict with student_name, student_id, email
        teacher_config: Dict with global_ai_notes, grade_level, subject, grading_style,
                       rubric, ai_model, period
        teacher_id: Teacher's user ID for results storage
        supabase_table: Which table to update — "submissions" for join-code,
                       "student_submissions" for class-based
    """
    try:
        logger.info("Portal grading started: submission=%s student=%s",
                    submission_id, student_info.get("student_name", ""))

        # Build AI instruction string with all grading factors
        from backend.accommodations import build_accommodation_prompt

        accommodation_prompt = ""
        student_id = student_info.get("student_id", "")
        if student_id:
            try:
                accommodation_prompt = build_accommodation_prompt(student_id, teacher_id)
            except Exception:
                pass

        # Build student history context
        history_context = ""
        try:
            from backend.services.assistant_tools import load_student_history_context
            history_context = load_student_history_context(student_id) or ""
        except Exception:
            try:
                from backend.storage import load_student_history
                history = load_student_history(teacher_id, student_id)
                if history:
                    history_context = str(history)
            except Exception:
                pass

        ai_notes = build_portal_ai_notes(
            global_ai_notes=teacher_config.get("global_ai_notes", ""),
            assignment_title=assessment.get("title", ""),
            grade_level=teacher_config.get("grade_level", ""),
            subject=teacher_config.get("subject", ""),
            grading_style=teacher_config.get("grading_style", "standard"),
            rubric=teacher_config.get("rubric"),
            accommodation_prompt=accommodation_prompt,
            student_history=history_context,
            class_period=teacher_config.get("period", ""),
        )

        # Add rubric prompt if available
        rubric = teacher_config.get("rubric")
        if rubric and rubric.get("categories"):
            from backend.app import format_rubric_for_prompt
            rubric_prompt = format_rubric_for_prompt(rubric)
            if rubric_prompt:
                ai_notes += f"\n{rubric_prompt}"

        # Flatten questions from sections for grading
        all_questions = []
        for sIdx, section in enumerate(assessment.get("sections", [])):
            for qIdx, q in enumerate(section.get("questions", [])):
                q_copy = dict(q)
                q_copy["section_name"] = section.get("name", "")
                q_copy["_answer_key"] = f"{sIdx}-{qIdx}"
                all_questions.append(q_copy)

        # Grade written questions via multipass pipeline
        written_questions = [q for q in all_questions if q.get("type", "multiple_choice") in WRITTEN_TYPES]
        ai_model = teacher_config.get("ai_model", "gpt-4o-mini")

        # Set API keys for this thread
        try:
            from backend.api_keys import set_context_keys, resolve_keys_for_teacher
            keys = resolve_keys_for_teacher(teacher_id)
            if keys:
                set_context_keys(keys)
        except Exception:
            pass

        written_results = grade_written_questions(
            questions=written_questions,
            answers=answers,
            ai_notes=ai_notes,
            grade_level=teacher_config.get("grade_level", ""),
            subject=teacher_config.get("subject", ""),
            grading_style=teacher_config.get("grading_style", "standard"),
            ai_model=ai_model,
        )

        # Calculate scores: combine instant (MC/TF) + written results
        total_score = 0
        total_possible = 0
        per_question_scores = []
        written_idx = 0

        for q in all_questions:
            q_type = q.get("type", "multiple_choice")
            points = q.get("points", 1)
            total_possible += points
            answer_key = q.get("_answer_key", "")
            student_answer = answers.get(answer_key, "")

            if q_type in WRITTEN_TYPES:
                # Use AI grading result
                if written_idx < len(written_results):
                    wr = written_results[written_idx]
                    grade = wr.get("grade", {})
                    earned = grade.get("score", 0)
                    total_score += earned
                    per_question_scores.append({
                        "question": q.get("question", ""),
                        "type": q_type,
                        "points_earned": earned,
                        "points_possible": points,
                        "reasoning": grade.get("reasoning", ""),
                        "quality": grade.get("quality", ""),
                        "student_answer": student_answer,
                    })
                    written_idx += 1
                else:
                    per_question_scores.append({
                        "question": q.get("question", ""),
                        "type": q_type,
                        "points_earned": 0,
                        "points_possible": points,
                        "reasoning": "Grading error",
                        "student_answer": student_answer,
                    })
            else:
                # Instant grading (MC/TF/matching) — re-score deterministically
                correct_answer = q.get("answer", "")
                is_correct = False
                earned = 0

                if q_type == "multiple_choice":
                    ca = correct_answer.upper().strip()[:1] if correct_answer else ""
                    sa = ""
                    if isinstance(student_answer, int):
                        sa = chr(65 + student_answer)
                    elif isinstance(student_answer, str):
                        sa = student_answer.upper().strip()[:1]
                    is_correct = sa == ca
                    earned = points if is_correct else 0

                elif q_type == "true_false":
                    is_correct = str(student_answer).lower() == str(correct_answer).lower()
                    earned = points if is_correct else 0

                elif q_type == "matching":
                    # Matching uses per-term keys: "{sIdx}-{qIdx}-match-{tIdx}"
                    terms = q.get("terms", [])
                    definitions = q.get("definitions", [])
                    correct_matches = q.get("answer", {})
                    total_matches = len(terms)
                    correct_count = 0
                    # Extract sIdx-qIdx from _answer_key
                    base_key = answer_key  # e.g., "0-2"
                    for tIdx in range(total_matches):
                        match_key = f"{base_key}-match-{tIdx}"
                        student_match = answers.get(match_key, "")
                        term = terms[tIdx] if tIdx < len(terms) else ""
                        correct_letter = None
                        if term in correct_matches:
                            correct_def = correct_matches[term]
                            try:
                                def_idx = definitions.index(correct_def)
                                correct_letter = chr(65 + def_idx)
                            except ValueError:
                                pass
                        if correct_letter and student_match.upper() == correct_letter:
                            correct_count += 1
                    earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                    is_correct = correct_count == total_matches

                total_score += earned
                per_question_scores.append({
                    "question": q.get("question", ""),
                    "type": q_type,
                    "points_earned": earned,
                    "points_possible": points,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                })

        # Generate overall feedback via Pass 3
        feedback_text = ""
        breakdown = {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0}
        try:
            from assignment_grader import generate_feedback

            student_responses = []
            for q in all_questions:
                answer_key = q.get("_answer_key", "")
                student_responses.append({
                    "question": q.get("question", ""),
                    "answer": answers.get(answer_key, ""),
                })

            percentage = round((total_score / total_possible * 100) if total_possible > 0 else 0)
            letter = _score_to_letter(percentage)

            feedback_result = generate_feedback(
                question_results=written_results,
                total_score=total_score,
                total_possible=total_possible,
                letter_grade=letter,
                grade_level=teacher_config.get("grade_level", ""),
                subject=teacher_config.get("subject", ""),
                teacher_instructions=ai_notes,
                ai_model=ai_model,
                ai_provider="anthropic" if ai_model.startswith("claude") else "gemini" if ai_model.startswith("gemini") else "openai",
                student_responses=student_responses,
                student_history=history_context,
                grading_style=teacher_config.get("grading_style", "standard"),
            )
            feedback_text = feedback_result.get("feedback", "")
            breakdown = feedback_result.get("rubric_breakdown", breakdown)
        except Exception as e:
            logger.error("Feedback generation failed: %s", str(e))
            feedback_text = "Grading complete. Teacher will review and provide detailed feedback."

        # Build result record in analytics-compatible format
        result_record = build_result_record(
            student_name=student_info.get("student_name", ""),
            student_id=student_info.get("student_id", ""),
            assignment_title=assessment.get("title", ""),
            score=total_score,
            total_possible=total_possible,
            period=teacher_config.get("period", ""),
            feedback=feedback_text,
            breakdown=breakdown,
            per_question_scores=per_question_scores,
        )

        # Save to teacher's results storage (for Results tab + Analytics)
        try:
            from backend.app import load_saved_results, save_results
            results = load_saved_results(teacher_id)
            results.append(result_record)
            save_results(results, teacher_id)
        except Exception as e:
            logger.error("Failed to save result to teacher storage: %s", str(e))

        # Update Supabase submission record with full grading
        # Uses supabase_table param: "submissions" for join-code, "student_submissions" for class-based
        try:
            from backend.supabase_client import get_supabase
            sb = get_supabase()
            if sb and submission_id:
                sb.table(supabase_table).update({
                    "results": {
                        "questions": per_question_scores,
                        "score": total_score,
                        "total_points": total_possible,
                        "percentage": round((total_score / total_possible * 100) if total_possible > 0 else 0),
                        "feedback_summary": feedback_text,
                        "breakdown": breakdown,
                        "grading_source": "multipass",
                    },
                    "score": total_score,
                    "percentage": round((total_score / total_possible * 100) if total_possible > 0 else 0),
                    "status": "graded",
                }).eq("id", submission_id).execute()
        except Exception as e:
            logger.error("Failed to update Supabase submission: %s", str(e))

        # Update student history for writing style tracking
        try:
            from backend.storage import save_student_history, load_student_history
            history = load_student_history(teacher_id, student_info.get("student_id")) or {}
            if not isinstance(history, dict):
                history = {}
            scores = history.get("scores", [])
            scores.append({
                "assignment": assessment.get("title", ""),
                "score": round((total_score / total_possible * 100) if total_possible > 0 else 0),
                "date": datetime.now(timezone.utc).isoformat(),
            })
            history["scores"] = scores[-20:]  # Keep last 20
            save_student_history(teacher_id, student_info.get("student_id"), history)
        except Exception as e:
            logger.error("Failed to update student history: %s", str(e))

        logger.info("AUDIT: Portal grading complete: submission=%s student=%s score=%d/%d",
                    submission_id, student_info.get("student_name", ""), total_score, total_possible)

    except Exception as e:
        logger.error("Portal grading thread failed: %s", str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_portal_grading.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/portal_grading.py tests/test_portal_grading.py
git commit -m "feat: create portal multipass grading service"
```

---

### Task 2: Update submission handlers to spawn background grading

**Files:**
- Modify: `backend/routes/student_portal_routes.py:461-540` — join-code submission handler
- Modify: `backend/routes/student_account_routes.py:729-825` — class-based submission handler

- [ ] **Step 1: Update join-code submission handler**

In `backend/routes/student_portal_routes.py`, the `submit_assessment` function (line 462) currently calls `grade_student_submission(assessment, answers)` at line 501 which runs AI grading for SA/ER questions. We must NOT do this for mixed assignments — instead use a new `grade_instant_only()` that only grades MC/TF/matching deterministically.

**First, add `grade_instant_only` function** after the existing `grade_student_submission` function (around line 720):

```python
def grade_instant_only(assessment, answers):
    """Grade ONLY deterministic questions (MC/TF/matching). Skip AI for written questions.

    Used when the multipass pipeline will handle written questions in a background thread.
    Written questions are marked as 'pending_review' with 0 points (scored later by multipass).
    """
    results = {
        "questions": [],
        "score": 0,
        "total_points": 0,
        "percentage": 0,
        "feedback_summary": ""
    }

    for sIdx, section in enumerate(assessment.get('sections', [])):
        for qIdx, question in enumerate(section.get('questions', [])):
            answer_key = f"{sIdx}-{qIdx}"
            student_answer = answers.get(answer_key)
            q_type = question.get('type', 'multiple_choice')
            points = question.get('points', 1)
            correct_answer = question.get('answer')

            results["total_points"] += points

            question_result = {
                "number": question.get('number', qIdx + 1),
                "question": question.get('question', ''),
                "type": q_type,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "points_possible": points,
                "points_earned": 0,
                "is_correct": False,
                "feedback": ""
            }

            if q_type in ("short_answer", "extended_response", "essay", "written"):
                # Skip — will be graded by multipass pipeline
                question_result["feedback"] = "Pending teacher review"
                question_result["status"] = "pending_review"
                results["questions"].append(question_result)
                continue

            if student_answer is None or student_answer == "":
                question_result["feedback"] = "No answer provided"
                results["questions"].append(question_result)
                continue

            # MC/TF/matching grading — same logic as grade_student_submission
            if q_type == "multiple_choice":
                options = question.get('options', [])
                student_letter = None
                if isinstance(student_answer, int) and student_answer < len(options):
                    student_letter = chr(65 + student_answer)
                elif isinstance(student_answer, str):
                    student_letter = student_answer.upper().strip()
                    if len(student_letter) > 1 and student_letter[1] == ')':
                        student_letter = student_letter[0]
                correct_letter = correct_answer.upper().strip() if correct_answer else ""
                if len(correct_letter) > 1 and correct_letter[1] == ')':
                    correct_letter = correct_letter[0]
                is_correct = student_letter == correct_letter
                question_result["is_correct"] = is_correct
                question_result["points_earned"] = points if is_correct else 0
                question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."

            elif q_type == "true_false":
                is_correct = str(student_answer).lower() == str(correct_answer).lower()
                question_result["is_correct"] = is_correct
                question_result["points_earned"] = points if is_correct else 0
                explanation = question.get('explanation', '')
                question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"

            elif q_type == "matching":
                correct_matches = question.get('answer', {})
                terms = question.get('terms', [])
                definitions = question.get('definitions', [])
                total_matches = len(terms)
                correct_count = 0
                for tIdx in range(total_matches):
                    match_key = f"{sIdx}-{qIdx}-match-{tIdx}"
                    student_match = answers.get(match_key, "")
                    term = terms[tIdx] if tIdx < len(terms) else ""
                    correct_letter = None
                    if term in correct_matches:
                        correct_def = correct_matches[term]
                        try:
                            def_idx = definitions.index(correct_def)
                            correct_letter = chr(65 + def_idx)
                        except ValueError:
                            pass
                    if correct_letter and student_match.upper() == correct_letter:
                        correct_count += 1
                earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                question_result["points_earned"] = earned
                question_result["is_correct"] = correct_count == total_matches
                question_result["feedback"] = f"Got {correct_count}/{total_matches} matches correct."

            results["score"] += question_result["points_earned"]
            results["questions"].append(question_result)

    # Only calculate percentage from instant-graded questions
    instant_possible = sum(q["points_possible"] for q in results["questions"] if q.get("status") != "pending_review")
    results["percentage"] = round((results["score"] / instant_possible * 100) if instant_possible > 0 else 0)

    return results
```

**Then replace lines 499-535** (from `# Grade the assessment` through the response building) with:

```python
        # Determine grading strategy
        assessment = assessment_data.get('assessment', {})
        from backend.services.portal_grading import has_written_questions
        needs_multipass = has_written_questions(assessment)

        if needs_multipass:
            # Mixed assignment: grade MC/TF instantly, queue written for multipass
            results = grade_instant_only(assessment, answers)
        else:
            # MC-only: use existing instant grader (no AI calls needed)
            results = grade_student_submission(assessment, answers)

        # Insert submission
        # For partial grading: store only instant scores, mark as provisional
        # so downstream consumers (analytics, teacher view) don't treat incomplete data as final
        submission_row = {
            "assessment_id": assessment_data.get('id'),
            "join_code": code,
            "student_name": student_name,
            "answers": answers,
            "results": results,
            "time_taken_seconds": time_taken_seconds,
            "graded_at": datetime.now().isoformat(),
        }
        if needs_multipass:
            # Don't write top-level score/percentage — they're incomplete
            # The background grading thread will update these when done
            submission_row["score"] = None
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = None
            submission_row["grading_status"] = "partial"
        else:
            submission_row["score"] = results.get('score')
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = results.get('percentage')

        submission_result = db.table('submissions').insert(submission_row).execute()

        if not submission_result.data:
            return jsonify({"error": "Failed to save submission"}), 500

        submission_id = submission_result.data[0].get('id')

        # Check if multipass grading is needed for written questions
        from backend.services.portal_grading import has_written_questions, run_portal_grading_thread
        if has_written_questions(assessment):
            teacher_id = assessment_data.get("teacher_id") or ""
            teacher_config = {
                "global_ai_notes": "",
                "grade_level": "",
                "subject": "",
                "grading_style": "standard",
                "rubric": None,
                "ai_model": "gpt-4o-mini",
                "period": "",
            }
            try:
                from backend.storage import load as storage_load
                settings = storage_load("settings", teacher_id)
                if settings:
                    teacher_config["global_ai_notes"] = settings.get("global_ai_notes", "")
                    teacher_config["grade_level"] = settings.get("grade_level", "")
                    teacher_config["subject"] = settings.get("subject", "")
                rubric_data = storage_load("rubric", teacher_id)
                if rubric_data:
                    teacher_config["rubric"] = rubric_data
                    teacher_config["grading_style"] = rubric_data.get("gradingStyle", "standard")
            except Exception:
                pass

            import threading
            from backend.services.portal_grading import run_portal_grading_thread
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    answers,
                    {"student_name": student_name, "student_id": "", "email": ""},
                    teacher_config,
                    teacher_id,
                    "submissions",  # Join-code submissions use "submissions" table
                ),
                daemon=True,
            )
            thread.start()

            # Mark results as partially graded for frontend
            results["grading_status"] = "partial"
            results["message"] = "Multiple choice and true/false graded. Written responses pending teacher review."

        # Prepare response based on settings
        response = {
            "success": True,
            "submission_id": submission_id,
            "student_name": student_name,
        }

        if results.get("grading_status") == "partial":
            # Mixed assignment: show MC scores but not percentage
            mc_correct = sum(1 for q in (results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("short_answer", "extended_response", "essay", "written"))
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = results["message"]
            if settings.get('show_correct_answers', True):
                # Only show MC/TF results, not written
                response["detailed_results"] = [q for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            # MC-only: show full results
            if settings.get('show_score_immediately', True):
                response["score"] = results.get('score')
                response["total_points"] = results.get('total_points')
                response["percentage"] = results.get('percentage')
                response["feedback_summary"] = results.get('feedback_summary')
            if settings.get('show_correct_answers', True):
                response["detailed_results"] = results.get('questions')

        return jsonify(response)
```

- [ ] **Step 2: Update class-based submission handler**

In `backend/routes/student_account_routes.py`, the `submit_student_work` function (line 730) inserts into `student_submissions` at line 760 but does NOT call any grading function. Clever students get zero feedback. Fix this by:
1. Import `grade_instant_only` from `student_portal_routes.py`
2. Grade MC/TF/matching instantly on submission
3. Write partial results into the submission record
4. Spawn multipass thread for written questions

**Replace lines 754-822** (from `existing = db.table...` through the old `return jsonify` response) with this single consolidated block that handles instant grading, submission insert, multipass thread, and response — all in one scope so variables are shared correctly:

```python
        existing = db.table('student_submissions').select('id').eq(
            'student_id', student_id
        ).eq('content_id', content_id).execute()

        attempt = len(existing.data) + 1

        # Load published content to get assessment data for grading
        pc = db.table('published_content').select('content, title, teacher_id').eq(
            'id', content_id).execute()
        if not pc.data:
            return jsonify({"error": "Published content not found"}), 404

        assessment_content = pc.data[0].get('content', {})
        content_title = pc.data[0].get('title', 'Assignment')
        teacher_id = pc.data[0].get('teacher_id', s.get('teacher_id', ''))

        # Grade instant questions (MC/TF/matching) immediately
        from backend.services.portal_grading import has_written_questions, run_portal_grading_thread
        from backend.routes.student_portal_routes import grade_instant_only, grade_student_submission
        needs_multipass = has_written_questions(assessment_content)

        if needs_multipass:
            instant_results = grade_instant_only(assessment_content, answers)
        else:
            instant_results = grade_student_submission(assessment_content, answers)

        # Build submission row with instant grading results
        submission_row = {
            'student_id': student_id,
            'content_id': content_id,
            'student_name': student_name,
            'student_id_number': s['student_id_number'],
            'period': s.get('period', ''),
            'answers': answers,
            'results': instant_results,
            'time_taken_seconds': time_taken,
            'attempt_number': attempt,
        }

        if needs_multipass:
            submission_row['status'] = 'partial'
            submission_row['score'] = None
            submission_row['percentage'] = None
            submission_row['grading_status'] = 'partial'
        else:
            submission_row['status'] = 'graded'
            submission_row['score'] = instant_results.get('score')
            submission_row['percentage'] = instant_results.get('percentage')
            submission_row['total_points'] = instant_results.get('total_points')

        result = db.table('student_submissions').insert(submission_row).execute()

        if not result.data:
            return jsonify({"error": "Failed to submit"}), 500

        submission_id = result.data[0]['id']

        # Spawn multipass grading thread for written questions
        if needs_multipass:
            teacher_config = {
                "global_ai_notes": "",
                "grade_level": "",
                "subject": "",
                "grading_style": "standard",
                "rubric": None,
                "ai_model": "gpt-4o-mini",
                "period": s.get("period", ""),
            }
            try:
                from backend.storage import load as storage_load
                settings = storage_load("settings", teacher_id)
                if settings:
                    teacher_config["global_ai_notes"] = settings.get("global_ai_notes", "")
                    teacher_config["grade_level"] = settings.get("grade_level", "")
                    teacher_config["subject"] = settings.get("subject", "")
                rubric_data = storage_load("rubric", teacher_id)
                if rubric_data:
                    teacher_config["rubric"] = rubric_data
                    teacher_config["grading_style"] = rubric_data.get("gradingStyle", "standard")
            except Exception:
                pass

            try:
                import threading
                grading_thread = threading.Thread(
                    target=run_portal_grading_thread,
                    args=(
                        submission_id,
                        assessment_content,
                        answers,
                        {
                            "student_name": student_name,
                            "student_id": s.get("student_id_number", ""),
                            "email": s.get("email", ""),
                        },
                        teacher_config,
                        teacher_id,
                        "student_submissions",  # Clever/class-based uses student_submissions table
                    ),
                    daemon=True,
                )
                grading_thread.start()
            except Exception as grading_err:
                _logger.warning("Failed to spawn portal grading: %s", str(grading_err))

        # Queue confirmation email (keep existing logic — move it here)
        student_email = s.get('email')
        if student_email and teacher_id:
            try:
                missing = []
                all_content = db.table('published_content').select('id, title').eq(
                    'class_id', class_id).eq('is_active', True).execute()
                if all_content.data:
                    all_content_ids = [c['id'] for c in all_content.data]
                    student_subs = db.table('student_submissions').select(
                        'content_id'
                    ).eq('student_id', student_id).in_(
                        'content_id', all_content_ids
                    ).execute()
                    submitted_ids = {sub['content_id'] for sub in student_subs.data}
                    missing = [
                        c['title'] for c in all_content.data
                        if c['id'] not in submitted_ids and c['id'] != content_id
                    ]

                now_ts = datetime.now(tz=timezone.utc).isoformat()
                db.table('submission_confirmations').insert({
                    'submission_id': submission_id,
                    'teacher_id': teacher_id,
                    'student_email': student_email,
                    'student_name': student_name,
                    'assignment_title': content_title,
                    'attempt_number': attempt,
                    'missing_assignments': missing,
                    'submitted_at': now_ts,
                    'status': 'pending',
                }).execute()
            except Exception as conf_err:
                _logger.debug("Confirmation queue insert skipped: %s", conf_err)

        # Return instant results to Clever student (MC scores immediately)
        response = {
            "success": True,
            "submission_id": submission_id,
        }
        if needs_multipass:
            mc_correct = sum(1 for q in (instant_results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (instant_results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (instant_results.get("questions") or []) if q.get("status") == "pending_review")
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = "Multiple choice graded. Written responses pending teacher review."
        else:
            response["message"] = "Submitted and graded successfully!"
            response["score"] = instant_results.get("score")
            response["percentage"] = instant_results.get("percentage")

        return jsonify(response)
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever" -q`
Expected: All pass

- [ ] **Step 4: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Success

- [ ] **Step 5: Commit**

```bash
git add backend/routes/student_portal_routes.py backend/routes/student_account_routes.py
git commit -m "feat: spawn multipass grading thread for portal submissions with written questions"
```

---

### Task 2B: Fix teacher regrade endpoint to use multipass

**Files:**
- Modify: `backend/routes/student_account_routes.py:438-547` — `grade_portal_submission` function

The current `grade_portal_submission()` is the teacher-triggered regrade endpoint. It uses sequential `str(i)` keys and different field names (`question_type` instead of `type`). It will overwrite multipass results if called.

- [ ] **Step 1: Update `grade_portal_submission` to spawn multipass thread**

Replace the grading logic in `grade_portal_submission()` (lines 472-533) to:
1. Use `grade_instant_only()` for MC/TF/matching
2. Spawn multipass thread for written questions (same as submission handlers)
3. Return partial results immediately, let multipass complete in background

```python
        assessment = content.data[0]['content']
        student_answers = submission.get('answers', {})

        # Use the portal grading service for consistent grading
        from backend.services.portal_grading import has_written_questions, run_portal_grading_thread
        from backend.routes.student_portal_routes import grade_instant_only, grade_student_submission

        needs_multipass = has_written_questions(assessment)

        if needs_multipass:
            instant_results = grade_instant_only(assessment, student_answers)
        else:
            instant_results = grade_student_submission(assessment, student_answers)

        # Update submission with instant results
        update_data = {
            'results': instant_results,
            'status': 'partial' if needs_multipass else 'graded',
            'graded_at': datetime.now(tz=timezone.utc).isoformat(),
        }
        if not needs_multipass:
            update_data['score'] = instant_results.get('score')
            update_data['total_points'] = instant_results.get('total_points')
            update_data['percentage'] = instant_results.get('percentage')

        db.table('student_submissions').update(update_data).eq('id', submission_id).execute()

        # Spawn multipass for written questions
        if needs_multipass:
            student_name = submission.get('student_name', '')
            student_id_number = submission.get('student_id_number', '')

            teacher_config = {
                "global_ai_notes": "",
                "grade_level": "",
                "subject": "",
                "grading_style": "standard",
                "rubric": None,
                "ai_model": "gpt-4o-mini",
                "period": submission.get('period', ''),
            }
            try:
                from backend.storage import load as storage_load
                settings = storage_load("settings", teacher_id)
                if settings:
                    teacher_config["global_ai_notes"] = settings.get("global_ai_notes", "")
                    teacher_config["grade_level"] = settings.get("grade_level", "")
                    teacher_config["subject"] = settings.get("subject", "")
                rubric_data = storage_load("rubric", teacher_id)
                if rubric_data:
                    teacher_config["rubric"] = rubric_data
                    teacher_config["grading_style"] = rubric_data.get("gradingStyle", "standard")
            except Exception:
                pass

            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    student_answers,
                    {"student_name": student_name, "student_id": student_id_number, "email": ""},
                    teacher_config,
                    teacher_id,
                    "student_submissions",
                ),
                daemon=True,
            )
            thread.start()

        needs_review = sum(1 for q in instant_results.get('questions', []) if q.get('status') == 'pending_review')
        percentage = instant_results.get('percentage', 0)

        return jsonify({
            "success": True,
            "score": instant_results.get('score', 0),
            "total_points": instant_results.get('total_points', 0),
            "percentage": percentage,
            "results": instant_results.get('questions', []),
            "needs_review": needs_review,
            "grading_status": "partial" if needs_multipass else "complete",
        })
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever" -q`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_account_routes.py
git commit -m "feat: teacher regrade endpoint uses multipass pipeline for written questions"
```

---

### Task 3: Update student portal frontend to show partial results

**Files:**
- Modify: `frontend/src/components/StudentPortal.jsx:125-151` — submission response handling
- Modify: `frontend/src/components/StudentPortal.jsx:573-645` — results display

- [ ] **Step 1: Update submission response handling**

In `StudentPortal.jsx`, **replace lines 137-145** (the `else` block after successful submission) with code that handles both full and partial results:

```javascript
      } else {
        if (data.grading_status === "partial") {
          setResults({
            grading_status: "partial",
            mc_correct: data.mc_correct,
            mc_total: data.mc_total,
            written_pending: data.written_pending,
            message: data.message,
            questions: data.detailed_results,
          });
        } else {
          setResults({
            score: data.score,
            total_points: data.total_points,
            percentage: data.percentage,
            feedback_summary: data.feedback_summary,
            questions: data.detailed_results,
          });
        }
        setStage("results");
      }
```

- [ ] **Step 2: Update results display for partial grading**

In `StudentPortal.jsx`, **replace lines 573-615** (the results stage rendering, from `if (stage === "results")` through the feedback summary closing `</div>`) with:

```jsx
  if (stage === "results") {
    var isPartial = results && results.grading_status === "partial";
    var percentage = results?.percentage || 0;
    var gradeColor = percentage >= 90 ? "#22c55e" : percentage >= 70 ? "#f59e0b" : "#ef4444";

    return (
      <div style={containerStyle}>
        <div style={{ padding: "40px 20px", maxWidth: "700px", margin: "0 auto" }}>
          {/* Score Card */}
          <div style={{ ...cardStyle, textAlign: "center", marginBottom: "30px" }}>
            <Icon name={isPartial ? "Clock" : "Award"} size={50} />
            <h2 style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
              {isPartial ? "Submitted!" : "Assessment Complete!"}
            </h2>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "25px" }}>{studentName}</p>

            {isPartial ? (
              <div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#6366f1", marginBottom: "10px" }}>
                  {results.mc_correct}/{results.mc_total} multiple choice correct
                </div>
                <div style={{
                  padding: "12px 16px", borderRadius: "10px",
                  background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.3)",
                  color: "#f59e0b", fontSize: "0.95rem", marginTop: "15px",
                }}>
                  <Icon name="Clock" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                  {results.written_pending} written response{results.written_pending !== 1 ? "s" : ""} pending teacher review
                </div>
                <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.85rem", marginTop: "12px" }}>
                  Your teacher will review your written responses and you'll see your full score soon.
                </p>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: "4rem", fontWeight: 800, color: gradeColor, marginBottom: "10px" }}>
                  {percentage}%
                </div>
                <div style={{ fontSize: "1.2rem", color: "rgba(255,255,255,0.7)" }}>
                  {results?.score}/{results?.total_points} points
                </div>
                {results?.feedback_summary && (
                  <div style={{
                    marginTop: "25px", padding: "15px",
                    background: "rgba(255,255,255,0.05)", borderRadius: "10px", fontStyle: "italic",
                  }}>
                    {results.feedback_summary}
                  </div>
                )}
              </div>
            )}
          </div>
```

The rest of the results display (Question Review section, lines 617+) stays unchanged — it will show MC/TF questions for partial results since those are the only ones passed in `detailed_results`.

- [ ] **Step 3: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Success

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StudentPortal.jsx
git commit -m "feat: show partial results for mixed MC/written assignments"
```

---

### Task 4: Fix district report export to read from results storage

**Files:**
- Modify: `backend/routes/analytics_routes.py:548-611` — `export_district_report` function

- [ ] **Step 1: Replace the data loading section**

In `backend/routes/analytics_routes.py`, the `export_district_report` function (line 548) currently reads settings from a local file (line 563-572) and grades from `master_grades.csv` (line 574-608).

**Replace lines 555-611** (from `# Get output folder` through `if not all_grades:`) with:

```python
    from flask import g

    teacher_id = getattr(g, 'user_id', 'local-dev')

    # Get teacher info from settings
    teacher_name = "Unknown Teacher"
    school_name = "Unknown School"
    subject = "Social Studies"

    # Try storage-based settings first (works for Clever/portal users)
    try:
        from backend.storage import load as storage_load
        settings = storage_load("settings", teacher_id)
        if settings:
            teacher_name = settings.get("teacher_name", teacher_name)
            school_name = settings.get("school_name", school_name)
            subject = settings.get("subject", subject)
    except Exception:
        pass

    # Fallback to local file settings
    if teacher_name == "Unknown Teacher":
        settings_file = os.path.expanduser("~/.graider_global_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    file_settings = json.load(f)
                    teacher_name = file_settings.get('teacher_name', teacher_name)
                    school_name = file_settings.get('school_name', school_name)
                    subject = file_settings.get('subject', subject)
            except Exception:
                pass

    # Collect anonymized aggregate data
    all_grades = []
    students = set()
    assignments = defaultdict(list)
    quarters = defaultdict(list)
    categories = {"content": [], "completeness": [], "writing": [], "effort": []}

    # Try results storage first (includes portal + file-based results)
    try:
        from backend.storage import load as storage_load
        results = storage_load("results", teacher_id)
        if results and isinstance(results, list):
            for r in results:
                score = int(r.get("score", 0) or 0)
                all_grades.append(score)
                students.add(r.get("student_id", r.get("student_name", "unknown")))
                assignment_name = r.get("assignment", "Unknown")
                assignments[assignment_name].append(score)
                quarter = r.get("period", "")
                if quarter:
                    quarters[quarter].append(score)
                bd = r.get("breakdown", {})
                categories["content"].append(int(bd.get("content_accuracy", 0) or 0))
                categories["completeness"].append(int(bd.get("completeness", 0) or 0))
                categories["writing"].append(int(bd.get("writing_quality", 0) or 0))
                categories["effort"].append(int(bd.get("effort_engagement", 0) or 0))
    except Exception:
        pass

    # Fall back to master_grades.csv if no results in storage
    if not all_grades:
        master_file = _find_master_grades()
        if not master_file:
            return jsonify({"error": "No grading data available to export"})

        try:
            with open(master_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    score = int(float(row.get("Overall Score", 0) or 0))
                    all_grades.append(score)
                    students.add(row.get("Student ID", row.get("Student Name", "unknown")))
                    assignment_name = row.get("Assignment", "Unknown")
                    assignments[assignment_name].append(score)
                    quarter = row.get("Quarter", "")
                    if quarter:
                        quarters[quarter].append(score)
                    categories["content"].append(int(float(row.get("Content Accuracy", 0) or 0)))
                    categories["completeness"].append(int(float(row.get("Completeness", 0) or 0)))
                    categories["writing"].append(int(float(row.get("Writing Quality", 0) or 0)))
                    categories["effort"].append(int(float(row.get("Effort Engagement", 0) or 0)))
        except Exception as e:
            _logger.exception("Error reading grades")
            return jsonify({"error": "An internal error occurred"}), 500

    if not all_grades:
        return jsonify({"error": "No grades found in data"})
```

The rest of the function (grade distribution calculation, assignment stats, category averages, response building — lines 613+) stays unchanged since it reads from the same `all_grades`, `students`, `assignments`, `quarters`, `categories` variables.

- [ ] **Step 2: Verify backend imports**

Run: `cd /Users/alexc/Downloads/Graider/backend && source ../venv/bin/activate && python -c "from app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever or portal" -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/routes/analytics_routes.py
git commit -m "feat: district report export reads from results storage (supports portal data)"
```

---

### Task 5: Full end-to-end verification

- [ ] **Step 1: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever or portal" -v`
Expected: All pass

- [ ] **Step 2: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Clean build

- [ ] **Step 3: Verify backend imports**

Run: `cd /Users/alexc/Downloads/Graider/backend && source ../venv/bin/activate && python -c "from app import app; from services.portal_grading import has_written_questions; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Manual test flow**

1. Create an assignment in Planner with mixed MC + short answer questions
2. Publish to class
3. Log in as student at `/student`
4. Complete and submit
5. Verify: MC scores shown immediately, written shows "pending review"
6. Check teacher's Results tab — submission should appear with "pending" approval
7. Check Analytics — student should appear with scores
8. Approve in Results tab — verify student can see full results

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: portal multipass grading — full 18-factor pipeline for student submissions"
```
