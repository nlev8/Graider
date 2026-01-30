"""
Accommodation Management for Graider
=====================================
FERPA-Compliant IEP/504 Accommodation Support

PRIVACY PROTECTIONS:
1. Accommodation data stored locally only (~/.graider_data/accommodations/)
2. Only accommodation TYPE is sent to AI - never student names or IDs
3. All access is audit logged
4. No cloud sync - data never leaves teacher's computer
5. Minimal data retention - only grading-relevant info stored

Accommodation types are generic categories that tell the AI how to adjust
feedback without revealing any student identity.
"""

import os
import json
from datetime import datetime
from typing import Optional

# Local storage directories
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
ACCOMMODATIONS_DIR = os.path.join(GRAIDER_DATA_DIR, "accommodations")
PRESETS_FILE = os.path.join(ACCOMMODATIONS_DIR, "presets.json")
STUDENT_ACCOMMODATIONS_FILE = os.path.join(ACCOMMODATIONS_DIR, "student_accommodations.json")
AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")

# Ensure directory exists
os.makedirs(ACCOMMODATIONS_DIR, exist_ok=True)


def audit_log_accommodation(action: str, details: str = ""):
    """
    FERPA Compliance: Log all accommodation data access.
    Details are anonymized - no student names in logs.
    """
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | teacher | ACCOMMODATION_{action} | {details}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Audit log error: {e}")


# ══════════════════════════════════════════════════════════════
# DEFAULT ACCOMMODATION PRESETS
# ══════════════════════════════════════════════════════════════

