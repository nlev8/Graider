"""
Assignment Grader for 6th Grade Social Studies
===============================================
Tailored for Southwestern Middle School

FILE NAMING EXPECTED: FirstName_LastName_AssignmentName.docx
ROSTER FORMAT: "LastName; FirstName" with Student ID and Email columns

FERPA COMPLIANCE:
- Student names are NOT sent to OpenAI's API
- Only assignment content is analyzed for grading
- All student identification stays local on your computer
- OpenAI API data is not used to train models (per their policy)
- Consult your district's policies for AI tool usage

SETUP:
1. pip install openai python-docx openpyxl python-dotenv
2. Create .env file with: OPENAI_API_KEY=your-key-here
3. Update the folder paths below
4. Update the ASSIGNMENT_INSTRUCTIONS for each assignment
"""

import os
import csv
import json
import re
import random
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import student history for personalized feedback
try:
    from backend.student_history import build_history_context
except ImportError:
    # Fallback if running standalone or module not available
    def build_history_context(student_id):
        return ""

# Import accommodations for IEP/504 support (FERPA compliant)
try:
    from backend.accommodations import build_accommodation_prompt
except ImportError:
    # Fallback if running standalone or module not available
    def build_accommodation_prompt(student_id):
        return ""

# Load environment variables from .env file (override system env vars)
import os
app_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(app_dir, '.env'), override=True)

# =============================================================================
# WRITING STYLE ANALYSIS - For AI Detection
# =============================================================================

def analyze_writing_style(text: str) -> dict:
    """
    Analyze writing style metrics from student text.
    Used to build a profile and detect AI-generated content.
    """
    if not text or len(text.strip()) < 20:
        return None

    # Clean text
    clean_text = text.strip()

    # Split into sentences (basic sentence detection)
    sentences = re.split(r'[.!?]+', clean_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]

    # Split into words
    words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
    if len(words) < 5:
        return None

    # Calculate metrics
    avg_word_length = sum(len(w) for w in words) / len(words)
    avg_sentence_length = len(words) / max(len(sentences), 1)

    # Vocabulary complexity (based on word length distribution)
    long_words = [w for w in words if len(w) > 7]
    complex_word_ratio = len(long_words) / len(words)

    # Detect common misspellings (lowercase words that might be proper nouns)
    potential_misspellings = []
    common_misspelled = re.findall(r'\b[a-z]+[A-Z][a-z]*\b|\b[a-z]{2,}\b', clean_text)

    # Check for specific patterns
    uses_contractions = bool(re.search(r"\b(don't|can't|won't|isn't|aren't|doesn't|didn't|wouldn't|couldn't|shouldn't|I'm|you're|they're|we're|it's|that's|what's|there's|here's)\b", clean_text, re.IGNORECASE))

    # Capitalization habits
    proper_caps = len(re.findall(r'\b[A-Z][a-z]+\b', clean_text))
    all_caps = len(re.findall(r'\b[A-Z]{2,}\b', clean_text))

    # Simple vs complex vocabulary indicators
    simple_words = ['the', 'a', 'an', 'is', 'was', 'are', 'were', 'it', 'they', 'he', 'she', 'we', 'you', 'i', 'and', 'but', 'or', 'so', 'because', 'like', 'just', 'really', 'very', 'good', 'bad', 'big', 'small']
    simple_count = sum(1 for w in words if w.lower() in simple_words)
    simple_ratio = simple_count / len(words)

    # Academic/AI indicator words
    academic_words = ['furthermore', 'therefore', 'consequently', 'however', 'nevertheless', 'moreover', 'subsequently', 'fundamental', 'significant', 'essentially', 'particularly', 'specifically', 'transforming', 'establishing', 'securing', 'trajectory', 'precedent', 'constitutional', 'acquisition', 'vital', 'expansion']
    academic_count = sum(1 for w in words if w.lower() in academic_words)

    # Calculate complexity score (1-10 scale)
    complexity_score = min(10, max(1,
        (avg_word_length - 3) * 1.5 +  # Word length contribution
        (avg_sentence_length / 5) +     # Sentence length contribution
        (complex_word_ratio * 10) +     # Complex words contribution
        (academic_count * 2) -          # Academic words add complexity
        (simple_ratio * 3)              # Simple words reduce complexity
    ))

    return {
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "complex_word_ratio": round(complex_word_ratio, 3),
        "simple_word_ratio": round(simple_ratio, 3),
        "academic_word_count": academic_count,
        "uses_contractions": uses_contractions,
        "complexity_score": round(complexity_score, 2)
    }


def compare_writing_styles(current_style: dict, historical_profile: dict) -> dict:
    """
    Compare current submission's writing style against student's historical profile.
    Returns deviation analysis and AI likelihood.
    """
    if not current_style or not historical_profile:
        return {"deviation": "unknown", "ai_likelihood": "unknown", "reason": "Insufficient data"}

    deviations = []

    # Check complexity score deviation
    hist_complexity = historical_profile.get("avg_complexity_score", 3.0)
    curr_complexity = current_style.get("complexity_score", 3.0)
    complexity_diff = curr_complexity - hist_complexity

    if complexity_diff > 3:
        deviations.append(f"Complexity jumped from {hist_complexity:.1f} to {curr_complexity:.1f}")

    # Check sentence length deviation
    hist_sent_len = historical_profile.get("avg_sentence_length", 8.0)
    curr_sent_len = current_style.get("avg_sentence_length", 8.0)
    sent_len_diff = curr_sent_len - hist_sent_len

    if sent_len_diff > 10:
        deviations.append(f"Sentence length jumped from {hist_sent_len:.1f} to {curr_sent_len:.1f} words")

    # Check for sudden academic vocabulary
    hist_academic = historical_profile.get("avg_academic_words", 0)
    curr_academic = current_style.get("academic_word_count", 0)

    if curr_academic > hist_academic + 2:
        deviations.append(f"Academic vocabulary increased significantly ({curr_academic} vs typical {hist_academic})")

    # Check word length deviation
    hist_word_len = historical_profile.get("avg_word_length", 4.0)
    curr_word_len = current_style.get("avg_word_length", 4.0)

    if curr_word_len - hist_word_len > 1.5:
        deviations.append(f"Word length increased from {hist_word_len:.1f} to {curr_word_len:.1f}")

    # Determine AI likelihood based on deviations
    if len(deviations) >= 3:
        ai_likelihood = "likely"
    elif len(deviations) >= 2:
        ai_likelihood = "possible"
    elif len(deviations) == 1 and complexity_diff > 4:
        ai_likelihood = "possible"
    else:
        ai_likelihood = "none"

    return {
        "deviation": "significant" if len(deviations) >= 2 else "minor" if len(deviations) == 1 else "none",
        "ai_likelihood": ai_likelihood,
        "deviations": deviations,
        "reason": "; ".join(deviations) if deviations else "Writing style consistent with history"
    }


