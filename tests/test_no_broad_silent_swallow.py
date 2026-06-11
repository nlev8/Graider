"""Guard test: broad silent exception swallows in ``backend/`` stay under the
rubric-8 threshold.

The 2026-06-02 hardening rubric (``docs/superpowers/specs/2026-06-02-
hardening-rubric-anchors.md``, dimension 2 "Error Handling") sets level 8 as:
"every broad ``except`` logs or captures; <10 silent ``except…: pass``".

A *broad silent swallow* here is an ``except Exception`` / ``except
BaseException`` / bare ``except:`` whose entire body is only ``pass`` (or only
``continue``) and which does NOT log, capture, re-raise, or otherwise observe
the error. PR1 of the hardening sprint converted all 82 such sites to emit a
DEBUG/WARNING log. This test re-runs the same AST scan and pins the count below
10 so the invariant can't silently regress.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

# Anything in the handler source that observes the error disqualifies it from
# being a "silent" swallow.
_OBSERVED_MARKERS = (
    "logger",
    "logging",
    "_logger",
    "capture_exception",
    "capture_message",
    "raise",
    "sentry",
    "print(",
)


def _find_broad_silent_swallows():
    """Return a list of ``"<relpath>:<lineno>"`` for every broad silent swallow."""
    sites = []
    for p in sorted(BACKEND.rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.ExceptHandler):
                continue
            body_src = ast.get_source_segment(src, n) or ""
            if any(marker in body_src for marker in _OBSERVED_MARKERS):
                continue
            stmts = n.body
            is_silent = all(isinstance(s, ast.Pass) for s in stmts) or (
                len(stmts) == 1 and isinstance(stmts[0], (ast.Pass, ast.Continue))
            )
            if not is_silent:
                continue
            t = n.type
            broad = (
                t is None
                or (isinstance(t, ast.Name) and t.id in ("Exception", "BaseException"))
                or (
                    isinstance(t, ast.Tuple)
                    and any(
                        isinstance(e, ast.Name) and e.id in ("Exception", "BaseException")
                        for e in t.elts
                    )
                )
            )
            if broad:
                sites.append(f"{p.relative_to(ROOT)}:{n.lineno}")
    return sites


def test_broad_silent_swallows_below_threshold():
    """Rubric Error-Handling level 8: <10 broad silent ``except…: pass`` in backend/."""
    sites = _find_broad_silent_swallows()
    assert len(sites) < 10, (
        f"Found {len(sites)} broad silent exception swallows in backend/ "
        f"(rubric level-8 requires <10). Each broad except must log or capture. "
        f"Offending sites:\n" + "\n".join(sites)
    )