DEFAULT_PRESETS = {
    "simplified_language": {
        "id": "simplified_language",
        "name": "Simplified Language",
        "description": "Use shorter sentences, simpler vocabulary, and clear structure",
        "icon": "MessageSquare",
        "ai_instructions": """ACCOMMODATION - SIMPLIFIED LANGUAGE:
- Use short, clear sentences (10-15 words max)
- Avoid complex vocabulary - use common words
- Break feedback into numbered steps or bullet points
- One idea per sentence
- Use concrete examples rather than abstract concepts
- Repeat key points for reinforcement"""
    },
    "effort_focused": {
        "id": "effort_focused",
        "name": "Effort-Focused",
        "description": "Emphasize effort, participation, and improvement over perfection",
        "icon": "Heart",
        "ai_instructions": """ACCOMMODATION - EFFORT-FOCUSED FEEDBACK:
- Lead with genuine praise for effort shown
- Celebrate any attempt, even if incorrect
- Focus on growth and improvement, not just accuracy
- Use phrases like "I can see you worked hard on..." and "You're making progress with..."
- Frame corrections as "next steps" rather than mistakes
- End with encouragement about continued effort"""
    },
    "extra_encouragement": {
        "id": "extra_encouragement",
        "name": "Extra Encouragement",
        "description": "More positive reinforcement and supportive tone",
        "icon": "Star",
        "ai_instructions": """ACCOMMODATION - EXTRA ENCOURAGEMENT:
- Start with a specific, genuine compliment
- Use warm, supportive language throughout
- For every area to improve, include two positives
- Use encouraging phrases: "You're on the right track!", "Keep going!", "Great effort!"
- Acknowledge challenges and praise persistence
- End with a motivating statement about their potential"""
    },
    "chunked_feedback": {
        "id": "chunked_feedback",
        "name": "Chunked Feedback",
        "description": "Break feedback into small, manageable sections",
        "icon": "List",
        "ai_instructions": """ACCOMMODATION - CHUNKED FEEDBACK:
- Organize feedback into clearly labeled sections
- Use headers: "What You Did Well:", "Areas to Improve:", "Next Steps:"
- Keep each section to 2-3 bullet points maximum
- Use numbered lists for action items
- Leave white space between sections
- Avoid long paragraphs - maximum 2 sentences per point"""
    },
    "modified_expectations": {
        "id": "modified_expectations",
        "name": "Modified Expectations",
        "description": "Adjust grading focus to core content over presentation",
        "icon": "Sliders",
        "ai_instructions": """ACCOMMODATION - MODIFIED EXPECTATIONS:
- Focus grading on CONTENT understanding, not presentation
- Do NOT penalize for spelling, grammar, or punctuation errors
- Do NOT penalize for handwriting quality or formatting
- Grade based on whether the student demonstrates understanding of concepts
- Partial credit for showing thought process, even if answer is incomplete
- Value effort and attempt over polish"""
    },
    "visual_structure": {
        "id": "visual_structure",
        "name": "Visual Structure",
        "description": "Use clear visual organization with headers and spacing",
        "icon": "Layout",
        "ai_instructions": """ACCOMMODATION - VISUAL STRUCTURE:
- Use clear section headers in ALL CAPS or bold
- Add blank lines between sections
- Use bullet points and numbered lists
- Avoid dense paragraphs
- Use symbols for emphasis: ✓ for correct, → for next steps
- Keep consistent formatting throughout"""
    },
    "read_aloud_friendly": {
        "id": "read_aloud_friendly",
        "name": "Read-Aloud Friendly",
        "description": "Write feedback that works well when read aloud",
        "icon": "Volume2",
        "ai_instructions": """ACCOMMODATION - READ-ALOUD FRIENDLY:
- Write in natural, conversational language
- Avoid abbreviations - write out full words
- Use complete sentences that flow when spoken
- Avoid complex punctuation (semicolons, em dashes)
- Include verbal cues: "First...", "Next...", "Finally..."
- Keep sentences under 20 words for easy reading"""
    },
    "growth_mindset": {
        "id": "growth_mindset",
        "name": "Growth Mindset",
        "description": "Frame all feedback around learning and growth",
        "icon": "TrendingUp",
        "ai_instructions": """ACCOMMODATION - GROWTH MINDSET FEEDBACK:
- Use "yet" language: "You haven't mastered this YET"
- Praise process and strategy, not just results
- Frame mistakes as learning opportunities
- Emphasize that skills develop with practice
- Use phrases like "You're building your skills in..."
- Connect effort to improvement: "Your practice is paying off!"
- Avoid fixed-ability language ("You're smart/not smart")"""
    },
    # ══════════════════════════════════════════════════════════════
    # ELL (English Language Learner) ACCOMMODATION
    # Note: Bilingual feedback is automatic when student writes in another language
    # ══════════════════════════════════════════════════════════════
    "ell_support": {
        "id": "ell_support",
        "name": "ELL Support",
        "description": "Simplified English, no grammar penalties for ELL students",
        "icon": "Globe",
        "ai_instructions": """ACCOMMODATION - ELL (English Language Learner) SUPPORT:
- Use basic, high-frequency vocabulary only
- Keep sentences very short (8-10 words max)
- Avoid idioms, slang, and figurative language
- Use present tense when possible
- Repeat key academic vocabulary with definitions
- Use simple subject-verb-object sentence structure
- Provide context clues for new words
- Do NOT penalize for grammar or spelling errors related to language learning
- Do NOT penalize for L1-influenced patterns (missing articles, verb tense, word order)
- Focus grading on CONTENT understanding, not language accuracy
- Celebrate effort and participation
- Note: Bilingual feedback is provided automatically when student writes in another language"""
    }
}


# ══════════════════════════════════════════════════════════════
# PRESET MANAGEMENT
# ══════════════════════════════════════════════════════════════

def load_presets() -> dict:
    """Load accommodation presets (defaults + any custom ones)."""
    presets = DEFAULT_PRESETS.copy()

    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r') as f:
                custom = json.load(f)
                # Merge custom presets (can override defaults)
                presets.update(custom)
        except Exception as e:
            print(f"Error loading custom presets: {e}")

    audit_log_accommodation("LOAD_PRESETS", f"Loaded {len(presets)} presets")
    return presets


def save_preset(preset: dict) -> bool:
    """Save a custom accommodation preset."""
    try:
        presets = {}
        if os.path.exists(PRESETS_FILE):
            with open(PRESETS_FILE, 'r') as f:
                presets = json.load(f)

        preset_id = preset.get('id', preset.get('name', '').lower().replace(' ', '_'))
        preset['id'] = preset_id
        presets[preset_id] = preset

        with open(PRESETS_FILE, 'w') as f:
            json.dump(presets, f, indent=2)

        audit_log_accommodation("SAVE_PRESET", f"Saved preset: {preset_id}")
        return True
    except Exception as e:
        print(f"Error saving preset: {e}")
        return False


