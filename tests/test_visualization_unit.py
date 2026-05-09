"""Unit tests for backend/services/visualization.py.

Strategy: drive matplotlib via the real Agg backend (already configured by
`_get_plt`) and assert that every public function returns a `data:image/png;base64,...`
data URL whose decoded bytes start with the PNG signature `\\x89PNG\\r\\n\\x1a\\n`.

Each function gets at least:
  * one populated/normal-path call
  * one `blank=True` (or empty-data) call where supported

Together these cover the populated + blank branches plus title/label/axis
formatting paths in every public function.

Per project audit MAJOR #4 coverage sprint — picks the biggest single-PR gain
remaining (visualization.py was at 5%, 502 uncovered LOC).
"""

import base64
import io

import pytest

from backend.services import visualization as viz


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DATA_URL_PREFIX = "data:image/png;base64,"


def _decode_data_url(data_url: str) -> bytes:
    """Strip `data:image/png;base64,` prefix and base64-decode."""
    assert isinstance(data_url, str), f"expected str, got {type(data_url)}"
    assert data_url.startswith(DATA_URL_PREFIX), f"missing data-URL prefix: {data_url[:40]!r}"
    payload = data_url.split(",", 1)[1]
    return base64.b64decode(payload)


def _assert_png_data_url(data_url: str, *, min_size: int = 100) -> bytes:
    """Assert the value is a PNG data URL and return the decoded bytes."""
    decoded = _decode_data_url(data_url)
    assert decoded[:8] == PNG_SIGNATURE, f"PNG signature missing: {decoded[:8]!r}"
    assert len(decoded) >= min_size, f"PNG suspiciously small: {len(decoded)} bytes"
    return decoded


class TestLazyLoaders:
    """Cover _get_plt and _get_np singleton-style lazy loaders."""

    def test_get_plt_returns_pyplot_module(self):
        plt = viz._get_plt()
        assert plt is not None
        assert hasattr(plt, "subplots")
        # Cached on second call
        assert viz._get_plt() is plt

    def test_get_np_returns_numpy_module(self):
        np = viz._get_np()
        assert np is not None
        assert hasattr(np, "linspace")
        assert viz._get_np() is np


class TestFigureToBase64:
    def test_returns_data_url_with_png_payload(self):
        plt = viz._get_plt()
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.plot([0, 1], [0, 1])
        try:
            result = viz.figure_to_base64(fig)
            _assert_png_data_url(result)
        finally:
            plt.close(fig)


class TestSaveFigure:
    def test_writes_png_file(self, tmp_path):
        plt = viz._get_plt()
        fig, ax = plt.subplots(figsize=(2, 2))
        ax.plot([0, 1], [0, 1])
        out = tmp_path / "out.png"
        try:
            viz.save_figure(fig, str(out))
        finally:
            plt.close(fig)
        assert out.exists()
        body = out.read_bytes()
        assert body[:8] == PNG_SIGNATURE


class TestRenderLatex:
    def test_renders_simple_expression(self):
        result = viz.render_latex(r"\frac{1}{2}")
        _assert_png_data_url(result)

    def test_respects_font_size(self):
        small = viz.render_latex("x^2", font_size=10)
        large = viz.render_latex("x^2", font_size=40)
        # Different font sizes should yield distinct images.
        assert small != large
        _assert_png_data_url(small)
        _assert_png_data_url(large)

    def test_handles_complex_latex_with_greek(self):
        result = viz.render_latex(r"\sum_{i=1}^{n} \alpha_i \beta_i")
        _assert_png_data_url(result)


class TestNumberLine:
    def test_default_call_renders(self):
        result = viz.create_number_line()
        _assert_png_data_url(result)

    def test_with_points_and_labels(self):
        result = viz.create_number_line(
            min_val=-5, max_val=5,
            points=[-3, 0.5, 2.75],
            labels=["A", "B", "C"],
            title="Plot the rational numbers",
        )
        _assert_png_data_url(result)

    def test_blank_template_skips_points(self):
        result = viz.create_number_line(
            min_val=0, max_val=10,
            points=[2, 5, 8],
            labels=["X", "Y", "Z"],
            blank=True,
        )
        _assert_png_data_url(result)

    def test_show_integers_false_hides_ticks(self):
        result = viz.create_number_line(min_val=0, max_val=4, show_integers=False)
        _assert_png_data_url(result)

    def test_more_points_than_labels(self):
        # zip stops at shortest — exercises labels-shorter-than-points branch
        result = viz.create_number_line(points=[1, 2, 3], labels=["only-one"])
        _assert_png_data_url(result)


