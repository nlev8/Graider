"""
Unit tests for backend/services/assistant_tools_automation.py.

Audit MAJOR #4 sprint follow-up to PR #261. Targets 70 uncovered LOC
(17% baseline) — small + safe target with storage + filesystem fallback
patterns proven in PRs #254 and #261.

Strategy:
- HOME redirect from `isolated_dirs` fixture for filesystem fallback.
- Patch `storage_load`/`storage_save` to None or specific values to
  exercise both branches.
- list_automations_tool: empty storage, populated storage, empty file
  fallback, populated file fallback, corrupt file fallback.
- create_automation_tool: storage path, file fallback, slug derivation,
  step ID + params defaults, replace-existing semantics.
- run_automation_tool: storage match, storage no-match, file match,
  file no-match.
- TestTeacherIdRequired: contract pin for all 3 tools.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest


TID = "teacher-alice"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME + AUTOMATIONS_DIR to tmp_path."""
    import backend.services.assistant_tools_automation as ata

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(ata, "AUTOMATIONS_DIR",
                        str(tmp_path / ".graider_data" / "automations"))
    return tmp_path, ata


# ──────────────────────────────────────────────────────────────────
# list_automations_tool
# ──────────────────────────────────────────────────────────────────


class TestListAutomations:
    def test_storage_empty_list_returns_friendly_message(self, isolated_dirs):
        _, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=[]) as m:
            result = ata.list_automations_tool(teacher_id=TID)
        assert "message" in result
        assert "No automations" in result["message"]
        m.assert_called_once_with("automations", TID)

    def test_storage_populated_list_returns_summaries(self, isolated_dirs):
        _, ata = isolated_dirs
        workflows = [
            {"id": "wf1", "name": "Login + Scrape", "description": "scrape grades",
             "steps": [{"type": "login"}, {"type": "navigate"}, {"type": "extract_text"}]},
            {"id": "wf2", "name": "Daily Roster", "description": "import roster",
             "steps": [{"type": "login"}, {"type": "download"}]},
        ]
        with patch.object(ata, "storage_load", return_value=workflows):
            result = ata.list_automations_tool(teacher_id=TID)
        assert result["count"] == 2
        items = result["automations"]
        assert items[0]["name"] == "Login + Scrape"
        assert items[0]["step_count"] == 3
        assert items[1]["step_count"] == 2

    def test_storage_dict_form_with_workflows_key(self, isolated_dirs):
        """Some legacy storage shapes wrap the list in a dict."""
        _, ata = isolated_dirs
        wrapped = {"workflows": [
            {"id": "x", "name": "X", "description": "", "steps": []}
        ]}
        with patch.object(ata, "storage_load", return_value=wrapped):
            result = ata.list_automations_tool(teacher_id=TID)
        assert result["count"] == 1

    def test_file_fallback_empty(self, isolated_dirs):
        tmp, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.list_automations_tool(teacher_id=TID)
        assert "message" in result
        assert "No automations" in result["message"]

    def test_file_fallback_populated(self, isolated_dirs):
        tmp, ata = isolated_dirs
        os.makedirs(ata.AUTOMATIONS_DIR, exist_ok=True)
        with open(os.path.join(ata.AUTOMATIONS_DIR, "wf1.json"), 'w') as f:
            json.dump({
                "id": "wf1", "name": "Test Workflow", "description": "",
                "steps": [{"type": "login"}, {"type": "click"}],
            }, f)

        with patch.object(ata, "storage_load", return_value=None):
            result = ata.list_automations_tool(teacher_id=TID)
        assert result["count"] == 1
        assert result["automations"][0]["name"] == "Test Workflow"
        assert result["automations"][0]["step_count"] == 2

    def test_file_fallback_skips_non_json(self, isolated_dirs):
        tmp, ata = isolated_dirs
        os.makedirs(ata.AUTOMATIONS_DIR, exist_ok=True)
        with open(os.path.join(ata.AUTOMATIONS_DIR, "ignore.txt"), 'w') as f:
            f.write("not a workflow")
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.list_automations_tool(teacher_id=TID)
        assert "message" in result  # treated as empty

    def test_file_fallback_corrupt_file_silently_skipped(self, isolated_dirs):
        tmp, ata = isolated_dirs
        os.makedirs(ata.AUTOMATIONS_DIR, exist_ok=True)
        with open(os.path.join(ata.AUTOMATIONS_DIR, "broken.json"), 'w') as f:
            f.write("garbage{")
        # And a good one
        with open(os.path.join(ata.AUTOMATIONS_DIR, "good.json"), 'w') as f:
            json.dump({"id": "g", "name": "Good", "description": "",
                       "steps": []}, f)
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.list_automations_tool(teacher_id=TID)
        # Good workflow survived the silent-skip on broken
        assert result["count"] == 1
        assert result["automations"][0]["name"] == "Good"


