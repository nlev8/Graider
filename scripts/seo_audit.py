#!/usr/bin/env python3
"""Deterministic SEO/GEO health audit for the Graider landing site.

Run locally or in CI (see .github/workflows/seo-audit.yml). Validates the
on-page invariants that make us win brand-term search + AI answers and keep us
disambiguated from grAIder.de. Exits non-zero (and prints a findings list) on
any regression so CI can open/raise an issue. Stdlib only — no deps.

Usage: python scripts/seo_audit.py [landing_dir]   (default: ./landing)
"""
import json
import re
import sys
from pathlib import Path

LANDING = Path(sys.argv[1] if len(sys.argv) > 1 else "landing")

# AI crawlers that MUST be allowed for us to appear in AI answers.
REQUIRED_AI_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]
# Schema.org @types that must be present in the JSON-LD for entity grounding.
REQUIRED_SCHEMA_TYPES = ["WebSite", "SoftwareApplication", "Organization", "FAQPage"]

findings: list[str] = []


def fail(msg: str) -> None:
    findings.append(msg)


def _read(name: str) -> str | None:
    p = LANDING / name
    if not p.exists():
        fail(f"MISSING FILE: landing/{name}")
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def _iter_ld_json(html: str):
    for block in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    ):
        try:
            yield json.loads(block)
        except json.JSONDecodeError as e:
            fail(f"JSON-LD does not parse: {e}")


def _collect_types(node, out: set) -> None:
    if isinstance(node, dict):
        t = node.get("@type")
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, list):
            out.update(x for x in t if isinstance(x, str))
        for v in node.values():
            _collect_types(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_types(v, out)


def _find_org_sameas(node):
    """Return the sameAs list from the first Organization node found."""
    if isinstance(node, dict):
        t = node.get("@type")
        if t == "Organization" or (isinstance(t, list) and "Organization" in t):
            return node.get("sameAs")
        for v in node.values():
            r = _find_org_sameas(v)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = _find_org_sameas(v)
            if r is not None:
                return r
    return None


def audit_index() -> None:
    html = _read("index.html")
    if html is None:
        return

    if "<title>" not in html:
        fail("index.html: missing <title>")
    if 'name="description"' not in html:
        fail("index.html: missing meta description")
    if 'rel="canonical"' not in html:
        fail("index.html: missing canonical link")

    # Dead placeholder links erode crawl/quality signals. Anchors with an
    # onclick handler are functional JS controls (e.g. auth-modal toggles),
    # not dead links — only flag href="#" anchors that lack onclick.
    anchors = re.findall(r"<a\b[^>]*>", html)
    dead = [a for a in anchors if 'href="#"' in a and "onclick" not in a]
    if dead:
        fail(f'index.html: {len(dead)} dead placeholder link(s) (href="#" with no '
             f"onclick) — fill or remove")

    types_seen: set = set()
    org_sameas = None
    for doc in _iter_ld_json(html):
        _collect_types(doc, types_seen)
        if org_sameas is None:
            org_sameas = _find_org_sameas(doc)

    for t in REQUIRED_SCHEMA_TYPES:
        if t not in types_seen:
            fail(f"JSON-LD: missing required @type '{t}'")

    if not org_sameas:
        fail("JSON-LD: Organization.sameAs is empty — entity is not disambiguated "
             "from grAIder.de. Populate with official profile URLs.")


def audit_robots() -> None:
    txt = _read("robots.txt")
    if txt is None:
        return
    for bot in REQUIRED_AI_BOTS:
        if bot not in txt:
            fail(f"robots.txt: AI crawler '{bot}' not listed (should be Allow)")
    if "Sitemap:" not in txt:
        fail("robots.txt: no Sitemap directive")


def audit_assets() -> None:
    for name in ("llms.txt", "sitemap.xml"):
        _read(name)  # presence-checked inside _read


def main() -> int:
    if not LANDING.exists():
        print(f"FAIL: landing dir not found: {LANDING}")
        return 2
    audit_index()
    audit_robots()
    audit_assets()

    if findings:
        print(f"SEO/GEO audit FAILED — {len(findings)} finding(s):\n")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("SEO/GEO audit PASSED — all on-page invariants intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
