# Graider User Manual

## Table of Contents
1. [Getting Started](#getting-started)
2. [Grade Tab - Grading Assignments](#grade-tab---grading-assignments)
3. [Results Tab](#results-tab)
4. [Exports](#exports)
5. [Assignment Builder](#assignment-builder)
6. [Analytics Tab](#analytics-tab)
7. [Lesson Planner](#lesson-planner)
8. [Resources Tab](#resources-tab)
9. [Settings](#settings)
10. [Privacy & FERPA Compliance](#privacy--ferpa-compliance)
11. [Student Progress Tracking](#student-progress-tracking)
12. [Troubleshooting](#troubleshooting)

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

### Period Filtering

Filter grading by class period to grade only specific classes:

1. Upload period rosters in **Settings > Class Periods**
2. In the Grade tab, select a period from the **Period Filter** dropdown
3. Only files matching students in that period will be graded
4. Works with both Start Grading and Auto-Grade Mode

### Selective File Grading

Choose specific files to grade instead of grading everything:

1. Click **Load Files** to see all files in your Assignments Folder
2. Check/uncheck individual files in the list
3. Use **Select All** / **Deselect All** for bulk selection
4. Already-graded files show a checkmark indicator
5. Click **Start Grading** to grade only selected files

> **Tip:** Combine with Period Filter to see only files from a specific class.

### Stop Grading

To stop grading in progress:

1. Click the **Stop Grading** button (appears while grading)
2. Current file completes, then grading stops
3. All progress is saved automatically
4. Resume by clicking Start Grading again

### Individual Upload (Paper/Handwritten Assignments)

Grade paper assignments by uploading photos:

1. In the Grade tab, find the **Individual Upload** section
2. Click **Choose File** and select an image (JPG, PNG, etc.)
3. Enter the student's name (autocompletes from period roster)
4. Click **Grade This Assignment**
5. Graider uses GPT-4o vision to read handwriting and grade

**Supported formats:** JPG, JPEG, PNG, GIF, WEBP, HEIC

**Note:** Individual uploads automatically use GPT-4o for better handwriting recognition (regardless of your model setting).

### Open Results Folder

Click **Open Results Folder** to open your output folder in Finder/Explorer. Quick access to:
- Focus CSV files
- Detailed reports
- Email text files
- Master grades spreadsheet

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
- **Baseline** - Deviation indicator (if student has history)
- **Email** - Email status
- **Actions** - View/edit options

### Search Results

Use the search box above the results table to filter by:
- Student name
- Assignment name
- Filename

Results update as you type.

### Filter Results

Filter the results table by type:
- **All** - Show all results
- **Handwritten** - Only paper/scanned assignments (pen icon)
- **Typed** - Only digital submissions

### Delete Single Result

To delete an individual grading result:

1. Find the result in the table
2. Click the **trash icon** in the Actions column
3. Confirm deletion

The file can then be re-graded if needed.

### Baseline Deviation Indicator

When a student has 3+ graded assignments, results show a baseline deviation indicator:

- **Normal** (no indicator) - Matches student's typical performance
- **Review** (yellow) - Minor deviation, worth checking
- **Significant** (red) - Major deviation, possible plagiarism/AI use

Click to see details about why the submission was flagged.

---

## Exports

### Automatic Exports

When grading completes, Graider automatically creates these files in your Output Folder:

### Focus CSV Files

Grade import files for Focus (student information system):

- **Format:** Student ID, Score, Comment
- **Separated by assignment** - One CSV per assignment type
- **Location:** `{Output Folder}/{Assignment}_{timestamp}.csv`

**Example:**
```csv
Student ID,Score,Comment
1950304,85,"Great job, Jackson! You correctly identified..."
1956701,92,"Excellent work, Maria!..."
```

### Detailed Report

Complete grading data for your records:

- **Location:** `{Output Folder}/Detailed_Report_{Assignment}_{timestamp}.csv`
- **Includes:** Student ID, name, email, score, letter grade, all rubric breakdowns, feedback

### Master Grades CSV

Cumulative grade tracking across the school year:

- **Location:** `{Output Folder}/master_grades.csv`
- **Appends** new grades each grading session
- **Columns:** Date, Student ID, Name, Period, Assignment, Quarter, Score, Letter Grade, Rubric Breakdowns, Feedback

Use this for:
- Progress reports
- Parent conferences
- Grade analysis over time

### Email Files

Text files ready to copy/paste or import:

- **Location:** `{Output Folder}/emails/`
- **One file per student** with all their assignments combined
- **Format:** TO, SUBJECT, then email body

---

## Authenticity Detection

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

### Email Preview & Approval

Click a row to preview the feedback email:
- Shows any authenticity alerts
- Allows editing subject and body
- Send directly from the app

### Email Approval Workflow

Before sending emails, you can review and approve each one:

1. Click **Preview Emails** to see all pending emails
2. Each email shows:
   - Student name and email address
   - Subject line
   - Full feedback body
3. For each email, choose:
   - **Approve** (green check) - Ready to send
   - **Reject** (red X) - Don't send
   - **Edit** - Modify subject or body before approving
4. Click **Send Approved** to send all approved emails

### Auto-Approve Emails

Toggle **Auto-Approve** to skip manual approval:
- All emails are automatically marked as approved
- Useful when you trust the AI feedback
- Can still review individual emails before sending

### Editing Emails

To edit an email before sending:

1. Click the email row to expand it
2. Edit the subject line or body text
3. Your changes are saved automatically
4. Approve the email when ready

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

### AI Model Selection

Choose which OpenAI model to use for grading:

| Model | Cost | Best For |
|-------|------|----------|
| **GPT-4o-mini** (default) | ~$0.09 per 100 assignments | Routine grading, cost savings |
| **GPT-4o** | ~$1.43 per 100 assignments | Complex assignments, better nuance |

**Note:** Individual uploads (handwritten/scanned) always use GPT-4o for better handwriting recognition.

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

## Student Progress Tracking

### Overview

Graider tracks each student's performance over time to provide personalized feedback and detect potential academic integrity issues.

### How It Works

After grading 3+ assignments for a student, Graider builds a **baseline profile** that includes:
- Average scores per rubric category
- Typical skill strengths (reading comprehension, critical thinking, etc.)
- Performance trends over time

### Personalized Feedback

The AI uses student history to generate feedback like:
- "You're on a 3-assignment improvement streak in writing quality!"
- "Your reading comprehension continues to be a real strength!"
- "I notice your critical thinking is getting sharper - great progress!"

### Skill Tracking (Beyond the Rubric)

Graider identifies skills demonstrated in each assignment:

**Skills Tracked:**
- Reading comprehension
- Critical thinking
- Source analysis
- Making connections
- Vocabulary usage
- Following directions
- Organization
- Cause-and-effect reasoning
- Comparing/contrasting
- Using evidence
- Drawing conclusions
- Attention to detail

**Pattern Detection:**
- **Consistent Strengths**: Skills shown in 2+ of last 5 assignments
- **Improving Skills**: Skills moving from "developing" to "strength"
- **Needs Focus**: Skills persistently in development

### Baseline Deviation Detection

When a submission significantly deviates from a student's established baseline, it's flagged for review:

| Flag | Meaning |
|------|---------|
| **Normal** | Submission matches student's typical performance |
| **Review** | Minor deviation - worth a second look |
| **Significant Deviation** | Major deviation - possible plagiarism/AI use |

**What Triggers a Flag:**
- Score more than 2.5 standard deviations above baseline
- Sudden 20+ point improvement from recent average
- New sophisticated skills not previously demonstrated
- Category scores exceeding student's historical maximum

**Example:**
> A student with a 73% average suddenly submits a 98% paper with advanced vocabulary and critical analysis skills they've never shown before → **Flagged for review**

### Viewing Student History

Access student history via API:
```
GET /api/student-history/<student_id>
GET /api/student-baseline/<student_id>
```

### Data Storage

Student history is stored locally at:
```
~/.graider_data/student_history/{student_id}.json
```

Each student's file contains:
- Last 20 assignments
- Skill averages and trends
- Detected patterns
- Baseline metrics

---

## Recent Updates (January 2026)

### New Features

- **Student Progress Tracking**: Personalized feedback based on historical performance
- **Skill Pattern Detection**: Tracks skills beyond rubric categories (reading comprehension, critical thinking, etc.)
- **Baseline Deviation Detection**: Flags submissions that deviate significantly from student's typical work
- **AI Model Selection**: Choose between GPT-4o (better quality) and GPT-4o-mini (lower cost)
- **Individual Upload**: Grade paper/handwritten assignments by uploading photos
- **Handwritten Assignment Support**: Auto-uses GPT-4o vision for image-based submissions
- **Results Filtering**: Filter results by handwritten vs typed assignments
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
- Handwritten indicator icon in Results table
- AI model selector in Settings

---

*Last updated: January 28, 2026*
