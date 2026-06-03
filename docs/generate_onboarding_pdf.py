#!/usr/bin/env python3
"""Generate the Graider District Onboarding Guide PDF.

Plain-English, CTO-facing walkthrough of how every role is onboarded and
exactly how every field on the /district configuration page is filled.

Usage:
    source venv/bin/activate
    python scripts/generate_onboarding_pdf.py
Output:
    docs/Graider-District-Onboarding-Guide.pdf

The content here is the source of truth for the printed guide. Edit the
SECTIONS / field tables below and re-run to regenerate.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PURPLE = colors.HexColor("#7c3aed")
PURPLE_DK = colors.HexColor("#5b21b6")
INK = colors.HexColor("#1f2937")
DIM = colors.HexColor("#5b6370")
LIGHT = colors.HexColor("#f3f0fb")
RULE = colors.HexColor("#e0e0e0")
GREEN = colors.HexColor("#15803d")
AMBER = colors.HexColor("#b45309")

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "Graider-District-Onboarding-Guide.pdf")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
ss = getSampleStyleSheet()


def style(name, **kw):
    base = kw.pop("parent", ss["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


S = {
    "h1": style("h1", fontName="Helvetica-Bold", fontSize=19, textColor=PURPLE_DK,
                spaceBefore=6, spaceAfter=10, leading=23),
    "h2": style("h2", fontName="Helvetica-Bold", fontSize=14, textColor=PURPLE_DK,
                spaceBefore=16, spaceAfter=6, leading=18),
    "h3": style("h3", fontName="Helvetica-Bold", fontSize=11.5, textColor=INK,
                spaceBefore=11, spaceAfter=3, leading=15),
    "body": style("body", fontName="Helvetica", fontSize=10, textColor=INK,
                  leading=15, spaceAfter=7, alignment=TA_LEFT),
    "bullet": style("bullet", fontName="Helvetica", fontSize=10, textColor=INK,
                    leading=14.5),
    "small": style("small", fontName="Helvetica", fontSize=8.5, textColor=DIM,
                   leading=12),
    "cell": style("cell", fontName="Helvetica", fontSize=8.8, textColor=INK,
                  leading=12),
    "cellb": style("cellb", fontName="Helvetica-Bold", fontSize=8.8, textColor=INK,
                   leading=12),
    "cellh": style("cellh", fontName="Helvetica-Bold", fontSize=9, textColor=colors.white,
                   leading=12),
    "callh": style("callh", fontName="Helvetica-Bold", fontSize=9.5, textColor=PURPLE_DK,
                   leading=13, spaceAfter=2),
    "call": style("call", fontName="Helvetica", fontSize=9.2, textColor=INK,
                  leading=13),
    "cover_t": style("cover_t", fontName="Helvetica-Bold", fontSize=34, textColor=PURPLE,
                     leading=38, alignment=TA_CENTER),
    "cover_s": style("cover_s", fontName="Helvetica", fontSize=14, textColor=DIM,
                     leading=20, alignment=TA_CENTER),
    "cover_m": style("cover_m", fontName="Helvetica", fontSize=10, textColor=DIM,
                     leading=15, alignment=TA_CENTER),
}


def P(text, s="body"):
    return Paragraph(text, S[s])


def bullets(items, s="bullet"):
    return ListFlowable(
        [ListItem(Paragraph(t, S[s]), leftIndent=10, value="•") for t in items],
        bulletType="bullet", bulletColor=PURPLE, leftIndent=12, spaceBefore=2, spaceAfter=8,
    )


def numbered(items, s="bullet"):
    return ListFlowable(
        [ListItem(Paragraph(t, S[s]), leftIndent=12) for t in items],
        bulletType="1", bulletColor=PURPLE_DK, leftIndent=16, spaceBefore=2, spaceAfter=8,
        bulletFontName="Helvetica-Bold",
    )


def rule():
    return HRFlowable(width="100%", thickness=0.7, color=RULE, spaceBefore=4, spaceAfter=10)


def callout(title, body, tone="info"):
    bar = {"info": PURPLE, "tip": GREEN, "warn": AMBER}[tone]
    bg = {"info": LIGHT, "tip": colors.HexColor("#eefbf2"),
          "warn": colors.HexColor("#fdf6ec")}[tone]
    inner = [Paragraph(title, S["callh"]), Paragraph(body, S["call"])]
    t = Table([[inner]], colWidths=[6.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def field_table(rows):
    """rows: list of (field, what_to_enter, where_to_find). First row is header."""
    data = [[Paragraph("Field", S["cellh"]),
             Paragraph("What to enter", S["cellh"]),
             Paragraph("Where to find it / notes", S["cellh"])]]
    for f, w, wh in rows:
        data.append([Paragraph(f, S["cellb"]), Paragraph(w, S["cell"]),
                     Paragraph(wh, S["cell"])])
    t = Table(data, colWidths=[1.35 * inch, 2.55 * inch, 2.8 * inch], repeatRows=1)
    sty = [
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            sty.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#faf9fe")))
    t.setStyle(TableStyle(sty))
    return t


# ---------------------------------------------------------------------------
# Document chrome (header / footer)
# ---------------------------------------------------------------------------
def on_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    if doc.page > 1:
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(PURPLE)
        canvas.drawString(0.9 * inch, h - 0.6 * inch, "Graider")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(DIM)
        canvas.drawRightString(w - 0.9 * inch, h - 0.6 * inch, "District Onboarding Guide")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.9 * inch, h - 0.72 * inch, w - 0.9 * inch, h - 0.72 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(DIM)
        canvas.drawCentredString(w / 2, 0.55 * inch, "Page %d" % doc.page)
        canvas.drawString(0.9 * inch, 0.55 * inch, "Confidential — for district staff")
    canvas.restoreState()


def build():
    doc = BaseDocTemplate(
        OUT, pagesize=letter,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.95 * inch, bottomMargin=0.8 * inch,
        title="Graider — District Onboarding Guide",
        author="Graider",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=on_page)])

    flow = []
    a = flow.append

    # ---- Cover ----
    a(Spacer(1, 1.7 * inch))
    a(P("Graider", "cover_t"))
    a(Spacer(1, 0.15 * inch))
    a(P("District Onboarding Guide", "cover_s"))
    a(Spacer(1, 0.1 * inch))
    a(P("How district admins, school admins, teachers, and students get set up — "
        "and exactly how to fill in every field on the configuration page.", "cover_m"))
    a(Spacer(1, 1.4 * inch))
    a(HRFlowable(width="40%", thickness=1, color=PURPLE, hAlign="CENTER"))
    a(Spacer(1, 0.3 * inch))
    a(P("Prepared for district technology leadership", "cover_m"))
    a(P("Setup time: about 30 minutes for a district admin", "cover_m"))
    a(PageBreak())

    # ---- 1. The big picture ----
    a(P("1. The big picture", "h1"))
    a(P("Graider is an AI grading and assessment assistant for teachers. Before "
        "teachers and students can sign in, one person at the district — the "
        "<b>district admin</b> — spends about half an hour on a single setup page "
        "to connect your student information system (SIS) and turn on the AI. "
        "After that, everyone else is onboarded automatically through the single "
        "sign-on (SSO) your district already uses.", "body"))

    a(P("The four roles", "h2"))
    roles = [
        ("District Admin", "Usually you or someone on the IT team. Connects the SIS, "
         "enters the AI keys, and decides who else gets admin access. Works on the "
         "<b>/district</b> page. This is the only role that touches configuration."),
        ("School Admin (Principal)", "A teacher or principal who can see school-wide "
         "results for their building. Gets access two ways: an invite code from the "
         "district admin, or by being named on the SSO admin list. They do <i>not</i> "
         "configure anything technical."),
        ("Teacher", "Signs in with your district SSO (Clever or ClassLink) or with a "
         "Graider email account. Their classes and students appear automatically from "
         "the roster. They create assignments and grade."),
        ("Student", "Signs in with district SSO, or joins a single assignment with a "
         "6-character class code — no account required for the quick-code path."),
    ]
    rt = [[Paragraph("<b>%s</b>" % r, S["cell"]), Paragraph(d, S["cell"])] for r, d in roles]
    tbl = Table(rt, colWidths=[1.5 * inch, 5.2 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LINEAFTER", (0, 0), (0, -1), 0.6, RULE),
    ]))
    a(tbl)
    a(Spacer(1, 0.12 * inch))

    a(P("The order things happen", "h2"))
    a(numbered([
        "<b>District admin sets up Graider</b> on the /district page (SIS + AI keys). "
        "~30 minutes, once.",
        "<b>Graider enables your SSO</b> (Clever or ClassLink) using the credentials "
        "you provide. This is a quick coordination step with the Graider team.",
        "<b>Teachers sign in</b> through your SSO portal. Their rosters sync "
        "automatically — no manual class building.",
        "<b>Students sign in</b> through the same SSO, or use a class code for a "
        "one-off assignment.",
        "<b>School admins are granted access</b> by the district admin whenever you "
        "want school-level reporting.",
    ]))
    a(callout("What the district provides vs. what Graider does",
              "You provide: SIS API credentials, your AI provider keys (or use Graider's), "
              "and your SSO app credentials. Graider does: the SSO wiring on our servers, "
              "hosting, security, and the grading engine. Nothing is installed on district "
              "hardware — Graider is a hosted web app at app.graider.live.", "info"))
    a(PageBreak())

    # ---- 2. District admin onboarding ----
    a(P("2. District admin onboarding", "h1"))
    a(P("The district admin is the first person to set up Graider. Everything happens "
        "at one URL.", "body"))

    a(P("Step 1 — Open the configuration page", "h3"))
    a(P("Go to <b>https://app.graider.live/district</b> in any browser. There is "
        "nothing to install.", "body"))

    a(P("Step 2 — Create the district admin password (first time only)", "h3"))
    a(P("The very first time anyone opens /district, Graider asks you to create a "
        "district admin password. This password protects the configuration page — "
        "it is separate from any teacher or SSO login.", "body"))
    a(field_table([
        ("Password", "A strong password, at least 8 characters. Store it in your IT "
         "password manager.", "You choose it. This is the key to the whole district "
         "configuration, so treat it like an admin credential."),
        ("Confirm Password", "Type the same password again.", "Must match exactly."),
    ]))
    a(callout("After setup, this screen becomes a login",
              "On every later visit, /district shows a single password box. Enter the "
              "password you created to reach the configuration. You can change it later "
              "from the “Change Password” control at the bottom of the page.", "tip"))

    a(P("Step 3 — Choose your SIS provider", "h3"))
    a(P("At the top of the page, under <b>SIS Provider</b>, pick the system that holds "
        "your rosters by selecting one of the two radio buttons: <b>Clever</b> or "
        "<b>OneRoster</b>. The fields below change to match your choice. (If your "
        "district uses ClassLink, see the note at the end of this section.)", "body"))
    a(PageBreak())

    a(P("Step 3a — Fill in the Clever fields", "h2"))
    a(P("Choose this if your district uses Clever for rostering and/or single sign-on. "
        "All values come from your Clever district dashboard "
        "(<b>schools.clever.com</b> → your Graider application).", "body"))
    a(field_table([
        ("Client ID", "Your Clever application&rsquo;s OAuth Client ID.",
         "Clever dashboard → Applications → Graider → <i>OAuth Credentials</i>."),
        ("Client Secret", "Your Clever application&rsquo;s OAuth Client Secret.",
         "Same screen as the Client ID. Keep it secret; it is write-only here and shows "
         "a &ldquo;Saved&rdquo; badge once stored."),
        ("Redirect URI", "Leave the pre-filled value: "
         "<font face='Courier'>https://app.graider.live/api/clever/callback</font>",
         "Must match the redirect URL registered in your Clever app exactly. Only change "
         "it if Graider tells you to."),
        ("District Token (optional)", "Your Clever Secure Sync district token, if you use "
         "Secure Sync.", "Clever dashboard → Secure Sync. Optional — leave blank "
         "if you are not using Secure Sync."),
    ]))

    a(P("Step 3b — Fill in the OneRoster fields", "h2"))
    a(P("Choose this if your SIS exposes a OneRoster 1.1 API (PowerSchool, Infinite "
        "Campus, Skyward, and many others). Values come from your SIS&rsquo;s OneRoster / "
        "API credentials screen.", "body"))
    a(field_table([
        ("Base URL", "The root of your OneRoster API, e.g. "
         "<font face='Courier'>https://sis.district.org/ims/oneroster/v1p1</font>",
         "Your SIS&rsquo;s OneRoster endpoint. Your SIS vendor or its API documentation "
         "provides this."),
        ("Client ID", "The OAuth 2.0 client ID issued by your SIS.",
         "SIS admin → API / OneRoster credentials. Often called &ldquo;consumer key.&rdquo;"),
        ("Client Secret", "The OAuth 2.0 client secret issued by your SIS.",
         "Same screen. Often called &ldquo;consumer secret.&rdquo; Stored write-only."),
        ("Token URL (optional)", "The OAuth token endpoint, if your SIS uses a "
         "non-standard one.", "Leave blank to let Graider auto-detect "
         "(<font face='Courier'>{Base URL}/token</font>). Fill only if your vendor "
         "specifies a different token URL."),
        ("School ID (optional)", "A single school&rsquo;s <i>sourcedId</i> to limit the "
         "roster to one building.", "Leave blank to sync the whole district. Use a "
         "school sourcedId from your SIS to scope a pilot."),
    ]))

    a(P("Step 3c — Test, then save", "h3"))
    a(bullets([
        "Click <b>Test Connection</b>. Graider contacts your SIS and confirms the "
        "credentials work. You&rsquo;ll see &ldquo;Connection successful&rdquo; or a clear error.",
        "Click <b>Save SIS Config</b>. A green <b>Saved</b> badge confirms it is stored.",
    ]))
    a(callout("Using ClassLink for SSO?",
              "ClassLink single sign-on is wired up on Graider&rsquo;s side using ClassLink "
              "app credentials you provide to the Graider team (it is not entered on this "
              "page). Roster data can still come from ClassLink&rsquo;s OneRoster API — "
              "enter those API credentials in the OneRoster fields above. Coordinate the "
              "ClassLink SSO tile with Graider support.", "info"))
    a(PageBreak())

    a(P("Step 4 — Enter the AI API keys", "h2"))
    a(P("Under <b>AI API Keys</b>, provide at least one AI provider key so Graider can "
        "grade. You can enter one, two, or all three. Teachers may optionally override "
        "these with their own keys in their personal Settings.", "body"))
    a(field_table([
        ("OpenAI API Key", "A key starting with <font face='Courier'>sk-</font>",
         "platform.openai.com → API keys. Powers GPT-based grading."),
        ("Anthropic API Key", "A key starting with <font face='Courier'>sk-ant-</font>",
         "console.anthropic.com → API keys. Powers Claude-based grading."),
        ("Gemini API Key", "A key starting with <font face='Courier'>AIza</font>",
         "Google AI Studio → API keys. Powers Gemini-based grading."),
    ]))
    a(bullets([
        "Each saved key shows a <b>Saved</b> badge. To keep an existing key, leave the "
        "box blank — typing replaces it.",
        "Click <b>Save Keys</b> when done.",
    ]))
    a(callout("Which key should we use?",
              "Any one is enough to start. Districts commonly provide an OpenAI or "
              "Anthropic key. If you&rsquo;d rather not manage AI billing, ask Graider about "
              "using Graider-managed keys instead — then you can leave all three blank.",
              "tip"))

    a(P("Step 5 — Decide who else gets admin access", "h2"))
    a(P("Two sections near the bottom of the page let you grant access to others. Use "
        "whichever fits how that person signs in.", "body"))

    a(P("Option A — School Admins (invite by code)", "h3"))
    a(P("Use this to make a principal or lead teacher a <b>school admin</b> who can see "
        "school-wide results. Graider generates a code they redeem inside the teacher "
        "app.", "body"))
    a(field_table([
        ("School Name", "The building this admin oversees, e.g. "
         "&ldquo;Lincoln Middle School.&rdquo;", "You type it. Appears on their dashboard."),
        ("Pre-assign Teachers (optional)", "Start typing a teacher&rsquo;s name to attach "
         "them to this school.", "Optional. Helps group teachers under the right building."),
    ]))
    a(P("Click to generate an <b>invite code</b>. Send that code to the principal; they "
        "enter it in the teacher app&rsquo;s <b>Admin</b> tab to claim access. Codes expire, "
        "so send them promptly. Existing admins appear in a table where you can "
        "<b>Revoke</b> access at any time.", "body"))

    a(P("Option B — SSO Admin Access (designate by email)", "h3"))
    a(P("Use this when admins sign in through SSO. You name their email in advance; the "
        "moment they sign in through Clever or ClassLink, they receive the admin level "
        "you chose. Graider never grants admin from the identity provider alone — the "
        "email must be on this list.", "body"))
    a(field_table([
        ("Email", "The exact email the person uses to sign in via SSO.",
         "Must match their SSO email. e.g. <font face='Courier'>principal@district.org</font>"),
        ("Access Level", "Pick <b>District Admin</b> (full configuration access) or "
         "<b>School Admin</b> (one building&rsquo;s reporting).", "Dropdown."),
        ("School", "The building name — shown only when Access Level is "
         "<b>School Admin</b>.", "Type the school this admin oversees."),
    ]))
    a(callout("District Admin vs. School Admin — what&rsquo;s the difference?",
              "A <b>District Admin</b> can open /district and change configuration, plus "
              "see district-wide analytics. A <b>School Admin</b> cannot change "
              "configuration — they get a read-only, school-scoped results dashboard "
              "inside the teacher app. Grant District Admin sparingly.", "warn"))

    a(P("Step 6 — Review the Configuration Summary", "h3"))
    a(P("The <b>Configuration Summary</b> at the bottom lists what is connected (SIS "
        "provider, which AI keys are set, admin counts) so you can confirm everything "
        "at a glance before you finish. Use <b>Change Password</b> here if you ever need "
        "to rotate the district admin password.", "body"))
    a(PageBreak())

    # ---- 3. School admin onboarding ----
    a(P("3. School admin (principal) onboarding", "h1"))
    a(P("School admins get a read-only, school-wide view of teacher activity and "
        "results. They never configure anything. There are two ways to onboard one — "
        "the district admin chooses based on how the person signs in.", "body"))
    a(P("Path 1 — Invite code", "h3"))
    a(numbered([
        "District admin generates an invite code in the <b>School Admins</b> section of "
        "/district (Step 5, Option A).",
        "Principal signs in to Graider as a normal teacher (SSO or email).",
        "Principal opens the <b>Admin</b> tab in the teacher app and enters the code.",
        "Access is granted immediately; the school dashboard appears.",
    ]))
    a(P("Path 2 — SSO designation", "h3"))
    a(numbered([
        "District admin adds the principal&rsquo;s email under <b>SSO Admin Access</b> with "
        "level <b>School Admin</b> and the school name (Step 5, Option B).",
        "Principal signs in through your district SSO.",
        "Graider matches their email to the designation and grants school admin access "
        "automatically — no code needed.",
    ]))
    a(callout("What a school admin sees",
              "School-wide totals (teachers, students, assessments, average score), a "
              "grade distribution, and a per-teacher activity list — all limited to "
              "their building. It is reporting only; they cannot change grades or "
              "settings.", "info"))

    # ---- 4. Teacher onboarding ----
    a(P("4. Teacher onboarding", "h1"))
    a(P("Teachers do not need any setup from IT beyond having a roster in your SIS and "
        "SSO turned on. They onboard themselves the first time they sign in.", "body"))
    a(P("How a teacher signs in", "h3"))
    a(bullets([
        "<b>District SSO (recommended):</b> The teacher clicks your Clever or ClassLink "
        "tile, or the SSO button on Graider&rsquo;s login screen. They are recognized as a "
        "teacher and land in their dashboard.",
        "<b>Email account:</b> Teachers can also sign up with an email and password "
        "directly, useful for pilots before SSO is live.",
    ]))
    a(P("What happens automatically", "h3"))
    a(bullets([
        "Their <b>classes and students sync from the roster</b> — no manual class "
        "building.",
        "Accommodations (IEP / 504 / ELL) flagged in your SIS can be applied so grading "
        "respects them.",
        "They can immediately create assignments, publish them, and grade with AI.",
    ]))
    a(callout("OneRoster teacher matching",
              "When rosters come from OneRoster, a teacher may be asked once to confirm "
              "their identity (their OneRoster sourcedId) so Graider attaches the right "
              "classes. This is a one-time, self-service step.", "tip"))
    a(PageBreak())

    # ---- 5. Student onboarding ----
    a(P("5. Student onboarding", "h1"))
    a(P("Students have the lightest path. Choose whichever fits the activity — both "
        "can coexist.", "body"))
    a(P("Path 1 — Single sign-on (recommended for class work)", "h3"))
    a(bullets([
        "The student clicks your Clever or ClassLink tile (or the SSO button on the "
        "student login screen).",
        "They land in their student portal at <b>/student</b> with their assigned work "
        "already listed — no account creation, no passwords to manage.",
        "Submissions are tied to their roster identity, so results flow to the right "
        "teacher and school.",
    ]))
    a(P("Path 2 — Class code (recommended for quick or one-off assignments)", "h3"))
    a(bullets([
        "The teacher publishes an assignment and shares a <b>6-character class code</b>.",
        "The student goes to <b>app.graider.live/join/CODE</b> (or types the code), "
        "completes the assignment, and submits — no account required.",
        "Great for substitutes, make-up work, or districts not yet on SSO.",
    ]))
    a(P("Path 3 — Email + class code (authenticated, no SSO)", "h3"))
    a(P("Students can also log in with their email and a class code when a teacher wants "
        "authenticated submissions but the district isn&rsquo;t using SSO. This keeps work "
        "tied to a named student without requiring the SIS roster.", "body"))

    # ---- 6. Data, privacy, and offboarding ----
    a(P("6. Data privacy & offboarding", "h1"))
    a(bullets([
        "<b>What syncs:</b> names, email/identifiers, class enrollment, and — if "
        "present — accommodation flags. Graider pulls only what it needs to roster "
        "and grade.",
        "<b>Where it lives:</b> Graider is hosted (app.graider.live). No district "
        "servers or installs are involved.",
        "<b>Credentials are write-only:</b> once saved, secrets and AI keys are never "
        "displayed back — the page only shows a &ldquo;Saved&rdquo; badge.",
        "<b>FERPA right-to-delete:</b> the district admin can delete all SIS-sourced data "
        "(Clever, ClassLink, or OneRoster) from the relevant integration controls. "
        "Removal is district-initiated and auditable.",
        "<b>Revoking access:</b> revoke a school admin from the admins table, or remove "
        "an SSO designation, at any time. Disabling a user in your SIS/SSO stops their "
        "access at the next sign-in.",
    ]))
    a(callout("One-page summary for the CTO",
              "Connect your SIS (Clever or OneRoster) on /district, add one AI key, and "
              "decide who gets admin. Coordinate the SSO tile with Graider. After that, "
              "teachers and students sign in with the SSO you already have, rosters sync "
              "themselves, and you can pull school- or district-wide reporting whenever "
              "you want. Total district-admin effort: about 30 minutes.", "tip"))

    a(Spacer(1, 0.2 * inch))
    a(rule())
    a(P("Questions during setup? Contact Graider support. This guide reflects the "
        "/district configuration page and onboarding flows as currently shipped.", "small"))

    doc.build(flow)
    return OUT


if __name__ == "__main__":
    path = build()
    print("Wrote", path)
