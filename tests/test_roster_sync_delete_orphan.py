"""delete_roster_data must delete a teacher's student rows even when the
teacher has no class rows (orphan students). Previously student deletion
was gated inside `if class_ids:`, leaving orphans behind — an incomplete
FERPA right-to-delete. Still teacher_id-scoped (never touches other teachers)."""
from unittest.mock import MagicMock, patch

from backend import roster_sync


def _delete_sb(class_ids, student_ids, deletes):
    """Fake Supabase recording which tables had .delete() executed."""
    sb = MagicMock()

    def _table(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        if name == "classes":
            q.execute.return_value = MagicMock(data=[{"id": c} for c in class_ids])
        elif name == "students":
            q.execute.return_value = MagicMock(data=[{"id": s} for s in student_ids])
        else:
            q.execute.return_value = MagicMock(data=[])

        def _delete():
            deletes.append(name)
            d = MagicMock()
            d.eq.return_value = d
            d.in_.return_value = d
            d.execute.return_value = MagicMock(data=[])
            return d

        q.delete.side_effect = _delete
        return q

    sb.table.side_effect = _table
    return sb


def test_deletes_orphan_students_with_no_classes():
    deletes = []
    sb = _delete_sb(class_ids=[], student_ids=["st1", "st2"], deletes=deletes)
    with patch("backend.supabase_client.get_supabase", return_value=sb):
        result = roster_sync.delete_roster_data("classlink:dist-A:teach1")
    assert "students" in deletes        # students deleted despite zero classes
    assert result["students"] == 2
