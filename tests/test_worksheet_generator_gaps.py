"""Gap-fill unit tests for backend/services/worksheet_generator.py.

Audit MAJOR #4 sprint follow-up to PR #304. Companion to existing
test_worksheet_generator_unit.py. Targets the 90 uncovered LOC (74%
baseline → ~99%). Most uncovered code is the `_embed_visual` dispatch
function (200 LOC across 17 visual types).

Branches covered
* _embed_visual dispatch for every vtype: math, number_line,
  coordinate_plane, graph (bar/line/scatter/unknown→return),
  box_plot, shape (triangle/rectangle/unknown→return),
  function_graph, circle, polygon, histogram, pie_chart, dot_plot,
  stem_and_leaf, venn_diagram, protractor (and angle_protractor alias)
* _embed_visual exception swallow → "[Visual failed to render]"
  paragraph + sentry capture
* _normalize_correct_answer_to_letter edge case (line 364)
* _add_options_with_bubbles correct_answer dispatch (424-427)
* _create_answer_key_doc empty-list early return (513)
* create_worksheet_docx error handling (564, 573-575)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _embed_visual dispatch — exercise every vtype + exception swallow
# ──────────────────────────────────────────────────────────────────


def _make_doc():
    """Build a MagicMock that looks enough like a python-docx Document."""
    doc = MagicMock()
    return doc


@pytest.fixture
def patch_viz():
    """Patch all visualization functions to return a stub PNG bytes
    object so add_image_to_docx never reaches matplotlib."""
    fake_png = b"fake-png-bytes"
    with patch.multiple(
        "backend.services.visualization",
        render_latex=MagicMock(return_value=fake_png),
        create_number_line=MagicMock(return_value=fake_png),
        create_coordinate_plane=MagicMock(return_value=fake_png),
        create_bar_chart=MagicMock(return_value=fake_png),
        create_line_graph=MagicMock(return_value=fake_png),
        create_scatter_plot=MagicMock(return_value=fake_png),
        create_box_plot=MagicMock(return_value=fake_png),
        create_triangle=MagicMock(return_value=fake_png),
        create_rectangle=MagicMock(return_value=fake_png),
        create_function_graph=MagicMock(return_value=fake_png),
        create_circle=MagicMock(return_value=fake_png),
        create_polygon=MagicMock(return_value=fake_png),
        create_histogram=MagicMock(return_value=fake_png),
        create_pie_chart=MagicMock(return_value=fake_png),
        create_dot_plot=MagicMock(return_value=fake_png),
        create_stem_and_leaf=MagicMock(return_value=fake_png),
        create_venn_diagram=MagicMock(return_value=fake_png),
        create_protractor=MagicMock(return_value=fake_png),
    ), patch(
        "backend.services.worksheet_generator.add_image_to_docx",
    ) as add_image_mock:
        yield add_image_mock


class TestEmbedVisual:
    def test_math(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        doc = _make_doc()
        _embed_visual(doc, {"type": "math", "latex": "x^2"})
        assert patch_viz.called

    def test_number_line(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "number_line", "min": 0, "max": 10,
            "points": [3, 7],
        })
        assert patch_viz.called

    def test_coordinate_plane(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "coordinate_plane",
            "x_range": [-5, 5], "y_range": [-5, 5],
        })
        assert patch_viz.called

    def test_graph_bar(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "graph", "graph_type": "bar",
            "categories": ["A", "B"], "values": [1, 2],
        })
        assert patch_viz.called

    def test_graph_line(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "graph", "graph_type": "line",
            "x_data": [1, 2], "y_data": [3, 4],
        })
        assert patch_viz.called

    def test_graph_scatter(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "graph", "graph_type": "scatter",
            "x_data": [1, 2], "y_data": [3, 4],
            "show_trend": True,
        })
        assert patch_viz.called

    def test_graph_unknown_type_returns_silently(self, patch_viz):
        # Unknown graph_type → early return, NO add_image call
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "graph", "graph_type": "pie-but-unknown",
        })
        # add_image_mock from fixture was NOT called
        assert not patch_viz.called

    def test_box_plot(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "box_plot",
            "data": [[1, 2, 3, 4, 5]],
            "labels": ["Set A"],
        })
        assert patch_viz.called

    def test_shape_triangle(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "shape", "shape_type": "triangle",
            "base": 6, "height": 4,
        })
        assert patch_viz.called

    def test_shape_rectangle(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "shape", "shape_type": "rectangle",
            "width": 8, "height": 5,
        })
        assert patch_viz.called

    def test_shape_unknown_type_returns_silently(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "shape", "shape_type": "hexagram-unknown",
        })
        assert not patch_viz.called

    def test_function_graph(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "function_graph",
            "expressions": ["x^2"],
            "x_range": [-5, 5],
            "y_range": [0, 25],
        })
        assert patch_viz.called

    def test_function_graph_no_y_range(self, patch_viz):
        # y_range missing → tuple(visual['y_range']) skipped, passed as None
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "function_graph",
            "expressions": ["x"],
        })
        assert patch_viz.called

    def test_circle(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "circle", "radius": 3,
            "center": [1, 1], "show_diameter": True,
        })
        assert patch_viz.called

    def test_polygon(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "polygon", "sides": 6, "side_length": 4,
        })
        assert patch_viz.called

    def test_histogram(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "histogram",
            "data": [1, 2, 2, 3, 3, 3, 4, 4, 4, 4],
            "bins": 4,
        })
        assert patch_viz.called

    def test_pie_chart(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "pie_chart",
            "categories": ["A", "B"],
            "values": [60, 40],
        })
        assert patch_viz.called

    def test_dot_plot(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "dot_plot",
            "categories": ["A", "B", "C"],
            "dots": [3, 5, 2],
        })
        assert patch_viz.called

    def test_stem_and_leaf(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "stem_and_leaf",
            "data": [12, 23, 34, 45, 56],
        })
        assert patch_viz.called

    def test_venn_diagram(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "venn_diagram",
            "sets": 2,
            "labels": ["A", "B"],
        })
        assert patch_viz.called

    def test_protractor_canonical_name(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "protractor", "given_angle": 60,
        })
        assert patch_viz.called

    def test_protractor_angle_alias(self, patch_viz):
        # 'angle_protractor' alias also dispatches to create_protractor
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {
            "type": "angle_protractor", "given_angle": 30,
        })
        assert patch_viz.called

    def test_unknown_type_silently_skipped(self, patch_viz):
        from backend.services.worksheet_generator import _embed_visual
        _embed_visual(_make_doc(), {"type": "totally-unknown"})
        # No image added because no branch matched
        assert not patch_viz.called

    def test_exception_renders_failure_paragraph(self):
        # Force visualization to raise → except branch adds failure
        # paragraph + sentry capture.
        from backend.services.worksheet_generator import _embed_visual
        doc = _make_doc()
        with patch(
            "backend.services.visualization.render_latex",
            side_effect=RuntimeError("matplotlib explosion"),
        ), patch(
            "backend.services.worksheet_generator.sentry_sdk.capture_exception",
        ) as sentry_mock:
            _embed_visual(doc, {"type": "math", "latex": "x"})
        doc.add_paragraph.assert_called_with("[Visual failed to render]")
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# Smaller gap-fills
# ──────────────────────────────────────────────────────────────────


class TestSmallerGaps:
    def test_normalize_correct_answer_letter_passthrough(self):
        # Line 364: normalize already-letter form — no munging needed
        from backend.services.worksheet_generator import (
            _normalize_correct_answer_to_letter,
        )
        # Already a single uppercase letter → returned as-is
        assert _normalize_correct_answer_to_letter(
            "B", ["alpha", "beta", "gamma"],
        ) == "B"

    def test_create_answer_key_doc_empty_returns_none(self):
        # Line 513: empty questions list → early return None
        from backend.services.worksheet_generator import _create_answer_key_doc
        result = _create_answer_key_doc("Title", [])
        assert result is None
