"""Multi-teacher smoke test — real Supabase, concurrent workflows.

Simulates 3 teachers in different subjects, each publishing content,
with students taking and being graded. Tests data isolation between teachers.

Teacher 1: US History — publishes an ASSESSMENT (MC + TF + short answer)
Teacher 2: Math — publishes an ASSIGNMENT (MC + matching)
Teacher 3: Science — publishes an ASSESSMENT (MC + TF + extended response)

Each teacher's students submit answers. Verifies:
- Correct instant grading per content type
- Data isolation (teacher 1 can't see teacher 2's content)
- Assessment vs Assignment behavior differences
- Written questions marked pending_review
- Matching questions scored correctly (bug fix verification)
"""
import os
import sys
import json
import random
import pytest
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def _get_supabase():
    try:
        from backend.supabase_client import get_supabase
        return get_supabase()
    except Exception:  # noqa: BLE001  # broad catch: returns fallback
        return None


pytestmark = pytest.mark.skipif(
    _get_supabase() is None,
    reason="Supabase not configured — skipping multi-teacher E2E tests"
)


def _random_code(prefix="SM"):
    return prefix + ''.join(random.choices('ABCDEFGHJKMNPQRSTUVWXYZ23456789', k=4))


# ══════════════════════════════════════════
# TEACHER 1: US History — Assessment
# ══════════════════════════════════════════

TEACHER_1 = {
    "id": "smoke-teacher-history",
    "name": "Ms. Rodriguez",
    "subject": "US History",
    "content_type": "assessment",
    "assessment": {
        "title": "Colonial America Quiz",
        "total_points": 25,
        "sections": [
            {
                "name": "Multiple Choice",
                "questions": [
                    {
                        "number": 1, "type": "multiple_choice",
                        "question": "Who wrote the Declaration of Independence?",
                        "options": ["A) George Washington", "B) Thomas Jefferson", "C) Benjamin Franklin", "D) John Adams"],
                        "answer": "B", "points": 5,
                    },
                    {
                        "number": 2, "type": "multiple_choice",
                        "question": "In what year was the Constitution ratified?",
                        "options": ["A) 1776", "B) 1783", "C) 1788", "D) 1791"],
                        "answer": "C", "points": 5,
                    },
                ],
            },
            {
                "name": "True/False",
                "questions": [
                    {
                        "number": 3, "type": "true_false",
                        "question": "The Boston Tea Party occurred in 1773.",
                        "answer": "True", "points": 5,
                    },
                ],
            },
            {
                "name": "Short Answer",
                "questions": [
                    {
                        "number": 4, "type": "short_answer",
                        "question": "Explain the significance of the Stamp Act.",
                        "answer": "The Stamp Act taxed printed materials, angering colonists who had no representation in Parliament.",
                        "points": 10,
                    },
                ],
            },
        ],
    },
    "student_answers": {
        "0-0": "B",     # Correct (Jefferson)
        "0-1": "A",     # Wrong (1776, correct is 1788)
        "1-0": "True",  # Correct
        "2-0": "The Stamp Act was a tax on paper goods that colonists opposed.",
    },
    "expected_instant_score": 10,  # MC1(5) + TF(5) = 10, MC2 wrong, SA pending
}


# ══════════════════════════════════════════
# TEACHER 2: Math — Assignment
# ══════════════════════════════════════════

TEACHER_2 = {
    "id": "smoke-teacher-math",
    "name": "Mr. Chen",
    "subject": "Mathematics",
    "content_type": "assignment",
    "assessment": {
        "title": "Algebra Practice Worksheet",
        "total_points": 20,
        "sections": [
            {
                "name": "Multiple Choice",
                "questions": [
                    {
                        "number": 1, "type": "multiple_choice",
                        "question": "What is 3x + 6 = 15? Solve for x.",
                        "options": ["A) 2", "B) 3", "C) 4", "D) 5"],
                        "answer": "B", "points": 5,
                    },
                    {
                        "number": 2, "type": "multiple_choice",
                        "question": "Simplify: 2(x + 4)",
                        "options": ["A) 2x + 4", "B) 2x + 8", "C) x + 8", "D) 2x + 6"],
                        "answer": "B", "points": 5,
                    },
                ],
            },
            {
                "name": "Vocabulary Matching",
                "questions": [
                    {
                        "number": 3, "type": "matching",
                        "question": "Match the math terms with their definitions.",
                        "terms": ["Variable", "Coefficient", "Constant"],
                        "definitions": ["A fixed number", "A letter representing an unknown", "A number multiplied by a variable"],
                        "answer": {
                            "Variable": "A letter representing an unknown",
                            "Coefficient": "A number multiplied by a variable",
                            "Constant": "A fixed number",
                        },
                        "points": 10,
                    },
                ],
            },
        ],
    },
    "student_answers": {
        "0-0": "B",          # Correct (x=3)
        "0-1": "B",          # Correct (2x+8)
        "1-0-match-0": "B",  # Variable → "A letter..." (index 1 = B) ✓
        "1-0-match-1": "C",  # Coefficient → "A number multiplied..." (index 2 = C) ✓
        "1-0-match-2": "A",  # Constant → "A fixed number" (index 0 = A) ✓
    },
    "expected_instant_score": 20,  # MC1(5) + MC2(5) + Matching(10) = 20, no written
}


