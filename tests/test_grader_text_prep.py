"""Characterization tests for the pure text-prep helpers
(Wave 7 Slice 2 — assignment_grader.py decomposition).

Pins the EXACT output of sanitize_pii_for_ai (FERPA-critical), preprocess_for_ai_detection,
and log_pii_sanitization BEFORE extracting them into backend/services/grader_text_prep.py.
All pure (regex / hashlib / print — no LLM / network / Flask). Imported via
`assignment_grader` so the tests stay valid through the re-export shim.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import (
    sanitize_pii_for_ai, preprocess_for_ai_detection, log_pii_sanitization)

CONTENT = ("Maria Gonzalez wrote this essay. Contact: maria.g@school.edu or 555-123-4567. "
           "SSN 123-45-6789, ID 1234567. Born 05/12/2010. Lives at 42 Oak Street, 90210. "
           "The Louisiana Purchase happened in 1803.")

SANITIZED_GOLDEN = ("[STUDENT] [STUDENT] wrote this essay. Contact: [STUDENT].[EMAIL-REMOVED] "
                    "or [PHONE-REMOVED]. SSN [SSN-REMOVED], ID [ID-REMOVED]. Born [DATE-REMOVED]. "
                    "Lives at [ADDRESS-REMOVED], [ZIP-REMOVED]. The Louisiana Purchase happened in 1803.")


def test_sanitize_pii_golden():
    anon_id, sanitized = sanitize_pii_for_ai("Maria Gonzalez", CONTENT)
    assert anon_id == "Student_8781"          # stable md5-derived id
    assert sanitized == SANITIZED_GOLDEN       # exact FERPA sanitization


def test_sanitize_pii_empty_content():
    assert sanitize_pii_for_ai("Bob Smith", "") == ("Student_0000", "")


def test_sanitize_pii_no_name_uses_default_id():
    anon_id, _ = sanitize_pii_for_ai("", "Some text with no name 555-123-4567.")
    assert anon_id == "Student_0000"


def test_sanitize_pii_id_is_stable_per_name():
    # same name -> same anon id; different name -> (almost always) different id
    a1, _ = sanitize_pii_for_ai("Maria Gonzalez", "x")
    a2, _ = sanitize_pii_for_ai("Maria Gonzalez", "y")
    assert a1 == a2 == "Student_8781"


def test_preprocess_for_ai_detection_golden():
    txt = ("Q: Why was the Louisiana Purchase important?\n"
           "I think it was important because it doubled the size of the country and gave "
           "farmers more land to grow crops on.\n"
           "The U.S. bought it from France.\n"
           "Vocabulary\n"
           "The year was ____1803____\n")
    assert preprocess_for_ai_detection(txt) == (
        "Student written content:\n"
        "I think it was important because it doubled the size of the country and gave "
        "farmers more land to grow crops on.")


def test_log_pii_sanitization_runs(caplog):
    # audit helper; only logs when something was removed (print→_logger.info on extraction
    # into grader_text_prep.py — services/ is ruff-T20 scanned, so it logs rather than prints).
    import logging
    with caplog.at_level(logging.INFO, logger="backend.services.grader_text_prep"):
        log_pii_sanitization("Maria", 100, 80, {"emails": 1, "phones": 0})
    assert any("PII sanitized" in r.message for r in caplog.records)
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="backend.services.grader_text_prep"):
        log_pii_sanitization("Maria", 100, 100, {"emails": 0, "phones": 0})
    assert not caplog.records  # nothing removed -> no log
