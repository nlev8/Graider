"""Golden characterization net for grade_portal_submission_sync.

No existing test drives the full function and asserts its scoring OUTPUT — the
dedicated tests cover signatures, dedup, and the helper functions only. This
net pins the EXACT deterministic scoring + persistence payload (the per-question
scores, totals, percentage, status, standards_mastery, and the saved result
record) for a representative assessment exercising every score-loop branch:
multiple_choice, true_false, matching, and a written (AI-graded) question.

It exists to make the CQ7 god-function split of grade_portal_submission_sync
(extraction of the score-calculation + feedback + persistence block into a
module-level helper) provably behavior-preserving: the captured repo.update
payload and saved result record must be byte-for-byte identical before and
after the split.

All AI/IO seams are mocked deterministically (grade_written_questions,
_safe_generate_feedback, the repository, results storage, history, api keys),
so the instant-scoring math (MC/TF/matching) and the wiring of the written
results into the payload are what's actually pinned.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


ASSESSMENT = {
    "title": "Golden Quiz",
    "sections": [
        {
            "name": "Part 1",
            "questions": [
                {"type": "multiple_choice", "question": "Pick B",
                 "answer": "B", "points": 2, "standard": "STD.1", "dok": 2},
                {"type": "true_false", "question": "Sky is blue",
                 "answer": "True", "points": 1, "standard": "STD.2", "dok": 1},
                {"type": "matching", "question": "Match them",
                 "terms": ["a", "b"], "definitions": ["X", "Y"],
                 "answer": {"a": "X", "b": "Y"}, "points": 4,
                 "standard": "STD.3", "dok": 3},
                {"type": "short_answer", "question": "Explain photosynthesis",
                 "points": 3, "standard": "STD.4", "dok": 2},
            ],
        }
    ],
}

ANSWERS = {
    "0-0": "B",            # MC correct -> 2
    "0-1": "true",         # TF correct -> 1
    "0-2-match-0": "A",    # a -> X (def idx 0 = A) correct
    "0-2-match-1": "B",    # b -> Y (def idx 1 = B) correct -> 4
    "0-3": "Plants make food from light.",  # written -> AI score 2
}

# Deterministic AI seams
WRITTEN_RESULTS = [
    {"grade": {"score": 2, "reasoning": "Partially correct", "quality": "developing"}},
]
FEEDBACK = {
    "feedback": "Solid effort — review matching.",
    "rubric_breakdown": {"content_accuracy": 4, "completeness": 3,
                         "writing_quality": 4, "effort_engagement": 5},
}


def _run_golden():
    """Drive grade_portal_submission_sync with all seams mocked; return the
    captured repo.update payload and the saved result record list."""
    from backend.services import portal_grading

    captured = {}
    mock_repo = MagicMock()
    mock_repo.update = MagicMock(side_effect=lambda sid, payload: captured.update(
        {"update_sid": sid, "update_payload": payload}))

    def _capture_save(results, teacher_id):
        captured["saved_results"] = results
        captured["saved_teacher_id"] = teacher_id

    with patch.object(portal_grading, 'repository_for', return_value=mock_repo), \
         patch('backend.supabase_client.get_supabase', return_value=MagicMock()), \
         patch.object(portal_grading, 'grade_written_questions',
                      return_value=WRITTEN_RESULTS), \
         patch.object(portal_grading, '_safe_generate_feedback',
                      return_value=FEEDBACK), \
         patch.object(portal_grading, '_safe_save_results',
                      side_effect=_capture_save), \
         patch('backend.grading.state.load_saved_results', return_value=[]), \
         patch('backend.grading.state._get_lock') as mock_lock, \
         patch('backend.storage.load_student_history', return_value=None), \
         patch('backend.storage.save_student_history'), \
         patch('backend.api_keys.resolve_keys_for_teacher', return_value=None):
        mock_lock.return_value.__enter__ = lambda *_: None
        mock_lock.return_value.__exit__ = lambda *_: None
        portal_grading.grade_portal_submission_sync(
            submission_id='sub-golden',
            assessment=ASSESSMENT,
            answers=ANSWERS,
            student_info={'student_name': 'Ada', 'student_id': 'stu-1'},
            teacher_config={'grade_level': '7', 'subject': 'Science',
                            'grading_style': 'standard', 'ai_model': 'gpt-4o-mini',
                            'period': 'P1'},
            teacher_id='teacher-1',
            path_type='submissions',
        )
    return captured


# Golden values (captured against main, pre-split, 2026-06-04)
GOLDEN_QUESTIONS = [
    {"question": "Pick B", "type": "multiple_choice", "points_earned": 2,
     "points_possible": 2, "student_answer": "B", "correct_answer": "B",
     "is_correct": True, "standard": "STD.1", "dok": 2},
    {"question": "Sky is blue", "type": "true_false", "points_earned": 1,
     "points_possible": 1, "student_answer": "true", "correct_answer": "True",
     "is_correct": True, "standard": "STD.2", "dok": 1},
    {"question": "Match them", "type": "matching", "points_earned": 4,
     "points_possible": 4, "student_answer": "", "correct_answer": {"a": "X", "b": "Y"},
     "is_correct": True, "standard": "STD.3", "dok": 3},
    {"question": "Explain photosynthesis", "type": "short_answer",
     "points_earned": 2, "points_possible": 3, "reasoning": "Partially correct",
     "quality": "developing", "student_answer": "Plants make food from light.",
     "standard": "STD.4", "dok": 2},
]


def test_golden_repo_update_payload():
    """The repo.update payload (the student-facing graded result) is pinned
    exactly for the representative assessment."""
    cap = _run_golden()
    assert cap.get("update_sid") == 'sub-golden'
    payload = cap["update_payload"]

    assert payload["score"] == 9
    assert payload["percentage"] == 90
    assert payload["status"] == "graded"

    results = payload["results"]
    assert results["score"] == 9
    assert results["total_points"] == 10
    assert results["percentage"] == 90
    assert results["grading_source"] == "multipass"
    assert results["feedback_summary"] == "Solid effort — review matching."
    assert results["breakdown"] == FEEDBACK["rubric_breakdown"]
    assert results["questions"] == GOLDEN_QUESTIONS
    # standards_mastery is derived from per_question_scores; pin its presence + shape
    assert isinstance(results["standards_mastery"], dict)
    assert set(results["standards_mastery"].keys()) == {"STD.1", "STD.2", "STD.3", "STD.4"}


def test_golden_saved_result_record():
    """The result record saved to teacher storage carries the same score and
    per-question scores."""
    cap = _run_golden()
    saved = cap.get("saved_results")
    assert saved and isinstance(saved, list)
    rec = saved[0]
    # build_result_record stores `score` as the percentage (not the raw score).
    assert rec["score"] == 90
    assert rec["letter_grade"] == "A"
    assert rec.get("submission_id") == 'sub-golden'
    assert rec["per_question_scores"] == GOLDEN_QUESTIONS
