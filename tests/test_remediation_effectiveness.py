"""Tests for the Phase 4.2 #6 Remediation Effectiveness dashboard.

Spec: docs/superpowers/specs/2026-04-27-phase4.2-effectiveness-dashboard-design.md

Reuses the filter-aware `_make_chain` mock from Phase 3b/4 tests.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Fixtures ============

@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    from backend.extensions import limiter
    flask_app.config['TESTING'] = True
    flask_app.config['RATELIMIT_ENABLED'] = False
    limiter.enabled = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


@pytest.fixture
def client_no_auth():
    """Minimal Flask app WITHOUT the dev-mode before_request hook so
    require_teacher can return 401."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.config['RATELIMIT_ENABLED'] = False
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Filter-aware Supabase mock — applies .eq() / .in_() / .neq() filters
    and .range() slicing at .execute() time. Mirrors Phase 3b/4 precedent.

    `.order()` and `.limit()` are no-ops; tests must control row order via
    `submitted_at` values when ordering matters for the route's logic.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    filters = []
    range_bounds = []

    def _eq(field, value):
        filters.append(('eq', field, value))
        return chain
    chain.eq.side_effect = _eq

    def _in(field, values):
        filters.append(('in', field, list(values)))
        return chain
    chain.in_.side_effect = _in

    def _neq(field, value):
        filters.append(('neq', field, value))
        return chain
    chain.neq.side_effect = _neq

    def _range(start, end):
        range_bounds.append((start, end))
        return chain
    chain.range.side_effect = _range

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
        if range_bounds:
            start, end = range_bounds[-1]
            result = result[start:end + 1]
            range_bounds.clear()
        filters.clear()
        return MagicMock(data=result)
    chain.execute.side_effect = _execute
    return chain


def _multi_table_sb(table_map):
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ============ Test data ============

CLS_OWNED = [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}]
CLS_OTHER_OWNER = [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'OTHER-TEACHER'}]

# All-digit UUIDs to satisfy any uuid.UUID() validation downstream.
STU_1 = '11111111-aaaa-aaaa-aaaa-111111111111'
STU_2 = '22222222-bbbb-bbbb-bbbb-222222222222'
STU_3 = '33333333-cccc-cccc-cccc-333333333333'

CID_REM_1 = '11111111-1111-1111-1111-111111111111'
CID_REM_2 = '22222222-2222-2222-2222-222222222222'
CID_ASSESSMENT_1 = '33333333-3333-3333-3333-333333333333'
CID_ASSESSMENT_2 = '44444444-4444-4444-4444-444444444444'
CID_OTHER_CLASS = '55555555-5555-5555-5555-555555555555'
CID_REM_OTHER = '66666666-6666-6666-6666-666666666666'

STD_AR_1 = 'MA.6.AR.1.2'
STD_NS_1 = 'MA.6.NS.1.1'


def _rem(cid, target_ids, std=STD_AR_1, created_at='2026-04-15T12:00:00Z',
         class_id='cls-1', title=None, settings=None, content=None):
    """Build a remediation published_content row. settings.target_standard
    defaults to `std`; pass `settings={}` to test the fallback path."""
    if settings is None:
        settings = {'target_standard': std}
    if title is None:
        title = f"Remediation: {std}"
    return {
        'id': cid, 'class_id': class_id, 'title': title,
        'content_type': 'assessment', 'created_at': created_at,
        'target_student_ids': target_ids, 'settings': settings,
        'content': content or {'sections': [{'questions': [{'standard': std}]}]},
    }


def _non_rem(cid, class_id='cls-1', std=STD_AR_1):
    """Build a NON-remediation published_content row (target_student_ids is None)."""
    return {
        'id': cid, 'class_id': class_id, 'title': f"Quiz {cid[:4]}",
        'content_type': 'assessment', 'created_at': '2026-04-01T00:00:00Z',
        'target_student_ids': None, 'settings': {},
        'content': {'sections': [{'questions': [{'standard': std}]}]},
    }


def _sub(sub_id, student_id, content_id, mastery_dict,
         submitted_at='2026-04-10T10:00:00Z', status='graded', attempt=1, percentage=50):
    return {
        'id': sub_id, 'student_id': student_id, 'content_id': content_id,
        'attempt_number': attempt, 'submitted_at': submitted_at,
        'percentage': percentage,
        'results': {'standards_mastery': mastery_dict, 'score': percentage / 10, 'total_points': 10},
        'status': status,
    }


def _mastery(std=STD_AR_1, earned=4, possible=10, q_count=2):
    """Mastery dict shape: percentage = earned/possible * 100."""
    return {std: {'percentage': round((earned / possible) * 100, 1),
                  'points_earned': earned, 'points_possible': possible,
                  'question_count': q_count}}


# ============ Auth tests ============

