"""Tests for study guide generation and export."""

import json
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, g


def _make_app():
    """Create a minimal Flask app with planner routes.

    Patches the limiter to a no-op to avoid shared state conflicts
    when other tests have already initialized it.
    """
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.config['RATELIMIT_ENABLED'] = False  # Disable rate limiting in tests

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.planner_routes import planner_bp
    app.register_blueprint(planner_bp)

    @app.before_request
    def set_test_user():
        from flask import request as req
        teacher_id = req.headers.get("X-Test-Teacher-Id")
        if teacher_id:
            g.user_id = teacher_id

    return app


def _mock_genai_response(text):
    """Create a mock response compatible with GeminiAdapter's genai.GenerativeModel."""
    mock_resp = MagicMock()
    mock_resp.text = text
    mock_resp.candidates = [MagicMock(finish_reason=MagicMock(name="STOP"))]
    mock_resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=500)
    return mock_resp


SAMPLE_STUDY_GUIDE = json.dumps({
    "title": "Unit 3: The Constitution",
    "sections": [
        {
            "heading": "Key Concepts",
            "content": [
                "The Constitution establishes three branches of government.",
                "Separation of powers prevents any one branch from dominating."
            ]
        },
        {
            "heading": "Vocabulary",
            "terms": [
                {"term": "Federalism", "definition": "Division of power between national and state governments."},
                {"term": "Ratification", "definition": "Formal approval of the Constitution by the states."}
            ]
        },
        {
            "heading": "Review Questions",
            "questions": [
                {"question": "What are the three branches of government?", "answer": "Legislative, Executive, and Judicial."},
                {"question": "Why is separation of powers important?", "answer": "It prevents tyranny by ensuring no single branch has too much power."}
            ]
        },
        {
            "heading": "Summary",
            "content": ["The Constitution created a federal system with checks and balances to protect individual rights."]
        }
    ]
})


class TestGenerateStudyGuide:
    def test_returns_study_guide_json(self):
        """Should return structured study guide from Gemini."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.return_value = _mock_genai_response(SAMPLE_STUDY_GUIDE)
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Unit 3 Study Guide",
                    "content": "The Constitution establishes three branches...",
                    "subject": "US History",
                    "grade": "8",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            data = resp.get_json()
            assert "study_guide" in data
            assert data["study_guide"]["title"] == "Unit 3: The Constitution"
            assert len(data["study_guide"]["sections"]) == 4

    def test_returns_400_without_content(self):
        """Should reject requests without content."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/generate-study-guide', json={
                "title": "Empty Guide",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_handles_gemini_error(self):
        """Should return 500 with message on Gemini failure."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = Exception("API error")
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Broken Guide",
                    "content": "Some content",
                    "subject": "Math",
                    "grade": "7",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 500
            assert "error" in resp.get_json()

    def test_includes_lesson_plan_content(self):
        """Should incorporate lesson plan sections into the prompt."""
        app = _make_app()
        captured_prompt = []

        def capture(contents, generation_config=None, request_options=None):
            prompt_text = contents[0]["parts"][0]["text"] if contents else ""
            captured_prompt.append(prompt_text)
            return _mock_genai_response(SAMPLE_STUDY_GUIDE)

        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = capture
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Lesson Review",
                    "content": "Day 1: Introduction to fractions...",
                    "lessonPlan": {
                        "title": "Fractions Unit",
                        "overview": "Students learn to add and subtract fractions.",
                        "days": [{"day": 1, "topic": "Intro to fractions"}]
                    },
                    "subject": "Math",
                    "grade": "6",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            assert captured_prompt, "generate_content was not called"
            assert "Fractions Unit" in captured_prompt[0]

    def test_includes_custom_instructions(self):
        """Should pass custom instructions to the prompt."""
        app = _make_app()
        captured_prompt = []

        def capture(contents, generation_config=None, request_options=None):
            prompt_text = contents[0]["parts"][0]["text"] if contents else ""
            captured_prompt.append(prompt_text)
            return _mock_genai_response(SAMPLE_STUDY_GUIDE)

        with app.test_client() as client:
            with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
                 patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
                mock_model = MagicMock()
                mock_model.generate_content.side_effect = capture
                mock_genai.GenerativeModel.return_value = mock_model

                resp = client.post('/api/generate-study-guide', json={
                    "title": "Custom Guide",
                    "content": "Some content",
                    "subject": "Science",
                    "grade": "7",
                    "instructions": "Focus on lab safety procedures",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

            assert resp.status_code == 200
            assert captured_prompt, "generate_content was not called"
            assert "lab safety procedures" in captured_prompt[0]


import os
import tempfile


class TestExportStudyGuide:
    def test_exports_docx(self):
        """Should export study guide as DOCX with actual content."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        # Verify file is non-trivial (DOCX with 4 sections should be > 5KB)
        assert len(resp.data) > 5000

    def test_docx_contains_sections(self):
        """Exported DOCX should contain the study guide sections."""
        from docx import Document
        from io import BytesIO
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        doc = Document(BytesIO(resp.data))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Key Concepts" in text
        assert "Vocabulary" in text
        assert "Federalism" in text
        assert "Review Questions" in text

    def test_exports_pdf(self):
        """Should export study guide as valid PDF."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "pdf",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert resp.content_type == 'application/pdf'
        # Verify it's a real PDF (starts with %PDF)
        assert resp.data[:5] == b'%PDF-'
        assert len(resp.data) > 1000

    def test_returns_400_without_study_guide(self):
        """Should reject requests without study_guide data."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.post('/api/export-study-guide', json={
                "format": "docx",
            }, headers={"X-Test-Teacher-Id": "teacher-1"})
        assert resp.status_code == 400

    def test_defaults_to_docx(self):
        """Should default to DOCX when no format specified."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200
        assert 'wordprocessingml' in resp.content_type

    def test_export_handles_empty_sections(self):
        """Should not crash when study guide has empty sections."""
        app = _make_app()
        guide = {"title": "Empty Guide", "sections": [
            {"heading": "Empty", "content": []},
            {"heading": "No terms", "terms": []},
            {"heading": "No questions", "questions": []},
        ]}
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        assert resp.status_code == 200

    def test_non_trivial_file_size(self):
        """Exported files should have non-trivial size."""
        app = _make_app()
        guide = json.loads(SAMPLE_STUDY_GUIDE)
        with app.test_client() as client:
            with patch('backend.routes.planner_routes._get_export_dir',
                       return_value=tempfile.mkdtemp()):
                resp = client.post('/api/export-study-guide', json={
                    "study_guide": guide,
                    "format": "docx",
                }, headers={"X-Test-Teacher-Id": "teacher-1"})

        # A DOCX with real content should be several KB
        assert len(resp.data) > 4000
