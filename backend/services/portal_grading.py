"""
Portal Multipass Grading Service.

Bridges portal student submissions to Graider's full 18-factor grading pipeline.
Skips Pass 1 (extraction) since portal answers are already structured JSON.
Calls grade_per_question (Pass 2) + generate_feedback (Pass 3) from assignment_grader.py.
"""
import hashlib
import logging
import signal
import sys
import threading
from datetime import datetime, timezone
from importlib import import_module

import sentry_sdk

from backend.observability import critical_path
from backend.services.submission_repository import (
    SubmissionPathType,
    repository_for,
)

logger = logging.getLogger(__name__)

# Track active grading threads for graceful shutdown
_active_threads = set()
_shutdown_event = threading.Event()


def _handle_shutdown(signum, frame):
    """Wait for active grading threads to finish before exiting."""
    logger.info("Shutdown signal received — waiting for %d grading threads", len(_active_threads))
    _shutdown_event.set()
    for t in list(_active_threads):
        t.join(timeout=30)
    logger.info("All grading threads finished, exiting")
    sys.exit(0)


# Register SIGTERM handler (Railway sends this on deploy)
try:
    signal.signal(signal.SIGTERM, _handle_shutdown)
except (OSError, ValueError):
    pass  # Can't set signal handler in non-main thread

# Import grade_per_question + generate_feedback at module level so tests can
# patch backend.services.portal_grading.grade_per_question / .generate_feedback.
# On ImportError we page Sentry directly: grade_per_question's downstream
# TypeError is caught by grade_written_questions which only logs + falls back,
# so log-only here would hide a config-level failure (assignment_grader
# unavailable means NO STEM grading happens for any student).
def _import_from_assignment_grader(attr):
    """Import attr from assignment_grader; page Sentry on failure, return None.
    Isolated so tests can drive the error path without reloading modules."""
    try:
        mod = import_module("assignment_grader")
        return getattr(mod, attr)
    except (ImportError, AttributeError) as e:
        logger.warning("assignment_grader.%s unavailable: %s", attr, e)
        sentry_sdk.capture_exception(e)
        return None


grade_per_question = _import_from_assignment_grader("grade_per_question")
generate_feedback = _import_from_assignment_grader("generate_feedback")

from backend.services.grading_service import _build_standards_mastery

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
                          student_history="", class_period="",
                          correction_context=""):
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

    if correction_context:
        notes += "\n\n" + correction_context

    return notes


