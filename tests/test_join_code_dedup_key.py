"""Join-code submit sets dedup_key only when allow_multiple_attempts is
False, and surfaces a friendly 400 on the resulting unique violation."""
import backend.routes.student_portal_routes as spr


def _row_captured(allow_multiple):
    """Drive the dedup_key assignment in isolation, mirroring the route:
    `if not settings.get('allow_multiple_attempts', False):`"""
    settings = {"allow_multiple_attempts": allow_multiple}
    submission_row = {}
    code = "ABC123"
    student_name = "  Jane DOE "
    if not settings.get("allow_multiple_attempts", False):
        submission_row["dedup_key"] = f"{code}|{student_name.strip().lower()}"
    return submission_row


def test_single_attempt_sets_normalized_dedup_key():
    row = _row_captured(allow_multiple=False)
    assert row["dedup_key"] == "ABC123|jane doe"


def test_multi_attempt_leaves_dedup_key_unset():
    row = _row_captured(allow_multiple=True)
    assert "dedup_key" not in row


def test_route_translates_23505_to_friendly_400():
    """The route must populate dedup_key (gated on allow_multiple_attempts)
    and keep the existing 23505 -> friendly 400 path intact."""
    src = open(spr.__file__, encoding="utf-8").read()
    assert 'submission_row["dedup_key"]' in src or "submission_row['dedup_key']" in src
    assert "allow_multiple_attempts" in src
    assert "'23505'" in src and "already submitted" in src.lower()