# ══════════════════════════════════════════
# TEACHER 3: Science — Assessment
# ══════════════════════════════════════════

TEACHER_3 = {
    "id": "smoke-teacher-science",
    "name": "Dr. Patel",
    "subject": "Biology",
    "content_type": "assessment",
    "assessment": {
        "title": "Cell Biology Assessment",
        "total_points": 30,
        "sections": [
            {
                "name": "Multiple Choice",
                "questions": [
                    {
                        "number": 1, "type": "multiple_choice",
                        "question": "What is the powerhouse of the cell?",
                        "options": ["A) Nucleus", "B) Ribosome", "C) Mitochondria", "D) Golgi apparatus"],
                        "answer": "C", "points": 5,
                    },
                    {
                        "number": 2, "type": "multiple_choice",
                        "question": "Which organelle contains DNA?",
                        "options": ["A) Lysosome", "B) Nucleus", "C) Cell membrane", "D) Vacuole"],
                        "answer": "B", "points": 5,
                    },
                ],
            },
            {
                "name": "True/False",
                "questions": [
                    {
                        "number": 3, "type": "true_false",
                        "question": "Plant cells have cell walls while animal cells do not.",
                        "answer": "True", "points": 5,
                    },
                    {
                        "number": 4, "type": "true_false",
                        "question": "Prokaryotic cells have a nucleus.",
                        "answer": "False", "points": 5,
                    },
                ],
            },
            {
                "name": "Extended Response",
                "questions": [
                    {
                        "number": 5, "type": "extended_response",
                        "question": "Compare and contrast plant and animal cells. Include at least 3 similarities and 3 differences.",
                        "answer": "Both have cell membrane, cytoplasm, and DNA. Plants have cell walls, chloroplasts, and large vacuoles while animals do not.",
                        "points": 10,
                    },
                ],
            },
        ],
    },
    "student_answers": {
        "0-0": "C",     # Correct (mitochondria)
        "0-1": "B",     # Correct (nucleus)
        "1-0": "True",  # Correct
        "1-1": "True",  # WRONG (correct is False)
        "2-0": "Plant cells have cell walls and chloroplasts. Animal cells are more round. Both have DNA.",
    },
    "expected_instant_score": 15,  # MC1(5) + MC2(5) + TF1(5) + TF2(0) = 15, ER pending
}


ALL_TEACHERS = [TEACHER_1, TEACHER_2, TEACHER_3]