def grade_written_questions(questions, answers, ai_notes, grade_level, subject,
                            grading_style, ai_model="gpt-4o-mini",
                            token_tracker=None, student_name=""):
    """Grade written questions using the multipass per-question grader.

    Args:
        questions: List of question dicts with type, question, answer (expected), points
        answers: Dict mapping answer_key to student's answer text

    Returns list of grade results from grade_per_question.
    """
    # Defensive: ai_model can arrive as None/"" from teacher_config
    # (e.g., db row with NULL ai_model field). Without this guard,
    # `.startswith()` crashes with AttributeError. Gemini quality-
    # review 2026-05-10 caught this regression risk.
    ai_model = ai_model or "gpt-4o-mini"
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
                student_name=student_name,
            )
            results.append(result)
        except Exception as e:
            # Issue #224: TransientError must bubble up so Celery's
            # `autoretry_for=(TransientError,)` can retry the whole
            # submission instead of locking in a per-question fallback
            # during an AI 5xx storm. Non-transient errors (ValueError
            # etc.) still fall back so one bad question doesn't kill
            # the whole submission.
            from backend.tasks.grading_tasks import TransientError
            if isinstance(e, TransientError):
                raise
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
                        per_question_scores, *, submission_id: str | None = None):
    """Build a result record in the exact format analytics expects.

    This format matches what the folder-based grading produces so Results tab
    and Analytics work without modification.

    Phase 4.1 PR2: added keyword-only `submission_id` for Celery idempotent upsert.
    When None (legacy callers), the key is omitted from the returned record so the
    record shape is unchanged. When provided, `_upsert_result_by_submission_id`
    uses it to de-duplicate across Celery retries.
    """
    percentage = round((score / total_possible * 100) if total_possible > 0 else 0)
    record = {
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
    if submission_id:
        record["submission_id"] = submission_id
    return record


# ══════════════════════════════════════════════════════════════
# Phase 2 Hotfix 1 — observability helpers for NEEDS_ALERT catches.
#
# These helpers wrap sub-steps of the grading thread that previously
# swallowed exceptions silently. Each one: calls the real work inside
# try/except, logs the error, and calls sentry_sdk.capture_exception
# so BetterStack sees the failure. No behavior change on the happy
# path.
# ══════════════════════════════════════════════════════════════


def _safe_generate_feedback(**kwargs):
    """Call assignment_grader.generate_feedback; capture to Sentry on failure
    and return a safe fallback so the grading thread can continue."""
    try:
        return generate_feedback(**kwargs)
    except Exception as e:
        # Issue #224: TransientError must bubble so Celery's autoretry
        # can fire — same rationale as `grade_written_questions` above.
        from backend.tasks.grading_tasks import TransientError
        if isinstance(e, TransientError):
            raise
        logger.error("Feedback generation failed: %s", e)
        sentry_sdk.capture_exception(e)
        return {
            "feedback": "Grading complete. Teacher will review and provide detailed feedback.",
            "rubric_breakdown": {},
        }


def _safe_save_results(results, teacher_id):
    """Persist results to teacher storage; capture to Sentry on failure."""
    try:
        from backend.grading.state import save_results
        save_results(results, teacher_id)
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.error("Failed to save result to teacher storage: %s", e)
        sentry_sdk.capture_exception(e)


def _upsert_result_by_submission_id(existing_results, new_record):
    """Phase 4.1 PR2: idempotent upsert of a teacher result record.

    If new_record has a `submission_id`, remove any existing record with the same
    submission_id before appending. Records without submission_id (legacy) append
    unconditionally — safe, just not de-duped.

    Returns a NEW list (pure function — does not mutate the input).
    Safe to call on every Celery retry: multiple retries of the same task
    converge on exactly one record per submission_id.
    """
    submission_id = new_record.get('submission_id')
    if submission_id:
        filtered = [r for r in existing_results if r.get('submission_id') != submission_id]
    else:
        filtered = list(existing_results)
    filtered.append(new_record)
    return filtered


def _is_stale_claim(started_at_iso, minutes=15):
    """True if started_at is older than `minutes` ago (reclaim allowed).

    Phase 4.1 PR2 subtask 3a: treat unparseable/None timestamps as stale so a
    malformed row never permanently blocks reclaim. Default TTL matches the
    Celery task soft-timeout ceiling.

    WORKER-LOSS REDELIVERY (pinned by tests in test_grading_tasks.py):
    Celery's acks_late + reject_on_worker_lost redelivery preserves the
    original message body, including the task_id (embedded as `id` in the
    message body and `correlation_id` in headers — see celery/app/amqp.py
    as_task_v2). So when a worker dies mid-grade and the broker redelivers,
    the redelivered task's self.request.id == the claim's grading_task_id.
    The dedup branch `current_task == task_id` fires and grading PROCEEDS
    on the redelivered run (see grade_portal_submission_sync:536). No
    worker-loss gap exists for the default Celery redelivery path.

    This TTL is therefore a BACKSTOP — it covers edge cases the task_id
    equality branch doesn't:
      - Manual re-enqueue from ops with a newly-minted task_id
      - Hypothetical future code that calls self.retry(task_id=...) with
        a different id (Celery 5.x default retry preserves task_id; don't
        change this without re-examining the dedup contract)
      - Schema/data corruption where grading_task_id is null-ish but
        status is 'grading_in_progress'

    Manual reclaim SQL (use only when the TTL doesn't fire in time):
        UPDATE submissions
        SET status='queued', grading_task_id=NULL, grading_started_at=NULL
        WHERE status='grading_in_progress'
          AND grading_started_at < now() - interval '30 minutes';
    """
    if not started_at_iso:
        return True
    from datetime import timedelta
    try:
        started = datetime.fromisoformat(started_at_iso.replace('Z', '+00:00'))
        return started < datetime.now(timezone.utc) - timedelta(minutes=minutes)
    except (ValueError, TypeError, AttributeError):
        return True  # unparseable → stale


def fetch_submission_full_context(path_type, submission_id, teacher_id):
    """Re-fetch submission + assessment + teacher config + accommodations from Supabase.

    Phase 4.1 PR2 subtask 3b: used by the Celery task to rebuild full grading
    context without a Flask session. Returns None if the submission is not
    found or Supabase is unavailable so the task can return early.

    Accommodations source:
      - The `submissions` table does NOT have a `student_accommodations` column
        (verified against backend/database/supabase_schema.sql and the Phase 4.1
        PR0 additive migration — only status/grading_task_id/grading_started_at/
        error_message were added).
      - The canonical source for join-code path is
        `published_assessments.settings.student_accommodations`, mirroring the
        existing inline extraction at backend/routes/student_portal_routes.py:807
        (`published_accommodations = assessment_data.get("settings", {}).get("student_accommodations", {})`).
      - For Phase 4.1b class-based path, `student_submissions.accommodations`
        MAY exist — handle gracefully as a fallback.
    """
    from backend.supabase_client import get_supabase
    from backend.services.grading_service import load_teacher_config

    sb = get_supabase()
    if not sb or not submission_id:
        return None
    repo = repository_for(path_type, sb)
    try:
        row = sb.table(repo.table_name).select('*').eq('id', submission_id).single().execute()
    except Exception as e:
        # FERPA: hash submission_id — see Codex audit MAJOR #14 round-4.
        logger.error("fetch_submission_full_context: submission fetch failed %s: %s",
                     hashlib.sha256(str(submission_id).encode()).hexdigest()[:8], e)
        sentry_sdk.capture_exception(e)
        # Closes audit MAJOR #7 round-1 finding 3 (Codex 2026-05-06):
        # transient supabase 5xx during context fetch must propagate so
        # Celery's autoretry catches them. Permanent errors (schema mismatch,
        # auth failure) still return None so the caller's existing
        # "no row → mark failed" flow handles them.
        from backend.retry import is_retryable_error
        if is_retryable_error(e):
            raise
        return None
    if not row or not getattr(row, 'data', None):
        return None
    data = row.data

    # Load assessment — join-code path uses assessment_id → published_assessments;
    # class-based path stores assessment inline on the row. Handle both.
    # Capture the full published_assessments row so we can pull `settings`
    # for accommodations below (join-code path only).
    assessment = None
    published_settings = {}
    if data.get('assessment_id'):
        try:
            a_row = sb.table('published_assessments').select('*').eq(
                'id', data['assessment_id']
            ).single().execute()
            if a_row and getattr(a_row, 'data', None):
                assessment = a_row.data.get('assessment') or a_row.data.get('content')
                published_settings = a_row.data.get('settings') or {}
        except Exception as e:
            # Capture so broker/schema failures surface instead of looking
            # like "no accommodations." Matches the _fetch_submission_row
            # pattern fixed in Subtask 3b.
            logger.error("Failed to fetch published_assessments %s: %s",
                         data.get('assessment_id'), str(e))
            sentry_sdk.capture_exception(e)
            # Closes audit MAJOR #7 round-2 (Codex 2026-05-06): transient
            # supabase 5xx fetching the published_assessments row must
            # propagate so Celery autoretries — otherwise this is the
            # "ctx with assessment=None → mark failed" silent-loss path
            # that Codex round-2 caught. Permanent errors (schema/auth)
            # continue to the existing fall-through below where assessment
            # may resolve from the inline data field.
            from backend.retry import is_retryable_error
            if is_retryable_error(e):
                raise
    if assessment is None:
        assessment = data.get('assessment') or data.get('content')

    teacher_config = load_teacher_config(teacher_id)

    # Student accommodations resolution order:
    #   1. published_assessments.settings.student_accommodations (join-code canonical)
    #   2. submission row's `accommodations` column (class-based 4.1b-forward)
    #   3. None → pipeline falls through to the "no accommodations" path
    # We do NOT read data.get('student_accommodations') because that column
    # does not exist on the submissions table.
    student_accommodations = (
        published_settings.get('student_accommodations')
        or data.get('accommodations')
        or None
    )

    # student_info / return-dict assembly + the per-path student_id branch
    # are now owned by SubmissionRepository.normalize_context (relocated
    # VERBATIM from the prior inline block). The accommodations 3-tier
    # resolution above STAYS here (carry-forward #3): the repository never
    # reads the accommodations source, it only receives the already-resolved
    # value via base_context.
    return repo.normalize_context(data, base_context={
        'assessment': assessment,
        'teacher_config': teacher_config,
        'student_accommodations': student_accommodations,
    })


def _finalize_portal_grading(all_questions, answers, written_results, ai_notes, ai_model,
                             history_context, student_info, assessment, teacher_config, teacher_id,
                             submission_id, repo):
    """Combine instant + written scores, generate overall feedback, build
    the result record, persist it to teacher storage + the submission row,
    update student history, and emit the AUDIT-complete log.

    Extracted verbatim from grade_portal_submission_sync (CQ7 god-function
    split). Called inside the parent's try/except; raises propagate to the
    parent's failure handler unchanged. Behavior pinned by
    tests/test_portal_grading_golden.py.
    """
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
                    "standard": q.get("standard"),
                    "dok": q.get("dok"),
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
                    "standard": q.get("standard"),
                    "dok": q.get("dok"),
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
                            logger.warning("Answer-key definition for term %r not in definitions list; match ungradable", term)
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
                "standard": q.get("standard"),
                "dok": q.get("dok"),
            })

    # Generate overall feedback via Pass 3
    feedback_text = ""
    breakdown = {"content_accuracy": 0, "completeness": 0, "writing_quality": 0, "effort_engagement": 0}
    student_responses = []
    for q in all_questions:
        answer_key = q.get("_answer_key", "")
        student_responses.append({
            "question": q.get("question", ""),
            "answer": answers.get(answer_key, ""),
        })

    percentage = round((total_score / total_possible * 100) if total_possible > 0 else 0)
    letter = _score_to_letter(percentage)

    feedback_result = _safe_generate_feedback(
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
        student_name=student_info.get("student_name", ""),
    )
    feedback_text = feedback_result.get("feedback", "") or feedback_text
    breakdown = feedback_result.get("rubric_breakdown", breakdown)

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
        submission_id=submission_id,
    )

    # Save to teacher's results storage (for Results tab + Analytics)
    # Use per-teacher lock to prevent race conditions with concurrent submissions.
    # Outer try catches load/lock failures; inner _safe_save_results covers save_results.
    try:
        from backend.grading.state import load_saved_results, _get_lock
        with _get_lock(teacher_id):
            results = load_saved_results(teacher_id)
            results = _upsert_result_by_submission_id(results, result_record)  # Phase 4.1 PR2: idempotent upsert
            _safe_save_results(results, teacher_id)
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.error("Failed to load/lock for result save: %s", str(e))
        sentry_sdk.capture_exception(e)

    # Update Supabase submission record with full grading (single write includes
    # status='graded' so teacher dashboards and retry-detection both observe it).
    standards_mastery = _build_standards_mastery(per_question_scores)
    repo.update(submission_id, {
        "results": {
            "questions": per_question_scores,
            "score": total_score,
            "total_points": total_possible,
            "percentage": round((total_score / total_possible * 100) if total_possible > 0 else 0),
            "feedback_summary": feedback_text,
            "breakdown": breakdown,
            "grading_source": "multipass",
            "standards_mastery": standards_mastery,
        },
        "score": total_score,
        "percentage": round((total_score / total_possible * 100) if total_possible > 0 else 0),
        "status": "graded",
    })

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
    except Exception as e:  # noqa: BLE001  # broad catch: error is logged
        logger.error("Failed to update student history: %s", str(e))

    # FERPA: hash both submission_id and student_name (Codex MAJOR #14
    # round-6). AUDIT-tier log so it's prominent in BetterStack; raw IDs
    # would leak via Sentry breadcrumbs on any subsequent capture.
    logger.info(
        "AUDIT: Portal grading complete: submission=%s student=%s score=%d/%d",
        hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
        hashlib.sha256(str(student_info.get("student_name", "")).encode()).hexdigest()[:8],
        total_score,
        total_possible,
    )


