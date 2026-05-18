import os
import pytest
from backend.paths import graider_export_dir


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("GRAIDER_EXPORT_DIR", raising=False)


def test_default_is_byte_identical_to_prior_expanduser():
    base = os.path.expanduser("~/Downloads/Graider")
    assert graider_export_dir() == base
    for sub in ("Results", "Assignments", "Documents", "Worksheets", "Exports"):
        assert graider_export_dir(sub) == os.path.join(base, sub)
    assert graider_export_dir("Results", "master_grades.csv") == os.path.join(
        base, "Results", "master_grades.csv"
    )


def test_env_var_overrides_base(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
    assert graider_export_dir() == str(tmp_path)
    assert graider_export_dir("Results") == os.path.join(str(tmp_path), "Results")


def test_resolved_fresh_each_call(monkeypatch, tmp_path):
    a = graider_export_dir("Results")
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path))
    b = graider_export_dir("Results")
    assert a != b and b == os.path.join(str(tmp_path), "Results")


def test_creates_no_directory(monkeypatch, tmp_path):
    target = tmp_path / "nope"
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(target))
    graider_export_dir("Results")
    assert not target.exists()


def test_empty_env_var_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", "")
    assert graider_export_dir() == os.path.expanduser("~/Downloads/Graider")