class TestEffectivenessAuth:
    """401 for unauth, 403 for wrong-teacher class."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/remediation-effectiveness')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OTHER_OWNER})
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        assert resp.status_code == 403


# ============ Happy-path tests ============

class TestEffectivenessHappyPath:
    """Empty class, single rem × single student improved/didn't improve, multiple rems same standard."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_class_returns_no_remediations(self, mock_sb_fn, client, teacher_headers):
        """Class with zero published_content rows — returns remediations: []."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [],
            'students': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['class_id'] == 'cls-1'
        assert body['class_name'] == 'Period 3'
        assert body['remediations'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_rem_single_student_improved(self, mock_sb_fn, client, teacher_headers):
        """Student had 40% pre-rem on standard, now has 80% — Δ = +40, completed=True, attempt_count=1."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1], created_at='2026-04-15T12:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                # Pre-rem: scored 40% on the standard.
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                # Post-rem: scored 80% on the same standard via the rem itself.
                _sub('s-rem', STU_1, CID_REM_1, _mastery(earned=8, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['remediations']) == 1
        rem = body['remediations'][0]
        assert rem['standard_code'] == STD_AR_1
        assert rem['target_count'] == 1
        assert len(rem['rows']) == 1
        row = rem['rows'][0]
        assert row['student_id'] == STU_1
        assert row['student_name'] == 'Alex'
        assert row['before'] == 40.0
        assert row['after'] == 80.0
        assert row['delta'] == 40.0
        assert row['completed'] is True
        assert row['attempt_count'] == 1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_single_rem_single_student_didnt_improve(self, mock_sb_fn, client, teacher_headers):
        """Student had 60% pre-rem, scored 40% on the rem — Δ = -20."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1]),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=6, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                _sub('s-rem', STU_1, CID_REM_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        row = body['remediations'][0]['rows'][0]
        assert row['before'] == 60.0
        assert row['after'] == 40.0
        assert row['delta'] == -20.0
        assert row['completed'] is True

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_multiple_rems_same_student_same_standard_distinct_rows(self, mock_sb_fn, client, teacher_headers):
        """Two remediations for the same (student, standard) → 2 separate cards."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1], created_at='2026-04-12T10:00:00Z'),
                _rem(CID_REM_2, [STU_1], created_at='2026-04-20T10:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                _sub('s-rem1', STU_1, CID_REM_1, _mastery(earned=6, possible=10),
                     submitted_at='2026-04-13T10:00:00Z'),
                _sub('s-rem2', STU_1, CID_REM_2, _mastery(earned=9, possible=10),
                     submitted_at='2026-04-21T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        assert len(body['remediations']) == 2
        rem_ids = [r['remediation_id'] for r in body['remediations']]
        assert CID_REM_1 in rem_ids
        assert CID_REM_2 in rem_ids


# ============ Edge-case tests ============

class TestEffectivenessEdgeCases:
    """NULL baseline, didn't complete, multiple students per rem, target_standard fallback,
    and the historical-card-shows-current-mastery (Q5 attribution) case."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_null_baseline_no_pre_rem_submission(self, mock_sb_fn, client, teacher_headers):
        """No submission before the rem → before is null, delta is null, after still computed."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1], created_at='2026-04-15T12:00:00Z'),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                # Only post-rem submission exists.
                _sub('s-rem', STU_1, CID_REM_1, _mastery(earned=7, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        row = body['remediations'][0]['rows'][0]
        assert row['before'] is None
        assert row['after'] == 70.0
        assert row['delta'] is None
        assert row['completed'] is True

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_student_didnt_complete_remediation(self, mock_sb_fn, client, teacher_headers):
        """Student was targeted but never submitted the remediation. completed=False, attempt_count=0.
        After still reflects latest mastery from non-rem sources (Q5 → A)."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1], created_at='2026-04-15T12:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                # Pre-rem mastery of 40%
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                # No submission for CID_REM_1 — student never completed the rem.
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        row = body['remediations'][0]['rows'][0]
        assert row['before'] == 40.0
        # After: latest mastery on this standard = pre-rem submission (newest is also the only one).
        assert row['after'] == 40.0
        assert row['delta'] == 0.0
        assert row['completed'] is False
        assert row['attempt_count'] == 0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_multiple_students_per_remediation(self, mock_sb_fn, client, teacher_headers):
        """One rem targeting two students → one card with two rows."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1, STU_2], created_at='2026-04-15T12:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [
                {'id': STU_1, 'name': 'Alex'},
                {'id': STU_2, 'name': 'Bailey'},
            ],
            'student_submissions': [
                _sub('s1-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=3, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                _sub('s1-rem', STU_1, CID_REM_1, _mastery(earned=8, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
                _sub('s2-pre', STU_2, CID_ASSESSMENT_1, _mastery(earned=5, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                _sub('s2-rem', STU_2, CID_REM_1, _mastery(earned=7, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        rem = body['remediations'][0]
        assert rem['target_count'] == 2
        assert len(rem['rows']) == 2
        rows_by_id = {r['student_id']: r for r in rem['rows']}
        assert rows_by_id[STU_1]['delta'] == 50.0
        assert rows_by_id[STU_2]['delta'] == 20.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_target_standard_fallback_to_questions_first_standard(self, mock_sb_fn, client, teacher_headers):
        """settings.target_standard missing → fall back to content.questions[0].standard."""
        rem_row = _rem(CID_REM_1, [STU_1])
        # Strip target_standard from settings; rely on content fallback.
        rem_row['settings'] = {}
        # content already has sections[0].questions[0].standard = STD_AR_1
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [rem_row, _non_rem(CID_ASSESSMENT_1)],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
                _sub('s-rem', STU_1, CID_REM_1, _mastery(earned=8, possible=10),
                     submitted_at='2026-04-16T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Standard was inferred — the rem still appears.
        assert len(body['remediations']) == 1
        assert body['remediations'][0]['standard_code'] == STD_AR_1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_historical_card_shows_current_mastery(self, mock_sb_fn, client, teacher_headers):
        """Q5 attribution: an OLDER remediation's `after` reflects current mastery,
        which may have moved further due to a SUBSEQUENT remediation. We show the
        latest, not freeze at the next-event boundary."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_1, [STU_1], created_at='2026-04-12T10:00:00Z'),
                _rem(CID_REM_2, [STU_1], created_at='2026-04-20T10:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                _sub('s-pre', STU_1, CID_ASSESSMENT_1, _mastery(earned=4, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),  # 40%
                _sub('s-rem1', STU_1, CID_REM_1, _mastery(earned=6, possible=10),
                     submitted_at='2026-04-13T10:00:00Z'),  # 60%
                _sub('s-rem2', STU_1, CID_REM_2, _mastery(earned=9, possible=10),
                     submitted_at='2026-04-21T10:00:00Z'),  # 90%
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        # Both rems present.
        rems_by_id = {r['remediation_id']: r for r in body['remediations']}
        rem1 = rems_by_id[CID_REM_1]
        rem2 = rems_by_id[CID_REM_2]
        # rem1's `after` is the LATEST mastery on the standard = 90%, not 60%.
        # This is the Q5 → A semantics: historical cards reflect current mastery.
        assert rem1['rows'][0]['after'] == 90.0
        assert rem1['rows'][0]['before'] == 40.0
        # rem2's `before` is the latest pre-2026-04-20 mastery on the standard = 60%.
        assert rem2['rows'][0]['before'] == 60.0
        assert rem2['rows'][0]['after'] == 90.0


# ============ Isolation tests ============

class TestEffectivenessIsolation:
    """Other class's rems not leaked, non-rems excluded, out-of-class submissions don't leak."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_class_remediations_not_leaked(self, mock_sb_fn, client, teacher_headers):
        """A remediation row in cls-OTHER must not appear in cls-1's dashboard."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem(CID_REM_OTHER, [STU_1], class_id='cls-OTHER',
                     created_at='2026-04-15T12:00:00Z'),
                _non_rem(CID_ASSESSMENT_1),  # cls-1
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # No remediations at all in cls-1 (the only "rem" was in cls-OTHER).
        assert body['remediations'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_non_remediation_published_content_excluded(self, mock_sb_fn, client, teacher_headers):
        """published_content with target_student_ids IS NULL must be filtered out
        — that's a class-wide assessment, not a remediation."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                # Class-wide assessment (NOT a remediation).
                _non_rem(CID_ASSESSMENT_1),
                _non_rem(CID_ASSESSMENT_2),
                # Actual remediation.
                _rem(CID_REM_1, [STU_1], created_at='2026-04-15T12:00:00Z'),
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        # Only the rem appears.
        assert len(body['remediations']) == 1
        assert body['remediations'][0]['remediation_id'] == CID_REM_1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_out_of_class_submissions_dont_leak(self, mock_sb_fn, client, teacher_headers):
        """Codex round 3: a student's submissions in another class on the same
        standard must NOT influence this class's effectiveness rows. Class-scoping
        via .in_('content_id', class_content_ids) is critical (same lesson as
        Phase 4's cross-class-submission-leakage bug)."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                # cls-1 rem
                _rem(CID_REM_1, [STU_1], created_at='2026-04-15T12:00:00Z'),
                # cls-1 has NO baseline content for this student.
            ],
            'students': [{'id': STU_1, 'name': 'Alex'}],
            'student_submissions': [
                # Out-of-class submission (CID_OTHER_CLASS is NOT in cls-1's published_content).
                # Must NOT count as cls-1's pre-rem baseline.
                _sub('s-other-class', STU_1, CID_OTHER_CLASS, _mastery(earned=8, possible=10),
                     submitted_at='2026-04-10T10:00:00Z'),
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/remediation-effectiveness', headers=teacher_headers)
        body = resp.get_json()
        row = body['remediations'][0]['rows'][0]
        # Before should be NULL because the only submission was out-of-class.
        # Without the class-content-ids filter, before would falsely read 80%.
        assert row['before'] is None, (
            "Out-of-class submission leaked into baseline — class-scoping filter is missing"
        )
        assert row['after'] is None
        assert row['delta'] is None
