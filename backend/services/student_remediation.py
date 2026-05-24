"""Remediation domain logic for the student portal.

Wave 5 Slice 2 - extracted verbatim from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; callers pass any
DB handle and OpenAI/LLM context in explicitly. Re-exported from
student_portal_routes.py so existing imports and
``patch('backend.routes.student_portal_routes.<name>')`` keep working.
"""
import logging

from backend.services.dok import DOK_OPTIONS, DOK_DESCRIPTIONS
from backend.services.student_mastery import (
    _sanitize_standards_mastery,
    _select_submissions_by_mode,
    _aggregate_mastery_for_student,
)

_logger = logging.getLogger(__name__)


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


def student_has_standard_evidence(db, student_id, class_content_ids, standard_code):
    """True iff the student has any non-draft submission (scoped to the given
    class content) whose results.standards_mastery contains `standard_code`.

    Wave 5 Slice 5 - extracted verbatim from post_remediate's single-student
    historical-evidence check. The route keeps the warning log + 400.
    """
    subs = db.table('student_submissions').select(
        'id, percentage, results, status, submitted_at'
    ).eq('student_id', student_id).in_(
        'content_id', class_content_ids
    ).neq('status', 'draft').execute()
    for s in (subs.data or []):
        mastery = (s.get('results') or {}).get('standards_mastery') or {}
        if isinstance(mastery, dict) and standard_code in mastery:
            return True
    return False


def resolve_red_tier_students(db, class_id, class_content_ids, class_content_titles, standard_code):
    """Return the list of student_ids in the class who are red-tier (<70%) on
    `standard_code`, using the full Progress-Rank aggregation pipeline so the set
    EXACTLY matches the Progress Rank grid. Scoped to current-class content.

    Wave 5 Slice 5 - extracted verbatim from post_remediate's red-tier resolver.
    The route keeps the empty->400 + warning log.
    """
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

        # Phase 4.3 Sprint 2 (Codex MAJOR): sanitize before aggregation
        # so old-shape and malformed entries are normalized in place
        # before _aggregate_mastery_for_student inspects them. The
        # aggregator's internal adapter handles shape conversion, but
        # this also drops malformed entries early.
        for s in (class_subs.data or []):
            _sanitize_standards_mastery(s)

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
    return red_tier
