"""AI study-aid generation for the planner (Gemini Flash).

Wave 6 Slice 3 - extracted from backend/routes/planner_routes.py
(behavior-preserving). Flask-free: the route reads request data + g.user_id and
passes them in; these functions build the prompt, call the Gemini adapter, parse
the JSON, and return the result dict (raising json.JSONDecodeError on bad JSON,
which the route translates to a 500 — same as before). No service->route imports.
"""
import json
import logging

_logger = logging.getLogger(__name__)


def generate_study_guide_content(*, content, subject, grade, instructions,
                                 global_ai_notes, lesson_plan, user_id):
    """Build the prompt, call Gemini, parse + return the study_guide dict."""
    prompt_parts = []
    prompt_parts.append(f"You are an expert {subject} teacher creating a study guide for grade {grade} students.")

    if global_ai_notes:
        prompt_parts.append("")
        prompt_parts.append("=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===")
        prompt_parts.append(global_ai_notes)
        prompt_parts.append("=== END TEACHER INSTRUCTIONS ===")
    prompt_parts.append("")
    prompt_parts.append("Generate a comprehensive study guide in JSON format with these sections:")
    prompt_parts.append('- "title": string')
    prompt_parts.append('- "sections": array of objects, each with:')
    prompt_parts.append('  - "heading": string (section name)')
    prompt_parts.append('  - "content": array of strings (bullet points) — for Key Concepts, Summary')
    prompt_parts.append('  - "terms": array of {"term": string, "definition": string} — for Vocabulary section')
    prompt_parts.append('  - "questions": array of {"question": string, "answer": string} — for Review Questions')
    prompt_parts.append("")
    prompt_parts.append("Include these sections in order:")
    prompt_parts.append("1. Key Concepts — main ideas students should understand")
    prompt_parts.append("2. Vocabulary — important terms with definitions")
    prompt_parts.append("3. Review Questions — 5-8 questions with answers to help students self-test")
    prompt_parts.append("4. Summary — concise recap of the material")
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON. No markdown, no code fences, no extra text.")

    if lesson_plan:
        prompt_parts.append("")
        prompt_parts.append("=== LESSON PLAN ===")
        prompt_parts.append(f"Title: {lesson_plan.get('title', '')}")
        if lesson_plan.get('overview'):
            prompt_parts.append(f"Overview: {lesson_plan['overview']}")
        if lesson_plan.get('objectives'):
            prompt_parts.append("Objectives:")
            for obj in lesson_plan['objectives']:
                prompt_parts.append(f"  - {obj}")
        if lesson_plan.get('vocabulary'):
            prompt_parts.append("Vocabulary: " + ", ".join(lesson_plan['vocabulary']))
        if lesson_plan.get('days'):
            for day in lesson_plan['days']:
                prompt_parts.append(f"Day {day.get('day', '?')}: {day.get('topic', '')}")
        prompt_parts.append("=== END LESSON PLAN ===")

    if content:
        prompt_parts.append("")
        prompt_parts.append("=== SOURCE CONTENT ===")
        prompt_parts.append(content[:8000])
        prompt_parts.append("=== END SOURCE CONTENT ===")

    if instructions:
        prompt_parts.append("")
        prompt_parts.append(f"Additional instructions: {instructions}")

    prompt = "\n".join(prompt_parts)

    from backend.api_keys import get_api_key as _gak
    from backend.services.llm_adapter import GeminiAdapter, LLMRequest, Message, TextPart
    adapter = GeminiAdapter(api_key=_gak('gemini', user_id))
    response = adapter.chat(LLMRequest(
        model="gemini-2.5-flash",
        messages=[Message(role="user", content=[TextPart(text=prompt)])],
        metadata={"feature_label": "generate_study_guide"},
    ))

    response_text = (response.content_parts[0].text if response.content_parts else "").strip()
    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()
    if response_text.startswith("json"):
        response_text = response_text[4:].strip()

    study_guide = json.loads(response_text)
    return study_guide