def grade_portal_submission_sync(
    submission_id,
    assessment,
    answers,
    student_info,
    teacher_config,
    teacher_id,
    # Slice 5 PR2 Task 2.4: renamed supabase_table -> path_type. Default kept
    # as the legacy table-name STRING (SubmissionPathType.CLASS.value ==
    # "student_submissions") so repository_for() coerces it correctly.
    path_type=SubmissionPathType.CLASS.value,
    student_accommodations=None,
    *,
    task_id=None,
    district_id=None,
    user_id=None,
    raise_transient=False,
):
    """Pure grading function — no Flask context required.

    Phase 4.1 PR2 subtask 3a: extracted body of run_portal_grading_thread.
    Accepts all dependencies as explicit parameters so the Celery task can
    call it without a Flask request context.

    Args:
        submission_id: Supabase ID of the submission record
        assessment: The published assessment/assignment content
        answers: Student's answers dict (keys are "{sIdx}-{qIdx}" format)
        student_info: Dict with student_name, student_id, email
        teacher_config: Dict with global_ai_notes, grade_level, subject, grading_style,
                       rubric, ai_model, period
        teacher_id: Teacher's user ID for results storage
        path_type: "submissions" for join-code, "student_submissions" for class-based
            (or the SubmissionPathType enum; repository_for() coerces either form).
        student_accommodations: Embedded accommodations dict from published content
        task_id: Celery task id; when set enables row-level dedup claim. None for
            the legacy thread path (skips dedup).
        district_id: District context for api_keys lookup (passed through explicitly
            so no Flask g access is required).
        user_id: Acting user id (reserved for future audit). Currently unused by
            the grading body but accepted for parity with the Celery call site.
    """
    from backend.supabase_client import get_supabase
    sb = get_supabase()

    # PR2: the per-path fetch/claim/update seams now route through
    # SubmissionRepository (repository_for coerces the enum OR the legacy
    # table-name string the thread/Celery callers still pass). The
    # _is_stale_claim dedup DECISION below stays VERBATIM in this pipeline
    # caller (carry-forward #2): it is pipeline-scoped, has its own direct
    # test caller, and is intentionally NOT moved into the repository.
    repo = repository_for(path_type, sb)

    # Row-level dedup (Celery path only — task_id=None skips this entirely)
    if task_id and submission_id:
        current = repo.fetch(submission_id)
        if current and current.get('status') == 'grading_in_progress':
            current_task = current.get('grading_task_id')
            if current_task == task_id:
                pass  # same task retrying — proceed (idempotent re-run)
            elif not _is_stale_claim(current.get('grading_started_at')):
                logger.info(
                    "Submission %s already being graded by task %s — skipping",
                    hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
                    current_task,
                )
                return  # another live worker owns it — skip
            # else: stale → fall through to reclaim
        repo.claim_for_grading(submission_id, task_id)

    try:
        # FERPA: hash submission_id — see Codex audit MAJOR #14 round-6.
        # An info-level log can ride a later capture_exception via Sentry's
        # logging integration (breadcrumbs), so even non-error logs leak.
        # student_name is also redacted — set_user upstream uses a hash.
        logger.info(
            "Portal grading started: submission=%s",
            hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
        )

        # Build AI instruction string with all grading factors
        accommodation_prompt = ""
        student_name = student_info.get("student_name", "")
        # Initialize student_id at the top so it's defined for the history-context
        # block below regardless of which accommodation strategy hits. Codex review
        # caught that the prior version only set student_id inside the Strategy 2
        # branch — when Strategy 1 succeeded, student_id was unbound and the
        # downstream load_student_history call raised UnboundLocalError. Pre-PR
        # the bare `except Exception: pass` swallowed it; the explicit log path
        # surfaces it.
        student_id = student_info.get("student_id", "")

        # Strategy 1: Use embedded accommodations from published content (works for both paths)
        if student_accommodations and student_name:
            try:
                from backend.accommodations import build_prompt_from_student_accommodations
                accommodation_prompt = build_prompt_from_student_accommodations(
                    student_name, student_accommodations, teacher_id
                )
            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                # Best-effort lookup: Strategy 2 below is the fallback. Debug-level
                # only — failure here is not user-visible. Log student_id (not
                # student_name) to avoid avoidable PII in log lines.
                logger.debug("build_prompt_from_student_accommodations failed for student_id=%s: %s", student_id, e)

        # Strategy 2: Fall back to student_id lookup (works for class-based with roster data)
        if not accommodation_prompt and student_id:
            try:
                from backend.accommodations import build_accommodation_prompt
                accommodation_prompt = build_accommodation_prompt(student_id, teacher_id)
            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                # Best-effort: if both strategies fail, the student gets no
                # accommodation prompt. Debug-level only.
                logger.debug("build_accommodation_prompt failed for student_id=%s: %s", student_id, e)

        # Build student history context
        history_context = ""
        try:
            from backend.storage import load_student_history
            history = load_student_history(teacher_id, student_id)
            if history:
                history_context = str(history)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: history is optional context. Debug-level only.
            logger.debug("load_student_history failed for student_id=%s: %s", student_id, e)

        # Build correction context from teacher edit history
        _correction_ctx = ""
        try:
            from backend.services.correction_patterns import build_correction_context
            _q_types = list(set(q.get("question_type", "short_answer") for q in questions if q.get("question_type")))
            if not _q_types:
                _q_types = ["short_answer", "multiple_choice"]
            _correction_ctx = build_correction_context(teacher_id, teacher_config.get("subject", ""), _q_types)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Best-effort: correction context is optional. Debug-level only.
            logger.debug("build_correction_context failed for teacher %s: %s", teacher_id, e)

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
            correction_context=_correction_ctx,
        )

        # Add rubric prompt if available
        rubric = teacher_config.get("rubric")
        if rubric and rubric.get("categories"):
            from backend.services.rubric_formatting import format_rubric_for_prompt
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

        # Set API keys for this thread — pass district_id explicitly so the
        # resolver doesn't need to reach into flask.g on the Celery path.
        try:
            from backend.api_keys import set_thread_keys, resolve_keys_for_teacher
            keys = resolve_keys_for_teacher(teacher_id, district_id=district_id)
            if keys:
                set_thread_keys(keys)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # If key resolution fails, grading falls back to whatever
            # backend.api_keys._get_api_key can find (thread-context, district
            # admin, or env), not the intended teacher/district keys. That can
            # mean stale keys or rate-limit issues that surface as confusing
            # downstream errors. Capture in Sentry so the resolver failure is
            # visible at the source instead of silently degrading.
            logger.error("resolve_keys_for_teacher failed for teacher %s (district %s): %s",
                         teacher_id, district_id, e)
            sentry_sdk.capture_exception(e)

        written_results = grade_written_questions(
            questions=written_questions,
            answers=answers,
            ai_notes=ai_notes,
            grade_level=teacher_config.get("grade_level", ""),
            subject=teacher_config.get("subject", ""),
            grading_style=teacher_config.get("grading_style", "standard"),
            ai_model=ai_model,
            student_name=student_info.get("student_name", ""),
        )

        _finalize_portal_grading(
            all_questions, answers, written_results, ai_notes, ai_model,
            history_context, student_info, assessment, teacher_config,
            teacher_id, submission_id, repo,
        )

    except Exception as e:
        logger.error("Portal grading failed: %s", str(e))
        # Page via BetterStack: the wrapper's @critical_path tags only ESCAPING
        # exceptions, and this outer except swallows. Capture explicitly before
        # cleanup. (Celery callers re-raise after their own capture; this keeps
        # thread-path parity.)
        sentry_sdk.capture_exception(e)

        # Closes audit MAJOR #7 (Codex 2026-05-06): when called from Celery
        # (raise_transient=True) AND the exception is classified transient
        # (httpx timeout, OpenAI 5xx, supabase 503, etc.), re-raise as
        # TransientError so Celery's autoretry_for kicks in. Skip the
        # "mark as grading_failed" step — the row stays in its current
        # claim state so the retry's _claim_submission_for_grading sees
        # `current_task == task_id` and proceeds idempotently. After
        # retry exhaustion, PortalGradingTask.on_failure marks the row
        # 'failed'.
        if raise_transient:
            from backend.retry import is_retryable_error
            if is_retryable_error(e):
                from backend.tasks.grading_tasks import TransientError
                raise TransientError(str(e)[:500]) from e

        # Update submission status to grading_failed so it doesn't stay in 'partial' forever
        try:
            if sb and submission_id:
                repo.update(submission_id, {
                    "status": "grading_failed",
                })
                # FERPA: hash submission_id — Codex audit MAJOR #14 round-6.
                logger.info(
                    "Marked submission %s as grading_failed",
                    hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
                )
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            # Critical: if we can't mark a submission as failed, it stays in
            # 'partial' forever and never retries. Sentry must see this.
            # FERPA: hash submission_id — see Codex audit MAJOR #14 round-4.
            logger.error(
                "Failed to mark submission %s as grading_failed: %s",
                hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
                e,
            )
            sentry_sdk.capture_exception(e)


