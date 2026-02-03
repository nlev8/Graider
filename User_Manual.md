# Graider User Manual

## Table of Contents
1. [Getting Started](#getting-started)
2. [Grade Tab - Grading Assignments](#grade-tab---grading-assignments)
3. [Results Tab](#results-tab)
4. [Exports](#exports)
5. [Bilingual Feedback (ELL Support)](#bilingual-feedback-ell-support)
6. [Assignment Builder](#assignment-builder)
7. [Analytics Tab](#analytics-tab)
8. [Lesson Planner](#lesson-planner)
9. [Assessment Generator](#assessment-generator)
10. [Student Portal](#student-portal)
11. [Teacher Dashboard](#teacher-dashboard)
12. [Resources Tab](#resources-tab)
13. [Settings](#settings)
14. [IEP/504 Accommodations](#iep504-accommodations)
15. [Privacy & FERPA Compliance](#privacy--ferpa-compliance)
16. [Student Progress Tracking](#student-progress-tracking)
17. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Running Graider

```bash
cd /Users/alexc/Downloads/Graider/backend
python app.py
```

The app opens automatically at **http://localhost:3000**

> **Note:** The frontend is pre-built and served by the Flask backend. No separate frontend process needed.

### Live Version

Access the live version at **[graider.live](https://graider.live)**

### First-Time Setup

1. **API Keys**: Create a `.env` file in the `backend` folder:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=your-anthropic-key     # Optional, for Claude
   RESEND_API_KEY=your-resend-key           # For email
   SUPABASE_URL=your-supabase-url           # For Student Portal
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-key
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

### Skip Verified Grades (Regrade Unverified Only)

When you have previously graded assignments and want to regrade only the unverified ones:

1. The **"Skip Verified Grades"** toggle appears when you have unverified results
2. Enable the toggle to keep verified grades and only regrade unverified ones
3. Shows count of unverified vs verified assignments
4. Click **Start Grading**

**Understanding the count display:**
> "14 unverified assignments will be regraded. 98 verified grades will be kept."

This means:
- **14 unverified** = Assignments graded without a saved config (AI had less guidance, grade may be less reliable)
- **98 verified** = Assignments you manually verified OR graded with a matching saved configuration

**When to use:**
- You graded files before setting up the assignment config
- You want to fix grades that were marked without proper markers
- You added a new assignment config and want to apply it retroactively
- You improved your grading instructions and want to update uncertain grades
- You switched AI models and want to regrade only questionable results

**How grades become verified:**
1. **Automatic**: Graded with a matching saved assignment configuration (custom markers, grading notes, etc.)
2. **Manual**: You click the "Verify" button after reviewing the grade in Results

**How it works:**
- Files that matched an assignment config during grading = **Verified** (kept)
- Files graded without config = **Unverified** (regraded)

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

### Sort Results

Sort the results table using the dropdown:

| Sort Option | Description |
|-------------|-------------|
| **Newest First** | Most recently graded at top (default) |
| **Oldest First** | Earliest graded at top |
| **Name (A-Z)** | Alphabetical by student name |
| **Name (Z-A)** | Reverse alphabetical |
| **Score (High-Low)** | Highest scores first |
| **Score (Low-High)** | Lowest scores first |
| **Assignment (A-Z)** | Alphabetical by assignment name |
| **Grade (A-F)** | Best grades first |
| **Grade (F-A)** | Worst grades first |

### Filter Results

Filter the results table by type:
- **All** - Show all results
- **Handwritten** - Only paper/scanned assignments (pen icon)
- **Typed** - Only digital submissions
- **Verified** - Only assignments graded with a matched config
- **Unverified** - Only assignments without config (may need regrade)

### Verified vs Unverified Grades

Assignments are marked as **Verified** or **Unverified** based on whether they had an assignment config during grading:

**Verified** (no indicator) - Graded with:
- Matched assignment config
- Custom markers
- Grading notes
- Response sections

**Unverified** (yellow warning icon) - Graded without any configuration:
- No assignment config matched the file
- No custom markers or notes provided
- Grade may be inaccurate since AI doesn't know what to look for

#### Regrading Unverified Assignments

If assignments were graded before you set up the assignment config:

1. **Create or update the assignment config** in the Builder tab
2. Save the config with a matching name
3. Go to Grade tab
4. Enable **"Skip Verified Grades (Regrade Only Unverified)"** toggle
5. Click Start Grading

This will:
- **Skip** all verified grades (keep existing scores)
- **Regrade** only the unverified assignments with the new config

This workflow is perfect when:
- You forgot to set up markers before initial grading
- You want to fix grades that were marked without context
- You added a new assignment config and want to apply it

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

## Bilingual Feedback (ELL Support)

### Overview

Graider automatically detects when students write their responses in a language other than English and provides **bilingual feedback** - feedback in both English AND the student's native language.

### Supported Languages

- Spanish
- Portuguese
- Haitian Creole
- French
- And other languages (auto-detected)

### How It Works

1. **Automatic Detection**: When grading, the AI analyzes the student's responses and detects the language
2. **Dual Feedback**: If the student wrote in Spanish (for example), feedback is provided in:
   - English (for grade records and English learning)
   - Spanish (so the student fully understands the feedback)
3. **Separator Format**: The two versions are separated by `---` in the feedback

### Example Bilingual Feedback

```
Great work on your vocabulary matching! Your answers show you really
understood the key concepts about the Louisiana Purchase. I especially
liked how you explained that "it doubled the size of the US" - that
shows you grasped the significance!

One area to work on: try to write in complete sentences for your
short answer responses. This will help you communicate your ideas
more clearly.

---

¡Excelente trabajo en tu emparejamiento de vocabulario! Tus respuestas
muestran que realmente entendiste los conceptos clave sobre la Compra
de Luisiana. ¡Me gustó especialmente cómo explicaste que "duplicó el
tamaño de los EE.UU." - eso demuestra que comprendiste la importancia!

Un área para mejorar: intenta escribir en oraciones completas para
tus respuestas cortas. Esto te ayudará a comunicar tus ideas más
claramente.
```

### Editing Bilingual Feedback

When reviewing grades in the **Review Modal** (pencil icon):

1. You can edit both the English and translated portions
2. If you edit the English feedback, click the **Re-translate** button to update the translation
3. The Re-translate button only appears when feedback contains bilingual content (the `---` separator)

### Benefits

- **ELL Students**: Understand their feedback completely in their native language
- **Parent Communication**: Families can read feedback in their home language
- **English Learning**: Students see both versions, helping them learn English vocabulary
- **Inclusive**: Supports Florida's 30%+ English Language Learner population

### Tips

- The AI uses the same warm, encouraging tone in both languages
- Translations preserve the specific references to the student's work
- You can manually edit either portion if needed
- The email preview will show the full bilingual feedback

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

### Assignment Aliases (Renamed Assignments)

When you rename an assignment in the Builder, Graider automatically tracks the previous name(s) as **aliases**. This ensures student submissions still match even after renaming.

**Example:**
1. You create an assignment called "Chapter 5 Quiz"
2. Students upload files like "John Smith Chapter 5 Quiz.docx"
3. Later, you rename the assignment to "Ch5 Quiz"
4. Student files with "Chapter 5 Quiz" in the name still match!

**How It Works:**
- When you change an assignment title, the old name is saved as an alias
- The Missing Assignments feature checks both current name AND all aliases
- Aliases are stored with the assignment config
- Multiple aliases are supported (if you rename multiple times)

**Viewing Aliases:**
- Aliases are stored in the assignment JSON config
- They're automatically used for matching - no action required

### Section Point Values

The Section Point Values feature lets you assign specific point values to different sections of an assignment, giving you fine-grained control over how grades are calculated.

**Enabling Section Points:**
1. In the Builder tab, find the **"Use Section Point Values"** toggle
2. When **OFF** (default): Uses standard rubric (Content 40, Completeness 25, Writing 20, Effort 15)
3. When **ON**: Shows the section point editor

**Using Section Points:**

1. **Toggle ON** the "Use Section Point Values" switch
2. **Select a Template** (optional):
   - **Cornell Notes**: Questions/Terms (40), Summary (20), Vocabulary (25), Effort (15)
   - **Worksheet - Fill-in-Blank Heavy**: Fill-in-blank (50), Short Answer (35), Effort (15)
   - **Worksheet - Written Heavy**: Questions (30), Written Response (40), Reflection (15), Effort (15)
   - **Essay**: Thesis/Intro (20), Body (45), Conclusion (20), Effort (15)
   - **Custom**: Define your own sections

3. **Customize Points**:
   - Edit section names directly in the text boxes
   - Adjust point values (must total 100)
   - Change section types (Written, Fill-blank, Vocabulary, Matching)
   - Adjust Effort & Engagement points (default 15)

4. **Verify Total**: The total points display shows if your points sum to 100
   - Shows warning in red if total ≠ 100

**How It Affects Grading:**

When Section Point Values is **enabled**:
- Each section is graded out of its assigned points
- **Blank sections = 0 points** for that section (no partial credit)
- The AI receives specific instructions about point values per section
- Results show section-by-section breakdown

When Section Point Values is **disabled**:
- Uses the standard rubric categories
- More flexible, holistic grading approach

**Best Practices:**
- Use for assignments with clearly defined sections
- Ensure total points = 100
- Match section names to actual assignment headers for accurate extraction
- Keep Effort & Engagement at 15 for consistency

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

### Missing Assignments

Track which students haven't uploaded their assignments:

1. Go to the **Analytics** tab
2. Find the **Missing Assignments** section
3. Use the filters to narrow down:
   - **Period**: Filter by class period or view all
   - **Student**: Type a name or select from autocomplete
   - **Assignment**: Check a specific assignment or all

**Summary Stats:**
- Total missing assignments
- Total uploaded
- Number of students
- Number of assignments being tracked

**Per-Period Breakdown:**
- Shows each period with completion status
- Lists students with missing work
- Shows which specific assignments are missing for each student

**Per-Student View:**
- Select a student to see their individual status
- Shows all assignments they're missing
- Shows assignments they've uploaded

**How Matching Works:**
- Compares files in your Assignments Folder against period rosters
- Matches by student name and assignment name in filename
- Supports renamed assignments (see Assignment Aliases below)

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

## Assessment Generator

Generate standards-aligned assessments with multiple question types.

### Creating an Assessment

1. Go to the **Planner** tab
2. Click **Assessment Generator** mode
3. Configure the assessment:
   - **Total Questions**: How many questions to generate
   - **Total Points**: Total point value for the assessment
   - **Question Types**: Multiple Choice, Short Answer, Extended Response, True/False, Matching
   - **DOK Levels**: Depth of Knowledge distribution (1-4)
4. **Select Standards**: Check the standards to assess
5. Add **AI Instructions** (optional): Special requirements
6. Click **Generate Assessment**

### Question Type Distribution

When you set the total questions, types are automatically distributed:
- **50%** Multiple Choice
- **15%** Short Answer
- **15%** True/False
- **10%** Extended Response
- **10%** Matching

Adjust individual counts as needed - the total is enforced.

### DOK Levels

DOK (Depth of Knowledge) indicates cognitive complexity:

| Level | Description | Example |
|-------|-------------|---------|
| DOK 1 | Recall | Define a term, identify a date |
| DOK 2 | Skill/Concept | Compare two events, explain a process |
| DOK 3 | Strategic Thinking | Analyze causes, evaluate arguments |
| DOK 4 | Extended Thinking | Synthesize multiple sources, design a solution |

Default distribution: 20% DOK 1, 40% DOK 2, 30% DOK 3, 10% DOK 4

### Exporting Assessments

Click **Export** to download in various formats:
- **Word Document** - Editable .docx
- **PDF** - Print-ready with answer key option
- **Canvas (QTI)** - Import directly into Canvas LMS
- **Kahoot** - Game-based learning format
- **Quizlet** - Flashcard study format
- **Google Forms** - Importable form

### Saving Assessments

Save assessments for later use (e.g., makeup exams):

1. Enter a name in the "Assessment name..." field
2. Click **Save for Later**
3. Access saved assessments in the **Student Portal Dashboard**

---

## Student Portal

Publish assessments online for students to take with automatic grading.

### Publishing an Assessment

1. Generate an assessment in **Assessment Generator**
2. Click **Publish to Portal**
3. Configure publish settings:
   - **Period** (optional): Organize by class period
   - **Makeup Exam**: Restrict to specific students
   - **Apply Accommodations**: Include IEP/504 modifications
   - **Time Limit** (optional): Set a time limit in minutes
4. Click **Publish Assessment**
5. Share the **Join Code** or **Link** with students

### Join Codes

Each published assessment gets a unique 6-character code (e.g., `ABC123`).

Students access assessments at:
- **Direct link**: `graider.live/join/ABC123`
- **Or manually**: Go to `graider.live/join` and enter the code

### Student Experience

1. Student goes to `graider.live/join`
2. Enters the join code
3. Enters their name
4. Takes the assessment (all question types supported)
5. Submits and receives immediate feedback with score

### Makeup Exams

For students who missed the original assessment:

1. **Save the assessment** when you first create it
2. Go to **Student Portal Dashboard**
3. Load the saved assessment
4. Click **Publish to Portal**
5. Enable **Makeup Exam** mode
6. Select only the students who need the makeup
7. Publish - only selected students can access

### Accommodations

When publishing with a period selected:

1. Enable **Apply IEP/504 Accommodations**
2. Students with accommodations (configured in Settings) will see:
   - Their specific accommodations listed at the top
   - Extended time settings (if configured)
   - Modified instructions

---

## Teacher Dashboard

Monitor published assessments and student submissions.

### Accessing the Dashboard

1. Go to **Planner** tab
2. Click **Student Portal** mode

### Published Assessments

View all your published assessments:
- **Title** and **Join Code**
- **Submission count**
- **Period** (if assigned)
- **Status** (Active/Closed)
- **Makeup Exam** indicator

**Actions:**
- Click an assessment to view submissions
- **Pause/Play**: Toggle accepting new submissions
- **Delete**: Remove the assessment

### Viewing Submissions

Click on an assessment to see student results:
- **Total submissions**
- **Average score**
- **High score**
- Individual student scores with:
  - Student name
  - Score and percentage
  - Time taken
  - Submission time

### Saved Assessments

Below the published assessments, view your saved assessments:
- Name and question count
- Total points
- Save date
- **Load**: Load into Assessment Generator for editing or publishing
- **Delete**: Remove from saved assessments

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

Choose which AI model to use for grading:

| Model | Cost | Best For |
|-------|------|----------|
| **GPT-4o-mini** (default) | ~$0.01 per assignment | Routine grading, cost savings |
| **GPT-4o** | ~$0.03 per assignment | Complex assignments, better nuance |
| **Claude 3.5 Haiku** | ~$0.01 per assignment | Fast, cost-effective |
| **Claude 3.5 Sonnet** | ~$0.02 per assignment | Excellent reasoning |
| **Gemini 2.0 Flash** | ~$0.01 per assignment | Fast, good value |
| **Gemini 2.0 Pro** | ~$0.05 per assignment | Most capable Gemini model |

**Note:** Individual uploads (handwritten/scanned) always use GPT-4o for better handwriting recognition.

### Ensemble Grading

Run each assignment through multiple AI models and use the median score for more reliable grading.

**How to enable:**
1. Go to **Settings > AI**
2. Enable **Ensemble Grading**
3. Select 2-3 models to use (checkboxes appear)
4. Grade assignments normally

**How it works:**
1. Each assignment is sent to all selected models **simultaneously** (parallel processing)
2. All models grade independently
3. The **median score** is selected (protects against outliers)
4. Feedback comes from the model closest to the median score

**Performance impact:**
| Mode | Time per Assignment |
|------|---------------------|
| Single model | 3-8 seconds |
| Ensemble (3 models) | 5-12 seconds |

Models run in parallel, so total time ≈ slowest model (not sum of all).

**Cost estimate:** ~$0.03-0.09 per assignment with 3 models

**When to use ensemble:**
- High-stakes assignments (final essays, major projects)
- Subjective writing where grading is harder
- Borderline grades where you want more confidence

**When to skip ensemble:**
- Routine homework
- Assignments you'll manually verify anyway
- Clear-cut right/wrong work (fill-in-the-blank, matching)

### Global AI Instructions

Add instructions that apply to ALL AI operations:

**Applies to:**
- Grading assignments
- Generating assessments
- Generating assignments from lessons
- Creating lesson plans

**Common uses:**
- Specific grading criteria and point allocations
- Period-based differentiation rules
- Things to look for or ignore
- Grade level adjustments per class

**Example for differentiation:**
```
For assessment generation:
- Periods 1, 2, and 5 are advanced and can be given questions at the 7th-8th grade level
- Periods 4, 6, and 7 should only be given questions at the 6th grade level
```

When generating assessments, select the **Target Period** in the Assessment Generator to apply these differentiation rules.

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

### IEP/504 Accommodations

Graider includes built-in support for IEP and 504 accommodations, allowing personalized feedback for students with special needs.

#### Available Presets

| Preset | Description |
|--------|-------------|
| **Simplified Language** | Shorter sentences, simpler vocabulary, clear structure |
| **Effort-Focused** | Emphasizes participation and growth over perfection |
| **Extra Encouragement** | More positive reinforcement and supportive tone |
| **Chunked Feedback** | Breaks feedback into small, labeled sections (bullet points, headers) |
| **Modified Expectations** | Focuses on content understanding, not spelling/grammar |
| **Visual Structure** | Clear headers, bullet points, organized layout |
| **Read-Aloud Friendly** | Natural language that flows when spoken, avoids abbreviations |
| **Growth Mindset** | Frames all feedback around learning and potential |

#### Adding Student Accommodations

1. Go to **Settings** → **IEP/504 Accommodations**
2. Click **Add Student**
3. Enter the student ID (must match your roster)
4. Select one or more accommodation presets
5. Add any custom notes if needed
6. Click **Save**

#### Importing from CSV

You can bulk-import accommodations by adding columns to your roster CSV:

```csv
student_id,first_name,last_name,accommodation_type,accommodation_notes
12345,John,Smith,Simplified Language,Also needs extra time
12346,Maria,Garcia,"Effort-Focused, Extra Encouragement",Focus on growth
```

Then use **Import from CSV** in Settings.

#### How It Works

When grading a student with accommodations:
1. Graider looks up the student's accommodation settings
2. The accommodation **type** (not student identity) is sent to the AI
3. AI adjusts feedback tone, structure, and focus accordingly
4. Student receives personalized feedback matching their needs

#### FERPA Compliance

Accommodation data is fully FERPA compliant:
- **Local storage only** - Data stays on your computer
- **No PII to AI** - Only accommodation type sent, never student names
- **Audit logged** - All access is tracked
- **Exportable** - Download for backup or transfer
- **Deletable** - One-click removal of all accommodation data

#### Viewing Accommodated Students in Results

Students with accommodations show a **pink heart icon** (♥) next to their name in the Results tab. Hover over the icon to see their assigned presets.

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

## Recent Updates (February 2026)

### New Features

- **Ensemble Grading**: Run assignments through multiple AI models (GPT-4, Claude, Gemini) and use median score for more reliable grading
- **Multi-Provider AI Support**: Choose from OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude 3.5 Sonnet, Haiku), and Google (Gemini 2.0 Flash, Pro)
- **Assessment Generator**: Create standards-aligned assessments with multiple question types (MC, Short Answer, Extended Response, True/False, Matching)
- **Student Portal**: Publish assessments with join codes for students to take online
- **Teacher Dashboard**: Monitor published assessments, view submissions, track scores
- **Saved Assessments**: Save assessments locally for reuse (makeup exams)
- **Makeup Exam Mode**: Restrict assessments to specific students only
- **Period Organization**: Organize published assessments by class period
- **Accommodation Integration**: Apply IEP/504 accommodations when publishing
- **DOK Level Configuration**: Set Depth of Knowledge distribution for assessments
- **Platform Export**: Export assessments to Canvas QTI, Kahoot, Quizlet, Google Forms
- **Missing Assignments Tracker**: See which students haven't uploaded their work in Analytics
- **Assignment Aliases**: Renamed assignments still match old student submissions
- **Student Progress Tracking**: Personalized feedback based on historical performance
- **Skill Pattern Detection**: Tracks skills beyond rubric categories (reading comprehension, critical thinking, etc.)
- **Baseline Deviation Detection**: Flags submissions that deviate significantly from student's typical work
- **AI Model Selection**: Choose between GPT-4o (better quality) and GPT-4o-mini (lower cost)
- **Individual Upload**: Grade paper/handwritten assignments by uploading photos
- **Handwritten Assignment Support**: Auto-uses GPT-4o vision for image-based submissions
- **Results Sorting**: Sort by time, name, score, assignment, or grade
- **Results Filtering**: Filter results by handwritten vs typed assignments
- **Toast Notifications**: Real-time popups when assignments are graded (can be disabled)
- **API Error Handling**: Automatic stop on errors with prominent alerts
- **Separate AI/Plagiarism Detection**: Independent indicators with confidence levels
- **Timestamps**: Date and time shown for each graded result
- **Activity Monitor Improvements**: Horizontal collapsible design, auto-expand on errors
- **FERPA Compliance**: Full PII sanitization, audit logging, data management tools
- **State Configuration**: Select your state for standards alignment
- **World History Standards**: Added Florida World History standards (20 benchmarks)
- **Cloud Deployment**: Railway + Supabase for production hosting

### UI Improvements

- Theme toggle simplified (icon only)
- Authenticity summary in Results tab
- Privacy & Data section in Settings
- Handwritten indicator icon in Results table
- AI model selector in Settings
- Solid modal backgrounds (not transparent)
- Matching question visual interface in Student Portal
- Text input for written answer questions

---

*Last updated: February 2, 2026*
