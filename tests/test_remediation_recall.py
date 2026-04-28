"""Tests for the Phase 4.2 #5 Remediation Recall endpoint.

Spec: docs/superpowers/specs/2026-04-28-phase4.2-recall-ux-design.md

Reuses the filter-aware `_make_chain` mock from Phase 3b/4 tests, adapted
to track `.update()` call counts via a per-table cached chain (so we can
assert "no second write" on the idempotent path).
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call

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
    """Filter-aware Supabase mock — applies .eq() / .in_() / .neq() at .execute()
    time. Same shape as test_remediation_effectiveness.py.
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

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
        filters.clear()
        return MagicMock(data=result)
    chain.execute.side_effect = _execute
    return chain


def _per_table_sb(table_map):
    """Returns a supabase mock where each table has a SINGLE cached chain
    (reused across calls to the same name). Lets tests assert call counts
    on a specific table's .update() chain. Different from _multi_table_sb
    in test_remediation_effectiveness.py which builds a fresh chain per call.
    """
    chains = {}
    mock_sb = MagicMock()

    def table_side_effect(name):
        if name not in chains:
            chains[name] = _make_chain(table_map.get(name) or [])
        return chains[name]

    mock_sb.table.side_effect = table_side_effect
    mock_sb._chains = chains  # exposed for assertions
    return mock_sb


# ============ Test data ============

CLS_OWNED = [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}]
CLS_OTHER_OWNER = [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'OTHER-TEACHER'}]

STU_1 = '11111111-aaaa-aaaa-aaaa-111111111111'
STU_2 = '22222222-bbbb-bbbb-bbbb-222222222222'

CID_REM_1 = '11111111-1111-1111-1111-111111111111'
CID_REM_INACTIVE = '22222222-2222-2222-2222-222222222222'
CID_ASSESSMENT_NON_REM = '33333333-3333-3333-3333-333333333333'
CID_REM_OTHER_CLASS = '44444444-4444-4444-4444-444444444444'

STD_AR_1 = 'MA.6.AR.1.2'


def _rem_row(cid, target_ids, is_active=True, class_id='cls-1'):
    """Build a remediation published_content row."""
    return {
        'id': cid,
        'class_id': class_id,
        'is_active': is_active,
        'target_student_ids': target_ids,
    }


def _non_rem_row(cid, is_active=True, class_id='cls-1'):
    """Build a NON-remediation row (target_student_ids is None)."""
    return {
        'id': cid,
        'class_id': class_id,
        'is_active': is_active,
        'target_student_ids': None,
    }


# ============ Auth tests ============

class TestRecallAuth:
    """401 unauth, 403 wrong-teacher class."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_1}/recall'
        )
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _per_table_sb({'classes': CLS_OTHER_OWNER})
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_1}/recall',
            headers=teacher_headers,
        )
        assert resp.status_code == 403


# ============ Happy-path tests ============

class TestRecallHappyPath:
    """Active remediation gets recalled; response shape correct; update call shape correct."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_flips_is_active_true_to_false(self, mock_sb_fn, client, teacher_headers):
        sb = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [_rem_row(CID_REM_1, [STU_1], is_active=True)],
        })
        mock_sb_fn.return_value = sb
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_1}/recall',
            headers=teacher_headers,
        )
        assert resp.status_code == 200

        # Verify .update({'is_active': False}) was called exactly once on
        # published_content with the correct .eq() filters.
        pc_chain = sb._chains['published_content']
        assert pc_chain.update.call_count == 1
        assert pc_chain.update.call_args == call({'is_active': False})
        # The filters applied to the update call: id=rem_id AND class_id=class_id.
        eq_calls = [c for c in pc_chain.eq.call_args_list]
        assert call('id', CID_REM_1) in eq_calls
        assert call('class_id', 'cls-1') in eq_calls

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_response_shape_recalled_true(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [_rem_row(CID_REM_1, [STU_1], is_active=True)],
        })
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_1}/recall',
            headers=teacher_headers,
        )
        body = resp.get_json()
        assert body == {
            'recalled': True,
            'already_recalled': False,
            'rem_id': CID_REM_1,
        }

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_rem_id_echoed_back(self, mock_sb_fn, client, teacher_headers):
        """Rem_id from URL is echoed in response body — frontend uses this
        to mark the correct card as recalled in optimistic UI."""
        mock_sb_fn.return_value = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [_rem_row(CID_REM_1, [STU_1], is_active=True)],
        })
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_1}/recall',
            headers=teacher_headers,
        )
        assert resp.get_json()['rem_id'] == CID_REM_1


# ============ Edge cases ============

class TestRecallEdgeCases:
    """Non-remediation 404, wrong-class 404, idempotent already-recalled, post-recall visibility."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_non_remediation_content_returns_404(self, mock_sb_fn, client, teacher_headers):
        """target_student_ids IS NULL — endpoint refuses to act on non-remediation
        published_content. Identical 404 message used to avoid existence-leak."""
        mock_sb_fn.return_value = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [_non_rem_row(CID_ASSESSMENT_NON_REM)],
        })
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_ASSESSMENT_NON_REM}/recall',
            headers=teacher_headers,
        )
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_remediation_in_different_class_returns_404(self, mock_sb_fn, client, teacher_headers):
        """rem_id exists in another class. The .eq('class_id', class_id) filter
        in the lookup misses — 404."""
        mock_sb_fn.return_value = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [
                _rem_row(CID_REM_OTHER_CLASS, [STU_1], class_id='cls-OTHER'),
            ],
        })
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_OTHER_CLASS}/recall',
            headers=teacher_headers,
        )
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_already_recalled_idempotent_no_second_write(self, mock_sb_fn, client, teacher_headers):
        """Recalling an already-inactive remediation returns 200 idempotent
        with already_recalled=True, AND does NOT call .update() a second time."""
        sb = _per_table_sb({
            'classes': CLS_OWNED,
            'published_content': [_rem_row(CID_REM_INACTIVE, [STU_1], is_active=False)],
        })
        mock_sb_fn.return_value = sb
        resp = client.post(
            f'/api/teacher/class/cls-1/remediation/{CID_REM_INACTIVE}/recall',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == {
            'recalled': True,
            'already_recalled': True,
            'rem_id': CID_REM_INACTIVE,
        }
        # CRITICAL: must NOT have called update on published_content.
        pc_chain = sb._chains['published_content']
        assert pc_chain.update.call_count == 0, (
            "Idempotent path must not write — already-recalled state is unchanged"
        )

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_recalled_remediation_invisible_to_targeted_student(self, mock_sb_fn, client, teacher_headers):
        """After recall, _content_visible_to_student returns False for a targeted
        student. End-to-end check that the visibility helper's is_active gate
        does what the recall endpoint expects.
        """
        # Simulate post-recall state directly: row has is_active=False.
        from backend.routes.student_account_routes import _content_visible_to_student

        mock_db = MagicMock()
        mock_db.table.return_value = _make_chain([
            _rem_row(CID_REM_1, [STU_1], is_active=False),
        ])
        # Helper requires class_id arg; row has class_id='cls-1'.
        visible = _content_visible_to_student(mock_db, CID_REM_1, STU_1, 'cls-1')
        assert visible is False, (
            "Recalled remediation (is_active=False) must be invisible to "
            "targeted students — visibility helper gates on is_active"
        )
