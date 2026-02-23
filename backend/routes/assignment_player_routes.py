"""
Assignment Player API routes for Graider.
Handles interactive assignment serving and auto-grading.

Grading approach:
- Programmatic types (geometry, data tables, coordinate planes, etc.) are graded
  with mathematical precision — no AI, 100% consistent.
- Text-based types (short_answer, essay, extended_response) use the multipass
  AI grading pipeline with full 18-factor context for nuanced evaluation.
- Image uploads: Mathpix OCR for STEM subjects (handwritten math → LaTeX),
  GPT-4o Vision for ELA/Social Studies (handwritten text → text).
"""
import os
import sys
import json
import time
from flask import Blueprint, request, jsonify
from pathlib import Path

# Import multipass grading for text-based question types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
try:
    from assignment_grader import grade_per_question as ai_grade_per_question
    AI_GRADING_AVAILABLE = True
except ImportError:
    AI_GRADING_AVAILABLE = False

# Import Mathpix OCR for handwritten math recognition
try:
    from backend.services.mathpix_ocr import extract_answer_from_image, is_available as mathpix_available
    MATHPIX_AVAILABLE = mathpix_available()
except ImportError:
    MATHPIX_AVAILABLE = False
    def extract_answer_from_image(*args, **kwargs):
        return {'extracted_text': '', 'latex': '', 'confidence': 0, 'error': 'Mathpix not available'}

# Subjects where Mathpix OCR is useful (handwritten math/science notation)
MATHPIX_SUBJECTS = {'math', 'algebra', 'geometry', 'calculus', 'statistics',
                    'science', 'biology', 'chemistry', 'physics', 'earth science',
                    'trigonometry', 'precalculus', 'ap calculus', 'ap statistics',
                    'ap physics', 'ap chemistry', 'ap biology'}

assignment_player_bp = Blueprint('assignment_player', __name__)

# Store active assignments (in production, use database)
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_data/active_assignments")
SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")


