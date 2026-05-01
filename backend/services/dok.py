"""Shared DOK (Webb's Depth of Knowledge) helpers.

Phase 4.3 Sprint 2: extracted from student_portal_routes.py so both
grading_service.py and the route module can import without circular
deps. Owns the int-1..4 enum, validation/coercion, and uniform-DOK
derivation across a question list.

Spec: docs/superpowers/specs/2026-04-30-phase4.2-dok-control-design.md
       docs/superpowers/specs/2026-05-01-phase4.3-sprint2-per-dok-mastery-design.md
"""

DOK_OPTIONS = (1, 2, 3, 4)
REMEDIATION_DOK_DEFAULT = None  # None = "Auto" (no DOK directive in prompt)
DOK_DESCRIPTIONS = {
    1: "Recall & Reproduction — facts, terms, simple procedures.",
    2: "Skills & Concepts — compare, organize, explain relationships, apply concepts.",
    3: "Strategic Thinking — analyze with evidence, justify reasoning, multi-step decisions.",
    4: "Extended Thinking — synthesize across sources, design solutions, sustained investigation.",
}


def _validate_dok(value):
    """Normalize a stored/incoming DOK value to int in DOK_OPTIONS or None.

    Phase 4.3 Sprint 1 (Codex MINOR): legacy storage and AI output drift can
    produce string DOKs ("3") instead of ints (3). Normalize on read so the
    frontend predicate stays simple. Bools must be rejected explicitly
    because bool is an int subclass, so ``isinstance(True, int)`` is True.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value in DOK_OPTIONS else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            as_int = int(stripped)
        except ValueError:
            return None
        return as_int if as_int in DOK_OPTIONS else None
    return None


def _derive_uniform_dok(content):
    """Return the uniform DOK from content.questions when all share one
    valid level (1..4), else None.

    Phase 4.3 Sprint 1: Gradebook + SubmissionDetail header derive a single
    DOK badge for remediation rows from the source content. Only emits a
    value when EVERY question contributes a valid DOK and they all agree —
    mixed DOK or any missing/invalid value collapses to None (no badge).
    """
    if not isinstance(content, dict):
        return None
    questions = content.get('questions')
    if not isinstance(questions, list) or not questions:
        return None
    dok_values = []
    for q in questions:
        if not isinstance(q, dict):
            return None
        normalized = _validate_dok(q.get('dok'))
        if normalized is None:
            return None
        dok_values.append(normalized)
    first = dok_values[0]
    return first if all(d == first for d in dok_values) else None
