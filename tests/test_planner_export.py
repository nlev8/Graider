from backend.services import planner_export as pe


def test_get_export_dir_returns_pathlike():
    d = pe._get_export_dir()
    assert isinstance(d, str) and len(d) > 0


def test_module_has_no_flask_import():
    src = open(pe.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src
