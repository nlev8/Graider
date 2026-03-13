"""Integration tests for assignment builder API routes."""
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock


@pytest.fixture(autouse=True)
def patch_assignments_dir(monkeypatch, tmp_path, flask_app):
    """Redirect ASSIGNMENTS_DIR to a temp directory and disable cloud storage."""
    import backend.routes.assignment_routes as ar
    assignments_path = str(tmp_path / 'assignments')
    os.makedirs(assignments_path, exist_ok=True)
    monkeypatch.setattr(ar, 'ASSIGNMENTS_DIR', assignments_path)
    monkeypatch.setattr(ar, 'storage_load', None)
    monkeypatch.setattr(ar, 'storage_save', None)
    monkeypatch.setattr(ar, 'storage_delete', None)
    monkeypatch.setattr(ar, 'storage_list_keys', None)


def _assignments_dir(tmp_path):
    return str(tmp_path / 'assignments')


# ---------------------------------------------------------------------------
# TestSaveAssignment
# ---------------------------------------------------------------------------

class TestSaveAssignment:
    """Tests for POST /api/save-assignment-config."""

    def test_save_valid_config_returns_saved(self, client):
        """Save a valid assignment config and verify 'saved' status."""
        resp = client.post('/api/save-assignment-config', json={
            'title': 'Unit 5 Vocab',
            'customMarkers': ['Vocab:'],
            'rubricType': 'standard',
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['status'] == 'saved'

    def test_save_persists_to_file(self, client, tmp_path):
        """Saved config should create a JSON file on disk."""
        client.post('/api/save-assignment-config', json={
            'title': 'Chapter 3 Test',
            'completionOnly': False,
        })
        filepath = os.path.join(_assignments_dir(tmp_path), 'Chapter 3 Test.json')
        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            saved = json.load(f)
        assert saved['title'] == 'Chapter 3 Test'

    def test_merge_save_preserves_existing_fields(self, client, tmp_path):
        """A second save should merge, not overwrite existing fields."""
        # First save with extra fields
        client.post('/api/save-assignment-config', json={
            'title': 'Merge Test',
            'rubricType': 'cornell-notes',
            'aliases': ['mt'],
        })
        # Second save with only partial data
        client.post('/api/save-assignment-config', json={
            'title': 'Merge Test',
            'completionOnly': True,
        })
        filepath = os.path.join(_assignments_dir(tmp_path), 'Merge Test.json')
        with open(filepath, 'r') as f:
            saved = json.load(f)
        # Original field preserved
        assert saved['rubricType'] == 'cornell-notes'
        assert saved['aliases'] == ['mt']
        # New field present
        assert saved['completionOnly'] is True

    def test_title_sanitized_for_filename(self, client, tmp_path):
        """Special characters in title should be stripped from the filename."""
        client.post('/api/save-assignment-config', json={
            'title': 'Test@#$%^&*!Quiz',
        })
        # Only alphanumeric, space, dash, underscore survive
        filepath = os.path.join(_assignments_dir(tmp_path), 'TestQuiz.json')
        assert os.path.exists(filepath)


# ---------------------------------------------------------------------------
# TestLoadAssignment
# ---------------------------------------------------------------------------

class TestLoadAssignment:
    """Tests for GET /api/load-assignment."""

    def test_load_existing_config(self, client, tmp_path):
        """Loading an existing assignment returns its data."""
        config = {'title': 'Load Me', 'rubricType': 'fill-in-blank', 'points': 50}
        filepath = os.path.join(_assignments_dir(tmp_path), 'Load Me.json')
        with open(filepath, 'w') as f:
            json.dump(config, f)

        resp = client.get('/api/load-assignment?name=Load Me')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['assignment']['rubricType'] == 'fill-in-blank'
        assert data['assignment']['points'] == 50

    def test_load_nonexistent_returns_error(self, client):
        """Loading a missing assignment returns an error key."""
        resp = client.get('/api/load-assignment?name=Does Not Exist')
        data = resp.get_json()
        assert 'error' in data

    def test_load_after_save_roundtrip(self, client):
        """Data saved via the API should be loadable and match."""
        payload = {
            'title': 'Roundtrip',
            'customMarkers': ['Q1:', 'Q2:'],
            'completionOnly': False,
            'rubricType': 'standard',
        }
        client.post('/api/save-assignment-config', json=payload)
        resp = client.get('/api/load-assignment?name=Roundtrip')
        data = resp.get_json()
        assert data['assignment']['title'] == 'Roundtrip'
        assert data['assignment']['customMarkers'] == ['Q1:', 'Q2:']
        assert data['assignment']['rubricType'] == 'standard'


# ---------------------------------------------------------------------------
# TestListAssignments
# ---------------------------------------------------------------------------

class TestListAssignments:
    """Tests for GET /api/list-assignments."""

    def test_empty_directory_returns_empty_list(self, client):
        """An empty assignments directory returns an empty list."""
        resp = client.get('/api/list-assignments')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['assignments'] == []
        assert data['assignmentData'] == {}

    def test_list_includes_saved_configs(self, client):
        """Saved assignments appear in the list endpoint."""
        client.post('/api/save-assignment-config', json={'title': 'Alpha'})
        client.post('/api/save-assignment-config', json={'title': 'Beta'})

        resp = client.get('/api/list-assignments')
        data = resp.get_json()
        names = data['assignments']
        assert 'Alpha' in names
        assert 'Beta' in names

    def test_list_includes_expected_metadata(self, client):
        """Each assignment in assignmentData includes required metadata fields."""
        client.post('/api/save-assignment-config', json={
            'title': 'Meta Check',
            'completionOnly': True,
            'rubricType': 'cornell-notes',
            'aliases': ['mc'],
            'dueDate': '2026-04-01',
        })
        resp = client.get('/api/list-assignments')
        data = resp.get_json()
        meta = data['assignmentData']['Meta Check']
        assert meta['title'] == 'Meta Check'
        assert meta['completionOnly'] is True
        assert meta['rubricType'] == 'cornell-notes'
        assert meta['aliases'] == ['mc']
        assert meta['dueDate'] == '2026-04-01'
        assert 'latePenalty' in meta
        assert 'countsTowardsGrade' in meta
        assert 'importedFilename' in meta


# ---------------------------------------------------------------------------
# TestDeleteAssignment
# ---------------------------------------------------------------------------

class TestDeleteAssignment:
    """Tests for DELETE /api/delete-assignment."""

    def test_delete_existing_returns_deleted(self, client, tmp_path):
        """Deleting an existing assignment returns 'deleted' and removes file."""
        client.post('/api/save-assignment-config', json={'title': 'To Delete'})
        filepath = os.path.join(_assignments_dir(tmp_path), 'To Delete.json')
        assert os.path.exists(filepath)

        resp = client.delete('/api/delete-assignment?name=To Delete')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['status'] == 'deleted'
        assert not os.path.exists(filepath)

    def test_delete_nonexistent_returns_deleted(self, client):
        """Deleting a non-existent assignment still returns 'deleted' (idempotent)."""
        resp = client.delete('/api/delete-assignment?name=Ghost')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['status'] == 'deleted'
