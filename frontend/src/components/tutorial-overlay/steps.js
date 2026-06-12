export const TUTORIAL_STEPS = [
  // ── Welcome & Navigation ──────────────────────────────────────────
  {
    target: "sidebar-nav",
    tab: null,
    icon: "Layout",
    title: "Your Workspace",
    description:
      "Welcome to Graider! This sidebar is your main navigation. There are 9 tabs — Grade, Results, Grading Setup, Analytics, Planner, Script Builder, Assistant, Settings, and Help — each handling a different part of your teaching workflow. We'll walk through every section so you know exactly what each one does and how to use it.",
  },
  {
    target: "grade-toolbar",
    tab: "grade",
    icon: "Zap",
    title: "Toolbar: Start Grading & Auto-Grade",
    description:
      "This toolbar stays at the top of your screen. The 'Auto-Grade' toggle watches your assignments folder and automatically grades new files as they appear — great for when students submit work throughout the day. The 'Start Grading' button kicks off a manual grading run on all files in your folder. You'll see a progress counter while it's running.",
  },

  // ── Grade Tab ─────────────────────────────────────────────────────
  {
    target: "grade-card",
    tab: "grade",
    icon: "GraduationCap",
    title: "Grade Tab: Your Grading Hub",
    description:
      "This is where all grading happens. Set your assignments folder path in Settings > General, then come here to configure filters (class period, student, assignment) and start grading. The AI processes each student file — Word docs, PDFs, even photos of handwritten work — and generates scores with detailed feedback in real-time.",
  },
  {
    target: "grade-period-filter",
    tab: "grade",
    icon: "Users",
    title: "Filter by Class Period",
    description:
      "If you've uploaded a class roster in Settings > Classroom, your class periods appear here. Select a period to only grade files for students in that section. This is especially useful when you have multiple classes in the same folder — it prevents mixing up grades between periods. Leave on 'All Periods' to grade everything at once.",
  },
  {
    target: "grade-student-filter",
    tab: "grade",
    icon: "User",
    title: "Filter by Student",
    description:
      "Narrow your grading run to a single student. This is helpful when you need to re-grade one student's work, or when a student submitted late and you want to grade just their file without re-processing the entire class. If you've selected a class period, the dropdown shows only students from that period.",
  },
  {
    target: "grade-assignment-filter",
    tab: "grade",
    icon: "FileText",
    title: "Select Assignment Config",
    description:
      "Choose a saved assignment configuration to apply during grading. Assignment configs (created in the Grading Setup tab) tell the AI exactly how to grade: which sections to look for, what the expected answers are, how many points each section is worth, and what rubric to use. Without a config, the AI uses your default rubric settings.",
  },
  {
    target: "grade-individual",
    tab: "grade",
    icon: "Camera",
    title: "Individual Upload: Handwritten Work",
    description:
      "For paper-based or handwritten assignments, use this section. Take a photo or scan of a student's work, type their name (autocomplete from your roster), and hit 'Grade.' The AI uses GPT-4o's vision capability to read handwriting, identify answers, and grade just like it does for typed documents. Perfect for in-class worksheets and tests.",
  },

  // ── Results Tab ───────────────────────────────────────────────────
  {
    target: "results-card",
    tab: "results",
    icon: "FileText",
    title: "Results Tab: Review & Export",
    description:
      "After grading, all results appear here in a sortable table. Each row shows the student name, assignment, score, letter grade, and period. Click any row to expand it and see the full AI breakdown: per-section scores, specific feedback comments, and the AI's reasoning. You can edit scores and feedback inline before exporting.",
  },
  {
    target: "results-filters",
    tab: "results",
    icon: "Filter",
    title: "Sort & Filter Results",
    description:
      "Use these dropdowns to organize your results. Sort by score (high-low or low-high), name (A-Z), or date. Filter to see only approved, needs-review, handwritten, or typed submissions. You can also filter by class period and assignment to isolate exactly the grades you want to export. The 'Apply Curve' button appears when filtering by period.",
  },
  {
    target: "results-approval",
    tab: "results",
    icon: "CheckCircle",
    title: "Approve Grades Before Export",
    description:
      "This is your quality gate. Before exporting to Focus SIS or sending parent emails, you must check this box to confirm you've reviewed the AI grades. This prevents accidental exports of unreviewed data. Review each student's breakdown, make any adjustments, then check the approval box to unlock the export buttons.",
  },
  {
    target: "results-focus",
    tab: "results",
    icon: "Download",
    title: "Focus SIS Export",
    description:
      "Export grades to your school's Focus SIS gradebook. 'Focus Export' creates a single CSV file you can import manually. 'Batch Focus' generates per-period CSV files plus a comments file — one click, all periods handled. 'Upload Comments' uses browser automation to log into Focus and enter feedback comments for each student automatically. Set up your Focus credentials in Settings > Tools first.",
  },
  {
    target: "results-email",
    tab: "results",
    icon: "Mail",
    title: "Parent Communication",
    description:
      "Generate and send parent feedback emails. 'Parent Emails' creates personalized email drafts with each student's score, grade, and AI-generated feedback. 'Send via Outlook' opens a browser window that logs into your school Outlook account and sends the emails automatically. Parent contact emails are pulled from your class roster in Settings > Classroom.",
  },
  {
    target: "results-confirmations",
    tab: "results",
    icon: "MailCheck",
    title: "Submission Confirmations",
    description:
      "Send students a confirmation email listing which assignments they've submitted and which are still outstanding. Graider scans your assignments folder, matches each file to a student via the roster, and compares against your saved assignment configs to build a personalized checklist. Filter by period or individual student using the dropdowns. The 'CC Parents' checkbox adds the student's primary parent/guardian email (from your uploaded parent contacts) to the CC field, so parents stay informed about submission status. Only files matching a saved assignment config are counted — random or misnamed uploads won't appear in the list.",
  },

  // ── Grading Setup (Builder) Tab ───────────────────────────────────
  {
    target: "builder-card",
    tab: "builder",
    icon: "FileEdit",
    title: "Grading Setup: Configure Assignments",
    description:
      "This is where you tell the AI HOW to grade each assignment. Think of it as creating a grading blueprint: import the original assignment document, mark which sections students need to complete, add expected answers and grading instructions, choose a rubric type, and save. Once saved, you can reuse this config every time you grade that assignment.",
  },
  {
    target: "builder-saved",
    tab: "builder",
    icon: "FolderOpen",
    title: "Saved Assignment Configs",
    description:
      "All your saved assignment configurations appear here. Click one to load it for editing, or double-click to fully load it with the imported document. Each card shows the assignment name — configs highlighted in purple are currently loaded. Use the delete button (trash icon) to remove old configs. These are the same configs that appear in the Grade tab's assignment dropdown.",
  },
  {
    target: "builder-import",
    tab: "builder",
    icon: "FileUp",
    title: "Import Document & Mark Sections",
    description:
      "Click 'Choose File' to upload the original assignment (Word .docx or PDF). Graider parses the document and displays it with formatting preserved. You can then highlight sections of text and mark them as 'gradeable' (green) or 'excluded' (orange). Gradeable sections become markers that tell the AI where to find student responses. Excluded sections (like vocabulary lists or instructions) are ignored during grading.",
  },
  {
    target: "builder-markers",
    tab: "builder",
    icon: "Bookmark",
    title: "Marker Library",
    description:
      "Quick-add common section markers based on your subject. Click any suggested marker (like 'Explain:', 'Compare and contrast:', etc.) to add it to your assignment. Markers tell the AI where each gradeable section begins in student submissions. You can also type custom markers directly when importing a document. The library updates based on the subject you've set in Settings > General.",
  },
  {
    target: "builder-rubric",
    tab: "builder",
    icon: "Scale",
    title: "Assignment Rubric Type",
    description:
      "Override the default rubric for this specific assignment. Choose 'Standard' for essays and written responses, 'Cornell Notes' for note-taking assignments, 'Fill-in-the-Blank' for worksheets with specific expected answers, or 'Custom' to define your own rubric categories and weights. Each type adjusts how the AI evaluates and scores student work.",
  },
  {
    target: "builder-notes",
    tab: "builder",
    icon: "StickyNote",
    title: "Grading Notes & Expected Answers",
    description:
      "This is one of the most powerful fields. Enter specific instructions the AI should follow when grading THIS assignment. Include expected answers (e.g., '1803, France, 15 million'), key vocabulary definitions, acceptable answer variations, or notes like 'accept any reasonable paraphrase.' These instructions are injected directly into the AI prompt, dramatically improving grading accuracy.",
  },
  {
    target: "builder-questions",
    tab: "builder",
    icon: "FileQuestion",
    title: "Questions & Point Values",
    description:
      "Define individual questions with point values for fine-grained scoring. Each question has a prompt (the question text), point value, and expected answer. The AI uses these to score each question separately and provide per-question feedback. Points are automatically summed. If you don't add questions, the AI scores the assignment holistically using the total points value above.",
  },
  {
    target: "builder-save",
    tab: "builder",
    icon: "Save",
    title: "Save & Export",
    description:
      "Configs auto-save whenever you make changes (indicated by the green checkmark). Click 'Save Now' to force an immediate save. 'Export Word Doc' and 'Export PDF' generate downloadable files of your assignment — useful for creating student copies from your marked-up template. All saved configs persist between sessions and appear in the Grade tab dropdown.",
  },

  // ── Analytics Tab ─────────────────────────────────────────────────
  {
    target: "analytics-card",
    tab: "analytics",
    icon: "BarChart3",
    title: "Analytics: Class Performance Overview",
    description:
      "The Analytics tab gives you a data-driven view of your classroom. Once you've graded assignments, this tab populates with summary statistics, interactive charts, trend analysis, and student-level breakdowns. It updates automatically as you grade more work. If you see 'No Data Yet,' grade some assignments first and come back. Let's walk through each section.",
  },
  {
    target: "analytics-filters",
    tab: "analytics",
    icon: "Filter",
    title: "Analytics Filters & Export",
    description:
      "Filter your analytics by class period and academic quarter to compare performance across sections or time frames. The Period dropdown shows each class you've set up in your roster. The Quarter dropdown lets you isolate Q1, Q2, etc. The 'Export District Report' button generates a JSON report with all analytics data — useful for submitting to administrators or tracking compliance.",
  },
  {
    target: "analytics-stats",
    tab: "analytics",
    icon: "FileCheck",
    title: "Summary Stats Cards",
    description:
      "Four at-a-glance metrics for your class: Total Graded (number of assignments processed), Students (unique students graded), Class Average (mean score across all graded work), and Highest Score (the top mark achieved). These cards update in real-time as you grade and respond to the period/quarter filters above.",
  },
  {
    target: "analytics-charts",
    tab: "analytics",
    icon: "PieChart",
    title: "Grade Distribution & Assignment Averages",
    description:
      "Two side-by-side charts. The pie chart on the left shows the A/B/C/D/F breakdown across all graded work — hover over slices for exact counts. The bar chart on the right shows the average score for each assignment, making it easy to spot which assignments were too easy, too hard, or well-calibrated. Both charts respect your active filters.",
  },
  {
    target: "analytics-scatter",
    tab: "analytics",
    icon: "Target",
    title: "Proficiency vs Growth Scatterplot",
    description:
      "This interactive chart plots every student as a dot: X-axis is their average score (proficiency), Y-axis is how much they've improved (growth). Students are color-coded: green = star performers, orange = improving, purple = stable, red = needs support. Click any dot to select that student and see their detailed breakdown below. The dashed lines mark the 70% proficiency threshold and zero-growth line.",
  },
  {
    target: "analytics-progress",
    tab: "analytics",
    icon: "TrendingUp",
    title: "Student Progress Over Time",
    description:
      "A line chart showing scores over time. By default it shows all students overlaid — click a student name (from the scatter plot or the lists below) to isolate their individual trend line. When a student is selected, you'll also see their personal stats: average, highest, lowest, and total assignments. Use this to track improvement or identify regression patterns.",
  },
  {
    target: "analytics-alerts",
    tab: "analytics",
    icon: "AlertTriangle",
    title: "Needs Attention & Top Performers",
    description:
      "Two side-by-side lists. 'Needs Attention' (red) highlights students with low averages or declining trends — these students may need intervention, re-teaching, or accommodation adjustments. 'Top Performers' (green) recognizes your highest-achieving students with their averages and trend indicators. Click any student name to jump to their detailed progress view above.",
  },

  // ── Planner Tab ───────────────────────────────────────────────────
  {
    target: "planner-card",
    tab: "planner",
    icon: "BookOpen",
    title: "Planner: Lessons, Assessments & Calendar",
    description:
      "The Planner is your curriculum command center. It has four modes: Lesson Planning (browse standards and generate AI lesson plans), Assessment Generator (create quizzes and tests aligned to standards), Student Portal (publish assignments for students to complete online), and Calendar (drag-and-drop lesson scheduling with a monthly view). Each mode is accessible from the toggle buttons at the top.",
  },
  {
    target: "planner-modes",
    tab: "planner",
    icon: "ToggleLeft",
    title: "Planner Mode Toggle",
    description:
      "Switch between the four planner modes here. 'Lesson Planning' lets you select state standards and generate full lesson plans with objectives, activities, and assessments. 'Assessment Generator' creates standards-aligned quizzes and tests. 'Student Portal' manages published assessments that students can access online. 'Calendar' gives you a monthly drag-and-drop view to schedule and rearrange your lessons.",
  },

  // ── Script Builder Tab ───────────────────────────────────────────
  {
    target: "automation-card",
    tab: "automations",
    icon: "Cpu",
    title: "Script Builder: Browser Automation",
    description:
      "The Script Builder lets you create, save, and run Playwright browser automations — no coding required. Automate repetitive portal tasks like screenshotting textbook pages from NGL Sync, exporting gradebook data from Focus, or pulling attendance reports. Each automation is a sequence of steps (navigate, click, fill, screenshot, etc.) that runs in a real browser window.",
  },
  {
    target: "automation-toolbar",
    tab: "automations",
    icon: "Plus",
    title: "Create & Manage Automations",
    description:
      "Click 'New Automation' to build a workflow from scratch, or start from a pre-built template below. Your saved automations appear as cards — each shows the workflow name, description, and step count. Click a card to edit it, hit 'Run' to launch it, or delete workflows you no longer need. Automations are saved locally and persist between sessions.",
  },
  {
    target: "automation-templates",
    tab: "automations",
    icon: "FileCode",
    title: "Templates: Pre-Built Workflows",
    description:
      "Templates are starter workflows for common school portal tasks. Click a template to create a copy you can customize. Available templates include NGL Sync screenshots (captures consecutive textbook pages) and Focus Gradebook screenshots. Templates use your saved portal credentials from Settings > Tools, so make sure those are configured first.",
  },

  // ── Assistant Tab ─────────────────────────────────────────────────
  {
    target: "assistant-chat",
    tab: "assistant",
    icon: "Sparkles",
    title: "AI Teaching Assistant",
    description:
      "Chat with an AI assistant that has full context about your class: student roster, grading history, assignment configs, and uploaded resources. Ask it to help write lesson plans, create assignment rubrics, analyze student performance trends, draft parent communications, brainstorm differentiation strategies, or explain grading results. Conversations are saved and persist between sessions.",
  },

  // ── Settings Tab ──────────────────────────────────────────────────
  {
    target: "settings-general",
    tab: "settings",
    settingsTab: "general",
    icon: "FolderOpen",
    title: "Settings: General",
    description:
      "Configure your basic setup. Set the Assignments Folder (where student files are stored) and Output Folder (where exports go). Enter your teacher name, school name, grade level, and subject — these are used in AI prompts for age-appropriate grading and in exported documents. You can also set your email signature for parent communications.",
  },
  {
    target: "settings-grading",
    tab: "settings",
    settingsTab: "grading",
    icon: "ClipboardCheck",
    title: "Settings: Rubric & Grading Style",
    description:
      "Define your default rubric categories (Content Knowledge, Critical Thinking, Writing Quality, Effort, etc.) with percentage weights that sum to 100%. Set the grading style to Lenient (forgiving of minor errors), Standard (balanced), or Strict (high expectations). Add global AI instructions that apply to ALL grading runs — like 'always give specific examples in feedback' or 'be encouraging for 6th graders.'",
  },
  {
    target: "settings-ai",
    tab: "settings",
    settingsTab: "ai",
    icon: "Sparkles",
    title: "Settings: AI Models & API Keys",
    description:
      "Choose which AI model powers your grading and enter your API key. GPT-4o (OpenAI) is fast and accurate for most assignments. Claude (Anthropic) excels at nuanced written feedback and longer responses. Gemini (Google) offers a generous free tier to get started. You can also configure which model the AI Assistant uses. Multiple keys can be saved — the grader uses whichever you select.",
  },
  {
    target: "settings-classroom",
    tab: "settings",
    settingsTab: "classroom",
    icon: "Users",
    title: "Settings: Roster & Accommodations",
    description:
      "Upload your class roster (CSV file or paste a screenshot) so Graider can match student names to their files automatically. Set up class periods, add IEP/504 accommodations per student (the AI adjusts grading expectations accordingly), and enter parent contact emails for the email export feature. Student data stays local on your machine and is never sent to external servers.",
  },
  {
    target: "settings-integration",
    tab: "settings",
    settingsTab: "integration",
    icon: "Laptop",
    title: "Settings: Tools & Integrations",
    description:
      "Select which EdTech tools your school provides (Google Classroom, Kahoot, Nearpod, etc.) — AI lesson plans will only suggest activities using tools you have access to. Configure your Focus SIS (VPortal) credentials for automated grade uploads and comment entry. Set up Outlook integration for sending parent emails directly from the app.",
  },
  {
    target: "settings-privacy",
    tab: "settings",
    settingsTab: "privacy",
    icon: "Shield",
    title: "Settings: Privacy & Data",
    description:
      "Control how your data is handled. Review what information is sent to AI providers during grading (student work text, but never names). See where local data is stored on your machine. Clear cached results, reset settings to defaults, or export all your configuration data. Student privacy is a top priority — all roster data and grades are stored locally, never in the cloud.",
  },
  {
    target: "resources-upload",
    tab: "settings",
    settingsTab: "resources",
    icon: "FolderOpen",
    title: "Settings: Resources",
    description:
      "Upload supporting documents your AI assistant can reference: pacing guides, district rubrics, textbook chapters, curriculum maps, and answer keys. These files enhance both grading accuracy and lesson planning — the AI references them when generating feedback, creating lesson plans, and answering questions in the Assistant chat. Choose a document type, add a description, and click Upload.",
  },
];
