"""Pure mastery/trajectory computation for the student portal.

Wave 5 Slice 1 - extracted verbatim from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; callers pass any
DB handle in explicitly. Re-exported from student_portal_routes.py so existing
imports and ``patch('backend.routes.student_portal_routes.<name>')`` keep working.
"""
import logging
from datetime import datetime

from backend.services.dok import _validate_dok

_logger = logging.getLogger(__name__)


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


def _aggregate_mastery_for_student(selected_submissions_by_content, content_titles, attempt_mode, *, include_dok=False):
    """Aggregate standards_mastery across submissions into a per-standard dict.

    Phase 4.3 Sprint 2 — internals operate on normalized (new) shape via
    _normalize_mastery_shape. Output is flat-by-default (preserves the
    pre-Sprint-2 API contract for existing routes); pass include_dok=True
    to emit new shape with by_dok aggregates (Student Report Card).

    Args:
        selected_submissions_by_content: { content_id: [submission, ...] }
            (one per content unless attempt_mode == 'average')
        content_titles: { content_id: title }
        attempt_mode: 'latest' | 'best' | 'average'
        include_dok: when True, emit {overall, by_dok} per standard.

    Returns:
        Flat shape (default):
            { standard_code: { percentage, points_earned, points_possible,
              question_count, contributing_submissions } }
        New shape (include_dok=True):
            { standard_code: { overall: {percentage, points_earned,
              points_possible, question_count, contributing_submissions},
              by_dok: { N: {percentage, points_earned, points_possible,
              question_count} } } }
    """
    from collections import defaultdict

    def _new_overall_total():
        return {
            'points_earned': 0.0,
            'points_possible': 0.0,
            'question_count': 0,
            'contributing_submissions': [],
        }

    def _new_dok_total():
        return {
            'points_earned': 0.0,
            'points_possible': 0.0,
            'question_count': 0,
        }

    overall_totals = defaultdict(_new_overall_total)
    # by_dok_totals[code][dok] -> dok_total dict
    by_dok_totals = defaultdict(lambda: defaultdict(_new_dok_total))

    for content_id, subs in selected_submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'average' and len(subs) > 1:
            # Average each standard's percentage across attempts, then scale
            # to "weighted earned" by attempt.
            per_standard_avg = defaultdict(lambda: {
                'pct_sum': 0.0, 'count': 0, 'pts_poss': 0, 'q_count': 0,
                'attempts': [], 'by_dok_pct_sum': defaultdict(float),
                'by_dok_pct_count': defaultdict(int),
                'by_dok_pts_poss': defaultdict(int),
                'by_dok_q_count': defaultdict(int),
            })
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, raw_entry in mastery.items():
                    normalized = _normalize_mastery_shape(raw_entry)
                    if normalized is None:
                        continue
                    overall = normalized['overall']
                    if not overall.get('points_possible'):
                        continue
                    pct = (overall.get('points_earned', 0) / overall['points_possible']) * 100
                    per_standard_avg[code]['pct_sum'] += pct
                    per_standard_avg[code]['count'] += 1
                    # Average mode: pts_poss / q_count overwrite per attempt (last wins).
                    # Consistent with pre-Sprint-2 behavior — the load-bearing value is
                    # the averaged percentage, computed below. Same invariant applies to
                    # by_dok_pts_poss / by_dok_q_count (see ~15 lines down).
                    per_standard_avg[code]['pts_poss'] = overall.get('points_possible', 0)
                    per_standard_avg[code]['q_count'] = overall.get('question_count', 0)
                    per_standard_avg[code]['attempts'].append({
                        'submission_id': sub.get('id'),
                        'attempt_number': sub.get('attempt_number', 1),
                        'points_earned': overall.get('points_earned', 0),
                        'points_possible': overall['points_possible'],
                    })
                    if include_dok:
                        for dok, d_agg in normalized.get('by_dok', {}).items():
                            if not d_agg.get('points_possible'):
                                continue
                            d_pct = (d_agg.get('points_earned', 0) / d_agg['points_possible']) * 100
                            per_standard_avg[code]['by_dok_pct_sum'][dok] += d_pct
                            per_standard_avg[code]['by_dok_pct_count'][dok] += 1
                            per_standard_avg[code]['by_dok_pts_poss'][dok] = d_agg.get('points_possible', 0)
                            per_standard_avg[code]['by_dok_q_count'][dok] = d_agg.get('question_count', 0)
            for code, agg in per_standard_avg.items():
                avg_pct = agg['pct_sum'] / agg['count']
                overall_totals[code]['points_earned'] += (avg_pct / 100.0) * agg['pts_poss']
                overall_totals[code]['points_possible'] += agg['pts_poss']
                overall_totals[code]['question_count'] += agg['q_count']
                for a in agg['attempts']:
                    overall_totals[code]['contributing_submissions'].append({
                        'submission_id': a['submission_id'],
                        'title': content_titles.get(content_id, ''),
                        'points_earned': a['points_earned'],
                        'points_possible': a['points_possible'],
                        'attempt_number': a['attempt_number'],
                    })
                if include_dok:
                    for dok, ct in agg['by_dok_pct_count'].items():
                        if ct == 0:
                            continue
                        d_avg_pct = agg['by_dok_pct_sum'][dok] / ct
                        d_pts_poss = agg['by_dok_pts_poss'][dok]
                        by_dok_totals[code][dok]['points_earned'] += (d_avg_pct / 100.0) * d_pts_poss
                        by_dok_totals[code][dok]['points_possible'] += d_pts_poss
                        by_dok_totals[code][dok]['question_count'] += agg['by_dok_q_count'][dok]
        else:
            # latest / best (already pre-selected upstream) — sum directly
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, raw_entry in mastery.items():
                    normalized = _normalize_mastery_shape(raw_entry)
                    if normalized is None:
                        continue
                    overall = normalized['overall']
                    if not overall.get('points_possible'):
                        continue
                    overall_totals[code]['points_earned'] += overall.get('points_earned', 0)
                    overall_totals[code]['points_possible'] += overall['points_possible']
                    overall_totals[code]['question_count'] += overall.get('question_count', 0)
                    overall_totals[code]['contributing_submissions'].append({
                        'submission_id': sub.get('id'),
                        'title': content_titles.get(content_id, ''),
                        'points_earned': overall.get('points_earned', 0),
                        'points_possible': overall['points_possible'],
                        'attempt_number': sub.get('attempt_number', 1),
                    })
                    if include_dok:
                        for dok, d_agg in normalized.get('by_dok', {}).items():
                            if not d_agg.get('points_possible'):
                                continue
                            by_dok_totals[code][dok]['points_earned'] += d_agg.get('points_earned', 0)
                            by_dok_totals[code][dok]['points_possible'] += d_agg['points_possible']
                            by_dok_totals[code][dok]['question_count'] += d_agg.get('question_count', 0)

    # Compute final percentages and project output shape
    result = {}
    for code, t in overall_totals.items():
        pct = round((t['points_earned'] / t['points_possible']) * 100, 1) if t['points_possible'] > 0 else 0
        contributing = sorted(
            t['contributing_submissions'],
            key=lambda c: c.get('attempt_number') or 0,
            reverse=True,
        )[:10]
        overall_out = {
            'percentage': pct,
            'points_earned': round(t['points_earned'], 2),
            'points_possible': t['points_possible'],
            'question_count': t['question_count'],
            'contributing_submissions': contributing,
        }
        if include_dok:
            by_dok_out = {}
            for dok, dt in by_dok_totals[code].items():
                d_pct = round((dt['points_earned'] / dt['points_possible']) * 100, 1) if dt['points_possible'] > 0 else 0
                by_dok_out[dok] = {
                    'percentage': d_pct,
                    'points_earned': round(dt['points_earned'], 2),
                    'points_possible': dt['points_possible'],
                    'question_count': dt['question_count'],
                }
            result[code] = {'overall': overall_out, 'by_dok': by_dok_out}
        else:
            result[code] = overall_out
    return result