def delete_preset(preset_id: str) -> bool:
    """Delete a custom preset (cannot delete defaults)."""
    if preset_id in DEFAULT_PRESETS:
        return False  # Cannot delete default presets

    try:
        if os.path.exists(PRESETS_FILE):
            with open(PRESETS_FILE, 'r') as f:
                presets = json.load(f)

            if preset_id in presets:
                del presets[preset_id]
                with open(PRESETS_FILE, 'w') as f:
                    json.dump(presets, f, indent=2)

                audit_log_accommodation("DELETE_PRESET", f"Deleted preset: {preset_id}")
                return True
        return False
    except Exception as e:
        print(f"Error deleting preset: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# STUDENT ACCOMMODATION MAPPING
# ══════════════════════════════════════════════════════════════

def load_student_accommodations() -> dict:
    """
    Load student-to-accommodation mappings.
    Returns dict: {student_id: {"presets": [...], "custom_notes": "..."}}

    FERPA Note: Student IDs are stored locally only and never sent to AI.
    """
    if os.path.exists(STUDENT_ACCOMMODATIONS_FILE):
        try:
            with open(STUDENT_ACCOMMODATIONS_FILE, 'r') as f:
                data = json.load(f)
            audit_log_accommodation("LOAD_STUDENT_MAPPINGS", f"Loaded {len(data)} student mappings")
            return data
        except Exception as e:
            print(f"Error loading student accommodations: {e}")

    return {}


def save_student_accommodations(mappings: dict) -> bool:
    """Save student-to-accommodation mappings."""
    try:
        with open(STUDENT_ACCOMMODATIONS_FILE, 'w') as f:
            json.dump(mappings, f, indent=2)

        audit_log_accommodation("SAVE_STUDENT_MAPPINGS", f"Saved {len(mappings)} student mappings")
        return True
    except Exception as e:
        print(f"Error saving student accommodations: {e}")
        return False


def set_student_accommodation(student_id: str, preset_ids: list, custom_notes: str = "") -> bool:
    """
    Assign accommodation presets to a student.

    Args:
        student_id: The student's ID (stored locally only)
        preset_ids: List of preset IDs to apply
        custom_notes: Additional custom accommodation notes
    """
    mappings = load_student_accommodations()

    mappings[student_id] = {
        "presets": preset_ids,
        "custom_notes": custom_notes,
        "updated": datetime.now().isoformat()
    }

    audit_log_accommodation("SET_STUDENT_ACCOMMODATION",
                           f"Student {student_id[:6]}... assigned {len(preset_ids)} presets")
    return save_student_accommodations(mappings)


def get_student_accommodation(student_id: str) -> Optional[dict]:
    """Get accommodation settings for a specific student."""
    if not student_id or student_id == "UNKNOWN":
        return None

    mappings = load_student_accommodations()
    accommodation = mappings.get(student_id)

    if accommodation:
        audit_log_accommodation("GET_STUDENT_ACCOMMODATION",
                               f"Retrieved accommodation for {student_id[:6]}...")

    return accommodation


def remove_student_accommodation(student_id: str) -> bool:
    """Remove accommodation settings for a student."""
    mappings = load_student_accommodations()

    if student_id in mappings:
        del mappings[student_id]
        audit_log_accommodation("REMOVE_STUDENT_ACCOMMODATION",
                               f"Removed accommodation for {student_id[:6]}...")
        return save_student_accommodations(mappings)

    return False


# ══════════════════════════════════════════════════════════════
# AI PROMPT GENERATION (FERPA-COMPLIANT)
# ══════════════════════════════════════════════════════════════

def build_accommodation_prompt(student_id: str) -> str:
    """
    Build AI prompt instructions for a student's accommodations.

    FERPA COMPLIANCE:
    - This function returns ONLY accommodation instructions
    - NO student identifying information is included
    - The AI sees "Apply these accommodations:" not "John Smith needs..."

    Returns:
        String with accommodation instructions for AI prompt, or empty string if none.
    """
    if not student_id or student_id == "UNKNOWN":
        return ""

    accommodation = get_student_accommodation(student_id)
    if not accommodation:
        return ""

    presets = load_presets()
    preset_ids = accommodation.get("presets", [])
    custom_notes = accommodation.get("custom_notes", "")

    if not preset_ids and not custom_notes:
        return ""

    # Build the prompt - NO student info included
    prompt_parts = [
        "",
        "═══════════════════════════════════════════════════════════",
        "ACCOMMODATION INSTRUCTIONS (Apply to all feedback below)",
        "═══════════════════════════════════════════════════════════",
        ""
    ]

    # Add preset instructions
    for preset_id in preset_ids:
        if preset_id in presets:
            preset = presets[preset_id]
            prompt_parts.append(preset.get("ai_instructions", ""))
            prompt_parts.append("")

    # Add custom notes if any
    if custom_notes:
        prompt_parts.append("ADDITIONAL ACCOMMODATION NOTES:")
        prompt_parts.append(custom_notes)
        prompt_parts.append("")

    prompt_parts.append("═══════════════════════════════════════════════════════════")
    prompt_parts.append("")

    audit_log_accommodation("BUILD_PROMPT",
                           f"Built prompt with {len(preset_ids)} presets for grading")

    return "\n".join(prompt_parts)


# ══════════════════════════════════════════════════════════════
# ROSTER IMPORT WITH ACCOMMODATIONS
# ══════════════════════════════════════════════════════════════

def import_accommodations_from_csv(csv_data: list, id_col: str, accommodation_col: str,
                                   notes_col: str = None) -> dict:
    """
    Import student accommodations from CSV data.

    Args:
        csv_data: List of dicts from CSV reader
        id_col: Column name for student ID
        accommodation_col: Column name for accommodation type/presets
        notes_col: Optional column for custom notes

    Returns:
        Dict with import statistics
    """
    presets = load_presets()
    preset_names = {p['name'].lower(): p['id'] for p in presets.values()}

    imported = 0
    skipped = 0

    for row in csv_data:
        student_id = row.get(id_col, '').strip()
        if not student_id:
            skipped += 1
            continue

        accommodation_value = row.get(accommodation_col, '').strip()
        custom_notes = row.get(notes_col, '').strip() if notes_col else ""

        if not accommodation_value and not custom_notes:
            skipped += 1
            continue

        # Parse accommodation value - could be comma-separated presets
        preset_ids = []
        for item in accommodation_value.split(','):
            item = item.strip().lower()
            if item in preset_names:
                preset_ids.append(preset_names[item])
            elif item:
                # Unknown preset name - add to custom notes
                if custom_notes:
                    custom_notes += f"; {item}"
                else:
                    custom_notes = item

        set_student_accommodation(student_id, preset_ids, custom_notes)
        imported += 1

    audit_log_accommodation("IMPORT_FROM_CSV", f"Imported {imported}, skipped {skipped}")

    return {
        "imported": imported,
        "skipped": skipped,
        "total": len(csv_data)
    }


# ══════════════════════════════════════════════════════════════
# DATA MANAGEMENT (FERPA COMPLIANCE)
# ══════════════════════════════════════════════════════════════

def export_student_accommodations() -> dict:
    """
    Export all student accommodation data for backup/portability.
    FERPA: Data stays local, this is for teacher's own backup.
    """
    audit_log_accommodation("EXPORT_DATA", "Exported all student accommodation data")
    return load_student_accommodations()


def clear_all_accommodations() -> bool:
    """
    Clear all student accommodation data.
    FERPA: Supports data deletion requirements.
    """
    try:
        if os.path.exists(STUDENT_ACCOMMODATIONS_FILE):
            os.remove(STUDENT_ACCOMMODATIONS_FILE)

        audit_log_accommodation("CLEAR_ALL_DATA", "Deleted all student accommodation data")
        return True
    except Exception as e:
        print(f"Error clearing accommodations: {e}")
        return False


def get_accommodation_stats() -> dict:
    """Get statistics about accommodation usage."""
    mappings = load_student_accommodations()
    presets = load_presets()

    preset_usage = {}
    for student_data in mappings.values():
        for preset_id in student_data.get("presets", []):
            preset_usage[preset_id] = preset_usage.get(preset_id, 0) + 1

    return {
        "total_students_with_accommodations": len(mappings),
        "preset_count": len(presets),
        "preset_usage": preset_usage
    }
