<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This repo is indexed by GitNexus; use the `mcp__gitnexus__*` tools to navigate
and assess impact. Full tool reference + per-task guides: `.claude/skills/gitnexus/`.

**Must:**
- `impact({target, direction:"upstream"})` before editing a symbol; warn on
  HIGH/CRITICAL. d=1 = will break.
- `detect_changes()` before committing (scope check).
- `rename({dry_run:true})` first — never find-and-replace.
- After committing the index goes stale; refresh with
  `npx gitnexus analyze --embeddings --skip-agents-md`
  (`--skip-agents-md` keeps this compact block; `--embeddings` preserves search).

When stuck: `query({query})` for flows, `context({name})` for a symbol's callers/callees.
<!-- gitnexus:end -->
