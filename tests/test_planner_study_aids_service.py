"""Direct-import tests for backend/services/planner_study_aids.py (Wave 6 Slice 3).

The endpoints are characterized by tests/test_study_guide.py + tests/test_flashcards.py
(which mock genai). These pin the service functions' contract directly: build the
prompt, call Gemini (mocked), parse, and return the dict — callable Flask-free.
"""
import json
from unittest.mock import patch, MagicMock


def _mock_genai_response(text):
    resp = MagicMock()
    resp.text = text
    resp.candidates = [MagicMock(finish_reason=MagicMock(name="STOP"))]
    resp.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=200)
    return resp


def test_generate_study_guide_content_returns_parsed_dict():
    from backend.services.planner_study_aids import generate_study_guide_content
    payload = json.dumps({"title": "Cells", "sections": [{"heading": "Key Concepts", "content": ["Cells are units of life."]}]})
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = _mock_genai_response(payload)
        out = generate_study_guide_content(
            content="Cells are the basic unit of life.", subject="Bio",
            grade="7", instructions="", global_ai_notes="", lesson_plan=None, user_id="t1",
        )
    assert out["title"] == "Cells"
    assert out["sections"][0]["heading"] == "Key Concepts"


def test_generate_study_guide_content_strips_code_fences():
    from backend.services.planner_study_aids import generate_study_guide_content
    fenced = "```json\n" + json.dumps({"title": "X", "sections": []}) + "\n```"
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = _mock_genai_response(fenced)
        out = generate_study_guide_content(
            content="x", subject="", grade="", instructions="",
            global_ai_notes="", lesson_plan=None, user_id="t1",
        )
    assert out == {"title": "X", "sections": []}  # fences stripped, parsed


def test_generate_flashcards_content_returns_parsed_dict():
    from backend.services.planner_study_aids import generate_flashcards_content
    payload = json.dumps({"title": "Vocab", "cards": [{"term": "cell", "definition": "unit of life"}]})
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = _mock_genai_response(payload)
        out = generate_flashcards_content(
            content="cells", subject="Bio", grade="7", instructions="",
            global_ai_notes="", lesson_plan=None, card_count=10, user_id="t1",
        )
    assert out["cards"][0]["term"] == "cell"


def test_generate_flashcards_content_raises_on_bad_json():
    from backend.services.planner_study_aids import generate_flashcards_content
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.gemini_adapter.genai') as mock_genai:
        mock_genai.Client.return_value.models.generate_content.return_value = _mock_genai_response("not json at all")
        try:
            generate_flashcards_content(
                content="x", subject="", grade="", instructions="",
                global_ai_notes="", lesson_plan=None, card_count=5, user_id="t1",
            )
            assert False, "expected JSONDecodeError"
        except json.JSONDecodeError:
            pass  # route translates this to a 500 — contract preserved


# ── generate_slides_payload (Wave 6 Slice 6) ──

def test_generate_slides_payload_returns_shape():
    from backend.services.planner_study_aids import generate_slides_payload
    sd = {"title": "Cells", "theme": {}, "slides": [{"h": 1}, {"h": 2}]}
    with patch('backend.api_keys.get_api_key', return_value='k'), \
         patch('backend.services.slide_generator.generate_slide_content', return_value=dict(sd)), \
         patch('backend.services.slide_generator.generate_slide_images', return_value={0: b"x"}):
        out = generate_slides_payload(
            content="cells", title="Cells", subject="Bio", grade="7", instructions="",
            global_ai_notes="", lesson_plan=None, slide_count=10, max_images=5,
            generate_images=True, deck_format="detailed", user_id="t1",
        )
    assert out["title"] == "Cells"
    assert out["slide_count"] == 2
    assert out["images_generated"] == 1
