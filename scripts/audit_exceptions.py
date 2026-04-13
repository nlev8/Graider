#!/usr/bin/env python3
"""AST-based exception handler auditor for the Graider backend.

Walks every .py file under backend/, finds each `except` block, and emits
a markdown table with: file, line, exception type(s), handler behavior,
parent function, and a Category column for manual annotation.

Usage:
    python scripts/audit_exceptions.py > docs/exception-audit-2026-04.md

Then manually fill in the Category column (INTENTIONAL / LEGACY /
NEEDS_ALERT / UNCATEGORIZED) for integration-critical rows.
"""

import ast
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"


def classify_handler_body(handler: ast.ExceptHandler) -> str:
    """Classify what the except handler does with the caught exception."""
    if not handler.body:
        return "empty"

    behaviors = []
    for node in ast.walk(handler):
        if isinstance(node, ast.Pass):
            behaviors.append("pass")
        elif isinstance(node, ast.Raise):
            behaviors.append("raise")
        elif isinstance(node, ast.Return):
            behaviors.append("return")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr in (
                    "error", "warning", "info", "exception",
                    "debug", "critical",
                ):
                    behaviors.append(f"log.{func.attr}")
                elif func.attr == "append":
                    behaviors.append("append")
            elif isinstance(func, ast.Name):
                if func.id == "print":
                    behaviors.append("print")

    if not behaviors:
        return "other"
    return " + ".join(sorted(set(behaviors)))


def get_exception_types(handler: ast.ExceptHandler) -> str:
    """Extract the exception type(s) from an except handler."""
    if handler.type is None:
        return "bare except"
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Tuple):
        return "(" + ", ".join(
            elt.id if isinstance(elt, ast.Name) else ast.unparse(elt)
            for elt in handler.type.elts
        ) + ")"
    if isinstance(handler.type, ast.Attribute):
        parts = []
        node = handler.type
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    try:
        return ast.unparse(handler.type)
    except Exception:
        return str(handler.type)


def find_parent_function(tree: ast.Module, target_line: int) -> str:
    """Find the innermost function/method containing the given line."""
    best_name = "<module>"
    best_span = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", None)
            if end is None:
                continue
            if node.lineno <= target_line <= end:
                span = end - node.lineno
                if best_span is None or span < best_span:
                    best_name = node.name
                    best_span = span
    return best_name


def audit_file(filepath: Path, tree: ast.Module) -> list[dict]:
    """Extract all except handlers from a parsed AST."""
    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            rel_path = filepath.relative_to(BACKEND_DIR.parent)
            results.append({
                "file": str(rel_path),
                "line": node.lineno,
                "exception_type": get_exception_types(node),
                "handler_behavior": classify_handler_body(node),
                "parent_function": find_parent_function(tree, node.lineno),
                "category": "UNCATEGORIZED",
            })
    return results


def main():
    all_results = []

    for py_file in sorted(BACKEND_DIR.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            all_results.extend(audit_file(py_file, tree))
        except SyntaxError as e:
            print(f"<!-- SKIP {py_file}: {e} -->", file=sys.stderr)

    from datetime import date
    print("# Exception Handler Audit — Graider Backend")
    print()
    print(f"> Generated: {date.today()}")
    print(f"> Total handlers: {len(all_results)}")
    print(f"> Files scanned: {len(set(r['file'] for r in all_results))}")
    print()
    print("## Category Legend")
    print()
    print("- **INTENTIONAL** — broad catch is correct by design (SIS API flakiness, graceful degradation)")
    print("- **LEGACY** — should be replaced with typed exception or removed (Phase 2 fixes)")
    print("- **NEEDS_ALERT** — failure should be observable via BetterStack (currently silent)")
    print("- **UNCATEGORIZED** — not yet reviewed")
    print()
    print("## Handlers")
    print()
    print("| File | Line | Exception Type | Handler Behavior | Parent Function | Category |")
    print("|------|------|---------------|-----------------|-----------------|----------|")

    for r in all_results:
        print(
            f"| `{r['file']}` | {r['line']} | `{r['exception_type']}` | "
            f"{r['handler_behavior']} | `{r['parent_function']}` | {r['category']} |"
        )


if __name__ == "__main__":
    main()
