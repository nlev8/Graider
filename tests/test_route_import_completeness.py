"""GH #423 — latent NameError: grading-results + FERPA routes referenced
`save_results` / `grade_with_parallel_detection` without importing them.

During the verbatim app.py -> grading_results_routes.py extraction (and in
ferpa_routes.py), these symbols were used in route bodies but never bound at
module level — so the grade-individual / delete-result / update-approval and
the FERPA-import paths raised `NameError` whenever executed. These pins assert
the symbols are bound at module scope so the routes can't silently regress to
a NameError. (Also implicitly proves the imports introduce no import cycle —
the modules wouldn't import at all if they did.)
"""
import importlib


def test_grading_results_routes_binds_grading_symbols():
    m = importlib.import_module("backend.routes.grading_results_routes")
    assert hasattr(m, "save_results"), \
        "save_results must be imported at module level (GH #423 latent NameError)"
    assert hasattr(m, "grade_with_parallel_detection"), \
        "grade_with_parallel_detection must be imported (GH #423 latent NameError)"


def test_ferpa_routes_binds_save_results():
    m = importlib.import_module("backend.routes.ferpa_routes")
    assert hasattr(m, "save_results"), \
        "save_results must be imported at module level (GH #423 latent NameError)"
