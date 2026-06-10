"""
Shared test fixtures for Graider assistant tools.
Monkeypatches all file path constants to use temporary fixture data.
Zero network calls — all data from local fixtures.
"""
import os
import json
import shutil
import tempfile
import pytest

import backend.supabase_client as _supabase_client_module

# Captured at conftest import time (before any test module loads), so this is
# guaranteed to be the GENUINE function — the identity reference the audit
# sink guard below uses to tell "real client" apart from test-installed fakes.
_REAL_GET_SUPABASE = _supabase_client_module.get_supabase

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GRADING_FIXTURES_DIR = os.path.join(FIXTURES_DIR, "grading")

# Export-dir isolation: backend.paths.graider_export_dir() honors
# GRAIDER_EXPORT_DIR (call-time). Setting it session-wide before any test
# body runs guarantees no test writes to a real ~/Downloads/Graider. All
# production sites were migrated to the resolver, so this single mechanism
# replaces the prior global os.path.expanduser monkeypatch.
@pytest.fixture(scope="session", autouse=True)
def _redirect_graider_export_dir():
    prior = os.environ.get("GRAIDER_EXPORT_DIR")
    tmp = tempfile.mkdtemp(prefix="graider_test_exports_")
    os.environ["GRAIDER_EXPORT_DIR"] = tmp
    yield tmp
    if prior is None:
        os.environ.pop("GRAIDER_EXPORT_DIR", None)
    else:
        os.environ["GRAIDER_EXPORT_DIR"] = prior
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def _ensure_tools_merged():
    """Ensure all submodule tools are registered.
    During pytest collection, circular imports may prevent the initial merge
    from loading all submodules. By session start all modules are fully loaded,
    so this retry succeeds."""
    import backend.services.assistant_tools as at
    at._merge_submodules()


# ── Issue #731: live-Supabase isolation ─────────────────────────────────
# The developer .env carries PRODUCTION Supabase credentials, so any code
# path that reaches the real backend.supabase_client singletons during a
# local pytest run talks to the LIVE project. Proven leak (2026-06-10): the
# audit sink in backend/utils/audit.py inserted fixture rows (teacher_id
# 't-1', actions CLEVER_USER_READ / CLASSLINK_LOGIN / ...) into the
# production audit_log table during full-suite runs. A create_client-level
# probe additionally showed unit tests reaching live teacher_data /
# submissions / published_assessments via unmocked storage paths.
#
# Guard strategy (autouse, per test):
#   1. Null the supabase_client singletons and stub create_client so
#      get_supabase()/get_raw_supabase()/get_supabase_or_raise() behave
#      exactly as they do in CI (no SUPABASE_URL there → no client). Tests
#      that need a client install their own fakes via mock.patch /
#      monkeypatch, which override this guard and restore it afterwards.
#   2. Patch the audit sink seam (backend.utils.audit._get_audit_supabase)
#      with an identity guard: the REAL get_supabase is never invoked from
#      audit_log() during a test — even if a real singleton exists — while a
#      test-installed fake on backend.supabase_client.get_supabase IS
#      honored (tests/test_audit_redaction.py asserts on inserted payloads).
#
# Intentionally-live modules (real-Supabase e2e/schema smoke tests that
# self-skip when Supabase is unconfigured and clean up the rows they
# create) are exempt: they exist to exercise the live project deliberately.
_LIVE_SUPABASE_TEST_MODULES = frozenset({
    "test_e2e_pipeline",
    "test_e2e_multi_teacher",
    "test_e2e_classroom",
    "test_schema_assertions",
    "test_schema_audit",
})


@pytest.fixture(autouse=True)
def _isolate_live_supabase(request, monkeypatch):
    """Prevent tests from reaching the live Supabase project (issue #731)."""
    # request.module.__name__ may be dotted ("tests.test_e2e_pipeline") —
    # compare on the final component only.
    if request.module.__name__.rpartition(".")[2] in _LIVE_SUPABASE_TEST_MODULES:
        yield
        return

    import backend.utils.audit as _audit_module

    # (1) No real client can be created or reused during this test.
    monkeypatch.setattr(_supabase_client_module, "_supabase_raw", None)
    monkeypatch.setattr(_supabase_client_module, "_supabase_resilient", None)
    monkeypatch.setattr(
        _supabase_client_module, "create_client", lambda *a, **k: None
    )

    # (2) Audit sink: block the real client even if a singleton somehow
    #     exists, but honor an explicitly installed test fake.
    def _guarded_audit_supabase():
        current = _supabase_client_module.get_supabase
        if current is _REAL_GET_SUPABASE:
            return None  # unpatched = would be the live client → block
        return current()  # a test installed its own fake → honor it

    monkeypatch.setattr(
        _audit_module, "_get_audit_supabase", _guarded_audit_supabase
    )
    yield


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
