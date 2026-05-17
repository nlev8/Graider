"""
Shared test fixtures for Graider assistant tools.
Monkeypatches all file path constants to use temporary fixture data.
Zero network calls — all data from local fixtures.
"""
import os
import json
import csv
import shutil
import tempfile
import unittest.mock
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GRADING_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "grading")

# ---------------------------------------------------------------------------
# Session-wide redirect: ~/Downloads/Graider output dirs → per-session tmp
#
# Many production routes call os.path.expanduser("~/Downloads/Graider...")
# at request time (inside the handler body, not at import time), so patching
# os.path.expanduser globally is effective for the whole test suite.
#
# IMPORTANT: The project itself lives at ~/Downloads/Graider, so we cannot
# naively redirect ALL paths under that prefix — that would break venv paths,
# matplotlib style lookups, etc.  Instead we redirect only the known runtime
# output subtrees that export handlers write into:
#   ~/Downloads/Graider                  (root, for Lesson_Plan_*.docx etc.)
#   ~/Downloads/Graider/Results/
#   ~/Downloads/Graider/Assignments/
#   ~/Downloads/Graider/Documents/
#   ~/Downloads/Graider/Worksheets/
#   ~/Downloads/Graider/Exports/
#
# Paths that go deeper into the project tree (venv/, backend/, tests/, etc.)
# pass through unchanged.
#
# Modules that did `from os.path import expanduser` would bypass this patch.
# Audit: no export-writer in backend/ uses that form — all call
# os.path.expanduser(...) through the os.path namespace.
# ---------------------------------------------------------------------------

_real_downloads_graider = os.path.expanduser("~/Downloads/Graider")
# Known output subdirectory names that export handlers write into.
_OUTPUT_SUBDIRS = frozenset(
    ["Results", "Assignments", "Documents", "Worksheets", "Exports"]
)


def _is_output_path(real: str) -> bool:
    """Return True iff *real* is a path we should redirect to the test tmp dir.

    Matches the root dir itself, any file sitting directly in the Graider root
    (e.g. Lesson_Plan_1.docx), and any path whose first component is a known
    output subdir (Results, Assignments, etc.).
    """
    if real == _real_downloads_graider:
        # Exact match — e.g. os.path.expanduser("~/Downloads/Graider")
        return True
    prefix = _real_downloads_graider + os.sep
    if not real.startswith(prefix):
        return False
    rest = real[len(prefix):]
    parts = rest.split(os.sep)
    if len(parts) == 1:          # a file sitting directly in the Graider root
        return True
    return parts[0] in _OUTPUT_SUBDIRS


@pytest.fixture(scope="session", autouse=True)
def _redirect_downloads_graider():
    """Redirect all ~/Downloads/Graider output writes to a session temp dir.

    Wraps os.path.expanduser so that any path that resolves into a known
    ~/Downloads/Graider output subtree (Results, Assignments, Documents,
    Worksheets, Exports, or the root itself) is transparently rebased under a
    throwaway temp directory for the entire pytest session.  Every other path
    (including venv/, backend/, tests/, matplotlib styles, etc.) passes through
    unchanged.  The temp dir is cleaned up on session teardown.
    """
    _orig_expanduser = os.path.expanduser  # captured BEFORE patching
    tmp = tempfile.mkdtemp(prefix="graider_test_downloads_")

    def _wrapper(path):
        real = _orig_expanduser(path)
        if _is_output_path(real):
            suffix = real[len(_real_downloads_graider):]
            return tmp + suffix
        return real

    patcher = unittest.mock.patch("os.path.expanduser", new=_wrapper)
    patcher.start()
    yield tmp
    patcher.stop()
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def _ensure_tools_merged():
    """Ensure all submodule tools are registered.
    During pytest collection, circular imports may prevent the initial merge
    from loading all submodules. By session start all modules are fully loaded,
    so this retry succeeds."""
    import backend.services.assistant_tools as at
    at._merge_submodules()


@pytest.fixture(autouse=True)
def _reset_llm_breaker_registry():
    """Clear the LLM adapter circuit breaker registry between tests.

    Phase 5b PR 1: breakers are module-level singletons; tests that trip a
    breaker (adapter tests, preflight tests) would otherwise leave it
    OPEN for unrelated tests in the same session. Clearing before + after
    each test avoids ordering-dependent failures in CI.
    """
    try:
        from backend.services.llm_adapter import breakers
    except ImportError:  # pragma: no cover — module missing is a bigger problem
        yield
        return
    breakers._BREAKERS.clear()
    yield
    breakers._BREAKERS.clear()


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def mock_data_dir(tmp_path):
    """Create a temp directory populated with fixture data copies.
    Returns the tmp_path root so tests can point path constants here."""
    # Copy all fixture files into tmp_path
    for f in os.listdir(FIXTURES_DIR):
        src = os.path.join(FIXTURES_DIR, f)
        dst = os.path.join(tmp_path, f)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
    return tmp_path


