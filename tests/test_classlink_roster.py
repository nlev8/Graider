"""ClassLink roster identity + shared-function safety."""
from unittest.mock import MagicMock, patch

from backend.routes.classlink_routes import _classlink_roster_external_id


def test_key_is_tenant_scoped():
    assert _classlink_roster_external_id("dist-A", "s1") == "classlink:dist-A:s1"


def test_key_percent_encodes_colon_in_components():
    # a ':' inside a component must not create a colliding key
    assert _classlink_roster_external_id("a:b", "c:d") == "classlink:a%3Ab:c%3Ad"


def test_key_tolerates_empty_components():
    assert _classlink_roster_external_id("", "") == "classlink::"


def _deactivate_sb(active_rows, captured_deactivations):
    """Fake Supabase for deactivate_missing_students."""
    sb = MagicMock()

    def _table(name):
        q = MagicMock()
        if name == "students":
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=list(active_rows))

            def _update(payload):
                upd = MagicMock()

                def _eq(col, val):
                    eqd = MagicMock()
                    eqd.execute.return_value = MagicMock(data=[])
                    captured_deactivations.append(val)
                    return eqd

                upd.eq.side_effect = _eq
                return upd

            q.update.side_effect = _update
        return q

    sb.table.side_effect = _table
    return sb


def test_clever_sync_does_not_deactivate_classlink_rows():
    from backend import roster_sync
    rows = [
        {"id": "row-cl", "student_id_number": "classlink:dist-A:s1"},  # protected
        {"id": "row-cv", "student_id_number": "cv-123"},               # clever, eligible
    ]
    captured = []
    with patch.object(roster_sync, "_get_supabase", return_value=_deactivate_sb(rows, captured)):
        roster_sync.deactivate_missing_students("t1", set(), provider="clever")
    assert "row-cl" not in captured       # classlink row NOT deactivated
    assert "row-cv" in captured           # clever row deactivated
