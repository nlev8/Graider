"""Unit tests for scripts/check_docs_drift.py (docs drift-check CI gate).

Pure-logic tests against temp trees / strings — the real-tree run happens in
the "Docs Drift Check" CI job (scripts/check_docs_drift.py executed directly),
so these tests stay hermetic and don't couple the backend suite to docs state.
"""
import importlib.util
from pathlib import Path

# scripts/ is not a package; load the script by file path WITHOUT touching
# sys.path (an inserted scripts/ dir could shadow same-named modules for the
# rest of the suite).
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_docs_drift.py"
_spec = importlib.util.spec_from_file_location("check_docs_drift", _SCRIPT)
drift = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drift)


# ---------------------------------------------------------------------------
# count_live_routes
# ---------------------------------------------------------------------------

def test_count_live_routes_counts_blueprint_route_decorators(tmp_path):
    (tmp_path / "a.py").write_text(
        "@bp.route('/api/x')\n"
        "def x():\n"
        "    pass\n"
        "@app.route('/api/y', methods=['POST'])\n"
        "def y():\n"
        "    pass\n"
    )
    sub = tmp_path / "routes"
    sub.mkdir()
    (sub / "b.py").write_text("@planner_bp.route('/api/z')\ndef z():\n    pass\n")
    assert drift.count_live_routes(tmp_path) == 3


def test_count_live_routes_ignores_non_route_lines(tmp_path):
    (tmp_path / "a.py").write_text(
        "@limiter.limit('10/min')\n"
        "def x():\n"
        "    pass\n"
        "route = '/api/x'\n"
    )
    (tmp_path / "notes.txt").write_text("@bp.route('/api/not-python')\n")
    assert drift.count_live_routes(tmp_path) == 0


# ---------------------------------------------------------------------------
# parse_documented_route_count
# ---------------------------------------------------------------------------

def test_parse_documented_route_count_reads_header():
    text = "# Graider API Reference\n\n> Auto-derived ... **308 endpoints.**\n"
    assert drift.parse_documented_route_count(text) == 308


def test_parse_documented_route_count_returns_none_when_absent():
    assert drift.parse_documented_route_count("# No count here\n") is None


# ---------------------------------------------------------------------------
# check_route_drift
# ---------------------------------------------------------------------------

def test_route_drift_within_tolerance_passes():
    # 308 documented vs 315 live = 2.2% drift, under the 5% bar.
    assert drift.check_route_drift(live=315, documented=308) == []


def test_route_drift_exact_match_passes():
    assert drift.check_route_drift(live=100, documented=100) == []


def test_route_drift_exactly_at_tolerance_passes():
    # Drift is abs(live - documented) / live; exactly 5.0% is NOT "> tolerance".
    assert drift.check_route_drift(live=100, documented=105) == []


def test_route_drift_just_over_tolerance_fails():
    # 6% drift (live=100, documented=106) is just past the 5% bar.
    problems = drift.check_route_drift(live=100, documented=106)
    assert len(problems) == 1
    assert "drift" in problems[0]


def test_route_drift_beyond_tolerance_fails():
    # 100 documented vs 120 live = 16.7% drift.
    problems = drift.check_route_drift(live=120, documented=100)
    assert len(problems) == 1
    assert "drift" in problems[0]


def test_route_drift_missing_documented_count_fails():
    problems = drift.check_route_drift(live=315, documented=None)
    assert len(problems) == 1


def test_route_drift_zero_live_routes_fails():
    # A zero live count means the scanner broke — fail loudly, never divide by 0.
    problems = drift.check_route_drift(live=0, documented=308)
    assert len(problems) == 1


# ---------------------------------------------------------------------------
# check_adr_index
# ---------------------------------------------------------------------------

def _make_adr_dir(tmp_path, index_text, adr_files=()):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "README.md").write_text(index_text)
    for name in adr_files:
        (adr_dir / name).write_text("# ADR\n")
    return adr_dir


