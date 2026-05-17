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
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import from the CURRENT location. After the move, only this import path
# changes (to backend.services.planner_export, or via the planner_routes
# shim) and every assertion below must still hold unchanged.
from backend.routes.planner_routes import _create_visual_for_question

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