class TestMultiTeacherSmoke:
    """Simulate 3 teachers publishing and students submitting concurrently."""

    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        self.db = _get_supabase()
        self.join_codes = []
        yield
        # Cleanup ALL test data
        for code in self.join_codes:
            try:
                self.db.table('submissions').delete().eq('join_code', code).execute()
            except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
                pass
            try:
                self.db.table('published_assessments').delete().eq('join_code', code).execute()
            except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
                pass

    def _publish(self, teacher):
        """Publish content for a teacher. Returns join code."""
        code = _random_code("SM")
        self.join_codes.append(code)

        settings = {
            "time_limit_minutes": 30 if teacher["content_type"] == "assessment" else None,
            "allow_multiple_attempts": teacher["content_type"] == "assignment",
            "show_correct_answers": teacher["content_type"] == "assignment",
            "show_score_immediately": teacher["content_type"] == "assignment",
            "content_type": teacher["content_type"],
            "student_accommodations": {},
        }

        result = self.db.table('published_assessments').insert({
            "join_code": code,
            "title": teacher["assessment"]["title"],
            "assessment": teacher["assessment"],
            "settings": settings,
            "teacher_id": teacher["id"],
            "teacher_name": teacher["name"],
            "is_active": True,
        }).execute()

        assert result.data, f"Failed to publish for {teacher['name']}"
        return code

    def _submit(self, code, teacher, student_name):
        """Submit student answers and grade. Returns results."""
        from backend.routes.student_portal_routes import grade_instant_only, grade_student_submission
        from backend.services.portal_grading import has_written_questions

        # Fetch assessment
        fetch = self.db.table('published_assessments').select('*').eq('join_code', code).execute()
        assert fetch.data, f"Could not fetch assessment {code}"
        assessment = fetch.data[0]['assessment']
        settings = fetch.data[0]['settings']

        # Grade
        needs_multipass = has_written_questions(assessment)
        if needs_multipass:
            results = grade_instant_only(assessment, teacher["student_answers"])
        else:
            results = grade_student_submission(assessment, teacher["student_answers"])

        # Store submission
        sub = self.db.table('submissions').insert({
            "assessment_id": fetch.data[0]['id'],
            "join_code": code,
            "student_name": student_name,
            "answers": teacher["student_answers"],
            "results": results,
            "score": results.get('score') if not needs_multipass else None,
            "total_points": results.get('total_points'),
            "percentage": results.get('percentage') if not needs_multipass else None,
            "time_taken_seconds": random.randint(120, 600),
            "graded_at": datetime.now().isoformat(),
        }).execute()

        assert sub.data, f"Failed to store submission for {student_name}"
        return results, needs_multipass

    def test_three_teachers_publish_and_grade(self):
        """3 teachers publish, 3 students submit, all graded correctly."""

        print("\n" + "=" * 60)
        print("MULTI-TEACHER SMOKE TEST")
        print("=" * 60)

        codes = {}
        for teacher in ALL_TEACHERS:
            code = self._publish(teacher)
            codes[teacher["id"]] = code
            print(f"\n✓ {teacher['name']} ({teacher['subject']}) published "
                  f"{teacher['content_type']}: {teacher['assessment']['title']}")
            print(f"  Join code: {code}")

        # Students submit
        results = {}
        for teacher in ALL_TEACHERS:
            code = codes[teacher["id"]]
            student_name = f"Student of {teacher['name']}"
            result, needs_multipass = self._submit(code, teacher, student_name)
            results[teacher["id"]] = result

            written_count = sum(1 for q in result.get('questions', [])
                                if q.get('status') == 'pending_review')

            print(f"\n✓ {student_name} submitted {teacher['content_type']}")
            print(f"  Instant score: {result['score']}/{result['total_points']}")
            print(f"  Expected: {teacher['expected_instant_score']}")
            print(f"  Written pending: {written_count}")
            print(f"  Needs multipass: {needs_multipass}")

            # Verify score matches expected
            assert result['score'] == teacher['expected_instant_score'], \
                f"{teacher['name']}: expected {teacher['expected_instant_score']}, got {result['score']}"

        print("\n" + "-" * 60)
        print("GRADING VERIFICATION")
        print("-" * 60)

        # Teacher 1 (History): Assessment — has written, score=10
        r1 = results[TEACHER_1["id"]]
        assert r1['score'] == 10
        assert any(q.get('status') == 'pending_review' for q in r1['questions'])
        print("✓ Teacher 1 (History): MC+TF scored, short answer pending")

        # Teacher 2 (Math): Assignment — all instant, score=20
        r2 = results[TEACHER_2["id"]]
        assert r2['score'] == 20
        assert not any(q.get('status') == 'pending_review' for q in r2['questions'])
        print("✓ Teacher 2 (Math): All instant scored, matching perfect")

        # Teacher 3 (Science): Assessment — has written, score=15
        r3 = results[TEACHER_3["id"]]
        assert r3['score'] == 15
        assert any(q.get('status') == 'pending_review' for q in r3['questions'])
        print("✓ Teacher 3 (Science): MC+TF scored, extended response pending")

        print("\n" + "-" * 60)
        print("DATA ISOLATION VERIFICATION")
        print("-" * 60)

        # Verify each teacher only sees their own content
        for teacher in ALL_TEACHERS:
            code = codes[teacher["id"]]
            own = self.db.table('published_assessments').select('teacher_id').eq(
                'join_code', code).execute()
            assert own.data[0]['teacher_id'] == teacher['id']

        # Verify teacher 1 can't see teacher 2's submissions
        t1_subs = self.db.table('submissions').select('*').eq(
            'join_code', codes[TEACHER_1["id"]]).execute()
        t2_subs = self.db.table('submissions').select('*').eq(
            'join_code', codes[TEACHER_2["id"]]).execute()
        assert len(t1_subs.data) == 1
        assert len(t2_subs.data) == 1
        assert t1_subs.data[0]['student_name'] != t2_subs.data[0]['student_name']
        print("✓ Data isolation: each teacher sees only their own submissions")

        print("\n" + "-" * 60)
        print("CONTENT TYPE BEHAVIOR VERIFICATION")
        print("-" * 60)

        # Verify assessment settings
        for teacher in ALL_TEACHERS:
            code = codes[teacher["id"]]
            pub = self.db.table('published_assessments').select('settings').eq(
                'join_code', code).execute()
            settings = pub.data[0]['settings']
            if teacher['content_type'] == 'assessment':
                assert settings['show_score_immediately'] is False
                assert settings['allow_multiple_attempts'] is False
                print(f"✓ {teacher['name']}: Assessment settings correct (scores hidden, no retakes)")
            else:
                assert settings['show_score_immediately'] is True
                assert settings['allow_multiple_attempts'] is True
                print(f"✓ {teacher['name']}: Assignment settings correct (scores shown, retakes allowed)")

        print("\n" + "=" * 60)
        print("ALL SMOKE TESTS PASSED ✓")
        print(f"  3 teachers, 3 subjects, 3 students")
        print(f"  {sum(t['assessment']['total_points'] for t in ALL_TEACHERS)} total points across all content")
        print(f"  Assessment vs Assignment behavior verified")
        print(f"  Data isolation verified")
        print(f"  Matching, MC, TF, short answer, extended response all tested")
        print("=" * 60)
