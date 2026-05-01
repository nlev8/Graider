"""
Student Assessment Portal Routes for Graider.
Handles publishing assessments, student access via join codes, and submission grading.
Uses Supabase for cloud storage - students can submit anytime.
"""
import json
import logging
import os
import random
import string
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as get_supabase
# Phase 4.5: this module has MIXED auth paths. Teacher-authenticated
# handlers use _get_teacher_supabase() so their requests land under RLS
# when USE_PER_USER_JWT=1. Anonymous join-code paths
# (/api/student/join/<code>, /api/student/submit/<code>) and the
# generate_join_code() uniqueness-check helper stay on service-role
# via get_supabase() — they have no teacher JWT.
from backend.supabase_client_scoped import get_request_supabase as _get_teacher_supabase

student_portal_bp = Blueprint('student_portal', __name__)
_logger = logging.getLogger(__name__)

from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import error_response, handle_route_errors
from backend.extensions import limiter
from backend.services.grading_service import grade_deterministic_question, grade_student_submission, grade_instant_only
# Phase 4.2 #12 / Phase 4.3 Sprint 2: shared DOK helpers live in
# backend/services/dok.py — see that module's docstring for rationale.
from backend.services.dok import (
    DOK_OPTIONS,
    DOK_DESCRIPTIONS,
    REMEDIATION_DOK_DEFAULT,
    _validate_dok,
    _derive_uniform_dok,
)
from backend.observability import critical_path


def _spawn_thread_grading(submission_id, assessment, answers, student_info,
                         teacher_config, teacher_id, supabase_table,
                         student_accommodations):
    """Thread-based portal grading spawn.

    Used for (a) the Celery enqueue-failure fallback on the join-code path
    (Redis outage → thread so the student doesn't lose their submission)
    and (b) the class-based submission path in student_account_routes.py,
    which remains thread-backed until Phase 4.1b migrates it to Celery.

    Preserves run_portal_grading_thread's full 8-arg contract including
    accommodations.
    """
    import threading
    from backend.services.portal_grading import run_portal_grading_thread
    thread = threading.Thread(
        target=run_portal_grading_thread,
        args=(submission_id, assessment, answers, student_info,
              teacher_config, teacher_id, supabase_table, student_accommodations),
        daemon=True,
    )
    thread.start()


