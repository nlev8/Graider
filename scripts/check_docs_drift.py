#!/usr/bin/env python3
"""Docs drift check — fails CI when key docs go stale.

Rubric anchors §6 level 10 ("docs generated and drift-checked in CI: stale
docs fail the build"). Three deterministic checks, no AI, no network:

1. Route-count drift: live Flask route registrations under backend/
   (the Python equivalent of `grep -rE "@[a-z_]+\\.route\\(" backend
   --include='*.py'`) vs the endpoint count declared in the
   docs/API_REFERENCE.md header (`**N endpoints.**`). Fails when relative
   drift exceeds ROUTE_DRIFT_TOLERANCE (±5% — the anchors' own level-7
   tolerance for the API reference).
2. ADR index integrity: every relative `*.md` link in docs/adr/README.md
   must resolve to an existing file, and every `NNNN-*.md` ADR on disk
   must be linked from the index.
3. Module-map path integrity: every backtick-quoted repo path in
   docs/MODULES.md (backend/, frontend/src/, scripts/, tests/) must exist.

Run locally:  python scripts/check_docs_drift.py
CI:           "Docs Drift Check" job in .github/workflows/ci.yml
Tests:        tests/test_docs_drift.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Same pattern family as the CLAUDE.md "API Reference" command:
#   grep -rE "@[a-z_]+\.route\(" backend --include='*.py'
ROUTE_DECORATOR_RE = re.compile(r"@[a-z_]+\.route\(")

# `**308 endpoints.**` in the API_REFERENCE.md header blockquote.
DOCUMENTED_COUNT_RE = re.compile(r"\*\*(\d+)\s+endpoints?\b")

# Relative markdown links inside the ADR index: [text](0001-foo.md)
ADR_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)\)")

# Backtick-quoted repo paths in the module map. Restricted to known
# top-level dirs and a conservative charset; anything with a glob (*) or
# outside these roots (env vars, ~/ paths, URLs) is intentionally skipped.
MODULE_PATH_RE = re.compile(
    r"`((?:backend|frontend/src|scripts|tests)/[A-Za-z0-9_./-]*)`"
)

ROUTE_DRIFT_TOLERANCE = 0.05  # ±5%


def count_live_routes(backend_dir: Path) -> int:
    """Count Flask route-decorator lines in all .py files under backend_dir."""
    total = 0
    for py_file in sorted(backend_dir.rglob("*.py")):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += sum(
            1 for line in text.splitlines() if ROUTE_DECORATOR_RE.search(line)
        )
    return total


def parse_documented_route_count(text: str) -> int | None:
    """Extract the `**N endpoints**` count from API_REFERENCE.md text."""
    match = DOCUMENTED_COUNT_RE.search(text)
    return int(match.group(1)) if match else None


def check_route_drift(
    live: int,
    documented: int | None,
    tolerance: float = ROUTE_DRIFT_TOLERANCE,
) -> list[str]:
    """Compare live vs documented route counts; return problem strings."""
    if documented is None:
        return [
            "docs/API_REFERENCE.md: could not find a '**N endpoints**' count "
            "in the header — add/restore it so drift can be measured."
        ]
    if live == 0:
        return [
            "Route scanner found 0 live routes under backend/ — the scanner "
            "is broken (or backend/ moved); refusing to compare."
        ]
    drift = abs(live - documented) / live
    if drift > tolerance:
        return [
            f"API_REFERENCE.md route-count drift {drift:.1%} exceeds "
            f"{tolerance:.0%}: {documented} documented vs {live} live. "
            "Regenerate the API reference and update the '**N endpoints**' "
            "header count."
        ]
    return []


def check_adr_index(adr_dir: Path) -> list[str]:
    """Validate docs/adr/README.md: links resolve, every ADR is indexed."""
    index = adr_dir / "README.md"
    if not index.is_file():
        return [f"{index}: ADR index is missing."]
    text = index.read_text(encoding="utf-8")
    problems = []
    linked = set(ADR_LINK_RE.findall(text))
    for link in sorted(linked):
        if not (adr_dir / link).is_file():
            problems.append(
                f"docs/adr/README.md links to '{link}' but that file does not exist."
            )
    for adr_file in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        if adr_file.name not in linked:
            problems.append(
                f"ADR '{adr_file.name}' exists but is not linked from docs/adr/README.md."
            )
    return problems


def check_module_map_paths(doc_path: Path, repo_root: Path) -> list[str]:
    """Validate that backtick-quoted repo paths in the module map exist."""
    if not doc_path.is_file():
        return [f"{doc_path}: module map is missing."]
    text = doc_path.read_text(encoding="utf-8")
    problems = []
    for raw in sorted(set(MODULE_PATH_RE.findall(text))):
        rel = raw.rstrip("/")
        if not rel or "*" in rel:
            continue
        if not (repo_root / rel).exists():
            problems.append(
                f"{doc_path.name} references '{raw}' which does not exist in the repo."
            )
    return problems


def main(repo_root: Path | None = None) -> int:
    root = repo_root or Path(__file__).resolve().parent.parent
    backend_dir = root / "backend"
    api_ref = root / "docs" / "API_REFERENCE.md"
    adr_dir = root / "docs" / "adr"
    module_map = root / "docs" / "MODULES.md"

    live = count_live_routes(backend_dir)
    documented = (
        parse_documented_route_count(api_ref.read_text(encoding="utf-8"))
        if api_ref.is_file()
        else None
    )

    problems: list[str] = []
    problems += check_route_drift(live, documented)
    problems += check_adr_index(adr_dir)
    problems += check_module_map_paths(module_map, root)

    print(f"Live routes under backend/: {live}")
    print(f"Documented endpoints (API_REFERENCE.md): {documented}")
    if documented and live:
        print(
            f"Drift: {abs(live - documented) / live:.1%} "
            f"(tolerance {ROUTE_DRIFT_TOLERANCE:.0%})"
        )

    if problems:
        print(f"\nDOCS DRIFT CHECK FAILED — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nDocs drift check OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
