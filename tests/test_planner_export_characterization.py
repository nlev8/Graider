"""Characterization safety net for _create_visual_for_question.

Pins the REAL observed behavior of the largest, most-entangled export
function BEFORE it is relocated to backend/services/planner_export.py.

This net must keep passing after the move with ONLY the import path
changed — that equivalence is the zero-behavior-change proof for the
Tier 2 slice-1 PR2 extraction.

Observed contract (probed against the pre-move code):
  * number_line        -> reportlab.platypus.Image (deterministic dims)
  * coordinate_plane   -> reportlab.platypus.Image (deterministic dims)
  * triangle (geometry)-> reportlab.platypus.Image (deterministic dims)
  * multiple_choice    -> None  (no rendering branch)
  * short_answer       -> None  (no rendering branch)
  * data_table         -> None  (no rendering branch)

Post-extraction additions (PR fix/unit-circle-visual-rgba):
  * unit_circle        -> reportlab.platypus.Image (both show_answer=False and True)
    Previously: returned None due to matplotlib rejecting CSS rgba() color string.
  * All 28 visual-producing q_types pinned via characterization probing.
"""
import sys
import os
import warnings
import pytest

import matplotlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Shim import — keeps the original tests green against the re-export shim in planner_routes.
from backend.routes.planner_routes import _create_visual_for_question

# Canonical post-extraction import used by the new tests added in this PR.
from backend.services.planner_export import _create_visual_for_question as _create_visual_export

from reportlab.platypus import Image


# ---------------------------------------------------------------------------
# Question types that have a rendering branch -> real ReportLab Image
# ---------------------------------------------------------------------------

def test_number_line_returns_reportlab_image():
    q = {'question_type': 'number_line', 'min_val': -5, 'max_val': 5}
    result = _create_visual_for_question(q, False)
    assert isinstance(result, Image)
    # Image carries explicit draw dimensions (aspect ratio preserved)
    assert result.drawWidth > 0
    assert result.drawHeight > 0


def test_coordinate_plane_returns_reportlab_image():
    q = {'question_type': 'coordinate_plane'}
    result = _create_visual_for_question(q, False)
    assert isinstance(result, Image)
    assert result.drawWidth > 0
    assert result.drawHeight > 0


def test_triangle_geometry_returns_reportlab_image():
    q = {'question_type': 'triangle', 'base': 6, 'height': 4}
    result = _create_visual_for_question(q, False)
    assert isinstance(result, Image)
    assert result.drawWidth > 0
    assert result.drawHeight > 0


# ---------------------------------------------------------------------------
# Question types with NO rendering branch -> None (pinned exactly)
# ---------------------------------------------------------------------------

def test_multiple_choice_returns_none():
    assert _create_visual_for_question({'question_type': 'multiple_choice'}, False) is None


def test_short_answer_returns_none():
    assert _create_visual_for_question({'question_type': 'short_answer'}, False) is None


def test_data_table_returns_none():
    assert _create_visual_for_question({'question_type': 'data_table'}, False) is None


def test_unknown_type_returns_none():
    assert _create_visual_for_question({'question_type': 'totally_unknown_xyz'}, False) is None


# ---------------------------------------------------------------------------
# Determinism: same input twice -> equal output (dims + rendered PNG bytes)
# ---------------------------------------------------------------------------

def _pixels(image):
    """Extract the decoded RGB pixel data backing a ReportLab Image.

    ReportLab consumes the source BytesIO into an ImageReader at
    construction time, so the rendered content is read back through
    the ImageReader rather than the (now-None) source buffer.
    """
    return image._img.getRGBData()


def test_number_line_is_deterministic():
    q = {'question_type': 'number_line', 'min_val': -5, 'max_val': 5}
    a = _create_visual_for_question(q, False)
    b = _create_visual_for_question(q, False)
    assert (a.drawWidth, a.drawHeight) == (b.drawWidth, b.drawHeight)
    assert _pixels(a) == _pixels(b)


def test_triangle_is_deterministic():
    q = {'question_type': 'triangle', 'base': 6, 'height': 4}
    a = _create_visual_for_question(q, False)
    b = _create_visual_for_question(q, False)
    assert (a.drawWidth, a.drawHeight) == (b.drawWidth, b.drawHeight)
    assert _pixels(a) == _pixels(b)


def test_none_branch_is_deterministic():
    q = {'question_type': 'multiple_choice'}
    assert _create_visual_for_question(q, False) is _create_visual_for_question(q, False)  # both None


