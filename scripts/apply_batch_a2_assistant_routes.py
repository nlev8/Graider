"""Apply Batch A.2 file 1 manual categorizations for
backend/routes/assistant_routes.py (45 rows).

Codex Gate 1 locked shape rules for this file:
  - tool-dispatch `except + print + continue` => LEGACY
  - SSE `catch + error event + clean close` => INTENTIONAL only if
    no hidden state mutation / data-loss path
  - Conversation persistence that can half-write on tool failure:
    blind spot, lean toward LEGACY
  - Exceptions converted into assistant text vs distinct system error
    surface: blind spot, lean toward LEGACY
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # ── Module-level import fallbacks (bootstrap carveout) ─────────────
    ("backend/routes/assistant_routes.py", 27, "INTENTIONAL", "ImportError → anthropic=None; explicit stub, degraded mode defined (runtime provider check)"),
    ("backend/routes/assistant_routes.py", 32, "INTENTIONAL", "ImportError → openai_pkg=None; same pattern"),
    ("backend/routes/assistant_routes.py", 37, "INTENTIONAL", "ImportError → genai_pkg=None; same pattern"),
    ("backend/routes/assistant_routes.py", 50, "INTENTIONAL", "ImportError → storage_load=None; bootstrap fallback"),
    ("backend/routes/assistant_routes.py", 53, "INTENTIONAL", "ImportError inner fallback; same pattern"),

    # ── _get_assistant_model ───────────────────────────────────────────
    ("backend/routes/assistant_routes.py", 90, "INTENTIONAL", "settings parse fail → return DEFAULT_MODEL; explicit typed fallback"),

    # ── _persist_conversation / _load_conversation ─────────────────────
    ("backend/routes/assistant_routes.py", 234, "LEGACY", "conversation persist fail → log.warning only; per Codex blind spot: conversation state can half-write, silent loss of session history"),
    ("backend/routes/assistant_routes.py", 246, "INTENTIONAL", "conversation load fail → return None; caller starts fresh session; defined degraded mode"),

    # ── _load_user_manual ──────────────────────────────────────────────
    ("backend/routes/assistant_routes.py", 289, "INTENTIONAL", "user manual read fail → cache=''; assistant works without Graider help docs; defined degraded mode"),

    # ── _extract_text_from_pdf / _docx (typed fallbacks) ───────────────
    ("backend/routes/assistant_routes.py", 304, "INTENTIONAL", "ImportError → return typed error string; defined degraded mode with user-visible error"),
    ("backend/routes/assistant_routes.py", 306, "INTENTIONAL", "Exception on PDF parse → return typed error string; same"),
    ("backend/routes/assistant_routes.py", 334, "INTENTIONAL", "ImportError → typed error string; defined degraded mode"),
    ("backend/routes/assistant_routes.py", 336, "INTENTIONAL", "Exception on DOCX parse → typed error string"),

    # ── Prompt enrichment loaders (all have defined fallbacks) ─────────
    ("backend/routes/assistant_routes.py", 402, "INTENTIONAL", "period differentiation read fail → empty dict; standard-level grading continues"),
    ("backend/routes/assistant_routes.py", 423, "INTENTIONAL", "accommodation summary read fail → None; optional system-prompt enrichment"),
    ("backend/routes/assistant_routes.py", 449, "INTENTIONAL", "per-file meta.json parse fail in loop → continue with next file"),
    ("backend/routes/assistant_routes.py", 458, "INTENTIONAL", "outer catch for _load_resource_names → return partial list; best-effort listing"),
    ("backend/routes/assistant_routes.py", 494, "INTENTIONAL", "per-file meta.json parse in _load_resource_content → skip meta, still load content"),
    ("backend/routes/assistant_routes.py", 511, "INTENTIONAL", "per-document content extract fail → continue to next doc"),
    ("backend/routes/assistant_routes.py", 533, "INTENTIONAL", "outer catch _load_resource_content → return ''; optional enrichment"),
    ("backend/routes/assistant_routes.py", 545, "INTENTIONAL", "rubric read fail → None; optional system-prompt injection"),
    ("backend/routes/assistant_routes.py", 576, "INTENTIONAL", "assessment templates parse → return empty list; optional"),
    ("backend/routes/assistant_routes.py", 599, "INTENTIONAL", "global settings read → fallback to default output_folder; analytics still tries the default path"),
    ("backend/routes/assistant_routes.py", 630, "INTENTIONAL", "(ValueError, TypeError) on float parse in per-row CSV → continue; typed"),
    ("backend/routes/assistant_routes.py", 712, "INTENTIONAL", "outer analytics-snapshot catch → return ''; optional enrichment, defined degraded mode (prompt just skips the section)"),
    ("backend/routes/assistant_routes.py", 744, "INTENTIONAL", "settings read fail → empty teacher context; defined degraded mode"),
    ("backend/routes/assistant_routes.py", 969, "INTENTIONAL", "memory file read fail → skip memory block; optional enrichment"),

    # ── _audit_log ─────────────────────────────────────────────────────
    ("backend/routes/assistant_routes.py", 1062, "LEGACY", "FERPA audit log append fail → pass; same class as app.py:246 (audit domain, mirror LEGACY)"),

    # ── _record_assistant_cost ─────────────────────────────────────────
    ("backend/routes/assistant_routes.py", 1094, "INTENTIONAL", "(FileNotFoundError, json.JSONDecodeError) → zero-init data; typed fallback with explicit shape"),
    ("backend/routes/assistant_routes.py", 1127, "LEGACY", "cost tracking write fail → log.error only; this IS the sole persistence path for cost data; silent data loss"),

    # ── generate (SSE tool-loop streaming) ─────────────────────────────
    ("backend/routes/assistant_routes.py", 1393, "INTENTIONAL", "voice settings read fail → voice_choice=None; TTS uses default voice"),
    ("backend/routes/assistant_routes.py", 1409, "INTENTIONAL", "voice mode init fail → log.warning + tts_stream=None; defined degraded mode (text-only response)"),
    ("backend/routes/assistant_routes.py", 1424, "INTENTIONAL", "queue.Empty → break; typed expected in polling loop"),
    ("backend/routes/assistant_routes.py", 1498, "INTENTIONAL", "Anthropic token count read → pass; cost tracking best-effort, not critical"),
    ("backend/routes/assistant_routes.py", 1647, "LEGACY", "Gemini function-call extraction swallow → tool call may be lost silently; per Codex blind spot: tool-dispatch exception in streaming loop"),
    ("backend/routes/assistant_routes.py", 1655, "INTENTIONAL", "Gemini token usage read → pass; cost tracking best-effort"),
    ("backend/routes/assistant_routes.py", 1712, "INTENTIONAL", "json.JSONDecodeError on tool input → tool_input={}; typed fallback, no partial side effects before parse"),
    ("backend/routes/assistant_routes.py", 1796, "INTENTIONAL", "pending_payload file read → pass; optional enrichment of SSE event"),
    ("backend/routes/assistant_routes.py", 1814, "INTENTIONAL", "outer tool-loop catch → SSE error event + clean break; Codex rule: catch+terminal error event+clean close passes"),
    ("backend/routes/assistant_routes.py", 1844, "INTENTIONAL", "queue.Empty → break; typed expected in final audio drain"),

    # ── Public route handlers ──────────────────────────────────────────
    ("backend/routes/assistant_routes.py", 1930, "INTENTIONAL", "(FileNotFoundError, json.JSONDecodeError) → return zero-cost shape; typed explicit default for first-time user"),
    ("backend/routes/assistant_routes.py", 1964, "LEGACY", "GET /api/assistant/memory: corrupt memory file → return [] silently; public-path silent success per Codex rule"),
    ("backend/routes/assistant_routes.py", 2039, "LEGACY", "GET /api/assistant/credentials: corrupt creds file → return configured=False; caller can't distinguish corruption from missing"),
    ("backend/routes/assistant_routes.py", 2067, "INTENTIONAL", "load_portal_credentials helper (internal, not public route) → return (None,None); caller checks and handles"),
    ("backend/routes/assistant_routes.py", 2100, "INTENTIONAL", "GET /api/assistant/voice-config: settings read fail → fallback to explicit default voice 'nova'; response shape preserved"),
]


ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()
    dmap = {(f, line): cat for (f, line, cat, _) in DECISIONS}
    applied = 0
    mismatches = []
    not_found = list(dmap.keys())

    for i, line_text in enumerate(lines):
        m = ROW_RE.match(line_text)
        if not m:
            continue
        key = (m.group("file"), int(m.group("line")))
        if key not in dmap:
            continue
        if m.group("cat") != "UNCATEGORIZED":
            mismatches.append((key, m.group("cat"), dmap[key]))
            not_found.remove(key)
            continue
        lines[i] = line_text.rsplit("|", 2)[0] + f"| {dmap[key]} |"
        applied += 1
        not_found.remove(key)

    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Applied {applied}/{len(DECISIONS)}", file=sys.stderr)
    if mismatches:
        print(f"\nSkipped (already categorized): {len(mismatches)}", file=sys.stderr)
        for k, existing, intended in mismatches:
            print(f"  {k}: was {existing}, would have been {intended}", file=sys.stderr)
    if not_found:
        print(f"\nNOT FOUND: {len(not_found)}", file=sys.stderr)
        for k in not_found:
            print(f"  {k}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