def generate_join_code():
    """Generate a unique 6-character join code (e.g., 'ABC123')."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    while True:
        code = ''.join(random.choices(chars, k=6))
        # Uniqueness check must see ALL existing codes across all teachers,
        # so we stay on service-role here even when USE_PER_USER_JWT=1.
        # Per-user RLS would limit visibility to current teacher's codes
        # and increase collision probability.
        db = get_supabase()
        result = db.table('published_assessments').select('id').eq('join_code', code).execute()
        if len(result.data) == 0:
            return code


def _parse_ts(ts):
    """Parse an ISO timestamp string to a datetime for safe comparison.
    Returns datetime.min if parsing fails so unparseable timestamps sort last.
    """
    if not ts:
        return datetime.min
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return datetime.min


def _coalesce(*vals, default=None):
    """Return the first non-None value among `vals`, or `default` if all are None.

    Use this instead of Python's `or` for fallback chains where 0 / "" / False
    are legitimate values. `or` short-circuits on falsy, corrupting numeric/text
    fallbacks (e.g., a legitimate `points_earned = 0` would silently become the
    fallback's value).
    """
    for v in vals:
        if v is not None:
            return v
    return default


def _find_content_row(db, content_id, teacher_id):
    """Locate a published content row by ID in either published_assessments
    or published_content, verifying teacher ownership.

    Returns (table_name, row_dict) or (None, None) if not found.
    """
    pa = db.table('published_assessments').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pa.data:
        row = pa.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_assessments', row)

    pc = db.table('published_content').select('id, settings, teacher_id').eq(
        'id', content_id
    ).execute()
    if pc.data:
        row = pc.data[0]
        if row.get('teacher_id') != teacher_id:
            return (None, None)
        return ('published_content', row)

    return (None, None)


def _select_submissions_by_mode(submissions_by_content, attempt_mode):
    """Given a dict of content_id -> list of submissions, return one selected
    submission per content based on attempt_mode.

    attempt_mode: 'latest' | 'best' | 'average'
    For 'average', returns all submissions; caller handles averaging.

    Tie-breaking:
    - 'latest': prefers higher attempt_number, then newer submitted_at (parsed)
    - 'best': prefers higher percentage, then newer submitted_at (parsed) on ties
    - 'average': no selection; all submissions used
    """
    selected = {}
    for content_id, subs in submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'best':
            best = max(subs, key=lambda s: (
                s.get('percentage') or 0,
                _parse_ts(s.get('submitted_at')),
                s.get('attempt_number') or 0,
            ))
            selected[content_id] = [best]
        elif attempt_mode == 'average':
            selected[content_id] = subs
        else:  # 'latest' (default)
            latest = max(subs, key=lambda s: (
                s.get('attempt_number') or 0,
                _parse_ts(s.get('submitted_at')),
            ))
            selected[content_id] = [latest]
    return selected


def _aggregate_mastery_for_student(selected_submissions_by_content, content_titles, attempt_mode):
    """Aggregate standards_mastery across submissions into a per-standard dict.

    Input: { content_id: [submission, ...] } (one per content unless attempt_mode=='average')
    Output: { standard_code: { percentage, points_earned, points_possible, question_count, contributing_submissions } }
    """
    from collections import defaultdict
    totals = defaultdict(lambda: {
        'points_earned': 0.0,
        'points_possible': 0.0,
        'question_count': 0,
        'contributing_submissions': [],
    })

    for content_id, subs in selected_submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'average' and len(subs) > 1:
            # Average each standard's percentage across attempts, then scale
            per_standard_avg = defaultdict(lambda: {'pct_sum': 0.0, 'count': 0, 'pts_poss': 0, 'q_count': 0, 'attempts': []})
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    pct = (m.get('points_earned', 0) / m['points_possible']) * 100
                    per_standard_avg[code]['pct_sum'] += pct
                    per_standard_avg[code]['count'] += 1
                    per_standard_avg[code]['pts_poss'] = m.get('points_possible', 0)
                    per_standard_avg[code]['q_count'] = m.get('question_count', 0)
                    per_standard_avg[code]['attempts'].append({
                        'submission_id': sub.get('id'),
                        'attempt_number': sub.get('attempt_number', 1),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                    })
            for code, agg in per_standard_avg.items():
                avg_pct = agg['pct_sum'] / agg['count']
                totals[code]['points_earned'] += (avg_pct / 100.0) * agg['pts_poss']
                totals[code]['points_possible'] += agg['pts_poss']
                totals[code]['question_count'] += agg['q_count']
                # In average mode, record each contributing attempt individually
                for a in agg['attempts']:
                    totals[code]['contributing_submissions'].append({
                        'submission_id': a['submission_id'],
                        'title': content_titles.get(content_id, ''),
                        'points_earned': a['points_earned'],
                        'points_possible': a['points_possible'],
                        'attempt_number': a['attempt_number'],
                    })
        else:
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    totals[code]['points_earned'] += m.get('points_earned', 0)
                    totals[code]['points_possible'] += m['points_possible']
                    totals[code]['question_count'] += m.get('question_count', 0)
                    totals[code]['contributing_submissions'].append({
                        'submission_id': sub.get('id'),
                        'title': content_titles.get(content_id, ''),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                        'attempt_number': sub.get('attempt_number', 1),
                    })

    # Compute final percentages and cap contributing_submissions at 10 (most recent first)
    result = {}
    for code, t in totals.items():
        pct = round((t['points_earned'] / t['points_possible']) * 100, 1) if t['points_possible'] > 0 else 0
        # Sort contributing submissions by attempt_number desc before capping
        contributing = sorted(
            t['contributing_submissions'],
            key=lambda c: c.get('attempt_number') or 0,
            reverse=True,
        )[:10]
        result[code] = {
            'percentage': pct,
            'points_earned': round(t['points_earned'], 2),
            'points_possible': t['points_possible'],
            'question_count': t['question_count'],
            'contributing_submissions': contributing,
        }
    return result


def _build_standards_breakdown_for_student(mastery_by_code, submission_lookup):
    """Convert _aggregate_mastery_for_student's dict output to the
    standards_breakdown array shape required by the report-card endpoint.

    - Sorts ASC by percentage (worst-first) per Phase 2b spec.
    - Enriches each contributing_submission with `submitted_at` and
      `percentage` (computed from points_earned / points_possible).
      Pulls `submitted_at` from `submission_lookup` (a dict keyed by
      submission_id). Keeps the existing 10-cap from the upstream helper.

    Args:
        mastery_by_code: dict from _aggregate_mastery_for_student
        submission_lookup: dict[submission_id -> submission row] for enrichment
    Returns:
        list[dict] sorted by percentage ASC; each dict has
        {code, percentage, points_earned, points_possible, question_count,
         contributing_submissions: [...]} with each contributing_submission
        having submission_id, title, attempt_number, points_earned,
        points_possible, percentage, submitted_at.
    """
    rows = []
    for code, m in mastery_by_code.items():
        enriched_contribs = []
        for c in m.get("contributing_submissions", []):
            pts_poss = c.get("points_possible") or 0
            pts_earned = c.get("points_earned") or 0
            pct = round((pts_earned / pts_poss) * 100, 1) if pts_poss > 0 else 0.0
            sub_row = submission_lookup.get(c.get("submission_id")) or {}
            enriched_contribs.append({
                "submission_id": c.get("submission_id"),
                "title": c.get("title", ""),
                "attempt_number": c.get("attempt_number"),
                "points_earned": pts_earned,
                "points_possible": pts_poss,
                "percentage": pct,
                "submitted_at": sub_row.get("submitted_at"),
            })
        rows.append({
            "code": code,
            "percentage": m.get("percentage", 0),
            "points_earned": m.get("points_earned", 0),
            "points_possible": m.get("points_possible", 0),
            "question_count": m.get("question_count", 0),
            "contributing_submissions": enriched_contribs,
        })
    rows.sort(key=lambda r: r["percentage"])  # ASC = worst-first
    return rows


def _build_trajectory_for_student(submissions, content_titles):
    """Build the chronological trajectory array for the report card.

    Sorted ASC by submitted_at; submissions with null submitted_at are
    appended at the END (we treat them as the "most recent" since their
    real position is unknown, and we'd rather not pollute the early-trend
    reading).

    Args:
        submissions: list of submission rows (id, content_id, submitted_at,
                     percentage, attempt_number, results.points_earned/possible).
        content_titles: dict[content_id -> title] for the title field.
    Returns:
        list[dict] of {submission_id, content_id, title, submitted_at,
                       percentage, attempt_number, points_earned,
                       points_possible}.
    """
    def sort_key(s):
        ts = s.get("submitted_at")
        # Use _parse_ts so mixed ISO formats ("Z" vs "+00:00" suffix) sort
        # by actual instant rather than by raw string. Null/empty timestamps
        # sort to bucket 1 (END), non-null to bucket 0 (chronological).
        return (0, _parse_ts(ts)) if ts else (1, datetime.min)

    sorted_subs = sorted(submissions, key=sort_key)
    out = []
    for s in sorted_subs:
        results = s.get("results") or {}
        out.append({
            "submission_id": s.get("id"),
            "content_id": s.get("content_id"),
            "title": content_titles.get(s.get("content_id"), ""),
            "submitted_at": s.get("submitted_at"),
            "percentage": s.get("percentage"),
            "attempt_number": s.get("attempt_number"),
            "points_earned": results.get("points_earned"),
            "points_possible": results.get("points_possible"),
        })
    return out


def _normalize_mastery_shape(raw):
    """Convert old flat shape -> new {overall, by_dok} shape; pass new through.

    Phase 4.3 Sprint 2 — the single boundary adapter for both shapes.

    Old flat shape (`{points_earned, points_possible, question_count, percentage}`)
    is wrapped into `{overall: <flat fields>, by_dok: {}}`. Pre-Sprint-2 stored
    JSONB has this shape. Aggregator output may also include `percentage` and
    `contributing_submissions` — both are preserved into `overall`.

    New shape (`{overall, by_dok}`) is passed through with sub-structure
    validation: by_dok keys are normalized via _validate_dok (handles
    "3" -> 3 from JSON serialization), and any non-dict per-DOK value is
    dropped.

    Returns None for malformed input (non-dict raw).
    """
    if not isinstance(raw, dict):
        return None
    if 'overall' in raw:
        overall = raw['overall'] if isinstance(raw['overall'], dict) else {}
        by_dok_raw = raw.get('by_dok') if isinstance(raw.get('by_dok'), dict) else {}
        by_dok = {}
        for k, v in by_dok_raw.items():
            normalized_k = _validate_dok(k)
            if normalized_k is not None and isinstance(v, dict):
                by_dok[normalized_k] = v
        return {'overall': overall, 'by_dok': by_dok}
    # Old flat shape — wrap.
    return {'overall': dict(raw), 'by_dok': {}}


def _sanitize_standards_mastery(sub):
    """Sanitize standards_mastery in a submission dict IN PLACE.

    Phase 4.3 Sprint 2: also normalizes shape via _normalize_mastery_shape.
    - Pre-Sprint-2 (old flat) entries get wrapped into {overall, by_dok: {}}
    - New shape entries pass through with sub-structure validation
    - Malformed entries (non-dict, or rejected by adapter) are dropped
    - Outer non-dict gets reset to {}

    Args:
        sub: a submission dict (mutated in place); typically the row
             from student_submissions.
    """
    results = sub.get('results') or {}
    raw = results.get('standards_mastery')
    if raw is None:
        results['standards_mastery'] = {}
        sub['results'] = results
        return
    if not isinstance(raw, dict):
        _logger.warning(
            "malformed standards_mastery (type=%s) in submission %s — treating as empty",
            type(raw).__name__, sub.get('id'),
        )
        results['standards_mastery'] = {}
        sub['results'] = results
        return
    cleaned = {}
    for code, entry in raw.items():
        normalized = _normalize_mastery_shape(entry)
        if normalized is None:
            _logger.warning(
                "malformed standards_mastery entry (code=%s, type=%s) in submission %s — skipping entry",
                code, type(entry).__name__, sub.get('id'),
            )
            continue
        cleaned[code] = normalized
    results['standards_mastery'] = cleaned
    sub['results'] = results


def _validate_and_clean_lesson(raw, *, teacher_id=None, class_id=None, standard_code=None):
    """Phase 4.2 #1: validate the AI-generated `lesson` dict and return a
    clean copy with EXACTLY the three known fields, or None if invalid.

    Drops unknown keys (no unbounded data leak into JSONB). Logs the
    specific failure reason. The caller treats None as "ship questions
    only, no lesson" — lesson is a nice-to-have, not load-bearing.

    Per-field constraints: non-empty string, ≤1500 chars after strip().
    """
    if not isinstance(raw, dict):
        _logger.warning(
            "remediation.lesson_invalid_dropped reason=not_dict teacher=%s class=%s standard=%s actual_type=%s",
            teacher_id, class_id, standard_code, type(raw).__name__,
        )
        return None
    cleaned = {}
    for field in ('intro', 'worked_example', 'key_takeaway'):
        val = raw.get(field)
        if not isinstance(val, str):
            _logger.warning(
                "remediation.lesson_invalid_dropped reason=missing_or_nonstring_%s teacher=%s class=%s standard=%s",
                field, teacher_id, class_id, standard_code,
            )
            return None
        stripped = val.strip()
        if not stripped:
            _logger.warning(
                "remediation.lesson_invalid_dropped reason=empty_%s teacher=%s class=%s standard=%s",
                field, teacher_id, class_id, standard_code,
            )
            return None
        if len(stripped) > 1500:
            _logger.warning(
                "remediation.lesson_oversize_dropped reason=%s_%dchars teacher=%s class=%s standard=%s",
                field, len(stripped), teacher_id, class_id, standard_code,
            )
            return None
        cleaned[field] = stripped
    return cleaned


# Phase 4.2 #8: per-student weekly cap on remediations.
# Spec: docs/superpowers/specs/2026-04-30-phase4.2-weekly-cap-design.md
REMEDIATION_PER_STUDENT_WEEKLY_CAP = 3

# Phase 4.2 #2: max students for personalized-mode class-wide generation.
# If red-tier resolves to MORE than this with at least one having
# accommodations, /remediate returns 422.
# Spec: docs/superpowers/specs/2026-04-30-phase4.2-perstudent-gen-design.md
REMEDIATION_PERSONALIZED_MAX = 10

# Phase 4.2 #3: pre-generation config dialog params.
# Spec: docs/superpowers/specs/2026-04-30-phase4.2-pregen-config-design.md
REMEDIATION_COUNT_MIN = 3
REMEDIATION_COUNT_MAX = 15
REMEDIATION_COUNT_DEFAULT = 8
DIFFICULTY_OPTIONS = ('easier', 'same', 'harder')
REMEDIATION_DIFFICULTY_DEFAULT = 'same'


def _check_remediation_cap(db, teacher_id, target_student_ids):
    """Phase 4.2 #8: returns a list of capped student IDs (those who would
    exceed the per-(teacher, student) weekly cap if a new remediation
    targeting them were published now). Empty list = clear to publish.

    Counting basis: every published_content row with target_student_ids
    containing the student, created_at >= now() - 7 days, regardless of
    is_active. Recall does NOT refund the slot — recall is an audit/
    visibility action, not a quota refund (otherwise publish/recall/
    republish would bypass the cap).

    Cross-class scope: per-teacher across all classes (the harm is student
    saturation, not class saturation).

    Mock-friendly: avoids PostgREST JSONB containment operator. Fetches
    by teacher_id + cutoff date, then Python-filters by membership.
    """
    from datetime import datetime, timedelta, timezone
    if not target_student_ids:
        return []
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()

    rows = db.table('published_content').select(
        'id, target_student_ids, created_at'
    ).eq('teacher_id', teacher_id).gte('created_at', cutoff).execute()

    counts = {sid: 0 for sid in target_student_ids if sid}
    for row in (rows.data or []):
        targets = row.get('target_student_ids')
        if not isinstance(targets, list):
            # Defensive: malformed/non-list non-None values are skipped + logged.
            # None is the normal class-wide case; don't log that.
            if targets is not None:
                _logger.warning(
                    "remediation.cap.malformed_target_student_ids row=%s type=%s",
                    row.get('id'), type(targets).__name__,
                )
            continue
        for sid in counts:
            if sid in targets:
                counts[sid] = counts[sid] + 1

    return [sid for sid, c in counts.items() if c >= REMEDIATION_PER_STUDENT_WEEKLY_CAP]


def _difficulty_directive(difficulty, grade):
    """Phase 4.2 #3: map (difficulty, grade) → prompt directive.

    Clamps grade arithmetic to K-12 (Codex MINOR — no grade-13 references).
    For non-numeric grade strings, uses generic phrasing.
    """
    grade_num = None
    try:
        grade_num = int(str(grade).strip())
    except (ValueError, TypeError, AttributeError):
        pass

    if difficulty == 'easier':
        if grade_num is not None:
            target = max(1, grade_num - 1)
            return (
                f"Use simpler vocabulary and more scaffolding. "
                f"Aim for grade-{target} difficulty."
            )
        return (
            "Use simpler vocabulary and more scaffolding. "
            "Aim for content below the current grade level."
        )
    if difficulty == 'harder':
        if grade_num is not None:
            target = min(12, grade_num + 1)
            return (
                f"Use more challenging vocabulary and higher cognitive demand. "
                f"Include some grade-{target} concepts."
            )
        return (
            "Use more challenging vocabulary and higher cognitive demand. "
            "Include some content above the current grade level."
        )
    # 'same' (default)
    return "Difficulty: grade-level review."


def _build_remediation_prompt(*, grade, subject, standard_code, count=None, difficulty=None, dok=None):
    """Build the base prompt used by both shared and personalized remediation.

    Phase 4.2 #1 added the lesson section.
    Phase 4.2 #3 parameterized count + difficulty (Codex MAJOR — earlier
    duplicate inline shared-mode prompt is now removed; this function is
    the single source of truth for the prompt).
    Phase 4.2 #12 parameterized dok (1-4 or None=Auto). When set, the
    prompt orders DOK as the cognitive-rigor constraint and difficulty
    as vocab/scaffolding tone — so AI handles "DOK 4 + easier" coherently.

    `count` defaults to REMEDIATION_COUNT_DEFAULT and is used for:
      - "Generate exactly N..." in the prompt
      - MC/SA mix split: mc=round(N*0.6), sa=N-mc
    `difficulty` defaults to REMEDIATION_DIFFICULTY_DEFAULT and threads
    through `_difficulty_directive`.
    `dok` defaults to REMEDIATION_DOK_DEFAULT (None = no directive).
    When dok in DOK_OPTIONS, prompt requires per-question `dok: N` field
    and clarifies DOK + difficulty are orthogonal.
    """
    if count is None:
        count = REMEDIATION_COUNT_DEFAULT
    if difficulty is None:
        difficulty = REMEDIATION_DIFFICULTY_DEFAULT
    mc = round(count * 0.6)
    sa = count - mc
    diff_directive = _difficulty_directive(difficulty, grade)

    # Phase 4.2 #12: optional DOK directive. Codex MAJOR — explicit
    # ordering clarifier prevents AI confusion on "DOK 4 + easier" cases.
    dok_directive = ""
    if dok in DOK_OPTIONS:
        dok_directive = (
            f"Each question MUST be at DOK level {dok}: "
            f"{DOK_DESCRIPTIONS[dok]} "
            f"Cognitive rigor is set by DOK; vocabulary and scaffolding tone "
            f"are set by difficulty. They can coexist — e.g., DOK 4 + easier "
            f"means extended thinking with simpler reading load. Each question "
            f"MUST include a 'dok' integer field set to {dok}. "
        )

    return (
        f"Generate exactly {count} grade-{grade} {subject} practice questions aligned to "
        f"standard {standard_code}, AND a short lesson explaining the standard.\n\n"
        f"QUESTIONS: Mix of {mc} multiple-choice questions (4 choices each, "
        f"exactly 1 correct, marked with an 'answer' field whose value is either the "
        f"choice letter (A/B/C/D) or the choice text) and {sa} short-answer questions "
        f"(each with an 'answer' field containing the model answer). "
        f"Each question MUST include a 'standard' field equal to '{standard_code}'. "
        f"{dok_directive}{diff_directive}\n\n"
        f"LESSON: A 300-400 word total mini-lesson with three string fields: "
        f"`intro` (~80-120 words explaining what standard {standard_code} is and "
        f"why it matters), `worked_example` (~150-200 words: a single fully worked "
        f"problem with problem statement, step-by-step reasoning, and final answer), "
        f"and `key_takeaway` (1-2 sentence summary of the rule or principle). "
        f"The worked example MUST demonstrate the same concept the practice "
        f"questions test. For any math, use \\(...\\) for inline equations and "
        f"\\[...\\] for display equations (NOT dollar signs — the renderer does "
        f"not support them).\n\n"
        f"Return valid JSON of this exact shape: "
        f"{{\"title\": \"Practice - {standard_code}\", "
        f"\"lesson\": {{\"intro\": \"...\", \"worked_example\": \"...\", "
        f"\"key_takeaway\": \"...\"}}, "
        f"\"sections\": [{{\"name\": \"Practice\", \"questions\": [...]}}]}}"
    )


def _gen_variant_for_student(*, sid, segment, students_by_id, api_key,
                             base_prompt, subject, grade, standard_code,
                             ctx_uid, ctx_client, teacher_id, class_id,
                             count=None):
    """Phase 4.2 #2 worker: builds prompt, calls AI once, post-processes,
    returns {student_id, student_name, questions, lesson, usage} or raises.

    Runs in a worker thread. NEVER reads Flask `g`, `request`, or any
    per-request DB handle — only the explicit kwargs above. Per-thread
    OpenAIAdapter instance to avoid shared-client surprises.

    Spec: docs/superpowers/specs/2026-04-30-phase4.2-perstudent-gen-design.md
    """
    import json as _json
    from backend.services.llm_adapter import (
        LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart,
    )
    from backend.services.assignment_post_processing import (
        _post_process_assignment, _extract_usage, _merge_usage,
    )

    adapter = OpenAIAdapter(api_key=api_key)
    seg = (segment or "")
    if seg:
        # Phase 4.2 #1: extend accommodation directive to apply to lesson too.
        seg = seg + "\n\nApply these accommodations to the lesson text as well as the questions."
    prompt = base_prompt + ("\n\n" + seg if seg else "")

    completion = adapter.chat(LLMRequest(
        model="gpt-4o",
        system_prompt="You are an expert teacher. Return valid JSON only.",
        messages=[Message(role="user", content=[TextPart(text=prompt)])],
        response_format=ResponseFormat(type="json_object"),
        metadata={"feature_label": "remediation_personalized"},
    ))
    raw_text = completion.content_parts[0].text if completion.content_parts else "{}"
    assignment = _json.loads(raw_text)

    # Fallback wrapper (Phase 4.2 #1) — preserve lesson when AI returns flat shape.
    if isinstance(assignment, dict) and 'sections' not in assignment and 'questions' in assignment:
        assignment = {
            'title': assignment.get('title', f"Practice - {standard_code}"),
            'lesson': assignment.get('lesson'),
            'sections': [{'name': 'Practice', 'questions': assignment.get('questions') or []}],
        }
    raw_lesson = assignment.get('lesson') if isinstance(assignment, dict) else None

    # Phase 4.2 #3: count is parameterized (default preserves prior behavior).
    effective_count = count if count is not None else REMEDIATION_COUNT_DEFAULT
    assignment, _extra_usage = _post_process_assignment(
        assignment, effective_count, target_total_points=effective_count * 10,
        subject=subject, grade=grade,
        valid_standard_codes=[standard_code],
        user_id=ctx_uid, client=ctx_client,
    )

    # Flatten sections back to questions list.
    flat_questions = []
    for section in (assignment or {}).get('sections', []):
        for q in section.get('questions', []):
            flat_questions.append(q)
    if len(flat_questions) < 3:
        raise ValueError(
            f"Generation produced too few valid questions for student {sid}"
        )

    clean_lesson = _validate_and_clean_lesson(
        raw_lesson, teacher_id=teacher_id, class_id=class_id, standard_code=standard_code,
    )

    s_row = students_by_id.get(sid) or {}
    student_name = (
        ((s_row.get('first_name') or '') + ' ' + (s_row.get('last_name') or '')).strip()
        or sid
    )

    # Phase 4.2 #2 (Codex full-PR MINOR): merge main-call usage with
    # post-processor usage so the parent's aggregation captures both.
    # Shared mode does this merge in the route; we mirror it here for
    # personalized variants.
    return {
        'student_id': sid,
        'student_name': student_name,
        'questions': flat_questions,
        'lesson': clean_lesson,
        'usage': _merge_usage(_extract_usage(completion, "gpt-4o"), _extra_usage),
    }


# ============ Teacher Endpoints ============

@student_portal_bp.route('/api/publish-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
@critical_path
def publish_assessment():
    """
    Publish an assessment for students to take.
    Returns a unique join code and shareable link.

    New features:
    - period: Class period for organization
    - restricted_students: List of student names (for makeup exams)
    - accommodations: Applied accommodations per student
    """
    try:
        db = _get_teacher_supabase()
        data = request.json
        assessment = data.get('assessment')
        settings = data.get('settings', {})

        if not assessment:
            return jsonify({"error": "No assessment provided"}), 400

        # Generate unique join code
        join_code = generate_join_code()

        # Get period and student restrictions
        period = settings.get('period', '')
        restricted_students = settings.get('restricted_students') or []  # Empty = open to all
        student_accommodations = settings.get('student_accommodations', {})  # {student_name: accommodation_settings}

        # Validate content_type
        content_type = settings.get('content_type', 'assessment')
        if content_type not in ('assessment', 'assignment'):
            content_type = 'assessment'

        # Validate assessment_category
        assessment_category = settings.get('assessment_category', 'formative')
        if assessment_category not in ('formative', 'summative'):
            assessment_category = 'formative'

        # Prepare settings
        db_settings = {
            "time_limit_minutes": settings.get('time_limit_minutes'),
            "allow_multiple_attempts": settings.get('allow_multiple_attempts', False),
            "show_correct_answers": settings.get('show_correct_answers', True),
            "show_score_immediately": settings.get('show_score_immediately', True),
            "require_name": settings.get('require_name', True),
            "content_type": content_type,
            "assessment_category": assessment_category,
            "period": period,
            "restricted_students": restricted_students,
            "student_accommodations": student_accommodations,
            "is_makeup": len(restricted_students) > 0,
            "available_from": settings.get('available_from'),
            "available_until": settings.get('available_until'),
            "due_date": settings.get('due_date'),
        }

        # Caller-generated UUID makes this retry-safe under full retry policy.
        result = db.table('published_assessments').upsert({
            "id": str(uuid.uuid4()),
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_id": g.teacher_id,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }, on_conflict='id').execute()

        if not result.data:
            return jsonify({"error": "Failed to publish assessment"}), 500

        # Generate shareable link (use request host for development)
        host = request.host_url.rstrip('/')
        join_link = f"{host}/join/{join_code}"

        return jsonify({
            "success": True,
            "join_code": join_code,
            "join_link": join_link,
            "period": period,
            "restricted_students": restricted_students,
            "message": f"Assessment published! Students can join with code: {join_code}"
        })

    except Exception as e:
        _logger.exception("Publish assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Saved Assessments (Local Storage) ============

SAVED_ASSESSMENTS_DIR = os.path.expanduser("~/.graider_saved_assessments")

@student_portal_bp.route('/api/save-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def save_assessment():
    """Save a generated assessment locally for later use."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        assessment = data.get('assessment')
        name = data.get('name', assessment.get('title', 'Untitled'))

        if not assessment:
            return jsonify({"error": "No assessment provided"}), 400

        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_name}.json"
        filepath = os.path.join(teacher_dir, filename)

        # Save with metadata
        save_data = {
            "name": name,
            "assessment": assessment,
            "saved_at": datetime.now().isoformat(),
        }

        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)

        return jsonify({"success": True, "filename": filename, "message": f"Assessment '{name}' saved"})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/list-saved-assessments', methods=['GET'])
