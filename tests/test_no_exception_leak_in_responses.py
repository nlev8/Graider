"""Regression guard: route handlers must not return raw exception text to clients.

Returning ``str(e)`` (or an f-string interpolating the exception) in an HTTP
response body leaks internal detail — stack context, file paths, DB/library
internals — to the client. This is the level-8 ``[CAP]`` criterion for both the
Security and Error Handling dimensions in
``docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md``: *0
exception-string-to-client sites*.

Server-side logging of the exception is correct and expected (and is preserved
at every fixed site); what this test forbids is the exception text reaching the
*response payload*. The generic, human-readable prefix (e.g. "Connection
failed") stays; only the interpolated exception value is removed.

Scope: ``backend/routes/`` (the client-facing layer). Service-layer dict returns
in ``backend/services/assistant_tools_*`` feed the AI tool-use loop and are
tracked as a separate follow-up, not gated here.
"""
import pathlib
import re

ROUTES_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend" / "routes"

# Matches a client-facing error/message/detail field whose VALUE references the
# caught exception variable, in any of the observed forms:
#   "error": str(e)              'error': str(e)[:200],
#   "error": f"...{str(e)}..."   "error": f"...{e}..."
#   "error": "..." + str(e)
# Logging calls (logger.*/logging.*) carry no such field and are not matched.
_LEAK = re.compile(
    r"""["'](?:error|message|detail|msg)["']\s*:\s*"""   # an error-ish field
    r""".*?"""                                            # any prefix text
    r"""(?:str\(e\)|str\(exc\)|str\(err\)|\{e[}\[:!]|\{str\(e\)|\{exc[}\[:!]|\{err[}\[:!])""",
    re.VERBOSE,
)


def _scan(path: pathlib.Path):
    offenders = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        # Skip logging statements — server-side logging of str(e) is correct.
        if re.match(r"^(?:_?logger|logging|current_app\.logger)\.", stripped):
            continue
        if _LEAK.search(line):
            offenders.append(f"{path.name}:{i}: {stripped}")
    return offenders


def test_no_route_returns_raw_exception_text():
    all_offenders = []
    for py in sorted(ROUTES_DIR.glob("*.py")):
        all_offenders.extend(_scan(py))
    assert not all_offenders, (
        "Route handlers must not return raw exception text to clients "
        "(Security/Error-Handling rubric level-8 [CAP]). Offending sites:\n  "
        + "\n  ".join(all_offenders)
    )
