#!/usr/bin/env python3
"""CQ level-8 backend scan: flag any function whose physical span >200 LOC.
Usage: cq_scan_backend.py [root1 root2 ...]  (default: <repo>/backend)
Definition: end_lineno - lineno + 1 (decorators excluded, matching Python's FunctionDef.lineno).

Exit codes (this is a measurement GATE — it FAILS CLOSED so an incomplete scan can never be
mistaken for a clean one):
  0 = scan complete AND zero functions >200 LOC
  1 = one or more functions >200 LOC
  2 = scan INCOMPLETE (a file failed to parse, or a root was missing) — NOT certified clean
"""
import ast, os, sys

LIMIT = 200

def scan(roots):
    rows = []
    skipped = []  # (path, reason) — any entry means the scan is incomplete → fail closed
    for root in roots:
        if not os.path.isdir(root):
            skipped.append((root, "root does not exist"))
            continue
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
                    skipped.append((p, str(e)))
                    continue
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        loc = (n.end_lineno or n.lineno) - n.lineno + 1
                        if loc > LIMIT:
                            rows.append((loc, p, n.name))
    return sorted(rows, reverse=True), skipped

if __name__ == "__main__":
    # Default root anchored to the script location, NOT cwd, so a wrong cwd can't undercount.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots = sys.argv[1:] or [os.path.join(repo_root, "backend")]
    rows, skipped = scan(roots)
    for loc, p, name in rows:
        print(f"{loc:5d}  {p}::{name}")
    print(f"\n{len(rows)} functions >{LIMIT} LOC", file=sys.stderr)
    for path, reason in skipped:
        print(f"SKIP (incomplete scan): {path}: {reason}", file=sys.stderr)
    if rows:
        sys.exit(1)
    if skipped:
        # Clean of offenders but the scan was incomplete — refuse to certify.
        print(f"INCOMPLETE: {len(skipped)} file(s)/root(s) unscanned — not certified clean.",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(0)
