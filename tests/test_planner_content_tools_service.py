"""Direct-import tests for backend/services/planner_content_tools.py (Wave 6 Slice 7)."""
import json
from unittest.mock import patch, MagicMock


def _completion(text):
    c = MagicMock()
    c.content_parts = [MagicMock(text=text)]
    c.usage = None
    return c


def test_adjust_reading_level_content_returns_parsed_dict():
    from backend.services.planner_content_tools import adjust_reading_level_content
    payload = json.dumps({"adjusted_text": "Simple text.", "reading_level_estimate": "4.0",
                          "vocabulary_changes": [{"original": "complex", "replacement": "hard"}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(payload)
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = adjust_reading_level_content(
            text="Complex prose.", target_level="4", subject="ELA",
            preserve_terms=["photosynthesis"], api_key="k",
        )
    assert out["adjusted_text"] == "Simple text."
    assert out["reading_level_estimate"] == "4.0"
    assert out["usage"] is None  # mock completion had usage=None


def test_adjust_reading_level_content_preserve_terms_in_prompt():
    # The preserve_terms must reach the prompt (verify via the captured LLMRequest).
    from backend.services.planner_content_tools import adjust_reading_level_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion('{"adjusted_text": "x"}')
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        adjust_reading_level_content(text="t", target_level="5", subject="",
                                     preserve_terms=["mitochondria"], api_key="k")
    sent = fake_adapter.chat.call_args[0][0]  # the LLMRequest
    prompt_text = sent.messages[0].content[0].text
    assert "mitochondria" in prompt_text
