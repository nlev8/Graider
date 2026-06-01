import backend.routes.district_routes as dr


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._served = False

    def select(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def execute(self):
        rows = [] if self._served else self._rows
        self._served = True
        return type("R", (), {"data": rows})()


class _FakeSB:
    def __init__(self, by_table):
        self._by_table = by_table

    def table(self, name):
        return _FakeQuery(self._by_table.get(name, []))


def test_district_teacher_ids_unions_and_includes_clever(monkeypatch):
    sb = _FakeSB({
        "classes": [{"teacher_id": "uuid-1"}, {"teacher_id": "uuid-1"}],
        "published_content": [{"teacher_id": "uuid-2"}],
        "published_assessments": [{"teacher_id": "clever:abc"}, {"teacher_id": "uuid-1"}],
    })
    ids = dr._district_teacher_ids(sb)
    assert ids == {"uuid-1", "uuid-2", "clever:abc"}


def test_district_teacher_ids_empty(monkeypatch):
    assert dr._district_teacher_ids(_FakeSB({})) == set()


def test_district_teacher_ids_no_sb():
    assert dr._district_teacher_ids(None) == set()
