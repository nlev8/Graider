"""
Shared grading utilities for Graider.

Contains helper functions used by multiple grading paths
(join-code, class-based, teacher regrade).
"""
import json
import logging
import sentry_sdk

logger = logging.getLogger(__name__)


def _build_standards_mastery(question_results):
    """Roll up per-question scores into a standards_mastery dict.

    Input: list of question result dicts (each may have a 'standard' key).
    Output: { standard_code: { points_earned, points_possible, question_count } }
    Questions without a 'standard' field are skipped.
    """
    mastery = {}
    for qr in question_results:
        code = qr.get('standard')
        if not code:
            continue
        bucket = mastery.setdefault(code, {
            'points_earned': 0,
            'points_possible': 0,
            'question_count': 0,
        })
        bucket['points_earned'] += qr.get('points_earned') or 0
        bucket['points_possible'] += qr.get('points_possible') or 0
        bucket['question_count'] += 1
    return mastery


def grade_deterministic_question(question, student_answer, answer_key, answers):
    """Grade a single MC/TF/matching question deterministically.

    Returns (points_earned, is_correct, feedback) tuple.
    """
    q_type = question.get('type') or question.get('question_type', 'multiple_choice')
    points = question.get('points', 1)
    correct_answer = question.get('answer')

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
        earned = points if is_correct else 0
        feedback = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."
        return earned, is_correct, feedback

    elif q_type == "true_false":
        is_correct = str(student_answer).lower() == str(correct_answer).lower()
        earned = points if is_correct else 0
        explanation = question.get('explanation', '')
        feedback = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"
        return earned, is_correct, feedback

    elif q_type == "matching":
        correct_matches = question.get('answer', {})
        terms = question.get('terms', [])
        definitions = question.get('definitions', [])
        total_matches = len(terms)
        correct_count = 0
        for tIdx in range(total_matches):
            match_key = f"{answer_key}-match-{tIdx}"
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
        feedback = f"Got {correct_count}/{total_matches} matches correct."
        return earned, is_correct, feedback

    return 0, False, ""


def load_teacher_config(teacher_id):
    """Load teacher's grading configuration from storage.

    Returns a dict with: global_ai_notes, grade_level, subject,
    grading_style, rubric, ai_model, period.

    This pattern was previously duplicated in 3 places:
    - student_portal_routes.py (join-code grading thread)
    - student_account_routes.py (class-based grading thread)
    - student_account_routes.py (teacher regrade)
    """
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
    except Exception as e:
        logger.debug("Failed to load teacher config for %s: %s", teacher_id, e)
        sentry_sdk.capture_exception(e)

    return teacher_config


def grade_student_submission(assessment, answers):
    """
    Grade a student's submission against the assessment.
    Handles all question types with immediate grading.
    """
    results = {
        "questions": [],
        "score": 0,
        "total_points": 0,
        "percentage": 0,
        "feedback_summary": ""
    }

    ai_grading_needed = []

    # Process each section and question
    for sIdx, section in enumerate(assessment.get('sections', [])):
        for qIdx, question in enumerate(section.get('questions', [])):
            answer_key = f"{sIdx}-{qIdx}"
            student_answer = answers.get(answer_key)
            q_type = question.get('type') or question.get('question_type', 'multiple_choice')
            points = question.get('points', 1)
            correct_answer = question.get('answer')

            results["total_points"] += points

            question_result = {
                "number": question.get('number', qIdx + 1),
                "question": question.get('question', ''),
                "type": q_type,
                "standard": question.get('standard'),
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "points_possible": points,
                "points_earned": 0,
                "is_correct": False,
                "feedback": "",
                "dok": question.get("dok"),
            }

            # For matching questions, check match-specific keys instead of base key
            has_match_keys = q_type == "matching" and any(
                k.startswith(f"{answer_key}-match-") for k in answers
            )

            if (student_answer is None or student_answer == "") and not has_match_keys:
                question_result["feedback"] = "No answer provided"
                results["questions"].append(question_result)
                continue

            # Grade based on question type
            if q_type in ["short_answer", "extended_response"]:
                ai_grading_needed.append({
                    "index": len(results["questions"]),
                    "question": question,
                    "student_answer": student_answer,
                    "result": question_result
                })
            else:
                # MC/TF/matching grading via shared deterministic grader
                earned, is_correct, feedback = grade_deterministic_question(
                    question, student_answer, answer_key, answers
                )
                question_result["points_earned"] = earned
                question_result["is_correct"] = is_correct
                question_result["feedback"] = feedback

            results["questions"].append(question_result)

    # AI grading for open-ended questions
    if ai_grading_needed:
        try:
            from backend.services.llm_adapter import (
                LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart,
            )
            adapter = OpenAIAdapter()

            for item in ai_grading_needed:
                q = item["question"]
                student_ans = item["student_answer"]
                q_result = item["result"]
                points = q.get('points', 1)

                grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