def update_writing_profile(student_id: str, current_style: dict):
    """
    Update student's writing profile with new submission data.
    Maintains running averages across assignments.
    """
    if not current_style or not student_id:
        return

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    history_file = os.path.join(history_dir, f"{student_id}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = {"student_id": student_id, "assignments": []}

        # Get or initialize writing profile
        profile = history.get("writing_profile", {
            "avg_word_length": 0,
            "avg_sentence_length": 0,
            "avg_complexity_score": 0,
            "avg_academic_words": 0,
            "uses_contractions": False,
            "sample_count": 0
        })

        # Update running averages
        n = profile.get("sample_count", 0)
        if n > 0:
            profile["avg_word_length"] = (profile["avg_word_length"] * n + current_style["avg_word_length"]) / (n + 1)
            profile["avg_sentence_length"] = (profile["avg_sentence_length"] * n + current_style["avg_sentence_length"]) / (n + 1)
            profile["avg_complexity_score"] = (profile["avg_complexity_score"] * n + current_style["complexity_score"]) / (n + 1)
            profile["avg_academic_words"] = (profile["avg_academic_words"] * n + current_style["academic_word_count"]) / (n + 1)
        else:
            profile["avg_word_length"] = current_style["avg_word_length"]
            profile["avg_sentence_length"] = current_style["avg_sentence_length"]
            profile["avg_complexity_score"] = current_style["complexity_score"]
            profile["avg_academic_words"] = current_style["academic_word_count"]

        profile["uses_contractions"] = profile.get("uses_contractions", False) or current_style["uses_contractions"]
        profile["sample_count"] = n + 1

        # Round values
        for key in ["avg_word_length", "avg_sentence_length", "avg_complexity_score", "avg_academic_words"]:
            if key in profile:
                profile[key] = round(profile[key], 2)

        history["writing_profile"] = profile

        # Save updated history
        os.makedirs(history_dir, exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        print(f"  ⚠️ Could not update writing profile: {e}")


def get_writing_profile(student_id: str) -> dict:
    """
    Retrieve student's historical writing profile.
    """
    if not student_id:
        return None

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    history_file = os.path.join(history_dir, f"{student_id}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
                return history.get("writing_profile")
    except Exception:
        pass

    return None

# =============================================================================
# CONFIGURATION - UPDATE THESE FOR EACH GRADING SESSION
# =============================================================================

# Folder containing student assignment files (.docx)
ASSIGNMENT_FOLDER = "/Users/alexc/Downloads/Assignments"

# Output folder for CSV and email files
OUTPUT_FOLDER = "/Users/alexc/Downloads/Assignment Grader/Results"

# Path to your student roster Excel file
ROSTER_FILE = "/Users/alexc/Downloads/Assignment Grader/all_students_updated.xlsx"

# Your OpenAI API key (set in .env file or paste here)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

# Assignment name (used in output files and emails)
ASSIGNMENT_NAME = "Cornell Notes - Political Parties"  # UPDATE FOR EACH ASSIGNMENT

# Marker phrase(s) that indicate where student work begins
# Only content within the section (until next header) will be graded
STUDENT_WORK_MARKERS = [
    # Direct task indicators
    "student task",
    "your turn",
    "now you try",
    "student responses below",
    
    # Question indicators
    "answer the question",
    "questions to check understanding",
    "questions / summary",
    
    # Activity types
    "answer the",
    "match",
    "fill-in-the-blank",
    "fill in the blank",
    "write",
    "explain",
    "complete",
    "describe",
    "summarize",
    
    # Analysis & thinking verbs
    "analyze",
    "compare",
    "contrast",
    "evaluate",
    "identify",
    "list",
    "define",
    
    # Application verbs
    "apply",
    "demonstrate",
    "illustrate",
    "predict",
    "solve",
    
    # Creation verbs
    "create",
    "design",
    "develop",
    "construct",
    
    # Reflection indicators
    "final reflection",
    "final reflection question",
    "reflect",
    "think about",
    
    # Learning check indicators
    "let's see what you've learned",
    "lets see what you've learned",
    "let's see what you've learned",  # curly apostrophe version
    "check your understanding",
    "show what you know",
    "practice",
]

# Section headers that indicate a NEW section (stops extraction from previous marker)
SECTION_HEADERS = [
    "vocabulary",
    "vocabulary mini-lesson",
    "key vocabulary",
    "notes",
    "guided notes",
    "reading",
    "directions",
    "instructions",
    "primary source",
    "background",
    "overview",
    "introduction",
]


# =============================================================================
# GRADING RUBRIC - Customize point values and criteria as needed
# =============================================================================

GRADING_RUBRIC = """
You are grading 6th grade Social Studies assignments. Be ENCOURAGING and GENEROUS.
These are 11-12 year old students - grade with appropriate expectations for their age.

IMPORTANT GRADING GUIDELINES:
- For FILL-IN-THE-BLANK exercises: Accept any answer that is factually correct or very close. Spelling mistakes should NOT reduce the grade if the intent is clear.
- Accept reasonable synonyms, alternate phrasings, and partial answers that demonstrate understanding.
- If a student gets the main idea right but uses slightly different wording, give FULL CREDIT.
- Minor spelling errors (like "piler" instead of "pillar") should NOT be penalized.
- Be GENEROUS - when in doubt, give the student the benefit of the doubt.

GRADING SCALE (out of 100 points):

1. CONTENT ACCURACY (40 points)
   - Are the answers factually correct or demonstrate understanding?
   - For fill-in-the-blank: Is the completed statement essentially true?
   - 40 pts: Most answers correct (90%+)
   - 35 pts: Good understanding (80-89% correct)
   - 30 pts: Solid effort (70-79% correct)
   - 25 pts: Some understanding (60-69% correct)
   - 20 pts: Partial understanding (50-59% correct)
   - Below 20: Less than half correct

2. COMPLETENESS (25 points)
   - Did the student attempt ALL questions/blanks?
   - 25 pts: All questions attempted
   - 20 pts: Nearly all attempted (90%+)
   - 15 pts: Most attempted (75%+)
   - 10 pts: About half attempted
   - 5 pts: Less than half attempted

3. WRITING QUALITY (20 points)
   - Is the writing legible and understandable?
   - For fill-in-blank, this is less important - be generous
   - 20 pts: Clear and readable
   - 15 pts: Minor issues but understandable
   - 10 pts: Some difficulty but can figure out meaning
   - 5 pts: Hard to understand

4. EFFORT & ENGAGEMENT (15 points)
   - Did the student put in genuine effort?
   - Are answers thoughtful (not random guesses)?
   - 15 pts: Clear effort shown
   - 10 pts: Good effort
   - 5 pts: Minimal effort
   - 0 pts: No real effort

GRADE RANGES:
- A: 90-100 (Great job!)
- B: 80-89 (Good work!)
- C: 70-79 (Solid effort)
- D: 60-69 (Needs improvement)
- F: Below 60 (Significant concerns)

REMEMBER: These are 6th graders. Be kind, encouraging, and generous with grading.
A student who attempts all questions and gets most right should get an A or B.
"""

# UPDATE THIS FOR EACH ASSIGNMENT
ASSIGNMENT_INSTRUCTIONS = """
CURRENT ASSIGNMENT: Cornell Notes - Political Parties

This is a Cornell Notes assignment about Political Parties in early American history.

Requirements:
1. Main notes section should contain key information about political parties
2. Questions/cue column should have relevant questions
3. Summary at bottom should synthesize the main ideas
4. Content should demonstrate understanding of:
   - Federalists vs Democratic-Republicans
   - Key figures (Hamilton, Jefferson, etc.)
   - Main beliefs and positions of each party
"""


# =============================================================================
# ROSTER LOADING - Reads your Excel student list
# =============================================================================

def load_roster(roster_path: str) -> dict:
    """
    Load student roster from Excel or CSV file.

    Excel format: Student, Student ID, Local ID, Email, Grade, Team
    CSV format: FirstName, LastName, StudentID, Email, Period

    Returns dict mapping "firstname lastname" (lowercase) -> student info
    """
    roster = {}

    if not Path(roster_path).exists():
        print(f"⚠️  Roster file not found: {roster_path}")
        return {}

    roster_path_lower = roster_path.lower()

    # Handle CSV files
    if roster_path_lower.endswith('.csv'):
        import csv
        with open(roster_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try various column name formats
                first_name = row.get('FirstName') or row.get('First Name') or row.get('first_name') or row.get('First') or ''
                last_name = row.get('LastName') or row.get('Last Name') or row.get('last_name') or row.get('Last') or ''
                student_id = row.get('StudentID') or row.get('Student ID') or row.get('student_id') or row.get('ID') or ''
                email = row.get('Email') or row.get('email') or ''
                period = row.get('Period') or row.get('period') or row.get('Class') or ''

                # If Student column exists with "Last; First" format
                if not first_name and not last_name:
                    student_col = row.get('Student') or row.get('Name') or ''
                    if ';' in student_col:
                        parts = student_col.split(';')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''
                    elif ',' in student_col:
                        parts = student_col.split(',')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''

                if not first_name and not last_name:
                    continue

                first_name_simple = first_name.split()[0] if first_name else ''
                lookup_key = f"{first_name_simple} {last_name}".lower().strip()

                roster[lookup_key] = {
                    "student_id": str(student_id),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email or "",
                    "period": str(period) if period else ""
                }

                reverse_key = f"{last_name} {first_name_simple}".lower().strip()
                roster[reverse_key] = roster[lookup_key]

        print(f"📋 Loaded {len(roster)//2} students from CSV roster")
        return roster

    # Handle Excel files
    try:
        import openpyxl
    except ImportError:
        print("❌ openpyxl not installed. Run: pip install openpyxl")
        return {}

    wb = openpyxl.load_workbook(roster_path)
    sheet = wb.active

    # Get header row to find column indices
    headers = [str(cell.value).lower() if cell.value else '' for cell in sheet[1]]

    # Try to find period column
    period_col = None
    for i, h in enumerate(headers):
        if 'period' in h or 'class' in h or 'team' in h:
            period_col = i
            break

    # Skip header row
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue

        student_name = row[0]
        student_id = row[1]
        email = row[3] if len(row) > 3 else ''
        period = row[period_col] if period_col is not None and len(row) > period_col else ''

        if ';' in str(student_name):
            parts = str(student_name).split(';')
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ""
            first_name_simple = first_name.split()[0] if first_name else ""
        else:
            last_name = str(student_name)
            first_name = ""
            first_name_simple = ""

        lookup_key = f"{first_name_simple} {last_name}".lower().strip()

        roster[lookup_key] = {
            "student_id": str(student_id),
            "student_name": f"{first_name} {last_name}".strip(),
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
            "period": str(period) if period else ""
        }

        reverse_key = f"{last_name} {first_name_simple}".lower().strip()
        roster[reverse_key] = roster[lookup_key]

    print(f"📋 Loaded {len(roster)//2} students from Excel roster")
    return roster


# =============================================================================
# FILE PARSING - Extract student name from filename
# =============================================================================

def parse_filename(filename: str) -> dict:
    """
    Parse student info from filename.
    
    Expected format: FirstName_LastName_AssignmentName.docx
    Examples:
        A'kareah_West_Cornell Notes_ Political Parties.docx
        Eli_Long_Hamilton_Jefferson_Graphic_Organizer.docx
        Gabriella_Bueno_Cornell Notes – The Louisiana Purchase.docx
    
    Returns: {"first_name": ..., "last_name": ..., "assignment_part": ...}
    """
    # Remove extension
    name = Path(filename).stem
    
    # Split by underscore
    parts = name.split('_')
    
    if len(parts) >= 2:
        first_name = parts[0].strip()
        last_name = parts[1].strip()
        assignment_part = '_'.join(parts[2:]) if len(parts) > 2 else ""
        
        return {
            "first_name": first_name,
            "last_name": last_name,
            "assignment_part": assignment_part,
            "lookup_key": f"{first_name} {last_name}".lower()
        }
    else:
        # Can't parse - return filename as-is
        return {
            "first_name": name,
            "last_name": "",
            "assignment_part": "",
            "lookup_key": name.lower()
        }


def read_docx_file(filepath: str) -> str:
    """
    Read text content from a Word document (.docx) in document order.
    This properly interleaves paragraphs and tables as they appear.
    """
    try:
        from docx import Document
        from docx.document import Document as DocType
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        print("❌ python-docx not installed. Run: pip install python-docx")
        return None

    try:
        doc = Document(filepath)
        full_text = []

        # Iterate through document body elements in order
        # This ensures tables and paragraphs appear in their actual document order
        for element in doc.element.body:
            # Check if it's a paragraph
            if element.tag.endswith('p'):
                para = Paragraph(element, doc)
                if para.text.strip():
                    full_text.append(para.text)
            # Check if it's a table
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        full_text.append(' | '.join(row_text))

        return '\n'.join(full_text)
    except Exception as e:
        print(f"  ⚠️  Error reading file: {e}")
        return None


def read_image_file(filepath: str) -> dict:
    """
    Read an image file and return it as base64 for GPT-4o vision.
    
    Returns dict with:
    - type: "image"
    - data: base64 encoded image
    - media_type: image MIME type
    """
    import base64
    
    filepath = Path(filepath)
    extension = filepath.suffix.lower()
    
    # Map extensions to MIME types
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    if extension not in mime_types:
        print(f"  ⚠️  Unsupported image type: {extension}")
        return None
    
    try:
        with open(filepath, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return {
            "type": "image",
            "data": image_data,
            "media_type": mime_types[extension]
        }
    except Exception as e:
        print(f"  ⚠️  Error reading image: {e}")
        return None


def read_assignment_file(filepath: str) -> dict:
    """
    Read assignment file based on its extension.
    Supports: .docx, .txt, .jpg, .jpeg, .png, .gif, .webp
    
    Returns dict with:
    - type: "text" or "image"
    - content: text content or base64 image data
    """
    filepath = Path(filepath)
    extension = filepath.suffix.lower()
    
    # Text-based files
    if extension == '.docx':
        content = read_docx_file(filepath)
        if content:
            return {"type": "text", "content": content}
        return None
    
    elif extension == '.txt':
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return {"type": "text", "content": f.read()}
        except Exception as e:
            print(f"  ⚠️  Error reading text file: {e}")
            return None
    
    # Image files
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        image_data = read_image_file(filepath)
        if image_data:
            return {
                "type": "image",
                "content": image_data["data"],
                "media_type": image_data["media_type"]
            }
        return None
    
    else:
        print(f"  ⚠️  Unsupported file type: {extension}")
        return None


def extract_student_work(content: str) -> tuple:
    """
    Extract only the student work portions of the document.

    Finds the first student work marker and returns everything after it.
    This ensures we capture student responses without duplicating content.

    Returns: (student_work, markers_found)
    - student_work: The extracted student content (or full content if no marker)
    - markers_found: List of markers that were found
    """
    content_lower = content.lower()

    # Find the earliest marker position
    found_markers = []
    earliest_pos = len(content)
    earliest_marker = None

    for marker in STUDENT_WORK_MARKERS:
        marker_lower = marker.lower()
        pos = content_lower.find(marker_lower)
        if pos != -1:
            if marker not in found_markers:
                found_markers.append(marker)
            if pos < earliest_pos:
                earliest_pos = pos
                earliest_marker = marker

    if not earliest_marker:
        # No markers found - return full content
        return content, []

    # Return everything from the first marker onward
    # Find the line containing the marker and start from there
    line_start = content.rfind('\n', 0, earliest_pos)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1  # Skip the newline character

    student_work = content[line_start:].strip()
    return student_work, found_markers


# =============================================================================
# FERPA COMPLIANCE - PII SANITIZATION
# =============================================================================

import hashlib

def sanitize_pii_for_ai(student_name: str, content: str) -> tuple:
    """
    FERPA Compliance: Remove all Personally Identifiable Information (PII)
    before sending student work to external AI services.

    Returns:
        tuple: (anonymous_id, sanitized_content)
    """
    if not content:
        return "Student_0000", ""

    # Create consistent anonymous identifier from student name
    if student_name:
        hash_val = int(hashlib.md5(student_name.encode()).hexdigest(), 16) % 10000
        anon_id = f"Student_{hash_val:04d}"
    else:
        anon_id = "Student_0000"

    sanitized = content

    # Remove student name variations (first name, last name, full name)
    if student_name:
        name_parts = student_name.split()
        for part in name_parts:
            if len(part) > 2:  # Avoid removing short words like "I" or "A"
                sanitized = re.sub(
                    rf'\b{re.escape(part)}\b',
                    '[STUDENT]',
                    sanitized,
                    flags=re.IGNORECASE
                )

    # Remove Social Security Numbers (XXX-XX-XXXX)
    sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REMOVED]', sanitized)

    # Remove Student ID numbers (7-10 digit numbers that look like IDs)
    sanitized = re.sub(r'\b\d{7,10}\b', '[ID-REMOVED]', sanitized)

    # Remove email addresses
    sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL-REMOVED]', sanitized)

    # Remove phone numbers (various formats)
    sanitized = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE-REMOVED]', sanitized)
    sanitized = re.sub(r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}', '[PHONE-REMOVED]', sanitized)

    # Remove dates that might be birthdates (MM/DD/YYYY, MM-DD-YYYY, etc.)
    # But preserve historical dates (years before 2000 are likely historical)
    sanitized = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-](20\d{2}|19[89]\d)\b', '[DATE-REMOVED]', sanitized)

    # Remove street addresses (basic pattern)
    sanitized = re.sub(
        r'\b\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct|boulevard|blvd|circle|cir|place|pl)\.?\b',
        '[ADDRESS-REMOVED]',
        sanitized,
        flags=re.IGNORECASE
    )

    # Remove zip codes (5 digit or 5+4 format)
    sanitized = re.sub(r'\b\d{5}(-\d{4})?\b', '[ZIP-REMOVED]', sanitized)

    return anon_id, sanitized


def log_pii_sanitization(student_name: str, original_len: int, sanitized_len: int, removals: dict):
    """
    Log PII sanitization actions for audit purposes.
    Does not log actual PII - only counts and types of removals.
    """
    # This could be extended to write to an audit log file
    if any(removals.values()):
        print(f"  🔒 PII sanitized for student submission (removed: {', '.join(k for k, v in removals.items() if v > 0)})")


# =============================================================================
# AI GRADING WITH CLAUDE
# =============================================================================

def grade_assignment(student_name: str, assignment_data: dict, custom_ai_instructions: str = '', grade_level: str = '6', subject: str = 'Social Studies', ai_model: str = 'gpt-4o-mini', student_id: str = None) -> dict:
    """
    Use OpenAI GPT to grade a student assignment.

    FERPA COMPLIANCE: Student name is NOT sent to OpenAI.
    We use "Student" as a placeholder to protect privacy.

    Supports both text and image inputs.

    Parameters:
    - student_name: Name of the student (kept local, not sent to API)
    - assignment_data: dict with "type" ("text" or "image") and "content"
    - custom_ai_instructions: Additional grading instructions from the teacher
    - grade_level: The student's grade level (e.g., '6', '7', '8')
    - subject: The subject being graded (e.g., 'Social Studies', 'English/ELA')
    - ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')

    Returns dict with:
    - score: numeric grade (0-100)
    - letter_grade: A, B, C, D, or F
    - feedback: detailed feedback for the student
    - breakdown: points for each rubric category
    - authenticity_flag: 'clean', 'review', or 'flagged'
    - authenticity_reason: Explanation for flagged or review status
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ openai not installed. Run: pip install openai")
        return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "API not available"}
    
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Check for empty/blank student submissions before sending to API
    content = assignment_data.get("content", "")
    if assignment_data.get("type") == "text" and content:
        import re

        # Method 1: Check for filled-in blanks (text between underscores like ___answer___)
        filled_blanks = re.findall(r'_{2,}([^_\n]+)_{2,}', content)
        filled_blanks = [b.strip() for b in filled_blanks if b.strip() and len(b.strip()) > 1]

        # Method 2: Check for content after colons that isn't just blanks
        # e.g., "Nationalism: the belief that..." vs "Nationalism: ___"
        after_colons = re.findall(r':\s*([^_\n:]{10,})', content)
        after_colons = [a.strip() for a in after_colons if a.strip() and not a.strip().startswith('_')]

        # Method 3: Look for paragraph-length responses (likely written answers)
        paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 50]
        # Filter out paragraphs that are mostly underscores
        real_paragraphs = [p for p in paragraphs if p.count('_') < len(p) * 0.3]

        # Method 4: Count lines that are JUST underscores (blank response lines)
        blank_lines = len(re.findall(r'^[\s_]+$', content, re.MULTILINE))
        total_lines = len([l for l in content.split('\n') if l.strip()])
        blank_ratio = blank_lines / max(total_lines, 1)

        # Method 5: Check for questions followed by no response
        # Look for question patterns and check if there's content after them
        lines = content.split('\n')
        unanswered_questions = []
        question_indices = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            # Check if line is a question (ends with ? or starts with number/bullet or is a vocab term with colon)
            is_question = (
                line_stripped.endswith('?') or
                re.match(r'^\d+[\.\)]\s*\w', line_stripped) or  # "1. Question" or "1) Question"
                re.match(r'^[a-zA-Z][\.\)]\s*\w', line_stripped) or  # "a. Question" or "a) Question"
                (line_stripped.endswith(':') and len(line_stripped) > 5 and '_' not in line_stripped)  # "Nationalism:"
            )
            if is_question and len(line_stripped) > 5:
                question_indices.append(i)

        # Check content between consecutive questions
        for idx, q_idx in enumerate(question_indices):
            line_stripped = lines[q_idx].strip()
            # Determine where the next question starts (or end of document)
            next_q_idx = question_indices[idx + 1] if idx + 1 < len(question_indices) else len(lines)

            # Get content between this question and the next
            content_between = []
            for j in range(q_idx + 1, min(next_q_idx, q_idx + 6)):  # Check up to 5 lines after
                if j < len(lines):
                    between_line = lines[j].strip()
                    # Skip empty lines and lines that are just underscores
                    if between_line and not re.match(r'^[_\s\-\.]+$', between_line):
                        # Check if this line has actual content (not just template markers)
                        if len(between_line) > 3 and between_line.count('_') < len(between_line) * 0.5:
                            content_between.append(between_line)

            # If no substantive content found after this question, mark as unanswered
            if not content_between:
                unanswered_questions.append(line_stripped[:60] + "..." if len(line_stripped) > 60 else line_stripped)

        # Determine if submission is blank
        has_filled_blanks = len(filled_blanks) >= 2
        has_written_responses = len(after_colons) >= 2 or len(real_paragraphs) >= 1
        mostly_blank_lines = blank_ratio > 0.4
        many_unanswered = len(unanswered_questions) >= 3

        is_blank = (not has_filled_blanks and not has_written_responses and mostly_blank_lines) or \
                   (many_unanswered and not has_filled_blanks and not has_written_responses)

        if is_blank:
            print(f"  ⚠️  BLANK/EMPTY SUBMISSION DETECTED")
            print(f"      Filled blanks: {len(filled_blanks)}, Written responses: {len(after_colons)}")
            print(f"      Blank line ratio: {blank_ratio:.1%}, Unanswered questions: {len(unanswered_questions)}")
            return {
                "score": 0,
                "letter_grade": "INCOMPLETE",
                "breakdown": {
                    "content_accuracy": 0,
                    "completeness": 0,
                    "critical_thinking": 0,
                    "communication": 0
                },
                "feedback": f"This assignment appears to be incomplete or blank. {len(unanswered_questions)} question(s) were found without responses. Please complete the assignment and resubmit, or see your teacher if you need help.",
                "student_responses": [],
                "unanswered_questions": unanswered_questions[:10],  # Limit to first 10
                "authenticity_flag": "clean",
                "authenticity_reason": "",
                "skills_demonstrated": {}
            }

    # FERPA: Use anonymous placeholder instead of real student name
    anonymous_name = "Student"
    
    # Build custom instructions section if provided
    custom_section = ''
    if custom_ai_instructions:
        custom_section = f"""
---
TEACHER'S GRADING INSTRUCTIONS (FOLLOW THESE CAREFULLY):
{custom_ai_instructions}
---
"""

    # Build student history context for personalized feedback
    history_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            history_context = build_history_context(student_id)
        except Exception as e:
            print(f"  Note: Could not load student history: {e}")

    # Build accommodation context for IEP/504 students (FERPA compliant)
    # NOTE: Only accommodation TYPE is sent to AI - no student identifying info
    accommodation_context = ''
    if student_id and student_id != "UNKNOWN":
        try:
            accommodation_context = build_accommodation_prompt(student_id)
            if accommodation_context:
                print(f"  Applying accommodations for student")
        except Exception as e:
            print(f"  Note: Could not load accommodations: {e}")

    # Analyze current submission's writing style for AI detection
    writing_style_context = ''
    current_writing_style = None
    style_comparison = None
    if assignment_data.get("type") == "text" and content:
        current_writing_style = analyze_writing_style(content)
        if current_writing_style:
            # Get student's historical writing profile
            historical_profile = get_writing_profile(student_id) if student_id and student_id != "UNKNOWN" else None

            if historical_profile and historical_profile.get("sample_count", 0) >= 2:
                # Compare current vs historical style
                style_comparison = compare_writing_styles(current_writing_style, historical_profile)

                if style_comparison.get("ai_likelihood") in ["likely", "possible"]:
                    print(f"  ⚠️  Writing style deviation detected: {style_comparison.get('deviation')}")
                    writing_style_context = f"""
---
WRITING STYLE ANALYSIS (COMPARE TO STUDENT'S HISTORY):
This student's historical writing profile (based on {historical_profile.get('sample_count', 0)} previous assignments):
- Average complexity score: {historical_profile.get('avg_complexity_score', 'N/A')}/10
- Average sentence length: {historical_profile.get('avg_sentence_length', 'N/A')} words
- Average word length: {historical_profile.get('avg_word_length', 'N/A')} characters
- Typical academic vocabulary: {historical_profile.get('avg_academic_words', 0):.1f} words per submission

Current submission analysis:
- Complexity score: {current_writing_style.get('complexity_score', 'N/A')}/10
- Sentence length: {current_writing_style.get('avg_sentence_length', 'N/A')} words
- Word length: {current_writing_style.get('avg_word_length', 'N/A')} characters
- Academic vocabulary count: {current_writing_style.get('academic_word_count', 0)}

DEVIATION ALERT: {'; '.join(style_comparison.get('deviations', []))}
This suggests possible AI use - be extra vigilant in your authenticity check!
---
"""

    # Map grade level to age range for context
    grade_age_map = {
        'K': '5-6', '1': '6-7', '2': '7-8', '3': '8-9', '4': '9-10', '5': '10-11',
        '6': '11-12', '7': '12-13', '8': '13-14', '9': '14-15', '10': '15-16',
        '11': '16-17', '12': '17-18'
    }
    age_range = grade_age_map.get(str(grade_level), '11-12')

    prompt_text = f"""
{GRADING_RUBRIC}

{ASSIGNMENT_INSTRUCTIONS}
{custom_section}
{accommodation_context}
{history_context}
{writing_style_context}
---

STUDENT CONTEXT:
- Grade Level: {grade_level}
- Subject: {subject}
- Expected Age Range: {age_range} years old

Please grade this student's work.

IMPORTANT - IDENTIFY STUDENT RESPONSES:
The document contains BOTH teacher-provided content (instructions, questions) AND student responses (answers).

Student responses can be in many formats:
- Fill-in-the-blank: text between underscores like ___1803___ or after blanks
- Written answers: paragraphs or sentences after questions
- MATCHING EXERCISES: Numbers written next to terms to match with numbered definitions
  (e.g., if "Judicial Review" has "3" next to it, the student matched it to definition #3)
- Multiple choice: letters or numbers indicating selected answers
- Short answer: brief responses to questions

For MATCHING exercises specifically:
- Look for numbers placed next to vocabulary terms
- The number indicates which definition the student chose
- Grade whether they matched correctly

DO NOT grade the questions/prompts themselves - only grade the STUDENT'S ANSWERS.
List each specific student response you found in the "student_responses" field.

GRADING GUIDELINES:
- Assess EVERY answer the student provided.
- For fill-in-the-blank: check if the answer is factually correct or close enough.
- Accept multiple valid answers and synonyms.
- DO NOT penalize spelling mistakes if the meaning is clear.
- Be age-appropriate - these are grade {grade_level} students ({age_range} years old).
- IMPORTANT: If the teacher provided custom grading instructions above, follow them carefully.

CRITICAL - COMPLETENESS REQUIREMENTS:
- CAREFULLY check if the student answered ALL parts of the assignment, especially:
  * "Explain in your own words" sections - these require written responses, not blank
  * "Reflection" or "Final Reflection" questions - these MUST be answered
  * "Student Task" sections - these are major components requiring written responses
  * Any prompt asking students to "Write a few sentences" or "Describe" or "Explain"
  * Summary sections at the end of notes/readings
  * Primary source analysis tasks
- Written response sections (reflections, explanations, analysis tasks) are worth as much as fill-in-the-blanks!
- STRICT GRADE CAPS FOR INCOMPLETE WORK:
  * Skipping 1 major written section = maximum score 80 (B-)
  * Skipping 2 major written sections = maximum score 70-75 (C)
  * Skipping 3+ major written sections = maximum score 65 or lower (D)
  * If student only did fill-in-the-blanks and skipped ALL written responses = maximum 70 (C)
- An "A" grade (90+) is ONLY possible if ALL sections are completed with quality responses
- Calculate the final score by considering what percentage of the assignment was actually completed
- List ALL skipped/unanswered questions in the "unanswered_questions" field

CRITICAL - AUTHENTICITY CHECKS (YOU MUST CHECK THIS CAREFULLY!):

1. AI DETECTION - Compare the student's simple answers to their written paragraphs:
STEP 1: Look at their short answers (fill-in-blanks, one-word responses). Note the vocabulary level.
STEP 2: Look at their paragraph responses. Compare the vocabulary and complexity.
STEP 3: If there's a MISMATCH (simple short answers but sophisticated paragraphs), flag as "likely" AI.

AUTOMATIC "likely" AI FLAGS - if you see ANY of these phrases, it's 100% AI:
- "transformed the nation into a continental power"
- "transforming a limited mission"
- "historic deal that doubled"
- "fueling westward expansion"
- "triggered intense political debates"
- "spurred exploration"
- "fundamentally altered the trajectory"
- "establishing the precedent for"
- "constitutional questions regarding federal authority"
- "resonate through subsequent decades"
- "vital for trade and growth"
- "securing vital trade routes"
- "manifest destiny"
- "territorial expansion"
- "abundant natural resources"
- Any phrase starting with "Transforming...", "Establishing...", "Securing..."
- Any phrase a {age_range} year old would NEVER write

CRITICAL CONTRAST CHECK - THIS IS THE MOST IMPORTANT CHECK:
Look at the student's spelling and grammar in simple answers. If they write:
- Misspellings like "Tomas Jefferson", "the u's", "france" (lowercase)
- Simple phrases like "It doubled in size", "idk"
- Basic vocabulary and short sentences

BUT THEN write sophisticated phrases like:
- "Transforming a limited mission to buy New Orleans into a historic deal"
- Any sentence with words like "vital", "securing", "expanding", "historic deal"

That is 100% AI or copied - flag as "likely" IMMEDIATELY. A student who misspells "Thomas" does NOT write "transforming a limited mission into a historic deal."

Real grade {grade_level} students write: "it made the US bigger", "they needed the river for boats", "so ships could go there"
AI writes: "it transformed the nation into a continental power", "securing vital trade routes"

2. PLAGIARISM DETECTION - Look for:
- SUDDEN SHIFTS in writing quality (simple answers + sophisticated paragraphs = copied/AI)
- Textbook-perfect definitions that don't match the student's other answers
- Phrases that sound memorized or copied verbatim
- Statistics or specific numbers not in the reading (like "828,000 square miles")

HARD CAPS FOR AI USE / PLAGIARISM (apply FIRST, before other caps):
- AI flag "likely" = MAX score is 50 (F) - this is cheating
- AI flag "possible" = MAX score is 65 (D) - suspicious, needs verification
- Plagiarism flag "likely" = MAX score is 50 (F) - this is cheating
- Plagiarism flag "possible" = MAX score is 65 (D) - suspicious
- If BOTH AI and plagiarism are flagged = MAX score is 40 (F)

In feedback for AI/plagiarism flags:
- Clearly state the work appears to be AI-generated or copied
- Explain that academic integrity is important
- Recommend the student redo the assignment in their own words
- Note this will be reviewed by the teacher

THEN apply HARD CAPS FOR INCOMPLETE WORK:
- 0 sections skipped = score based on quality (up to 100, unless AI/plagiarism capped)
- 1 skipped = MAX score is 80
- 2 skipped = MAX score is 72
- 3+ skipped = MAX score is 65

The LOWEST cap wins. Example: AI "likely" (cap 50) + 1 section skipped (cap 80) = final cap is 50.

Provide your response in the following JSON format ONLY (no other text):
{{
    "score": <number 0-100, but CAPPED per rules above - AI/plagiarism caps take priority>,
    "letter_grade": "<A, B, C, D, or F - must match the capped score>",
    "breakdown": {{
        "content_accuracy": <points out of 40 - correctness of answers>,
        "completeness": <points out of 25 - ALL sections must be attempted. Written responses (reflections, explanations, Student Tasks) count heavily! 0-5 if 2+ major sections skipped, 6-12 if 1 major section skipped, 13-20 if minor gaps only, 21-25 only if ALL parts fully completed>,
        "writing_quality": <points out of 20>,
        "effort_engagement": <points out of 15>
    }},
    "student_responses": ["<list each student answer you found, e.g. '1803', 'France', 'It helped trade...' etc>"],
    "unanswered_questions": ["<list ALL questions/sections the student left blank or didn't answer - especially written response sections like reflections, explanations, summaries>"],
    "excellent_answers": ["<Quote 2-4 specific answers that were particularly strong, accurate, or showed great understanding. Include the exact text the student wrote.>"],
    "needs_improvement": ["<Quote 1-3 specific answers that were incorrect or incomplete, along with what the correct/better answer would be. Format: 'You wrote [X] but [correct info]' or 'For the question about [topic], [guidance]'>"],
    "skills_demonstrated": {{
        "strengths": ["<List 2-4 specific skills the student showed strength in. Go BEYOND the rubric categories - identify skills like: reading comprehension, critical thinking, source analysis, making connections, vocabulary usage, following directions, organization, creativity, historical thinking, cause-and-effect reasoning, comparing/contrasting, using evidence, drawing conclusions, summarizing, note-taking, attention to detail, etc. Only include skills clearly demonstrated in THIS assignment.>"],
        "developing": ["<List 1-2 skills the student is still developing or struggled with. Same skill types as above. Be specific about what skill needs work based on their answers.>"]
    }},
    "ai_detection": {{
        "flag": "<none, unlikely, possible, or likely>",
        "confidence": <number 0-100 representing confidence in the assessment>,
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "plagiarism_detection": {{
        "flag": "<none, possible, or likely>",
        "reason": "<Brief explanation if not 'none', otherwise empty string>"
    }},
    "feedback": "<Write 3-4 paragraphs of thorough, personalized feedback that sounds like a real teacher wrote it - warm, encouraging, and specific. IMPORTANT GUIDELINES: 1) VARY your sentence structure and openings - don't start every sentence the same way. Mix short punchy sentences with longer ones. 2) QUOTE specific answers from the student's work when praising them (e.g., 'I loved how you explained that [quote their answer]' or 'Your answer about [topic] - '[their exact words]' - shows real understanding'). 3) When mentioning areas to improve, be gentle and constructive - reference specific questions they struggled with and give them a hint or the right direction. 4) Sound HUMAN - use contractions (you're, that's, I'm), occasional casual phrases ('Nice!', 'Great thinking here'), and vary your enthusiasm. 5) End with genuine encouragement that connects to something specific they did well. 6) Do NOT use the student's name - say 'you' or 'your'. 7) Avoid repetitive phrases like 'Great job!' at the start of every paragraph - mix it up! 8) IF STUDENT HISTORY IS PROVIDED ABOVE: Reference their progress! Mention streaks, acknowledge CONSISTENT SKILLS (e.g., 'Your reading comprehension continues to be a real strength!'), celebrate IMPROVING SKILLS (e.g., 'I notice your critical thinking is getting sharper - great progress!'), and gently encourage SKILLS TO DEVELOP (e.g., 'Keep working on making connections between ideas'). Connect current work to past achievements when relevant. 9) BILINGUAL FEEDBACK: ONLY provide bilingual feedback if the student ACTUALLY WROTE their answers in a non-English language. Do NOT assume language based on the student's name - a Hispanic surname does NOT mean the student needs Spanish feedback. Analyze the ACTUAL TEXT of their responses. If (and ONLY if) the student wrote answers in Spanish, Creole, Portuguese, etc., then provide feedback in BOTH English and their language. Format: [English feedback]\\n\\n---\\n\\n[Traducción / Translation]\\n[Same feedback in student's language].>",
    "student_language": "<Detected language based on the ACTUAL TEXT of student's written responses (not their name): 'english', 'spanish', 'portuguese', 'creole', or other. Default to 'english' unless student clearly wrote in another language>"
}}
"""

    print(f"  🤖 Grading with AI...")

    try:
        # FERPA COMPLIANCE: Sanitize PII from text content before sending to AI
        if assignment_data["type"] == "text":
            original_content = assignment_data['content']
            anon_id, sanitized_content = sanitize_pii_for_ai(student_name, original_content)

            # Log if any PII was removed (for audit trail)
            if sanitized_content != original_content:
                print(f"  🔒 PII sanitized from submission before AI processing")

            # Build the message content based on input type
            full_prompt = prompt_text + f"\n\nSTUDENT'S RESPONSES/WORK:\n{sanitized_content}"
            messages = [{"role": "user", "content": full_prompt}]

        elif assignment_data["type"] == "image":
            # Image-based assignment - use vision
            # Note: Cannot sanitize PII from images, but names are not sent in prompt
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text + "\n\nSTUDENT'S WORK (see attached image):"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{assignment_data['media_type']};base64,{assignment_data['content']}"
                        }
                    }
                ]
            }]
        else:
            return {"score": 0, "letter_grade": "ERROR", "breakdown": {}, "feedback": "Unknown content type"}
        
        response = client.chat.completions.create(
            model=ai_model,  # Configurable: gpt-4o or gpt-4o-mini
            messages=messages,
            max_tokens=1500,
            temperature=0.3
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response (remove markdown code blocks if present)
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines)
            for i in range(len(lines)-1, -1, -1):
                if lines[i].strip() == "```":
                    end = i
                    break
            response_text = '\n'.join(lines[start:end])
        response_text = response_text.strip()
        
        result = json.loads(response_text)

        # Update student's writing profile (only if not flagged as AI)
        # This builds their baseline for future AI detection
        if student_id and student_id != "UNKNOWN" and current_writing_style:
            ai_flag = result.get("ai_detection", {}).get("flag", "none")
            if ai_flag not in ["likely", "possible"]:
                try:
                    update_writing_profile(student_id, current_writing_style)
                    print(f"  📊 Updated writing profile for student")
                except Exception as e:
                    print(f"  Note: Could not update writing profile: {e}")

        # Add style comparison info to result for transparency
        if style_comparison and style_comparison.get("ai_likelihood") in ["likely", "possible"]:
            result["writing_style_deviation"] = style_comparison

        return result

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Error parsing AI response: {e}")
        return {
            "score": 0,
            "letter_grade": "ERROR",
            "breakdown": {},
            "feedback": "Error grading - please review manually."
        }
    except Exception as e:
        print(f"  ⚠️  API error: {e}")
        return {
            "score": 0,
            "letter_grade": "ERROR", 
            "breakdown": {},
            "feedback": f"API error: {e}"
        }


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def generate_email_content(student_info: dict, grade_result: dict, assignment_name: str) -> tuple:
    """
    Generate email subject and body for a student.
    
    Returns: (subject, body)
    """
    first_name = student_info.get('first_name', 'Student').split()[0]  # Just first name
    
    subject = f"Grade for {assignment_name}: {grade_result['letter_grade']}"
    
    body = f"""Hi {first_name},

Here is your grade and feedback for {assignment_name}:

GRADE: {grade_result['score']}/100 ({grade_result['letter_grade']})

FEEDBACK:
{grade_result['feedback']}

If you have any questions about your grade, please see me during class.

- Mr. Crionas US History
"""
    return subject, body


def save_emails_to_folder(grades: list, output_folder: str, teacher_name: str = '', subject: str = '', school_name: str = ''):
    """
    Save emails as individual text files - ONE EMAIL PER STUDENT
    with feedback for ALL their assignments combined.
    """
    email_folder = Path(output_folder) / "emails"
    email_folder.mkdir(parents=True, exist_ok=True)
    
    # Group grades by student
    students = {}
    for grade in grades:
        student_name = grade.get('student_name', 'Unknown')
        if student_name not in students:
            # Get only first name (no middle initial)
            full_first = grade.get('first_name', student_name.split()[0])
            first_only = full_first.split()[0] if full_first else student_name.split()[0]
            students[student_name] = {
                'email': grade.get('email', ''),
                'first_name': first_only,
                'assignments': []
            }
        students[student_name]['assignments'].append(grade)
    
    email_count = 0
    for student_name, data in students.items():
        if not data['email']:
            continue
        
        # Build combined email
        assignments = data['assignments']
        first_name = data['first_name']
        
        # Email subject line
        if len(assignments) == 1:
            email_subject = f"Grade for {assignments[0].get('assignment', 'Assignment')}: {assignments[0]['letter_grade']}"
        else:
            email_subject = f"Grades for {len(assignments)} Assignments"
        
        # Body
        body = f"Hi {first_name},\n\n"
        
        if len(assignments) == 1:
            a = assignments[0]
            body += f"Here is your grade and feedback for {a.get('assignment', 'your assignment')}:\n\n"
            body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
            body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n"
        else:
            body += "Here are your grades and feedback:\n\n"
            for a in assignments:
                assignment_name = a.get('assignment', 'Assignment')
                body += f"{'='*50}\n"
                body += f"📝 {assignment_name}\n"
                body += f"{'='*50}\n"
                body += f"GRADE: {a['score']}/100 ({a['letter_grade']})\n\n"
                body += f"FEEDBACK:\n{a.get('feedback', 'No feedback available.')}\n\n"
        
        body += "\nIf you have any questions about your grades, please see me during class.\n\n"
        signature = teacher_name if teacher_name else "Your Teacher"
        if subject:
            signature += f" {subject}"
        body += f"- {signature}\n"
        
        # Save file
        safe_name = re.sub(r'[^\w\s-]', '', student_name).replace(' ', '_')
        filepath = email_folder / f"{safe_name}_email.txt"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"TO: {data['email']}\n")
            f.write(f"SUBJECT: {email_subject}\n")
            f.write(f"{'='*50}\n\n")
            f.write(body)
        
        email_count += 1
    
    print(f"📧 Saved {email_count} email files to: {email_folder}")


def create_outlook_drafts(grades: list):
    """
    Create draft emails in Outlook desktop app (Windows only).
    This lets you review each email before sending.
    """
    try:
        import win32com.client
    except ImportError:
        print("⚠️  pywin32 not installed. Run: pip install pywin32")
        print("   Falling back to saving emails as files.")
        return False
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        count = 0
        
        for grade in grades:
            if not grade.get('email'):
                continue
                
            subject, body = generate_email_content(grade, grade, ASSIGNMENT_NAME)
            
            mail = outlook.CreateItem(0)  # 0 = mail item
            mail.To = grade['email']
            mail.Subject = subject
            mail.Body = body
            mail.Save()  # Save as draft
            count += 1
        
        print(f"📧 Created {count} draft emails in Outlook")
        return True
        
    except Exception as e:
        print(f"⚠️  Outlook error: {e}")
        return False


# =============================================================================
# CSV EXPORT FOR FOCUS
# =============================================================================

def export_focus_csv(grades: list, output_folder: str, assignment_name: str) -> list:
    """
    Create CSV files formatted for Focus import, SEPARATED BY ASSIGNMENT.
    
    Groups students by the assignment extracted from their filename,
    creates one CSV per assignment type.
    
    Format:
    Student ID,Score,Comment
    1950304,85,"Great job, Jackson! You correctly identified..."
    1956701,92,"Excellent work, Maria!..."
    
    Returns list of created file paths.
    """
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Group grades by assignment
    assignments = {}
    for grade in grades:
        # Extract assignment name from filename (everything after FirstName_LastName_)
        filename = grade.get('filename', '')
        parts = Path(filename).stem.split('_')
        if len(parts) >= 3:
            # Assignment is everything after first two parts (first_last)
            assignment = '_'.join(parts[2:])
        else:
            assignment = "Unknown_Assignment"
        
        # Clean up assignment name for display (replace underscores with spaces)
        assignment = assignment.strip().replace('_', ' ')
        
        if assignment not in assignments:
            assignments[assignment] = []
        assignments[assignment].append(grade)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    created_files = []
    
    print(f"\n  Creating {len(assignments)} separate Focus CSVs by assignment:")
    
    for assignment, assignment_grades in assignments.items():
        # Clean assignment name for filename
        safe_name = re.sub(r'[^\w\s-]', '', assignment).replace(' ', '_')[:50]
        filepath = Path(output_folder) / f"{safe_name}_{timestamp}.csv"
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Column headers: Student ID, Score, Comment
            writer.writerow(['Student ID', 'Score', 'Comment'])
            
            for grade in assignment_grades:
                if grade['student_id'] != "UNKNOWN":
                    # Get student's first name only (no middle initial)
                    full_first = grade.get('first_name', '')
                    first_name = full_first.split()[0] if full_first else ''
                    
                    # Clean up feedback
                    feedback = grade.get('feedback', '')
                    feedback_clean = ' '.join(feedback.split())
                    
                    # Varied natural phrases based on grade
                    score = grade.get('score', 0)
                    
                    if first_name:
                        if score >= 90:
                            openers = [
                                f"Great job, {first_name}!",
                                f"Excellent work, {first_name}!",
                                f"{first_name}, this was fantastic!",
                                f"Well done, {first_name}!",
                                f"{first_name}, you nailed this!"
                            ]
                        elif score >= 80:
                            openers = [
                                f"Nice work, {first_name}!",
                                f"Good job, {first_name}!",
                                f"{first_name}, solid effort here!",
                                f"Well done, {first_name}!",
                                f"{first_name}, this was good work!"
                            ]
                        elif score >= 70:
                            openers = [
                                f"{first_name}, decent effort!",
                                f"Good start, {first_name}!",
                                f"{first_name}, you're on the right track!",
                                f"Keep it up, {first_name}!",
                                f"{first_name}, nice try!"
                            ]
                        else:
                            openers = [
                                f"{first_name}, let's work on this together.",
                                f"{first_name}, I know you can do better!",
                                f"Keep trying, {first_name}!",
                                f"{first_name}, don't give up!",
                                f"{first_name}, let's review this."
                            ]
                        
                        opener = random.choice(openers)
                        comment = f"{opener} {feedback_clean}"
                    else:
                        comment = feedback_clean
                    
                    writer.writerow([
                        grade['student_id'], 
                        grade['score'],
                        comment
                    ])
        
        print(f"    📊 {assignment}: {len(assignment_grades)} students → {filepath.name}")
        created_files.append(str(filepath))
    
    return created_files


def save_to_master_csv(grades: list, output_folder: str):
    """
    Append grades to a master CSV file that tracks ALL grades over time.
    This enables progress tracking across the entire school year.
    
    Columns:
    - Date, Student ID, Student Name, Period, Assignment, Unit, Quarter
    - Overall Score, Letter Grade
    - Content Accuracy, Completeness, Writing Quality, Effort & Engagement
    """
    master_file = Path(output_folder) / "master_grades.csv"
    
    # Check if file exists to determine if we need headers
    file_exists = master_file.exists()
    
    # Determine current quarter based on date
    today = datetime.now()
    month = today.month
    if month >= 8 and month <= 10:
        quarter = "Q1"
    elif month >= 11 or month <= 1:
        quarter = "Q2"
    elif month >= 2 and month <= 4:
        quarter = "Q3"
    else:
        quarter = "Q4"
    
    with open(master_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header if new file
        if not file_exists:
            writer.writerow([
                'Date', 'Student ID', 'Student Name', 'First Name', 'Last Name',
                'Period', 'Assignment', 'Unit', 'Quarter',
                'Overall Score', 'Letter Grade',
                'Content Accuracy', 'Completeness', 'Writing Quality', 'Effort Engagement',
                'Feedback'
            ])
        
        # Write each grade
        for grade in grades:
            if grade.get('student_id') == "UNKNOWN":
                continue
            
            breakdown = grade.get('breakdown', {})
            
            writer.writerow([
                today.strftime('%Y-%m-%d'),
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('first_name', ''),
                grade.get('last_name', ''),
                grade.get('period', ''),
                grade.get('assignment', ''),
                grade.get('unit', ''),
                grade.get('grading_period', quarter),  # Use grading_period from settings, fallback to calculated
                grade.get('score', 0),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', 0),
                breakdown.get('completeness', 0),
                breakdown.get('writing_quality', 0),
                breakdown.get('effort_engagement', 0),
                grade.get('feedback', '')[:500]  # Truncate feedback for CSV
            ])
    
    print(f"📊 Updated master grades file: {master_file}")


def export_detailed_report(grades: list, output_folder: str, assignment_name: str) -> str:
    """
    Create detailed CSV with all grading information for your records.
    """
    safe_name = re.sub(r'[^\w\s-]', '', assignment_name).replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = Path(output_folder) / f"Detailed_Report_{safe_name}_{timestamp}.csv"
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Student ID', 'Student Name', 'Email', 'Assignment', 'Score', 'Letter Grade',
            'Content (40)', 'Completeness (25)', 'Writing (20)', 'Effort (15)',
            'Feedback', 'Filename'
        ])
        
        for grade in grades:
            breakdown = grade.get('breakdown', {})
            writer.writerow([
                grade.get('student_id', ''),
                grade.get('student_name', ''),
                grade.get('email', ''),
                grade.get('assignment', ''),
                grade.get('score', ''),
                grade.get('letter_grade', ''),
                breakdown.get('content_accuracy', ''),
                breakdown.get('completeness', ''),
                breakdown.get('writing_quality', ''),
                breakdown.get('effort_engagement', breakdown.get('critical_thinking', '')),
                grade.get('feedback', ''),
                grade.get('filename', '')
            ])
    
    print(f"📋 Detailed report saved: {filepath}")
    return str(filepath)


# =============================================================================
# MAIN GRADING WORKFLOW
# =============================================================================

def run_grading(
    assignment_folder: str = ASSIGNMENT_FOLDER,
    output_folder: str = OUTPUT_FOLDER,
    roster_file: str = ROSTER_FILE,
    assignment_name: str = ASSIGNMENT_NAME,
    create_outlook_emails: bool = False  # Set True if you have Outlook on Windows
):
    """
    Main function - runs the complete grading workflow.
    
    1. Loads student roster
    2. Reads each .docx file from assignment folder
    3. Grades each assignment with AI
    4. Generates emails (saves to files or creates Outlook drafts)
    5. Creates Focus CSV for grade import
    6. Creates detailed report for your records
    """
    print("=" * 60)
    print("📚 ASSIGNMENT GRADER - 6th Grade Social Studies")
    print("=" * 60)
    print(f"📁 Assignment folder: {assignment_folder}")
    print(f"💾 Output folder: {output_folder}")
    print(f"📝 Assignment: {assignment_name}")
    print()
    
    # Load roster
    roster = load_roster(roster_file)
    
    # Get all .docx files
    assignment_path = Path(assignment_folder)
    if not assignment_path.exists():
        print(f"❌ Assignment folder not found: {assignment_folder}")
        return []
    
    # Find all supported files (docx, txt, and images)
    supported_extensions = ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
    all_files = []
    for ext in supported_extensions:
        all_files.extend(assignment_path.glob(ext))
    
    print(f"📄 Found {len(all_files)} files ({', '.join(supported_extensions)})")
    print()
    
    # Process each file
    all_grades = []
    
    for i, filepath in enumerate(all_files, 1):
        print(f"[{i}/{len(all_files)}] {filepath.name}")
        
        # Parse filename to get student name
        parsed = parse_filename(filepath.name)
        student_name = f"{parsed['first_name']} {parsed['last_name']}"
        lookup_key = parsed['lookup_key']
        
        # Look up student in roster
        if lookup_key in roster:
            student_info = roster[lookup_key].copy()
            print(f"  👤 {student_info['student_name']} (ID: {student_info['student_id']})")
        else:
            # Not found in roster - use parsed name
            student_info = {
                "student_id": "UNKNOWN",
                "student_name": student_name,
                "first_name": parsed['first_name'],
                "last_name": parsed['last_name'],
                "email": ""
            }
            print(f"  👤 {student_name} (⚠️ NOT IN ROSTER)")
        
        # Read file content
        file_data = read_assignment_file(filepath)
        if not file_data:
            print(f"  ❌ Could not read file")
            continue
        
        # Handle based on file type
        markers_found = []
        
        if file_data["type"] == "text":
            # Text-based file - check for markers
            content = file_data["content"]
            
            if len(content.strip()) < 20:
                print(f"  ⚠️  File appears empty ({len(content)} chars)")
                continue
            
            # Extract only the student work portion
            student_work, markers_found = extract_student_work(content)
            
            if markers_found:
                print(f"  📝 Found marker(s): {', '.join(markers_found[:2])}{'...' if len(markers_found) > 2 else ''}")
            else:
                print(f"  ⚠️  NO MARKERS FOUND - Check if student uploaded wrong document!")
                print(f"      → Review manually: {filepath.name}")
            
            if len(student_work.strip()) < 10:
                print(f"  ⚠️  No student work found after marker")
                continue
            
            # Prepare data for grading
            grade_data = {"type": "text", "content": student_work}
        
        elif file_data["type"] == "image":
            # Image file - send entire image to AI for grading
            print(f"  🖼️  Image file - sending to AI for visual grading")
            grade_data = file_data
            markers_found = ["image"]  # Mark as having content
        
        else:
            print(f"  ❌ Unknown file type")
            continue
        
        # Grade with AI
        grade_result = grade_assignment(student_info['student_name'], grade_data)
        
        # Combine all info
        # Extract assignment name from filename
        parts = Path(filepath.name).stem.split('_')
        if len(parts) >= 3:
            assignment_from_file = ' '.join(parts[2:])
        else:
            assignment_from_file = ASSIGNMENT_NAME
        
        grade_record = {
            **student_info,
            **grade_result,
            "filename": filepath.name,
            "assignment": assignment_from_file,
            "has_markers": len(markers_found) > 0
        }
        all_grades.append(grade_record)
        
        print(f"  ✅ Score: {grade_result['score']} ({grade_result['letter_grade']})")
        print()
    
    # Export results
    print("=" * 60)
    print("📊 EXPORTING RESULTS")
    print("=" * 60)
    
    # Focus CSVs (separated by assignment)
    focus_files = export_focus_csv(all_grades, output_folder, assignment_name)
    
    # Detailed report (one file with all grades)
    export_detailed_report(all_grades, output_folder, assignment_name)
    
    # Emails
    if create_outlook_emails:
        if not create_outlook_drafts(all_grades):
            save_emails_to_folder(all_grades, output_folder)
    else:
        save_emails_to_folder(all_grades, output_folder)
    
    # Summary
    print()
    print("=" * 60)
    print("📈 GRADING SUMMARY")
    print("=" * 60)
    
    if all_grades:
        scores = [g['score'] for g in all_grades if g['score'] > 0]
        if scores:
            print(f"Total graded: {len(all_grades)}")
            print(f"Average score: {sum(scores)/len(scores):.1f}")
            print(f"Highest: {max(scores)}")
            print(f"Lowest: {min(scores)}")
            
            # Grade distribution
            grade_dist = {}
            for g in all_grades:
                letter = g['letter_grade']
                grade_dist[letter] = grade_dist.get(letter, 0) + 1
            print(f"Distribution: {dict(sorted(grade_dist.items()))}")
            
            # Per-assignment breakdown
            print(f"\n📚 By Assignment:")
            assignments = {}
            for g in all_grades:
                a = g.get('assignment', 'Unknown')
                if a not in assignments:
                    assignments[a] = []
                assignments[a].append(g['score'])
            
            for assignment, scores_list in sorted(assignments.items()):
                valid_scores = [s for s in scores_list if s > 0]
                if valid_scores:
                    avg = sum(valid_scores) / len(valid_scores)
                    print(f"   • {assignment[:40]}: {len(scores_list)} students, avg {avg:.1f}")
        
        # List students not in roster
        unknown = [g for g in all_grades if g['student_id'] == 'UNKNOWN']
        if unknown:
            print(f"\n⚠️  {len(unknown)} students NOT FOUND in roster:")
            for g in unknown:
                print(f"   - {g['student_name']} ({g['filename']})")
        
        # List documents with no markers (possible wrong uploads)
        no_markers = [g for g in all_grades if not g.get('has_markers', True)]
        if no_markers:
            print(f"\n🚨 {len(no_markers)} documents had NO MARKERS - review for possible wrong uploads:")
            for g in no_markers:
                print(f"   - {g['student_name']}: {g['filename']}")
    
    print()
    print("✅ GRADING COMPLETE!")
    return all_grades


# =============================================================================
# RUN THE SCRIPT
# =============================================================================

if __name__ == "__main__":
    # Update the paths at the top of this file, then run!
    results = run_grading(
        create_outlook_emails=False  # Set True if you have Outlook desktop on Windows
    )