def test_adr_index_all_links_resolve(tmp_path):
    adr_dir = _make_adr_dir(
        tmp_path,
        "| [0001](0001-two-publish-paths.md) | Two publish paths |\n",
        adr_files=["0001-two-publish-paths.md"],
    )
    assert drift.check_adr_index(adr_dir) == []


def test_adr_index_broken_link_fails(tmp_path):
    adr_dir = _make_adr_dir(
        tmp_path,
        "| [0001](0001-missing.md) | Gone |\n",
        adr_files=[],
    )
    problems = drift.check_adr_index(adr_dir)
    assert len(problems) == 1
    assert "0001-missing.md" in problems[0]


def test_adr_file_not_listed_in_index_fails(tmp_path):
    adr_dir = _make_adr_dir(
        tmp_path,
        "| [0001](0001-listed.md) | Listed |\n",
        adr_files=["0001-listed.md", "0002-unlisted.md"],
    )
    problems = drift.check_adr_index(adr_dir)
    assert len(problems) == 1
    assert "0002-unlisted.md" in problems[0]


def test_adr_index_missing_readme_fails(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    problems = drift.check_adr_index(adr_dir)
    assert len(problems) == 1


# ---------------------------------------------------------------------------
# check_module_map_paths
# ---------------------------------------------------------------------------

def test_module_map_existing_paths_pass(tmp_path):
    (tmp_path / "backend" / "routes").mkdir(parents=True)
    (tmp_path / "backend" / "routes" / "x.py").write_text("")
    doc = tmp_path / "MODULES.md"
    doc.write_text("See `backend/routes/x.py` and `backend/routes/`.\n")
    assert drift.check_module_map_paths(doc, tmp_path) == []


def test_module_map_missing_path_fails(tmp_path):
    doc = tmp_path / "MODULES.md"
    doc.write_text("See `backend/services/deleted_module.py`.\n")
    problems = drift.check_module_map_paths(doc, tmp_path)
    assert len(problems) == 1
    assert "backend/services/deleted_module.py" in problems[0]


def test_module_map_ignores_globs_and_non_repo_paths(tmp_path):
    doc = tmp_path / "MODULES.md"
    doc.write_text(
        "Wildcard `backend/routes/*.py` and env var `SUPABASE_URL` and "
        "home file `~/.graider_rubric.json` are not checked.\n"
    )
    assert drift.check_module_map_paths(doc, tmp_path) == []


def test_module_map_missing_doc_fails(tmp_path):
    problems = drift.check_module_map_paths(tmp_path / "MODULES.md", tmp_path)
    assert len(problems) == 1


# ---------------------------------------------------------------------------
# main (aggregation / exit code)
# ---------------------------------------------------------------------------

def test_main_green_tree_exits_zero(tmp_path, capsys):
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "r.py").write_text("@bp.route('/api/a')\ndef a():\n    pass\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "API_REFERENCE.md").write_text("**1 endpoints.**\n")
    (docs / "MODULES.md").write_text("`backend/r.py`\n")
    _make_adr_dir(docs, "[0001](0001-a.md)\n", adr_files=["0001-a.md"])
    assert drift.main(repo_root=tmp_path) == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_main_drifted_tree_exits_nonzero(tmp_path, capsys):
    backend = tmp_path / "backend"
    backend.mkdir()
    routes = "".join(
        f"@bp.route('/api/r{i}')\ndef r{i}():\n    pass\n" for i in range(20)
    )
    (backend / "r.py").write_text(routes)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "API_REFERENCE.md").write_text("**10 endpoints.**\n")
    (docs / "MODULES.md").write_text("`backend/r.py`\n")
    _make_adr_dir(docs, "[0001](0001-a.md)\n", adr_files=["0001-a.md"])
    assert drift.main(repo_root=tmp_path) == 1
    out = capsys.readouterr().out
    assert "drift" in out.lower()
