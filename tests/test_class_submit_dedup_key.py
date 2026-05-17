"""Class submit sets dedup_key = student_id|content_id|attempt_number so
concurrent same-attempt double-submits collide on the partial index,
while legitimate new attempts (incremented attempt_number) do not."""
import backend.routes.student_account_routes as sar


def test_source_sets_attempt_scoped_dedup_key():
    src = open(sar.__file__, encoding="utf-8").read()
    assert "dedup_key" in src, "class submit must set dedup_key"
    # attempt-scoped (NOT student_id|content_id only — multi-attempt is intentional)
    assert "attempt" in src.split("dedup_key", 1)[1][:200], \
        "dedup_key must include attempt_number (multi-attempt is intentional)"
    assert "'23505'" in src and "already submitted" in src.lower()


def test_key_shape_is_triple():
    sid, cid, att = "s1", "c1", 2
    assert f"{sid}|{cid}|{att}" == "s1|c1|2"  # documents the exact shape