def _build_standards_breakdown_for_student(mastery_by_code, submission_lookup):
    """Convert _aggregate_mastery_for_student's dict output to the
    standards_breakdown array shape required by the report-card endpoint.

    - Sorts ASC by percentage (worst-first) per Phase 2b spec.
    - Enriches each contributing_submission with `submitted_at` and
      `percentage` (computed from points_earned / points_possible).
      Pulls `submitted_at` from `submission_lookup` (a dict keyed by
      submission_id). Keeps the existing 10-cap from the upstream helper.

    Phase 4.3 Sprint 2: when input carries the new shape (mastery_by_code
    entries with `overall` + `by_dok` keys, emitted by the aggregator
    when called with `include_dok=True`), each row gains a `by_dok`
    array of {dok, percentage, points_earned, points_possible,
    question_count} sorted ASC by dok. For flat-shape input
    (pre-Sprint-2 stored data or include_dok=False callers), `by_dok`
    is `[]`.

    Args:
        mastery_by_code: dict from _aggregate_mastery_for_student
        submission_lookup: dict[submission_id -> submission row] for enrichment
    Returns:
        list[dict] sorted ASC by percentage; each dict has
        {code, percentage, points_earned, points_possible, question_count,
         contributing_submissions, by_dok}. Each contributing_submission
        has submission_id, title, attempt_number, points_earned,
        points_possible, percentage, submitted_at. Each by_dok entry has
        dok, percentage, points_earned, points_possible, question_count
        (sorted ASC by dok); empty list when no DOK data is present.
    """
    rows = []
    for code, m in mastery_by_code.items():
        # Phase 4.3 Sprint 2 — when aggregator was called with include_dok=True,
        # `m` carries {overall, by_dok}. Otherwise it's flat (pre-Sprint-2
        # contract). Detect via 'overall' presence.
        if 'overall' in m:
            ov = m['overall']
            by_dok_rows = []
            for dok in sorted(m.get('by_dok') or {}):
                d = m['by_dok'][dok]
                by_dok_rows.append({
                    'dok': dok,
                    'percentage': d.get('percentage', 0),
                    'points_earned': d.get('points_earned', 0),
                    'points_possible': d.get('points_possible', 0),
                    'question_count': d.get('question_count', 0),
                })
        else:
            ov = m
            by_dok_rows = []
        enriched_contribs = []
        for c in ov.get("contributing_submissions", []):
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
            "percentage": ov.get("percentage", 0),
            "points_earned": ov.get("points_earned", 0),
            "points_possible": ov.get("points_possible", 0),
            "question_count": ov.get("question_count", 0),
            "contributing_submissions": enriched_contribs,
            "by_dok": by_dok_rows,
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


