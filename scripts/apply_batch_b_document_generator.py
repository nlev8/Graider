"""Apply Batch B file 4 for document_generator.py.

Codex Gate 1 rule for this file: style/visual-embed swallows that
still return status=created are LEGACY (silent partial-success), not
INTENTIONAL, even though caller wraps top-level errors in tool dict.
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # _hex_to_rgb
    ("backend/services/document_generator.py", 53,  "INTENTIONAL", "(ValueError, TypeError) → None; typed fallback for color parse"),

    # load_style
    ("backend/services/document_generator.py", 81,  "LEGACY", "Codex Gate 1: saved style merge swallow discards user overrides silently"),
    ("backend/services/document_generator.py", 91,  "INTENTIONAL", "(ValueError, TypeError) per-int-key → DEFAULT_STYLE[k] explicit fallback"),
    ("backend/services/document_generator.py", 97,  "INTENTIONAL", "(ValueError, TypeError) per-float-key → DEFAULT_STYLE[k] fallback"),
    ("backend/services/document_generator.py", 105, "INTENTIONAL", "(ValueError, TypeError) heading_sizes → explicit per-level default"),

    # create_document_docx — all 15 per-visual embed swallows
    ("backend/services/document_generator.py", 338, "LEGACY", "Codex Gate 1: LaTeX math image fail → [Math image generation failed] placeholder; doc still returned as status=created"),
    ("backend/services/document_generator.py", 353, "LEGACY", "number-line embed fail → placeholder paragraph; same class"),
    ("backend/services/document_generator.py", 368, "LEGACY", "coordinate-plane embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 409, "LEGACY", "graph embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 422, "LEGACY", "box-plot embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 447, "LEGACY", "shape embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 463, "LEGACY", "function-graph embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 479, "LEGACY", "circle embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 494, "LEGACY", "polygon embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 510, "LEGACY", "histogram embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 525, "LEGACY", "pie-chart embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 541, "LEGACY", "dot-plot embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 553, "LEGACY", "stem-and-leaf embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 567, "LEGACY", "venn diagram embed fail → placeholder; same"),
    ("backend/services/document_generator.py", 579, "LEGACY", "protractor embed fail → placeholder; same"),
]

ROW_RE = re.compile(r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| (?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$")


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()
    dmap = {(f, line): cat for (f, line, cat, _) in DECISIONS}
    applied = 0
    not_found = list(dmap.keys())
    for i, line_text in enumerate(lines):
        m = ROW_RE.match(line_text)
        if not m:
            continue
        key = (m.group("file"), int(m.group("line")))
        if key not in dmap or m.group("cat") != "UNCATEGORIZED":
            if key in dmap:
                not_found.remove(key)
            continue
        lines[i] = line_text.rsplit("|", 2)[0] + f"| {dmap[key]} |"
        applied += 1
        not_found.remove(key)
    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Applied {applied}/{len(DECISIONS)}", file=sys.stderr)
    if not_found:
        for k in not_found:
            print(f"NOT FOUND {k}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
