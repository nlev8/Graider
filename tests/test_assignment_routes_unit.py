"""Additional unit tests for backend/routes/assignment_routes.py.

Audit MAJOR #4 sprint follow-up to PR #290. Companion to existing
tests/test_assignment_routes.py which covers basic save/load/list/
delete flows. Targets the 261 uncovered LOC (31% baseline).

Endpoints / branches covered here
---------------------------------
* save_assignment_config: storage_save path, IO failure swallow,
  corrupt-JSON fallback, outer except 500
* generate_model_answers: validation, prompt construction, AI
  happy path, AI JSONDecodeError, AI raises, dict + str marker
  variants
* list_assignments: storage_list_keys path with metadata
  population
* load_assignment: storage_load path, file-fallback corrupt JSON
* delete_assignment: storage_delete path, file-remove failure 500
* export_assignment dispatch: docx vs pdf vs unknown format,
  customMarkers→questions fallback (str + dict)
* _export_docx: happy path with paragraph-based questions
  (MC/TF + short_answer + essay), table_structured path,
  python-docx ImportError, generic exception 500, answer-key
  doc creation when MC questions present
* _export_pdf: happy path multi-page (questions force showPage),
  reportlab ImportError, MC option rendering with bubbles
* download_document / download_worksheet / download_csv /
  download_export: invalid filename, file-not-found 404, happy
  send_from_directory

Strategy
--------
Reuses `client` fixture from conftest_routes.py (Flask app with all
blueprints registered, g.user_id pre-populated). storage_*
abstractions monkeypatched per test, ASSIGNMENTS_DIR redirected to
tmp_path. python-docx / reportlab / OpenAIAdapter mocked so no real
files are written outside tmp_path and no real LLM is called.
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock  # noqa: F401,E501


@pytest.fixture(autouse=True)
def patch_dirs(monkeypatch, tmp_path, flask_app):  # noqa: F811
    """Redirect every output directory used by assignment_routes to
    tmp_path so the tests never touch ~/Downloads or ~/.graider_*."""
    import backend.routes.assignment_routes as ar

    assignments = tmp_path / "assignments"
    assignments.mkdir(exist_ok=True)
    monkeypatch.setattr(ar, "ASSIGNMENTS_DIR", str(assignments))

    # Default to filesystem-fallback paths (storage_*=None). Individual
    # tests opt back into storage by explicitly patching.
    monkeypatch.setattr(ar, "storage_load", None)
    monkeypatch.setattr(ar, "storage_save", None)
    monkeypatch.setattr(ar, "storage_delete", None)
    monkeypatch.setattr(ar, "storage_list_keys", None)

    # Output dirs for export/download endpoints
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "Documents").mkdir()
    (downloads / "Worksheets").mkdir()
    (downloads / "Exports").mkdir()
    (downloads / "Assignments").mkdir()
    (tmp_path / ".graider_exports").mkdir()
    (tmp_path / ".graider_exports" / "focus").mkdir()

    # The export/download endpoints use `os.path.expanduser` for their
    # output paths. Patch expanduser on the route module so each call
    # resolves into our tmp_path subtree. (Other module-level expanduser
    # calls happen at import time, before the fixture runs.)
    real_expanduser = os.path.expanduser

    def fake_expanduser(p):
        if p.startswith("~/Downloads/Graider"):
            return str(downloads / p[len("~/Downloads/Graider/"):])
        if p.startswith("~/.graider_exports"):
            return str(tmp_path / ".graider_exports" / p[len("~/.graider_exports/"):])
        if p.startswith("~/.graider_assignments"):
            return str(assignments)
        return real_expanduser(p)

    monkeypatch.setattr(
        "backend.routes.assignment_routes.os.path.expanduser",
        fake_expanduser,
    )
    # graider_export_dir() reads GRAIDER_EXPORT_DIR at call time; override
    # per-test so exports land in this fixture's downloads dir, not the
    # session-level isolation dir set by _redirect_graider_export_dir.
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(downloads))

    return {
        "ar": ar,
        "assignments": assignments,
        "downloads": downloads,
        "exports_focus": tmp_path / ".graider_exports" / "focus",
    }


# ──────────────────────────────────────────────────────────────────
# /api/save-assignment-config
# ──────────────────────────────────────────────────────────────────


class TestSaveAssignmentConfig:
    def test_storage_save_path_called_when_available(
        self, client, patch_dirs,
    ):
        save_mock = MagicMock()
        load_mock = MagicMock(return_value={"old": "data"})
        with patch.multiple(
            patch_dirs["ar"],
            storage_save=save_mock,
            storage_load=load_mock,
        ):
            resp = client.post(
                "/api/save-assignment-config",
                json={"title": "T", "newField": "v"},
            )
        assert resp.status_code == 200
        save_mock.assert_called_once()
        # Merged: existing 'old' preserved, new 'newField' set
        merged = save_mock.call_args.args[1]
        assert merged["old"] == "data"
        assert merged["newField"] == "v"

    def test_corrupt_json_in_existing_swallowed(
        self, client, patch_dirs,
    ):
        # Storage None + corrupt file → except branch (66-68) + treat
        # existing as {} → save still succeeds.
        bad = patch_dirs["assignments"] / "T.json"
        bad.write_text("{ corrupt")
        resp = client.post(
            "/api/save-assignment-config",
            json={"title": "T", "newField": "v"},
        )
        assert resp.status_code == 200
        # File overwritten with valid merged JSON (just the new data)
        result = json.loads(bad.read_text())
        assert result["title"] == "T"
        assert result["newField"] == "v"

    def test_outer_io_failure_returns_500(self, client, patch_dirs):
        # Force the JSON write to raise. Selective open patch so
        # Flask internals (templates/etc) pass through.
        real_open = open

        def selective(path, *args, **kwargs):
            if str(path).endswith("T.json"):
                raise IOError("disk gone")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=selective):
            resp = client.post(
                "/api/save-assignment-config",
                json={"title": "T"},
            )
        assert resp.status_code == 500
        assert "internal error" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# /api/generate-model-answers
# ──────────────────────────────────────────────────────────────────


class TestGenerateModelAnswers:
    def test_no_markers_returns_400(self, client):
        resp = client.post(
            "/api/generate-model-answers",
            json={"customMarkers": [], "documentText": "x"},
        )
        assert resp.status_code == 400
        assert "No sections" in resp.get_json()["error"]

    def test_no_doc_text_returns_400(self, client):
        resp = client.post(
            "/api/generate-model-answers",
            json={
                "customMarkers": [{"start": "Q1", "type": "written", "points": 5}],
                "documentText": "",
            },
        )
        assert resp.status_code == 400
        assert "Import" in resp.get_json()["error"]

    def test_happy_path_returns_model_answers(self, client):
        # Mock OpenAIAdapter.chat() → returns valid JSON
        fake_response = MagicMock()
        text_part = MagicMock()
        text_part.text = json.dumps({
            "model_answers": [
                {"section": "Q1", "answer": "Mountains form when..."},
            ],
        })
        fake_response.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_response

        with patch(
            "backend.api_keys.get_api_key", return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.OpenAIAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/generate-model-answers",
                json={
                    "customMarkers": [
                        {"start": "Q1", "type": "written", "points": 10},
                        "string-marker-Q2",  # str variant
                    ],
                    "documentText": "Plate tectonics intro",
                    "title": "Geo Quiz",
                    "grade_level": "9",
                    "subject": "Science",
                    "globalAINotes": "be encouraging",
                },
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["model_answers"][0]["answer"].startswith("Mountains")

    def test_ai_returns_invalid_json_returns_500(self, client):
        fake_response = MagicMock()
        text_part = MagicMock(); text_part.text = "not json"
        fake_response.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_response
        with patch(
            "backend.api_keys.get_api_key", return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.OpenAIAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/generate-model-answers",
                json={
                    "customMarkers": [{"start": "Q", "type": "written"}],
                    "documentText": "x",
                },
            )
        assert resp.status_code == 500
        assert "Failed to parse" in resp.get_json()["error"]

    def test_ai_adapter_raises_returns_500(self, client):
        fake_adapter = MagicMock()
        fake_adapter.chat.side_effect = RuntimeError("network down")
        with patch(
            "backend.api_keys.get_api_key", return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.OpenAIAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/generate-model-answers",
                json={
                    "customMarkers": [{"start": "Q", "type": "written"}],
                    "documentText": "x",
                },
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/list-assignments — storage path
# ──────────────────────────────────────────────────────────────────


class TestListAssignmentsFileFallback:
    def test_no_assignments_dir_returns_empty(self, client, patch_dirs):
        # Delete ASSIGNMENTS_DIR after fixture-create → triggers line 197
        import shutil
        shutil.rmtree(patch_dirs["assignments"])
        resp = client.get("/api/list-assignments")
        body = resp.get_json()
        assert body["assignments"] == []
        assert body["assignmentData"] == {}

    def test_corrupt_json_filed_in_fallback_recovered(
        self, client, patch_dirs,
    ):
        # Fallback file walk hits a corrupt JSON file → except branch
        # at lines 221-223 falls back to default metadata stub.
        good = patch_dirs["assignments"] / "good.json"
        good.write_text(json.dumps({
            "title": "Good", "aliases": ["g"], "rubricType": "standard",
        }))
        bad = patch_dirs["assignments"] / "bad.json"
        bad.write_text("{ corrupt")
        resp = client.get("/api/list-assignments")
        body = resp.get_json()
        # Both files listed (assignments has both names)
        assert "good" in body["assignments"]
        assert "bad" in body["assignments"]
        # Good has its real metadata
        assert body["assignmentData"]["good"]["title"] == "Good"
        # Bad falls back to the default stub (title=name, empty aliases)
        bad_meta = body["assignmentData"]["bad"]
        assert bad_meta["title"] == "bad"
        assert bad_meta["aliases"] == []
        assert bad_meta["rubricType"] == "standard"


class TestListAssignmentsStorage:
    def test_storage_path_returns_metadata(self, client, patch_dirs):
        keys = ["assignment:Quiz1", "assignment:Test2"]
        loaded = {
            "assignment:Quiz1": {
                "title": "Quiz One",
                "aliases": ["q1"],
                "completionOnly": True,
                "rubricType": "completion",
                "countsTowardsGrade": False,
                "importedDoc": {"filename": "quiz1.docx"},
                "dueDate": "2026-05-15",
                "latePenalty": {"per_day": 10},
            },
            "assignment:Test2": {
                "title": "Test Two",
                # Test the rubricType=None → fallback to "standard"
                "rubricType": None,
            },
        }
        with patch.multiple(
            patch_dirs["ar"],
            storage_list_keys=MagicMock(return_value=keys),
            storage_load=MagicMock(side_effect=lambda k, t: loaded.get(k)),
        ):
            resp = client.get("/api/list-assignments")
        body = resp.get_json()
        # Sort by title (alphabetical)
        assert body["assignments"] == ["Quiz1", "Test2"]
        # Quiz1 metadata fully populated
        q1 = body["assignmentData"]["Quiz1"]
        assert q1["title"] == "Quiz One"
        assert q1["aliases"] == ["q1"]
        assert q1["completionOnly"] is True
        assert q1["rubricType"] == "completion"
        assert q1["countsTowardsGrade"] is False
        assert q1["importedFilename"] == "quiz1.docx"
        assert q1["dueDate"] == "2026-05-15"
        # Test2 falls back to "standard" rubricType
        assert body["assignmentData"]["Test2"]["rubricType"] == "standard"


# ──────────────────────────────────────────────────────────────────
# /api/load-assignment
# ──────────────────────────────────────────────────────────────────


class TestLoadAssignment:
    def test_invalid_name_returns_400(self, client):
        # Name with disallowed characters
        resp = client.get("/api/load-assignment?name=../../../etc")
        assert resp.status_code == 400

    def test_empty_name_returns_400(self, client):
        resp = client.get("/api/load-assignment?name=")
        assert resp.status_code == 400

    def test_storage_load_path(self, client, patch_dirs):
        load_mock = MagicMock(return_value={"title": "T"})
        with patch.multiple(
            patch_dirs["ar"], storage_load=load_mock,
        ):
            resp = client.get("/api/load-assignment?name=MyQuiz")
        assert resp.status_code == 200
        assert resp.get_json()["assignment"]["title"] == "T"
        load_mock.assert_called_once_with("assignment:MyQuiz", "test-teacher")

    def test_storage_miss_falls_to_file_corrupt_json(
        self, client, patch_dirs,
    ):
        # storage_load returns None → file fallback → file is corrupt
        # → except branch (254-256) → 500
        f = patch_dirs["assignments"] / "Bad.json"
        f.write_text("{ corrupt")
        with patch.multiple(
            patch_dirs["ar"],
            storage_load=MagicMock(return_value=None),
        ):
            resp = client.get("/api/load-assignment?name=Bad")
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/delete-assignment
# ──────────────────────────────────────────────────────────────────


class TestDeleteAssignment:
    def test_invalid_name_returns_400(self, client):
        resp = client.delete("/api/delete-assignment?name=$$$")
        assert resp.status_code == 400

    def test_storage_delete_called(self, client, patch_dirs):
        delete_mock = MagicMock()
        with patch.multiple(
            patch_dirs["ar"], storage_delete=delete_mock,
        ):
            resp = client.delete("/api/delete-assignment?name=ToGo")
        assert resp.status_code == 200
        delete_mock.assert_called_once_with(
            "assignment:ToGo", "test-teacher",
        )

    def test_file_remove_failure_returns_500(self, client, patch_dirs):
        # Pre-create file then patch os.remove to raise
        f = patch_dirs["assignments"] / "ToGo.json"
        f.write_text("{}")
        with patch("os.remove", side_effect=IOError("perm denied")):
            resp = client.delete("/api/delete-assignment?name=ToGo")
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/export-assignment — dispatch + helpers
# ──────────────────────────────────────────────────────────────────


class TestExportDispatch:
    def test_unknown_format_returns_error(self, client):
        resp = client.post(
            "/api/export-assignment",
            json={"assignment": {"title": "T"}, "format": "txt"},
        )
        assert "Unknown format" in resp.get_json()["error"]

    def test_custom_markers_str_converted_to_questions(
        self, client, patch_dirs,
    ):
        # Provide ONLY customMarkers (no questions); production code
        # converts each marker to a question dict. Inspect via mock
        # that intercepts _export_docx to capture the questions arg.
        captured = {}

        def fake_export(*args, **kwargs):
            captured["title"] = args[0]
            captured["questions"] = args[2]
            return MagicMock(status_code=200, get_json=lambda: {})

        with patch(
            "backend.routes.assignment_routes._export_docx",
            side_effect=fake_export,
        ):
            client.post(
                "/api/export-assignment",
                json={
                    "assignment": {
                        "title": "From Markers",
                        "customMarkers": [
                            "string-marker",
                            {"start": "Q1", "points": 5, "type": "essay"},
                        ],
                    },
                    "format": "docx",
                },
            )
        assert captured["title"] == "From Markers"
        # Two questions built from the customMarkers
        assert len(captured["questions"]) == 2
        assert captured["questions"][0]["marker"] == "string-marker"
        assert captured["questions"][1]["marker"] == "Q1"
        assert captured["questions"][1]["points"] == 5


class TestExportDocx:
    def _payload(self, **overrides):
        base = {
            "assignment": {
                "title": "Sample",
                "instructions": "Read carefully.",
                "questions": [
                    {
                        "marker": "Q1:", "prompt": "Define mitosis",
                        "type": "short_answer", "points": 10,
                    },
                    {
                        "marker": "Q2:", "prompt": "True or false?",
                        "type": "true_false", "points": 5,
                        "options": ["True", "False"],
                        "answer": "True",
                    },
                    {
                        "marker": "Q3:", "prompt": "Pick A or B",
                        "type": "multiple_choice", "points": 5,
                        "options": ["A", "B"], "answer": "A",
                    },
                    {
                        "marker": "Q4:", "prompt": "Long-form response",
                        "type": "essay", "points": 20,
                    },
                ],
            },
            "format": "docx",
        }
        base["assignment"].update(overrides)
        return base

    def test_happy_path_writes_docx_and_answer_key(
        self, client, patch_dirs,
    ):
        # Mock subprocess.run so the macOS `open` call doesn't actually
        # launch Finder during tests.
        with patch("subprocess.run"):
            resp = client.post(
                "/api/export-assignment", json=self._payload(),
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "exported"
        # Main doc + answer key both written
        assignments = patch_dirs["downloads"] / "Assignments"
        assert (assignments / "Sample.docx").exists()
        # Answer key created when MC/TF questions present
        assert (assignments / "Sample_Answer_Key.docx").exists()

    def test_table_structured_path(self, client, patch_dirs):
        with patch("subprocess.run"):
            resp = client.post(
                "/api/export-assignment",
                json=self._payload(tableStructured=True),
            )
        assert resp.status_code == 200
        # Main doc written; no answer-key for table-structured path
        assignments = patch_dirs["downloads"] / "Assignments"
        assert (assignments / "Sample.docx").exists()

    def test_python_docx_missing_returns_error(self, client):
        # Force ImportError on `from docx import Document` by setting
        # sys.modules["docx"] = None.
        with patch.dict("sys.modules", {"docx": None}):
            resp = client.post(
                "/api/export-assignment", json=self._payload(),
            )
        body = resp.get_json()
        assert "python-docx" in body["error"]

    def test_generic_failure_returns_500(self, client, patch_dirs):
        # Force docx.Document() instantiation to raise
        fake_docx = MagicMock()
        fake_docx.Document.side_effect = RuntimeError("disk fail")
        with patch.dict("sys.modules", {
            "docx": fake_docx,
            "docx.shared": MagicMock(),
            "docx.enum.text": MagicMock(),
        }), patch("subprocess.run"):
            resp = client.post(
                "/api/export-assignment", json=self._payload(),
            )
        assert resp.status_code == 500


class TestExportPdf:
    def _payload(self, **overrides):
        base = {
            "assignment": {
                "title": "PDFTest",
                "instructions": "Read me.",
                "questions": [
                    # Many questions to trigger c.showPage() pagination
                    *[
                        {
                            "marker": f"Q{i}:",
                            "prompt": "x" * 80,
                            "type": "short_answer",
                            "points": 5,
                        }
                        for i in range(25)
                    ],
                    # MC question with MANY options to force page break
                    # WITHIN the option-rendering loop (lines 506-508).
                    # Pre-loop pagination already pushes y down; the
                    # 30+ options ensure y < 1.5*inch is hit mid-list.
                    {
                        "marker": "QMC:", "prompt": "Pick",
                        "type": "multiple_choice", "points": 5,
                        "options": [f"Option {i}" for i in range(40)],
                    },
                    {
                        "marker": "QEssay:", "prompt": "Long",
                        "type": "essay", "points": 20,
                    },
                ],
            },
            "format": "pdf",
        }
        base["assignment"].update(overrides)
        return base

    def test_happy_path_writes_pdf(self, client, patch_dirs):
        with patch("subprocess.run"):
            resp = client.post(
                "/api/export-assignment", json=self._payload(),
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "exported"
        # PDF written to expected dir
        pdf_path = (
            patch_dirs["downloads"] / "Assignments" / "PDFTest.pdf"
        )
        assert pdf_path.exists()

    def test_reportlab_missing_returns_error(self, client):
        # Force ImportError on reportlab. Production imports
        # `from reportlab.lib.pagesizes import letter` etc. INSIDE
        # _export_pdf, so blocking the top-level reportlab module
        # surfaces the ImportError branch.
        with patch.dict("sys.modules", {
            "reportlab": None,
            "reportlab.lib.pagesizes": None,
        }):
            resp = client.post(
                "/api/export-assignment", json=self._payload(),
            )
        body = resp.get_json()
        assert "reportlab" in body["error"]

    def test_generic_failure_returns_500(self, client):
        # Production catches generic exceptions inside _export_pdf and
        # returns 500. `from reportlab.pdfgen import canvas` resolves
        # the `canvas` name via attribute lookup on the parent
        # reportlab.pdfgen module — patching sys.modules alone is not
        # enough because Python imports the submodule and binds it
        # locally on the parent. Patch Canvas directly on the real
        # canvas submodule instead.
        with patch(
            "reportlab.pdfgen.canvas.Canvas",
            side_effect=RuntimeError("pdf error"),
        ):
            resp = client.post(
                "/api/export-assignment",
                json={
                    "assignment": {"title": "X", "questions": [
                        {"marker": "M", "prompt": "p", "points": 1,
                         "type": "short_answer"},
                    ]},
                    "format": "pdf",
                },
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# Download endpoints (4)
# ──────────────────────────────────────────────────────────────────


class TestDownloads:
    @pytest.mark.parametrize("endpoint", [
        "/api/download-document",
        "/api/download-worksheet",
        "/api/download-csv",
        "/api/download-export",
    ])
    def test_invalid_filename_returns_400(self, client, endpoint):
        # secure_filename(".") returns "" → triggers the empty-name
        # 400 branch (lines 551, 565, 579, 593). A bare "." survives
        # Flask routing and reaches the handler.
        resp = client.get(f"{endpoint}/.")
        assert resp.status_code == 400
        assert "Invalid filename" in resp.get_json()["error"]

    @pytest.mark.parametrize("endpoint,subdir,key", [
        ("/api/download-document", "Documents", "Document"),
        ("/api/download-worksheet", "Worksheets", "Worksheet"),
        ("/api/download-csv", "Exports", "CSV"),
    ])
    def test_file_not_found_returns_404(
        self, client, patch_dirs, endpoint, subdir, key,
    ):
        resp = client.get(f"{endpoint}/missing.txt")
        assert resp.status_code == 404
        body = resp.get_json()
        assert key in body["error"]

    @pytest.mark.parametrize("endpoint,subdir", [
        ("/api/download-document", "Documents"),
        ("/api/download-worksheet", "Worksheets"),
        ("/api/download-csv", "Exports"),
    ])
    def test_happy_path_serves_file(
        self, client, patch_dirs, endpoint, subdir,
    ):
        d = patch_dirs["downloads"] / subdir
        f = d / "real.txt"
        f.write_text("payload")
        resp = client.get(f"{endpoint}/real.txt")
        assert resp.status_code == 200
        assert resp.data == b"payload"

    def test_download_export_not_found(self, client):
        resp = client.get("/api/download-export/missing.csv")
        assert resp.status_code == 404
        assert "Export" in resp.get_json()["error"]

    def test_download_export_happy_path(self, client, patch_dirs):
        f = patch_dirs["exports_focus"] / "report.csv"
        f.write_text("a,b,c")
        resp = client.get("/api/download-export/report.csv")
        assert resp.status_code == 200
        assert resp.data == b"a,b,c"
