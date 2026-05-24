"""Characterization tests for parse_filename (Wave 7 Slice 6 — grader decomposition).

Pins the student-info-from-filename parsing BEFORE moving parse_filename into a new
backend/services/submission_parsing.py (the home for the upcoming file-reader cluster).
Pure (pathlib + string ops — no file I/O despite the domain). Imported via
`assignment_grader` (re-export shim).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import parse_filename


def test_standard_underscore_format():
    assert parse_filename("Eli_Long_Hamilton_Jefferson_Graphic_Organizer.docx") == {
        "first_name": "Eli", "last_name": "Long",
        "assignment_part": "Hamilton_Jefferson_Graphic_Organizer", "lookup_key": "eli long"}


def test_comma_last_first_format():
    assert parse_filename("Deloach, Rylee M._Washington_Stations_Handout.docx") == {
        "first_name": "Rylee", "last_name": "Deloach",
        "assignment_part": "Washington_Stations_Handout", "lookup_key": "rylee deloach"}


def test_apostrophe_stripped_in_lookup_key():
    assert parse_filename("A'kareah_West_Cornell Notes_ Political Parties.docx") == {
        "first_name": "A'kareah", "last_name": "West",
        "assignment_part": "Cornell Notes_ Political Parties", "lookup_key": "akareah west"}


def test_two_part_no_assignment():
    assert parse_filename("Jane_Doe.pdf") == {
        "first_name": "Jane", "last_name": "Doe", "assignment_part": "", "lookup_key": "jane doe"}


def test_unparseable_single_word_fallback():
    assert parse_filename("singleword.txt") == {
        "first_name": "singleword", "last_name": "", "assignment_part": "",
        "lookup_key": "singleword"}
