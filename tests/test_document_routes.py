"""Integration tests for document API routes."""
import io
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock


class TestParseDocument:
    """Tests for POST /api/parse-document."""

    def test_no_file_uploaded_returns_400(self, client):
        """Missing file in request returns 400 with error message."""
        response = client.post('/api/parse-document', data={}, content_type='multipart/form-data')
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "No file uploaded" in data["error"]

    def test_upload_txt_file_returns_200(self, client):
        """Uploading a .txt file returns 200 with html and text fields."""
        file_data = {'file': (io.BytesIO(b'Hello World'), 'test.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert "html" in data
        assert "text" in data

    def test_unsupported_file_type_returns_400(self, client):
        """Uploading an unsupported file type (.exe) returns 400."""
        file_data = {'file': (io.BytesIO(b'\x00\x01\x02'), 'malware.exe')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Unsupported file type" in data["error"]

    def test_error_response_no_traceback(self, client):
        """Error responses should not leak traceback information."""
        file_data = {'file': (io.BytesIO(b'\x00\x01\x02'), 'malware.exe')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        data = response.get_json()
        assert "Traceback" not in data.get("error", "")
        assert "File \"" not in data.get("error", "")

    def test_response_has_filename_field(self, client):
        """Response includes filename matching the uploaded file."""
        file_data = {'file': (io.BytesIO(b'content here'), 'my_notes.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert data["filename"] == "my_notes.txt"

    def test_txt_content_preserved_in_text_field(self, client):
        """Plain text content is preserved exactly in the text field."""
        original_text = "Line one\nLine two\nLine three"
        file_data = {'file': (io.BytesIO(original_text.encode('utf-8')), 'notes.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert data["text"] == original_text

    def test_empty_filename_still_processes(self, client):
        """A file with an empty-ish name that ends with .txt still processes."""
        file_data = {'file': (io.BytesIO(b'data'), '.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert "text" in data

    def test_html_content_wrapped_in_pre_tag_for_txt(self, client):
        """TXT files have their HTML content wrapped in a <pre> tag."""
        file_data = {'file': (io.BytesIO(b'Some text content'), 'readme.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert "<pre" in data["html"]
        assert "Some text content" in data["html"]

    def test_response_content_type_is_json(self, client):
        """Response Content-Type is application/json."""
        file_data = {'file': (io.BytesIO(b'hello'), 'test.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.content_type == "application/json"

    def test_large_text_file_returns_valid_json(self, client):
        """A large text file still returns a valid JSON response."""
        large_content = ("A" * 1000 + "\n") * 500  # ~500KB
        file_data = {'file': (io.BytesIO(large_content.encode('utf-8')), 'large.txt')}
        response = client.post('/api/parse-document', data=file_data, content_type='multipart/form-data')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert "text" in data
        assert "html" in data


class TestServeFile:
    """Tests for GET /api/serve-file."""

    def test_serve_existing_file(self, client, tmp_path):
        """Serving an existing file returns 200."""
        test_file = tmp_path / "testfile.txt"
        test_file.write_text("hello world")
        response = client.get(f'/api/serve-file?path={str(test_file)}')
        assert response.status_code == 200

    def test_non_existent_file_returns_404(self, client):
        """Requesting a non-existent file returns 404."""
        response = client.get('/api/serve-file?path=/tmp/does_not_exist_abc123.txt')
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_no_path_parameter_returns_404(self, client):
        """Missing path parameter returns 404."""
        response = client.get('/api/serve-file')
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_empty_path_parameter_returns_404(self, client):
        """Empty path parameter returns 404."""
        response = client.get('/api/serve-file?path=')
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_file_content_matches(self, client, tmp_path):
        """Served file content matches what was written."""
        test_file = tmp_path / "content_check.txt"
        test_file.write_bytes(b"exact content to verify")
        response = client.get(f'/api/serve-file?path={str(test_file)}')
        assert response.status_code == 200
        assert response.data == b"exact content to verify"