def generate_flashcards_content(*, content, subject, grade, instructions,
                                global_ai_notes, lesson_plan, card_count, user_id):
    """Build the prompt, call Gemini, parse + return the flashcards dict."""
    prompt_parts = []
    prompt_parts.append("You are an expert " + subject + " teacher creating flashcards for grade " + grade + " students.")

    if global_ai_notes:
        prompt_parts.append("")
        prompt_parts.append("=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===")
        prompt_parts.append(global_ai_notes)
        prompt_parts.append("=== END TEACHER INSTRUCTIONS ===")

    prompt_parts.append("")
    prompt_parts.append("Generate " + str(card_count) + " flashcards in JSON format:")
    prompt_parts.append('- "title": string (flashcard set title)')
    prompt_parts.append('- "cards": array of {"term": string, "definition": string}')
    prompt_parts.append("")
    prompt_parts.append("Guidelines:")
    prompt_parts.append("- Each term should be a key vocabulary word, concept, person, or event")
    prompt_parts.append("- Each definition should be concise (1-2 sentences max)")
    prompt_parts.append("- Use age-appropriate language for grade " + grade)
    prompt_parts.append("- Focus on the most important terms from the source material")
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON. No markdown, no code fences, no extra text.")

    if lesson_plan:
        prompt_parts.append("")
        prompt_parts.append("=== LESSON PLAN ===")
        prompt_parts.append("Title: " + (lesson_plan.get('title', '') or ''))
        if lesson_plan.get('overview'):
            prompt_parts.append("Overview: " + lesson_plan['overview'])
        if lesson_plan.get('vocabulary'):
            prompt_parts.append("Key Vocabulary: " + ", ".join(lesson_plan['vocabulary']))
        if lesson_plan.get('objectives'):
            prompt_parts.append("Objectives:")
            for obj in lesson_plan['objectives']:
                prompt_parts.append("  - " + obj)
        prompt_parts.append("=== END LESSON PLAN ===")

    if content:
        prompt_parts.append("")
        prompt_parts.append("=== SOURCE CONTENT ===")
        prompt_parts.append(content[:8000])
        prompt_parts.append("=== END SOURCE CONTENT ===")

    if instructions:
        prompt_parts.append("")
        prompt_parts.append("Additional instructions: " + instructions)

    prompt = "\n".join(prompt_parts)

    from backend.api_keys import get_api_key as _gak
    from backend.services.llm_adapter import GeminiAdapter, LLMRequest, Message, TextPart
    adapter = GeminiAdapter(api_key=_gak('gemini', user_id))
    response = adapter.chat(LLMRequest(
        model="gemini-2.5-flash",
        messages=[Message(role="user", content=[TextPart(text=prompt)])],
        metadata={"feature_label": "generate_flashcards"},
    ))

    response_text = (response.content_parts[0].text if response.content_parts else "").strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1] if "\n" in response_text else response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3].strip()
    if response_text.startswith("json"):
        response_text = response_text[4:].strip()

    flashcards = json.loads(response_text)
    return flashcards


def generate_slides_payload(*, content, title, subject, grade, instructions,
                            global_ai_notes, lesson_plan, slide_count, max_images,
                            generate_images, deck_format, user_id):
    """Generate the slide-deck payload (content via slide_generator + optional
    images). Returns {slides, title, slide_count, images_generated}. Flask-free;
    the route keeps request parse + the 400 guard + jsonify/except.
    """
    from backend.api_keys import get_api_key as _gak
    api_key = _gak('gemini', user_id)

    from backend.services.slide_generator import (
        generate_slide_content, generate_slide_images
    )

    # Phase 1: Generate slide content
    slide_data = generate_slide_content(
        content=content, subject=subject, grade=grade, title=title,
        api_key=api_key, lesson_plan=lesson_plan,
        global_ai_notes=global_ai_notes, instructions=instructions,
        slide_count=slide_count,
        deck_format=deck_format,
    )

    # Phase 2: Generate images (optional)
    images_generated = 0
    if generate_images:
        try:
            images = generate_slide_images(
                slide_data["slides"], slide_data["theme"],
                api_key=api_key, max_images=max_images,
            )
            images_generated = len(images)
            # Store image references in session for export
            # (images are too large for JSON response)
            import base64
            slide_data["_image_data"] = {
                str(k): base64.b64encode(v).decode('ascii') for k, v in images.items()
            }
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            _logger.warning("Image generation failed, continuing without images: %s", e)
            slide_data["_image_data"] = {}

    return {
        "slides": slide_data,
        "title": slide_data.get("title", title),
        "slide_count": len(slide_data.get("slides", [])),
        "images_generated": images_generated,
    }
