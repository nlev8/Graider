"""Assessment grading + regeneration logic for the planner.

Wave 6 Slice 5 - extracted from backend/routes/planner_routes.py
(behavior-preserving). Flask-free: the route reads request data and passes
assessment + answers in; this builds the per-question results (deterministic
grading for MC/true_false/matching; OpenAI grading for open-ended) and returns
the {results, usage} dict. No service->route imports.
"""
import json
import logging

from backend.services.assignment_post_processing import _extract_usage, _record_planner_cost

_logger = logging.getLogger(__name__)


def grade_assessment_answers_logic(assessment, answers):
    """Grade student answers against the assessment; return {results, usage}.

    Deterministic for multiple_choice/true_false/matching; calls OpenAIAdapter
    (env key) for short_answer/extended_response. usage is None when no AI ran.
    """
    results = {
        "questions": [],
        "score": 0,
        "total_points": 0,
        "percentage": 0,
        "feedback_summary": ""
    }

    # Collect questions that need AI grading (short answer, extended response)
    ai_grading_needed = []

    # Process each section and question
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

            if student_answer is None or student_answer == "":
                question_result["feedback"] = "No answer provided"
                results["questions"].append(question_result)
                continue

            # Grade based on question type
            if q_type == "multiple_choice":
                # Check if answer matches (handle both index and letter formats)
                options = question.get('options', [])
                student_letter = None
                if isinstance(student_answer, int) and student_answer < len(options):
                    student_letter = chr(65 + student_answer)  # Convert index to letter
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
                question_result["student_answer"] = f"{student_letter}) {options[ord(student_letter) - 65] if student_letter and ord(student_letter) - 65 < len(options) else student_answer}" if student_letter else student_answer
                question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."

            elif q_type == "true_false":
                is_correct = str(student_answer).lower() == str(correct_answer).lower()
                question_result["is_correct"] = is_correct
                question_result["points_earned"] = points if is_correct else 0
                explanation = question.get('explanation', '')
                question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"

            elif q_type == "matching":
                # Check matching answers
                correct_matches = question.get('answer', {})
                terms = question.get('terms', [])
                total_matches = len(terms)
                correct_count = 0

                match_details = []
                for tIdx in range(total_matches):
                    match_key = f"{sIdx}-{qIdx}-match-{tIdx}"
                    student_match = answers.get(match_key, "")
                    term = terms[tIdx] if tIdx < len(terms) else f"Term {tIdx + 1}"

                    # Find correct letter for this term
                    correct_letter = None
                    definitions = question.get('definitions', [])
                    if term in correct_matches:
                        correct_def = correct_matches[term]
                        try:
                            def_idx = definitions.index(correct_def)
                            correct_letter = chr(65 + def_idx)
                        except ValueError:
                            correct_letter = None

                    is_match_correct = student_match.upper() == correct_letter if correct_letter else False
                    if is_match_correct:
                        correct_count += 1
                    match_details.append({
                        "term": term,
                        "student": student_match,
                        "correct": correct_letter,
                        "is_correct": is_match_correct
                    })

                # Partial credit
                earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                question_result["points_earned"] = earned
                question_result["is_correct"] = correct_count == total_matches
                question_result["match_details"] = match_details
                question_result["feedback"] = f"Got {correct_count}/{total_matches} matches correct."

            elif q_type in ["short_answer", "extended_response"]:
                # Queue for AI grading
                ai_grading_needed.append({
                    "index": len(results["questions"]),
                    "question": question,
                    "student_answer": student_answer,
                    "result": question_result
                })

            results["questions"].append(question_result)

    # AI grading for open-ended questions
    grading_usage = {"model": "gpt-4o-mini", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0}
    if ai_grading_needed:
        try:
            from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
            _grade_adapter = OpenAIAdapter()

            for item in ai_grading_needed:
                q = item["question"]
                student_ans = item["student_answer"]
                q_result = item["result"]
                points = q.get('points', 1)

                grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
Question Type: {q.get('type', 'short_answer')}
Points Possible: {points}
Correct/Model Answer: {q.get('answer', 'N/A')}
Rubric: {q.get('rubric', 'N/A')}
DOK Level: {q.get('dok', 'N/A')}
Standard: {q.get('standard', 'N/A')}

Student's Answer: {student_ans}

Evaluate the student's response and provide:
1. Points earned (0 to {points})
2. Brief feedback (2-3 sentences)
3. Whether the answer demonstrates understanding

Respond in JSON format:
{{"points_earned": <number>, "feedback": "<string>", "is_correct": <boolean>}}"""

                response = _grade_adapter.chat(LLMRequest(
                    model="gpt-4o-mini",
                    system_prompt="You are a fair and helpful teacher grading student work. Be encouraging but accurate. Provide constructive feedback.",
                    messages=[Message(role="user", content=[TextPart(text=grading_prompt)])],
                    response_format=ResponseFormat(type="json_object"),
                    max_tokens=300,
                    metadata={"feature_label": "submit_assessment_ai_grading"},
                ))

                u = _extract_usage(response, "gpt-4o-mini")
                if u:
                    for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                        grading_usage[k] += u[k]

                ai_result = json.loads(response.content_parts[0].text if response.content_parts else "{}")
                q_result["points_earned"] = min(ai_result.get("points_earned", 0), points)
                q_result["feedback"] = ai_result.get("feedback", "")
                q_result["is_correct"] = ai_result.get("is_correct", False)

                # Update in results
                results["questions"][item["index"]] = q_result

        except Exception as e:
            _logger.exception("AI grading error")
            # Fall back to basic comparison for failed AI grading
            for item in ai_grading_needed:
                q_result = item["result"]
                q_result["feedback"] = "Answer recorded. Manual review recommended."
                q_result["points_earned"] = 0
                results["questions"][item["index"]] = q_result

    # Calculate final score
    results["score"] = sum(q["points_earned"] for q in results["questions"])
    results["percentage"] = round((results["score"] / results["total_points"]) * 100) if results["total_points"] > 0 else 0

    # Generate summary feedback
    correct_count = sum(1 for q in results["questions"] if q["is_correct"])
    total_questions = len(results["questions"])
    results["feedback_summary"] = f"You answered {correct_count} out of {total_questions} questions correctly, earning {results['score']}/{results['total_points']} points ({results['percentage']}%)."

    grading_usage["cost"] = round(grading_usage["cost"], 6)
    grading_usage["cost_display"] = f"${grading_usage['cost']:.4f}"
    _record_planner_cost(grading_usage if grading_usage["total_tokens"] > 0 else None)
    return {"results": results, "usage": grading_usage if grading_usage["total_tokens"] > 0 else None}
