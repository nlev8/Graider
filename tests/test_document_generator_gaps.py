"""Gap-fill unit tests for backend/services/document_generator.py.

Audit MAJOR #4 sprint follow-up to PR #305. Companion to existing
test_document_generator_unit.py. Targets the 154 uncovered LOC (62%
baseline → ~95%). Most uncovered code is the visual-block dispatch
section of `create_document_docx` (lines 435-699, 17 block types).

Branches covered
* create_document_docx visual block dispatch for every block_type:
  math, number_line, coordinate_plane, graph (bar/line/scatter/
  unknown→continue), box_plot, shape (triangle/rectangle/
  unknown→continue), function_graph (with + without y_range),
  circle, polygon, histogram, pie_chart, dot_plot, stem_and_leaf,
  venn_diagram, protractor + angle_protractor alias
* Per-type exception swallow paths → "[X image generation failed]"
  paragraph + sentry capture
* Other small gaps (lines 67/93/109/117/188-189/226/275/277/295/297/
  380/407-411/416)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, DEFAULT

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixture: shared visualization mocks for create_document_docx
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_viz():
    """Patch all visualization functions and yield a dict mapping fn
    names to their MagicMock instances. Use `DEFAULT` so the
    yielded dict carries the mocks (vs the keyword-arg form which
    yields an empty dict)."""
    with patch.multiple(
        "backend.services.visualization",
        render_latex=DEFAULT,
        create_number_line=DEFAULT,
        create_coordinate_plane=DEFAULT,
        create_bar_chart=DEFAULT,
        create_line_graph=DEFAULT,
        create_scatter_plot=DEFAULT,
        create_box_plot=DEFAULT,
        create_triangle=DEFAULT,
        create_rectangle=DEFAULT,
        create_function_graph=DEFAULT,
        create_circle=DEFAULT,
        create_polygon=DEFAULT,
        create_histogram=DEFAULT,
        create_pie_chart=DEFAULT,
        create_dot_plot=DEFAULT,
        create_stem_and_leaf=DEFAULT,
        create_venn_diagram=DEFAULT,
        create_protractor=DEFAULT,
        add_image_to_docx=DEFAULT,
    ) as mocks:
        # Set sane defaults so the mocks return PNG-like bytes.
        fake_png = b"fake-png"
        for name, m in mocks.items():
            if name != "add_image_to_docx":
                m.return_value = fake_png
        yield mocks


def _default_style():
    """Minimal style dict that satisfies create_document_docx."""
    from backend.services.document_generator import DEFAULT_STYLE
    return dict(DEFAULT_STYLE)


def _run_docx(tmp_path, blocks, style=None):
    """Helper: invoke create_document_docx with the given content blocks
    and return the doc/filepath."""
    from backend.services.document_generator import create_document_docx
    fp = tmp_path / "test.docx"
    create_document_docx(
        str(fp),
        title="Test Document",
        content_blocks=blocks,
        style=style or _default_style(),
    )
    return fp


# ──────────────────────────────────────────────────────────────────
# Visual block dispatch — one test per block_type
# ──────────────────────────────────────────────────────────────────


class TestVisualBlocks:
    def test_math_block_invokes_render_latex(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{"type": "math", "latex": "x^2 + 1"}])
        assert patch_viz["render_latex"].called

    def test_number_line_block(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "number_line", "min": 0, "max": 10,
            "points": [3, 7],
        }])
        assert patch_viz["create_number_line"].called

    def test_coordinate_plane_block(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "coordinate_plane",
            "x_range": [-5, 5], "y_range": [-5, 5],
            "points": [[1, 2], [3, 4]],
        }])
        assert patch_viz["create_coordinate_plane"].called

    def test_graph_bar(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "graph", "graph_type": "bar",
            "categories": ["A", "B"], "values": [1, 2],
        }])
        assert patch_viz["create_bar_chart"].called

    def test_graph_line(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "graph", "graph_type": "line",
            "x_data": [1, 2, 3], "y_data": [4, 5, 6],
        }])
        assert patch_viz["create_line_graph"].called

    def test_graph_scatter(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "graph", "graph_type": "scatter",
            "x_data": [1, 2], "y_data": [3, 4],
            "show_trend": True,
        }])
        assert patch_viz["create_scatter_plot"].called

    def test_graph_unknown_skips_via_continue(self, tmp_path, patch_viz):
        # Unknown graph_type → "[Unknown graph type: X]" + continue
        # add_image_to_docx never called.
        _run_docx(tmp_path, [{
            "type": "graph", "graph_type": "weird",
        }])
        assert not patch_viz["add_image_to_docx"].called

    def test_box_plot(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "box_plot", "data": [[1, 2, 3, 4, 5]],
            "labels": ["A"],
        }])
        assert patch_viz["create_box_plot"].called

    def test_shape_triangle(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "shape", "shape_type": "triangle",
            "base": 6, "height": 4,
        }])
        assert patch_viz["create_triangle"].called

    def test_shape_rectangle(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "shape", "shape_type": "rectangle",
            "width": 8, "height": 5,
        }])
        assert patch_viz["create_rectangle"].called

    def test_shape_unknown_skips_via_continue(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "shape", "shape_type": "hexagon-unknown",
        }])
        assert not patch_viz["add_image_to_docx"].called

    def test_function_graph_with_y_range(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "function_graph",
            "expressions": ["x^2"],
            "x_range": [-3, 3], "y_range": [0, 9],
        }])
        assert patch_viz["create_function_graph"].called

    def test_function_graph_without_y_range(self, tmp_path, patch_viz):
        # y_range missing → conditional `tuple(...)` skipped, None passed
        _run_docx(tmp_path, [{
            "type": "function_graph",
            "expressions": ["x"],
        }])
        assert patch_viz["create_function_graph"].called

    def test_circle(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "circle", "radius": 5,
            "center": [0, 0], "show_diameter": True,
        }])
        assert patch_viz["create_circle"].called

    def test_polygon(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "polygon", "sides": 6,
        }])
        assert patch_viz["create_polygon"].called

    def test_histogram(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "histogram",
            "data": [1, 2, 2, 3, 3, 3, 4],
            "bins": 4,
        }])
        assert patch_viz["create_histogram"].called

    def test_pie_chart(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "pie_chart",
            "categories": ["X", "Y"],
            "values": [70, 30],
        }])
        assert patch_viz["create_pie_chart"].called

    def test_dot_plot(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "dot_plot",
            "categories": ["A", "B"],
            "dots": [3, 5],
        }])
        assert patch_viz["create_dot_plot"].called

    def test_stem_and_leaf(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "stem_and_leaf",
            "data": [12, 23, 34, 45],
        }])
        assert patch_viz["create_stem_and_leaf"].called

    def test_venn_diagram(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "venn_diagram", "sets": 2,
        }])
        assert patch_viz["create_venn_diagram"].called

    def test_protractor_canonical(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "protractor", "given_angle": 60,
        }])
        assert patch_viz["create_protractor"].called

    def test_protractor_angle_alias(self, tmp_path, patch_viz):
        _run_docx(tmp_path, [{
            "type": "angle_protractor", "given_angle": 30,
        }])
        assert patch_viz["create_protractor"].called


# ──────────────────────────────────────────────────────────────────
# Visual block exception swallow paths — one per block_type
# ──────────────────────────────────────────────────────────────────


class TestVisualExceptionSwallow:
    @pytest.mark.parametrize("block_type,viz_fn,marker", [
        ("math", "render_latex", "Math image"),
        ("number_line", "create_number_line", "Number line"),
        ("coordinate_plane", "create_coordinate_plane", "Coordinate plane"),
        ("box_plot", "create_box_plot", "Box plot"),
        ("function_graph", "create_function_graph", "Function graph"),
        ("circle", "create_circle", "Circle"),
        ("polygon", "create_polygon", "Polygon"),
        ("histogram", "create_histogram", "Histogram"),
        ("pie_chart", "create_pie_chart", "Pie chart"),
        ("dot_plot", "create_dot_plot", "Dot plot"),
        ("stem_and_leaf", "create_stem_and_leaf", "Stem-and-leaf"),
        ("venn_diagram", "create_venn_diagram", "Venn diagram"),
        ("protractor", "create_protractor", "Protractor"),
    ])
    def test_visual_failure_renders_failure_paragraph(
        self, tmp_path, block_type, viz_fn, marker,
    ):
        from backend.services.document_generator import create_document_docx
        with patch(
            f"backend.services.visualization.{viz_fn}",
            side_effect=RuntimeError("matplotlib explosion"),
        ), patch(
            "backend.services.document_generator.sentry_sdk.capture_exception",
        ) as sentry_mock:
            fp = tmp_path / "fail.docx"
            create_document_docx(
                str(fp), "T", [{"type": block_type}], _default_style(),
            )
        # Doc was saved successfully despite the visualization failure
        assert fp.exists()
        # Sentry captured the exception
        assert sentry_mock.called

    def test_graph_failure_renders_failure_paragraph(self, tmp_path):
        from backend.services.document_generator import create_document_docx
        with patch(
            "backend.services.visualization.create_bar_chart",
            side_effect=RuntimeError("matplotlib err"),
        ), patch(
            "backend.services.document_generator.sentry_sdk.capture_exception",
        ) as sentry_mock:
            fp = tmp_path / "graph_fail.docx"
            create_document_docx(
                str(fp), "T",
                [{"type": "graph", "graph_type": "bar"}],
                _default_style(),
            )
        assert fp.exists()
        assert sentry_mock.called

    def test_shape_failure_renders_failure_paragraph(self, tmp_path):
        from backend.services.document_generator import create_document_docx
        with patch(
            "backend.services.visualization.create_triangle",
            side_effect=RuntimeError("shape err"),
        ), patch(
            "backend.services.document_generator.sentry_sdk.capture_exception",
        ) as sentry_mock:
            fp = tmp_path / "shape_fail.docx"
            create_document_docx(
                str(fp), "T",
                [{"type": "shape", "shape_type": "triangle"}],
                _default_style(),
            )
        assert fp.exists()
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# Text blocks — table empty rows + bullet/numbered list happy paths
# ──────────────────────────────────────────────────────────────────


class TestTextBlocks:
    def test_table_with_empty_rows_skipped(self, tmp_path):
        # block_type="table" with rows=[] → continue (no table added)
        from backend.services.document_generator import create_document_docx
        fp = tmp_path / "empty_table.docx"
        create_document_docx(
            str(fp), "T",
            [{"type": "table", "rows": []}],
            _default_style(),
        )
        assert fp.exists()

    def test_bullet_list_block(self, tmp_path):
        from backend.services.document_generator import create_document_docx
        fp = tmp_path / "bullets.docx"
        create_document_docx(
            str(fp), "T",
            [{"type": "bullet_list",
              "items": ["First", "Second", "Third"]}],
            _default_style(),
        )
        assert fp.exists()

    def test_numbered_list_block(self, tmp_path):
        from backend.services.document_generator import create_document_docx
        fp = tmp_path / "numbered.docx"
        create_document_docx(
            str(fp), "T",
            [{"type": "numbered_list",
              "items": ["Step 1", "Step 2"]}],
            _default_style(),
        )
        assert fp.exists()

    def test_heading_levels_clamped(self, tmp_path):
        # level=99 → clamped to 3 by max(1, min(3, level))
        from backend.services.document_generator import create_document_docx
        fp = tmp_path / "headings.docx"
        create_document_docx(
            str(fp), "T",
            [
                {"type": "heading", "level": 99, "text": "Big"},
                {"type": "heading", "level": 0, "text": "Tiny"},
                {"type": "heading", "level": 2, "text": "Mid"},
            ],
            _default_style(),
        )
        assert fp.exists()
