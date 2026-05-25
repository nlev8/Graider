"""Command-line grading workflow (legacy local-folder batch grading), extracted from the
assignment_grader.py facade. Reads .docx assignments from a folder, grades each via the service
pipeline, and writes CSV + email/report outputs. Wave 8 (CLI/email split pt.2b).

The primary workflow is the browser portal; this is the legacy local CLI. Invoke via
`python assignment_grader.py` (the facade __main__ calls run_grading) or
`python -m backend.services.grader_cli`. Prints are intentional CLI progress output
(grader_cli.py is exempt from ruff T20 in pyproject.toml).
"""
from pathlib import Path

from backend.services.grader_export import (
    create_outlook_drafts,
    export_detailed_report,
    export_focus_csv,
    save_emails_to_folder,
)
from backend.services.grader_roster import load_roster
from backend.services.grading_models import ASSIGNMENT_NAME
from backend.services.grading_pipeline import grade_assignment
from backend.services.response_extraction import extract_student_work
from backend.services.submission_parsing import parse_filename, read_assignment_file

# =============================================================================
# CONFIGURATION — update these local paths for your CLI run
# =============================================================================

# Folder containing student assignment files (.docx)
ASSIGNMENT_FOLDER = "/Users/alexc/Downloads/Assignments"

# Output folder for CSV and email files
OUTPUT_FOLDER = "/Users/alexc/Downloads/Assignment Grader/Results"

# Path to your student roster Excel file
ROSTER_FILE = "/Users/alexc/Downloads/Assignment Grader/all_students_updated.xlsx"


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
    export_focus_csv(all_grades, output_folder, assignment_name)
    
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


if __name__ == "__main__":
    run_grading(create_outlook_emails=False)