class TestCoordinatePlane:
    def test_default_call_renders(self):
        result = viz.create_coordinate_plane()
        _assert_png_data_url(result)

    def test_with_points_and_labels(self):
        result = viz.create_coordinate_plane(
            x_range=(-5, 5), y_range=(-5, 5),
            points=[(3, 4), (-2, 5), (-4, -3), (2, -5)],
            labels=["A", "B", "C", "D"],
            title="Plot the points",
        )
        _assert_png_data_url(result)

    def test_with_points_no_labels_uses_coord_text(self):
        # Hits `f"({pt[0]}, {pt[1]})"` fallback path
        result = viz.create_coordinate_plane(
            points=[(1, 2), (-3, -4)],
        )
        _assert_png_data_url(result)

    def test_grid_off(self):
        result = viz.create_coordinate_plane(grid=False)
        _assert_png_data_url(result)

    def test_blank_template_skips_points(self):
        result = viz.create_coordinate_plane(
            points=[(1, 2)], labels=["A"], blank=True,
        )
        _assert_png_data_url(result)


class TestBoxPlot:
    def test_single_dataset_default_labels(self):
        result = viz.create_box_plot(
            data=[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]],
            title="Test Scores",
        )
        _assert_png_data_url(result)

    def test_two_datasets_with_labels(self):
        result = viz.create_box_plot(
            data=[
                [23, 45, 67, 32, 44, 55, 66, 77, 34, 45],
                [34, 56, 78, 43, 55, 66, 77, 88, 45, 56],
            ],
            labels=["Class A", "Class B"],
            title="Test Scores by Class",
            show_values=True,
        )
        _assert_png_data_url(result)

    def test_show_values_off(self):
        result = viz.create_box_plot(
            data=[[1, 2, 3, 4, 5]],
            show_values=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_box_plot(data=[], blank=True)
        _assert_png_data_url(result)


class TestBarChart:
    def test_with_data(self):
        result = viz.create_bar_chart(
            categories=["Math", "Science", "English", "History"],
            values=[85, 92, 78, 88],
            title="Average Grades by Subject",
            x_label="Subject",
            y_label="Score",
            color="seagreen",
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_bar_chart(
            categories=[], values=[], blank=True,
            title="Draw a bar chart",
        )
        _assert_png_data_url(result)


class TestLineGraph:
    def test_with_data_show_points(self):
        result = viz.create_line_graph(
            x_data=[1, 2, 3, 4, 5],
            y_data=[2, 4, 6, 8, 10],
            title="y = 2x",
            x_label="x",
            y_label="y",
            show_points=True,
        )
        _assert_png_data_url(result)

    def test_with_data_no_points(self):
        result = viz.create_line_graph(
            x_data=[1, 2, 3], y_data=[1, 4, 9],
            show_points=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_line_graph(x_data=[], y_data=[], blank=True)
        _assert_png_data_url(result)


class TestScatterPlot:
    def test_with_data_no_trend(self):
        result = viz.create_scatter_plot(
            x_data=[1, 2, 3, 4, 5],
            y_data=[2, 5, 7, 6, 9],
            title="Scatter",
            x_label="x", y_label="y",
            show_trend=False,
        )
        _assert_png_data_url(result)

    def test_with_data_show_trend(self):
        result = viz.create_scatter_plot(
            x_data=[1, 2, 3, 4, 5],
            y_data=[2, 4, 5, 4, 5],
            show_trend=True,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_scatter_plot(x_data=[], y_data=[], blank=True)
        _assert_png_data_url(result)


class TestTriangle:
    def test_default(self):
        result = viz.create_triangle()
        _assert_png_data_url(result)

    def test_full_labels_and_dimensions(self):
        result = viz.create_triangle(
            base=8, height=6,
            show_labels=True, show_dimensions=True,
            title="Find the Area",
        )
        _assert_png_data_url(result)

    def test_no_labels_no_dimensions(self):
        result = viz.create_triangle(
            base=4, height=3,
            show_labels=False, show_dimensions=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_triangle(blank=True)
        _assert_png_data_url(result)


class TestRectangle:
    def test_default(self):
        result = viz.create_rectangle()
        _assert_png_data_url(result)

    def test_full_labels_and_dimensions(self):
        result = viz.create_rectangle(
            width=10, height=5,
            show_labels=True, show_dimensions=True,
            title="Area",
        )
        _assert_png_data_url(result)

    def test_no_labels_no_dimensions(self):
        result = viz.create_rectangle(
            width=2, height=3,
            show_labels=False, show_dimensions=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_rectangle(blank=True)
        _assert_png_data_url(result)


class TestFunctionGraph:
    def test_single_linear(self):
        result = viz.create_function_graph(
            expressions=["2*x + 1"],
            x_range=(-5, 5),
            title="y = 2x + 1",
        )
        _assert_png_data_url(result)

    def test_multiple_expressions_with_labels(self):
        result = viz.create_function_graph(
            expressions=["x**2", "x + 1", "y = 3*x - 2"],
            x_range=(-3, 3),
            labels=["parabola", "line", "another"],
        )
        _assert_png_data_url(result)

    def test_caret_notation_handled(self):
        # Hits replace('^', '**')
        result = viz.create_function_graph(expressions=["x^2 + 1"])
        _assert_png_data_url(result)

    def test_invalid_expression_continues(self):
        # `not_a_function(x)` raises during sympify or lambdify — continue branch
        result = viz.create_function_graph(
            expressions=["definitely-invalid-???", "x"],
            x_range=(-2, 2),
        )
        _assert_png_data_url(result)

    def test_constant_expression(self):
        # Hits not hasattr(y_vals, '__len__') — full_like branch
        result = viz.create_function_graph(expressions=["3"])
        _assert_png_data_url(result)

    def test_explicit_y_range(self):
        result = viz.create_function_graph(
            expressions=["x"], y_range=(-5, 5),
        )
        _assert_png_data_url(result)

    def test_blank_with_y_range(self):
        result = viz.create_function_graph(
            expressions=[], blank=True, y_range=(-2, 2),
        )
        _assert_png_data_url(result)

    def test_blank_no_y_range(self):
        result = viz.create_function_graph(expressions=[], blank=True)
        _assert_png_data_url(result)

    def test_grid_off(self):
        result = viz.create_function_graph(
            expressions=["x"], show_grid=False,
        )
        _assert_png_data_url(result)


class TestCircle:
    def test_default(self):
        result = viz.create_circle()
        _assert_png_data_url(result)

    def test_show_radius_diameter_area(self):
        result = viz.create_circle(
            radius=4, center=(1, 1),
            show_radius=True, show_diameter=True, show_area=True,
            title="Circle",
        )
        _assert_png_data_url(result)

    def test_no_decorations(self):
        result = viz.create_circle(
            show_radius=False, show_diameter=False, show_area=False,
        )
        _assert_png_data_url(result)

    def test_blank_unlabeled(self):
        result = viz.create_circle(blank=True, show_radius=True, show_area=True)
        _assert_png_data_url(result)


class TestPolygon:
    @pytest.mark.parametrize("sides", [3, 4, 5, 6, 8])
    def test_various_sides_render(self, sides):
        result = viz.create_polygon(sides=sides, side_length=3)
        _assert_png_data_url(result)

    def test_with_labels_and_dimensions(self):
        result = viz.create_polygon(
            sides=5, side_length=2,
            show_labels=True, show_dimensions=True,
            title="Pentagon",
        )
        _assert_png_data_url(result)

    def test_no_labels_no_dimensions(self):
        result = viz.create_polygon(
            sides=6, show_labels=False, show_dimensions=False,
        )
        _assert_png_data_url(result)

    def test_blank(self):
        result = viz.create_polygon(sides=4, blank=True)
        _assert_png_data_url(result)


class TestHistogram:
    def test_with_data(self):
        result = viz.create_histogram(
            data=[1, 1, 2, 3, 3, 3, 4, 5, 5, 5, 5, 6, 7, 8, 9],
            bins=5,
            title="Frequency",
            x_label="Value",
            show_values=True,
        )
        _assert_png_data_url(result)

    def test_show_values_off(self):
        result = viz.create_histogram(
            data=[1, 2, 3, 4, 5], bins=3, show_values=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_histogram(data=[], blank=True)
        _assert_png_data_url(result)


class TestPieChart:
    def test_with_data(self):
        result = viz.create_pie_chart(
            categories=["A", "B", "C"],
            values=[30, 40, 30],
            title="Distribution",
            show_percentages=True,
        )
        _assert_png_data_url(result)

    def test_with_explode(self):
        result = viz.create_pie_chart(
            categories=["X", "Y", "Z"],
            values=[1, 2, 3],
            explode=[0, 0.1, 0],
            show_percentages=False,
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_pie_chart(categories=[], values=[], blank=True)
        _assert_png_data_url(result)


class TestDotPlot:
    def test_with_categories_and_dots(self):
        result = viz.create_dot_plot(
            categories=["A", "B", "C"],
            dots={"A": 2, "B": 3, "C": 1},
            title="Dot Plot",
        )
        _assert_png_data_url(result)

    def test_auto_generate_categories(self):
        # Hits `items = ... range` branch when categories is None
        result = viz.create_dot_plot(
            min_val=0, max_val=4, step=1,
            dots={"0": 1, "2": 2, "4": 3},
        )
        _assert_png_data_url(result)

    def test_blank_template(self):
        result = viz.create_dot_plot(
            categories=["A", "B"], dots={"A": 1}, blank=True,
        )
        _assert_png_data_url(result)

    def test_no_dots_default_max(self):
        # Hits `default=3` for max_count
        result = viz.create_dot_plot(categories=["X", "Y"])
        _assert_png_data_url(result)


class TestStemAndLeaf:
    def test_with_data(self):
        result = viz.create_stem_and_leaf(
            data=[12, 15, 22, 25, 28, 31, 33, 47],
            title="Test Scores",
        )
        _assert_png_data_url(result)

    def test_blank_with_data_hides_leaves(self):
        result = viz.create_stem_and_leaf(
            data=[10, 20, 30, 40], blank=True,
        )
        _assert_png_data_url(result)

    def test_no_data_placeholder(self):
        result = viz.create_stem_and_leaf(data=None)
        _assert_png_data_url(result)


class TestVennDiagram:
    def test_two_sets_with_regions(self):
        result = viz.create_venn_diagram(
            sets=2,
            labels=["Cats", "Dogs"],
            regions={"only_a": "5", "a_and_b": "2", "only_b": "8"},
            title="Pets",
        )
        _assert_png_data_url(result)

    def test_three_sets_with_regions(self):
        result = viz.create_venn_diagram(
            sets=3,
            regions={
                "only_a": "1", "only_b": "2", "only_c": "3",
                "a_and_b": "4", "a_and_c": "5", "b_and_c": "6",
                "all": "7",
            },
        )
        _assert_png_data_url(result)

    def test_default_labels(self):
        # No labels passed — hits `Set A`, `Set B` default
        result = viz.create_venn_diagram(sets=2)
        _assert_png_data_url(result)

    def test_blank_no_regions(self):
        result = viz.create_venn_diagram(sets=2, blank=True)
        _assert_png_data_url(result)


class TestProtractor:
    def test_default(self):
        result = viz.create_protractor()
        _assert_png_data_url(result)

    @pytest.mark.parametrize("angle", [0, 30, 45, 60, 90, 135, 180])
    def test_various_angles(self, angle):
        result = viz.create_protractor(given_angle=angle)
        _assert_png_data_url(result)

    def test_show_answer_false(self):
        result = viz.create_protractor(given_angle=72, show_answer=False, title="Measure")
        _assert_png_data_url(result)


class TestAddImageToDocx:
    def test_strips_data_url_prefix_and_adds_picture(self):
        # Render a real PNG to base64, then exercise both prefix-stripping and
        # `doc.add_picture` invocation via a stub.
        png = viz.create_rectangle(width=2, height=2, title="t")

        recorded: dict = {}

        class _StubDoc:
            def add_picture(self, stream, width=None):
                recorded["bytes"] = stream.read()
                recorded["width"] = width

        doc = _StubDoc()
        viz.add_image_to_docx(doc, png, width_inches=3)

        assert recorded["bytes"][:8] == PNG_SIGNATURE
        # docx Inches(3) is an EMU value; we just confirm it was passed
        assert recorded["width"] is not None

    def test_accepts_raw_base64_without_prefix(self):
        # PNG signature in raw base64
        raw_png = base64.b64encode(PNG_SIGNATURE + b"\x00" * 32).decode("utf-8")

        captured: dict = {}

        class _StubDoc:
            def add_picture(self, stream, width=None):
                captured["bytes"] = stream.read()

        viz.add_image_to_docx(_StubDoc(), raw_png, width_inches=1)
        assert captured["bytes"][:8] == PNG_SIGNATURE