# ──────────────────────────────────────────────────────────────────
# create_automation_tool
# ──────────────────────────────────────────────────────────────────


class TestCreateAutomation:
    def test_storage_path_writes_workflow(self, isolated_dirs):
        _, ata = isolated_dirs
        steps = [
            {"type": "login", "label": "Login"},
            {"type": "navigate", "label": "Go to grades"},
        ]
        with patch.object(ata, "storage_load", return_value=[]), \
             patch.object(ata, "storage_save") as mock_save:
            result = ata.create_automation_tool(
                "My Auto Login", steps, description="test", teacher_id=TID,
            )
        assert result["success"] is True
        assert result["id"] == "my-auto-login"
        assert result["step_count"] == 2
        # storage_save called with the new workflows list
        mock_save.assert_called_once()
        call_args = mock_save.call_args.args
        assert call_args[0] == "automations"
        saved_workflows = call_args[1]
        assert call_args[2] == TID
        assert any(w["id"] == "my-auto-login" for w in saved_workflows)

    def test_slug_derived_from_name(self, isolated_dirs):
        """Multi-word names with special chars become alphanumeric-dash slugs."""
        _, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=[]), \
             patch.object(ata, "storage_save"):
            result = ata.create_automation_tool(
                "My Workflow! v2.0", [{"type": "click", "label": "x"}], teacher_id=TID,
            )
        # Special chars collapsed to dashes; trailing dashes stripped
        assert result["id"] == "my-workflow-v2-0"

    def test_step_id_and_params_defaults_filled(self, isolated_dirs):
        """create_automation_tool sets id and params defaults for each step."""
        _, ata = isolated_dirs
        steps = [{"type": "login", "label": "L"}, {"type": "click", "label": "C"}]
        with patch.object(ata, "storage_load", return_value=[]), \
             patch.object(ata, "storage_save") as mock_save:
            ata.create_automation_tool("Test Auto", steps, teacher_id=TID)
        # storage_save received a workflow with steps that have default id + params
        saved_wfs = mock_save.call_args.args[1]
        wf = saved_wfs[0]
        assert wf["steps"][0]["id"] == "step-1"
        assert wf["steps"][1]["id"] == "step-2"
        assert wf["steps"][0]["params"] == {}

    def test_browser_options_passed_through(self, isolated_dirs):
        _, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=[]), \
             patch.object(ata, "storage_save") as mock_save:
            ata.create_automation_tool(
                "Persistent Auto", [{"type": "click", "label": "x"}],
                browser_persistent=True, headless=True, teacher_id=TID,
            )
        wf = mock_save.call_args.args[1][0]
        assert wf["browser"]["persistent_context"] is True
        assert wf["browser"]["headless"] is True
        assert wf["browser"]["context_dir"] == "persistent-auto_browser"

    def test_browser_non_persistent_has_null_context_dir(self, isolated_dirs):
        _, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=[]), \
             patch.object(ata, "storage_save") as mock_save:
            ata.create_automation_tool(
                "Non Persistent", [{"type": "click", "label": "x"}],
                browser_persistent=False, teacher_id=TID,
            )
        wf = mock_save.call_args.args[1][0]
        assert wf["browser"]["context_dir"] is None

    def test_replaces_existing_workflow_with_same_id(self, isolated_dirs):
        """Same slug → existing workflow replaced, not duplicated."""
        _, ata = isolated_dirs
        existing = [
            {"id": "test-auto", "name": "Test Auto", "version": 1, "steps": []},
            {"id": "other", "name": "Other", "version": 1, "steps": []},
        ]
        with patch.object(ata, "storage_load", return_value=existing), \
             patch.object(ata, "storage_save") as mock_save:
            ata.create_automation_tool(
                "Test Auto", [{"type": "click", "label": "new"}], teacher_id=TID,
            )
        saved = mock_save.call_args.args[1]
        # Exactly 2 workflows (replaced, not duplicated)
        assert len(saved) == 2
        ids = [w["id"] for w in saved]
        assert ids.count("test-auto") == 1
        assert "other" in ids
        # The replacement has the new step
        new_wf = next(w for w in saved if w["id"] == "test-auto")
        assert any(s["label"] == "new" for s in new_wf["steps"])

    def test_dict_form_existing_workflows_unwrapped(self, isolated_dirs):
        """When storage returns {workflows: [...]} legacy shape, still works."""
        _, ata = isolated_dirs
        existing = {"workflows": [
            {"id": "old-one", "name": "Old", "steps": []}
        ]}
        with patch.object(ata, "storage_load", return_value=existing), \
             patch.object(ata, "storage_save") as mock_save:
            ata.create_automation_tool(
                "New Auto", [{"type": "click", "label": "x"}], teacher_id=TID,
            )
        saved = mock_save.call_args.args[1]
        # List form with both old + new
        assert isinstance(saved, list)
        ids = [w["id"] for w in saved]
        assert "old-one" in ids
        assert "new-auto" in ids

    def test_file_fallback_writes_json_file(self, isolated_dirs):
        """When storage_save unavailable, file fallback writes to AUTOMATIONS_DIR."""
        tmp, ata = isolated_dirs
        with patch.object(ata, "storage_load", None), \
             patch.object(ata, "storage_save", None):
            result = ata.create_automation_tool(
                "File Auto", [{"type": "click", "label": "x"}], teacher_id=TID,
            )
        assert result["success"] is True
        # File written
        filepath = os.path.join(ata.AUTOMATIONS_DIR, "file-auto.json")
        assert os.path.exists(filepath)
        with open(filepath) as f:
            wf = json.load(f)
        assert wf["name"] == "File Auto"


