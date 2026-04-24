"""Tests for LLMAdapter.generate_image (Phase 5c PR 1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pybreaker
import pytest


def test_generate_image_types_exported_from_package():
    """ImageRequest and ImageResponse must be importable from the package root."""
    from backend.services.llm_adapter import ImageRequest, ImageResponse
    assert ImageRequest is not None
    assert ImageResponse is not None


def test_llm_adapter_protocol_declares_generate_image():
    """Every concrete adapter class must implement generate_image() to satisfy
    the @runtime_checkable LLMAdapter protocol."""
    from backend.services.llm_adapter import LLMAdapter, OpenAIAdapter, AnthropicAdapter, GeminiAdapter

    for cls in (OpenAIAdapter, AnthropicAdapter, GeminiAdapter):
        assert hasattr(cls, "generate_image"), f"{cls.__name__} missing generate_image()"

    # Runtime-checkable protocol recognition — instances must match structurally.
    openai = OpenAIAdapter(api_key="test-key")
    assert isinstance(openai, LLMAdapter)
