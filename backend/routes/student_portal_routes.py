"""
Student Assessment Portal Routes for Graider.
Handles publishing assessments, student access via join codes, and submission grading.
Uses Supabase for cloud storage - students can submit anytime.
"""
import json
import os
import random
import string
from datetime import datetime
from flask import Blueprint, request, jsonify
from supabase import create_client, Client

student_portal_bp = Blueprint('student_portal', __name__)

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for full access

supabase: Client = None

def get_supabase() -> Client:
    """Get or create Supabase client."""
    global supabase
    if supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Supabase credentials not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        supabase = create_client(url, key)
    return supabase


def generate_join_code():
    """Generate a unique 6-character join code (e.g., 'ABC123')."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        # Check if code already exists
        db = get_supabase()
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


# ============ Teacher Endpoints ============

@student_portal_bp.route('/api/publish-assessment', methods=['POST'])
def publish_assessment():
    """
    Publish an assessment for students to take.
    Returns a unique join code and shareable link.
    """
    try:
        db = get_supabase()
        data = request.json
        assessment = data.get('assessment')
        settings = data.get('settings', {})

        if not assessment:
            return jsonify({"error": "No assessment provided"}), 400

        # Generate unique join code
        join_code = generate_join_code()

        # Prepare settings
        db_settings = {
            "time_limit_minutes": settings.get('time_limit_minutes'),
            "allow_multiple_attempts": settings.get('allow_multiple_attempts', False),
            "show_correct_answers": settings.get('show_correct_answers', True),
            "show_score_immediately": settings.get('show_score_immediately', True),
            "require_name": settings.get('require_name', True),
        }

        # Insert into Supabase
        result = db.table('published_assessments').insert({
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }).execute()

        if not result.data:
            return jsonify({"error": "Failed to publish assessment"}), 500

        # Generate shareable link (use request host for development)
        host = request.host_url.rstrip('/')
        join_link = f"{host}/join/{join_code}"

        return jsonify({
            "success": True,
            "join_code": join_code,
            "join_link": join_link,
            "message": f"Assessment published! Students can join with code: {join_code}"
        })

    except Exception as e:
        print(f"Publish assessment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/teacher/assessments', methods=['GET'])
def list_published_assessments():
    """List all published assessments for the teacher."""
    try:
        db = get_supabase()

        result = db.table('published_assessments').select(
            'id, join_code, title, created_at, submission_count, is_active, teacher_name'
        ).order('created_at', desc=True).execute()

        assessments = [{
            "id": a.get('id'),
            "join_code": a.get('join_code'),
            "title": a.get('title'),
            "created_at": a.get('created_at'),
            "submission_count": a.get('submission_count', 0),
            "active": a.get('is_active', True),
        } for a in result.data]

        return jsonify({"assessments": assessments})

    except Exception as e:
        print(f"List assessments error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/results', methods=['GET'])
def get_assessment_results(code):
    """Get all submissions for a published assessment."""
    try:
        db = get_supabase()
        code = code.upper()

        # Get assessment
        assessment_result = db.table('published_assessments').select('*').eq('join_code', code).execute()

        if not assessment_result.data:
            return jsonify({"error": "Assessment not found"}), 404

        assessment_data = assessment_result.data[0]

        # Get submissions
        submissions_result = db.table('submissions').select('*').eq('join_code', code).order('submitted_at', desc=True).execute()

        submissions = [{
            "submission_id": s.get('id'),
            "student_name": s.get('student_name'),
            "score": s.get('score'),
            "total_points": s.get('total_points'),
            "percentage": s.get('percentage'),
            "time_taken_seconds": s.get('time_taken_seconds'),
            "submitted_at": s.get('submitted_at'),
            "results": s.get('results'),
        } for s in submissions_result.data]

        return jsonify({
            "assessment": {
                "title": assessment_data.get('title'),
                "join_code": code,
                "created_at": assessment_data.get('created_at'),
                "is_active": assessment_data.get('is_active'),
            },
            "submissions": submissions,
            "total_submissions": len(submissions),
        })

    except Exception as e:
        print(f"Get results error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/toggle', methods=['POST'])
def toggle_assessment(code):
    """Activate or deactivate a published assessment."""
    try:
        db = get_supabase()
        code = code.upper()

        # Get current status
        result = db.table('published_assessments').select('is_active').eq('join_code', code).execute()

        if not result.data:
            return jsonify({"error": "Assessment not found"}), 404

        current_active = result.data[0].get('is_active', True)
        new_active = not current_active

        # Update
        db.table('published_assessments').update({'is_active': new_active}).eq('join_code', code).execute()

        status = "activated" if new_active else "deactivated"
        return jsonify({
            "success": True,
            "active": new_active,
            "message": f"Assessment {status}"
        })

    except Exception as e:
        print(f"Toggle assessment error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>', methods=['DELETE'])
def delete_published_assessment(code):
    """Delete a published assessment and all its submissions."""
    try:
        db = get_supabase()
        code = code.upper()

        # Delete submissions first (cascade should handle this, but be explicit)
        db.table('submissions').delete().eq('join_code', code).execute()

        # Delete assessment
        result = db.table('published_assessments').delete().eq('join_code', code).execute()

        return jsonify({"success": True, "message": "Assessment deleted"})

    except Exception as e:
        print(f"Delete assessment error: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Student Endpoints ============

@student_portal_bp.route('/api/student/join/<code>', methods=['GET'])
def get_assessment_for_student(code):
    """
    Get assessment details for a student joining with a code.
    Returns assessment without answers for student to take.
    """
    try:
        db = get_supabase()
        code = code.upper()

        result = db.table('published_assessments').select('*').eq('join_code', code).execute()

        if not result.data:
            return jsonify({"error": "Assessment not found. Check your join code."}), 404

        data = result.data[0]

        # Check if assessment is active
        if not data.get('is_active', True):
            return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        assessment = data.get('assessment', {})
        settings = data.get('settings', {})

        # Remove answers from questions before sending to student
        sanitized_sections = []
        for section in assessment.get('sections', []):
            sanitized_questions = []
            for q in section.get('questions', []):
                student_question = {
                    "number": q.get('number'),
                    "question": q.get('question'),
                    "type": q.get('type'),
                    "points": q.get('points'),
                    "options": q.get('options'),
                    "terms": q.get('terms'),
                    "definitions": q.get('definitions'),
                }
                sanitized_questions.append(student_question)

            sanitized_sections.append({
                "name": section.get('name'),
                "instructions": section.get('instructions'),
                "questions": sanitized_questions,
            })

        return jsonify({
            "title": assessment.get('title'),
            "instructions": assessment.get('instructions'),
            "total_points": assessment.get('total_points'),
            "time_estimate": assessment.get('time_estimate'),
            "sections": sanitized_sections,
            "settings": {
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
            },
            "teacher": data.get('teacher_name', 'Teacher'),
        })

    except Exception as e:
        print(f"Get assessment for student error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/student/submit/<code>', methods=['POST'])
def submit_assessment(code):
    """
    Submit student answers for grading.
    Returns immediate feedback and score.
    """
    try:
        db = get_supabase()
        code = code.upper()

        # Get assessment
        assessment_result = db.table('published_assessments').select('*').eq('join_code', code).execute()

        if not assessment_result.data:
            return jsonify({"error": "Assessment not found"}), 404

        assessment_data = assessment_result.data[0]

        # Check if active
        if not assessment_data.get('is_active', True):
            return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        data = request.json
        student_name = data.get('student_name', 'Anonymous')
        answers = data.get('answers', {})
        time_taken_seconds = data.get('time_taken_seconds')

        settings = assessment_data.get('settings', {})

        # Check for duplicate submission
        if not settings.get('allow_multiple_attempts', False):
            existing = db.table('submissions').select('id, results').eq('join_code', code).ilike('student_name', student_name).execute()
            if existing.data:
                return jsonify({
                    "error": "You have already submitted this assessment.",
                    "previous_results": existing.data[0].get('results')
                }), 400

        # Grade the assessment
        assessment = assessment_data.get('assessment', {})
        results = grade_student_submission(assessment, answers)

        # Insert submission
        submission_result = db.table('submissions').insert({
            "assessment_id": assessment_data.get('id'),
            "join_code": code,
            "student_name": student_name,
            "answers": answers,
            "results": results,
            "score": results.get('score'),
            "total_points": results.get('total_points'),
            "percentage": results.get('percentage'),
            "time_taken_seconds": time_taken_seconds,
            "graded_at": datetime.now().isoformat(),
        }).execute()

        if not submission_result.data:
            return jsonify({"error": "Failed to save submission"}), 500

        # Prepare response based on settings
        response = {
            "success": True,
            "submission_id": submission_result.data[0].get('id'),
            "student_name": student_name,
        }

        if settings.get('show_score_immediately', True):
            response["score"] = results.get('score')
            response["total_points"] = results.get('total_points')
            response["percentage"] = results.get('percentage')
            response["feedback_summary"] = results.get('feedback_summary')

        if settings.get('show_correct_answers', True):
            response["detailed_results"] = results.get('questions')

        return jsonify(response)

    except Exception as e:
        print(f"Submit assessment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

                if student_letter and ord(student_letter) - 65 < len(options):
                    question_result["student_answer_display"] = f"{student_letter}) {options[ord(student_letter) - 65]}"

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

                match_details = []
                for tIdx in range(total_matches):
                    match_key = f"{sIdx}-{qIdx}-match-{tIdx}"
                    student_match = answers.get(match_key, "")
                    term = terms[tIdx] if tIdx < len(terms) else f"Term {tIdx + 1}"

                    correct_letter = None
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

                earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                question_result["points_earned"] = earned
                question_result["is_correct"] = correct_count == total_matches
                question_result["match_details"] = match_details
                question_result["feedback"] = f"Got {correct_count}/{total_matches} matches correct."

            elif q_type in ["short_answer", "extended_response"]:
                ai_grading_needed.append({
                    "index": len(results["questions"]),
                    "question": question,
                    "student_answer": student_answer,
                    "result": question_result
                })

            results["questions"].append(question_result)

    # AI grading for open-ended questions
    if ai_grading_needed:
        try:
            from openai import OpenAI
            client = OpenAI()

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

Student's Answer: {student_ans}

Evaluate the student's response and provide:
1. Points earned (0 to {points})
2. Brief, encouraging feedback (2-3 sentences)
3. Whether the answer demonstrates understanding

Respond in JSON format:
{{"points_earned": <number>, "feedback": "<string>", "is_correct": <boolean>}}"""

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a fair and encouraging teacher grading student work. Be supportive but accurate. Provide constructive feedback that helps students learn."},
                        {"role": "user", "content": grading_prompt}
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=300
                )

                ai_result = json.loads(response.choices[0].message.content)
                q_result["points_earned"] = min(ai_result.get("points_earned", 0), points)
                q_result["feedback"] = ai_result.get("feedback", "")
                q_result["is_correct"] = ai_result.get("is_correct", False)

                results["questions"][item["index"]] = q_result

        except Exception as e:
            print(f"AI grading error: {e}")
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

    return results