@require_teacher
@handle_route_errors
def list_saved_assessments():
    """List all saved assessments."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        assessments = []
        for filename in os.listdir(teacher_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(teacher_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        assessment = data.get('assessment', {})
                        # Count questions
                        question_count = 0
                        for section in assessment.get('sections', []):
                            question_count += len(section.get('questions', []))
                        assessments.append({
                            "filename": filename,
                            "name": data.get('name', filename.replace('.json', '')),
                            "title": assessment.get('title', 'Untitled'),
                            "saved_at": data.get('saved_at'),
                            "total_points": assessment.get('total_points'),
                            "question_count": question_count,
                        })
                except Exception:
                    pass

        assessments.sort(key=lambda x: x.get('saved_at', ''), reverse=True)
        return jsonify({"assessments": assessments})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/load-saved-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def load_saved_assessment():
    """Load a saved assessment by filename."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "No filename provided"}), 400

        # Prevent path traversal
        filepath = os.path.join(teacher_dir, filename)
        if not os.path.realpath(filepath).startswith(os.path.realpath(teacher_dir)):
            return jsonify({"error": "Invalid filename"}), 400

        if not os.path.exists(filepath):
            return jsonify({"error": "Assessment not found"}), 404

        with open(filepath, 'r') as f:
            save_data = json.load(f)

        return jsonify({
            "success": True,
            "assessment": save_data.get('assessment'),
            "name": save_data.get('name'),
        })

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/delete-saved-assessment', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_saved_assessment():
    """Delete a saved assessment."""
    try:
        teacher_dir = os.path.join(SAVED_ASSESSMENTS_DIR, g.teacher_id)
        os.makedirs(teacher_dir, exist_ok=True)

        data = request.json
        filename = data.get('filename')

        if not filename:
            return jsonify({"error": "No filename provided"}), 400

        # Prevent path traversal
        filepath = os.path.join(teacher_dir, filename)
        if not os.path.realpath(filepath).startswith(os.path.realpath(teacher_dir)):
            return jsonify({"error": "Invalid filename"}), 400

        if os.path.exists(filepath):
            os.remove(filepath)

        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Request failed: %s", request.path)
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessments', methods=['GET'])
@require_teacher
@handle_route_errors
def list_published_assessments():
    """List all published assessments for the teacher."""
    try:
        db = _get_teacher_supabase()

        result = db.table('published_assessments').select(
            'id, join_code, title, created_at, submission_count, is_active, teacher_name, settings'
        ).eq('teacher_id', g.teacher_id).order('created_at', desc=True).execute()

        assessments = [{
            "id": a.get('id'),
            "join_code": a.get('join_code'),
            "title": a.get('title'),
            "created_at": a.get('created_at'),
            "submission_count": a.get('submission_count', 0),
            "is_active": a.get('is_active', True),
            "content_type": a.get('settings', {}).get('content_type', 'assessment'),
            "period": a.get('settings', {}).get('period', ''),
            "is_makeup": a.get('settings', {}).get('is_makeup', False),
            "restricted_students": a.get('settings', {}).get('restricted_students', []),
            "unit_name": a.get('settings', {}).get('unit_name', ''),
            "tags": a.get('settings', {}).get('tags', []),
        } for a in result.data]

        return jsonify({"assessments": assessments})

    except Exception as e:
        _logger.exception("List assessments error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/results', methods=['GET'])
@require_teacher
@handle_route_errors
def get_assessment_results(code):
    """Get all submissions for a published assessment."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Get assessment — scoped to this teacher
        assessment_result = db.table('published_assessments').select('*').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

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
        _logger.exception("Get results error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/toggle', methods=['POST'])
@require_teacher
@handle_route_errors
def toggle_assessment(code):
    """Activate or deactivate a published assessment."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Get current status — scoped to this teacher
        result = db.table('published_assessments').select('is_active').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        if not result.data:
            return jsonify({"error": "Assessment not found"}), 404

        current_active = result.data[0].get('is_active', True)
        new_active = not current_active

        # Update
        db.table('published_assessments').update({'is_active': new_active}).eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        status = "activated" if new_active else "deactivated"
        return jsonify({
            "success": True,
            "active": new_active,
            "message": f"Assessment {status}"
        })

    except Exception as e:
        _logger.exception("Toggle assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_published_assessment(code):
    """Delete a published assessment and all its submissions."""
    try:
        db = _get_teacher_supabase()
        code = code.upper()

        # Verify ownership before deleting
        ownership = db.table('published_assessments').select('id').eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()
        if not ownership.data:
            return jsonify({"error": "Assessment not found"}), 404

        # Delete submissions first (cascade should handle this, but be explicit)
        db.table('submissions').delete().eq('join_code', code).execute()

        # Delete assessment — scoped to this teacher
        result = db.table('published_assessments').delete().eq(
            'join_code', code
        ).eq('teacher_id', g.teacher_id).execute()

        return jsonify({"success": True, "message": "Assessment deleted"})

    except Exception as e:
        _logger.exception("Delete assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


# ============ Student Endpoints ============

@student_portal_bp.route('/api/student/join/<code>', methods=['GET'])
@limiter.limit("30 per minute")
@handle_route_errors
def get_assessment_for_student(code):
    """
    Get assessment details for a student joining with a code.
    Returns assessment without answers for student to take.

    Rate-limited at 30/min per IP (Phase 4.6) to prevent join-code
    enumeration attacks. Typical student traffic is <5/min per IP.
    """
    try:
        # Anonymous join-code path — no teacher JWT, so service-role.
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

        # Shared study-material content (study guide, flashcards, etc.) — return directly
        content_type = settings.get('content_type') or assessment.get('content_type')
        # Only study materials get the material response format.
        # Assignments and assessments both get the sections/questions format.
        material_types = ('study_guide', 'flashcards', 'slide_deck', 'mind_map',
                          'audio_overview', 'video_overview', 'infographic', 'data_table')
        if content_type and content_type in material_types:
            resp = {
                "content_type": content_type,
                "title": assessment.get('title', data.get('title', content_type)),
                "teacher": data.get('teacher_name', 'Teacher'),
            }
            # JSON types: quiz, flashcards, mind_map
            if assessment.get('data'):
                resp["data"] = assessment['data']
            # Legacy flashcards format
            if assessment.get('cards'):
                resp["data"] = assessment['cards']
            # Text types: study_guide
            if assessment.get('content'):
                resp["content"] = assessment['content']
            # Media types: provide URL
            if assessment.get('shared_file'):
                resp["media_url"] = "/api/student/shared-media/" + code
            return jsonify(resp)

        # Remove answers from questions before sending to student
        sanitized_sections = []
        for section in assessment.get('sections', []):
            sanitized_questions = []
            for q in section.get('questions', []):
                student_question = {
                    "number": q.get('number'),
                    "question": q.get('question'),
                    "type": q.get('type') or q.get('question_type', 'short_answer'),
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

        # Check for student restrictions (makeup exams)
        restricted_students = settings.get('restricted_students', [])
        student_accommodations = settings.get('student_accommodations', {})
        is_makeup = settings.get('is_makeup', False)

        return jsonify({
            "title": assessment.get('title'),
            "instructions": assessment.get('instructions'),
            "total_points": assessment.get('total_points'),
            "time_estimate": assessment.get('time_estimate'),
            "sections": sanitized_sections,
            "settings": {
                "content_type": content_type or 'assessment',
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,  # Frontend checks if student allowed
                "period": settings.get('period', ''),
            },
            "student_accommodations": student_accommodations,  # Accommodations per student
            "teacher": data.get('teacher_name', 'Teacher'),
        })

    except Exception as e:
        _logger.exception("Get assessment for student error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/student/submit/<code>', methods=['POST'])
@limiter.limit("10 per minute")
@handle_route_errors
@critical_path
def submit_assessment(code):
    """
    Submit student answers for grading.
    Returns immediate feedback and score.
    """
    try:
        # Anonymous join-code path — no teacher JWT, so service-role.
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

        # Enforce availability window (assessments)
        available_from = settings.get('available_from')
        available_until = settings.get('available_until')
        if available_from or available_until:
            now = datetime.now(timezone.utc).isoformat()
            if available_from and now < available_from:
                return jsonify({"error": "This assessment is not yet available."}), 403
            if available_until and now > available_until:
                return jsonify({"error": "This assessment is no longer accepting submissions."}), 403

        # Check for duplicate submission
        if not settings.get('allow_multiple_attempts', False):
            existing = db.table('submissions').select('id, results').eq('join_code', code).ilike('student_name', student_name).execute()
            if existing.data:
                return jsonify({
                    "error": "You have already submitted this assessment.",
                    "previous_results": existing.data[0].get('results')
                }), 400

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
        _logger.info("Grading complete: score=%s/%s", results.get('score'), results.get('total_points'))

        # Insert submission
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
            submission_row["score"] = None
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = None
            # Note: submissions table has no grading_status column
            # Status is tracked in the results JSON instead
        else:
            submission_row["score"] = results.get('score')
            submission_row["total_points"] = results.get('total_points')
            submission_row["percentage"] = results.get('percentage')

        # Caller-generated UUID + upsert on id makes this retry-safe.
        submission_row['id'] = str(uuid.uuid4())
        try:
            submission_result = db.table('submissions').upsert(
                submission_row, on_conflict='id'
            ).execute()
        except Exception as insert_err:
            if '23505' in str(insert_err) or 'duplicate' in str(insert_err).lower():
                return jsonify({
                    "error": "You have already submitted this assessment.",
                }), 400
            raise

        if not submission_result.data:
            return jsonify({"error": "Failed to save submission"}), 500

        submission_id = submission_result.data[0].get('id')

        # Spawn multipass grading thread for written questions
        if needs_multipass:
            from backend.services.grading_service import load_teacher_config

            # Hoist context values that both the Celery path and the thread
            # fallback need. Before Phase 4.1 these were constructed inline
            # inside the threading.Thread(...) spawn.
            teacher_id = assessment_data.get("teacher_id") or ""
            teacher_config = load_teacher_config(teacher_id)
            student_info = {"student_name": student_name, "student_id": "", "email": ""}
            student_accommodations = assessment_data.get("settings", {}).get("student_accommodations", {})

            # Phase 4.1 PR3: Celery is the always-on primary path for join-code
            # grading. The CELERY_PORTAL_GRADING flag gate + else-branch thread
            # spawn were removed after the 48h post-flip monitor window closed
            # green. Thread-based grading still runs for the class-based
            # submission path (backend/routes/student_account_routes.py); that
            # migration is Phase 4.1b scope.
            from backend.tasks.grading_tasks import grade_portal_submission
            # Enqueue-failure fallback — broker outage degrades to the
            # legacy thread path so the student doesn't lose their
            # submission. Catch ONLY known broker-communication failures:
            #   - kombu.exceptions.OperationalError: Kombu's wrapped
            #     connection failure (redis down, auth, network)
            #   - kombu.exceptions.ConnectionError: transport-layer
            #     errors (NOT Python's builtin ConnectionError)
            # Do NOT catch bare Exception — programming bugs
            # (serialization, missing decorator) must surface loudly.
            import kombu.exceptions
            try:
                district_id = getattr(g, 'district_id', None)
                user_id = getattr(g, 'user_id', None)
            except RuntimeError:
                district_id = None
                user_id = None
            try:
                grade_portal_submission.delay(
                    submission_id,
                    teacher_id,
                    'submissions',
                    district_id=district_id,
                    user_id=user_id,
                )
            except (kombu.exceptions.OperationalError,
                    kombu.exceptions.ConnectionError) as e:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag('celery_enqueue_failure', True)
                    scope.level = 'warning'
                    sentry_sdk.capture_exception(e)
                _spawn_thread_grading(submission_id, assessment, answers,
                                      student_info, teacher_config, teacher_id,
                                      'submissions', student_accommodations)

            # Mark results as partially graded for frontend
            results["grading_status"] = "partial"
            results["message"] = "Multiple choice and true/false graded. Written responses pending teacher review."

        # Prepare response based on settings
        # Use assessment_data settings (not shadowed variable) for display decisions
        publish_settings = assessment_data.get('settings', {})
        response = {
            "success": True,
            "submission_id": submission_id,
            "student_name": student_name,
        }

        # Assessment mode: if both score and answers are hidden, return pending_review
        if not publish_settings.get('show_score_immediately', True) and not publish_settings.get('show_correct_answers', True):
            response["grading_status"] = "pending_review"
            response["message"] = "Submitted! Your teacher will review and share your results."
        elif results.get("grading_status") == "partial":
            # Mixed assignment: show MC scores but not percentage
            mc_correct = sum(1 for q in (results.get("questions") or []) if q.get("is_correct") and q.get("type") in ("multiple_choice", "true_false", "matching"))
            mc_total = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching"))
            written_count = sum(1 for q in (results.get("questions") or []) if q.get("type") in ("short_answer", "extended_response", "essay", "written"))
            response["grading_status"] = "partial"
            response["mc_correct"] = mc_correct
            response["mc_total"] = mc_total
            response["written_pending"] = written_count
            response["message"] = results["message"]
            if publish_settings.get('show_correct_answers', True):
                response["detailed_results"] = [q for q in (results.get("questions") or []) if q.get("type") in ("multiple_choice", "true_false", "matching")]
        else:
            # MC-only: show full results
            if publish_settings.get('show_score_immediately', True):
                response["score"] = results.get('score')
                response["total_points"] = results.get('total_points')
                response["percentage"] = results.get('percentage')
                response["feedback_summary"] = results.get('feedback_summary')
            if publish_settings.get('show_correct_answers', True):
                response["detailed_results"] = results.get('questions')

        return jsonify(response)

    except Exception as e:
        _logger.exception("Submit assessment error")
        return jsonify({"error": "An internal error occurred"}), 500


RESOURCE_CONTENT_TYPES = ('study_guide', 'flashcards', 'slide_deck')


@student_portal_bp.route('/api/teacher/shared-resources', methods=['GET'])
@require_teacher
@handle_route_errors
def list_shared_resources():
    """List all shared resources (flashcards, study guides, slide decks) for the teacher."""
    try:
        db = _get_teacher_supabase()

        result = db.table('published_content').select(
            'id, title, content_type, class_id, created_at, is_active, settings'
        ).eq('teacher_id', g.teacher_id).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).order('created_at', desc=True).execute()

        # Fetch class names for display
        class_ids = list(set(r.get('class_id') for r in result.data if r.get('class_id')))
        class_names = {}
        if class_ids:
            classes_result = db.table('classes').select('id, name').in_('id', class_ids).execute()
            class_names = {c['id']: c['name'] for c in classes_result.data}

        resources = [{
            "id": r.get('id'),
            "title": r.get('title'),
            "content_type": r.get('content_type'),
            "class_id": r.get('class_id'),
            "class_name": class_names.get(r.get('class_id'), 'Unknown'),
            "created_at": r.get('created_at'),
            "is_active": r.get('is_active', True),
            "unit_name": r.get('settings', {}).get('unit_name', ''),
            "tags": r.get('settings', {}).get('tags', []),
        } for r in result.data]

        return jsonify({"resources": resources})

    except Exception as e:
        _logger.exception("List shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>', methods=['DELETE'])
@require_teacher
@handle_route_errors
def delete_shared_resource(resource_id):
    """Delete a single shared resource."""
    try:
        db = _get_teacher_supabase()

        # Verify ownership
        check = db.table('published_content').select('id').eq(
            'id', resource_id
        ).eq('teacher_id', g.teacher_id).execute()
        if not check.data:
            return jsonify({"error": "Resource not found"}), 404

        db.table('published_content').delete().eq('id', resource_id).execute()
        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Delete shared resource error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/delete-shared-resources-bulk', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_shared_resources_bulk():
    """Delete all shared resources matching a title for this teacher."""
    try:
        db = _get_teacher_supabase()
        data = request.json
        title = data.get('title', '').strip()

        if not title:
            return jsonify({"error": "Title is required"}), 400

        result = db.table('published_content').delete().eq(
            'teacher_id', g.teacher_id
        ).eq('title', title).in_(
            'content_type', list(RESOURCE_CONTENT_TYPES)
        ).execute()

        deleted = len(result.data) if result.data else 0
        return jsonify({"success": True, "deleted": deleted})

    except Exception as e:
        _logger.exception("Bulk delete shared resources error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/shared-resource/<resource_id>/unit', methods=['POST'])
@require_teacher
@handle_route_errors
def update_shared_resource_unit(resource_id):
    """Update the unit_name in a published content row's settings.
    Works for both published_assessments and published_content tables.
    """
    try:
        db = _get_teacher_supabase()
        data = request.json
        unit_name = data.get('unit_name', '').strip()

        table_name, row = _find_content_row(db, resource_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Resource not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['unit_name'] = unit_name

        db.table(table_name).update({
            'settings': existing_settings
        }).eq('id', resource_id).execute()

        return jsonify({"success": True})

    except Exception as e:
        _logger.exception("Update unit error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/end-attempt/<submission_id>', methods=['POST'])
@require_teacher
@handle_route_errors
def end_student_attempt(submission_id):
    """Force-end a student's in-progress draft, converting it to a submitted row."""
    try:
        db = _get_teacher_supabase()

        # Fetch the draft
        sub = db.table('student_submissions').select('*').eq('id', submission_id).execute()
        if not sub.data:
            return jsonify({"error": "Submission not found"}), 404
        row = sub.data[0]

        if row.get('status') != 'draft':
            return jsonify({"error": "Not an in-progress draft"}), 400

        # Verify teacher owns the class this content belongs to
        content_id = row.get('content_id')
        content = db.table('published_content').select('teacher_id').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Convert draft to submission
        db.table('student_submissions').update({
            'status': 'submitted',
            'answers': row.get('draft_answers') or {},
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'results': {'force_ended_by_teacher': True},
        }).eq('id', submission_id).execute()

        return jsonify({"success": True})
    except Exception as e:
        _logger.exception("End attempt error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/content/<content_id>/in-progress', methods=['GET'])
@require_teacher
@handle_route_errors
def list_in_progress_drafts(content_id):
    """List students currently drafting a specific piece of class-based content."""
    try:
        db = _get_teacher_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        drafts = db.table('student_submissions').select(
            'id, student_name, draft_answers, marked_for_review, time_started_at'
        ).eq('content_id', content_id).eq('status', 'draft').execute()

        now = datetime.now(timezone.utc)
        rows = []
        for d in drafts.data:
            answers = d.get('draft_answers') or {}
            answered_count = sum(1 for v in answers.values() if v not in (None, '', []))
            elapsed_seconds = 0
            remaining_seconds = None
            if d.get('time_started_at'):
                started = datetime.fromisoformat(d['time_started_at'].replace('Z', '+00:00'))
                elapsed_seconds = int((now - started).total_seconds())
                if time_limit_seconds:
                    remaining_seconds = max(0, time_limit_seconds - elapsed_seconds)
            rows.append({
                "submission_id": d['id'],
                "student_name": d.get('student_name'),
                "answered_count": answered_count,
                "elapsed_seconds": elapsed_seconds,
                "remaining_seconds": remaining_seconds,
            })

        return jsonify({"drafts": rows})
    except Exception as e:
        _logger.exception("List in-progress error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/content/<content_id>/submissions', methods=['GET'])
@require_teacher
@handle_route_errors
def list_content_submissions(content_id):
    """List all submissions (all attempts per student) for a class-based assessment."""
    try:
        db = _get_teacher_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, title, content, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Fetch all submissions for this content (excluding drafts)
        submissions = db.table('student_submissions').select('*').eq(
            'content_id', content_id
        ).neq('status', 'draft').order('student_id', desc=False).order('attempt_number', desc=False).execute()

        # Group by student
        groups = {}
        for s in submissions.data:
            sid = s.get('student_id') or s.get('student_name')
            if sid not in groups:
                groups[sid] = {
                    'student_id': s.get('student_id'),
                    'student_name': s.get('student_name'),
                    'student_id_number': s.get('student_id_number'),
                    'period': s.get('period'),
                    'attempts': [],
                }
            groups[sid]['attempts'].append({
                'submission_id': s.get('id'),
                'attempt_number': s.get('attempt_number', 1),
                'score': s.get('score'),
                'total_points': s.get('total_points'),
                'percentage': s.get('percentage'),
                'letter_grade': s.get('letter_grade'),
                'status': s.get('status'),
                'time_taken_seconds': s.get('time_taken_seconds'),
                'question_times': s.get('question_times'),
                'submitted_at': s.get('submitted_at'),
                'results': s.get('results'),
            })

        return jsonify({
            "content_id": content_id,
            "title": content.data[0].get('title'),
            "content": content.data[0].get('content'),
            "students": list(groups.values()),
        })
    except Exception as e:
        _logger.exception("List content submissions error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/class/<class_id>/progress-rank', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_progress_rank(class_id):
    """Return a class-scoped progress rank grid aggregating standards_mastery
    across all graded submissions for students in the class.

    Query params:
      attempt_mode: 'latest' (default) | 'best' | 'average'
    """
    try:
        db = _get_teacher_supabase()

        attempt_mode = request.args.get('attempt_mode', 'latest')
        if attempt_mode not in ('latest', 'best', 'average'):
            attempt_mode = 'latest'

        # Verify class ownership
        cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
        if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403
        class_name = cls.data[0].get('name')

        # Fetch class roster — query students directly by joining via class_students
        # Two-step query avoids Supabase foreign-table alias ambiguity
        enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
        student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

        student_records = []
        if student_ids:
            students_rows = db.table('students').select(
                'id, first_name, last_name'
            ).in_('id', student_ids).execute()
            for sdata in students_rows.data or []:
                student_records.append({
                    'student_id': sdata.get('id'),
                    'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
                })
            # Sort alphabetically by name for stable grid order
            student_records.sort(key=lambda s: s['student_name'].lower())

        if not student_records:
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [],
            })

        # Fetch all published_content for this class (assessments/assignments only)
        content = db.table('published_content').select(
            'id, title, content_type'
        ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

        content_ids = [c['id'] for c in content.data or []]
        content_titles = {c['id']: c.get('title', '') for c in content.data or []}

        if not content_ids:
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [{'student_id': s['student_id'], 'student_name': s['student_name'], 'mastery': {}} for s in student_records],
            })

        # Fetch all non-draft submissions for those contents, ordered for deterministic selection
        # Select only columns we need to keep payload bounded
        subs = db.table('student_submissions').select(
            'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
        ).in_('content_id', content_ids).neq('status', 'draft').order(
            'submitted_at', desc=True
        ).execute()

        # Sanitize malformed standards_mastery in place so column-union and
        # aggregation don't 500 on a single corrupt row. Phase 2b extracted
        # this from get_student_report_card to share between endpoints.
        for s in subs.data or []:
            _sanitize_standards_mastery(s)

        # Group submissions by (student_id, content_id)
        from collections import defaultdict
        subs_by_student_content = defaultdict(lambda: defaultdict(list))
        all_standards_in_class = set()  # Union across the whole class — used for columns
        for s in subs.data or []:
            sid = s.get('student_id')
            cid = s.get('content_id')
            if sid and cid:
                subs_by_student_content[sid][cid].append(s)
                # Track every standard seen anywhere in the class for column union
                results = s.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code in mastery.keys():
                    if code:
                        all_standards_in_class.add(code)

        # Build per-student mastery
        students_output = []
        for student in student_records:
            sid = student['student_id']
            by_content = subs_by_student_content.get(sid, {})
            selected = _select_submissions_by_mode(by_content, attempt_mode)
            mastery = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
            students_output.append({
                'student_id': sid,
                'student_name': student['student_name'],
                'mastery': mastery,
            })

        return jsonify({
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "standards": sorted(all_standards_in_class),
            "students": students_output,
        })
    except Exception as e:
        _logger.exception("Progress rank error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/class/<class_id>/student/<student_id>/report-card', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_report_card(class_id, student_id):
    """Return per-student report card: trajectory + standards breakdown.

    Class-scoped view of a single student's mastery within ONE class.
    Reuses _select_submissions_by_mode + _aggregate_mastery_for_student
    + bridge helpers to assemble the response.

    Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
    """
    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Student-in-class check
    enrollment = db.table('class_students').select('student_id').eq(
        'class_id', class_id
    ).eq('student_id', student_id).execute()
    if not enrollment.data:
        return error_response("Student not in class", 404)

    # 3) Fetch student name (orphan-enrollment guard)
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return error_response("Student not in class", 404)
    student_name = (
        (student_row.data[0].get('first_name') or '') + ' ' +
        (student_row.data[0].get('last_name') or '')
    ).strip()

    # 4) Fetch all class assessments/assignments
    content_rows = db.table('published_content').select(
        'id, title, content_type'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()
    content_ids = [c['id'] for c in (content_rows.data or [])]
    content_titles = {c['id']: c.get('title', '') for c in (content_rows.data or [])}

    if not content_ids:
        return jsonify({
            "student_id": student_id,
            "student_name": student_name,
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "trajectory": [],
            "standards_breakdown": [],
        })

    # 5) Fetch all non-draft submissions for this student in those contents
    subs_rows = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
    ).eq('student_id', student_id).in_('content_id', content_ids).neq(
        'status', 'draft'
    ).execute()
    submissions = subs_rows.data or []

    # 6) Build trajectory from ALL submissions chronologically
    # (trajectory tolerates missing standards_mastery — only uses
    # submitted_at + percentage from the row.)
    trajectory = _build_trajectory_for_student(submissions, content_titles)

    # 7) Sanitize standards_mastery IN PLACE so attempt-mode selection
    # still sees every submission. A malformed-mastery submission stays
    # selectable (so 'latest' picks the truly latest attempt), but its
    # mastery contribution is empty.
    for s in submissions:
        _sanitize_standards_mastery(s)

    # 8) Build standards_breakdown via existing helpers + bridge code
    from collections import defaultdict
    subs_by_content = defaultdict(list)
    for s in submissions:
        cid = s.get('content_id')
        if cid:
            subs_by_content[cid].append(s)
    selected = _select_submissions_by_mode(subs_by_content, attempt_mode)
    mastery_by_code = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
    submission_lookup = {s.get('id'): s for s in submissions if s.get('id')}
    standards_breakdown = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)

    return jsonify({
        "student_id": student_id,
        "student_name": student_name,
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "trajectory": trajectory,
        "standards_breakdown": standards_breakdown,
    })


@student_portal_bp.route('/api/teacher/class/<class_id>/gradebook', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_gradebook(class_id):
    """Return per-(student, assessment) canonical grades for a class.

    Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
    """
    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Fetch class roster: enrollments + students. Skip orphans silently.
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    student_records = []
    if student_ids:
        students_rows = db.table('students').select(
            'id, first_name, last_name'
        ).in_('id', student_ids).execute()
        seen = {s['id']: s for s in (students_rows.data or []) if s.get('id')}
        for sid in student_ids:
            sdata = seen.get(sid)
            if sdata is None:
                _logger.debug("Orphan enrollment in class %s: student_id=%s missing from students table", class_id, sid)
                continue
            student_records.append({
                'student_id': sid,
                'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
            })
        student_records.sort(key=lambda s: s['student_name'].lower())

    if not student_records:
        return jsonify({
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [], "assessments": [], "grades": {},
        })

    # 3) Fetch all class assessments/assignments. Sort ASC by publish_date.
    content_rows = db.table('published_content').select(
        'id, title, content_type, publish_date, due_date, is_active, target_student_ids'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

    assessments = sorted(
        (content_rows.data or []),
        key=lambda c: (c.get('publish_date') or '', c.get('id') or ''),
    )
    # Phase 4.2 #7: capture is_active and target_student_ids for the
    # remediation-badge UI. The grouping logic below keys off c['id'] only,
    # so adding these passthrough fields doesn't affect any join/aggregation.
    content_titles = {c['id']: c.get('title', '') for c in assessments}

    if not assessments:
        return jsonify({
            "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
            "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
            "assessments": [], "grades": {},
        })

    # Phase 4.3 Sprint 1: derive uniform DOK for remediation rows only.
    # The metadata SELECT above intentionally omits `content` (JSONB blob —
    # could be 50-200KB per row × dozens of rows). Remediation rows are
    # typically 1-3 per class, so a focused second fetch keeps the payload
    # tight while letting the gradebook column header render a "DOK N" pill.
    remediation_ids = [
        c['id'] for c in assessments
        if c.get('target_student_ids') and c.get('id')
    ]
    assessment_dok_by_id = {}
    if remediation_ids:
        # Paginate via .range() — same pattern as the submissions fetch
        # below. PostgREST's default row cap is 1000; a class can in
        # principle accumulate more remediations over time (Phase 4.2 #8
        # caps publishes per-(teacher × student × rolling 7-day) but the
        # historical total can grow). Without pagination, later rows would
        # silently miss assessment_dok (Codex full-PR MINOR).
        page_size = 1000
        rem_start = 0
        while True:
            rem_page = db.table('published_content').select(
                'id, content'
            ).in_('id', remediation_ids).range(rem_start, rem_start + page_size - 1).execute()
            rem_rows = rem_page.data or []
            for row in rem_rows:
                cid = row.get('id')
                if cid:
                    assessment_dok_by_id[cid] = _derive_uniform_dok(row.get('content'))
            if len(rem_rows) < page_size:
                break
            rem_start += page_size

    # 4) Fetch non-draft submissions for these students × these contents.
    # Paginate via .range() because PostgREST's default row cap is 1000 —
    # a real class (30 students x 40 assessments x several attempts each) can
    # silently truncate without paging. Drop `results` from the SELECT —
    # gradebook only needs row-level columns (id/percentage/attempt_number
    # /submitted_at), not the rich per-question results JSON; this also
    # means we don't need the defensive _sanitize_standards_mastery call here.
    student_id_set = [s['student_id'] for s in student_records]
    content_id_set = [c['id'] for c in assessments]
    page_size = 1000
    submissions = []
    start = 0
    while True:
        page = db.table('student_submissions').select(
            'id, student_id, content_id, attempt_number, submitted_at, percentage, status'
        ).in_('student_id', student_id_set).in_('content_id', content_id_set).neq(
            'status', 'draft'
        ).range(start, start + page_size - 1).execute()
        rows = page.data or []
        submissions.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size

    # 5) Group by (student_id, content_id) and build the canonical-grade map
    from collections import defaultdict
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    grades = {}
    for sid, by_content in subs_by_student_content.items():
        per_student = {}
        for cid, subs in by_content.items():
            if not subs:
                continue
            total_attempts = len(subs)
            selected = _select_submissions_by_mode({cid: subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # mean percentage across attempts; drilldown anchor = latest.
                # Use _coalesce (NOT `or`) so a legitimate 0 doesn't fall through.
                pcts = [_coalesce(s.get('percentage'), default=0) for s in subs]
                mean_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0
                latest = max(subs, key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))))
                per_student[cid] = {
                    'submission_id': latest.get('id'),
                    'percentage': mean_pct,
                    'attempt_number': latest.get('attempt_number'),
                    'submitted_at': latest.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
            else:
                if not selected:
                    continue
                chosen = selected[0]
                per_student[cid] = {
                    'submission_id': chosen.get('id'),
                    'percentage': chosen.get('percentage'),
                    'attempt_number': chosen.get('attempt_number'),
                    'submitted_at': chosen.get('submitted_at'),
                    'total_attempts': total_attempts,
                }
        if per_student:
            grades[sid] = per_student

    return jsonify({
        "class_id": class_id, "class_name": class_name, "attempt_mode": attempt_mode,
        "students": [{'student_id': s['student_id'], 'student_name': s['student_name']} for s in student_records],
        "assessments": [
            {'content_id': c['id'], 'title': c.get('title', ''), 'content_type': c.get('content_type'),
             'publish_date': c.get('publish_date'), 'due_date': c.get('due_date'),
             # Phase 4.2 #7: surface remediation flags for the badge UI.
             'is_active': c.get('is_active'),
             'target_student_ids': c.get('target_student_ids'),
             # Phase 4.3 Sprint 1: uniform DOK for remediation rows only.
             # Non-remediation rows always get None (no badge).
             'assessment_dok': assessment_dok_by_id.get(c['id'])}
            for c in assessments
        ],
        "grades": grades,
    })


@student_portal_bp.route('/api/teacher/submission/<submission_id>/detail', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_submission_detail(submission_id):
    """Return per-submission detail: metadata + per-question breakdown + sibling attempts.

    Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
    """
    db = _get_teacher_supabase()

    # 1) Look up the submission
    sub_row = db.table('student_submissions').select(
        'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status, score, total_points'
    ).eq('id', submission_id).execute()
    if not sub_row.data:
        return error_response("Submission not found", 404)
    sub = sub_row.data[0]

    # 2) Look up the content. Phase 4.2 #7: also fetch is_active and
    # target_student_ids so the drawer header can render the remediation
    # badges that match the gradebook column header.
    content_id = sub.get('content_id')
    content_row = db.table('published_content').select(
        'id, title, class_id, is_active, target_student_ids, content'
    ).eq('id', content_id).execute()
    if not content_row.data:
        return error_response("Submission's content no longer exists", 404)
    content = content_row.data[0]

    # 3) Verify class ownership
    class_row = db.table('classes').select('id, teacher_id').eq('id', content.get('class_id')).execute()
    if not class_row.data or class_row.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)

    # 4) Look up the student
    student_id = sub.get('student_id')
    student_row = db.table('students').select(
        'id, first_name, last_name'
    ).eq('id', student_id).execute()
    if not student_row.data:
        return error_response("Student not found", 404)
    sdata = student_row.data[0]
    student_name = ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip()

    # 5) Sibling attempts (same student × same content)
    siblings_row = db.table('student_submissions').select(
        'id, attempt_number, submitted_at, percentage'
    ).eq('student_id', student_id).eq('content_id', content_id).execute()
    siblings = sorted(
        siblings_row.data or [],
        key=lambda s: (s.get('attempt_number') or 0, _parse_ts(s.get('submitted_at'))),
    )

    # 6) Top-level score with row + results fallback. Use _coalesce so legitimate 0 isn't lost.
    results = sub.get('results') or {}
    points_earned = _coalesce(results.get('score'), sub.get('score'), default=0)
    points_possible = _coalesce(results.get('total_points'), sub.get('total_points'), default=0)

    # 7) Per-question normalization (spec fallback rules)
    raw_questions = results.get('questions')
    questions = []
    if isinstance(raw_questions, list):
        for q in raw_questions:
            if not isinstance(q, dict):
                _logger.warning("malformed question entry (type=%s) in submission %s — skipping",
                                type(q).__name__, submission_id)
                continue
            questions.append({
                "question_text": _coalesce(q.get('question'), q.get('question_text'), default=''),
                "question_type": _coalesce(q.get('type'), q.get('question_type'), default='unknown'),
                "student_answer": _coalesce(q.get('student_answer'), q.get('answer'), default=''),
                "correct_answer": q.get('correct_answer'),
                "is_correct": q.get('is_correct'),
                "ai_feedback": _coalesce(q.get('feedback'), q.get('reasoning'), q.get('quality'), default=''),
                "points_earned": _coalesce(q.get('points_earned'), q.get('score'), default=0),
                "points_possible": _coalesce(q.get('points_possible'), q.get('points'), default=0),
                "dok": _validate_dok(q.get('dok')),
            })
    elif raw_questions is not None:
        _logger.warning("malformed results.questions (type=%s) in submission %s — returning empty",
                        type(raw_questions).__name__, submission_id)

    return jsonify({
        "submission_id": sub.get('id'),
        "student_id": student_id,
        "student_name": student_name,
        "content_id": content_id,
        "content_title": content.get('title', ''),
        # Phase 4.2 #7: surface remediation flags so SubmissionDetail drawer
        # header can render the badges (matches Gradebook column header).
        "is_active": content.get('is_active'),
        "target_student_ids": content.get('target_student_ids'),
        # Phase 4.3 Sprint 1: uniform DOK across all questions, else null.
        # Drives the optional "DOK N" pill in RemediationBadges.
        "assessment_dok": _derive_uniform_dok(content.get('content')),
        "attempt_number": sub.get('attempt_number'),
        "total_attempts": len(siblings),
        "submitted_at": sub.get('submitted_at'),
        "percentage": sub.get('percentage'),
        "points_earned": points_earned,
        "points_possible": points_possible,
        "questions": questions,
        "sibling_attempts": [
            {"submission_id": s.get('id'), "attempt_number": s.get('attempt_number'),
             "submitted_at": s.get('submitted_at'), "percentage": s.get('percentage')}
            for s in siblings
        ],
    })


@student_portal_bp.route('/api/teacher/class/<class_id>/compare', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_assessment_comparison(class_id):
    """Compare 2-6 assessments side-by-side (class-scoped).

    Spec: docs/superpowers/specs/2026-04-26-phase3b-assessment-comparison-design.md
    """
    import uuid as _uuid

    db = _get_teacher_supabase()

    attempt_mode = request.args.get('attempt_mode', 'latest')
    if attempt_mode not in ('latest', 'best', 'average'):
        attempt_mode = 'latest'

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Parse content_ids CSV
    raw = request.args.get('content_ids', '').strip()
    if not raw:
        return error_response("content_ids is required", 400)
    content_ids = [cid.strip() for cid in raw.split(',') if cid.strip()]

    # 3) UUID validation — catch malformed before Postgres errors out as 500
    for cid in content_ids:
        try:
            _uuid.UUID(cid)
        except (ValueError, TypeError):
            return error_response("Invalid content_id", 400)

    # 4) Count bounds
    if len(content_ids) < 2:
        return error_response("Pick at least 2 assessments to compare", 400)
    if len(content_ids) > 6:
        return error_response("Compare at most 6 assessments at once", 400)

    # 5) Fetch published_content rows scoped to this class.
    # Select content + settings (both JSONB) so the max_points read site can fall
    # back through row column → content.max_points → settings.max_points per spec.
    content_rows = db.table('published_content').select(
        'id, title, content_type, max_points, content, settings'
    ).in_('id', content_ids).eq('class_id', class_id).execute()
    raw_found = content_rows.data or []
    # Reject anything that isn't an assessment — assignments must not be comparable here.
    found = [r for r in raw_found if r.get('content_type') == 'assessment']
    if len(found) < len(content_ids):
        # One or more content_ids isn't in this class OR isn't an assessment — cross-class/type injection guard.
        return error_response("Not authorized", 403)

    # 6) Resolve valid roster (skip orphans matching Phase 3a pattern)
    enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
    enrolled_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

    valid_student_ids = []
    if enrolled_ids:
        students_rows = db.table('students').select('id').in_('id', enrolled_ids).execute()
        existing = {s['id'] for s in (students_rows.data or []) if s.get('id')}
        for sid in enrolled_ids:
            if sid in existing:
                valid_student_ids.append(sid)
            else:
                _logger.debug("Orphan enrollment in class %s: student_id=%s missing from students table", class_id, sid)

    class_roster_size = len(valid_student_ids)

    # Local numeric sanitizer — coerce percentage to float or None.
    # Use this instead of `or` because legitimate 0 must not fall through.
    def _safe_percentage(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            _logger.warning(
                "non-numeric percentage value (type=%s, value=%r) — skipping",
                type(val).__name__, val,
            )
            return None

    # 7) Fetch non-draft submissions for these students × these contents (paginated)
    submissions = []
    if valid_student_ids:
        page_size = 1000
        start = 0
        while True:
            page = db.table('student_submissions').select(
                'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
            ).in_('student_id', valid_student_ids).in_('content_id', content_ids).neq(
                'status', 'draft'
            ).range(start, start + page_size - 1).execute()
            rows = page.data or []
            submissions.extend(rows)
            if len(rows) < page_size:
                break
            start += page_size

    # 8) Sanitize-in-place
    for s in submissions:
        _sanitize_standards_mastery(s)

    # Normalize percentage to float (or 0.0 sentinel) so best-mode's max(...) doesn't
    # TypeError on mixed numeric/string values. Distribution stats still call
    # _safe_percentage downstream on `_raw_percentage`, which converts non-numeric
    # back to None and skips them — preserving the existing skip contract.
    for s in submissions:
        s['_raw_percentage'] = s.get('percentage')
        coerced = _safe_percentage(s.get('percentage'))
        s['percentage'] = coerced if coerced is not None else 0.0

    # 9) Group submissions by (student_id, content_id)
    from collections import defaultdict
    import statistics as _stats
    subs_by_student_content = defaultdict(lambda: defaultdict(list))
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if sid and cid:
            subs_by_student_content[sid][cid].append(s)

    assessments_out = []
    # Keep selected_per_content for the standards-matrix bridge in Task 4.
    selected_per_content_per_student = {}
    for cid in content_ids:
        match = next((c for c in found if c.get('id') == cid), None)
        # Same _coalesce fallback ladder as Task 2 — row column → content JSON → settings JSON.
        if match:
            content_json = match.get('content') if isinstance(match.get('content'), dict) else None
            settings_json = match.get('settings') if isinstance(match.get('settings'), dict) else None
            max_points = _coalesce(
                match.get('max_points'),
                content_json.get('max_points') if content_json else None,
                settings_json.get('max_points') if settings_json else None,
                default=0,
            )
        else:
            max_points = 0
        title = match.get('title', '') if match else ''

        percentages = []
        selected_for_this_content = {}
        for sid in valid_student_ids:
            student_subs = subs_by_student_content.get(sid, {}).get(cid, [])
            if not student_subs:
                continue
            selected = _select_submissions_by_mode({cid: student_subs}, attempt_mode).get(cid, [])
            if attempt_mode == 'average':
                # Mean across attempts for this student. Read `_raw_percentage` (set above)
                # so non-numeric values are still skipped by _safe_percentage instead of
                # being counted as the 0.0 ranking sentinel.
                attempt_pcts = [_safe_percentage(s.get('_raw_percentage')) for s in student_subs]
                attempt_pcts = [p for p in attempt_pcts if p is not None]
                if not attempt_pcts:
                    continue
                student_pct = sum(attempt_pcts) / len(attempt_pcts)
            else:
                # latest/best modes — _select_submissions_by_mode picks one submission per
                # (student, content). The pre-pass normalization above coerced `percentage`
                # to a float (or 0.0 sentinel for non-numeric), so best-mode's max(...) is
                # safe. We still read `_raw_percentage` here so submissions with originally
                # non-numeric percentages get skipped from the distribution rather than
                # contributing the 0.0 sentinel.
                if not selected:
                    continue
                student_pct = _safe_percentage(selected[0].get('_raw_percentage'))
                if student_pct is None:
                    continue
            percentages.append(student_pct)
            selected_for_this_content[sid] = selected

        selected_per_content_per_student[cid] = selected_for_this_content

        n = len(percentages)
        if n >= 2:
            sorted_pcts = sorted(percentages)
            mean_v = round(sum(sorted_pcts) / n, 2)
            median_v = round(_stats.median(sorted_pcts), 2)
            quartiles = _stats.quantiles(sorted_pcts, n=4, method='inclusive')
            q1_v, q3_v = round(quartiles[0], 2), round(quartiles[2], 2)
            min_v, max_v = sorted_pcts[0], sorted_pcts[-1]
        elif n == 1:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = round(percentages[0], 2)
        else:
            mean_v = median_v = q1_v = q3_v = min_v = max_v = 0

        submission_rate = round(n / class_roster_size, 2) if class_roster_size > 0 else 0.0

        assessments_out.append({
            "content_id": cid,
            "title": title,
            "max_points": max_points,
            "n": n,
            "submission_rate": submission_rate,
            "mean": mean_v,
            "median": median_v,
            "min": min_v,
            "max": max_v,
            "q1": q1_v,
            "q3": q3_v,
            "percentages": [round(p, 2) for p in percentages],
        })

    # 10) Standards-matrix bridge: invert per-student mastery rollups into
    # per-(content_id, standard_code) class-mean cells.
    cells_accumulator: dict = {}  # cid -> standard_code -> list[float]
    content_titles = {c['id']: c.get('title', '') for c in found}
    for cid in content_ids:
        cells_accumulator[cid] = {}
        for sid, selected in selected_per_content_per_student.get(cid, {}).items():
            if not selected:
                continue
            mastery_by_code = _aggregate_mastery_for_student(
                {cid: selected}, content_titles, attempt_mode,
            )
            for code, m in mastery_by_code.items():
                pct = _safe_percentage(m.get('percentage'))
                if pct is None:
                    continue
                cells_accumulator[cid].setdefault(code, []).append(pct)

    cells_out: dict = {}
    all_standards: set = set()
    for cid, by_code in cells_accumulator.items():
        cells_out[cid] = {}
        for code, pct_list in by_code.items():
            students_assessed = len(pct_list)
            cells_out[cid][code] = {
                "percentage": round(sum(pct_list) / students_assessed, 2) if students_assessed > 0 else 0,
                "students_assessed": students_assessed,
            }
            all_standards.add(code)

    standards_matrix = {
        "standards": sorted(all_standards),
        "cells": cells_out,
    }

    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "attempt_mode": attempt_mode,
        "class_roster_size": class_roster_size,
        "assessments": assessments_out,
        "standards_matrix": standards_matrix,
    })


@student_portal_bp.route('/api/teacher/tags', methods=['GET'])
@require_teacher
@handle_route_errors
def list_teacher_tags():
    """Return all unique tags across the teacher's published content (both tables),
    including unit_name values and tags array values.
    """
    try:
        db = _get_teacher_supabase()
        teacher_id = g.teacher_id

        tag_set = set()

        pa = db.table('published_assessments').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pa.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        pc = db.table('published_content').select('settings').eq(
            'teacher_id', teacher_id
        ).execute()
        for row in pc.data or []:
            s = row.get('settings') or {}
            unit = s.get('unit_name')
            if unit and isinstance(unit, str) and unit.strip():
                tag_set.add(unit.strip())
            for t in (s.get('tags') or []):
                if isinstance(t, str) and t.strip():
                    tag_set.add(t.strip())

        return jsonify({"tags": sorted(tag_set)})
    except Exception as e:
        _logger.exception("List teacher tags error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/published-content/<content_id>/tags', methods=['POST'])
@require_teacher
@handle_route_errors
def set_content_tags(content_id):
    """Replace the tags array on a published content row (either table).

    Request: { "tags": [str, ...] }
    Preserves all other settings fields.
    """
    try:
        db = _get_teacher_supabase()
        data = request.json or {}
        raw_tags = data.get('tags')
        if not isinstance(raw_tags, list):
            return jsonify({"error": "tags must be an array"}), 400

        seen = set()
        clean_tags = []
        for t in raw_tags:
            if not isinstance(t, str):
                continue
            s = t.strip()
            if not s or s in seen:
                continue
            if len(s) > 100:
                s = s[:100]
            seen.add(s)
            clean_tags.append(s)

        table_name, row = _find_content_row(db, content_id, g.teacher_id)
        if not row:
            return jsonify({"error": "Content not found"}), 404

        existing_settings = row.get('settings') or {}
        existing_settings['tags'] = clean_tags

        db.table(table_name).update({'settings': existing_settings}).eq('id', content_id).execute()
        return jsonify({"success": True, "tags": clean_tags})
    except Exception as e:
        _logger.exception("Set content tags error")
        return jsonify({"error": "An internal error occurred"}), 500


@student_portal_bp.route('/api/teacher/class/<class_id>/remediate', methods=['POST'])
@require_teacher
@handle_route_errors
@limiter.limit("10 per minute")
def post_remediate(class_id):
    """Phase 4 Quick-Click Remediation: generate 8 grade-level practice
    questions targeted to a single student or class red-tier on one standard.

    Spec: docs/superpowers/specs/2026-04-26-phase4-quick-click-remediation-design.md
    """
    import uuid as _uuid

    db = _get_teacher_supabase()
    body = request.get_json(silent=True) or {}
    standard_code = (body.get('standard_code') or '').strip()
    target_mode = body.get('target_mode')
    target_student_id = body.get('target_student_id')

    # 1) Class ownership check
    cls = db.table('classes').select('id, name, teacher_id, grade_level, subject').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    cls_row = cls.data[0]

    # 2) target_mode validation
    if target_mode not in ('single_student', 'red_tier_in_class'):
        return error_response("target_mode must be 'single_student' or 'red_tier_in_class'", 400)

    # 3) Single-student: target_student_id required + UUID + enrollment
    if target_mode == 'single_student':
        if not target_student_id:
            return error_response("target_student_id is required for single_student mode", 400)
        try:
            _uuid.UUID(str(target_student_id))
        except (ValueError, TypeError):
            return error_response("target_student_id must be a valid UUID", 400)
        # Enrollment check: must be in class_students AND must exist in students.
        enr = db.table('class_students').select('student_id').eq(
            'class_id', class_id
        ).eq('student_id', target_student_id).execute()
        if not enr.data:
            return error_response("Student is not enrolled in this class", 403)
        stu = db.table('students').select('id').eq('id', target_student_id).execute()
        if not stu.data:
            return error_response("Student record not found", 403)

    # 4) standard_code non-empty
    if not standard_code:
        return error_response("standard_code is required", 400)

    # 4.5) Phase 4.2 #3: validate optional count + difficulty config.
    # Strict 400 on invalid explicit values; defaults only when missing.
    # Reject booleans explicitly — bool is an int subclass in Python, so
    # `count=true` would otherwise pass an `isinstance(int)` check.
    raw_count = body.get('count')
    if raw_count is None:
        count = REMEDIATION_COUNT_DEFAULT
    else:
        if isinstance(raw_count, bool) or not isinstance(raw_count, int):
            return error_response(
                f"count must be an integer between {REMEDIATION_COUNT_MIN} and {REMEDIATION_COUNT_MAX}",
                400,
            )
        if raw_count < REMEDIATION_COUNT_MIN or raw_count > REMEDIATION_COUNT_MAX:
            return error_response(
                f"count must be between {REMEDIATION_COUNT_MIN} and {REMEDIATION_COUNT_MAX}",
                400,
            )
        count = raw_count

    raw_difficulty = body.get('difficulty')
    if raw_difficulty is None:
        difficulty = REMEDIATION_DIFFICULTY_DEFAULT
    elif raw_difficulty in DIFFICULTY_OPTIONS:
        difficulty = raw_difficulty
    else:
        return error_response(
            "difficulty must be one of: " + ", ".join(DIFFICULTY_OPTIONS),
            400,
        )

    # Phase 4.2 #12: validate optional dok param. Same defensive pattern as
    # count — reject booleans (Python bool is int subclass), require int in
    # DOK_OPTIONS range. Default None (= Auto, no DOK directive in prompt).
    raw_dok = body.get('dok')
    if raw_dok is None:
        dok = REMEDIATION_DOK_DEFAULT
    else:
        if isinstance(raw_dok, bool) or not isinstance(raw_dok, int):
            return error_response(
                f"dok must be an integer in {list(DOK_OPTIONS)}",
                400,
            )
        if raw_dok not in DOK_OPTIONS:
            return error_response(
                "dok must be one of: " + ", ".join(str(d) for d in DOK_OPTIONS),
                400,
            )
        dok = raw_dok

    target_student_ids = []

    # Resolve current-class assessment/assignment content (matches Phase 2
    # Progress Rank scoping at lines 1393-1416). Both the single-student
    # historical evidence check AND the red-tier resolver MUST scope
    # submission queries to these content_ids so a student's submissions
    # in OTHER classes (covering the same standard) do not leak into THIS
    # class's remediation decisions. Spec promises parity with Progress Rank.
    class_content_rows = db.table('published_content').select(
        'id, title'
    ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()
    class_content_ids = [c['id'] for c in (class_content_rows.data or [])]
    class_content_titles = {c['id']: c.get('title', '') for c in (class_content_rows.data or [])}
    if not class_content_ids:
        # Edge case: no class content yet -> no historical evidence possible, no red tier.
        if target_mode == 'single_student':
            _logger.warning(
                "remediation.no_historical_evidence teacher=%s class=%s student=%s standard=%s reason=no_class_content",
                g.teacher_id, class_id, target_student_id, standard_code,
            )
            return error_response(
                "No prior assessment data on this standard for student",
                400,
            )
        else:  # red_tier_in_class
            _logger.warning(
                "remediation.no_red_tier_students teacher=%s class=%s standard=%s reason=no_class_content",
                g.teacher_id, class_id, standard_code,
            )
            return error_response("No red-tier students on this standard", 400)

    # 5) Single-student historical evidence check.
    if target_mode == 'single_student':
        # Fetch student's submissions whose results contain this standard.
        # Scoped to current-class content so out-of-class evidence does not count.
        subs = db.table('student_submissions').select(
            'id, percentage, results, status, submitted_at'
        ).eq('student_id', target_student_id).in_(
            'content_id', class_content_ids
        ).neq('status', 'draft').execute()
        has_evidence = False
        for s in (subs.data or []):
            mastery = (s.get('results') or {}).get('standards_mastery') or {}
            if isinstance(mastery, dict) and standard_code in mastery:
                has_evidence = True
                break
        if not has_evidence:
            _logger.warning(
                "remediation.no_historical_evidence teacher=%s class=%s student=%s standard=%s",
                g.teacher_id, class_id, target_student_id, standard_code,
            )
            return error_response(
                "No prior assessment data on this standard for student",
                400,
            )
        target_student_ids = [target_student_id]

    # 6) Red-tier resolution (class-wide). Uses the full Phase 2
    # _select_submissions_by_mode + _aggregate_mastery_for_student aggregation
    # pipeline so the red-tier set EXACTLY matches what teachers see in the
    # Progress Rank grid. A direct read of `results.standards_mastery[std]`
    # per latest submission would be cheaper, but could classify differently
    # when a student has multiple content rows touching the same standard --
    # the aggregation pipeline merges per-content mastery before thresholding.
    if target_mode == 'red_tier_in_class':
        # Resolve roster (skip orphans).
        enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
        enrolled_ids = [r['student_id'] for r in (enrollments.data or []) if r.get('student_id')]
        valid_ids = []
        if enrolled_ids:
            stu_rows = db.table('students').select('id').in_('id', enrolled_ids).execute()
            existing = {s['id'] for s in (stu_rows.data or []) if s.get('id')}
            valid_ids = [sid for sid in enrolled_ids if sid in existing]
        # Pull class submissions scoped to current-class content (matches
        # Progress Rank semantic). Out-of-class submissions on the same
        # standard must NOT influence red-tier classification for this class.
        red_tier = []
        if valid_ids:
            class_subs = db.table('student_submissions').select(
                'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
            ).in_('student_id', valid_ids).in_(
                'content_id', class_content_ids
            ).neq('status', 'draft').execute()
            # Group submissions by student -> content_id -> [submissions].
            from collections import defaultdict
            per_student = defaultdict(lambda: defaultdict(list))
            for s in (class_subs.data or []):
                sid = s.get('student_id')
                cid = s.get('content_id')
                if sid and cid:
                    per_student[sid][cid].append(s)
            # For each student: select latest per content, aggregate mastery, read standard's percentage.
            # Reuse class_content_titles built above -- avoids a redundant published_content fetch.
            for sid, by_cid in per_student.items():
                selected = _select_submissions_by_mode(by_cid, 'latest')
                mastery = _aggregate_mastery_for_student(selected, class_content_titles, 'latest')
                std_entry = mastery.get(standard_code) if isinstance(mastery, dict) else None
                if not std_entry:
                    continue
                pct = std_entry.get('percentage')
                if pct is None:
                    continue
                if pct < 70:
                    red_tier.append(sid)
        if not red_tier:
            _logger.warning(
                "remediation.no_red_tier_students teacher=%s class=%s standard=%s",
                g.teacher_id, class_id, standard_code,
            )
            return error_response("No red-tier students on this standard", 400)
        target_student_ids = red_tier

    # 6.5) Phase 4.2 #8: per-student weekly cap. Block before LLM call to
    # save AI cost on doomed publishes. /publish-to-class enforces the cap
    # again as defense against direct-API bypass.
    capped = _check_remediation_cap(db, g.teacher_id, target_student_ids)
    if capped:
        _logger.warning(
            "remediation.cap.exceeded teacher=%s class=%s standard=%s mode=%s capped=%s",
            g.teacher_id, class_id, standard_code, target_mode, capped,
        )
        return jsonify({
            "error": "Weekly remediation cap reached",
            "detail": (
                "Each student can receive at most "
                + str(REMEDIATION_PER_STUDENT_WEEKLY_CAP)
                + " remediations per rolling 7-day window. Wait up to "
                + "7 days for an older remediation to age out."
            ),
            "capped_student_ids": capped,
            "cap": REMEDIATION_PER_STUDENT_WEEKLY_CAP,
            "window_days": 7,
        }), 422

    # 6.6) Phase 4.2 #2: auto-decide whether to personalize. Personalize iff
    # at least one targeted student has a non-empty accommodation_segment.
    # Single-student mode is gated out — its existing accommodation logic at
    # the shared path (below) already covers it.
    # Spec: docs/superpowers/specs/2026-04-30-phase4.2-perstudent-gen-design.md
    should_personalize = False
    per_student_segments = {}
    if target_mode == 'red_tier_in_class' and len(target_student_ids) > 1:
        from backend.accommodations import build_accommodation_prompt as _bap
        for sid in target_student_ids:
            try:
                seg = _bap(sid, g.teacher_id) or ""
            except Exception:
                _logger.warning(
                    "remediation.personalize.accommodation_load_failed teacher=%s student=%s",
                    g.teacher_id, sid,
                )
                seg = ""
            per_student_segments[sid] = seg
            if seg:
                should_personalize = True

        if should_personalize and len(target_student_ids) > REMEDIATION_PERSONALIZED_MAX:
            _logger.warning(
                "remediation.personalize.too_many_students teacher=%s class=%s standard=%s n=%d",
                g.teacher_id, class_id, standard_code, len(target_student_ids),
            )
            return jsonify({
                "error": "Class has too many students for personalized mode",
                "detail": (
                    "Personalized remediation supports at most "
                    + str(REMEDIATION_PERSONALIZED_MAX)
                    + " students at a time. Use single-student mode for "
                    + "individual students, or remove accommodations from "
                    + "some students to fall back to shared mode."
                ),
                "target_count": len(target_student_ids),
                "max": REMEDIATION_PERSONALIZED_MAX,
            }), 422

    # If personalized, run the parallel path and return early.
    if should_personalize:
        # Fetch student names for tab labels (deterministic ordering).
        students_rows = db.table('students').select(
            'id, first_name, last_name'
        ).in_('id', target_student_ids).execute()
        students_by_id = {
            s['id']: s for s in (students_rows.data or []) if s.get('id')
        }

        grade = cls_row.get('grade_level') or '7'
        subject = cls_row.get('subject') or 'General'
        base_prompt = _build_remediation_prompt(
            grade=grade, subject=subject, standard_code=standard_code,
            count=count, difficulty=difficulty, dok=dok,
        )

        # Capture per-request context BEFORE submitting to the worker pool.
        # Workers must NEVER read Flask globals (Codex round 2 MAJOR).
        from backend.api_keys import get_api_key as _gak
        from backend.routes.planner_routes import _get_openai_context
        from backend.services.assignment_post_processing import _merge_usage
        api_key = _gak('openai', g.teacher_id)
        if not api_key or 'your-key-here' in api_key:
            return error_response("Missing OpenAI API key", 500)
        _ctx_uid, _ctx_client = _get_openai_context()
        captured_teacher_id = g.teacher_id
        captured_class_id = class_id

        from concurrent.futures import ThreadPoolExecutor, as_completed
        # Cap concurrency at 5 (Codex MAJOR) to reduce nondeterministic
        # rate-limit failures under all-or-nothing semantics.
        max_workers = min(len(target_student_ids), 5)
        variants = []
        errors = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _gen_variant_for_student,
                    sid=sid,
                    segment=per_student_segments.get(sid, ""),
                    students_by_id=students_by_id,
                    api_key=api_key,
                    base_prompt=base_prompt,
                    subject=subject,
                    grade=grade,
                    standard_code=standard_code,
                    ctx_uid=_ctx_uid,
                    ctx_client=_ctx_client,
                    teacher_id=captured_teacher_id,
                    class_id=captured_class_id,
                    count=count,
                ): sid
                for sid in target_student_ids
            }
            for fut in as_completed(futures):
                sid = futures[fut]
                try:
                    variants.append(fut.result())
                except Exception as e:
                    errors.append({'student_id': sid, 'error': str(e)})

        if errors:
            _logger.exception(
                "remediation.personalize.partial_failure teacher=%s class=%s standard=%s errors=%s",
                g.teacher_id, class_id, standard_code, errors,
            )
            return jsonify({
                "error": "One or more personalized variants failed to generate",
                "detail": "Try again. Personalized mode requires all variants to succeed.",
                "failed_student_ids": [e['student_id'] for e in errors],
            }), 500

        # Deterministic ordering by student_name (id fallback).
        variants.sort(key=lambda v: (
            (v.get('student_name') or '').lower(), v.get('student_id') or '',
        ))

        # Aggregate usage from workers and record once in parent thread
        # (Codex round 2 MINOR — cost telemetry thread-safety).
        from backend.services.assignment_post_processing import _record_planner_cost
        total_usage = {}
        for v in variants:
            v_usage = v.pop('usage', None) or {}
            total_usage = _merge_usage(total_usage, v_usage)
        if total_usage:
            _record_planner_cost(total_usage)

        _logger.info(
            "remediation.generated mode=personalized teacher=%s class=%s standard=%s n_variants=%d cost_tokens=%s",
            g.teacher_id, class_id, standard_code, len(variants),
            (total_usage or {}).get('total_tokens', 0),
        )

        return jsonify({
            "mode": "personalized",
            "count": count,
            "difficulty": difficulty,
            "dok": dok,
            "variants": variants,
            "target_mode": target_mode,
            "standard_code": standard_code,
            "generated_at": datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }), 200

    # 7) Build remediation prompt via the shared helper (Codex MAJOR — was
    # previously duplicated inline; now both shared and personalized paths
    # use the same _build_remediation_prompt single source of truth).
    # Phase 4.2 #3: count + difficulty parameterize the helper output.
    grade = cls_row.get('grade_level') or '7'
    subject = cls_row.get('subject') or 'General'
    base_prompt = _build_remediation_prompt(
        grade=grade, subject=subject, standard_code=standard_code,
        count=count, difficulty=difficulty, dok=dok,
    )

    accommodation_segment = ""
    if target_mode == 'single_student':
        try:
            from backend.accommodations import build_accommodation_prompt
            accommodation_segment = build_accommodation_prompt(target_student_id, g.teacher_id) or ""
        except Exception:
            _logger.warning(
                "remediation.accommodations_helper_failed teacher=%s student=%s",
                g.teacher_id, target_student_id,
            )
            accommodation_segment = ""
    if accommodation_segment:
        # Phase 4.2 #1: extend accommodation directive to apply to lesson text too.
        # Best-effort; AI compliance is not contracted (mixed-language output is acceptable).
        accommodation_segment = (
            accommodation_segment
            + "\n\nApply these accommodations to the lesson text as well as the questions."
        )
    final_prompt = base_prompt + ("\n\n" + accommodation_segment if accommodation_segment else "")

    # 8) Generate via OpenAIAdapter (matches planner_routes pattern).
    # Verified imports -- _get_openai_context lives in planner_routes; the post-processing
    # helpers (incl. _extract_usage/_merge_usage) live in assignment_post_processing
    # and are merely re-imported by planner_routes. Importing direct from the source
    # avoids an unnecessary circular-import surface.
    from backend.api_keys import get_api_key as _gak
    from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
    from backend.routes.planner_routes import _get_openai_context
    from backend.services.assignment_post_processing import (
        _post_process_assignment, _extract_usage, _merge_usage,
    )
    import json as _json

    api_key = _gak('openai', g.teacher_id)
    if not api_key or 'your-key-here' in api_key:
        return error_response("Missing OpenAI API key", 500)
    adapter = OpenAIAdapter(api_key=api_key)
    _ctx_uid, _ctx_client = _get_openai_context()

    # Narrow try/except: only the LLM call + JSON parse + post-process.
    # Anything outside (imports, api_key, adapter ctor, ctx fetch) should
    # surface its real cause to the caller, not a generic "Generation failed".
    try:
        completion = adapter.chat(LLMRequest(
            model="gpt-4o",
            system_prompt="You are an expert teacher. Return valid JSON only.",
            messages=[Message(role="user", content=[TextPart(text=final_prompt)])],
            response_format=ResponseFormat(type="json_object"),
            metadata={"feature_label": "remediation"},
        ))
        raw_text = completion.content_parts[0].text if completion.content_parts else "{}"
        assignment = _json.loads(raw_text)

        # Defensive: if the AI returned `{questions: [...]}` instead of sections shape,
        # wrap it so `_post_process_assignment`'s section iteration runs over the questions.
        # Phase 4.2 #1: must preserve `lesson` through the wrapper — without this,
        # AI responses with the {questions, lesson} shape would silently drop lesson.
        if isinstance(assignment, dict) and 'sections' not in assignment and 'questions' in assignment:
            assignment = {
                'title': assignment.get('title', f"Practice - {standard_code}"),
                'lesson': assignment.get('lesson'),
                'sections': [{'name': 'Practice', 'questions': assignment.get('questions') or []}],
            }

        # Capture lesson BEFORE _post_process_assignment runs. The processor
        # iterates `sections` only (assignment_post_processing.py:2113ish);
        # it doesn't touch top-level `lesson`. But capturing here makes the
        # validation order explicit and protects against future processor
        # changes.
        raw_lesson = assignment.get('lesson') if isinstance(assignment, dict) else None

        assignment, extra_usage = _post_process_assignment(
            assignment, count, target_total_points=count * 10,
            subject=subject, grade=grade,
            valid_standard_codes=[standard_code],
            user_id=_ctx_uid, client=_ctx_client,
        )
        usage = _merge_usage(_extract_usage(completion, "gpt-4o"), extra_usage)
    except Exception:
        _logger.exception("remediation.generation_failed teacher=%s class=%s standard=%s",
                          g.teacher_id, class_id, standard_code)
        return error_response("Generation failed", 500)

    # Flatten sections back to a single questions list for the drawer/wire.
    questions = []
    for section in (assignment or {}).get('sections', []):
        for q in section.get('questions', []):
            questions.append(q)
    # 422 floor: fewer than 3 valid questions after post-processing.
    if len(questions) < 3:
        return error_response("Generation produced too few valid questions", 422)

    # Phase 4.2 #1: validate the lesson and build a clean dict (or None).
    # Always-present `lesson` key in response (None if validation failed).
    clean_lesson = _validate_and_clean_lesson(
        raw_lesson, teacher_id=g.teacher_id, class_id=class_id, standard_code=standard_code,
    )

    # 9) Audit log.
    if accommodation_segment:
        _logger.info(
            "remediation.accommodations_applied teacher=%s class=%s student=%s",
            g.teacher_id, class_id, target_student_id,
        )
    _logger.info(
        "remediation.generated teacher=%s class=%s mode=%s standard=%s targets=%d cost_tokens=%s",
        g.teacher_id, class_id, target_mode, standard_code, len(target_student_ids),
        (usage or {}).get('total_tokens', 0),
    )

    # `datetime`/`timezone` are imported at module level (line 12).
    # Phase 4.2 #1: response ALWAYS includes `lesson` key. None if validation
    # failed; clean dict {intro, worked_example, key_takeaway} if valid.
    # Phase 4.2 #2: `mode` field distinguishes shared vs personalized response
    # shapes. Frontend reads it to decide single-preview vs tab-per-variant.
    return jsonify({
        "mode": "shared",
        "count": count,
        "difficulty": difficulty,
        "dok": dok,
        "questions": questions,
        "lesson": clean_lesson,
        "target_mode": target_mode,
        "target_student_ids": target_student_ids,
        "standard_code": standard_code,
        "generated_at": datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }), 200


@student_portal_bp.route('/api/teacher/class/<class_id>/remediation-effectiveness', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_remediation_effectiveness(class_id):
    """Phase 4.2 #6 — Remediation Effectiveness dashboard (read-only).

    Per-(student × remediation) row showing before/after mastery on the
    targeted standard, completion, and attempt count. Lets teachers answer
    "did my recent remediations work?" without leaving the analytics tab.

    Spec: docs/superpowers/specs/2026-04-27-phase4.2-effectiveness-dashboard-design.md

    Convention: a published_content row is treated as a remediation if
    target_student_ids IS NOT NULL. Today only /api/teacher/class/<id>/remediate
    populates this field; if another feature ever publishes to a class subset,
    add an `is_remediation` flag and update the filter here.
    """
    db = _get_teacher_supabase()

    # 1) Class ownership check.
    cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)
    class_name = cls.data[0].get('name')

    # 2) Fetch all published_content rows for this class.
    # NOTE: we cannot use PostgREST's null syntax (`.is_("target_student_ids",
    # "null")` / `.not_(...)`) because the existing test mock doesn't support
    # those operators. Phase 4 codebase already uses Python-side filters for the
    # same reason. So: fetch with .eq('class_id', X), then Python-filter for
    # `target_student_ids is not None` below.
    content_rows = db.table('published_content').select(
        'id, title, content_type, created_at, is_active, target_student_ids, settings, content'
    ).eq('class_id', class_id).execute()
    all_class_content = content_rows.data or []

    # `class_content_ids` covers the FULL class published_content set (NOT just
    # remediations) — used in step 5 to scope submissions. Without this scope,
    # a student's submissions in OTHER classes touching the same standard would
    # leak into THIS class's dashboard. Same lesson as Phase 4's cross-class
    # submission leakage bug (see test_excludes_out_of_class_submissions_for_evidence).
    class_content_ids = [c['id'] for c in all_class_content if c.get('id')]

    # Python-side filter: keep only rows that are remediations (target_student_ids
    # IS NOT NULL — distinct from `if c.get(...)` which would also exclude `[]`.
    # publish_to_class rejects empty arrays at write time so this is defensive,
    # but the spec contract is "non-null" not "truthy", so we match exactly).
    remediations = [c for c in all_class_content if c.get('target_student_ids') is not None]

    if not remediations:
        return jsonify({
            "class_id": class_id,
            "class_name": class_name,
            "remediations": [],
        })

    # 3) Resolve targeted standard for each remediation, with fallback ladder.
    # Defensive: settings.target_standard must be a non-empty string. Falls back
    # to content.questions[0].standard if missing (Phase 4 invariant: every
    # remediation question has the targeted code in its `standard` field).
    # Skip + warn if neither yields a non-empty string.
    def _extract_target_standard(rem):
        settings = rem.get('settings') if isinstance(rem.get('settings'), dict) else {}
        val = settings.get('target_standard') if settings else None
        if isinstance(val, str) and val.strip():
            return val.strip()
        # Fallback: content.questions[0].standard.
        content = rem.get('content') if isinstance(rem.get('content'), dict) else {}
        # Phase 4 produces sections-shaped content; flatten to find first question.
        first_q = None
        sections = content.get('sections') if isinstance(content.get('sections'), list) else []
        for sec in sections:
            qs = sec.get('questions') if isinstance(sec.get('questions'), list) else []
            if qs:
                first_q = qs[0]
                break
        if first_q is None:
            qs = content.get('questions') if isinstance(content.get('questions'), list) else []
            if qs:
                first_q = qs[0]
        if isinstance(first_q, dict):
            std = first_q.get('standard')
            if isinstance(std, str) and std.strip():
                return std.strip()
        return None

    rems_with_std = []
    for rem in remediations:
        std = _extract_target_standard(rem)
        if not std:
            _logger.warning(
                "remediation.unknown_standard remediation_id=%s class=%s teacher=%s",
                rem.get('id'), class_id, g.teacher_id,
            )
            continue
        rems_with_std.append((rem, std))

    if not rems_with_std:
        return jsonify({
            "class_id": class_id,
            "class_name": class_name,
            "remediations": [],
        })

    # 4) Build the union set of student IDs across all remediations and fetch
    # student names. Skips students that don't exist (orphan resilience).
    all_target_student_ids = set()
    for rem, _std in rems_with_std:
        for sid in (rem.get('target_student_ids') or []):
            if sid:
                all_target_student_ids.add(sid)

    student_name_by_id = {}
    if all_target_student_ids:
        stu_rows = db.table('students').select('id, name').in_(
            'id', list(all_target_student_ids)
        ).execute()
        student_name_by_id = {
            s['id']: (s.get('name') or '') for s in (stu_rows.data or []) if s.get('id')
        }

    # 5) Fetch student_submissions for these students — SCOPED to current-class
    # content. The .in_('content_id', class_content_ids) filter is critical:
    # without it, out-of-class submissions covering the same standard would
    # leak into the dashboard rows. (Phase 4 ate this bug; the regression test
    # is test_out_of_class_submissions_dont_leak.)
    submissions = []
    if all_target_student_ids and class_content_ids:
        sub_rows = db.table('student_submissions').select(
            'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
        ).in_('student_id', list(all_target_student_ids)).in_(
            'content_id', class_content_ids
        ).neq('status', 'draft').order('submitted_at', desc=True).execute()
        submissions = sub_rows.data or []

    # Sanitize standards_mastery in-place to drop malformed entries (matches
    # Phase 2/2b/3a/3b precedent).
    for s in submissions:
        _sanitize_standards_mastery(s)

    # 6) Build indexes ONCE.
    # `subs_by_student_with_standard[student_id][standard_code]` =
    #   ordered list of submissions where that student touched that standard,
    #   newest first.
    # NOTE: a submission with N standards in its results.standards_mastery is
    # intentionally appended to N different bucket lists (one per standard
    # key). Each bucket means "submissions touching THIS standard." This is
    # correct, not duplication.
    from collections import defaultdict
    subs_by_student_with_standard = defaultdict(lambda: defaultdict(list))
    attempts_by_student_content = defaultdict(int)
    for s in submissions:
        sid = s.get('student_id')
        cid = s.get('content_id')
        if not sid or not cid:
            continue
        attempts_by_student_content[(sid, cid)] += 1
        mastery = (s.get('results') or {}).get('standards_mastery') or {}
        if not isinstance(mastery, dict):
            continue
        for std_code in mastery.keys():
            subs_by_student_with_standard[sid][std_code].append(s)

    # Pre-sort each bucket by submitted_at DESC so "first item" = newest.
    # The query already used .order(submitted_at, desc=True), but the mock is
    # a no-op for .order(). Re-sort defensively in Python so behavior is the
    # same in tests and production.
    for sid_buckets in subs_by_student_with_standard.values():
        for std_code, bucket in sid_buckets.items():
            bucket.sort(key=lambda s: _parse_ts(s.get('submitted_at')), reverse=True)

    # Helper: read mastery percentage for a standard from a single submission.
    def _percentage_for_standard(sub, std_code):
        mastery = (sub.get('results') or {}).get('standards_mastery') or {}
        if not isinstance(mastery, dict):
            return None
        entry = mastery.get(std_code)
        if not isinstance(entry, dict):
            return None
        # Prefer pre-computed percentage; otherwise derive from points.
        pct = entry.get('percentage')
        if isinstance(pct, (int, float)):
            return float(pct)
        try:
            earned = float(entry.get('points_earned') or 0)
            possible = float(entry.get('points_possible') or 0)
        except (ValueError, TypeError):
            return None
        if possible <= 0:
            return None
        return round((earned / possible) * 100, 1)

    # 7) For each (remediation, student_id) pair, compute before/after/delta.
    out_remediations = []
    for rem, std_code in rems_with_std:
        rem_id = rem.get('id')
        rem_created = rem.get('created_at')
        rem_created_dt = _parse_ts(rem_created)
        target_ids = rem.get('target_student_ids') or []

        rows = []
        for sid in target_ids:
            if not sid:
                continue
            student_name = student_name_by_id.get(sid, '')
            std_buckets = subs_by_student_with_standard.get(sid, {})
            bucket = std_buckets.get(std_code, [])

            # Before: first item where submitted_at < remediation.created_at.
            # Bucket is sorted newest-first; iterate to find latest pre-event sub.
            before = None
            for sub in bucket:
                sub_dt = _parse_ts(sub.get('submitted_at'))
                if sub_dt < rem_created_dt:
                    before = _percentage_for_standard(sub, std_code)
                    break

            # After: newest item in bucket (regardless of which content
            # produced it). Q5 → A: this is current mastery, not bounded by
            # any subsequent remediation. For repeat (student × standard)
            # cases, an older card's `after` reflects the latest mastery
            # state — possibly moved further by a later remediation.
            after = None
            if bucket:
                after = _percentage_for_standard(bucket[0], std_code)

            delta = None
            if before is not None and after is not None:
                delta = round(after - before, 1)

            attempt_count = int(attempts_by_student_content.get((sid, rem_id), 0))
            completed = attempt_count > 0

            rows.append({
                'student_id': sid,
                'student_name': student_name,
                'before': before,
                'after': after,
                'delta': delta,
                'completed': completed,
                'attempt_count': attempt_count,
            })

        out_remediations.append({
            'remediation_id': rem_id,
            'title': rem.get('title') or '',
            'standard_code': std_code,
            'created_at': rem_created,
            'target_count': len([t for t in target_ids if t]),
            'is_active': bool(rem.get('is_active')) if rem.get('is_active') is not None else True,
            'rows': rows,
        })

    # Sort remediations newest-first for stable UI ordering.
    out_remediations.sort(
        key=lambda r: _parse_ts(r.get('created_at')), reverse=True,
    )

    return jsonify({
        "class_id": class_id,
        "class_name": class_name,
        "remediations": out_remediations,
    })


@student_portal_bp.route(
    '/api/teacher/class/<class_id>/remediation/<rem_id>/recall',
    methods=['POST'],
)
@require_teacher
@handle_route_errors
def recall_remediation(class_id, rem_id):
    """Phase 4.2 #5: soft-recall a remediation by flipping is_active=false.

    Hides the remediation from students who haven't engaged (the existing
    visibility helper `_content_visible_to_student` gates on is_active).
    Submissions already made are preserved. Reversible at the DB level
    (just flip is_active=true again) — no UI for un-recall in this slice.

    No schema migration; reuses the existing is_active column.
    Idempotent: already-recalled returns 200 with `already_recalled: true`.
    """
    db = _get_teacher_supabase()

    # 1) Class ownership check (first, to avoid existence-leak: a teacher
    # who doesn't own the class shouldn't learn whether rem_id exists).
    cls = db.table('classes').select('id, teacher_id').eq('id', class_id).execute()
    if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
        return error_response("Not authorized", 403)

    # 2) Remediation lookup, class-scoped.
    rem_rows = db.table('published_content').select(
        'id, is_active, target_student_ids'
    ).eq('id', rem_id).eq('class_id', class_id).execute()
    if not rem_rows.data:
        return error_response("Remediation not found", 404)
    rem = rem_rows.data[0]

    # 3) Defense-in-depth: refuse non-remediation content. Endpoint name
    # says "remediation"; identical 404 message intentionally — don't leak
    # whether the ID exists as non-remediation content.
    if rem.get('target_student_ids') is None:
        return error_response("Remediation not found", 404)

    # 4) Idempotent: already recalled.
    if not rem.get('is_active'):
        _logger.info(
            "remediation.recalled rem_id=%s class=%s teacher=%s already_recalled=True",
            rem_id, class_id, g.teacher_id,
        )
        return jsonify({
            "recalled": True,
            "already_recalled": True,
            "rem_id": rem_id,
        })

    # 5) Action: flip is_active=false. Belt-and-suspenders class-scoping
    # in WHERE clause beyond step 2's verification.
    db.table('published_content').update({'is_active': False}).eq(
        'id', rem_id
    ).eq('class_id', class_id).execute()

    _logger.info(
        "remediation.recalled rem_id=%s class=%s teacher=%s already_recalled=False",
        rem_id, class_id, g.teacher_id,
    )
    return jsonify({
        "recalled": True,
        "already_recalled": False,
        "rem_id": rem_id,
    })
