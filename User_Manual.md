# Graider User Manual

## Table of Contents
1. [Getting Started](#getting-started)
2. [Grade Tab - Grading Assignments](#grade-tab---grading-assignments)
3. [Results Tab](#results-tab)
4. [Exports](#exports)
5. [Resubmissions](#resubmissions)
6. [Authenticity Detection](#authenticity-detection)
7. [Bilingual Feedback (ELL Support)](#bilingual-feedback-ell-support)
8. [Assignment Builder](#assignment-builder)
9. [Analytics Tab](#analytics-tab)
10. [Lesson Planner](#lesson-planner)
11. [Assessment Generator](#assessment-generator)
12. [Student Portal](#student-portal)
13. [Teacher Dashboard](#teacher-dashboard)
14. [Resources Tab](#resources-tab)
15. [Assistant Tab](#assistant-tab)
16. [Settings](#settings)
17. [Privacy & FERPA Compliance](#privacy--ferpa-compliance)
18. [Student Progress Tracking](#student-progress-tracking)
19. [Troubleshooting](#troubleshooting)
20. [Tips for Best Results](#tips-for-best-results)
21. [Keyboard Shortcuts](#keyboard-shortcuts)
22. [Support](#support)

---

## Getting Started

Access Graider at **[app.graider.live](https://app.graider.live)**

### First-Time Setup

1. **Folders**: In Settings, configure:
   - **Assignments Folder**: Where student submissions are (e.g., OneDrive sync folder)
   - **Output Folder**: Where graded results go
   - **Roster File**: Excel file with student names and emails

2. **Configuration**: Set your:
   - State (for standards alignment)
   - Grade Level
   - Subject

3. **Rubric Selection** (Onboarding Wizard):
   - After setting your state, grade level, and subject, the onboarding wizard prompts you to choose a grading rubric
   - **Florida teachers**: If your state is set to Florida, you'll see a B.E.S.T. rubric preset matched to your subject (e.g., ELA, Math, Science, Social Studies) with pre-configured category weights
   - **All other teachers**: You'll see the Standard rubric preset
   - Options: **Use B.E.S.T. Rubric** / **Use Standard Rubric** / **Customize Later**
   - The final onboarding step shows a **"Create Your First Assignment"** button to get started immediately

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

### Policy 428 Compliance (Florida)

Florida teachers see additional compliance features related to **Policy 428** (AI-assisted grading requires teacher review before grades are recorded):

- **Results tab banner**: A notice reminds FL teachers that AI-assisted grades must be reviewed before submission to the gradebook
- **Focus Export modal**: A Policy 428 compliance notice appears when exporting grades to Focus, reinforcing that teacher review is required
- **What Policy 428 means**: Any grade produced or assisted by AI must be reviewed and approved by the teacher before it becomes part of the student's official record

---

## Exports

### Approval Gate

Before any export, you must confirm that you have reviewed the grades:

1. An **"I have reviewed and approve these grades"** checkbox appears above all export buttons
2. **All export buttons are disabled** until the checkbox is checked
3. The checkbox **resets automatically** when new grading results arrive, requiring fresh approval
4. This ensures compliance with best practices and Florida Policy 428 for AI-assisted grading

### Automatic Exports

When grading completes, Graider automatically creates these files in your Output Folder:

### Focus CSV Files

Grade import files for Focus (student information system):

- **Format:** Student ID, Score, Comment
- **Separated by assignment** - One CSV per assignment type
- **Location:** `{Output Folder}/{Assignment}_{timestamp}.csv`
- **Letter Grade column**: Enable the **"Include Letter Grade column"** checkbox in the Focus Export modal to add a `Letter_Grade` column to the CSV output

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

## Resubmissions

When students resubmit assignments for a higher grade, Graider automatically detects the resubmission and applies a **"keep higher grade"** policy.

### How Resubmission Detection Works

Graider groups files by student name and assignment title. When multiple versions exist (e.g., `Essay (1).docx` and `Essay (2).docx`), the newer file is flagged as a resubmission. The activity log shows a summary:

```
🔄 2 resubmission(s) detected — grading latest versions
  ↳ Essay (2).docx
```

### Keep Higher Grade

When a resubmission is graded:

- **New score >= old score:** The new grade replaces the old one. The result shows a blue 🔄 icon with a tooltip like *"Improved from 72 → 85"*.
- **New score < old score:** The original (higher) grade is kept. The result shows a yellow 🛡 icon with a tooltip like *"Kept original grade (85). New submission scored 68."* The activity log notes: `Kept original grade (85) — resubmission scored lower (68)`.

This ensures students are never penalized for attempting to improve their work.

### Resubmission Indicators in Results

| Icon | Color | Meaning |
|------|-------|---------|
| 🔄 Refresh | Blue | Resubmission replaced the old grade (score improved or equal) |
| 🛡 Shield | Yellow | Original grade kept (resubmission scored lower) |

Hover over any resubmission icon to see the old and new scores.

### Filtering Resubmissions

Use the **filter dropdown** in the Results tab and select **"🔄 Resubmissions"** to show only resubmitted assignments. This helps you quickly review which students resubmitted and whether their grades improved.

### Master CSV Behavior

The master grades CSV (`master_grades.csv`) follows the same keep-higher-grade policy. When a resubmission is exported, the old row is only replaced if the new score is higher or equal. Lower-scoring resubmissions do not overwrite existing entries.

### Grading Completion Notification

After grading completes, if any resubmissions were detected, a notification banner appears summarizing:
- Total resubmissions found
- How many improved their grade
- How many kept the original (higher) grade

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

### Writing Style Profiling

Each student builds a unique writing fingerprint over time. When a student has 3+ graded assignments, the system tracks baseline writing patterns and flags sudden changes that may indicate AI use:

| Metric Tracked | What It Catches |
|----------------|-----------------|
| **Complexity Score** | Sudden jump from simple to advanced writing |
| **Sentence Length** | Student who writes short sentences suddenly writes long, complex ones |
| **Academic Vocabulary** | Appearance of sophisticated terms not in the student's history |
| **Word Length** | Average word length shifts dramatically between assignments |
| **Spelling Patterns** | Student who typically misspells words suddenly produces error-free text |

The system compares each new submission against the student's established baseline. Large deviations trigger AI detection flags with confidence percentages. This works alongside the standard AI detection — the writing profile provides additional context about whether a submission matches the student's typical work.

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

### Rubric Performance

When assignments are graded with rubric categories, the Analytics tab shows rubric-level performance data:

- **Radar Chart** — Visual breakdown of average scores by rubric category (e.g., content accuracy, writing quality, completeness). Quickly see which categories are strongest and weakest across the class.
- **Category Columns** — The student overview table includes individual columns for each rubric category, so you can see per-student breakdowns at a glance.
- **Sortable Columns** — Click any column header (name, score, or rubric category) to sort the table. Useful for finding which students scored lowest in a specific category.

### Diagnostic Cause Analysis

Understanding *why* students scored low is more useful than knowing *that* they scored low. The Analytics tab and Assistant both support diagnostic analysis:

- **Rubric Category Breakdowns** — See average scores per rubric category across the entire assignment. Identify if low grades were caused by weak writing, missing content, or incomplete sections.
- **Omission Impact Analysis** — Compare students who completed all sections vs. those who skipped sections. The system calculates the average score gap (e.g., students with omissions averaged 13.3 points lower).
- **Section Skip Rates** — See which sections students skipped most often (e.g., "Summary section skipped by 15% of students").
- **Feedback Pattern Aggregation** — Common strengths and growth areas across all students, with frequency counts.

You can also ask the Assistant for diagnostic analysis directly — see [Assistant Tab](#assistant-tab) for examples.

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

### Brainstorm Mode

Before committing to a full lesson plan, brainstorm multiple approaches to the same standard:

1. Select the standards you want to cover
2. Click **Brainstorm Ideas**
3. The AI generates 5 diverse lesson concepts, each with a different teaching approach:
   - **Activity-Based** — Hands-on tasks, station rotations, interactive activities
   - **Discussion** — Socratic seminar, class debates, guided questioning
   - **Project-Based** — Student research, presentations, creative products
   - **Simulation** — Role-play, mock events, scenario-based learning
   - **Primary Sources** — Document analysis, evidence-based reasoning
4. Each idea shows: Title, Approach, Hook, Key Activity, and Assessment Type
5. Click an idea to select it, then generate a full lesson plan from that concept

### Multiple Variations

Compare three different teaching approaches side-by-side before deciding which one works best for your class:

| Variation | Focus | Best For |
|-----------|-------|----------|
| **Activity-Based** | Hands-on learning, station rotations, interactive tasks | Kinesthetic learners, engagement |
| **Discussion & Analysis** | Socratic questioning, primary sources, class debates | Critical thinking, depth |
| **Project-Based** | Student research, presentations, creative products | Long-term retention, ownership |

Each variation includes a complete lesson plan with timing, different activities aligned to the same standards, unique essential questions and assessments, and a one-click button to select and use.

### Standards Browser

Every standard in the planner includes rich benchmark data to guide lesson planning:

- **DOK Level** — Color-coded badges showing Depth of Knowledge (1-4)
- **Essential Questions** — Driving questions for inquiry-based learning
- **Learning Targets** — Student-friendly "I can..." statements
- **Key Vocabulary** — Terms students need to master, shown as clickable tags
- **Item Specifications** — How the standard is typically assessed
- **Sample Assessment** — Example test question with answer choices

Click **Show Details** on any standard card to expand it and see all of this information. Standards are searchable and filterable by topic, DOK level, and keyword.

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

### Overview

Upload supporting documents so the AI Assistant has full context about your curriculum, pacing, and academic calendar. Everything you upload here is read automatically by the Assistant — it doesn't need to be told to look at them.

### What to Upload

The more context you give the Assistant, the better it can generate lesson plans, worksheets, and assessments that align with what you're actually teaching and when.

**Recommended uploads (in order of impact):**

| Document | Why It Matters |
|----------|---------------|
| **Pacing Guide / Pacing Calendar** | Tells the Assistant what standards and topics you should be covering each week and quarter. This is the single most impactful document you can upload — it lets the Assistant answer "What should I be teaching next week?" using your district's actual timeline. |
| **Curriculum Framework / Course Description** | The state or district document that defines your course scope — benchmark descriptions, course outcomes, content limits. Gives the Assistant the full picture beyond just standard codes. |
| **School Year Calendar** | Start/end dates, holidays, teacher workdays, early release days, testing windows. The Assistant uses this to schedule lessons on actual school days and plan around breaks. |
| **Scope & Sequence** | If your department has a unit-by-unit sequence with suggested timeframes, upload it. Helps the Assistant know what comes before and after any given topic. |
| **District Curriculum Guide** | Any district-specific document with expected vocabulary, essential questions, or learning targets per unit. |
| **Department or PLC Documents** | Common assessment schedules, shared rubrics, or unit plans your team uses. |

### Supported File Types

- **PDF** — pacing guides, curriculum frameworks, school calendars
- **Word (.docx)** — scope & sequence documents, department guides
- **Text / Markdown (.txt, .md)** — any plain text reference

### How Uploads Work

1. Go to the **Resources** tab
2. Click **Upload Document**
3. Select your file and add a description (e.g., "Q3-Q4 Pacing Calendar")
4. Choose a document type (curriculum, calendar, general)
5. The document is stored locally and its full text is available to the Assistant immediately

### How the Assistant Uses Your Documents

Once uploaded, the Assistant **automatically reads all your documents** at the start of every conversation. You don't need to tell it to look anything up — it already knows:

- What standards you should be covering this week (from your pacing guide)
- When holidays and breaks fall (from your school calendar)
- What vocabulary and essential questions go with each unit (from your curriculum framework)
- What's coming up next quarter (from your scope & sequence)

**Example questions that work better with uploaded resources:**

- "Create a worksheet for what I'm teaching next week" — uses your pacing guide to pick the right standards and topics
- "Generate a lesson plan for the first two weeks of Q3" — combines your pacing calendar, standards, and school calendar to plan around holidays
- "What standards should I focus on before the benchmark test?" — cross-references your pacing guide with the standards database
- "Am I on track with my pacing?" — compares your teaching calendar against your pacing guide

### Tips

- **Upload your pacing guide first** — this single document transforms the Assistant from a generic standards tool into a curriculum-aware planning partner
- **Keep documents current** — if your department updates the pacing mid-year, upload the new version
- **Add descriptions** — a clear description like "District US History Pacing Calendar 2025-2026" helps you manage multiple files
- Documents are stored locally at `~/.graider_data/documents/` and never leave your machine

---

## Assistant Tab

### Overview

The Graider Assistant is a built-in AI chat that helps you understand student performance, plan curriculum-aligned lessons, generate worksheets, and manage your gradebook. Powered by Claude (Anthropic), it has access to your grading data, curriculum standards, uploaded resources, teaching calendar, and persistent memory — all queried locally. No student PII leaves your machine.

### Getting Started

1. Go to the **Assistant** tab
2. Type a question or click one of the suggested prompts
3. The assistant streams its response in real-time
4. Tool indicators show when data is being queried

### What You Can Ask

| Category | Example Questions |
|----------|------------------|
| **Grade diagnostics** | "What caused the low grades on Cornell Notes?" |
| **Lesson planning** | "Create a lesson plan for what I'm teaching next week" |
| **Worksheet creation** | "Create a Cornell Notes worksheet about the American Revolution" |
| **Standards alignment** | "What standards should I be covering this quarter?" |
| **Pacing & calendar** | "Am I on track with my pacing guide?" / "What's on my calendar next week?" |
| **Period comparison** | "Which period did best on this assignment?" |
| **Student lookup** | "How is Maria doing?" / "What are her parent's contact details?" |
| **At-risk students** | "Which students need attention?" / "Who has missing work?" |
| **Document generation** | "Create a study guide for Unit 3" / "Write a parent letter about upcoming exams" |
| **Focus automation** | "Create a Focus assignment called Quiz 3 worth 100 points" |
| **Export grades** | "Export grades for Period 3 as a Focus CSV" |
| **Scheduling** | "Schedule the Colonization lesson starting Monday" |

### Curriculum & Resource Awareness

The Assistant automatically knows your **full curriculum standards** and the contents of **every document you've uploaded** in the Resources tab. You don't need to tell it to look anything up — it already has this context at the start of every conversation.

This means it can:
- Reference specific standard codes (e.g., SS.8.A.1.1) when generating content
- Pull from your pacing guide to know what you should be teaching on any given week
- Use your school calendar to plan around holidays and breaks
- Combine standards + pacing + calendar to create lessons that fit your actual schedule

**To get the most out of this, upload your pacing guide and school calendar in the Resources tab.** See [Resources Tab](#resources-tab) for details on what to upload.

### Voice Mode

Talk to the Assistant instead of typing. Voice mode uses your browser's speech recognition (free, no extra API needed) and can optionally read responses aloud using ElevenLabs.

**To use voice mode:**

1. Click the **speaker icon** in the input bar to enable voice mode
2. Click the **microphone button** to start speaking
3. The mic stays active while you talk — it waits for a natural pause (~2 seconds of silence) before sending
4. You can also press the mic button again to send immediately
5. Your words appear as a live transcript while you speak

**Voice responses (optional):**
- Requires an `ELEVENLABS_API_KEY` in your `.env` file
- When configured, the assistant reads its responses aloud
- Click anywhere or send a new message to interrupt the audio

### Persistent Memory

The Assistant remembers important facts across conversations. When you share preferences, class structure, or workflow habits, it saves them automatically so you don't have to repeat yourself.

**What it remembers:**
- Class structure ("Period 3 is my honors class")
- Preferences ("I like Cornell Notes worksheets with 10 vocabulary terms")
- Workflow habits ("I always do a bell ringer at the start of class")
- Student context ("I have 5 ELL students in Period 4")

**Managing memory:**
- **Clear Memory** button in the header erases all saved facts (requires confirmation)
- **Clear Chat** button clears the conversation window but **keeps all memories intact**
- Memory persists across browser sessions and server restarts

### Class Performance Awareness

The Assistant is automatically aware of live rubric performance data from your most recent grading sessions. It can proactively recommend instructional changes based on actual student results:

- **Rubric category analysis** — The assistant knows which rubric categories are strongest and weakest across your classes, and can recommend targeted lessons
- **Data-driven lesson recommendations** — Ask "What should I teach next?" and the assistant cross-references student weaknesses with your curriculum standards to suggest specific topics
- **Period differentiation** — Recommendations are tailored per class level (advanced, standard, support) with DOK-appropriate standards
- **IEP/504 accommodation analysis** — Lesson suggestions account for students with accommodations

**Example:**
> "Based on the Slavery and Resistance assignment, what should my next lesson focus on?"
>
> The assistant analyzes rubric breakdowns (writing_quality was weakest at avg 12.7), identifies content gaps (Summary section skipped by 15%), checks developing skills, cross-references curriculum standards, and returns actionable lesson recommendations with specific topics and standards.

### Teaching Calendar

The Assistant can read and manage your teaching calendar:

- **View schedule**: "What am I teaching this week?" / "What's coming up?"
- **Schedule lessons**: "Put the Revolution lesson on Tuesday" — places saved lesson plans onto specific dates
- **Add holidays**: "We're off next Friday" / "Add Spring Break March 17-21"
- **Multi-day lessons**: Automatically skips weekends and holidays when scheduling multi-day units

### Stopping and Clearing

**Stop mid-response:** If the Assistant is generating a response and you want to cancel (wrong question, too long, etc.), click the **red stop button** that replaces the send button during streaming. This immediately stops the response, the TTS audio, and any tool execution.

**Clear chat:** Click **Clear Chat** in the header to clear the conversation window. This resets the chat but **preserves your persistent memory** — the Assistant will still remember your preferences and class info in the next conversation.

### Available Tools

The assistant has access to tools that query your local data:

| Tool | What It Does |
|------|-------------|
| **Query Grades** | Search and filter grades by student, assignment, period, or score range |
| **Student Summary** | Deep dive into one student: all grades, trends, category breakdowns, strengths and weaknesses |
| **Class Analytics** | Class-wide stats: average, grade distribution, top/bottom performers |
| **Assignment Stats** | Statistics for a specific assignment: mean, median, min, max, standard deviation |
| **Analyze Grade Causes** | WHY students got their grades: rubric breakdowns, skipped questions, score impact of omissions |
| **Feedback Patterns** | Common strengths and growth areas across an assignment, feedback samples from high/low scorers |
| **Compare Periods** | Side-by-side period comparison: averages, distributions, category scores, omission rates |
| **Recommend Next Lesson** | Data-driven lesson recommendations with differentiated suggestions by class level (advanced/standard/support) and IEP/504 accommodation analysis |
| **Lookup Student Info** | Roster info, parent contacts, student schedules, 504 status. Supports batch lookup. |
| **Missing Assignments** | Find who hasn't submitted work — by student, period, or assignment |
| **Generate Worksheet** | Create downloadable worksheets (Cornell Notes, fill-in-blank, short-answer, vocabulary) with embedded answer keys for AI grading |
| **Generate Document** | Create formatted Word documents (study guides, parent letters, rubrics, lesson outlines) |
| **Get Standards** | Look up curriculum standards with full details: vocabulary, learning targets, essential questions |
| **List Resources** | See what supporting documents you've uploaded |
| **Read Resource** | Read the full text of a specific uploaded document |
| **Calendar Tools** | View, schedule lessons, and add holidays to your teaching calendar |
| **Save Memory** | Save important facts for future conversations |
| **Focus Automation** | Create assignments in Focus gradebook, export Focus-compatible CSVs |

### Deep Analytics Examples

**"What caused the low grades on Cornell Notes Slavery and Resistance?"**
> The assistant finds: writing_quality was weakest (avg 12.7), 64.8% of students had omissions, summary section was skipped most (15% of students), and students with omissions averaged 13.3 points lower than those who completed everything.

**"Create a worksheet for what I'm teaching next week"**
> The assistant checks your pacing guide, finds the standards you should be covering, pulls relevant vocabulary and learning targets, and generates a downloadable worksheet with an embedded answer key — all aligned to your actual schedule.

**"Based on student performance, what should I teach next?"**
> Analyzes category weaknesses and developing skills, then cross-references your curriculum standards to recommend specific topics. Provides differentiated suggestions for advanced, standard, and support classes.

### Conversation Management

- **Clear Chat**: Clears the conversation window. Memory is preserved.
- **Clear Memory**: Erases all saved facts from previous conversations (requires confirmation).
- Conversations auto-expire after 2 hours of inactivity.
- Chat history persists in your browser between page loads.

### Focus SIS Automation

The assistant can create assignments directly in Focus gradebook:

1. Ask something like: *"Create a Focus assignment called Quiz 3 worth 100 points for 02/14/2026"*
2. The assistant confirms the details before proceeding
3. A browser window opens and logs into VPortal automatically
4. **Check your phone for 2FA approval**
5. The form is filled out — review and click Save manually
6. The browser stays open for 2 minutes for verification

**Prerequisites:**
- VPortal credentials configured in **Settings > Tools > District Portal**
- Node.js installed on your computer
- Playwright browser installed (`npx playwright install chromium`)

### Setting Up VPortal Credentials

1. Go to **Settings > Tools**
2. Scroll to **District Portal (VPortal)**
3. Enter your district email and password
4. Click **Save Credentials**
5. A green "Configured" indicator confirms they're saved

Credentials are stored locally at `~/.graider_data/portal_credentials.json` with basic encoding. They never leave your machine.

### FERPA Compliance

The assistant is designed with FERPA in mind:

| Concern | Protection |
|---------|-----------|
| **Data source** | All tools query local files only (`~/.graider_results.json`, `master_grades.csv`) |
| **API calls** | Anthropic API does not use data for model training |
| **Conversations** | In-memory only, cleared on server restart, auto-expire after 2 hours |
| **Audit logging** | Every assistant query and tool call logged to `~/.graider_audit.log` |
| **Student names** | The assistant is instructed to minimize PII and use first names only |

### Requirements

- `ANTHROPIC_API_KEY` set in your `.env` file (get one at [console.anthropic.com](https://console.anthropic.com))
- Grading data available (at least some assignments graded)

### Troubleshooting

**"ANTHROPIC_API_KEY not set"**
- Add `ANTHROPIC_API_KEY=sk-ant-...` to your `.env` file in the backend folder

**"No grading data available"**
- Grade some assignments first — the assistant queries your local results files

**Streaming not working in development**
- The Vite dev server proxies SSE correctly by default
- If responses appear all at once instead of streaming, check browser DevTools for proxy issues

**Focus automation fails**
- Verify VPortal credentials are saved in Settings > Tools
- Make sure `node focus-automation.js` runs from the project root
- Run `npx playwright install chromium` if browser is missing

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

#### Quick Presets (B.E.S.T. Rubric Presets)

A **Quick Presets** row appears in Settings > Grading for Florida teachers. These presets configure category weights aligned with Florida's B.E.S.T. (Benchmarks for Excellent Student Thinking) standards:

| Preset | Content | Completeness | Writing | Effort |
|--------|---------|-------------|---------|--------|
| **ELA** | 35 | 20 | 30 | 15 |
| **Math** | 45 | 25 | 15 | 15 |
| **Science** | 40 | 25 | 20 | 15 |
| **Social Studies** | 40 | 20 | 25 | 15 |
| **Standard** | 40 | 25 | 20 | 15 |

- **Florida teachers** (state set to FL): See all 4 B.E.S.T. presets plus Standard
- **Non-FL teachers**: See the Standard preset only
- Click any preset to instantly apply its weights
- You can further customize weights after selecting a preset

### Student Roster

Upload and manage student rosters:
- Import CSV files
- Map columns (name, email, student ID)
- Supports multiple rosters for different periods

### Class Periods

Upload separate rosters for each class period for organized grading.

### Focus Roster Import (Volusia County)

Instead of manually uploading CSV rosters, you can import your class rosters directly from Focus SIS. Graider logs into Focus through VPortal, runs a saved report, and automatically populates your class periods with student names, IDs, parent contacts, schedules, and 504 status.

#### Prerequisites

1. **VPortal credentials** saved in Settings > Tools > District Portal
2. **Teacher Name** set in Settings (Graider matches your last name to filter your classes)
3. A **saved report in Focus** called exactly **"Student Data"** with the right columns (see below)

#### Setting Up the Saved Report in Focus

This is the most important step. You need to create a saved report in Focus **once**, and Graider will reuse it every time you import.

**Step-by-step:**

1. Log into **Focus** through VPortal
2. Go to **Reports > Saved Reports**
3. Click **New Report** (or edit an existing one)
4. Name the report exactly: **Student Data**
5. Add the following columns to the report:

| Column | Required? | What Graider Uses It For |
|--------|-----------|--------------------------|
| **Last, First** (student name) | Required | Student name on rosters and grading |
| **Student ID** | Required | Matching grades to students, Focus CSV exports |
| **Local ID** | Recommended | Secondary identifier |
| **Teacher / Period** | Required | Determines which period each student belongs to and filters to your classes only |
| **504 Plan** | Recommended | Flags students with 504 accommodations for modified feedback |
| **Primary Contact - First Name** | Recommended | Parent/guardian name |
| **Primary Contact - Last Name** | Recommended | Parent/guardian name |
| **Primary Contact - Relationship** | Recommended | Relationship to student |
| **Primary Contact - Cell Phone** | Recommended | Parent phone for communications |
| **Primary Contact - Call Out Number** | Optional | Alternate phone |
| **Primary Contact - Email** | Recommended | Parent email for sending feedback |
| **Secondary Contact - First Name** | Optional | Second guardian name |
| **Secondary Contact - Last Name** | Optional | Second guardian name |
| **Secondary Contact - Relationship** | Optional | Relationship to student |
| **Secondary Contact - Cell Phone** | Optional | Second guardian phone |
| **Third Contact - First Name** | Optional | Third contact name |
| **Third Contact - Last Name** | Optional | Third contact name |
| **Third Contact - Email** | Optional | Third contact email |
| **Third Contact - Cell Phone** | Optional | Third contact phone |

6. **Save the report**

> **Important:** The report must be named exactly **"Student Data"** — Graider looks for this name when it runs the import.

#### Running the Import

1. Go to **Settings > Class Periods**
2. Click **Import from Focus**
3. A browser window opens and logs into VPortal automatically
4. **Check your phone for 2FA approval** if prompted
5. Graider navigates to your saved report, runs it, and downloads the CSV
6. Students are automatically grouped by period based on the "Teacher / Period" column
7. Only your classes appear (filtered by your last name)

#### What Gets Imported

After a successful import, each period roster includes:
- Student name, Student ID, Local ID
- 504 plan status
- Up to 3 parent/guardian contacts with names, relationships, phone numbers, and emails
- Each student's full class schedule (all periods, teachers, and course codes)

#### Re-importing

You can re-run the import anytime — beginning of a new quarter, after schedule changes, or when new students enroll. The saved report in Focus stays in place, so it's just one click.

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

### AI Assistant Enhancements

- **Full Curriculum Standards Access**: The Assistant now knows ALL your curriculum standards at the start of every conversation — no keyword search needed. It can reference specific standard codes when generating lessons, worksheets, and assessments.
- **Resource-Aware Context**: Uploaded documents (pacing guides, school calendars, curriculum frameworks) are automatically read into the Assistant's context. It can answer "What should I teach next week?" using your actual pacing calendar.
- **Teaching Calendar**: Schedule lessons, add holidays, and view your upcoming calendar directly through the Assistant. Multi-day lessons auto-skip weekends and holidays.
- **Persistent Memory**: The Assistant remembers facts you share across conversations — class structure, preferences, workflow habits. No need to repeat yourself each session.
- **Voice Conversation**: Talk to the Assistant using your browser's microphone. Continuous listening with natural pause detection (~2 seconds of silence before sending). Optional voice responses via ElevenLabs.
- **Stop Mid-Response**: Cancel any response or document generation in progress with the stop button — no page refresh needed.
- **Clear Chat Without Losing Memory**: Clear the conversation window while keeping all saved memories intact.
- **Worksheet & Document Generation**: Create downloadable worksheets (Cornell Notes, fill-in-blank, vocabulary) with embedded answer keys, or formatted Word documents (study guides, parent letters, rubrics). Saves directly to Grading Setup.
- **Student Info & Contact Lookup**: Look up roster info, parent contacts, student schedules, and 504 status. Supports batch lookup for multiple students at once.
- **Missing Assignments Tool**: Find who hasn't submitted work — search by student, period, or assignment.
- **Differentiated Lesson Recommendations**: Lesson suggestions now include separate recommendations for advanced, standard, and support classes with DOK-appropriate standards, plus IEP/504 accommodation analysis.

### Grading Improvements

- **Multi-Provider Multipass Grading**: Claude (Anthropic) and Gemini (Google) models now support the full multipass grading pipeline, same as OpenAI. All providers produce per-question scoring, rubric breakdowns, and personalized feedback.
- **History-Aware Feedback**: Students with 3+ graded assignments receive personalized feedback that references their improvement trends, consistent strengths, and developing skills.
- **Token Cost Tracking**: Track API costs across all AI providers (OpenAI, Anthropic, Google) per grading session. Costs are logged to CSV for long-term tracking and visible in the cost analytics panel.
- **GPT-4o Feedback Generation**: Final feedback generation upgraded to GPT-4o for higher-quality, more specific student feedback.

### Other

- **Ensemble Grading**: Run assignments through multiple AI models simultaneously and use the median score for more reliable grading
- **Assessment Generator**: Create standards-aligned assessments with multiple question types, DOK level distribution, and export to Canvas QTI, Kahoot, Quizlet, or Google Forms
- **Student Portal**: Publish assessments with join codes for students to take online, with accommodation support and makeup exam mode
- **Focus SIS Automation**: Create assignments in Focus gradebook via browser automation from the Assistant
- **Outlook Email Integration**: Send feedback emails through your district Outlook account with SSO login support

*Last updated: February 16, 2026*
