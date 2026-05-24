"""Content tools for the planner (reading-level adjustment, etc.).

Wave 6 Slice 7 - extracted from backend/routes/planner_routes.py
(behavior-preserving). Flask-free: the route reads request data + g.user_id +
the OpenAI key and passes them in; this builds the prompt, calls the adapter,
parses, and returns the result dict (raising on error, which the route maps to
a 500). No service->route imports.
"""
import json

from backend.services.assignment_post_processing import _extract_usage, _record_planner_cost


def adjust_reading_level_content(*, text, target_level, subject, preserve_terms, api_key):
    """Rewrite `text` at the target Flesch-Kincaid level; return
    {adjusted_text, reading_level_estimate, vocabulary_changes, usage}.
    """
    preserve_instruction = ""
    if preserve_terms:
        preserve_instruction = (
            "\n\nIMPORTANT: The following key terms MUST be preserved exactly as-is "
            "(do NOT simplify or replace them): " + ", ".join(preserve_terms)
        )

    subject_context = ""
    if subject:
        subject_context = f" This is {subject} content, so maintain subject-specific accuracy."

    prompt = f"""Rewrite the following text at a Flesch-Kincaid grade level of {target_level}.{subject_context}

Rules:
- Simplify vocabulary and sentence structure to match the target reading level
- Maintain ALL factual content — do not remove or alter any information
- Keep the same overall structure (paragraphs, lists, etc.)
- Preserve proper nouns, names, and dates exactly{preserve_instruction}

Respond with a JSON object containing:
- "adjusted_text": the rewritten text
- "reading_level_estimate": estimated Flesch-Kincaid grade level of the output (as a string like "6.2")
- "vocabulary_changes": array of objects with "original" and "replacement" keys showing significant word substitutions made (max 15 entries)

TEXT TO REWRITE:
{text}"""


    from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, ResponseFormat, TextPart
    adapter = OpenAIAdapter(api_key=api_key)
    completion = adapter.chat(LLMRequest(
        model="gpt-4o",
        system_prompt="You are a reading level adjustment specialist. Rewrite text at the requested grade level while preserving meaning and key terms. Always respond with valid JSON.",
        messages=[Message(role="user", content=[TextPart(text=prompt)])],
        response_format=ResponseFormat(type="json_object"),
        temperature=0.3,
        metadata={"feature_label": "adjust_reading_level"},
    ))

    usage = _extract_usage(completion, "gpt-4o")
    _record_planner_cost(usage)

    raw = completion.content_parts[0].text if completion.content_parts else "{}"
    result = json.loads(raw)
    return {
        "adjusted_text": result.get("adjusted_text", ""),
        "reading_level_estimate": result.get("reading_level_estimate", ""),
        "vocabulary_changes": result.get("vocabulary_changes", []),
        "usage": usage,
    }
