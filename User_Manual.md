# Graider User Manual

## Table of Contents
1. [Getting Started](#getting-started)
2. [Grade Tab - Grading Assignments](#grade-tab---grading-assignments)
3. [Results Tab](#results-tab)
4. [Assignment Builder](#assignment-builder)
5. [Analytics Tab](#analytics-tab)
6. [Lesson Planner](#lesson-planner)
7. [Resources Tab](#resources-tab)
8. [Settings](#settings)
9. [Privacy & FERPA Compliance](#privacy--ferpa-compliance)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Running Graider

```bash
cd /Users/alexc/Downloads/Graider
python graider_app.py
```

The app opens automatically at **http://localhost:3000**

> **Note:** There is NO separate frontend to run. Everything is served by the single Python command.

### First-Time Setup

1. **API Key**: Add your OpenAI API key to `.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

2. **Folders**: In Settings, configure:
   - **Assignments Folder**: Where student submissions are (e.g., OneDrive sync folder)
   - **Output Folder**: Where graded results go
   - **Roster File**: Excel file with student names and emails

3. **Configuration**: Set your:
   - State (for standards alignment)
   - Grade Level
   - Subject

---

## Grade Tab - Grading Assignments

### Activity Monitor

The **Activity Monitor** sits above the Start Grading section and shows real-time progress:
- Click to expand/collapse the activity log
- Shows "Running..." badge when grading is in progress
- Displays entry count
- **Auto-expands when errors occur**

### Error Handling

If the internet goes out or the OpenAI API fails during grading:
- Grading **automatically stops** to prevent incorrect grades
- A **red error banner** appears at the top
- The Activity Monitor auto-expands with error details
- All progress is saved - you can resume after fixing the issue

### Toast Notifications

When assignments are graded, **toast notifications** appear in the bottom-right corner showing:
- Student name
- Letter grade
- Percentage score

**Color coding:**
- Green - A or B grades
- Blue - C grades
- Yellow - D or F grades

To disable toast notifications: **Settings > Notifications > Toast Notifications**

### Basic Grading

1. Click **Start Grading**
2. Graider processes all files in your Assignments Folder
3. Each file is read, analyzed by AI, and scored
4. Results appear in the Activity Monitor and Results tab

### Using Assignment Configs

If you have saved assignment configurations (from the Builder):

1. Select your assignment from the **Assignment Config** dropdown
2. Your custom markers and AI notes will be used
3. Click **Start Grading**

### Auto-Grade Mode

Toggle **Auto-Grade Mode** to:
- Automatically watch for new files
- Grade them as soon as they appear
- Perfect for OneDrive/SharePoint sync

---

## Results Tab

### Results Table

View all graded assignments with columns:
- **Student** - Student name
- **Assignment** - File name
- **Time** - Date and time graded
- **Score** - Percentage score
- **Grade** - Letter grade (color-coded)
- **Authenticity** - AI and plagiarism detection status
- **Email** - Email status
- **Actions** - View/edit options

### Authenticity Detection

Each result shows two separate indicators:

**AI Detection:**
- **Clear** (green) - No AI-generated content detected
- **Unlikely** (blue) - Low likelihood of AI use
- **Possible** (yellow) - Some indicators of AI assistance
- **Likely** (red) - Strong indicators of AI-generated content
- Shows confidence percentage when available

**Plagiarism Detection:**
- **Clear** (green) - No copied content detected
- **Possible** (yellow) - Some content may be copied
- **Likely** (red) - Strong indicators of plagiarism

Hover over badges to see detailed explanations.

### Authenticity Summary

When concerns are detected, a summary banner appears showing:
- Count of AI detection concerns (likely/possible)
- Count of plagiarism concerns (likely/possible)

### Timestamps

Each graded result includes the exact date and time it was graded, displayed in the "Time" column.

### Email Preview

Click a row to preview the feedback email:
- Shows any authenticity alerts
- Allows editing subject and body
- Send directly from the app

---

## Assignment Builder

### Purpose

The Assignment Builder lets you configure HOW an assignment should be graded by:
- Marking sections where student work appears
- Adding AI grading instructions
- Defining response sections

### Workflow

1. **Import Document**: Click "Import Word/PDF" and select your assignment
2. **Click "Edit & Mark"**: Opens the document editor
3. **Select Text**: Highlight question prompts or section headers
4. **Click "Mark Selected Text"**: Adds it as a marker
5. **Add AI Notes**:
   - **Global AI Notes** (green): Apply to ALL assignments
   - **Assignment-Specific Notes** (purple): Apply to this assignment only
6. **Save**: Click "Save Assignment Configuration"

### Response Sections

Define specific sections of student responses to extract and grade:
- Add section markers
- The AI will extract content between markers
- Useful for multi-part assignments

### What to Mark

Mark **question prompts** or **section headers**, NOT student answers:

**Good markers:**
- "Question 1: Explain the causes of..."
- "Describe the significance of:"
- "In your own words, summarize:"

**Bad markers:**
- Student's actual answer text
- Random sentences

### Persistence

All saved assignment configs are stored in `~/.graider_assignments/` and persist across restarts.

---

## Analytics Tab

### Score Distribution

View aggregated data across all graded assignments:
- Score distribution charts
- Class averages
- Grade breakdown (A, B, C, D, F counts)

### Time Period Filter

Filter analytics by:
- All time
- This week
- This month
- Custom date range

### Student Performance

Click on individual students to see their performance history and trends.

---

## Lesson Planner

### Configuration

The Lesson Planner now uses your **Settings configuration** for:
- State (for standards alignment)
- Grade Level
- Subject

These appear as badges at the top of the Standards section.

### Creating a Lesson Plan

1. Go to the **Planner** tab
2. Configure in the Generate section:
   - **Content Type**: Lesson Plan, Unit Plan, Assignment, or Project
   - **Duration**: Number of days
   - **Period Length**: Your class period in minutes (e.g., 50 min)
3. **Select Standards**: Check the standards you want to address
4. **Add Requirements** (optional): Any specific instructions
5. Click **Generate**

### Available Standards

Standards are loaded based on your Settings configuration:
- **Florida US History** (Grade 8) - 16 standards
- **Florida World History** (Grades 9-10) - 20 standards
- More states and subjects coming soon

### What You Get

The AI creates a comprehensive plan including:

- **Overview** and **Essential Questions**
- **For each day:**
  - Learning objective (SWBAT format)
  - Standards addressed
  - Vocabulary with definitions
  - Minute-by-minute timing
  - Bell ringer with expected responses
  - Direct instruction key points
  - Main activity with student tasks
  - Differentiation (struggling & advanced)
  - Assessment with exit ticket
  - Materials list
  - Homework
  - Teacher notes

### Exporting

Click **Export** to download as a Word document ready for classroom use.

---

## Resources Tab

Upload and manage supporting documents:
- Curriculum guides
- Rubrics
- Standards documents
- Reference materials

These resources can enhance AI grading and lesson planning accuracy.

---

## Settings

### Folder Configuration

| Setting | Description |
|---------|-------------|
| Assignments Folder | Where student files are uploaded |
| Output Folder | Where results/exports are saved |
| Roster File | Excel with student info |

### Teacher & School Info

- **Teacher Name**: Used in email signatures
- **School Name**: Used in exports and emails

### Academic Configuration

| Setting | Description |
|---------|-------------|
| State | Your state (for standards alignment) |
| Grade Level | K-12 selection |
| Subject | U.S. History, World History, Civics, etc. |
| Grading Period | Q1, Q2, Q3, Q4, S1, S2 |

### Global AI Instructions

Add instructions that apply to ALL grading sessions:
- Specific grading criteria
- Point allocations
- Things to look for or ignore

### Notifications

- **Toast Notifications**: Toggle on/off for grading completion popups

### Grading Rubric

Configure scoring weights:
- Content Accuracy
- Completeness
- Writing Quality
- Effort & Engagement

Weights must total 100%.

### Student Roster

Upload and manage student rosters:
- Import CSV files
- Map columns (name, email, student ID)
- Supports multiple rosters for different periods

### Class Periods

Upload separate rosters for each class period for organized grading.

---

## Privacy & FERPA Compliance

### Overview

Graider is designed for **FERPA compliance**. All student data is protected through multiple safeguards.

### Privacy Features

| Feature | Description |
|---------|-------------|
| **PII Sanitization** | Student names, IDs, emails, phone numbers, SSNs, and addresses are removed before AI processing |
| **Local Storage Only** | All data stays on your computer - no cloud storage |
| **No AI Training** | OpenAI API does not train on submitted data (per their policy) |
| **Audit Logging** | All data access is logged for compliance tracking |

### Data Management

Access these tools in **Settings > Privacy & Data (FERPA)**:

**View Data Summary**
- See how many records are stored
- View data file locations
- Check audit log status

**Export All Data**
- Download all student data as JSON
- Supports parent/guardian data requests
- Includes all grading results and feedback

**Delete All Data**
- Securely removes all student data
- Requires double confirmation (dialog + type "DELETE")
- Clears grading results and session data
- Cannot be undone

### What Data is Stored

| Data | Location |
|------|----------|
| Grading Results | `~/.graider_results.json` |
| App Settings | `~/.graider_settings.json` |
| Audit Log | `~/.graider_audit.log` |
| Assignment Configs | `~/.graider_assignments/` |
| Rubric Settings | `~/.graider_rubric.json` |
| Email Config | `~/.graider_email.json` |

### For IT Administrators

See `GRAIDER_FERPA_IMPLEMENTATION.md` for:
- Complete API documentation
- Data flow diagrams
- Security details
- Compliance checklist

---

## Troubleshooting

### API Errors During Grading

If grading stops with an API error:
1. Check your internet connection
2. Verify your OpenAI API key is valid
3. Check if OpenAI service is available
4. Fix the issue and click Start Grading to resume

Progress is automatically saved - grading continues from where it stopped.

### "Invalid API Key format detected"

Your `.env` file has the wrong key or format. Ensure:
```
OPENAI_API_KEY=sk-xxxxxxxx
```
No quotes, no spaces.

### Standards Not Loading

1. Check your Settings configuration (State, Grade, Subject)
2. Ensure the subject matches available standards files
3. Standards files are in `backend/data/standards_*.json`

### Markers Not Working

Make sure you're marking **question prompts**, not answers. The marker text must appear in student submissions for detection to work.

### Settings Not Saving

Settings auto-save to:
- `~/.graider_rubric.json` - Rubric settings
- `~/.graider_settings.json` - Global settings and AI notes
- `~/.graider_assignments/` - Assignment configs

Check file permissions if issues occur.

### Grading Not Starting

1. Verify Assignments Folder exists and has files
2. Check Roster File path is correct
3. Look at the Activity Monitor for error messages

### Export Errors

If export fails, ensure you have write permissions to the Output Folder.

### Resetting Graded Detection

To re-grade all assignments:
1. Delete `~/.graider_results.json`
2. Delete `master_grades.csv` in your output folder
3. Restart the app

Or use **Settings > Privacy & Data > Delete All Data**

---

## Tips for Best Results

1. **Be specific in AI notes**: "Give full credit if student mentions at least 2 of: X, Y, Z"
2. **Use clear markers**: Question numbers or unique prompts work best
3. **Review first batch**: Check a few grades manually, then adjust AI notes if needed
4. **Save configs**: Once you've set up an assignment, save it for reuse
5. **Check authenticity flags**: Review flagged assignments before sending feedback

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Theme Toggle | Click sun/moon icon in header |

---

## Support

Report issues at: https://github.com/acrionas/Graider/issues

---

## Recent Updates (January 2026)

### New Features

- **Toast Notifications**: Real-time popups when assignments are graded (can be disabled)
- **API Error Handling**: Automatic stop on errors with prominent alerts
- **Separate AI/Plagiarism Detection**: Independent indicators with confidence levels
- **Timestamps**: Date and time shown for each graded result
- **Activity Monitor Improvements**: Horizontal collapsible design, auto-expand on errors
- **FERPA Compliance**: Full PII sanitization, audit logging, data management tools
- **State Configuration**: Select your state for standards alignment
- **World History Standards**: Added Florida World History standards (20 benchmarks)

### UI Improvements

- Theme toggle simplified (icon only)
- Authenticity summary in Results tab
- Privacy & Data section in Settings

---

*Last updated: January 26, 2026*
