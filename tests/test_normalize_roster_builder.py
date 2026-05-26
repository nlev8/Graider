"""normalize_roster gains a default-preserving external_id builder.

Default (no builder) must stay byte-identical to the historical
`oneroster:{sourcedId}` behavior — OneRoster + Clever depend on it.
A custom builder must be applied to ALL five external_id sites:
class, student, enrollment.class, enrollment.student, accommodation.student.
"""
from backend.oneroster import normalize_roster

RAW = {
    "classes": [{"sourcedId": "c1", "title": "Math", "subjects": ["Math"], "grades": ["9"]}],
    "students": [{"sourcedId": "s1", "givenName": "A", "familyName": "B", "email": "a@b.edu"}],
    "enrollments": [{"role": "student", "class": {"sourcedId": "c1"}, "user": {"sourcedId": "s1"}}],
    "demographics": [{"sourcedId": "s1", "metadata": {"iep_status": "active"}}],
}


def test_default_preserves_oneroster_prefix():
    classes, students, enrollments, accommodations = normalize_roster(RAW)
    assert classes[0]["external_id"] == "oneroster:c1"
    assert students[0]["external_id"] == "oneroster:s1"
    assert enrollments[0]["class_external_id"] == "oneroster:c1"
    assert enrollments[0]["student_external_id"] == "oneroster:s1"
    assert accommodations[0]["student_external_id"] == "oneroster:s1"


def test_custom_builder_applied_to_all_sites():
    builder = lambda sid: f"classlink:dist-A:{sid}"
    classes, students, enrollments, accommodations = normalize_roster(RAW, external_id_for=builder)
    assert classes[0]["external_id"] == "classlink:dist-A:c1"
    assert students[0]["external_id"] == "classlink:dist-A:s1"
    assert enrollments[0]["class_external_id"] == "classlink:dist-A:c1"
    assert enrollments[0]["student_external_id"] == "classlink:dist-A:s1"
    assert accommodations[0]["student_external_id"] == "classlink:dist-A:s1"
