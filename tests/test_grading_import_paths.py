"""Regression guard: grading modules must be imported via `backend.grading.*` only.

Prior to this test, `backend/app.py`, `backend/grading/pipeline.py`, and
`backend/grading/thread.py` used short-path imports (`from grading.state ...`)
while every other consumer used the full path (`from backend.grading.state ...`).

At runtime Python registers `grading.state` and `backend.grading.state` as
two distinct entries in ``sys.modules``, each with its own module-level
``_grading_states`` dict and ``_grading_locks`` table. The per-teacher lock
that serializes ``load_saved_results -> append -> save_results`` in
``portal_grading.py`` lives in one module; the batch grader in
``pipeline.py`` holds the lock from the other. When both run concurrently
for the same teacher the two write paths race on ``teacher_data['results']``
and one append is silently lost.

This test prevents the regression at the source-grep level: zero
short-path imports anywhere in the ``backend/`` tree.
"""
from __future__ import annotations

import pathlib
import re


_SHORT_PATH_PATTERN = re.compile(
    r"^\s*(?:from\s+grading(?:\.|\s)|import\s+grading(?:\.|\s))",
    re.MULTILINE,
)


def test_no_short_path_grading_imports_in_backend():
    """Every grading-module import in backend/** must use the ``backend.grading.*`` prefix."""
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"

    offenders: list[str] = []
    for py_path in backend_dir.rglob("*.py"):
        text = py_path.read_text(encoding="utf-8", errors="replace")
        for match in _SHORT_PATH_PATTERN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{py_path.relative_to(repo_root)}:{line_no} -> {match.group(0).strip()}")

    assert not offenders, (
        "Short-path `from grading.*` imports found — these split the grading "
        "state module across two sys.modules entries and break lock "
        "serialization. Use `from backend.grading.*` instead.\n"
        + "\n".join(offenders)
    )


def test_full_path_grading_modules_singleton():
    """Sanity: the canonical `backend.grading.*` imports resolve to one module each."""
    import backend.grading.state as state_a
    import backend.grading.state as state_b
    assert state_a is state_b

    import backend.grading.pipeline as pipe_a
    import backend.grading.pipeline as pipe_b
    assert pipe_a is pipe_b

    import backend.grading.thread as thread_a
    import backend.grading.thread as thread_b
    assert thread_a is thread_b