Question Type: {q.get('type') or q.get('question_type', 'short_answer')}
Points Possible: {points}
Correct/Model Answer: {q.get('answer', 'N/A')}
Rubric: {q.get('rubric', 'N/A')}

Student's Answer: {student_ans}

Evaluate the student's response and provide:
1. Points earned (0 to {points})
2. Brief, encouraging feedback (2-3 sentences)
3. Whether the answer demonstrates understanding

Respond in JSON format:
{{"points_earned": <number>, "feedback": "<string>", "is_correct": <boolean>}}"""

                resp = adapter.chat(LLMRequest(
                    model="gpt-4o-mini",
                    system_prompt="You are a fair and encouraging teacher grading student work. Be supportive but accurate. Provide constructive feedback that helps students learn.",
                    messages=[Message(role="user", content=[TextPart(text=grading_prompt)])],
                    response_format=ResponseFormat(type="json_object"),
                    max_tokens=300,
                    metadata={"feature_label": "portal_ai_grading"},
                ))

                ai_result = json.loads(resp.content_parts[0].text if resp.content_parts else "{}")
                q_result["points_earned"] = min(ai_result.get("points_earned", 0), points)
                q_result["feedback"] = ai_result.get("feedback", "")
                q_result["is_correct"] = ai_result.get("is_correct", False)

                results["questions"][item["index"]] = q_result

        except Exception as e:
            logger.error("AI grading error: %s", str(e))
            for item in ai_grading_needed:
                q_result = item["result"]
                q_result["feedback"] = "Answer recorded. Your teacher will review this response."
                q_result["points_earned"] = 0
                results["questions"][item["index"]] = q_result

    # Calculate final score
    results["score"] = sum(q["points_earned"] for q in results["questions"])
    results["percentage"] = round((results["score"] / results["total_points"]) * 100) if results["total_points"] > 0 else 0

    # Generate summary feedback
    correct_count = sum(1 for q in results["questions"] if q["is_correct"])
    total_questions = len(results["questions"])

    if results["percentage"] >= 90:
        grade_comment = "Excellent work!"
    elif results["percentage"] >= 80:
        grade_comment = "Great job!"
    elif results["percentage"] >= 70:
        grade_comment = "Good effort!"
    elif results["percentage"] >= 60:
        grade_comment = "Keep practicing!"
    else:
        grade_comment = "Don't give up - review the material and try again!"

    results["feedback_summary"] = f"{grade_comment} You scored {results['score']}/{results['total_points']} points ({results['percentage']}%), answering {correct_count} out of {total_questions} questions correctly."

    results['standards_mastery'] = _build_standards_mastery(results.get('questions', []))

    return results


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
            q_type = question.get('type') or question.get('question_type', 'multiple_choice')
            points = question.get('points', 1)
            correct_answer = question.get('answer')

            results["total_points"] += points

            question_result = {
                "number": question.get('number', qIdx + 1),
                "question": question.get('question', ''),
                "type": q_type,
                "standard": question.get('standard'),
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "points_possible": points,
                "points_earned": 0,
                "is_correct": False,
                "feedback": "",
                "dok": question.get("dok"),
            }

            if q_type in ("short_answer", "extended_response", "essay", "written"):
                # Skip — will be graded by multipass pipeline
                question_result["feedback"] = "Pending teacher review"
                question_result["status"] = "pending_review"
                results["questions"].append(question_result)
                continue

            # For matching questions, check match-specific keys instead of base key
            has_match_keys = q_type == "matching" and any(
                k.startswith(f"{answer_key}-match-") for k in answers
            )

            if (student_answer is None or student_answer == "") and not has_match_keys:
                question_result["feedback"] = "No answer provided"
                results["questions"].append(question_result)
                continue

            # MC/TF/matching grading via shared deterministic grader
            earned, is_correct, feedback = grade_deterministic_question(
                question, student_answer, answer_key, answers
            )
            question_result["points_earned"] = earned
            question_result["is_correct"] = is_correct
            question_result["feedback"] = feedback

            results["score"] += question_result["points_earned"]
            results["questions"].append(question_result)

    # Only calculate percentage from instant-graded questions
    instant_possible = sum(q["points_possible"] for q in results["questions"] if q.get("status") != "pending_review")
    results["percentage"] = round((results["score"] / instant_possible * 100) if instant_possible > 0 else 0)

    results['standards_mastery'] = _build_standards_mastery(results.get('questions', []))

    return results
