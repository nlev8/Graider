"""Regression guard: silent `except ...: pass` swallows must not regrow.

Hardening sprint PR6 (docs/superpowers/plans/2026-06-09-hardening-sprint-to-85.md)
swept the backend's silent exception swallows from 49 down to a small,
individually-justified survivor set. Each survivor is a site where silence is
the *correct* behavior (numeric-parse probe chains, optional signal-handler
registration, per-chunk streaming control flow) and carries an inline
justification comment on the `pass` line.

This test is the Python equivalent of the anchor grep:

    grep -rnE "except[^:]*:\\s*$" backend/ --include='*.py' -A1 | grep -c "pass"

i.e. an `except` clause (no inline comment after the colon) whose very next
line is a bare `pass`. Two invariants:

1. The total count must stay at or below the post-sweep ceiling. New silent
   swallows must instead log (debug for expected/hot paths, warning for
   operationally interesting failures), re-raise, or — if silence is genuinely
   correct — keep `pass` WITH an inline justification comment and a ceiling
   bump justified in this file's history.
2. Every surviving `pass` must carry an inline justification comment
   (`pass  # why silence is correct here`). An unexplained bare `pass` under
   an `except` is a defect even if the count is under the ceiling.
"""
import pathlib
import re

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend"

# Post-sweep survivor ceiling (2026-06-11, hardening PR6). The 9 survivors:
#   backend/services/stem_grading.py        x6  (numeric-parse probe chain —
#       failure is the normal control path for symbolic/string input)
#   backend/services/portal_grading.py      x1  (SIGTERM handler registration —
#       unavailable in non-main threads by design)
#   backend/services/llm_adapter/gemini_adapter.py x1 (chunk.text raises on
#       function-call chunks — documented SDK behavior, per-chunk hot loop)
#   backend/services/assistant_tools_ai.py  x1  (direct-JSON-parse probe —
#       fence-strip retry immediately follows)
MAX_SILENT_SWALLOWS = 9

# Mirrors the anchor grep: `except ...:` ending the line (no trailing comment).
_EXCEPT_RE = re.compile(r"except[^:]*:\s*$")
# The swallow: next line is `pass` (with or without trailing comment).
_PASS_RE = re.compile(r"^\s*pass\b")


def _find_swallow_sites():
    """Return [(relpath, lineno, pass_line)] for every except->pass site."""
    sites = []
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines[:-1]):
            if _EXCEPT_RE.search(line) and _PASS_RE.match(lines[i + 1]):
                rel = path.relative_to(BACKEND_DIR.parent).as_posix()
                sites.append((rel, i + 2, lines[i + 1].strip()))
    return sites


def test_silent_swallow_count_under_ceiling():
    sites = _find_swallow_sites()
    listing = "\n".join(f"  {f}:{n}: {l}" for f, n, l in sites)
    assert len(sites) <= MAX_SILENT_SWALLOWS, (
        f"{len(sites)} silent `except: pass` swallows found "
        f"(ceiling {MAX_SILENT_SWALLOWS}). Log it (debug/warning), re-raise, "
        f"or justify the silence inline AND bump the ceiling with a dated "
        f"comment. Sites:\n{listing}"
    )


def test_every_surviving_swallow_is_justified():
    unjustified = [
        (f, n, l) for f, n, l in _find_swallow_sites() if "#" not in l
    ]
    listing = "\n".join(f"  {f}:{n}: {l}" for f, n, l in unjustified)
    assert not unjustified, (
        "Surviving `except: pass` sites missing an inline justification "
        f"comment on the pass line:\n{listing}"
    )
