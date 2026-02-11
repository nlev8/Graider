# Graider

**AI-Powered Grading Assistant for Educators**

Graider automates the grading process using AI, saving teachers hours of work while providing detailed, personalized feedback to students. Generate standards-aligned assessments, publish them to a student portal, and grade submissions automatically.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![React](https://img.shields.io/badge/React-18-61dafb.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Live Demo:** [graider.live](https://graider.live)

---

## Features

### Auto-Grading
- Grade Word docs, PDFs, and images (including handwritten work)
- AI evaluates content accuracy, completeness, and reasoning
- Generates detailed feedback and letter grades
- Tracks already-graded files to avoid duplicates
- Academic integrity detection

### Assessment Generator
- Generate standards-aligned assessments from state standards (Florida B.E.S.T.)
- Multiple question types: Multiple Choice, Short Answer, Extended Response, True/False, Matching
- Configurable DOK (Depth of Knowledge) levels 1-4
- Set total questions and points with automatic distribution
- Export to Word, PDF, or platform formats (Canvas QTI, Kahoot, Quizlet, Google Forms)

### Student Portal
- Publish assessments with unique join codes
- Students access via `graider.live/join` or direct link
- Real-time grading with immediate feedback
- Supports all question types including matching and written responses
- Mobile-friendly interface

### Teacher Dashboard
- View all published assessments and submission counts
- Track student scores and completion times
- Toggle assessments active/inactive
- Export results for gradebook import

### Makeup Exams & Accommodations
- Save assessments locally for reuse
- Restrict assessments to specific students (makeup exams)
- Organize assessments by class period
- Apply IEP/504 accommodations per student
- Extended time and modified instructions support

### Lesson Planner
- Browse state standards (Florida B.E.S.T.)
- AI-generated comprehensive lesson plans
- Detailed timing, activities, and assessments
- Essential questions and learning objectives
- Differentiation strategies included
- Generate assignments directly from lesson plans

### Results Management
- View all grades in a sortable table
- Sort by time, name, score, assignment, or grade
- Review and edit individual grades
- Export to CSV for Focus/SIS import

### Email Integration
- Auto-generate personalized feedback emails
- Bilingual support (English/Spanish) for ELL students
- Preview before sending
- Send directly via Resend API or Gmail SMTP

### Assignment Builder
- Import existing Word/PDF assignments
- Mark gradeable sections visually
- Add custom AI grading instructions
- Export assignments with answer keys

### Auto-Grade Mode
- Watches folder for new submissions
- Automatically grades when files appear
- Perfect for OneDrive/SharePoint sync

---

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+ (for frontend development)
- OpenAI API key
- Supabase account (for Student Portal)

### Installation

```bash
# Clone the repo
git clone https://github.com/acrionas/Graider.git
cd Graider

# Install backend dependencies
pip install -r requirements.txt

# Create .env file in backend folder
cat > backend/.env << EOF
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key  # Optional, for Claude
RESEND_API_KEY=your-resend-key        # For email
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key
EOF

# Run the app
cd backend
python app.py
```

Open http://localhost:3000 in your browser.

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173 with hot reload.

### Build for Production

```bash
cd frontend
npm run build  # Builds to backend/static
```

---

## Project Structure

```
graider/
├── backend/
│   ├── app.py                 # Main Flask application
│   ├── routes/
│   │   ├── grading_routes.py  # Grading endpoints
│   │   ├── planner_routes.py  # Lesson planner & assessment generation
│   │   ├── student_portal_routes.py  # Student portal & teacher dashboard
│   │   └── settings_routes.py # Configuration endpoints
│   ├── static/                # Built frontend (auto-generated)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React application
│   │   ├── components/
│   │   │   └── StudentPortal.jsx  # Student-facing assessment UI
│   │   └── services/
│   │       └── api.js        # API client
│   └── package.json
├── assignment_grader.py      # Core grading logic
├── email_sender.py           # Email functionality
└── CLAUDE.md                 # Development guidelines
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 grading |
| `ANTHROPIC_API_KEY` | Anthropic API key (optional, for Claude) |
| `RESEND_API_KEY` | Resend API key for email delivery |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |

### Supabase Setup

Create these tables in your Supabase project:

```sql
-- Published assessments
CREATE TABLE published_assessments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  join_code TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  assessment JSONB NOT NULL,
  settings JSONB DEFAULT '{}',
  teacher_name TEXT,
  teacher_email TEXT,
  is_active BOOLEAN DEFAULT true,
  submission_count INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Student submissions
CREATE TABLE submissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  join_code TEXT NOT NULL REFERENCES published_assessments(join_code),
  student_name TEXT NOT NULL,
  answers JSONB NOT NULL,
  results JSONB,
  score NUMERIC,
  total_points NUMERIC,
  percentage NUMERIC,
  time_taken_seconds INTEGER,
  submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Local Storage Paths

| Path | Description |
|------|-------------|
| `~/.graider_rubric.json` | Rubric settings |
| `~/.graider_settings.json` | Global AI notes |
| `~/.graider_assignments/` | Saved assignment configs |
| `~/.graider_saved_assessments/` | Saved assessments for reuse |
| `~/.graider_periods/` | Class period rosters |
| `~/.graider_accommodations/` | IEP/504 accommodation settings |

---

## Deployment

### Railway (Recommended)

1. Connect your GitHub repo to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

**Procfile:**
```
web: cd backend && gunicorn app:app --bind 0.0.0.0:$PORT
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:8000"]
```

---

## API Reference

### Grading
- `POST /api/grade` - Start grading job
- `GET /api/status` - Get grading status/progress
- `POST /api/stop-grading` - Stop current grading

### Assessment Generator
- `POST /api/get-standards` - Get curriculum standards
- `POST /api/generate-assessment` - Generate AI assessment
- `POST /api/export-assessment` - Export to Word/PDF

### Student Portal
- `POST /api/publish-assessment` - Publish assessment (returns join code)
- `GET /api/student/join/:code` - Get assessment for student
- `POST /api/student/submit/:code` - Submit student answers

### Teacher Dashboard
- `GET /api/teacher/assessments` - List published assessments
- `GET /api/teacher/assessment/:code/results` - Get submissions
- `POST /api/teacher/assessment/:code/toggle` - Toggle active status

### Saved Assessments
- `POST /api/save-assessment` - Save assessment locally
- `GET /api/list-saved-assessments` - List saved assessments
- `POST /api/load-saved-assessment` - Load saved assessment
- `POST /api/delete-saved-assessment` - Delete saved assessment

---

## AI Grading Factors Reference

Every grading decision accounts for the following factors. All factors must reach the AI grader — dropping any factor produces incorrect or generic results.

### Per-Question Grading Factors

| # | Factor | Source | Description |
|---|--------|--------|-------------|
| 1 | **Global AI Instructions** | Settings tab | Teacher's global notes applied to all assignments (e.g., "Be lenient on spelling", "These are ELL students") |
| 2 | **Assignment Grading Notes** | Grading Setup / Builder | Per-assignment notes with expected answers, vocabulary definitions, summary key points |
| 3 | **Custom Rubric** | Settings tab | Teacher's custom rubric categories, weights, and descriptions (e.g., Content Accuracy: 40pts, Completeness: 25pts) |
| 4 | **Rubric Type Override** | Assignment config | Per-assignment rubric type (cornell-notes, fill-in-blank, standard) that adjusts grading behavior |
| 5 | **Grading Style** | Settings tab | lenient / standard / strict — affects AI prompt instructions and post-grading score caps |
| 6 | **IEP/504 Accommodations** | Accommodations config | Per-student accommodations (modified instructions, simplified language, adjusted expectations) |
| 7 | **Student History** | Auto-tracked | Past assignment scores, improvement streaks, trend context for personalized feedback |
| 8 | **Class Period Differentiation** | Period rosters | Different grading expectations per class period (e.g., honors vs regular) |
| 9 | **Expected Answers** | Grading notes | Parsed from gradingNotes, matched to questions by number, text, term name, or index |
| 10 | **Grade Level** | Grading config | Student's grade level — sets age-appropriate expectations |
| 11 | **Subject** | Assignment config | Assignment subject area (Social Studies, ELA, Science, etc.) |
| 12 | **Section Type** | Extraction | Whether this is a vocab term, numbered question, FITB, summary, or written response — each type has specific grading criteria |
| 13 | **Section Name** | Markers | The marker section this belongs to (VOCABULARY, QUESTIONS, SUMMARY) |
| 14 | **Points Possible** | Marker config / distribution | Per-question point allocation with score anchors |

### Feedback Generation Factors

| # | Factor | Description |
|---|--------|-------------|
| 15 | **Student Actual Answers** | The literal text students wrote — AI quotes specifics in feedback |
| 16 | **ELL Language** | If student is ELL, feedback is translated to their native language |
| 17 | **Per-Question Results** | Scores, reasoning, and quality labels from the grading pass |

### Score Aggregation Factors

| # | Factor | Description |
|---|--------|-------------|
| 18 | **Effort Points** | Configurable points for effort/engagement (default 15 of 100) |
| 19 | **Completeness Caps** | Missing sections cap the maximum achievable score (e.g., 1 blank = max 89) |
| 20 | **Marker Config** | Section-based point distribution and section grading types |

### AI / Plagiarism Detection Factors

| # | Factor | Description |
|---|--------|-------------|
| 21 | **FITB Exemption** | Fill-in-the-blank answers exempt from AI/plagiarism detection (matching source text is expected) |
| 22 | **Writing Style Profile** | Student's historical writing patterns compared against current submission |

### Extraction Factors

| # | Factor | Description |
|---|--------|-------------|
| 23 | **Assignment Template** | The original worksheet template — used to strip prompt/instruction text from extracted student responses |
| 24 | **Custom Markers** | Section markers (VOCABULARY, QUESTIONS, SUMMARY) that define extractable regions |
| 25 | **Exclude Markers** | Markers to skip during extraction |

### Data Flow (Multipass Pipeline)

```
app.py builds file_ai_notes (factors 1-2, 4, 6-8)
    + rubric_prompt (factor 3)
    + grading_style (factor 5)
         |
         v
grade_with_parallel_detection()
    |                    |
    v                    v
grade_multipass()    detect_ai_plagiarism()
    |
    |-- extract_student_responses() (factors 23-25)
    |-- _parse_expected_answers() (factor 9)
    |-- effective_instructions = ai_notes + rubric_prompt
    |
    |-- grade_per_question() x N  (factors 1-14, parallel)
    |       receives: effective_instructions, grading_style,
    |       expected_answer, grade_level, subject, section info
    |
    |-- Aggregate scores (factors 18-20)
    |
    |-- generate_feedback() (factors 15-17)
    |       receives: effective_instructions, student_responses,
    |       question_results, ell_language
    |
    v
Final result with score, feedback, detection flags, audit trail
```

---

## Privacy & Security

- **FERPA Compliant Design** - Student data stored locally by default
- **No PII to OpenAI** - Only assignment content sent for grading
- **Supabase Security** - Row-level security for cloud data
- **Local-First Option** - Run entirely on teacher's machine
- **IEP/504 Data** - Stored locally, never sent to cloud without consent

---

## Roadmap

### Completed
- [x] AI Grading with GPT-4
- [x] Email Integration (Resend/Gmail)
- [x] Document Import & Marking
- [x] Auto-Grade Mode (folder watching)
- [x] Lesson Planner with State Standards
- [x] Assessment Generator
- [x] Student Portal with Join Codes
- [x] Teacher Dashboard
- [x] Makeup Exam Support
- [x] IEP/504 Accommodations
- [x] Bilingual Feedback (ELL Support)
- [x] Academic Integrity Detection
- [x] Cloud Deployment (Railway + Supabase)

### In Progress
- [ ] Multi-district Analytics
- [ ] Enhanced Reporting Dashboard
- [ ] Question Bank Management

### Planned
- [ ] SSO Integration (Clever, ClassLink)
- [ ] LMS Integration (Canvas, Schoology)
- [ ] SIS Grade Passback
- [ ] Mobile App

---

## For Schools & Districts

### Pilot Program

1. **Start small** - 5-10 teachers for one semester
2. **Measure** - Track time savings, feedback quality
3. **Expand** - Roll out to department or school
4. **Scale** - District-wide deployment

### IT Requirements

| Deployment | Requirements |
|------------|--------------|
| **Local** | Python 3.9+, internet for API calls |
| **Cloud** | Modern browser, Supabase account |
| **Enterprise** | SSO provider, DPA, security review |

---

## Contributing

Contributions welcome! Please read CLAUDE.md for development guidelines.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- OpenAI for GPT-4 API
- Anthropic for Claude API
- Supabase for database hosting
- Railway for deployment
- All the teachers who provided feedback

---

**Made with care for educators**