def _load_teacher_context():
    """Load teacher settings for AI grading context (rubric, global notes, style)."""
    context = {
        'global_ai_notes': '',
        'rubric_prompt': '',
        'grading_style': 'standard',
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
            context['global_ai_notes'] = settings.get('globalAINotes', settings.get('aiNotes', ''))
            # Build rubric prompt from settings
            rubric = settings.get('rubric', {})
            if rubric and rubric.get('categories'):
                parts = []
                for cat in rubric['categories']:
                    name = cat.get('name', '')
                    weight = cat.get('weight', 0)
                    desc = cat.get('description', '')
                    if name:
                        parts.append(f"- {name} ({weight}%): {desc}")
                if parts:
                    context['rubric_prompt'] = "CUSTOM RUBRIC:\n" + '\n'.join(parts)
            context['grading_style'] = settings.get('gradingStyle', 'standard')
    except Exception:
        pass
    return context


@assignment_player_bp.route('/api/assignment/<assignment_id>', methods=['GET'])
def get_assignment(assignment_id):
    """Get an assignment for a student to complete."""
    try:
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        if not os.path.exists(filepath):
            return jsonify({"error": "Assignment not found"}), 404

        with open(filepath, 'r') as f:
            assignment = json.load(f)

        # Remove answer keys for student version
        student_assignment = strip_answers(assignment)
        return jsonify({"assignment": student_assignment})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment', methods=['POST'])
def create_assignment():
    """Create/publish an assignment for students."""
    try:
        data = request.json
        assignment = data.get('assignment', {})

        if not assignment:
            return jsonify({"error": "No assignment provided"}), 400

        # Generate unique ID
        assignment_id = f"assign_{int(time.time() * 1000)}"
        assignment['id'] = assignment_id
        assignment['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

        # Save assignment
        os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        with open(filepath, 'w') as f:
            json.dump(assignment, f, indent=2)

        # Generate shareable link (in production, use actual domain)
        share_url = f"/student/assignment/{assignment_id}"

        return jsonify({
            "status": "success",
            "assignment_id": assignment_id,
            "share_url": share_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment/<assignment_id>/submit', methods=['POST'])
def submit_assignment(assignment_id):
    """Submit and grade an assignment."""
    try:
        # Load the assignment with answers
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        if not os.path.exists(filepath):
            return jsonify({"error": "Assignment not found"}), 404

        with open(filepath, 'r') as f:
            assignment = json.load(f)

        # Get student answers
        data = request.json
        student_answers = data.get('answers', {})
        student_name = data.get('student_name', 'Unknown')

        # Grade the assignment
        results = grade_assignment(assignment, student_answers)
        results['student_name'] = student_name
        results['submitted_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        results['assignment_id'] = assignment_id

        # Save submission
        submissions_dir = os.path.join(ASSIGNMENTS_DIR, 'submissions', assignment_id)
        os.makedirs(submissions_dir, exist_ok=True)
        submission_file = os.path.join(submissions_dir, f"{student_name}_{int(time.time())}.json")
        with open(submission_file, 'w') as f:
            json.dump({
                'student_name': student_name,
                'answers': student_answers,
                'results': results
            }, f, indent=2)

        return jsonify({"results": results})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment/<assignment_id>/submissions', methods=['GET'])
def get_submissions(assignment_id):
    """Get all submissions for an assignment (teacher view)."""
    try:
        submissions_dir = os.path.join(ASSIGNMENTS_DIR, 'submissions', assignment_id)
        if not os.path.exists(submissions_dir):
            return jsonify({"submissions": []})

        submissions = []
        for filename in os.listdir(submissions_dir):
            if filename.endswith('.json'):
                with open(os.path.join(submissions_dir, filename), 'r') as f:
                    submissions.append(json.load(f))

        # Sort by submission time
        submissions.sort(key=lambda x: x.get('results', {}).get('submitted_at', ''), reverse=True)

        return jsonify({"submissions": submissions})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def strip_answers(assignment):
    """Remove answer keys from assignment for student version."""
    stripped = {**assignment}
    stripped['sections'] = []

    for section in assignment.get('sections', []):
        stripped_section = {**section}
        stripped_section['questions'] = []

        for q in section.get('questions', []):
            # Copy question without answer fields
            stripped_q = {k: v for k, v in q.items()
                         if k not in ['answer', 'expected_data', 'points_to_plot',
                                      'expected_values', 'correct_answer',
                                      'correct_expressions', 'correct_dots',
                                      'correct_leaves', 'correct_values',
                                      'correct_vertices', 'correct_numerator']}
            stripped_section['questions'].append(stripped_q)

        stripped['sections'].append(stripped_section)

    return stripped


def _should_use_mathpix(subject):
    """Check if Mathpix OCR should be used for this subject."""
    if not MATHPIX_AVAILABLE:
        return False
    return subject.lower().strip() in MATHPIX_SUBJECTS


def _process_image_answer(answer, question, subject, q_type, ai_model='gpt-4o'):
    """
    Process an answer that contains an uploaded image.

    For STEM subjects: uses Mathpix to convert handwritten math → LaTeX.
    For ELA/Social Studies: uses GPT-4o Vision to read handwritten text.

    Returns the answer with 'extracted_text' added (the OCR'd content).
    """
    image_data = None
    text_answer = ''

    if isinstance(answer, dict):
        image_data = answer.get('image')
        # Also grab any typed text the student provided alongside the image
        val = answer.get('value', answer)
        if isinstance(val, dict):
            text_answer = val.get('text', val.get('final', val.get('work', '')))
            image_data = image_data or val.get('image')
        elif isinstance(val, str):
            text_answer = val

    if not image_data:
        return answer, None  # No image to process

    question_text = question.get('question', '')
    ocr_result = None

    if _should_use_mathpix(subject):
        # STEM: Mathpix OCR (handwritten math → LaTeX)
        ocr_result = extract_answer_from_image(
            image_data,
            question_text=question_text,
            question_type=q_type,
        )
        if ocr_result.get('error'):
            print(f"Mathpix OCR failed, falling back to GPT-4o Vision: {ocr_result['error']}")
            ocr_result = _vision_ocr_fallback(image_data, question_text, subject)
    else:
        # Non-STEM: GPT-4o Vision (handwritten text → text)
        ocr_result = _vision_ocr_fallback(image_data, question_text, subject)

    if ocr_result and ocr_result.get('extracted_text'):
        # Combine typed text with OCR'd text
        extracted = ocr_result['extracted_text']
        if text_answer:
            combined = f"{text_answer}\n\n[From uploaded image]: {extracted}"
        else:
            combined = extracted

        # Return the combined answer for grading
        if isinstance(answer, dict):
            enhanced = {**answer, 'ocr_text': extracted, 'ocr_confidence': ocr_result.get('confidence', 0)}
            enhanced['value'] = combined
            if 'latex' in ocr_result and ocr_result['latex']:
                enhanced['ocr_latex'] = ocr_result['latex']
            return enhanced, ocr_result
        else:
            return combined, ocr_result

    return answer, ocr_result


def _vision_ocr_fallback(image_data, question_text, subject):
    """
    Use GPT-4o Vision to read handwritten text from an image.
    Fallback for non-STEM subjects or when Mathpix fails.
    """
    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {'extracted_text': '', 'confidence': 0, 'error': 'No OpenAI API key'}

        client = OpenAI(api_key=api_key)

        # Ensure proper data URI format
        if not image_data.startswith('data:'):
            image_data = f"data:image/png;base64,{image_data}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an OCR assistant. Read the handwritten student work in the image and transcribe it exactly as written. For math expressions, use LaTeX notation. For regular text, transcribe plainly. Only output the transcribed content, nothing else."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Read and transcribe the student's handwritten answer to this question: {question_text}"},
                        {"type": "image_url", "image_url": {"url": image_data, "detail": "high"}},
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0,
        )

        text = response.choices[0].message.content.strip()
        return {
            'extracted_text': text,
            'latex': '',
            'confidence': 0.8,  # GPT-4o Vision doesn't return confidence scores
            'ocr_source': 'gpt4o_vision',
            'error': None,
        }

    except Exception as e:
        print(f"GPT-4o Vision OCR failed: {e}")
        return {
            'extracted_text': '',
            'latex': '',
            'confidence': 0,
            'ocr_source': 'gpt4o_vision',
            'error': str(e),
        }


def grade_assignment(assignment, student_answers):
    """Grade all student answers against the assignment.

    Uses three strategies:
    - Programmatic grading for math/visual types (100% consistent, no AI)
    - AI multipass grading for text-based types (short_answer, essay, extended_response)
      with full teacher context (rubric, grading style, grade level, subject)
    - Image OCR: Mathpix for STEM (handwritten math → LaTeX), GPT-4o Vision for
      ELA/Social Studies (handwritten text → text), then graded through the pipeline
    """
    total_points = 0
    earned_points = 0
    question_results = {}

    # Types that need AI grading (text-based, subjective)
    AI_GRADED_TYPES = {'short_answer', 'essay', 'extended_response', 'bar_chart'}

    # Load teacher context once for the whole assignment
    grade_level = str(assignment.get('grade_level', assignment.get('grade', '7')))
    subject = assignment.get('subject', 'General')
    teacher_ctx = _load_teacher_context()
    grading_style = assignment.get('grading_style', teacher_ctx.get('grading_style', 'standard'))

    # Build full teacher instructions (mirrors app.py file_ai_notes assembly)
    teacher_instructions = teacher_ctx.get('global_ai_notes', '')
    grading_notes = assignment.get('grading_notes', '')
    if grading_notes:
        teacher_instructions += f"\n\nASSIGNMENT GRADING NOTES:\n{grading_notes}"
    rubric_prompt = teacher_ctx.get('rubric_prompt', '')
    if rubric_prompt:
        teacher_instructions += f"\n\n{rubric_prompt}"

    # Determine AI model from env
    ai_model = os.getenv('GRADING_MODEL', 'gpt-4o-mini')
    ai_provider = 'openai'
    if 'claude' in ai_model:
        ai_provider = 'anthropic'
    elif 'gemini' in ai_model:
        ai_provider = 'google'

    for sIdx, section in enumerate(assignment.get('sections', [])):
        section_type = section.get('type', 'short_answer')
        section_name = section.get('name', '')

        for qIdx, question in enumerate(section.get('questions', [])):
            key = f"{sIdx}-{qIdx}"
            student_answer = student_answers.get(key, {})
            q_type = question.get('question_type', section_type)
            q_points = question.get('points', 10)
            total_points += q_points

            # --- Image OCR preprocessing ---
            # If the student uploaded an image, run OCR before grading
            ocr_result = None
            has_image = (isinstance(student_answer, dict) and
                        (student_answer.get('image') or
                         (isinstance(student_answer.get('value'), dict) and
                          student_answer['value'].get('image'))))

            if has_image:
                student_answer, ocr_result = _process_image_answer(
                    student_answer, question, subject, q_type, ai_model
                )

            # --- Route to appropriate grader ---
            if q_type in AI_GRADED_TYPES and AI_GRADING_AVAILABLE:
                result = _grade_with_ai(
                    question, student_answer, q_type, q_points,
                    grade_level, subject, teacher_instructions,
                    grading_style, section_name, ai_model, ai_provider,
                    ocr_result=ocr_result,
                )
            else:
                # For programmatic types with image uploads (e.g., math_equation with photo),
                # try to use the OCR'd text as the answer
                if ocr_result and ocr_result.get('extracted_text') and q_type == 'math_equation':
                    # Create a synthetic answer from OCR for math grading
                    ocr_text = ocr_result['extracted_text']
                    latex = ocr_result.get('latex', ocr_result.get('ocr_latex', ''))
                    student_answer = {
                        'final': latex or ocr_text,
                        'work': ocr_text,
                    }
                result = grade_question(question, student_answer, q_type)

            # Attach OCR metadata to result
            if ocr_result:
                result['ocr_used'] = True
                result['ocr_source'] = ocr_result.get('ocr_source', 'mathpix')
                result['ocr_confidence'] = ocr_result.get('confidence', 0)
                result['ocr_text'] = ocr_result.get('extracted_text', '')

            result['points_possible'] = q_points
            if 'points_earned' not in result:
                result['points_earned'] = q_points if result['correct'] else (
                    q_points * result.get('partial_credit', 0)
                )
            earned_points += result['points_earned']

            question_results[key] = result

    percent = round((earned_points / total_points) * 100) if total_points > 0 else 0

    return {
        'score': round(earned_points, 1),
        'total': total_points,
        'percent': percent,
        'questions': question_results,
        'grade': get_letter_grade(percent)
    }


def _grade_with_ai(question, student_answer, q_type, q_points,
                   grade_level, subject, teacher_instructions,
                   grading_style, section_name, ai_model, ai_provider,
                   ocr_result=None):
    """Grade a text-based question using the multipass AI pipeline.

    This gives portal submissions the same quality grading as marked Word docs,
    with full 18-factor context integration. When an image was uploaded, the
    OCR-extracted text is included for richer grading context.
    """
    # Extract answer text
    if isinstance(student_answer, dict):
        answer_text = student_answer.get('value', student_answer.get('answer', ''))
        if isinstance(answer_text, dict):
            answer_text = str(answer_text)
    else:
        answer_text = str(student_answer) if student_answer else ''

    # If OCR was performed, enrich the answer text
    if ocr_result and ocr_result.get('extracted_text'):
        ocr_text = ocr_result['extracted_text']
        ocr_latex = ocr_result.get('latex', '')
        ocr_source = ocr_result.get('ocr_source', 'mathpix')
        confidence = ocr_result.get('confidence', 0)

        # Add OCR context to the answer for the AI grader
        if not answer_text or not answer_text.strip():
            answer_text = ocr_text
        elif ocr_text not in answer_text:
            answer_text += f"\n\n[Handwritten work transcribed via {ocr_source} (confidence: {confidence:.0%})]: {ocr_text}"
        if ocr_latex:
            answer_text += f"\n[LaTeX]: {ocr_latex}"

    if not answer_text or not answer_text.strip():
        return {'correct': False, 'feedback': 'No answer provided', 'partial_credit': 0}

    expected_answer = str(question.get('answer', ''))
    question_text = question.get('question', '')

    # Map question type to response_type for grade_per_question
    response_type = 'marker_response'
    if q_type == 'essay' or q_type == 'extended_response':
        response_type = 'marker_response'
    elif q_type == 'short_answer':
        response_type = 'numbered_question'

    try:
        ai_result = ai_grade_per_question(
            question=question_text,
            student_answer=answer_text,
            expected_answer=expected_answer,
            points=q_points,
            grade_level=grade_level,
            subject=subject,
            teacher_instructions=teacher_instructions,
            grading_style=grading_style,
            ai_model=ai_model,
            ai_provider=ai_provider,
            response_type=response_type,
            section_name=section_name,
            section_type='written',
        )

        # Convert AI result format to portal result format
        grade = ai_result.get('grade', {})
        score = grade.get('score', 0)
        possible = grade.get('possible', q_points)
        reasoning = grade.get('reasoning', '')
        quality = grade.get('quality', 'developing')
        is_correct = grade.get('is_correct', score >= possible * 0.7)

        return {
            'correct': is_correct,
            'feedback': reasoning,
            'partial_credit': score / possible if possible > 0 else 0,
            'points_earned': score,
            'quality': quality,
            'improvement_note': ai_result.get('improvement_note', ''),
        }

    except Exception as e:
        # Fallback to basic grading if AI fails
        print(f"AI grading failed, falling back to basic: {e}")
        return grade_short_answer(question, answer_text)


def grade_question(question, student_answer, q_type):
    """Grade a single question based on its type."""
    correct_answer = question.get('answer', '')

    # Handle different answer formats
    if isinstance(student_answer, dict):
        answer_value = student_answer.get('value', student_answer)
    else:
        answer_value = student_answer

    try:
        if q_type == 'number_line':
            return grade_number_line(question, answer_value)

        elif q_type == 'coordinate_plane':
            return grade_coordinate_plane(question, answer_value)

        elif q_type in ['geometry', 'triangle', 'rectangle', 'circle',
                       'trapezoid', 'parallelogram', 'regular_polygon',
                       'rectangular_prism', 'cylinder', 'similarity',
                       'pythagorean', 'angles', 'trig']:
            return grade_geometry(question, answer_value)

        elif q_type == 'box_plot':
            return grade_box_plot(question, answer_value)

        elif q_type == 'math_equation':
            return grade_math_equation(question, answer_value)

        elif q_type == 'coordinates':
            return grade_coordinates(question, answer_value)

        elif q_type == 'data_table':
            return grade_data_table(question, answer_value)

        elif q_type == 'bar_chart':
            return grade_bar_chart(question, answer_value)

        elif q_type == 'function_graph':
            return grade_function_graph(question, answer_value)

        elif q_type == 'dot_plot':
            return grade_dot_plot(question, answer_value)

        elif q_type == 'stem_and_leaf':
            return grade_stem_and_leaf(question, answer_value)

        elif q_type == 'unit_circle':
            return grade_unit_circle(question, answer_value)

        elif q_type == 'transformations':
            return grade_transformations(question, answer_value)

        elif q_type == 'fraction_model':
            return grade_fraction_model(question, answer_value)

        elif q_type == 'probability_tree':
            return grade_probability_tree(question, answer_value)

        elif q_type == 'tape_diagram':
            return grade_tape_diagram(question, answer_value)

        elif q_type == 'venn_diagram':
            return grade_venn_diagram(question, answer_value)

        elif q_type in ['protractor', 'angle_protractor']:
            return grade_protractor(question, answer_value)

        elif q_type == 'multiselect':
            correct_indices = set(question.get('correct', []))
            student_indices = set(answer_value) if isinstance(answer_value, list) else set()
            is_correct = correct_indices == student_indices
            if not is_correct and correct_indices:
                hits = len(correct_indices & student_indices)
                false_pos = len(student_indices - correct_indices)
                partial = max(0, hits - false_pos) / len(correct_indices)
                return {'correct': False, 'partial_credit': partial, 'feedback': f'Partially correct. Expected {len(correct_indices)} selections.'}
            return {'correct': is_correct, 'feedback': 'Correct!' if is_correct else 'Incorrect.'}

        elif q_type == 'multi_part':
            parts = question.get('parts', [])
            part_results = []
            total_earned = 0
            for i, part in enumerate(parts):
                part_answer = answer_value.get(str(i), '') if isinstance(answer_value, dict) else ''
                part_result = grade_question(part, part_answer, part.get('question_type', 'multiple_choice'))
                part_results.append(part_result)
                part_pts = part.get('points', 1)
                total_earned += part_pts if part_result.get('correct') else part_result.get('points_earned', 0)
            all_correct = all(r.get('correct') for r in part_results)
            return {'correct': all_correct, 'part_results': part_results, 'points_earned': total_earned, 'feedback': 'All parts correct!' if all_correct else 'Some parts incorrect.'}

        elif q_type == 'grid_match':
            correct_matrix = question.get('correct', [])
            student_matrix = answer_value if isinstance(answer_value, list) else []
            rows_correct = sum(1 for c, s in zip(correct_matrix, student_matrix) if c == s)
            total_rows = len(correct_matrix)
            all_correct = rows_correct == total_rows
            return {'correct': all_correct, 'partial_credit': rows_correct / total_rows if total_rows else 0, 'feedback': f'{rows_correct}/{total_rows} rows correct.'}

        elif q_type == 'inline_dropdown':
            dropdowns = question.get('dropdowns', [])
            student_selections = answer_value if isinstance(answer_value, list) else []
            correct_count = sum(1 for d, s in zip(dropdowns, student_selections) if d.get('correct') == s)
            total = len(dropdowns)
            all_correct = correct_count == total
            return {'correct': all_correct, 'partial_credit': correct_count / total if total else 0, 'feedback': f'{correct_count}/{total} selections correct.'}

        elif q_type in ['multiple_choice', 'true_false']:
            correct = str(answer_value).strip().lower() == str(correct_answer).strip().lower()
            return {'correct': correct, 'feedback': 'Correct!' if correct else f'Incorrect. The answer was: {correct_answer}'}

        else:  # short_answer and others
            return grade_short_answer(question, answer_value)

    except Exception as e:
        return {'correct': False, 'feedback': f'Error grading: {str(e)}', 'error': True}


def grade_number_line(question, answer):
    """Grade number line plotting."""
    expected = question.get('points_to_plot', [])
    if not expected or not answer:
        return {'correct': False, 'feedback': 'No points plotted'}

    # Check if all expected points are plotted (within tolerance)
    tolerance = 0.5
    correct_count = 0
    for exp_pt in expected:
        if any(abs(pt - exp_pt) < tolerance for pt in answer):
            correct_count += 1

    if correct_count == len(expected) and len(answer) == len(expected):
        return {'correct': True, 'feedback': 'All points correctly plotted!'}
    elif correct_count > 0:
        return {
            'correct': False,
            'partial_credit': correct_count / len(expected),
            'feedback': f'{correct_count}/{len(expected)} points correct'
        }
    else:
        return {'correct': False, 'feedback': 'No points correctly plotted'}


def grade_coordinate_plane(question, answer):
    """Grade coordinate plane plotting."""
    expected = question.get('points_to_plot', [])
    if not expected or not answer:
        return {'correct': False, 'feedback': 'No points plotted'}

    correct_count = 0
    for exp_pt in expected:
        if any(pt[0] == exp_pt[0] and pt[1] == exp_pt[1] for pt in answer):
            correct_count += 1

    if correct_count == len(expected) and len(answer) == len(expected):
        return {'correct': True, 'feedback': 'All points correctly plotted!'}
    elif correct_count > 0:
        return {
            'correct': False,
            'partial_credit': correct_count / len(expected),
            'feedback': f'{correct_count}/{len(expected)} points correct'
        }
    else:
        return {'correct': False, 'feedback': 'No points correctly plotted'}


def grade_geometry(question, answer):
    """Grade geometry questions for all shape types and modes.

    Supported shapes: triangle, rectangle, circle, trapezoid, parallelogram,
                      regular_polygon, rectangular_prism, cylinder
    Supported modes:  area, perimeter, pythagorean, volume, surface_area,
                      angles, similarity, trig, decompose
    """
    import math

    q_type = question.get('question_type', 'triangle')
    mode = question.get('mode', 'area')
    base = question.get('base', 6)
    height = question.get('height', 4)
    width = question.get('width', base)
    radius = question.get('radius', 5)
    top_base = question.get('top_base', 4)
    sides = question.get('sides', 6)
    side_length = question.get('side_length', 4)
    side_a = question.get('side_a')
    side_b = question.get('side_b')
    side_c = question.get('side_c')
    angle1 = question.get('angle1')
    angle2 = question.get('angle2')
    missing_angle = question.get('missing_angle', 3)
    theta = question.get('theta', 30)
    trig_func = question.get('trig_func', 'sin')
    missing_side = question.get('missing_side', 'c')
    scale = question.get('scale', 2)

    # Get the numeric answer from student
    if isinstance(answer, dict):
        answer_val = answer.get('value', '')
    else:
        answer_val = answer

    if not answer_val and answer_val != 0:
        return {'correct': False, 'feedback': 'No answer provided'}

    expected = None
    label = 'Answer'

    # --- Compute expected answer for each shape + mode ---

    # TRIANGLE
    if q_type in ('triangle', 'geometry'):
        if mode == 'area':
            expected = (base * height) / 2
            label = 'Area'
        elif mode == 'perimeter':
            a = side_a or 5
            b = side_b or 4
            c = side_c or 3
            expected = a + b + c
            label = 'Perimeter'
        elif mode == 'pythagorean':
            a = side_a or base or 3
            b = side_b or height or 4
            c = side_c
            if missing_side == 'c':
                expected = round(math.sqrt(a * a + b * b), 2)
            elif missing_side == 'b':
                c = c or math.sqrt(a * a + (b or 4) ** 2)
                expected = round(math.sqrt(c * c - a * a), 2)
            elif missing_side == 'a':
                c = c or math.sqrt((a or 3) ** 2 + b * b)
                expected = round(math.sqrt(c * c - b * b), 2)
            label = 'Missing side'
        elif mode == 'angles':
            a1 = angle1 or 60
            a2 = angle2 or 60
            if missing_angle == 1:
                expected = 180 - a2 - (question.get('angle3') or (180 - a1 - a2))
            elif missing_angle == 2:
                expected = 180 - a1 - (question.get('angle3') or (180 - a1 - a2))
            else:
                expected = 180 - a1 - a2
            expected = round(expected, 2)
            label = 'Missing angle'
        elif mode == 'trig':
            th_rad = math.radians(theta)
            # Given the triangle: opp = left side, adj = bottom, hyp = slanted
            a = side_a or base or 3
            b = side_b or height or 4
            c = side_c or round(math.sqrt(a * a + b * b), 2)
            if trig_func == 'sin':
                expected = round(b / c if c else math.sin(th_rad) * c, 2)
                if question.get('solve_for') == 'hyp':
                    expected = round(b / math.sin(th_rad), 2)
                elif question.get('solve_for') == 'opp':
                    expected = round(c * math.sin(th_rad), 2)
                else:
                    expected = round(math.sin(th_rad), 4)
            elif trig_func == 'cos':
                if question.get('solve_for') == 'hyp':
                    expected = round(a / math.cos(th_rad), 2)
                elif question.get('solve_for') == 'adj':
                    expected = round(c * math.cos(th_rad), 2)
                else:
                    expected = round(math.cos(th_rad), 4)
            elif trig_func == 'tan':
                if question.get('solve_for') == 'opp':
                    expected = round(a * math.tan(th_rad), 2)
                elif question.get('solve_for') == 'adj':
                    expected = round(b / math.tan(th_rad), 2)
                else:
                    expected = round(math.tan(th_rad), 4)
            label = 'Missing value'
        elif mode == 'similarity':
            expected = round(side_b * scale, 2) if side_b else round(base * scale, 2)
            label = 'Missing side'

    # RECTANGLE
    elif q_type == 'rectangle':
        w = width or base
        if mode == 'area':
            expected = w * height
            label = 'Area'
        elif mode == 'perimeter':
            expected = 2 * w + 2 * height
            label = 'Perimeter'

    # CIRCLE
    elif q_type == 'circle':
        r = radius or 5
        if mode == 'area':
            expected = round(math.pi * r * r, 2)
            label = 'Area'
        elif mode in ('perimeter', 'circumference'):
            expected = round(2 * math.pi * r, 2)
            label = 'Circumference'

    # TRAPEZOID
    elif q_type == 'trapezoid':
        if mode == 'area':
            expected = round(0.5 * (top_base + base) * height, 2)
            label = 'Area'

    # PARALLELOGRAM
    elif q_type == 'parallelogram':
        if mode == 'area':
            expected = round(base * height, 2)
            label = 'Area'

    # REGULAR POLYGON
    elif q_type == 'regular_polygon':
        n = sides
        s = side_length
        if mode == 'perimeter':
            expected = round(n * s, 2)
            label = 'Perimeter'
        elif mode in ('area', 'decompose'):
            # apothem = s / (2 * tan(pi/n))
            apothem = s / (2 * math.tan(math.pi / n))
            expected = round(0.5 * n * s * apothem, 2)
            label = 'Area'

    # RECTANGULAR PRISM
    elif q_type == 'rectangular_prism':
        l = base
        w = width or base
        h = height
        if mode == 'volume':
            expected = round(l * w * h, 2)
            label = 'Volume'
        elif mode == 'surface_area':
            expected = round(2 * (l * w + l * h + w * h), 2)
            label = 'Surface Area'

    # CYLINDER
    elif q_type == 'cylinder':
        r = radius or 3
        h = height or 7
        if mode == 'volume':
            expected = round(math.pi * r * r * h, 2)
            label = 'Volume'
        elif mode == 'surface_area':
            expected = round(2 * math.pi * r * r + 2 * math.pi * r * h, 2)
            label = 'Surface Area'

    # If question has an explicit answer field, prefer it
    if expected is None:
        explicit = question.get('answer')
        if explicit is not None:
            try:
                expected = float(explicit)
            except (ValueError, TypeError):
                return {'correct': False, 'feedback': f'Expected answer: {explicit}'}
        else:
            return {'correct': False, 'feedback': 'Could not determine expected answer for this question type'}

    # Compare student answer to expected
    tolerance = 0.1 if mode in ('trig',) else 0.01
    # Allow pi-based answers: if expected involves pi, use wider tolerance
    if expected > 10:
        tolerance = max(tolerance, expected * 0.005)  # 0.5% for larger numbers

    try:
        student_val = float(str(answer_val).replace(' ', '').replace(',', ''))
        diff = abs(student_val - expected)
        if diff < tolerance:
            return {'correct': True, 'feedback': f'Correct! {label} = {expected}'}
        elif diff < expected * 0.1 if expected != 0 else diff < 1:
            # Within 10% — partial credit
            return {
                'correct': False,
                'partial_credit': 0.5,
                'feedback': f'Close but not exact. {label} = {expected}'
            }
        else:
            return {'correct': False, 'feedback': f'Incorrect. {label} = {expected}'}
    except (ValueError, TypeError):
        return {'correct': False, 'feedback': f'Could not parse answer. Expected: {expected}'}


def grade_box_plot(question, answer):
    """Grade box plot five-number summary."""
    data = question.get('data', [[50, 60, 70, 80, 90]])[0]
    sorted_data = sorted(data)
    n = len(sorted_data)

    # Calculate expected values
    expected = {
        'min': sorted_data[0],
        'max': sorted_data[-1],
        'median': (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2 if n % 2 == 0 else sorted_data[n // 2],
    }

    lower = sorted_data[:n // 2]
    upper = sorted_data[(n + 1) // 2:]
    expected['q1'] = lower[len(lower) // 2] if len(lower) % 2 else (lower[len(lower) // 2 - 1] + lower[len(lower) // 2]) / 2
    expected['q3'] = upper[len(upper) // 2] if len(upper) % 2 else (upper[len(upper) // 2 - 1] + upper[len(upper) // 2]) / 2
    expected['range'] = expected['max'] - expected['min']
    expected['iqr'] = expected['q3'] - expected['q1']

    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No answers provided'}

    correct_count = 0
    total = len(expected)
    tolerance = 0.5

    for key, exp_val in expected.items():
        try:
            student_val = float(answer.get(key, 0))
            if abs(student_val - exp_val) < tolerance:
                correct_count += 1
        except:
            pass

    if correct_count == total:
        return {'correct': True, 'feedback': 'All values correct!'}
    else:
        return {
            'correct': False,
            'partial_credit': correct_count / total,
            'feedback': f'{correct_count}/{total} values correct'
        }


def grade_math_equation(question, answer):
    """Grade math equation using SymPy equivalence."""
    correct_answer = question.get('answer', '')

    if isinstance(answer, dict):
        answer_val = answer.get('final', '')
    else:
        answer_val = answer

    if not answer_val:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Try using STEM grading service
    try:
        from backend.services.stem_grading import check_math_equivalence
        result = check_math_equivalence(str(answer_val), str(correct_answer))
        if result.get('equivalent'):
            return {'correct': True, 'feedback': 'Correct!'}
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}
    except:
        # Fallback to string comparison
        if str(answer_val).strip() == str(correct_answer).strip():
            return {'correct': True, 'feedback': 'Correct!'}
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_coordinates(question, answer):
    """Grade coordinate/geography answers using distance."""
    correct = question.get('answer', {})
    tolerance_km = question.get('tolerance_km', 50)

    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No coordinates provided'}

    try:
        from backend.services.stem_grading import haversine_distance
        student_lat = float(answer.get('lat', 0))
        student_lng = float(answer.get('lng', 0))
        correct_lat = float(correct.get('lat', 0))
        correct_lng = float(correct.get('lng', 0))

        distance = haversine_distance(student_lat, student_lng, correct_lat, correct_lng)

        if distance <= tolerance_km:
            return {'correct': True, 'feedback': f'Correct! Within {distance:.1f} km'}
        else:
            return {'correct': False, 'feedback': f'Off by {distance:.1f} km. Expected: ({correct_lat}, {correct_lng})'}
    except Exception as e:
        return {'correct': False, 'feedback': f'Error: {str(e)}'}


def grade_data_table(question, answer):
    """Grade data table with tolerance."""
    expected = question.get('expected_data', [])
    tolerance = question.get('tolerance', 0.05)

    # DataTable onChange sends {headers, units, data} — extract the data array
    student_data = answer
    if isinstance(answer, dict):
        student_data = answer.get('data', [])

    if not student_data or not expected:
        return {'correct': False, 'feedback': 'No data provided'}

    try:
        correct_cells = 0
        total_cells = 0

        for i, row in enumerate(expected):
            if i >= len(student_data):
                continue
            for j, exp_val in enumerate(row):
                total_cells += 1
                if j >= len(student_data[i]):
                    continue
                try:
                    student_val = float(student_data[i][j])
                    expected_val = float(exp_val)
                    if expected_val == 0:
                        if abs(student_val) <= tolerance:
                            correct_cells += 1
                    elif abs(student_val - expected_val) <= abs(expected_val * tolerance):
                        correct_cells += 1
                except (ValueError, TypeError):
                    if str(student_data[i][j]).strip().lower() == str(exp_val).strip().lower():
                        correct_cells += 1

        if correct_cells == total_cells:
            return {'correct': True, 'feedback': 'All values correct!'}
        else:
            return {
                'correct': False,
                'partial_credit': correct_cells / total_cells if total_cells > 0 else 0,
                'feedback': f'{correct_cells}/{total_cells} cells correct'
            }
    except Exception as e:
        return {'correct': False, 'feedback': f'Error: {str(e)}'}


def grade_bar_chart(question, answer):
    """Grade bar chart interpretation questions (text-based answer)."""
    correct = str(question.get('answer', '')).strip().lower()
    student = str(answer).strip().lower() if answer else ''

    if not student:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Exact match
    if student == correct:
        return {'correct': True, 'feedback': 'Correct!'}

    # Keyword overlap — bar chart answers are interpretation/analysis text
    correct_words = set(correct.split())
    student_words = set(student.split())
    overlap = len(correct_words & student_words)

    if correct_words and overlap >= len(correct_words) * 0.7:
        return {'correct': True, 'partial_credit': 0.8, 'feedback': 'Mostly correct'}

    return {'correct': False, 'feedback': f'Incorrect. Expected: {question.get("answer", "")}'}


def grade_function_graph(question, answer):
    """Grade function graph by comparing student expressions to expected expressions."""
    expected = question.get('correct_expressions', [])
    if not expected:
        expected_str = question.get('answer', '')
        expected = [expected_str] if expected_str else []

    if not answer or not expected:
        return {'correct': False, 'feedback': 'No expressions provided'}

    student_exprs = answer if isinstance(answer, list) else [answer]

    try:
        from sympy import sympify, simplify, Symbol
        x = Symbol('x')

        def normalize_expr(expr_str):
            """Normalize a math expression string for comparison."""
            s = str(expr_str).strip().lower()
            s = s.replace('^', '**')
            s = s.replace(' ', '')
            # Remove leading 'y=' or 'f(x)='
            for prefix in ['y=', 'f(x)=']:
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s

        matched = 0
        for exp_expr in expected:
            exp_norm = normalize_expr(exp_expr)
            try:
                exp_sym = sympify(exp_norm)
            except Exception:
                continue

            for stu_expr in student_exprs:
                stu_norm = normalize_expr(stu_expr)
                try:
                    stu_sym = sympify(stu_norm)
                    if simplify(exp_sym - stu_sym) == 0:
                        matched += 1
                        break
                except Exception:
                    # Fall back to string comparison
                    if exp_norm == stu_norm:
                        matched += 1
                        break

        if matched == len(expected) and len(student_exprs) == len(expected):
            return {'correct': True, 'feedback': 'All functions correctly graphed!'}
        elif matched > 0:
            return {
                'correct': False,
                'partial_credit': matched / len(expected),
                'feedback': f'{matched}/{len(expected)} functions correct'
            }
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {", ".join(expected)}'}

    except ImportError:
        # SymPy not available — fall back to normalized string comparison
        def normalize_expr(expr_str):
            s = str(expr_str).strip().lower().replace('^', '**').replace(' ', '')
            for prefix in ['y=', 'f(x)=']:
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s

        expected_norm = [normalize_expr(e) for e in expected]
        student_norm = [normalize_expr(s) for s in student_exprs]

        matched = sum(1 for e in expected_norm if e in student_norm)

        if matched == len(expected) and len(student_norm) == len(expected):
            return {'correct': True, 'feedback': 'All functions correctly graphed!'}
        elif matched > 0:
            return {
                'correct': False,
                'partial_credit': matched / len(expected),
                'feedback': f'{matched}/{len(expected)} functions correct'
            }
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {", ".join(expected)}'}


def grade_dot_plot(question, answer):
    """Grade dot plot questions by comparing frequency counts."""
    correct_dots = question.get('correct_dots', {})
    if not correct_dots or not answer:
        return {'correct': False, 'feedback': 'No data plotted'}

    if not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'Invalid answer format'}

    total_keys = set(list(correct_dots.keys()) + list(answer.keys()))
    matches = 0
    total = len(total_keys)

    for key in total_keys:
        expected = int(correct_dots.get(key, 0))
        actual = int(answer.get(key, 0))
        if expected == actual:
            matches += 1

    if total == 0:
        return {'correct': False, 'feedback': 'No data to compare'}

    ratio = matches / total
    if ratio >= 1.0:
        return {'correct': True, 'feedback': 'All frequencies are correct!'}
    elif ratio >= 0.7:
        return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} values correct'}
    else:
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} values correct'}


def grade_stem_and_leaf(question, answer):
    """Grade stem-and-leaf plot by comparing sorted leaves per stem."""
    data = question.get('data', [])
    correct_leaves = question.get('correct_leaves', {})
    if not answer:
        return {'correct': False, 'feedback': 'No leaves entered'}

    if not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'Invalid answer format'}

    # Compute correct leaves from data if not provided
    if not correct_leaves and data:
        stems = sorted(set(v // 10 for v in data))
        correct_leaves = {}
        for stem in stems:
            leaves = sorted(v % 10 for v in data if v // 10 == stem)
            correct_leaves[str(stem)] = ' '.join(str(l) for l in leaves)

    matches = 0
    total = len(correct_leaves)

    for stem, expected_str in correct_leaves.items():
        user_str = answer.get(str(stem), '')
        expected_sorted = sorted(int(x) for x in expected_str.strip().split() if x.isdigit())
        user_sorted = sorted(int(x) for x in str(user_str).strip().split() if x.isdigit())
        if expected_sorted == user_sorted:
            matches += 1

    if total == 0:
        return {'correct': False, 'feedback': 'No stems to compare'}

    ratio = matches / total
    if ratio >= 1.0:
        return {'correct': True, 'feedback': 'All stems are correct!'}
    elif ratio >= 0.7:
        return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} stems correct'}
    else:
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} stems correct'}


def grade_unit_circle(question, answer):
    """Grade unit circle questions by checking filled-in values."""
    correct_values = question.get('correct_values', {})
    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No values entered'}

    if not correct_values:
        # Build from hidden angles/values
        hidden_angles = question.get('hidden_angles', [])
        hidden_values = question.get('hidden_values', [])
        # Without explicit correct_values, fall back to text comparison with answer field
        answer_text = str(question.get('answer', '')).strip().lower()
        if answer_text:
            user_text = ' '.join(str(v) for v in answer.values()).strip().lower()
            correct = answer_text == user_text
            return {'correct': correct, 'feedback': 'Correct!' if correct else f'Expected: {answer_text}'}
        return {'correct': False, 'feedback': 'Missing answer key'}

    matches = 0
    total = len(correct_values)

    for key, expected in correct_values.items():
        user_val = str(answer.get(key, '')).replace(' ', '').lower()
        expected_val = str(expected).replace(' ', '').lower()
        if user_val == expected_val:
            matches += 1

    if total == 0:
        return {'correct': False, 'feedback': 'No values to check'}

    ratio = matches / total
    if ratio >= 1.0:
        return {'correct': True, 'feedback': 'All values correct!'}
    elif ratio >= 0.6:
        return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} values correct'}
    else:
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} values correct'}


def grade_transformations(question, answer):
    """Grade transformation questions by checking plotted vertices or identification."""
    import math
    mode = question.get('mode', 'plot')

    if mode == 'identify':
        correct = str(question.get('answer', '')).strip().lower()
        student = str(answer.get('answer', '') if isinstance(answer, dict) else answer).strip().lower()
        if not student:
            return {'correct': False, 'feedback': 'No answer provided'}
        # Check key words
        if correct == student:
            return {'correct': True, 'feedback': 'Correct!'}
        # Partial: check if transformation type keyword matches
        keywords = ['translation', 'reflection', 'rotation', 'dilation']
        for kw in keywords:
            if kw in correct and kw in student:
                return {'correct': True, 'partial_credit': 0.7, 'feedback': f'Correct type, but be more specific. Expected: {correct}'}
        return {'correct': False, 'feedback': f'Incorrect. Expected: {question.get("answer", "")}'}

    # Plot mode: check vertices
    correct_vertices = question.get('correct_vertices', [])
    user_vertices = answer.get('vertices', []) if isinstance(answer, dict) else []

    if not correct_vertices:
        # Compute from transformation
        original = question.get('original_vertices', [])
        t_type = question.get('transformation_type', 'translation')
        params = question.get('transform_params', {})
        correct_vertices = []
        for x, y in original:
            if t_type == 'translation':
                correct_vertices.append([x + params.get('dx', 0), y + params.get('dy', 0)])
            elif t_type == 'reflection':
                axis = params.get('axis', 'y-axis')
                if axis == 'y-axis': correct_vertices.append([-x, y])
                elif axis == 'x-axis': correct_vertices.append([x, -y])
                elif axis == 'y=x': correct_vertices.append([y, x])
                elif axis == 'y=-x': correct_vertices.append([-y, -x])
            elif t_type == 'rotation':
                deg = params.get('degrees', 90)
                rad = math.radians(deg)
                cx_r = params.get('centerX', 0)
                cy_r = params.get('centerY', 0)
                nx = round((x - cx_r) * math.cos(rad) - (y - cy_r) * math.sin(rad) + cx_r)
                ny = round((x - cx_r) * math.sin(rad) + (y - cy_r) * math.cos(rad) + cy_r)
                correct_vertices.append([nx, ny])
            elif t_type == 'dilation':
                scale = params.get('scale', 2)
                cx_d = params.get('centerX', 0)
                cy_d = params.get('centerY', 0)
                correct_vertices.append([round(cx_d + scale * (x - cx_d)), round(cy_d + scale * (y - cy_d))])

    if not user_vertices:
        return {'correct': False, 'feedback': 'No vertices plotted'}

    # Match vertices (order-independent)
    matched = 0
    used = set()
    for cv in correct_vertices:
        for i, uv in enumerate(user_vertices):
            if i not in used and abs(cv[0] - uv[0]) <= 0.5 and abs(cv[1] - uv[1]) <= 0.5:
                matched += 1
                used.add(i)
                break

    total = len(correct_vertices)
    if total == 0:
        return {'correct': False, 'feedback': 'Missing correct vertices'}

    ratio = matched / total
    if ratio >= 1.0 and len(user_vertices) == total:
        return {'correct': True, 'feedback': 'All transformed vertices are correct!'}
    elif ratio >= 0.7:
        return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matched}/{total} vertices correct'}
    else:
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matched}/{total} vertices correct'}


def grade_fraction_model(question, answer):
    """Grade fraction model questions."""
    if not answer:
        return {'correct': False, 'feedback': 'No answer provided'}

    correct_answer = str(question.get('answer', '')).strip()
    student_answer = ''

    if isinstance(answer, dict):
        student_answer = str(answer.get('answer', '')).strip()
        shaded = answer.get('shaded', [])
        denom = question.get('denominator', 4)
        correct_num = question.get('correct_numerator')

        # Check shading if correct_numerator is provided
        if correct_num is not None:
            if len(shaded) == correct_num:
                if student_answer and correct_answer:
                    if normalize_fraction(student_answer) == normalize_fraction(correct_answer):
                        return {'correct': True, 'feedback': 'Correct shading and fraction!'}
                    else:
                        return {'correct': True, 'partial_credit': 0.7, 'feedback': f'Correct shading but fraction should be {correct_answer}'}
                return {'correct': True, 'feedback': 'Correct shading!'}
            else:
                return {'correct': False, 'feedback': f'Expected {correct_num} shaded parts out of {denom}'}
    else:
        student_answer = str(answer).strip()

    if not student_answer:
        return {'correct': False, 'feedback': 'No answer entered'}

    if correct_answer and normalize_fraction(student_answer) == normalize_fraction(correct_answer):
        return {'correct': True, 'feedback': 'Correct!'}

    return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def normalize_fraction(s):
    """Normalize fraction string for comparison."""
    s = s.strip().lower()
    # Try to evaluate as a number
    try:
        if '/' in s:
            parts = s.split('/')
            return round(float(parts[0]) / float(parts[1]), 6)
        return round(float(s), 6)
    except (ValueError, ZeroDivisionError):
        return s


def grade_probability_tree(question, answer):
    """Grade probability tree questions."""
    correct_values = question.get('correct_values', {})
    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No answer provided'}

    # Check each hidden probability/answer
    if correct_values:
        matches = 0
        total = len(correct_values)
        for key, expected in correct_values.items():
            user_val = str(answer.get(key, '')).strip()
            expected_val = str(expected).strip()
            if normalize_fraction(user_val) == normalize_fraction(expected_val):
                matches += 1

        if total == 0:
            return {'correct': False, 'feedback': 'No values to check'}
        ratio = matches / total
        if ratio >= 1.0:
            return {'correct': True, 'feedback': 'All probabilities correct!'}
        elif ratio >= 0.6:
            return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} values correct'}
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} values correct'}

    # Fall back to final answer
    correct_answer = str(question.get('answer', '')).strip()
    student_answer = str(answer.get('final', '')).strip()
    if correct_answer and normalize_fraction(student_answer) == normalize_fraction(correct_answer):
        return {'correct': True, 'feedback': 'Correct!'}
    return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_tape_diagram(question, answer):
    """Grade tape diagram questions."""
    correct_values = question.get('correct_values', {})
    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No answer provided'}

    if correct_values:
        matches = 0
        total = len(correct_values)
        for key, expected in correct_values.items():
            user_val = str(answer.get(key, '')).strip()
            expected_val = str(expected).strip()
            try:
                if abs(float(user_val) - float(expected_val)) < 0.01:
                    matches += 1
            except ValueError:
                if user_val.lower() == expected_val.lower():
                    matches += 1

        if total == 0:
            return {'correct': False, 'feedback': 'No values to check'}
        ratio = matches / total
        if ratio >= 1.0:
            return {'correct': True, 'feedback': 'All values correct!'}
        elif ratio >= 0.6:
            return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} values correct'}
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} values correct'}

    # Fall back to final answer
    correct_answer = str(question.get('answer', '')).strip()
    student_answer = str(answer.get('final', '')).strip()
    if correct_answer:
        try:
            if abs(float(student_answer) - float(correct_answer)) < 0.01:
                return {'correct': True, 'feedback': 'Correct!'}
        except ValueError:
            if student_answer.lower() == correct_answer.lower():
                return {'correct': True, 'feedback': 'Correct!'}
    return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_venn_diagram(question, answer):
    """Grade Venn diagram questions."""
    correct_values = question.get('correct_values', {})
    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No answer provided'}

    if correct_values:
        matches = 0
        total = len(correct_values)
        for key, expected in correct_values.items():
            user_val = str(answer.get(key, '')).strip()
            expected_val = str(expected).strip()
            try:
                if abs(float(user_val) - float(expected_val)) < 0.01:
                    matches += 1
            except ValueError:
                if user_val.lower() == expected_val.lower():
                    matches += 1

        if total == 0:
            return {'correct': False, 'feedback': 'No values to check'}
        ratio = matches / total
        if ratio >= 1.0:
            return {'correct': True, 'feedback': 'All regions correct!'}
        elif ratio >= 0.6:
            return {'correct': True, 'partial_credit': ratio, 'feedback': f'{matches}/{total} regions correct'}
        return {'correct': False, 'partial_credit': ratio, 'feedback': f'Only {matches}/{total} regions correct'}

    # Fall back to final answer
    correct_answer = str(question.get('answer', '')).strip()
    student_answer = str(answer.get('final', '')).strip()
    if correct_answer and student_answer.lower() == correct_answer.lower():
        return {'correct': True, 'feedback': 'Correct!'}
    return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_protractor(question, answer):
    """Grade protractor/angle questions."""
    correct_answer = str(question.get('answer', '')).strip()
    mode = question.get('mode', 'measure')

    # Handle construct mode first (uses userAngle, not text answer)
    if mode == 'construct':
        target = question.get('target_angle', 0)
        user_angle = 0
        if isinstance(answer, dict):
            user_angle = answer.get('userAngle', 0)
        try:
            user_angle = float(user_angle)
            if abs(user_angle - target) <= 3:
                return {'correct': True, 'feedback': 'Correct angle constructed!'}
            elif abs(user_angle - target) <= 10:
                return {'correct': True, 'partial_credit': 0.6, 'feedback': f'Close! Target was {target} degrees, you made {int(user_angle)} degrees'}
            return {'correct': False, 'feedback': f'Incorrect. Target was {target} degrees'}
        except (ValueError, TypeError):
            return {'correct': False, 'feedback': 'Could not read your angle'}

    student_answer = ''
    if isinstance(answer, dict):
        student_answer = str(answer.get('answer', '')).strip()
    else:
        student_answer = str(answer).strip() if answer else ''

    if not student_answer:
        return {'correct': False, 'feedback': 'No answer provided'}

    if mode == 'measure':
        # Numeric comparison with tolerance
        try:
            expected = float(correct_answer)
            actual = float(student_answer)
            if abs(expected - actual) <= 2:  # 2-degree tolerance
                return {'correct': True, 'feedback': 'Correct!'}
            elif abs(expected - actual) <= 5:
                return {'correct': True, 'partial_credit': 0.7, 'feedback': f'Close! The exact answer is {correct_answer} degrees'}
            return {'correct': False, 'feedback': f'Incorrect. The angle measures {correct_answer} degrees'}
        except ValueError:
            pass

    if mode == 'classify':
        expected = correct_answer.lower()
        actual = student_answer.lower()
        if expected == actual:
            return {'correct': True, 'feedback': 'Correct!'}
        return {'correct': False, 'feedback': f'Incorrect. This is a(n) {correct_answer} angle'}

    # Generic fallback
    if student_answer.lower() == correct_answer.lower():
        return {'correct': True, 'feedback': 'Correct!'}
    return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_short_answer(question, answer):
    """Grade short answer questions."""
    correct = str(question.get('answer', '')).strip().lower()
    student = str(answer).strip().lower() if answer else ''

    if not student:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Exact match
    if student == correct:
        return {'correct': True, 'feedback': 'Correct!'}

    # Check for key words
    correct_words = set(correct.split())
    student_words = set(student.split())
    overlap = len(correct_words & student_words)

    if overlap >= len(correct_words) * 0.7:
        return {'correct': True, 'partial_credit': 0.8, 'feedback': 'Mostly correct'}

    return {'correct': False, 'feedback': f'Incorrect. Expected: {question.get("answer", "")}'}


def get_letter_grade(percent):
    """Convert percentage to letter grade."""
    if percent >= 90:
        return 'A'
    elif percent >= 80:
        return 'B'
    elif percent >= 70:
        return 'C'
    elif percent >= 60:
        return 'D'
    else:
        return 'F'
