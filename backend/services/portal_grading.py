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

# Import grade_per_question at module level so it can be patched in tests
try:
    from assignment_grader import grade_per_question
except ImportError:
    grade_per_question = None

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

    # Note: rubric categories are appended via format_rubric_for_prompt() in
    # run_portal_grading_thread() — don't duplicate them here.

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

    Returns list of grade results from grade_per_question.
    """
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
            from backend.api_keys import set_thread_keys, resolve_keys_for_teacher
            keys = resolve_keys_for_teacher(teacher_id)
            if keys:
                set_thread_keys(keys)
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
        # Use per-teacher lock to prevent race conditions with concurrent submissions
        try:
            from backend.app import load_saved_results, save_results, _get_lock
            with _get_lock(teacher_id):
                results = load_saved_results(teacher_id)
                results.append(result_record)
                save_results(results, teacher_id)
        except Exception as e:
            logger.error("Failed to save result to teacher storage: %s", str(e))

        # Update Supabase submission record with full grading
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
