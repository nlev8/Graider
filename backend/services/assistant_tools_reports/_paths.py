"""Module-level filesystem path constants for the report tools package.

Split out of the former single-file ``assistant_tools_reports`` so both the
package ``__init__`` (public re-export) and ``grades`` (the only function
consumer, via ``PROJECT_ROOT``) can share them without a circular import.
"""
import os

# Constants
CREDS_FILE = os.path.expanduser("~/.graider_data/portal_credentials.json")
# One extra dirname() vs. the pre-split module: this file is one directory
# deeper, so four hops (not three) land on the repo root. Value verified
# identical to the original PROJECT_ROOT.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PARENT_CONTACTS_FILE = os.path.expanduser("~/.graider_data/parent_contacts.json")
CALENDAR_FILE = os.path.expanduser("~/.graider_data/teaching_calendar.json")
