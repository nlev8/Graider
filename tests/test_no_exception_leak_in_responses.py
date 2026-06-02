"""Regression guard: route handlers must not put raw exception text where it can
reach a client response.

Returning ``str(e)`` (or an f-string interpolating the exception) in an HTTP
response leaks internal detail — stack context, file paths, DB/library internals.
This is the level-8 ``[CAP]`` criterion for both the Security and Error Handling
dimensions in ``docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md``:
*0 exception-string-to-client sites*.

The invariant is enforced at the **creation point**, not by tracking where the
value flows. The convention for ``backend/routes/`` is simple:

    An exception (``str(e)`` / ``{e}``) may appear ONLY in
      (a) a logging call  — pass the exception, e.g. ``logger.warning("...: %s", e)``
      (b) inline inspection — ``str(e).lower()``, ``"x" in str(e)`` (control flow)
    It must NEVER be assigned to a variable or placed in a dict / list / response
    payload, because from there it can flow to the client.

Because the exception string is forbidden at the point it is produced, there is
nothing to taint-track: ``error_msg = str(e)`` is itself the violation, caught
regardless of where ``error_msg`` later goes.

Scope: ``backend/routes/`` (the client-facing layer). Service-layer
``backend/services/assistant_tools_*`` dict returns feed the AI tool-use loop
(consumed by the model, not returned raw) and are a tracked follow-up.
"""
import pathlib
import re

ROUTES_DIR = pathlib.Path(__file__).resolve().parent.parent / "backend" / "routes"

# An exception variable being stringified / interpolated.
_EXC = re.compile(r"str\(e\)|str\(exc\)|str\(err\)|\{e[}\[:!]|\{str\(e\)|\{exc[}\[:!]|\{err[}\[:!]")

# (a) a logging statement — the exception belongs here.
_LOGGING = re.compile(r"^(?:_?logger|logging|log|current_app\.logger)\.")
# (b) inline exception-content inspection for control flow — not a response.
# NOTE: this exemption assumes the inspected value is used for control flow only
# (e.g. `if "timeout" in str(e).lower()`), NOT returned. `jsonify({"error":
# str(e).lower()})` would slip through — don't do that; lowercasing an exception
# into a response is still a leak. Acceptable residual for a regex guard (the
# pattern is unidiomatic and the exemption is required for the 503 network-error
# detection in planner_routes).
_INSPECT = re.compile(r"str\((?:e|exc|err)\)\.(?:lower|upper|find|startswith|split)|in str\((?:e|exc|err)\)|str\((?:e|exc|err)\)\s*==|==\s*str\((?:e|exc|err)\)")


def _exempt(stripped: str) -> bool:
    return (
        not stripped
        or stripped.startswith("#")
        or bool(_LOGGING.match(stripped))
        or bool(_INSPECT.search(stripped))
    )


def _scan(path: pathlib.Path):
    offenders = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if _exempt(stripped):
            continue
        if _EXC.search(raw):
            offenders.append(f"{path.name}:{i}: {stripped}")
    return offenders


def test_no_route_exposes_raw_exception_text():
    offenders = []
    for py in sorted(ROUTES_DIR.glob("*.py")):
        offenders.extend(_scan(py))
    assert not offenders, (
        "Raw exception text must not be produced outside a logging call or inline "
        "inspection in backend/routes/ — it can leak to clients (Security / Error "
        "Handling rubric level-8 [CAP]). Log the exception (logger.x('...: %s', e)) "
        "or inspect it inline (str(e).lower()); never store it in a variable or "
        "response payload. Offending sites:\n  " + "\n  ".join(offenders)
    )
