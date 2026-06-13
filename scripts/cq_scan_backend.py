#!/usr/bin/env python3
"""CQ level-8 backend scan: flag any function whose physical span >200 LOC.
Usage: cq_scan_backend.py [root1 root2 ...]  (default: backend)
Exit 1 if any offender, 0 if clean. Definition: end_lineno - lineno + 1 (decorators excluded,
matching Python's FunctionDef.lineno)."""
import ast, os, sys

LIMIT = 200

def scan(roots):
    rows = []
    for root in roots:
        for dp, _, files in os.walk(root):
            if "__pycache__" in dp:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dp, fn)
                try:
                    with open(p, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read())
                except Exception as e:
                    # Make an undercount visible rather than silent during active refactoring.
                    print(f"SKIP (parse error): {p}: {e}", file=sys.stderr)
                    continue
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        loc = (n.end_lineno or n.lineno) - n.lineno + 1
                        if loc > LIMIT:
                            rows.append((loc, p, n.name))
    return sorted(rows, reverse=True)

if __name__ == "__main__":
    roots = sys.argv[1:] or ["backend"]
    rows = scan(roots)
    for loc, p, name in rows:
        print(f"{loc:5d}  {p}::{name}")
    print(f"\n{len(rows)} functions >{LIMIT} LOC", file=sys.stderr)
    sys.exit(1 if rows else 0)
