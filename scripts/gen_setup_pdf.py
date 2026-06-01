#!/usr/bin/env python3
"""Generate the Graider brand-setup instruction PDF (off-platform SEO/GEO tasks).

Output: docs/seo/Graider-Brand-Setup-Instructions.pdf
Run: source venv/bin/activate && python scripts/gen_setup_pdf.py
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path("docs/seo/Graider-Brand-Setup-Instructions.pdf")
PURPLE = colors.HexColor("#7c3aed")
DARK = colors.HexColor("#1f2937")
GRAY = colors.HexColor("#6b7280")
LIGHT = colors.HexColor("#f3f0ff")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], textColor=PURPLE, fontSize=24, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=ss["Normal"], textColor=GRAY, fontSize=11, spaceAfter=14)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=PURPLE, fontSize=15,
                    spaceBefore=16, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], textColor=DARK, fontSize=10.5,
                      leading=15, spaceAfter=6, alignment=TA_LEFT)
STEP = ParagraphStyle("STEP", parent=BODY, leftIndent=4)
NOTE = ParagraphStyle("NOTE", parent=BODY, textColor=GRAY, fontSize=9.5, leading=13)
COPY = ParagraphStyle("COPY", parent=ss["Code"], fontName="Courier", fontSize=8.8,
                      textColor=DARK, leading=12, leftIndent=6, rightIndent=6,
                      spaceBefore=4, spaceAfter=4)


def esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def copybox(text: str):
    """A light-purple boxed 'paste this' block."""
    p = Paragraph(esc(text).replace("\n", "<br/>"), COPY)
    t = Table([[p]], colWidths=[6.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, PURPLE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def steps(items):
    return ListFlowable(
        [ListItem(Paragraph(esc(x), STEP), value=i + 1) for i, x in enumerate(items)],
        bulletType="1", leftIndent=18, bulletColor=PURPLE,
    )


def rule():
    return HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#e5e7eb"),
                      spaceBefore=10, spaceAfter=4)


flow = []
flow.append(Paragraph("Graider — Brand Setup Checklist", H1))
flow.append(Paragraph("Own &ldquo;Graider&rdquo; in Google &amp; AI search &mdash; exactly what you need to do", SUB))

flow.append(Paragraph(
    "Each account below makes Google and AI assistants (ChatGPT, Claude, Perplexity) "
    "recognize <b>graider.live</b> as &ldquo;Graider&rdquo; and separate you from the German "
    "competitor at graider.de. The website's structured data already points at these "
    "profiles &mdash; standing them up makes those links valid. <b>Do them in the order shown</b>, "
    "and after each one, <b>send the live URL back</b> so it gets confirmed on the site.", BODY))

# Canonical identity box
flow.append(Paragraph("Use these details identically on every platform", H2))
ident = [
    ["Name", "Graider  (always one capital G — never grAIder)"],
    ["Website", "https://graider.live"],
    ["Category", "Educational Technology / AI Grading"],
    ["Location", "United States"],
    ["Logo", "graider-brain-light.png  (in the landing/ folder)"],
    ["Tagline", "AI grading & planning assistant for 6–12 teachers"],
]
it = Table([[Paragraph(f"<b>{esc(k)}</b>", NOTE), Paragraph(esc(v), NOTE)] for k, v in ident],
           colWidths=[1.2 * inch, 5.5 * inch])
it.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#eeeeee")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
flow.append(it)
flow.append(Paragraph(
    "<b>Already done:</b> X / Twitter — <font face='Courier'>x.com/graiderlive</font> "
    "(the username <i>graider</i> was taken, so X is the one exception; the display name is still "
    "&ldquo;Graider&rdquo;).", NOTE))

# 1. Wikidata
flow.append(rule())
flow.append(Paragraph("1.  Wikidata  &mdash;  do this first (biggest impact on AI answers)", H2))
flow.append(Paragraph(
    "AI assistants lean on Wikidata to answer &ldquo;what is X?&rdquo;. grAIder has no Wikidata "
    "entry, so this is the single best move to own the name in AI answers.", BODY))
flow.append(steps([
    "Go to wikidata.org and create a free account.",
    "Click “Create a new item.”",
    "Fill in the fields exactly as shown in the box below.",
    "Add the statements (click “+ add statement” for each).",
    "Save, then copy the item URL (it looks like wikidata.org/wiki/Q123456789) and send it back.",
]))
flow.append(copybox(
    "Label (English):  Graider\n"
    "Description:       AI-powered grading and planning assistant for K-12 teachers\n"
    "Aliases:          Graider app, Graider AI, graider.live\n"
    "\n"
    "Statements:\n"
    "  instance of (P31)        -> software\n"
    "  official website (P856)  -> https://graider.live\n"
    "  country of origin (P495) -> United States\n"
    "  industry (P452)          -> educational technology\n"
    "  inception (P571)         -> 2026"))
flow.append(Paragraph(
    "Tip: Wikidata likes an outside source. If it asks, doing Product Hunt (step 2) first gives "
    "you one to reference. This item is about <i>your</i> US product at graider.live — do not "
    "merge it with the German grAIder.", NOTE))

# 2. Product Hunt
flow.append(rule())
flow.append(Paragraph("2.  Product Hunt  &mdash;  a backlink + an independent source in one", H2))
flow.append(steps([
    "Go to producthunt.com and sign in.",
    "Add a new product named “Graider” (you can launch later — the page itself is the win).",
    "Paste the tagline, description, and first comment from the box below. Add the logo and link graider.live.",
    "Copy the product URL and send it back.",
]))
flow.append(copybox(
    "Tagline:  Grade 100 papers in minutes — AI grading + planning for teachers\n"
    "\n"
    "Description:\n"
    "Graider is the AI teaching assistant for grades 6-12. It grades student work in\n"
    "minutes with per-question feedback (you approve every grade), then generates lesson\n"
    "plans, worksheets, and class analytics - the whole teaching loop in one tool. 3-pass\n"
    "grading evaluates 18 contextual factors per question, including your rubric, IEP/504\n"
    "accommodations, and student history. Runs on GPT-4o, Claude, or Gemini. Integrates\n"
    "with Clever, ClassLink, and OneRoster. FERPA-compliant, free tier available.\n"
    "\n"
    "First comment (as the maker):\n"
    "Teachers spend 5+ hours a week grading. We built Graider to give that time back -\n"
    "without handing the grade to a black box. Every grade is AI-drafted and teacher-\n"
    "approved. We'd love feedback from educators on what would make this a daily driver.\n"
    "\n"
    "Topics:  Education, Artificial Intelligence, Productivity, Teaching"))

# 3. LinkedIn
flow.append(rule())
flow.append(Paragraph("3.  LinkedIn Company Page  &mdash;  fast credibility signal", H2))
flow.append(steps([
    "On linkedin.com, click the Work grid icon (top right) → “Create a Company Page” → Small business.",
    "Name: Graider.  Try the page URL slug “graider”.  Website: graider.live.  Industry: E-Learning Providers.",
    "Upload the logo, then paste the About text from the box below.",
    "Copy the page URL (linkedin.com/company/...) and send it back.",
]))
flow.append(copybox(
    "Graider is an AI-powered grading and planning assistant built for grades 6-12\n"
    "teachers. It grades student assignments - typed in our student portal, or uploaded as\n"
    "Word, PDF, or photos of handwritten work - in minutes, with detailed per-question\n"
    "feedback the teacher reviews and approves before anything is finalized. Beyond grading,\n"
    "Graider generates standards-aligned lesson plans, builds worksheets and assessments,\n"
    "and surfaces real-time class analytics, combining the full teaching loop in one tool.\n"
    "It runs on GPT-4o, Claude, or Gemini (teacher's choice), integrates with Clever,\n"
    "ClassLink, and OneRoster for rostering and SSO, supports IEP/504 accommodations and\n"
    "ELL feedback, and is FERPA-compliant. Built in the United States for US K-12 classrooms."))

# 4. Crunchbase
flow.append(rule())
flow.append(Paragraph("4.  Crunchbase  &mdash;  quick free company profile", H2))
flow.append(steps([
    "On crunchbase.com, use “Add” → add a company (free).",
    "Name: Graider.  Website: graider.live.  Location: United States.  Founded: 2026.",
    "Paste the description from the box below.",
    "Copy the profile URL and send it back.",
]))
flow.append(copybox(
    "Graider is an AI-powered grading and planning assistant for grades 6-12 that grades\n"
    "student work in minutes, generates lesson plans, and tracks student progress - with the\n"
    "teacher approving every grade."))

# What to send back
flow.append(rule())
flow.append(Paragraph("When you're done: send these back", H2))
flow.append(Paragraph(
    "Paste the live URLs here and they get confirmed in the website's structured data "
    "(the X one is already wired):", BODY))
flow.append(steps([
    "Wikidata item URL  (wikidata.org/wiki/Q...)",
    "Product Hunt product URL",
    "LinkedIn company page URL",
    "Crunchbase profile URL",
]))
flow.append(Paragraph(
    "If any platform won't give you the &ldquo;graider&rdquo; slug (like X forced "
    "&ldquo;graiderlive&rdquo;), just send whatever URL you got and that one entry gets updated. "
    "The display name stays &ldquo;Graider&rdquo; everywhere regardless of the URL.", NOTE))

SimpleDocTemplate(
    str(OUT), pagesize=LETTER,
    leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    topMargin=0.8 * inch, bottomMargin=0.8 * inch,
    title="Graider Brand Setup Checklist", author="Graider",
).build(flow)
print(f"Wrote {OUT}")
