"""Regression guard: backend modules must be imported via ``backend.<pkg>.*`` only.

Python's import system registers each fully-qualified module path as its own
entry in ``sys.modules``. When `backend/app.py` says ``from routes import
register_routes`` and the test suite imports the same subpackage as
``backend.routes``, Python creates TWO distinct module objects — one under
``routes.student_portal_routes`` and one under
``backend.routes.student_portal_routes`` — each with their own class-level
and module-level state.

For most modules this is merely wasteful. For three patterns in this codebase
it silently breaks correctness:

1. ``backend.grading.state`` (fixed PR #80) — the per-teacher write lock that
   serialises ``load_saved_results → append → save_results`` in
   ``portal_grading.py`` lives in one module instance, while the batch
   grader in ``pipeline.py`` holds a lock from the other instance. Concurrent
   writes on the same teacher race and one append is silently lost.

2. ``backend.routes`` (fixed PR this branch) — flask-limiter 4.1.1 keys its
   ``decorated_limits`` registry on ``view_fn.__module__`` at decoration
   time. When ``backend/app.py`` imports via the short path, decorated view
   callables end up with ``__module__ == 'routes.student_portal_routes'``
   while Flask's url_map resolves the request's view to the
   ``backend.routes.student_portal_routes`` twin. The registry lookup
   returns ``[]`` for every decorated route and every rate limit silently
   no-ops in production.

3. ``backend.auth``, ``backend.storage``, ``backend.supabase_client``,
   ``backend.utils.*`` — no confirmed correctness bugs, but they share the
   same structural risk whenever module-level singletons (e.g. cached Supabase
   client, lazily-initialised JWKS client) live in them. A short-path import
   in any future edit would produce a second instance and divergent state.

This test prevents the regression at the source-grep level: zero
top-level unconditional short-path imports anywhere in ``backend/``.

Intentional fallback patterns like ::

    try:
        from backend.storage import load
    except ImportError:
        try:
            from storage import load  # legacy fallback for test harnesses
        except ImportError:
            ...

are INDENTED and therefore NOT matched (the regex anchors at column 0). The
Python ``try/except ImportError`` ensures at most one of the two branches
actually runs, so the short-path name is never added to ``sys.modules`` when
the canonical import succeeds.
"""
from __future__ import annotations

import pathlib
import re


# Modules that must ALWAYS be imported via the ``backend.`` prefix when
# referenced from inside the ``backend/`` tree. Top-level unconditional
# ``from X ...`` / ``import X`` forms are disallowed.
_PROTECTED_MODULES = (
    "grading",
    "routes",
    "auth",
    "storage",
    "supabase_client",
    "utils",
    "services",
    "observability",
    "tasks",
    "database",
    "extensions",
    "celery_app",
    "accommodations",
    "student_history",
)


# Anchor at column 0 (no ``\s*``) — the regex only matches unconditional,
# top-level imports. Indented fallback imports inside ``try/except`` blocks
# are intentional and safe (Python only runs the except branch on failure).
_SHORT_PATH_PATTERN = re.compile(
    r"^(?:from\s+(?P<mod_from>{modules})(?:\.|\s)|import\s+(?P<mod_import>{modules})(?:\.|\s))".format(
        modules="|".join(_PROTECTED_MODULES),
    ),
    re.MULTILINE,
)


def test_no_short_path_backend_imports_in_backend():
    """Every protected-module import in backend/** must use the ``backend.`` prefix."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"

    offenders: list[str] = []
    for py_path in backend_dir.rglob("*.py"):
        text = py_path.read_text(encoding="utf-8", errors="replace")
        for match in _SHORT_PATH_PATTERN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(
                f"{py_path.relative_to(repo_root)}:{line_no} -> {match.group(0).strip()}"
            )

    assert not offenders, (
        "Short-path backend imports found — these split a module across two "
        "sys.modules entries and break singletons (flask-limiter registry, "
        "grading state locks, Supabase client cache, etc.). "
        "Use the ``backend.`` prefix instead.\n"
        + "\n".join(offenders)
    )


def test_full_path_grading_modules_singleton():
    """Sanity: the canonical ``backend.grading.*`` imports resolve to one module each."""
    import backend.grading.state as state_a
    import backend.grading.state as state_b
    assert state_a is state_b

    import backend.grading.pipeline as pipe_a
    import backend.grading.pipeline as pipe_b
    assert pipe_a is pipe_b

    import backend.grading.thread as thread_a
    import backend.grading.thread as thread_b
    assert thread_a is thread_b


def test_full_path_routes_module_singleton():
    """Sanity: ``backend.routes`` and child blueprints resolve to single modules.

    Regression guard for the flask-limiter non-firing bug: if a test run ever
    ends up with both ``routes.student_portal_routes`` and
    ``backend.routes.student_portal_routes`` in ``sys.modules``, the two
    ``student_portal_bp`` objects will be different instances and this test
    will fail before the dual-registration can cause subtler downstream bugs.
    """
    import sys

    import backend.routes as routes_pkg_a
    import backend.routes as routes_pkg_b
    assert routes_pkg_a is routes_pkg_b

    import backend.routes.student_portal_routes as spr
    # Short-path twin must NOT be loaded — its presence in sys.modules means
    # something in the import chain reached for the unqualified name.
    assert "routes.student_portal_routes" not in sys.modules, (
        "Short-path `routes.student_portal_routes` is loaded in sys.modules "
        "alongside `backend.routes.student_portal_routes`. flask-limiter's "
        "decorated_limits registry is keyed on view_fn.__module__ and will "
        "silently return [] for whichever twin Flask's url_map resolves to."
    )
    assert spr is sys.modules["backend.routes.student_portal_routes"]
