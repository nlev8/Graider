# 🎓 Graider

**AI-Powered Grading Assistant for Educators**

Graider automates the grading process using AI, saving teachers hours of work while providing detailed, personalized feedback to students.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## ✨ Features

### 📝 Auto-Grading
- Grade Word docs, PDFs, and images
- AI evaluates content accuracy, completeness, and reasoning
- Generates detailed feedback and letter grades
- Tracks already-graded files to avoid duplicates

### 📊 Results Management
- View all grades in a sortable table
- Review and edit individual grades
- Export to CSV for Focus/SIS import

### 📧 Email Integration
- Auto-generate personalized feedback emails
- Preview before sending
- Send directly via Gmail SMTP

### 📄 Assignment Builder
- Import existing Word/PDF assignments
- Mark gradeable sections visually
- Add custom AI grading instructions
- Export assignments with answer keys

### 📚 Lesson Planner
- Browse state standards (Florida B.E.S.T.)
- AI-generated comprehensive lesson plans
- Detailed timing, activities, and assessments
- Essential questions and learning objectives
- Differentiation strategies included
- Export to Word

### ⚡ Auto-Grade Mode
- Watches folder for new submissions
- Automatically grades when files appear
- Perfect for OneDrive/SharePoint sync

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key

### Installation

```bash
# Clone the repo
git clone https://github.com/acrionas/Graider.git
cd Graider

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env

# Run
python graider_app.py
```

Open http://localhost:3000 in your browser.

### Gmail Setup (for emails)

1. Enable 2FA on your Gmail account
2. Generate an App Password: Google Account → Security → App Passwords
3. Configure in Settings tab or create `~/.graider_email.json`:

```json
{
  "email": "your.email@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx"
}
```

---

## 📁 Project Structure

```
graider/
├── graider_app.py      # Main application
├── assignment_grader.py # Core grading logic
├── email_sender.py     # Email functionality
├── requirements.txt    # Python dependencies
├── .env               # API keys (not in repo)
└── .gitignore
```

---

## ⚙️ Configuration

### Settings Tab
| Setting | Description |
|---------|-------------|
| Assignments Folder | Where student submissions are |
| Output Folder | Where results are saved |
| Roster File | Excel file with student names/emails |
| Assignment Name | Name for this grading session |
| OpenAI API Key | Your API key |

### OneDrive Sync
Point the Assignments Folder to your OneDrive sync location:
```
/Users/you/Library/CloudStorage/OneDrive-YourOrg/Assignments
```

---

## 🛠️ Dependencies

```
flask>=2.0.0
flask-cors>=3.0.0
openai>=1.0.0
python-docx>=0.8.11
openpyxl>=3.0.0
python-dotenv>=0.19.0
Pillow>=9.0.0
pymupdf>=1.23.0
mammoth>=1.6.0
reportlab>=4.0.0
```

---

## 🔒 Privacy & Security

- **Student data is never uploaded to GitHub** - see `.gitignore`
- All grading happens via API calls to OpenAI
- Roster files and grades are stored locally only
- FERPA compliance is your responsibility

---

## 📋 Roadmap

### Completed
- [x] AI Grading with GPT-4
- [x] Email Integration (Gmail SMTP)
- [x] Document Import & Marking
- [x] Auto-Grade Mode (folder watching)
- [x] Lesson Planner with State Standards
- [x] Student Progress Tracking
- [x] IEP/504 Accommodations Support
- [x] Bilingual Feedback (ELL Support)
- [x] Academic Integrity Detection

### In Progress
- [ ] Rubric Builder UI
- [ ] Multi-class/Period Management
- [ ] Enhanced Analytics Dashboard

### Planned
- [ ] Cloud Deployment Option
- [ ] District Admin Panel
- [ ] SSO Integration (Clever, ClassLink)
- [ ] LMS Integration (Canvas, Schoology)

---

## 🚀 Deployment Plan

### Current: Local-First (v1.0)

Graider runs entirely on the teacher's machine — no cloud required.

```
Teacher's Computer
├── Graider App (Python/Flask)
├── Student Files (local folder)
├── Grades & Feedback (local storage)
└── API calls to OpenAI (content only, no PII)
```

**Best for:** Individual teachers, pilot programs, privacy-sensitive schools

### Phase 2: Cloud Option (v2.0)

Optional cloud deployment for schools wanting central management.

```
┌─────────────────────────────────────────┐
│           Cloud Dashboard               │
│  • Admin panel for principals           │
│  • Usage analytics                       │
│  • Shared rubrics & templates           │
└─────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   School A                School B
   Teachers                Teachers
```

**Requirements:**
- Data Processing Agreement (DPA) with district
- SOC 2 Type I certification
- US-only hosting (AWS/GCP)

**Best for:** Schools/districts wanting visibility and central management

### Phase 3: Enterprise (v3.0)

Full district-scale deployment with SSO and integrations.

```
District Infrastructure
├── SSO (Clever, ClassLink, Google)
├── LMS Integration (Canvas, Schoology)
├── SIS Sync (PowerSchool, Infinite Campus)
├── District Analytics Dashboard
└── Multi-tenant Architecture
```

**Features:**
- Single sign-on for all teachers
- Automatic roster sync from SIS
- Grade passback to LMS
- District-wide reporting

**Best for:** Large districts with existing EdTech infrastructure

---

## 🏢 For Schools & Districts

### Pilot Program

1. **Start small** — 5-10 teachers for one semester
2. **Measure** — Track time savings, feedback quality
3. **Expand** — Roll out to department or school
4. **Scale** — District-wide deployment

### IT Requirements

| Deployment | Requirements |
|------------|--------------|
| **Local** | Python 3.9+, internet for API calls |
| **Cloud** | Modern browser, DPA signed |
| **Enterprise** | SSO provider, DPA, security review |

### Contact

For pilot programs or district pricing: [Contact Info]

---

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines first.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Flask team for the web framework
- python-docx and mammoth for document processing
- All the teachers who provided feedback

---

**Made with ❤️ for educators**
