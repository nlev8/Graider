"""Grading thread lifecycle wrapper.

Extracted from backend/app.py in Phase 3a PR3. Handles BYOK (bring your
own key) context management then delegates to the pipeline module for
the actual grading logic. Thin wrapper (~27 LOC) — lifecycle concerns
ONLY; business logic lives in backend.grading.pipeline.
"""
from grading.pipeline import _run_grading_thread_inner
from grading.state import _get_state


def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False, class_period='', rubric=None, ensemble_models=None, extraction_mode='structured', trusted_students=None, grading_style='standard', teacher_id='local-dev', user_api_keys=None):
    """Run the grading process in a background thread.

    Args:
        selected_files: List of filenames to grade, or None to grade all files
        ai_model: AI model to use (or primary model if not using ensemble)
        skip_verified: If True, skip files that were previously graded with verified status
        rubric: Custom rubric dict from Settings with categories, weights, descriptions
        ensemble_models: List of models for ensemble grading (e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash'])
        extraction_mode: "structured" (parse with rules) or "ai" (let AI identify responses)
        trusted_students: List of student IDs to skip AI/plagiarism detection for
        user_api_keys: Pre-resolved BYOK keys dict for contextvars propagation
    """
    # Resolve per-teacher state for try/finally
    state = _get_state(teacher_id)

    # BYOK: Set per-user API keys in contextvars for this thread + child workers
    from backend.api_keys import set_thread_keys, clear_thread_keys
    if user_api_keys:
        set_thread_keys(user_api_keys)

    try:
        _run_grading_thread_inner(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified, class_period, rubric, ensemble_models, extraction_mode, trusted_students, grading_style, teacher_id)
    finally:
        clear_thread_keys()