@critical_path
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
                              teacher_config, teacher_id,
                              # Slice 5 PR2 Task 2.4: renamed supabase_table ->
                              # path_type. Default keeps the legacy string value
                              # so repository_for() coerces it correctly.
                              path_type=SubmissionPathType.CLASS.value,
                              student_accommodations=None):
    """Phase 4.1 PR2 subtask 3a: thin wrapper that preserves the original signature.

    Class-based path (student_account_routes) and the join-code thread fallback
    (student_portal_routes + the future Celery-enqueue fallback) keep using this
    entry point unchanged. Responsibilities retained in the wrapper:
      - _active_threads lifecycle tracking (for graceful SIGTERM handling)
      - _shutdown_event check (skip grading if Railway is redeploying)
      - Extract user_id + district_id from flask.g and pass them explicitly

    The actual grading pipeline lives in grade_portal_submission_sync, which
    has no Flask dependencies so the Celery task body (subtask 3b) can call it
    directly.
    """
    current_thread = threading.current_thread()
    _active_threads.add(current_thread)
    try:
        if _shutdown_event.is_set():
            # FERPA: hash submission_id — Codex audit MAJOR #14 round-6.
            # logger.info also rides Sentry capture_exception breadcrumbs.
            sub_hash = hashlib.sha256(str(submission_id).encode()).hexdigest()[:8]
            logger.info("Shutdown in progress — skipping grading for submission %s", sub_hash)
            try:
                if submission_id:
                    # PR2 Task 2.2: route through the DI provider; the repo's
                    # internal `if not self._sb` guard handles the None-client
                    # case (no write when client is None — observable effect
                    # identical to the old `if sb and submission_id` gate).
                    from backend.providers import get_submission_repository
                    get_submission_repository(path_type).update(
                        submission_id, {"status": "grading_deferred"}
                    )
            except Exception as e:  # noqa: BLE001  # broad catch: error is logged
                # Critical: status state matters. If we can't mark deferred,
                # the submission stays in 'partial' through the redeploy and
                # may not auto-retry on the new instance.
                logger.error("Failed to mark submission %s as grading_deferred during shutdown: %s",
                             sub_hash, e)
                sentry_sdk.capture_exception(e)
            return

        try:
            from flask import g as _flask_g
            user_id = getattr(_flask_g, 'user_id', None)
            district_id = getattr(_flask_g, 'district_id', None)
        except (RuntimeError, ImportError):
            user_id = None
            district_id = None

        grade_portal_submission_sync(
            submission_id=submission_id,
            assessment=assessment,
            answers=answers,
            student_info=student_info,
            teacher_config=teacher_config,
            teacher_id=teacher_id,
            path_type=path_type,
            student_accommodations=student_accommodations,
            task_id=None,  # legacy thread path skips row-level dedup
            district_id=district_id,
            user_id=user_id,
        )
    finally:
        _active_threads.discard(current_thread)
