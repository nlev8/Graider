"""Pure OpenAI-context helper for the post-processing pipeline.

Wave 6 Slice 2 - extracted from planner_routes._get_openai_context to remove the
cross-route circular-import surface (student_portal_routes imported the route
helper directly). Flask-free: the caller reads g.user_id and passes it in.
"""


def build_openai_context(user_id):
    """Return the (user_id, client) tuple the post-processing pipeline expects.

    The client slot is intentionally None (kept for call-site compatibility;
    _auto_fix_flagged_questions builds its own LLM adapter internally).
    """
    return user_id, None