def _flatten_mastery_for_response(results):
    """Project new-shape standards_mastery to flat shape for response.

    Phase 4.3 Sprint 2 — endpoints that return raw `results` JSONB
    (e.g., assessment results, class content submissions) must keep
    emitting the pre-Sprint-2 flat shape per the API contract policy.
    Only Student Report Card opts into the new {overall, by_dok} shape
    via aggregator's include_dok flag.

    Reads `results['standards_mastery']`. For each new-shape entry
    ({overall, by_dok}), emits flat {percentage, points_earned,
    points_possible, question_count}. Old flat entries pass through
    unchanged. Returns a NEW results dict (does not mutate input).

    Returns the input unchanged when results is None or not a dict.
    """
    if not isinstance(results, dict):
        return results
    raw = results.get('standards_mastery')
    if not isinstance(raw, dict):
        return results
    flattened = {}
    for code, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        if 'overall' in entry and isinstance(entry.get('overall'), dict):
            ov = entry['overall']
            pts_earned = ov.get('points_earned', 0) or 0
            pts_possible = ov.get('points_possible', 0) or 0
            pct = ov.get('percentage')
            if not isinstance(pct, (int, float)):
                pct = round((pts_earned / pts_possible) * 100, 1) if pts_possible > 0 else 0
            flattened[code] = {
                'percentage': pct,
                'points_earned': pts_earned,
                'points_possible': pts_possible,
                'question_count': ov.get('question_count', 0),
            }
        else:
            # Old flat shape — pass through (filter out by_dok if present)
            flattened[code] = {
                'percentage': entry.get('percentage', 0),
                'points_earned': entry.get('points_earned', 0),
                'points_possible': entry.get('points_possible', 0),
                'question_count': entry.get('question_count', 0),
            }
    new_results = dict(results)
    new_results['standards_mastery'] = flattened
    return new_results


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