# ===========================================================================
# NEW TESTS — canonical import from backend.services.planner_export
# (added in fix/unit-circle-visual-rgba)
# ===========================================================================

# ---------------------------------------------------------------------------
# RED → GREEN: unit_circle bug fix
# The branch used 'rgba(99,102,241,0.2)' as a matplotlib color, which raises
# ValueError at render time; the function-wide except swallowed it → None.
# Fix: replace with hex '#6366f1' + alpha= kwarg (same color, same translucency).
# ---------------------------------------------------------------------------

def test_unit_circle_show_answer_false_returns_image():
    """unit_circle with show_answer=False must produce a real ReportLab Image."""
    q = {'question_type': 'unit_circle'}
    result = _create_visual_export(q, False)
    assert isinstance(result, Image), f"Expected Image, got {result!r}"
    assert result.drawWidth > 0
    assert result.drawHeight > 0


def test_unit_circle_show_answer_true_returns_image():
    """unit_circle with show_answer=True must also produce a real ReportLab Image."""
    q = {'question_type': 'unit_circle'}
    result = _create_visual_export(q, True)
    assert isinstance(result, Image), f"Expected Image, got {result!r}"
    assert result.drawWidth > 0
    assert result.drawHeight > 0


def test_unit_circle_is_deterministic():
    """Same unit_circle input twice must yield identical dims and pixel data."""
    q = {'question_type': 'unit_circle'}
    a = _create_visual_export(q, False)
    b = _create_visual_export(q, False)
    assert (a.drawWidth, a.drawHeight) == (b.drawWidth, b.drawHeight)
    assert _pixels(a) == _pixels(b)


# ---------------------------------------------------------------------------
# Full 28-branch characterization net — pins OBSERVED reality for every
# visual-producing q_type.  Probed with minimal dicts; branches that need
# additional keys to reach a successful render have a second variant test.
# ---------------------------------------------------------------------------

# These 6 geometry sub-types all share one code branch; pin each separately.
@pytest.mark.parametrize("q_type", [
    'geometry', 'triangle', 'pythagorean', 'trig', 'angles', 'similarity',
])
def test_geometry_family_minimal_returns_image(q_type):
    """geometry-family branches render successfully with a minimal dict."""
    q = {'question_type': q_type}
    result = _create_visual_export(q, False)
    assert isinstance(result, Image), f"{q_type}: Expected Image, got {result!r}"
    assert result.drawWidth > 0
    assert result.drawHeight > 0


# Remaining individual visual-producing branches
@pytest.mark.parametrize("q_type", [
    'number_line',
    'coordinate_plane',
    'rectangle',
    'circle',
    'trapezoid',
    'parallelogram',
    'regular_polygon',
    'rectangular_prism',
    'cylinder',
    'box_plot',
    'bar_chart',
    'function_graph',
    'dot_plot',
    'stem_and_leaf',
    'unit_circle',
    'transformations',
    'fraction_model',
    'probability_tree',
    'tape_diagram',
    'venn_diagram',
    'histogram',
    'pie_chart',
])
def test_visual_branch_minimal_returns_image(q_type):
    """Each visual-producing branch returns a ReportLab Image for a minimal dict."""
    q = {'question_type': q_type}
    result = _create_visual_export(q, False)
    assert isinstance(result, Image), f"{q_type}: Expected Image, got {result!r}"
    assert result.drawWidth > 0
    assert result.drawHeight > 0


# ---------------------------------------------------------------------------
# None-contract: non-visual types remain None when called via export module
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("q_type", [
    'multiple_choice', 'short_answer', 'data_table', 'totally_unknown_xyz',
])
def test_non_visual_types_return_none_export(q_type):
    assert _create_visual_export({'question_type': q_type}, False) is None


# ---------------------------------------------------------------------------
# Deprecation-strict regression: box_plot must not emit MatplotlibDeprecationWarning
# ax.boxplot(labels=...) was renamed tick_labels= in mpl 3.9 and removed in 3.11.
# ---------------------------------------------------------------------------

def test_box_plot_no_matplotlib_deprecation():
    q = {"question_type": "box_plot", "data": [[50, 60, 70, 75, 80, 85, 90]]}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = _create_visual_export(q, False)
    deprecations = [
        w for w in caught
        if issubclass(w.category, DeprecationWarning)
        and ("boxplot" in str(w.message).lower() or "tick_labels" in str(w.message).lower())
    ]
    assert not deprecations, (
        "box_plot emitted MatplotlibDeprecationWarning(s): "
        + "; ".join(str(w.message) for w in deprecations)
    )
    assert isinstance(result, Image)