@pytest.fixture
def patch_paths(monkeypatch, mock_data_dir):
    """Monkeypatch all assistant_tools path constants to use fixture data.
    This is the primary fixture for tool handler tests."""
    import backend.services.assistant_tools as at

    # Disable storage layer so all functions fall back to fixture files
    monkeypatch.setattr(at, "storage_load", None)
    monkeypatch.setattr(at, "storage_save", None)
    monkeypatch.setattr(at, "storage_list_keys", None)

    results_file = os.path.join(mock_data_dir, "results.json")
    settings_file = os.path.join(mock_data_dir, "settings.json")
    master_dir = os.path.join(mock_data_dir, "output")
    os.makedirs(master_dir, exist_ok=True)
    # Copy master_grades.csv into the output folder
    shutil.copy2(
        os.path.join(mock_data_dir, "master_grades.csv"),
        os.path.join(master_dir, "master_grades.csv"),
    )

    accomm_dir = os.path.join(mock_data_dir, "accommodations")
    os.makedirs(accomm_dir, exist_ok=True)
    # Split accommodations.json into per-student files
    accomm_data = json.loads(open(os.path.join(mock_data_dir, "accommodations.json")).read())
    for sid, data in accomm_data.items():
        with open(os.path.join(accomm_dir, f"{sid}.json"), "w") as fh:
            json.dump(data, fh)

    periods_dir = os.path.join(mock_data_dir, "periods")
    os.makedirs(periods_dir, exist_ok=True)
    for f in os.listdir(mock_data_dir):
        if f.startswith("roster_period_") and f.endswith(".csv"):
            shutil.copy2(os.path.join(mock_data_dir, f), os.path.join(periods_dir, f))
    # Period metadata
    meta = json.loads(open(os.path.join(mock_data_dir, "period_meta.json")).read())
    for key, val in meta.items():
        meta_file = os.path.join(periods_dir, f"roster_{key}.csv.meta.json")
        with open(meta_file, "w") as fh:
            json.dump(val, fh)

    calendar_file = os.path.join(mock_data_dir, "teaching_calendar.json")
    shutil.copy2(os.path.join(mock_data_dir, "calendar.json"), calendar_file)

    contacts_file = os.path.join(mock_data_dir, "parent_contacts.json")

    memory_file = os.path.join(mock_data_dir, "memories.json")

    lessons_dir = os.path.join(mock_data_dir, "lessons")
    os.makedirs(lessons_dir, exist_ok=True)
    # Create a sample lesson
    unit_dir = os.path.join(lessons_dir, "Unit 3 - Constitution")
    os.makedirs(unit_dir, exist_ok=True)
    with open(os.path.join(unit_dir, "Bill of Rights Review.json"), "w") as fh:
        json.dump({
            "title": "Bill of Rights Review",
            "unit": "Unit 3 - Constitution",
            "standards": ["SS.7.C.3.6"],
            "objectives": ["Review the first 10 amendments"],
            "vocabulary": ["amendment", "Bill of Rights", "ratify"],
            "days": [{"day": 1, "topic": "Amendments 1-5"}, {"day": 2, "topic": "Amendments 6-10"}],
        }, fh)

    standards_dir = os.path.join(mock_data_dir, "standards_data")
    os.makedirs(standards_dir, exist_ok=True)
    shutil.copy2(
        os.path.join(mock_data_dir, "standards_fl_civics.json"),
        os.path.join(standards_dir, "standards_fl_civics.json"),
    )

    exports_dir = os.path.join(mock_data_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)

    documents_dir = os.path.join(mock_data_dir, "documents")
    os.makedirs(documents_dir, exist_ok=True)

    assignments_dir = os.path.join(mock_data_dir, "assignments")
    os.makedirs(assignments_dir, exist_ok=True)

    # Monkeypatch all path constants
    monkeypatch.setattr(at, "RESULTS_FILE", results_file)
    monkeypatch.setattr(at, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(at, "ACCOMMODATIONS_DIR", accomm_dir)
    monkeypatch.setattr(at, "PERIODS_DIR", periods_dir)
    monkeypatch.setattr(at, "CALENDAR_FILE", calendar_file)
    monkeypatch.setattr(at, "PARENT_CONTACTS_FILE", contacts_file)
    monkeypatch.setattr(at, "MEMORY_FILE", memory_file)
    monkeypatch.setattr(at, "LESSONS_DIR", lessons_dir)
    monkeypatch.setattr(at, "STANDARDS_DIR", standards_dir)
    monkeypatch.setattr(at, "EXPORTS_DIR", exports_dir)
    monkeypatch.setattr(at, "DOCUMENTS_DIR", documents_dir)
    monkeypatch.setattr(at, "ASSIGNMENTS_DIR", assignments_dir)

    # Patch _get_output_folder to return our temp output dir
    monkeypatch.setattr(at, "_get_output_folder", lambda: master_dir)

    return mock_data_dir


@pytest.fixture
def sample_grades(patch_paths):
    """Load the fixture grade rows via the real _load_master_csv."""
    from backend.services.assistant_tools import _load_master_csv
    return _load_master_csv(period_filter='all')


@pytest.fixture
def sample_standards(patch_paths):
    """Load the fixture standards via the real _load_standards."""
    from backend.services.assistant_tools import _load_standards
    return _load_standards()


@pytest.fixture
def sample_results(patch_paths):
    """Load the fixture results JSON."""
    from backend.services.assistant_tools import _load_results
    return _load_results()


# ── Grading pipeline fixtures ──────────────────────────────────────────

@pytest.fixture
def grading_fixtures():
    """Load all grading test fixtures (submissions, configs, rubrics)."""
    data = {"submissions": {}, "configs": {}, "rubrics": {}}

    for fname in os.listdir(GRADING_FIXTURES_DIR):
        fpath = os.path.join(GRADING_FIXTURES_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        if fname.startswith("submission_") and fname.endswith(".txt"):
            key = fname.replace("submission_", "").replace(".txt", "")
            with open(fpath, "r") as f:
                data["submissions"][key] = f.read()
        elif fname.startswith("config_") and fname.endswith(".json"):
            key = fname.replace("config_", "").replace(".json", "")
            with open(fpath, "r") as f:
                data["configs"][key] = json.load(f)
        elif fname.startswith("rubric_") and fname.endswith(".json"):
            key = fname.replace("rubric_", "").replace(".json", "")
            with open(fpath, "r") as f:
                data["rubrics"][key] = json.load(f)

    return data