# ──────────────────────────────────────────────────────────────────
# run_automation_tool
# ──────────────────────────────────────────────────────────────────


class TestRunAutomation:
    def test_storage_match_by_substring(self, isolated_dirs):
        _, ata = isolated_dirs
        workflows = [
            {"id": "scrape-grades", "name": "Scrape Grades from Focus",
             "steps": [{"type": "login"}, {"type": "extract_text"}]},
        ]
        with patch.object(ata, "storage_load", return_value=workflows):
            # Partial substring match
            result = ata.run_automation_tool("focus", teacher_id=TID)
        assert result["found"] is True
        assert result["workflow_id"] == "scrape-grades"
        assert result["step_count"] == 2

    def test_storage_no_match_returns_error(self, isolated_dirs):
        _, ata = isolated_dirs
        with patch.object(ata, "storage_load",
                          return_value=[{"id": "x", "name": "X", "steps": []}]):
            result = ata.run_automation_tool("nonexistent", teacher_id=TID)
        assert result["found"] is False
        assert "No automation matching" in result["error"]

    def test_storage_dict_form_unwrapped(self, isolated_dirs):
        _, ata = isolated_dirs
        wrapped = {"workflows": [
            {"id": "w1", "name": "Wrapped Workflow", "steps": []}
        ]}
        with patch.object(ata, "storage_load", return_value=wrapped):
            result = ata.run_automation_tool("wrapped", teacher_id=TID)
        assert result["found"] is True

    def test_file_fallback_match(self, isolated_dirs):
        tmp, ata = isolated_dirs
        os.makedirs(ata.AUTOMATIONS_DIR, exist_ok=True)
        with open(os.path.join(ata.AUTOMATIONS_DIR, "wf.json"), 'w') as f:
            json.dump({
                "id": "from-file", "name": "From File Workflow",
                "steps": [{"type": "click"}],
            }, f)
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.run_automation_tool("file workflow", teacher_id=TID)
        assert result["found"] is True
        assert result["workflow_id"] == "from-file"

    def test_file_fallback_corrupt_json_skipped(self, isolated_dirs):
        tmp, ata = isolated_dirs
        os.makedirs(ata.AUTOMATIONS_DIR, exist_ok=True)
        with open(os.path.join(ata.AUTOMATIONS_DIR, "broken.json"), 'w') as f:
            f.write("garbage{")
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.run_automation_tool("broken", teacher_id=TID)
        # Silent skip → no match found
        assert result["found"] is False

    def test_file_fallback_no_match(self, isolated_dirs):
        tmp, ata = isolated_dirs
        with patch.object(ata, "storage_load", return_value=None):
            result = ata.run_automation_tool("doesnotexist", teacher_id=TID)
        assert result["found"] is False


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract pin
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    def test_list_automations_empty_raises(self):
        from backend.services.assistant_tools_automation import list_automations_tool
        with pytest.raises(ValueError, match="teacher_id is required"):
            list_automations_tool(teacher_id="")

    def test_create_automation_empty_raises(self):
        from backend.services.assistant_tools_automation import create_automation_tool
        with pytest.raises(ValueError, match="teacher_id is required"):
            create_automation_tool(
                "X", [{"type": "click", "label": "x"}], teacher_id="",
            )

    def test_run_automation_empty_raises(self):
        from backend.services.assistant_tools_automation import run_automation_tool
        with pytest.raises(ValueError, match="teacher_id is required"):
            run_automation_tool("X", teacher_id="")
