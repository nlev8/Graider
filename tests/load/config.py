"""
Load test configuration for Graider.
Defines personas, timeouts, and test parameters.
"""
import os

BASE_URL = os.getenv("LOAD_TEST_URL", "http://localhost:3000")
REQUEST_TIMEOUT = 30  # seconds per request
GRADING_TIMEOUT = 300  # seconds for grading poll
POLL_INTERVAL = 0.5  # seconds between status polls
CONCURRENT_TEACHERS = 5
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")

# AI-dependent tests cost money — gate on env var
LIVE_TESTS_ENABLED = bool(os.getenv("OPENAI_API_KEY"))

# Persona definitions
PERSONAS = [
    {
        "id": "teacher-test-001",
        "name": "Ms. Rivera",
        "subject": "Civics",
        "grade": "7",
        "grade_level": "7th Grade",
        "grading_style": "standard",
        "rubric_type": "cornell-notes",
        "state": "FL",
    },
    {
        "id": "teacher-test-002",
        "name": "Mr. Chen",
        "subject": "US History",
        "grade": "8",
        "grade_level": "8th Grade",
        "grading_style": "strict",
        "rubric_type": "standard",
        "state": "FL",
    },
    {
        "id": "teacher-test-003",
        "name": "Dr. Patel",
        "subject": "Mathematics",
        "grade": "6",
        "grade_level": "6th Grade",
        "grading_style": "lenient",
        "rubric_type": "fill-in-blank",
        "state": "FL",
    },
    {
        "id": "teacher-test-004",
        "name": "Mrs. Johnson",
        "subject": "English Language Arts",
        "grade": "7",
        "grade_level": "7th Grade",
        "grading_style": "standard",
        "rubric_type": "standard",
        "state": "FL",
    },
    {
        "id": "teacher-test-005",
        "name": "Coach Williams",
        "subject": "Science",
        "grade": "8",
        "grade_level": "8th Grade",
        "grading_style": "strict",
        "rubric_type": "standard",
        "state": "FL",
    },
]
