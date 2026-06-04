import React, { useState, useEffect, useRef, useMemo, useCallback, Suspense, Fragment } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  ScatterChart,
  Scatter,
  Cell,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import Icon from "./components/Icon";
import StandardCard from "./components/StandardCard";
import PasswordResetScreen from "./components/PasswordResetScreen";
import ImportEventsModal from "./components/ImportEventsModal";
import CurveModal from "./components/CurveModal";
import HolidayModal from "./components/HolidayModal";
import PlatformExportMenu from "./components/PlatformExportMenu";
import ActivityLog from "./components/ActivityLog";
import { AssignmentPlayer } from "./components";
import QuestionEditToolbar from "./components/QuestionEditToolbar";
import QuestionEditOverlay from "./components/QuestionEditOverlay";
import StudentPortal from "./components/StudentPortal";
import StudentApp from "./components/StudentApp";
import * as api from "./services/api";
import { getAuthHeaders } from "./services/api";
import LoginScreen from "./components/LoginScreen";
import AssistantChat from "./components/AssistantChat";
import AutomationBuilder from "./components/AutomationBuilder";
import BehaviorPanel from "./components/BehaviorPanel";
import DistrictSetup from "./components/DistrictSetup";
import MatchingCards from "./components/MatchingCards";
import MindMapView from "./components/MindMapView";
import FlashcardView from "./components/FlashcardView";
import { initPostHog, identifyUser, resetUser, track as phTrack } from "./services/posthog";

// Inline CSV table preview — fetches CSV from URL and renders as HTML table
import DataTablePreview from "./components/DataTablePreview";
import OnboardingWizard from "./components/OnboardingWizard";
import TutorialOverlay, { TUTORIAL_STEPS } from "./components/TutorialOverlay";
import HelpTab from "./components/HelpTab";
import { AuthLoadingScreen, ApprovalCheckingScreen, NotApprovedScreen } from "./components/AuthScreens";
import { RUBRIC_PRESETS, getPresetForStateSubject } from "./data/rubricPresets";
import { checkRequirementsMismatch } from "./utils/standardsMismatch";
import { normalizeText, buildTextToHtmlMap, htmlToPlainText, highlightTextInHtml, removeHighlightFromHtml, textToRichHtml, removeAllHighlightsFromHtml } from "./utils/htmlHighlight";
import { getSubjectSectionDefaults, distributeDOK, distributePoints } from "./utils/assessmentDistribution";
import { getMarkerText, getEndMarker, getMarkerPoints, getMarkerType, calculateTotalPoints } from "./utils/markerHelpers";
import BuilderTab from "./tabs/BuilderTab";
import GradeTab from "./tabs/GradeTab";
import PlannerTab from "./tabs/PlannerTab";
import ResultsTab from "./tabs/ResultsTab";
import SettingsTab from "./tabs/SettingsTab";
import EmailPreviewModal from "./components/EmailPreviewModal";
import DocumentEditorModal from "./components/DocumentEditorModal";
import ReviewModal from "./components/ReviewModal";
import Sidebar from "./components/Sidebar";
import { useTheme } from "./hooks/useTheme";
import { useToasts } from "./hooks/useToasts";
import { useAuthSession } from "./hooks/useAuthSession";
import { useBillingRedirect } from "./hooks/useBillingRedirect";
import { useAssignmentAutoSave } from "./hooks/useAssignmentAutoSave";
import { useGradingStatusPoll } from "./hooks/useGradingStatusPoll";
import { useGradingToast } from "./hooks/useGradingToast";
import { useEditedResultsAutoSave } from "./hooks/useEditedResultsAutoSave";
import { useAssessmentAuthoring } from "./hooks/useAssessmentAuthoring";
import { useAssignmentBuilderActions } from "./hooks/useAssignmentBuilderActions";
import { useTeacherDashboardActions } from "./hooks/useTeacherDashboardActions";
import { useResultsCurveAndEmail } from "./hooks/useResultsCurveAndEmail";
import { useMarkerEditing } from "./hooks/useMarkerEditing";
import { useDocImport } from "./hooks/useDocImport";
import { useSavedAssessmentActions } from "./hooks/useSavedAssessmentActions";
import { useSubscription } from "./hooks/useSubscription";
import { useFocusPolling } from "./hooks/useFocusPolling";
import { useOutlookSendPolling } from "./hooks/useOutlookSendPolling";
import { useSettingsAutoSave } from "./hooks/useSettingsAutoSave";
import { usePortalSubmissions } from "./hooks/usePortalSubmissions";
const AnalyticsTab = React.lazy(() => import("./tabs/AnalyticsTab"));
var AdminTab = React.lazy(function() { return import("./tabs/AdminTab"); });

// Tab configuration
const TABS = [
  { id: "grade", label: "Grade", icon: "GraduationCap" },
  { id: "results", label: "Results", icon: "FileText" },
  { id: "builder", label: "Grading Setup", icon: "FileEdit" },
  { id: "analytics", label: "Analytics", icon: "BarChart3" },
  { id: "planner", label: "Planner", icon: "BookOpen" },
  { id: "automations", label: "Script Builder", icon: "Cpu" },
  { id: "assistant", label: "Assistant", icon: "Sparkles" },
  { id: "settings", label: "Settings", icon: "Settings" },
  { id: "help", label: "Help", icon: "HelpCircle" },
];

// Marker libraries by subject
const markerLibrary = {
  "Social Studies": [
    "Explain:",
    "Describe the significance of:",
    "Compare and contrast:",
    "What were the causes of:",
    "What were the effects of:",
    "Analyze:",
    "In your own words:",
    "Why do you think:",
  ],
  "English/ELA": [
    "Write your response:",
    "Your thesis statement:",
    "Analyze the text:",
    "Provide evidence:",
    "Explain the theme:",
    "Character analysis:",
    "Authors purpose:",
  ],
  Math: [
    "Show your work:",
    "Solve:",
    "Calculate:",
    "Prove:",
    "Find the value of:",
    "Graph:",
    "Simplify:",
    "Word Problem:",
  ],
  Science: [
    "Hypothesis:",
    "Data/Observations:",
    "Conclusion:",
    "Procedure:",
    "Variables:",
    "Analysis:",
    "Explain the results:",
  ],
  "US History": [
    "Explain:",
    "Describe:",
    "What was the impact of:",
    "Primary source analysis:",
    "Timeline:",
    "Cause and effect:",
    "Historical significance:",
  ],
  "World History": [
    "Explain:",
    "Describe:",
    "What was the impact of:",
    "Primary source analysis:",
    "Timeline:",
    "Cause and effect:",
    "Historical significance:",
    "Compare civilizations:",
  ],
  Spanish: [
    "Traduce:",
    "Conjugación:",
    "Respuesta:",
    "Escribe en español:",
    "Completa la oración:",
    "Vocabulario:",
    "Lectura:",
    "Conversación:",
  ],
  French: [
    "Traduisez:",
    "Conjugaison:",
    "Répondez:",
    "Écrivez en français:",
    "Complétez la phrase:",
    "Vocabulaire:",
    "Lecture:",
    "Conversation:",
  ],
  "World Languages": [
    "Translate:",
    "Conjugation:",
    "Response:",
    "Write in target language:",
    "Complete the sentence:",
    "Vocabulary:",
    "Reading comprehension:",
    "Conversation:",
  ],
  Other: [
    "Answer:",
    "Explain:",
    "Describe:",
    "Your response:",
    "Short answer:",
    "Essay:",
  ],
};

// Assignment templates with section-based point values
const ASSIGNMENT_TEMPLATES = {
  "Cornell Notes": {
    markers: [
      { start: "Questions/Terms", points: 40, type: "fill-blank", description: "Fill-in-the-blank and short answers" },
      { start: "Summary (Bottom Section)", points: 20, type: "written", description: "3-4 sentence summary" },
      { start: "Vocabulary", points: 25, type: "vocabulary", description: "Vocabulary definitions" },
    ],
    effortPoints: 15,
    description: "Standard Cornell Notes format with summary section"
  },
  "Worksheet - Fill-in-Blank Heavy": {
    markers: [
      { start: "Fill-in-the-blank", points: 50, type: "fill-blank", description: "Fill-in-the-blank questions" },
      { start: "Short Answer", points: 35, type: "written", description: "Written response questions" },
    ],
    effortPoints: 15,
    description: "Worksheet with mostly fill-in-the-blank"
  },
  "Worksheet - Written Heavy": {
    markers: [
      { start: "Questions", points: 30, type: "fill-blank", description: "Fill-in-the-blank and factual questions" },
      { start: "Written Response", points: 40, type: "written", description: "Paragraph responses" },
      { start: "Reflection", points: 15, type: "written", description: "Personal reflection" },
    ],
    effortPoints: 15,
    description: "Worksheet emphasizing written responses"
  },
  "Essay": {
    markers: [
      { start: "Thesis/Introduction", points: 20, type: "written", description: "Opening paragraph with thesis" },
      { start: "Body Paragraphs", points: 45, type: "written", description: "Supporting arguments" },
      { start: "Conclusion", points: 20, type: "written", description: "Summary and closing" },
    ],
    effortPoints: 15,
    description: "Standard essay format"
  },
  "Custom": {
    markers: [
      { start: "Content", points: 85, type: "written", description: "Main assignment content" },
    ],
    effortPoints: 15,
    description: "Define your own sections and point values"
  }
};


function App() {
  // Check if this is the district admin route
  if (window.location.pathname.startsWith("/district")) {
    return React.createElement(DistrictSetup, null);
  }
  // Check if this is the student portal route
  if (window.location.pathname.startsWith("/student")) {
    return <StudentApp />;
  }
  if (window.location.pathname.startsWith("/join")) {
    return <StudentPortal />;
  }

  // isLocalhost stays in App (used in ~10 places); passed into useAuthSession.
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  // Auth lifecycle extracted to useAuthSession (App.jsx decomposition slice 3):
  // sticky user + Supabase onAuthStateChange, Clever/ClassLink redirect bootstrap,
  // approval gate, PostHog identify, handleLogout. Moved verbatim as a contiguous
  // block (hook order preserved).
  const {
    user,
    _setUser,
    authLoading,
    userApproved,
    showPasswordReset,
    setShowPasswordReset,
    handleLogout,
  } = useAuthSession(isLocalhost);

  // Theme state + persistence (extracted to useTheme; App.jsx decomposition slice 1)
  const { theme, toggleTheme } = useTheme();

  // Per-model cost estimates ($ per assignment)
  const MODEL_COST_PER_ASSIGNMENT = {
    "gpt-4o-mini": 0.001, "gpt-4o": 0.015,
    "claude-haiku": 0.002, "claude-sonnet": 0.02,
    "gemini-flash": 0.0005, "gemini-pro": 0.008
  };

  // Core state
  const [config, setConfig] = useState({
    assignments_folder: "",
    output_folder: "",
    roster_file: "",
    grading_period: "Q1",
    grade_level: "7",
    subject: "US History",
    state: "FL",
    teacher_name: "",
    teacher_email: "",
    email_signature: "",
    school_name: "",
    sis_type: "csv",  // "focus", "powerschool", "canvas", "csv"
    showToastNotifications: true,
    ai_model: "gpt-4o-mini",
    ensemble_enabled: false,
    ensemble_models: [], // e.g., ['gpt-4o-mini', 'claude-haiku', 'gemini-flash']
    extraction_mode: "structured", // "structured" = parsing logic, "ai" = let AI identify responses
    availableTools: [], // Tools teacher has access to for lesson planning
    trustedStudents: [], // Students exempt from AI/copy detection flags (by student_id)
    cost_limit_per_session: 0,   // Max $ per grading session (0 = no limit)
    cost_limit_monthly: 0,       // Advisory monthly budget (0 = no limit)
    cost_warning_pct: 80,        // Warn at this % of session limit
  });

  // API Keys state (separate from config for security)
  const [apiKeys, setApiKeys] = useState({
    openai: "",
    anthropic: "",
    gemini: "",
    openaiConfigured: false,
    anthropicConfigured: false,
    geminiConfigured: false,
    openaiIsOwn: false,
    anthropicIsOwn: false,
    geminiIsOwn: false,
  });

  // Focus Export state
  const [focusExportModal, setFocusExportModal] = useState(false);
  const [focusExportLoading, setFocusExportLoading] = useState(false);
  const [focusIncludeLetterGrade, setFocusIncludeLetterGrade] = useState(false);
  // Approval gate — teacher must approve grades before export
  const [gradesApproved, setGradesApproved] = useState(false);

  // VPortal credentials state
  const [vportalEmail, setVportalEmail] = useState("");
  const [vportalConfigured, setVportalConfigured] = useState(false);
  const [pendingConfirmations, setPendingConfirmations] = useState(0);
  const [pendingConfirmationStudents, setPendingConfirmationStudents] = useState([]);
  const [confirmationStudentFilter, setConfirmationStudentFilter] = useState("");
  const pendingConfirmationIds = useRef([]);
  const pendingConfirmationFilenames = useRef([]);

  // Available EdTech tools that can be selected
  const EDTECH_TOOLS = [
    // Microsoft & Google
    {
      id: "microsoft_365",
      name: "Microsoft 365",
      category: "All",
      description: "Word, Excel, PowerPoint",
    },
    {
      id: "microsoft_teams",
      name: "Microsoft Teams",
      category: "All",
      description: "Collaboration & meetings",
    },
    {
      id: "google_classroom",
      name: "Google Classroom",
      category: "All",
      description: "Assignment management",
    },
    {
      id: "google_slides",
      name: "Google Slides",
      category: "All",
      description: "Presentations",
    },
    {
      id: "google_docs",
      name: "Google Docs",
      category: "All",
      description: "Collaborative writing",
    },
    // LMS & Interactive
    {
      id: "canvas",
      name: "Canvas",
      category: "All",
      description: "Learning management system",
    },
    {
      id: "nearpod",
      name: "Nearpod",
      category: "All",
      description: "Interactive lessons",
    },
    {
      id: "edpuzzle",
      name: "Edpuzzle",
      category: "All",
      description: "Interactive video lessons",
    },
    {
      id: "pear_deck",
      name: "Pear Deck",
      category: "All",
      description: "Interactive slides",
    },
    {
      id: "padlet",
      name: "Padlet",
      category: "All",
      description: "Collaborative boards",
    },
    {
      id: "flipgrid",
      name: "Flip (Flipgrid)",
      category: "All",
      description: "Video discussions",
    },
    // Design & Media
    {
      id: "canva",
      name: "Canva",
      category: "All",
      description: "Design & infographics",
    },
    {
      id: "adobe_express",
      name: "Adobe Express",
      category: "All",
      description: "Creative design tool",
    },
    // Math
    {
      id: "ixl",
      name: "IXL",
      category: "Math/ELA",
      description: "Adaptive practice",
    },
    {
      id: "desmos",
      name: "Desmos",
      category: "Math",
      description: "Graphing calculator & activities",
    },
    {
      id: "geogebra",
      name: "GeoGebra",
      category: "Math",
      description: "Dynamic math software",
    },
    {
      id: "delta_math",
      name: "DeltaMath",
      category: "Math",
      description: "Math practice & videos",
    },
    {
      id: "fl_math_4_all",
      name: "FL Math 4 All",
      category: "Math",
      description: "Florida math resources",
    },
    {
      id: "prodigy",
      name: "Prodigy",
      category: "Math",
      description: "Math game",
    },
    {
      id: "zearn",
      name: "Zearn",
      category: "Math",
      description: "Math curriculum",
    },
    // ELA & Reading
    {
      id: "newsela",
      name: "Newsela",
      category: "ELA/SS",
      description: "Leveled articles",
    },
    {
      id: "commonlit",
      name: "CommonLit",
      category: "ELA",
      description: "Reading passages",
    },
    // Science
    {
      id: "phet",
      name: "PhET Simulations",
      category: "Science/Math",
      description: "Interactive simulations",
    },
    // Social Studies
    {
      id: "dbq_online",
      name: "DBQ Online",
      category: "SS/ELA",
      description: "Document-based questions",
    },
    {
      id: "cpalms",
      name: "CPALMS",
      category: "All",
      description: "Florida standards & resources",
    },
    // General Learning
    {
      id: "brainpop",
      name: "BrainPOP",
      category: "All",
      description: "Animated educational videos",
    },
    {
      id: "edgenuity",
      name: "Edgenuity",
      category: "All",
      description: "Online curriculum",
    },
    {
      id: "everfi",
      name: "EVERFI",
      category: "Life Skills",
      description: "Financial literacy & digital citizenship",
    },
    {
      id: "progress_learning",
      name: "Progress Learning",
      category: "All",
      description: "Standards-based practice",
    },
    {
      id: "hour_of_code",
      name: "Hour of Code",
      category: "CS",
      description: "Coding activities",
    },
    // Quiz & Games
    {
      id: "kahoot",
      name: "Kahoot",
      category: "All",
      description: "Game-based quizzes",
    },
    {
      id: "quizlet",
      name: "Quizlet",
      category: "All",
      description: "Flashcards & study sets",
    },
    {
      id: "blooket",
      name: "Blooket",
      category: "All",
      description: "Game-based review",
    },
    {
      id: "gimkit",
      name: "Gimkit",
      category: "All",
      description: "Live learning games",
    },
    // Video
    {
      id: "khan_academy",
      name: "Khan Academy",
      category: "All",
      description: "Video lessons & practice",
    },
    {
      id: "youtube",
      name: "YouTube",
      category: "All",
      description: "Educational videos",
    },
  ];


  const [status, setStatus] = useState({
    is_running: false,
    progress: 0,
    total: 0,
    current_file: "",
    log: [],
    results: [],
    complete: false,
    error: null,
  });

  // PR 4 of the Grade tab extraction sprint deleted the dead portal-era file-selection
  // branch: availableFiles, selectedFiles, filesLoading, loadAvailableFiles (no-op),
  // the preload effect on gradeFilterStudent, the matching-files UI in the Grade tab,
  // and the helpers fileMatchesPeriodStudent + stripNamePunctuation. PR 3 already
  // moved selectedPeriod, periodStudents, gradeFilterAssignment, individualUpload,
  // gradeAssignment, and the related handlers into tabs/GradeTab.jsx. PR 4 also moved
  // gradeFilterStudent into GradeTab as pure local UI state.

  const [activeTab, _setActiveTab] = useState("grade");
  const setActiveTab = useCallback((tab) => {
    _setActiveTab(tab);
    if (!isLocalhost) phTrack('tab_switched', { tab });
  }, []);
  var [isAdmin, setIsAdmin] = useState(false);
  var [adminSchool, setAdminSchool] = useState('');
  const [showOnboardingWizard, setShowOnboardingWizard] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [tutorialStep, setTutorialStep] = useState(0);
  const [settingsTab, setSettingsTab] = useState("general"); // general, grading, classroom, integration, privacy, billing
  const { subscription, setSubscription, subscriptionLoading, setSubscriptionLoading } = useSubscription(settingsTab);
  // Resizable column widths for Results table (in px, initialized on first render)
  const [colWidths, setColWidths] = useState(null);
  const tableRef = useRef(null);
  const resizingCol = useRef(null);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(0);

  const defaultColPercents = [13, 14, 11, 6, 10, 6, 13, 10, 17];

  function initColWidths() {
    if (colWidths || !tableRef.current) return;
    const tableW = tableRef.current.offsetWidth;
    setColWidths(defaultColPercents.map(p => Math.round(tableW * p / 100)));
  }

  function handleResizeStart(e, colIndex) {
    e.preventDefault();
    resizingCol.current = colIndex;
    resizeStartX.current = e.clientX;
    resizeStartW.current = colWidths[colIndex];

    function onMouseMove(ev) {
      const diff = ev.clientX - resizeStartX.current;
      setColWidths(prev => {
        const next = [...prev];
        const newW = Math.max(40, resizeStartW.current + diff);
        next[resizingCol.current] = newW;
        return next;
      });
    }

    function onMouseUp() {
      resizingCol.current = null;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  const [assessmentResults, setAssessmentResults] = useState([]);
  const [resultsPeriodFilter, setResultsPeriodFilter] = useState(""); // Filter results by class period
  // Grade-specific state (skipVerified, excludeGradedStudents, excludeApprovedStudents,
  // showActivityLog) moved into tabs/GradeTab.jsx in PR 2 of the Grade tab extraction sprint.
  const [globalAINotes, setGlobalAINotes] = useState("");

  // Check admin status
  useEffect(function() {
    if (!userApproved) return;
    api.getAdminStatus().then(function(data) {
      setIsAdmin(data.is_admin || false);
      setAdminSchool(data.school || '');
    }).catch(function() {});
  }, [userApproved]);

  const { portalSubmissions } = usePortalSubmissions({ user, showTutorial, userApproved, setPendingConfirmations });

  // Fetch assessment results for Results tab
  useEffect(function() {
    if (!user || showTutorial || userApproved !== true) return;
    var loadAssessmentResults = async function() {
      try {
        var data = await api.getAggregatedAssessmentResults();
        if (data.assessments) setAssessmentResults(data.assessments);
      } catch (e) {}
    };
    loadAssessmentResults();
    var interval = setInterval(loadAssessmentResults, 30000);
    return function() { clearInterval(interval); };
  }, [user, showTutorial, userApproved]);

  // Toast notifications (state + add/remove handlers extracted to useToasts; decomp
  // slice 2). The status.results-keyed toast-spawn effect and its lastResultCount ref
  // stay in App below — that effect is coupled to grading `status` and moving it would
  // reorder a useEffect across ~40 hooks. setToasts is returned for the live-toast
  // mutation in the grading-status block.
  const { toasts, setToasts, addToast, removeToast } = useToasts();
  const lastResultCount = useRef(0);

  const {
    focusCommsStatus, setFocusCommsStatus, focusCommsPolling, setFocusCommsPolling,
    focusCommentsStatus, setFocusCommentsStatus, focusCommentsPolling, setFocusCommentsPolling,
  } = useFocusPolling(addToast);

  // Sidebar state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Builder state
  const [assignment, setAssignment] = useState({
    title: "",
    subject: "Social Studies",
    totalPoints: 100,
    instructions: "",
    questions: [],
    customMarkers: [],           // Now stores objects with points: { start: "Summary:", points: 20, type: "written" }
    excludeMarkers: [], // Sections to NOT grade (e.g., "Notes Section")
    gradingNotes: "",
    responseSections: [],
    aliases: [], // Previous names for matching renamed assignments
    completionOnly: false, // If true, track submission but don't AI grade
    rubricType: "standard", // standard, fill-in-blank, essay, cornell-notes, completion-only, custom
    customRubric: null, // Custom rubric categories if rubricType is "custom"
    useSectionPoints: false,     // Toggle for section-based point system
    sectionTemplate: "Custom",   // Track which template is applied
    effortPoints: 15,            // Points for effort/engagement category
    dueDate: "",                 // ISO datetime string e.g. "2026-03-15T23:59"
    latePenalty: {
      enabled: false,
      type: "points_per_day",    // "points_per_day" | "percent_per_day" | "tiered"
      amount: 10,
      tiers: [
        { daysLate: 1, penalty: 10 },
        { daysLate: 3, penalty: 25 },
        { daysLate: 7, penalty: 50 },
      ],
      maxPenalty: 50,
      gracePeriodHours: 0,
    },
  });
  const [savedAssignments, setSavedAssignments] = useState([]);
  const [savedAssignmentData, setSavedAssignmentData] = useState({}); // Map of name -> {aliases: [], title: ""}
  // gradingModesExpanded moved into tabs/GradeTab.jsx in PR 2 of the Grade tab extraction sprint.
  const [modelAnswersLoading, setModelAnswersLoading] = useState(false);
  const [loadedAssignmentName, setLoadedAssignmentName] = useState("");
  const [isLoadingAssignment, setIsLoadingAssignment] = useState(false); // Prevent auto-save during load
  const skipAutoSaveRef = useRef(false); // Skip one auto-save cycle after loading from disk
  // gradeAssignment moved into tabs/GradeTab.jsx in PR 3.
  // gradeImportedDoc was DEAD state (set but never read) — DELETED in PR 4.
  const [importedDoc, setImportedDoc] = useState({
    text: "",
    html: "",
    filename: "",
    loading: false,
  });
  const [docEditorModal, setDocEditorModal] = useState({
    show: false,
    editedHtml: "",
    viewMode: "formatted",
  });

  // Highlighter mode: "start" (green), "end" (red), or "exclude" (orange)
  const [highlighterMode, setHighlighterMode] = useState("start");

  // Highlight colors
  const HIGHLIGHT_COLORS = {
    start: { bg: "rgba(34, 197, 94, 0.4)", border: "#22c55e", label: "Start" },
    end: { bg: "rgba(239, 68, 68, 0.4)", border: "#ef4444", label: "End" },
    exclude: { bg: "rgba(251, 146, 60, 0.4)", border: "#fb923c", label: "Exclude" },
  };

  // Results state
  const [editedResults, setEditedResults] = useState([]);
  const [reviewModal, setReviewModal] = useState({ show: false, index: -1 });
  const [reviewModalTab, setReviewModalTab] = useState("detected"); // "detected" or "raw"
  const [reviewModalRightTab, setReviewModalRightTab] = useState("edit"); // "edit" or "email"
  const [showAIReasoning, setShowAIReasoning] = useState(false);
  const [emailPreview, setEmailPreview] = useState({ show: false, emails: [] });
  const [emailStatus, setEmailStatus] = useState({
    sending: false,
    sent: 0,
    failed: 0,
    message: "",
  });
  const [emailApprovals, setEmailApprovals] = useState({}); // { index: 'approved' | 'rejected' | 'pending' }
  const [sentEmails, setSentEmails] = useState({}); // { index: true } - tracks which emails have been sent
  const [autoApproveEmails, setAutoApproveEmails] = useState(false);
  const [editedEmails, setEditedEmails] = useState({}); // { index: { subject, body } }
  const [curveModal, setCurveModal] = useState({ show: false, curveType: "add", curveValue: 5 }); // Curve modal state

  // Planner state
  const [standards, setStandards] = useState([]);
  const [selectedStandards, setSelectedStandards] = useState([]);
  // expandedStandards moved into PlannerTab in PR 6a of the Planner extraction sprint.
  const standardsScrollRef = useRef(null);
  const assessmentStandardsScrollRef = useRef(null);
  const [lessonPlan, setLessonPlan] = useState(null);
  // lessonVariations + brainstormIdeas + selectedIdea + plannerLoading +
  // brainstormLoading + assignmentQuestionCounts moved into PlannerTab
  // in PR 8d (lesson-gen big cluster). assignmentLoading + assignmentType +
  // generateAssignmentFromLessonHandler were dead code (never wired to UI)
  // and were deleted in the same PR.
  const [generatedAssignment, setGeneratedAssignment] = useState(null);
  // assignmentSectionsOpen moved into PlannerTab in PR 6a.
  // previewShowAnswers moved into PlannerTab in PR 6a.
  // previewResults moved into PlannerTab in PR 8c (preview cluster).

  // Reference document upload state
  const [uploadedDocs, setUploadedDocs] = useState([]);
  // docUploading moved into PlannerTab in PR 8b (doc upload cluster).
  const [contentOnly, setContentOnly] = useState(false);
  // matchingInProgress + matchResults moved into PlannerTab in PR 8a
  // (matching cluster).

  // Study Guide state
  // studyGuide + studyGuideGenerating + studyGuideInstructions moved into
  // PlannerTab in PR 6a of the Planner extraction sprint.
  // Flashcard state
  // flashcards + flashcardsGenerating + flashcardInstructions + flashcardCount
  // moved into PlannerTab in PR 6a of the Planner extraction sprint.
  // Slide Deck state
  // slideDeck + 8 slide* states moved into PlannerTab in PR 6a of the
  // Planner extraction sprint.

  // shareWithClass + executeShareWithClasses moved into PlannerTab in
  // PR 7d (share cluster) of the Planner extraction sprint.

  // Reading-level (RL) tools state moved into PlannerTab in PR 4 of the
  // Planner extraction sprint. Per plan #190 Task 4 — isolated tools-mode
  // workflow with no cross-cutting consumers.


  // Question editing state
  // Question-editing slice (editMode, selectedQuestions, editingQuestion,
  // regeneratingQuestions, sectionsDropdownOpen) moved into PlannerTab in
  // PR 5 of the Planner extraction sprint. Per plan #190 Task 5 — the
  // 6 question-editing helpers (toggleQuestionSelect, selectAllQuestions,
  // saveEditedQuestion, deleteSelectedQuestions, regenerateSelectedQuestions,
  // regenerateOneQuestion) moved with them. getActiveAssignment and
  // setActiveAssignment stay in App because the publish flow at
  // App.jsx:3681 + 3757 still calls them; they get passed as props to
  // PlannerTab and the moved helpers consume them via closure.

  // Preview-results reset useEffect moved into PlannerTab in PR 8c
  // (preview cluster) alongside the previewResults state itself.

  // Saved lessons for assessment generation
  const [savedLessons, setSavedLessons] = useState({ units: {}, lessons: [] });
  // savedUnits is a redundant derivation of Object.keys(savedLessons.units)
  // — replaced by inline derivation in PlannerTab in PR 6b. The two App-
  // level setSavedUnits calls (initial fetch + fetchSavedLessons handler)
  // were already calling setSavedLessons on the same lines, so removal is
  // a pure cleanup.
  // showSaveLesson + saveLessonUnit + newUnitName + the Save Lesson modal
  // block (formerly App.jsx:7853-7956) all moved into PlannerTab in PR 6b.
  const [selectedSources, setSelectedSources] = useState([]); // [{type, unit, filename, content}]

  const [unitConfig, setUnitConfig] = useState({
    title: "",
    duration: 1,
    periodLength: 50,
    type: "Lesson Plan",
    format: "Word",
    requirements: "",
    totalQuestions: 10,
    questionsPerSection: 0,
  });

  // Assessment generator state
  const [assessmentConfig, setAssessmentConfig] = useState({
    type: "quiz",
    title: "",
    targetPeriod: "", // For differentiation based on Global AI Instructions
    totalQuestions: 20,
    totalPoints: 30,
    // Section categories — controls which "Parts" the AI generates
    // FL FAST-aligned defaults: MC, short answer, math computation, geometry, graphing, data analysis ON
    // Vocabulary and extended writing OFF by default
    sectionCategories: {
      multiple_choice: 6,         // Part: Multiple Choice
      short_answer: 4,            // Part: Short Answer / Gridded Response
      math_computation: 3,        // Part: Math Computation (equations, solve for x)
      geometry_visual: 2,         // Part: Geometry & Measurement (interactive shapes, protractor, transformations)
      graphing: 2,                // Part: Graphing & Coordinate Plane (number lines, function graphs)
      data_analysis: 2,           // Part: Data Analysis (tables, box plots, dot plots, stem-and-leaf)
      extended_writing: 0,        // Part: Extended Writing / Essay
      vocabulary: 0,              // Part: Vocabulary / Matching
      true_false: 0,              // Part: True/False
      florida_fast: 0,            // Part: FL FAST Item Types (multiselect, multi-part, grid match, inline dropdown)
    },
    questionTypes: {
      multiple_choice: 10,
      short_answer: 4,
      extended_response: 0,
      true_false: 0,
      matching: 0,
      math_equation: 3,
      data_table: 3,
    },
    pointsPerType: {
      multiple_choice: 1,
      short_answer: 2,
      true_false: 1,
      matching: 1,
      extended_response: 4,
      math_equation: 2,
      data_table: 3,
      multiselect: 2,
      multi_part: 2,
      grid_match: 3,
      inline_dropdown: 2,
    },
    dokDistribution: {
      "1": 4,
      "2": 8,
      "3": 6,
      "4": 2,
    },
    includeAnswerKey: true,
    includeStandardsReference: true,
  });
  // sectionsDropdownOpen moved into PlannerTab in PR 5.

  // Helper function to distribute questions across types based on enabled section categories
  const distributeQuestions = (total, categories = null) => {
    const cats = categories || assessmentConfig.sectionCategories || {};
    // Map section categories → question types with weights
    // FL FAST alignment: heavy MC + short answer + STEM visuals
    const typeWeights = {};
    if (cats.multiple_choice) typeWeights.multiple_choice = 40;
    if (cats.short_answer) typeWeights.short_answer = 15;
    if (cats.math_computation) typeWeights.math_equation = 15;
    if (cats.geometry_visual || cats.graphing || cats.data_analysis) typeWeights.data_table = 15;
    if (cats.extended_writing) typeWeights.extended_response = 10;
    if (cats.true_false) typeWeights.true_false = 10;
    if (cats.vocabulary) typeWeights.matching = 10;
    if (cats.florida_fast) { typeWeights.multiselect = 10; typeWeights.multi_part = 8; typeWeights.grid_match = 6; typeWeights.inline_dropdown = 6; }

    // If nothing enabled, default to MC
    if (Object.keys(typeWeights).length === 0) typeWeights.multiple_choice = 100;

    const totalWeight = Object.values(typeWeights).reduce((a, b) => a + b, 0);
    const result = {};
    let assigned = 0;
    const entries = Object.entries(typeWeights);
    entries.forEach(([type, weight], i) => {
      if (i === entries.length - 1) {
        result[type] = Math.max(1, total - assigned); // remainder
      } else {
        const count = Math.max(1, Math.round(total * weight / totalWeight));
        result[type] = count;
        assigned += count;
      }
    });

    // Ensure all types exist in result
    const allTypes = ['multiple_choice', 'short_answer', 'extended_response', 'true_false', 'matching', 'math_equation', 'data_table', 'multiselect', 'multi_part', 'grid_match', 'inline_dropdown'];
    allTypes.forEach(t => { if (!(t in result)) result[t] = 0; });
    return result;
  };

  // Get subject-appropriate section category defaults
  // getSubjectSectionDefaults extracted to utils/assessmentDistribution.js (decomp slice 18).

  // assignmentQuestionCounts portion of this effect moved into PlannerTab
  // in PR 8d alongside the assignmentQuestionCounts state itself.
  useEffect(() => {
    if (config.subject) {
      var newCats = getSubjectSectionDefaults(config.subject);
      var total = assessmentConfig.totalQuestions || 20;
      var newTypes = distributeQuestions(total, newCats);
      var newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);
      var numericCats = Object.fromEntries(Object.entries(newCats).map(function(e) { return [e[0], e[1] ? Math.max(1, Math.round(total / Object.values(newCats).filter(Boolean).length)) : 0]; }));
      setAssessmentConfig(prev => ({
        ...prev,
        sectionCategories: numericCats,
        questionTypes: newTypes,
        pointsPerType: newPointsPerType,
      }));
    }
  }, [config.subject]);

  // Helper function to distribute DOK levels
  // distributeDOK + distributePoints extracted to utils/assessmentDistribution.js (decomp slice 18).

  const [generatedAssessment, setGeneratedAssessment] = useState(null);
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessmentAnswers, setAssessmentAnswers] = useState({}); // Track interactive answers for preview
  const [assessmentGradingResults, setAssessmentGradingResults] = useState(null); // Results from AI grading
  const [gradingAssessment, setGradingAssessment] = useState(false);
  // plannerMode stays in App.jsx so TutorialOverlay (rendered at App level)
  // can drive Planner tutorial steps that switch between lesson/assessment/
  // dashboard/calendar modes. The rest of the calendar slice (calendarData
  // + 14 UI states + 11 helpers + 2 useEffects) moved into PlannerTab in
  // PR 3 of the Planner extraction sprint.
  const [plannerMode, setPlannerMode] = useState("lesson"); // "lesson", "assessment", "dashboard", or "calendar"

  // Edit-state reset on [generatedAssessment] change moved into PlannerTab in
  // PR 5 alongside the moved states.

  // publishingAssessment moved into PlannerTab in PR 7c (publish cluster).
  const [teacherClasses, setTeacherClasses] = useState([]);
  // publishClassId + publishedAssessmentModal moved into PlannerTab in PR 7c.
  // Share-with-class modal state
  // showShareModal + shareModalContent + shareModalSelected + shareModalSharing
  // moved into PlannerTab in PR 7d (share cluster).
  const [assessmentTemplates, setAssessmentTemplates] = useState([]);
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  // showPlatformExport moved into PlannerTab in PR 7b of the Planner extraction sprint.

  // Teacher Dashboard state (Student Portal)
  const [publishedAssessments, setPublishedAssessments] = useState([]);
  const [loadingPublished, setLoadingPublished] = useState(false);
  const [selectedAssessmentResults, setSelectedAssessmentResults] = useState(null);
  const [inProgressDrafts, setInProgressDrafts] = useState([]);
  const [loadingResults, setLoadingResults] = useState(false);
  // attemptDrawerStudent + the AttemptDrawer modal block moved into
  // PlannerTab in PR 7a of the Planner extraction sprint.
  const [contentSubmissionsGroups, setContentSubmissionsGroups] = useState([]);
  const [sharedResources, setSharedResources] = useState([]);
  const [loadingSharedResources, setLoadingSharedResources] = useState(false);
  // newUnitModal + tagDropdownOpenFor moved into PlannerTab in PR 7e
  // (NewUnit + tag cluster); they're consumed only by renderTagRow + the
  // 4 tag handlers, all of which moved together.
  const [allTeacherTags, setAllTeacherTags] = useState([]);
  const [selectedTagFilter, setSelectedTagFilter] = useState('all');

  // Saved Assessments state
  const [savedAssessments, setSavedAssessments] = useState([]);
  const [loadingSavedAssessments, setLoadingSavedAssessments] = useState(false);

  // Publish Modal state (showPublishModal + publishSettings +
  // publishModalStudents + loadingPublishStudents) moved into PlannerTab
  // in PR 7c of the Planner extraction sprint.
  const [savingAssessment, setSavingAssessment] = useState(false);
  const [saveAssessmentName, setSaveAssessmentName] = useState('');

  // File upload state
  const [rosters, setRosters] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [supportDocs, setSupportDocs] = useState([]);
  const [uploadingRoster, setUploadingRoster] = useState(false);




  // Accommodation state (IEP/504 support - FERPA compliant)
  const [accommodationPresets, setAccommodationPresets] = useState([]);
  const [studentAccommodations, setStudentAccommodations] = useState({});



  // Rubric state
  const [rubric, setRubric] = useState({
    categories: [
      {
        name: "Content Accuracy",
        weight: 40,
        description: "Are answers factually correct?",
      },
      {
        name: "Completeness",
        weight: 25,
        description: "Did student attempt all questions?",
      },
      {
        name: "Writing Quality",
        weight: 20,
        description: "Is writing clear and readable?",
      },
      {
        name: "Effort & Engagement",
        weight: 15,
        description: "Did student show genuine effort?",
      },
    ],
    gradingStyle: 'lenient',
  });

  // logRef moved into tabs/GradeTab.jsx (with the auto-scroll + auto-expand-on-error effects)
  // in PR 2 of the Grade tab extraction sprint.
  const fileInputRef = useRef(null);
  const docHtmlRef = useRef(null);
  const rosterInputRef = useRef(null);

  // Track if initial load is complete (to avoid saving on first render)
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  // Load saved settings on startup (wait for approval gate)
  useEffect(() => {
    if (userApproved !== true) return;
    Promise.all([
      api
        .loadGlobalSettings()
        .then((data) => {
          if (data.settings?.globalAINotes)
            setGlobalAINotes(data.settings.globalAINotes);
          if (data.settings?.config) {
            // Migrate old "History" subject to "US History"
            const loadedConfig = { ...data.settings.config };
            if (loadedConfig.subject === "History") {
              loadedConfig.subject = "US History";
            }
            setConfig((prev) => ({ ...prev, ...loadedConfig }));
          }
        })
        .catch(console.error),
      api
        .loadRubric()
        .then((data) => {
          if (data.rubric) setRubric(function(prev) { return Object.assign({}, prev, data.rubric); });
        })
        .catch(console.error),
    ]).then(() => {
      // Mark settings as loaded after a short delay to prevent immediate auto-save
      setTimeout(() => setSettingsLoaded(true), 500);
    });

    api
      .listAssignments()
      .then((data) => {
        if (data.assignments) setSavedAssignments(data.assignments);
        if (data.assignmentData) setSavedAssignmentData(data.assignmentData);
      })
      .catch(console.error);

    // Load uploaded files
    api
      .listRosters()
      .then((data) => {
        if (data.rosters) setRosters(data.rosters);
      })
      .catch(console.error);

    api
      .listPeriods()
      .then((data) => {
        if (data.periods) setPeriods(data.periods);
      })
      .catch(console.error);

    api
      .listSupportDocuments()
      .then((data) => {
        if (data.documents) setSupportDocs(data.documents);
      })
      .catch(console.error);

    // Load accommodation presets and student mappings (FERPA compliant - local only)
    api
      .getAccommodationPresets()
      .then((data) => {
        if (data.presets) setAccommodationPresets(data.presets);
      })
      .catch(console.error);

    api
      .getStudentAccommodations()
      .then((data) => {
        if (data.accommodations) setStudentAccommodations(data.accommodations);
      })
      .catch(console.error);

    // Load saved lessons for assessment generation
    api
      .listLessons()
      .then((data) => {
        if (data.units) {
          setSavedLessons(data);
        }
      })
      .catch(console.error);

    // Check API keys status
    api
      .checkApiKeys()
      .then((data) => {
        setApiKeys((prev) => ({
          ...prev,
          openaiConfigured: data.openai_configured,
          anthropicConfigured: data.anthropic_configured,
          geminiConfigured: data.gemini_configured,
          openaiIsOwn: data.openai_is_own || false,
          anthropicIsOwn: data.anthropic_is_own || false,
          geminiIsOwn: data.gemini_is_own || false,
        }));
      })
      .catch(console.error);
  }, [userApproved]);

  // Refresh saved assignments when switching to Builder tab
  useEffect(() => {
    if (activeTab === "builder") {
      api
        .listAssignments()
        .then((data) => {
          if (data.assignments) setSavedAssignments(data.assignments);
          if (data.assignmentData) setSavedAssignmentData(data.assignmentData);
        })
        .catch(console.error);
    }
  }, [activeTab]);

  useSettingsAutoSave({ config, globalAINotes, rubric, settingsLoaded });

  // Show onboarding wizard on first run
  useEffect(() => {
    if (!settingsLoaded) return;
    if (!config.onboarding_completed) {
      setShowOnboardingWizard(true);
    }
  }, [settingsLoaded]);


  // Stripe billing redirect handling extracted to useBillingRedirect (decomp slice 4).
  useBillingRedirect({ addToast, setActiveTab, setSettingsTab });

  // Builder assignment auto-save extracted to useAssignmentAutoSave (decomp slice 5).
  useAssignmentAutoSave({
    assignment,
    setAssignment,
    importedDoc,
    settingsLoaded,
    loadedAssignmentName,
    setLoadedAssignmentName,
    isLoadingAssignment,
    skipAutoSaveRef,
    setSavedAssignments,
    setSavedAssignmentData,
    addToast,
  });

  // Fetch status once on mount (catch in-progress grading on page refresh)
  useEffect(() => {
    api.getStatus().then(setStatus).catch(() => {});
  }, []);

  // Adaptive grading status-poll extracted to useGradingStatusPoll (decomp slice 6).
  useGradingStatusPoll({ status, setStatus });

  // Fetch pending confirmation count and student list (scans assignments folder + roster)
  const fetchPendingConfirmations = async (studentOverride) => {
    if (!config.assignments_folder) return;
    try {
      var data = await api.getPendingConfirmations({
        assignments_folder: config.assignments_folder,
        period_filter: resultsPeriodFilter,
        student_filter: studentOverride !== undefined ? studentOverride : confirmationStudentFilter,
      });
      setPendingConfirmations(data.count || 0);
      if (data.students) setPendingConfirmationStudents(data.students);
    } catch (e) { /* ignore */ }
  };

  // Refresh count when Results tab opens, period filter changes, or grading stops
  useEffect(() => {
    if (activeTab === "results") fetchPendingConfirmations();
  }, [activeTab, resultsPeriodFilter, confirmationStudentFilter, config.assignments_folder, status.is_running]);

  // Persistent grading-toast lifecycle extracted to useGradingToast (decomp slice 7).
  useGradingToast({ status, config, isLocalhost, addToast, setToasts, removeToast });

  // PR 4 deleted the dead preload effect that called loadAvailableFiles() (a no-op)
  // when gradeFilterStudent changed. Both the effect and the no-op are gone now.

  // Clear selected standards when grade/subject/state changes
  useEffect(() => {
    setSelectedStandards([]);
    setStandards([]);
  }, [config.state, config.grade_level, config.subject]);

  // Load-standards effect moved into PlannerTab in PR 8d (lesson-gen
  // cluster) alongside the plannerLoading state.

  // Planner-mode dashboard fetch + calendar fetch effect + calendar helpers
  // (loadCalendar/scheduleLesson/unscheduleLesson/addHoliday/removeHoliday/
  // isHoliday/getLessonsForDate/isSchoolDay/getCalendarDays/getWeekDays/
  // getStartOfWeek) moved into PlannerTab in PR 3 of the Planner extraction
  // sprint. The analytics-tab fetch below stays — it's keyed off activeTab,
  // not plannerMode.

  useEffect(function() {
    if (activeTab === "analytics" && teacherClasses.length === 0) {
      fetchTeacherClasses();
    }
  }, [activeTab]);

  // Load VPortal credentials on startup so buttons are enabled on Results tab
  useEffect(() => {
    api.getPortalCredentials()
      .then((data) => {
        setVportalConfigured(data.configured || false);
        if (data.email) setVportalEmail(data.email);
      })
      .catch(() => {});
  }, []);

  // Load assessment templates and refresh VPortal credentials when settings tab is opened
  useEffect(() => {
    if (activeTab === "settings") {
      api.getAssessmentTemplates()
        .then((data) => {
          setAssessmentTemplates(data.templates || []);
        })
        .catch((e) => {
          console.error("Error loading assessment templates:", e);
        });
      api.getPortalCredentials()
        .then((data) => {
          setVportalConfigured(data.configured || false);
          if (data.email) setVportalEmail(data.email);
        })
        .catch(() => {});
    }
  }, [activeTab]);

  const { outlookSendStatus, setOutlookSendStatus, outlookSendPolling, setOutlookSendPolling } = useOutlookSendPolling({
    addToast, pendingConfirmationIds, pendingConfirmationFilenames, setPendingConfirmations, fetchPendingConfirmations,
  });



  // Auto-scroll log + auto-expand-on-error effects moved into tabs/GradeTab.jsx
  // (with logRef and showActivityLog state) in PR 2 of the Grade tab extraction sprint.

  // Load email approvals from persisted results AND re-index when results change.
  // emailApprovals is keyed by array index. When re-grading, the backend removes
  // the old result and appends the new one at the end, shifting all indices.
  // This effect rebuilds the index mapping by matching filenames so approvals
  // follow the correct results even when indices change.
  const prevResultsRef = useRef([]);
  useEffect(() => {
    if (status.results.length > 0) {
      const prevResults = prevResultsRef.current;
      const loadedApprovals = {};
      status.results.forEach((r, idx) => {
        if (r.email_approval) {
          loadedApprovals[idx] = r.email_approval;
        }
      });
      setEmailApprovals((prev) => {
        // Build filename → approval from previous state + previous results
        var fileApprovals = {};
        prevResults.forEach(function(r, oldIdx) {
          if (prev[oldIdx]) fileApprovals[r.filename] = prev[oldIdx];
        });
        // Rebuild index-based mapping for current results
        var reindexed = {};
        status.results.forEach(function(r, newIdx) {
          if (loadedApprovals[newIdx]) {
            // Persisted approval on the result itself takes priority
            reindexed[newIdx] = loadedApprovals[newIdx];
          } else if (fileApprovals[r.filename]) {
            // Carry over approval from previous state by filename
            reindexed[newIdx] = fileApprovals[r.filename];
          }
        });
        return reindexed;
      });
    }
    prevResultsRef.current = status.results.map(function(r) { return { filename: r.filename }; });
  }, [status.results]); // Run on every results change, not just length

  // Reset approval gate when new results come in
  useEffect(() => {
    setGradesApproved(false);
  }, [status.results.length]);

  // Sync editedResults with status.results (preserve user edits)
  useEffect(() => {
    if (status.results.length === 0) {
      setEditedResults([]);
      return;
    }
    setEditedResults((prev) => {
      // If same length, merge new data but preserve edits
      if (prev.length === status.results.length) {
        return prev.map((edited, i) => {
          if (edited.edited) {
            return { ...status.results[i], ...edited, edited: true };
          }
          return { ...status.results[i], edited: false };
        });
      }
      // Length changed (results added or deleted) — rebuild from status.results
      // preserving any user edits by matching on filename
      var editMap = {};
      prev.forEach(function(er) {
        if (er.edited) editMap[er.filename] = er;
      });
      return status.results.map(function(r) {
        var existing = editMap[r.filename];
        if (existing) return { ...r, ...existing, edited: true };
        return { ...r, edited: false };
      });
    });
  }, [status.results]);

  // Edited-results auto-save extracted to useEditedResultsAutoSave (decomp slice 8).
  useEditedResultsAutoSave({ editedResults, setEditedResults });

  // Show toast when new assignments are graded
  useEffect(() => {
    const currentCount = status.results.length;
    if (
      config.showToastNotifications &&
      currentCount > lastResultCount.current &&
      lastResultCount.current > 0
    ) {
      const newResults = status.results.slice(lastResultCount.current);
      newResults.forEach((result) => {
        const grade = result.letter_grade || "N/A";
        const score = result.score !== undefined ? `${result.score}%` : "";
        addToast(
          `Graded - ${result.student_name}: ${grade} ${score}`,
          grade === "A" || grade === "B"
            ? "success"
            : grade === "C"
              ? "info"
              : "warning",
        );
      });
    }
    lastResultCount.current = currentCount;
  }, [status.results, config.showToastNotifications]);

  // PR 4 deleted the dead portal-era loadAvailableFiles no-op and the unused
  // fileMatchesPeriodStudent + stripNamePunctuation helpers. AnalyticsTab has
  // its own independent local copy of stripNamePunctuation that still works.
  // loadPeriodStudents was already moved into tabs/GradeTab.jsx in PR 3.

  // Sort periods numerically by extracting number from period_name (e.g., "Period 1" → 1)
  const sortedPeriods = useMemo(() => {
    return [...periods].sort((a, b) => {
      const numA = parseInt(
        (a.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      const numB = parseInt(
        (b.period_name || "").match(/\d+/)?.[0] || "999",
        10,
      );
      return numA - numB;
    });
  }, [periods]);

  // Grading functions
  const handleStartGrading = async () => {
    // Folder-based bulk grading removed — grading happens via portal submissions.
    // This function is kept as a stub for UI references.
    addToast("Grading happens automatically when students submit via the portal.", "info");
  };


  const handleStopGrading = async () => {
    try {
      await api.stopGrading();
      setAutoGrade(false);
    } catch (error) {
      console.error("Failed to stop grading:", error);
    }
  };

  // handleIndividualFileSelect, handleIndividualGrade, clearIndividualUpload,
  // getStudentSuggestions all moved into tabs/GradeTab.jsx (with the state they
  // close over) in PR 3 of the Grade tab extraction sprint.

  // Generate default email body for a result (matches exactly what backend sends)
  const getDefaultEmailBody = (index) => {
    const r = status.results[index];
    if (!r) return "";
    const firstName = r.student_name?.split(" ")[0] || "Student";
    const signature = [
      config.teacher_name || "Your Teacher",
      config.subject,
      config.school_name,
    ]
      .filter(Boolean)
      .join("\n");

    return `Hi ${firstName},

Here is your grade and feedback for ${r.assignment || "your assignment"}:

${"=".repeat(40)}
GRADE: ${r.score}/100 (${r.letter_grade})
${"=".repeat(40)}

FEEDBACK:
${r.feedback || "No feedback available."}

${"=".repeat(40)}

If you have any questions, please see me during class.

${signature}`;
  };

  // Builder functions

  // Helper to get marker text (handles both string and object formats)
  // Marker-accessor helpers extracted to utils/markerHelpers.js (decomp slice 14).


  const handleGenerateModelAnswers = async () => {
    const docText = importedDoc.text || (importedDoc.html ? importedDoc.html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() : '');
    if (!importedDoc || !docText) {
      addToast("Import the assignment document first", "warning");
      return;
    }
    if (!assignment.customMarkers || assignment.customMarkers.length === 0) {
      addToast("Add section markers first", "warning");
      return;
    }
    setModelAnswersLoading(true);
    try {
      var settingsResp = {};
      try { settingsResp = await api.loadGlobalSettings(); } catch(e) {}
      var settings = (settingsResp && settingsResp.settings) || {};
      var data = await api.generateModelAnswers({
        customMarkers: assignment.customMarkers,
        documentText: docText,
        title: assignment.title,
        grade_level: config.grade_level || "7",
        subject: config.subject || "Social Studies",
        globalAINotes: settings.globalAINotes || ""
      });
      if (data.error) { addToast(data.error, "error"); return; }
      var answers = {};
      (data.model_answers || []).forEach(function(ma) {
        answers[ma.section] = ma.answer;
      });
      setAssignment(function(prev) { return Object.assign({}, prev, { modelAnswers: answers }); });
      addToast("Model answers generated! Review and edit below.", "success");
    } catch (err) {
      addToast("Failed: " + err.message, "error");
    } finally {
      setModelAnswersLoading(false);
    }
  };



  // Add or update end marker for a given start marker
  const setEndMarker = (markerIndex, endText) => {
    const updated = [...(assignment.customMarkers || [])];
    const current = updated[markerIndex];
    const startText = getMarkerText(current);

    if (endText && endText.trim()) {
      // Convert to object with end marker
      updated[markerIndex] = { start: startText, end: endText.trim() };
    } else {
      // Remove end marker, convert back to string
      updated[markerIndex] = startText;
    }
    setAssignment({ ...assignment, customMarkers: updated });
  };

  // Normalize special characters (smart quotes, em-dashes) to ASCII equivalents
  // HTML/text highlight helpers extracted to utils/htmlHighlight.js (decomp slice 13).


  // Apply all marker highlights to HTML (start, end, AND exclude markers)
  const applyAllHighlights = (html, markers, excludeMarkers) => {
    if (!html) return html;

    let result = html;
    if (markers) {
      markers.forEach((marker, i) => {
        const startText = getMarkerText(marker);
        const endText = getEndMarker(marker);

        // Highlight start marker in green
        result = highlightTextInHtml(result, startText, HIGHLIGHT_COLORS.start, `start-${i}`);

        // Highlight end marker in red (if exists)
        if (endText) {
          result = highlightTextInHtml(result, endText, HIGHLIGHT_COLORS.end, `end-${i}`);
        }
      });
    }

    // Re-apply exclude marker highlights (orange)
    if (excludeMarkers) {
      excludeMarkers.forEach((marker, i) => {
        result = highlightTextInHtml(result, marker, HIGHLIGHT_COLORS.exclude, `exclude-${i}`);
      });
    }
    return result;
  };

  // Doc import + editor-open handlers extracted to useDocImport (decomp slice 16).
  // Placed AFTER applyAllHighlights: handleDocImport closes over it, and this factory call
  // runs during render, so the const must be initialized first (slice-15 TDZ lesson).
  const {
    handleDocImport,
    openDocEditor,
  } = useDocImport({
  importedDoc,
  assignment,
  savedAssignments,
  applyAllHighlights,
  addToast,
  setImportedDoc,
  setAssignment,
  setLoadedAssignmentName,
  setDocEditorModal,
  });

  // Doc-editor marker handlers extracted to useMarkerEditing (decomp slice 15).
  const {
    addSelectedAsMarker,
    removeMarker,
  } = useMarkerEditing({
  docHtmlRef,
  highlighterMode,
  assignment,
  docEditorModal,
  importedDoc,
  HIGHLIGHT_COLORS,
  applyAllHighlights,
  addToast,
  setAssignment,
  setDocEditorModal,
  setImportedDoc,
  });

  const addQuestion = () => {
    setAssignment({
      ...assignment,
      questions: [
        ...assignment.questions,
        {
          id: Date.now(),
          type: "short_answer",
          prompt: "",
          points: 10,
          marker: markerLibrary[assignment.subject]?.[0] || "Answer:",
        },
      ],
    });
  };

  const updateQuestion = (index, field, value) => {
    const updated = [...assignment.questions];
    updated[index] = { ...updated[index], [field]: value };
    setAssignment({ ...assignment, questions: updated });
  };

  const removeQuestion = (index) => {
    setAssignment({
      ...assignment,
      questions: assignment.questions.filter((_, i) => i !== index),
    });
  };

  // Assignment-builder CRUD handlers extracted to useAssignmentBuilderActions (decomp slice 10).
  const {
    saveAssignmentConfig,
    loadAssignment,
    deleteAssignment,
    exportAssignment,
  } = useAssignmentBuilderActions({
  assignment,
  savedAssignments,
  loadedAssignmentName,
  docEditorModal,
  importedDoc,
  skipAutoSaveRef,
  textToRichHtml,
  addToast,
  setAssignment,
  setImportedDoc,
  setDocEditorModal,
  setLoadedAssignmentName,
  setSavedAssignments,
  setSavedAssignmentData,
  setIsLoadingAssignment,
  });

  // Planner functions
  const domainNamesBySubject = {
    Math: { NSO: "Number Sense & Ops", AR: "Algebraic Reasoning", GR: "Geometric Reasoning", DP: "Data & Probability", F: "Functions", T: "Trigonometry", LT: "Logic & Thinking", FL: "Financial Literacy" },
    Science: { N: "Nature of Science", P: "Physical Science", L: "Life Science", E: "Earth & Space" },
    "English/ELA": { R: "Reading", C: "Communication", V: "Vocabulary" },
    "Social Studies": { A: "American History", C: "Civics & Gov", E: "Economics", G: "Geography", W: "World History" },
    Civics: { C: "Civics & Gov", E: "Economics" },
    Geography: { G: "Geography" },
    "US History": { A: "American History" },
    "World History": { W: "World History" },
    Spanish: { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
    French: { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
    "World Languages": { C: "Communication", CU: "Culture", CO: "Connections", CM: "Comparisons", CT: "Communities" },
  };
  const domainNameMap = domainNamesBySubject[config.subject] || domainNamesBySubject.Math;

  const scrollToDomain = (ref, domain) => {
    const container = ref.current;
    if (!container) return;
    const target = container.querySelector('[data-domain="' + domain + '"]');
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const getDomains = (stds) => {
    const seen = [];
    stds.forEach((s) => {
      const parts = s.code.split(".");
      const domain = parts.length >= 3 ? parts[2] : "";
      if (domain && !seen.includes(domain)) seen.push(domain);
    });
    return seen;
  };

  const toggleStandard = (code) => {
    setSelectedStandards((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  // brainstormIdeasHandler + generateLessonPlan moved into PlannerTab in
  // PR 8d (lesson-gen big cluster). Both close over plannerLoading,
  // brainstormLoading, brainstormIdeas, selectedIdea, lessonVariations,
  // assignmentQuestionCounts — all of which moved with them.

  const exportLessonPlanHandler = async () => {
    if (!lessonPlan) return;
    try {
      const data = await api.exportLessonPlan(lessonPlan);
      if (data.error) addToast("Error exporting: " + data.error, "error");
      else addToast("Lesson plan exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  // Reference document upload handlers
  // handleDocUpload moved into PlannerTab in PR 8b (doc upload cluster).

  // removeUploadedDoc + handleMatchStandards moved into PlannerTab in
  // PR 8a (matching cluster). removeUploadedDoc moved with the cluster
  // because it called setMatchResults(null) on doc removal.

  // Assessment generation handlers
  // Assessment authoring handlers extracted to useAssessmentAuthoring (decomp slice 9).
  const {
    generateAssessmentHandler,
    redistributePoints,
    exportAssessmentHandler,
    exportAssessmentForPlatformHandler,
  } = useAssessmentAuthoring({
  config,
  addToast,
  selectedStandards,
  uploadedDocs,
  unitConfig,
  standards,
  assessmentConfig,
  selectedSources,
  globalAINotes,
  contentOnly,
  generatedAssessment,
  setAssessmentLoading,
  setGeneratedAssessment,
  setAssessmentAnswers,
  });

  // Fetch teacher's Clever classes for publish modal
  const fetchTeacherClasses = async () => {
    try {
      const data = await api.listClasses();
      if (data.classes) setTeacherClasses(data.classes);
    } catch (e) {
      console.error("Failed to load classes:", e);
    }
  };

  // publishAssessmentHandler / loadPublishModalStudents /
  // handleContentTypeChange / confirmPublishAssessment moved into
  // PlannerTab in PR 7c (publish cluster).

  // Saved-assessment / saved-lesson handlers extracted to useSavedAssessmentActions (decomp slice 17).
  const {
    saveAssessmentHandler,
    fetchSavedLessons,
    fetchSavedAssessments,
    loadSavedAssessment,
    deleteSavedAssessment,
    gradeAssessmentAnswersHandler,
  } = useSavedAssessmentActions({
  generatedAssessment,
  saveAssessmentName,
  assessmentAnswers,
  addToast,
  setSavingAssessment,
  setSaveAssessmentName,
  setSavedLessons,
  setLoadingSavedAssessments,
  setSavedAssessments,
  setGeneratedAssessment,
  setAssessmentAnswers,
  setAssessmentGradingResults,
  setGradingAssessment,
  });

  // Fetch published assessments for teacher dashboard
  // Teacher-dashboard / publish / resource handlers extracted to useTeacherDashboardActions (decomp slice 11).
  const {
    fetchPublishedAssessments,
    fetchSharedResources,
    fetchTeacherTags,
    handleDeleteSharedResource,
    handleDeleteAllSharedResources,
    fetchContentSubmissions,
    fetchAssessmentResults,
    toggleAssessmentStatus,
    deletePublishedAssessment,
  } = useTeacherDashboardActions({
  addToast,
  selectedAssessmentResults,
  setLoadingPublished,
  setPublishedAssessments,
  setLoadingSharedResources,
  setSharedResources,
  setAllTeacherTags,
  setContentSubmissionsGroups,
  setLoadingResults,
  setSelectedAssessmentResults,
  setInProgressDrafts,
  });

  // handleSetUnit / handleSetTags / handleAddTag / handleRemoveTag moved
  // into PlannerTab in PR 7e (NewUnit + tag cluster). They were the closure
  // set behind renderTagRow; the helper moved with them.

  var itemMatchesTagFilter = function(item) {
    if (selectedTagFilter === 'all') return true;
    if (item.unit_name && item.unit_name === selectedTagFilter) return true;
    var tags = item.tags || [];
    return tags.indexOf(selectedTagFilter) !== -1;
  };

  // renderTagRow helper moved into PlannerTab in PR 7e (NewUnit + tag cluster).



  // generateAssignmentFromLessonHandler deleted in PR 8d. It had no call
  // sites anywhere in the frontend (verified via grep) — orphaned dead
  // code. Its private states (assignmentLoading, assignmentType) were
  // also dead and were removed alongside it.

  // ── Question Edit Mode Handlers ──

  /** Get the active assignment object (could be generatedAssignment, lessonPlan with sections, or generatedAssessment) */
  const getActiveAssignment = () => {
    if (generatedAssignment) return generatedAssignment;
    if (lessonPlan?.sections && !lessonPlan.days) return lessonPlan;
    if (generatedAssessment) return generatedAssessment;
    return null;
  };

  /** Set the active assignment object back into whichever state holds it */
  const setActiveAssignment = (updated) => {
    if (generatedAssignment) {
      setGeneratedAssignment(updated);
    } else if (lessonPlan?.sections && !lessonPlan.days) {
      setLessonPlan(updated);
    } else if (generatedAssessment) {
      setGeneratedAssessment(updated);
    }
  };

  /** Count total questions in the active assignment */
  const getTotalQuestionCount = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return 0;
    return a.sections.reduce((sum, s) => sum + (s.questions?.length || 0), 0);
  };

  // Question-editing helpers (toggleQuestionSelect, selectAllQuestions,
  // saveEditedQuestion, deleteSelectedQuestions, regenerateSelectedQuestions,
  // regenerateOneQuestion) moved into PlannerTab in PR 5 of the Planner
  // extraction sprint. They consume getActiveAssignment + setActiveAssignment
  // (still here, still passed as props) via closure inside PlannerTab.

  // Results/Email functions
  const openReview = (index) => setReviewModal({ show: true, index });

  const updateGrade = (index, field, value) => {
    const updated = [...editedResults];
    updated[index] = { ...updated[index], [field]: value, edited: true };
    if (field === "score") {
      const score = parseInt(value) || 0;
      updated[index].letter_grade =
        score >= 90
          ? "A"
          : score >= 80
            ? "B"
            : score >= 70
              ? "C"
              : score >= 60
                ? "D"
                : "F";
    }
    setEditedResults(updated);

    // Also sync to status.results so the table updates immediately
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      updatedResults[index] = { ...updatedResults[index], [field]: value, edited: true };
      if (field === "score") {
        const score = parseInt(value) || 0;
        updatedResults[index].letter_grade =
          score >= 90 ? "A" : score >= 80 ? "B" : score >= 70 ? "C" : score >= 60 ? "D" : "F";
      }
      return { ...prev, results: updatedResults };
    });
  };

  // Helper to get letter grade from score
  // Results curve + email/approval handlers extracted to useResultsCurveAndEmail (decomp slice 12).
  const {
    applyCurve,
    sendEmails,
    sendSingleEmail,
    updateApprovalStatus,
    updateApprovalsBulk,
  } = useResultsCurveAndEmail({
  addToast,
  status,
  resultsPeriodFilter,
  editedResults,
  editedEmails,
  curveModal,
  emailPreview,
  config,
  getDefaultEmailBody,
  setEditedResults,
  setEditedEmails,
  setStatus,
  setCurveModal,
  setEmailPreview,
  setEmailStatus,
  setEmailApprovals,
  setOutlookSendPolling,
  setOutlookSendStatus,
  });

  const pct = status.total > 0 ? (status.progress / status.total) * 100 : 0;

  // Auth gate — show loading spinner or login screen before main app
  if (authLoading) {
    return <AuthLoadingScreen />;
  }

  if (!user) {
    return <LoginScreen onLogin={function(u) { _setUser(u); }} theme={theme} toggleTheme={toggleTheme} />;
  }

  if (showPasswordReset) {
    return <PasswordResetScreen onDone={() => { setShowPasswordReset(false); window.history.replaceState(null, '', window.location.pathname); }} />;
  }

  if (userApproved === null) {
    // Still checking approval — show spinner instead of briefly flashing the app
    return <ApprovalCheckingScreen />;
  }

  if (userApproved === false) {
    return <NotApprovedScreen handleLogout={handleLogout} />;
  }

  return (
    <div style={{ minHeight: "100vh", padding: "20px" }}>
      {/* AI notice moved to OnboardingWizard */}
      {/* Onboarding Wizard */}
      {showOnboardingWizard && (
        <OnboardingWizard
          config={config}
          setConfig={setConfig}
          rubric={rubric}
          setRubric={setRubric}
          apiKeys={apiKeys}
          setApiKeys={setApiKeys}
          user={user}
          onComplete={(navigateTo) => {
            setShowOnboardingWizard(false);
            if (navigateTo === "builder") setActiveTab("builder");
            if (!localStorage.getItem("graider-tutorial-complete")) {
              setTutorialStep(0);
              setShowTutorial(true);
            }
          }}
          addToast={addToast}
          theme={theme}
          toggleTheme={toggleTheme}
        />
      )}

      {/* Tutorial Overlay */}
      {showTutorial && (
        <TutorialOverlay
          currentStep={tutorialStep}
          onNext={() => setTutorialStep((s) => Math.min(s + 1, TUTORIAL_STEPS.length - 1))}
          onBack={() => setTutorialStep((s) => Math.max(s - 1, 0))}
          onSkip={() => {
            setShowTutorial(false);
            setTutorialStep(0);
            localStorage.setItem("graider-tutorial-complete", "true");
          }}
          setActiveTab={setActiveTab}
          setSettingsTab={setSettingsTab}
          setPlannerMode={setPlannerMode}
        />
      )}

      {/* Email Preview Modal */}
      {emailPreview.show && (
        <EmailPreviewModal
          emailPreview={emailPreview}
          sendEmails={sendEmails}
          setEmailPreview={setEmailPreview}
        />
      )}

      {/* Review Modal - Full Screen */}
      {reviewModal.show && reviewModal.index >= 0 && (
        <ReviewModal
          addToast={addToast}
          autoApproveEmails={autoApproveEmails}
          config={config}
          editedEmails={editedEmails}
          editedResults={editedResults}
          emailApprovals={emailApprovals}
          reviewModal={reviewModal}
          reviewModalRightTab={reviewModalRightTab}
          reviewModalTab={reviewModalTab}
          sentEmails={sentEmails}
          setEditedEmails={setEditedEmails}
          setReviewModal={setReviewModal}
          setReviewModalRightTab={setReviewModalRightTab}
          setReviewModalTab={setReviewModalTab}
          setSentEmails={setSentEmails}
          setShowAIReasoning={setShowAIReasoning}
          setStatus={setStatus}
          showAIReasoning={showAIReasoning}
          status={status}
          updateApprovalStatus={updateApprovalStatus}
          updateGrade={updateGrade}
        />
      )}

      {/* Document Editor Modal */}
      {docEditorModal.show && (
        <DocumentEditorModal
          HIGHLIGHT_COLORS={HIGHLIGHT_COLORS}
          addSelectedAsMarker={addSelectedAsMarker}
          addToast={addToast}
          applyAllHighlights={applyAllHighlights}
          assignment={assignment}
          docEditorModal={docEditorModal}
          docHtmlRef={docHtmlRef}
          getEndMarker={getEndMarker}
          getMarkerText={getMarkerText}
          highlighterMode={highlighterMode}
          importedDoc={importedDoc}
          removeAllHighlightsFromHtml={removeAllHighlightsFromHtml}
          removeMarker={removeMarker}
          setAssignment={setAssignment}
          setDocEditorModal={setDocEditorModal}
          setHighlighterMode={setHighlighterMode}
          setImportedDoc={setImportedDoc}
          setLoadedAssignmentName={setLoadedAssignmentName}
          setSavedAssignmentData={setSavedAssignmentData}
          setSavedAssignments={setSavedAssignments}
        />
      )}

      {/* App Layout with Sidebar */}
      <div style={{ display: "flex", minHeight: "100vh" }}>
        {/* Sidebar */}
        <Sidebar
          activeTab={activeTab}
          TABS={TABS}
          handleLogout={handleLogout}
          isAdmin={isAdmin}
          setActiveTab={setActiveTab}
          setSidebarCollapsed={setSidebarCollapsed}
          sidebarCollapsed={sidebarCollapsed}
          theme={theme}
        />

        {/* Main Content */}
        <div
          style={{
            flex: 1,
            marginLeft: sidebarCollapsed ? "70px" : "260px",
            padding: "0",
            minWidth: 0,
            overflowX: "auto",
            display: "flex",
            flexDirection: "column",
            transition: "all 0.3s ease",
          }}
        >
          {/* Top Header Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "15px 30px",
              borderBottom: "1px solid var(--glass-border)",
              background: "var(--card-bg)",
              position: "sticky",
              top: 0,
              zIndex: 50,
            }}
          >
            {/* Left: Auto-Grade & Start/Stop */}
            <div data-tutorial="grade-toolbar" style={{ display: "flex", alignItems: "center", gap: "15px" }}>
              <div
                style={{
                  width: "1px",
                  height: "24px",
                  background: "var(--glass-border)",
                }}
              />
              {!status.is_running ? (
                <button
                  onClick={handleStartGrading}
                  className="btn btn-primary"
                  style={{ padding: "8px 20px" }}
                >
                  <Icon name="Play" size={16} />
                  Start Grading
                </button>
              ) : (
                <button
                  onClick={handleStopGrading}
                  className="btn btn-danger"
                  style={{ padding: "8px 20px" }}
                >
                  <Icon name="Square" size={16} />
                  Stop ({status.progress}/{status.total})
                </button>
              )}
            </div>

            {/* Right: Theme Toggle */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={toggleTheme}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px",
                borderRadius: "8px",
                border: "1px solid var(--glass-border)",
                background: "var(--glass-bg)",
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
              title={
                theme === "dark"
                  ? "Switch to Light Mode"
                  : "Switch to Dark Mode"
              }
            >
              <Icon name={theme === "dark" ? "Sun" : "Moon"} size={18} />
            </button>
            </div>
          </div>

          <div style={{ padding: activeTab === "results" ? "20px 15px" : "30px", flex: 1, overflowY: "auto" }}>
            <div style={{ maxWidth: activeTab === "results" ? "none" : "1400px", margin: "0 auto" }}>
              {/* Grade Tab — always-mounted with display:none so state persists across tab switches.
                  Same precedent as the Assistant tab below at App.jsx:9306-9317.
                  Required before PR 2 moves Grade-specific state into GradeTab — conditional
                  mount + local state would reset state on every tab switch. */}
              <div style={{ display: activeTab === "grade" ? "block" : "none" }}>
                <GradeTab
                  status={status}
                  setStatus={setStatus}
                  config={config}
                  globalAINotes={globalAINotes}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  addToast={addToast}
                  periods={periods}
                  sortedPeriods={sortedPeriods}
                  emailApprovals={emailApprovals}
                />
              </div>

              {/* Results Tab */}
              {activeTab === "results" && (
                <ResultsTab
                  status={status}
                  config={config}
                  rubric={rubric}
                  globalAINotes={globalAINotes}
                  theme={theme}
                  resultsPeriodFilter={resultsPeriodFilter}
                  editedResults={editedResults}
                  emailApprovals={emailApprovals}
                  sentEmails={sentEmails}
                  editedEmails={editedEmails}
                  emailStatus={emailStatus}
                  autoApproveEmails={autoApproveEmails}
                  gradesApproved={gradesApproved}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  studentAccommodations={studentAccommodations}
                  sortedPeriods={sortedPeriods}
                  portalSubmissions={portalSubmissions}
                  assessmentResults={assessmentResults}
                  setAssessmentResults={setAssessmentResults}
                  vportalConfigured={vportalConfigured}
                  outlookSendStatus={outlookSendStatus}
                  focusCommsStatus={focusCommsStatus}
                  focusCommentsStatus={focusCommentsStatus}
                  curveModal={curveModal}
                  colWidths={colWidths}
                  defaultColPercents={defaultColPercents}
                  pendingConfirmations={pendingConfirmations}
                  pendingConfirmationStudents={pendingConfirmationStudents}
                  confirmationStudentFilter={confirmationStudentFilter}
                  setResultsPeriodFilter={setResultsPeriodFilter}
                  setStatus={setStatus}
                  setConfig={setConfig}
                  setEditedResults={setEditedResults}
                  setEmailApprovals={setEmailApprovals}
                  setSentEmails={setSentEmails}
                  setEditedEmails={setEditedEmails}
                  setEmailStatus={setEmailStatus}
                  setAutoApproveEmails={setAutoApproveEmails}
                  setGradesApproved={setGradesApproved}
                  setOutlookSendStatus={setOutlookSendStatus}
                  setOutlookSendPolling={setOutlookSendPolling}
                  setFocusCommsStatus={setFocusCommsStatus}
                  setFocusCommsPolling={setFocusCommsPolling}
                  setFocusCommentsStatus={setFocusCommentsStatus}
                  setFocusCommentsPolling={setFocusCommentsPolling}
                  setCurveModal={setCurveModal}
                  setFocusExportModal={setFocusExportModal}
                  setColWidths={setColWidths}
                  setConfirmationStudentFilter={setConfirmationStudentFilter}
                  addToast={addToast}
                  openReview={openReview}
                  sendSingleEmail={sendSingleEmail}
                  getDefaultEmailBody={getDefaultEmailBody}
                  updateApprovalsBulk={updateApprovalsBulk}
                  initColWidths={initColWidths}
                  handleResizeStart={handleResizeStart}
                  tableRef={tableRef}
                  pendingConfirmationIds={pendingConfirmationIds}
                  pendingConfirmationFilenames={pendingConfirmationFilenames}
                />
              )}

              {/* Help Tab */}
              <HelpTab activeTab={activeTab} setShowTutorial={setShowTutorial} setTutorialStep={setTutorialStep} />

              {/* Settings Tab */}
              {activeTab === "settings" && (
                <SettingsTab
                  settingsTab={settingsTab}
                  setSettingsTab={setSettingsTab}
                  config={config}
                  setConfig={setConfig}
                  rubric={rubric}
                  setRubric={setRubric}
                  globalAINotes={globalAINotes}
                  setGlobalAINotes={setGlobalAINotes}
                  apiKeys={apiKeys}
                  setApiKeys={setApiKeys}
                  subscription={subscription}
                  setSubscription={setSubscription}
                  subscriptionLoading={subscriptionLoading}
                  setSubscriptionLoading={setSubscriptionLoading}
                  periods={periods}
                  setPeriods={setPeriods}
                  rosters={rosters}
                  setRosters={setRosters}
                  studentAccommodations={studentAccommodations}
                  setStudentAccommodations={setStudentAccommodations}
                  vportalEmail={vportalEmail}
                  setVportalEmail={setVportalEmail}
                  vportalConfigured={vportalConfigured}
                  setVportalConfigured={setVportalConfigured}
                  supportDocs={supportDocs}
                  setSupportDocs={setSupportDocs}
                  assessmentTemplates={assessmentTemplates}
                  setAssessmentTemplates={setAssessmentTemplates}
                  uploadingTemplate={uploadingTemplate}
                  setUploadingTemplate={setUploadingTemplate}
                  showOnboardingWizard={showOnboardingWizard}
                  setShowOnboardingWizard={setShowOnboardingWizard}
                  sortedPeriods={sortedPeriods}
                  accommodationPresets={accommodationPresets}
                  EDTECH_TOOLS={EDTECH_TOOLS}
                  MODEL_COST_PER_ASSIGNMENT={MODEL_COST_PER_ASSIGNMENT}
                  addToast={addToast}
                />
              )}

              {/* Script Builder / Automations Tab */}
              {activeTab === "automations" && (
                <div className="fade-in glass-card" style={{ padding: "25px" }}>
                  <AutomationBuilder addToast={addToast} />
                </div>
              )}

              {/* Assistant Tab — always mounted so chat persists across tab switches */}
              <div data-tutorial="assistant-chat" className={activeTab === "assistant" ? "fade-in glass-card" : ""} style={{
                padding: 0,
                overflow: "hidden",
                display: activeTab === "assistant" ? "flex" : "none",
                position: "relative",
              }}>
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                  <AssistantChat addToast={addToast} subject={config.subject} />
                </div>
                {window.location.hostname === 'localhost' && <BehaviorPanel addToast={addToast} />}
              </div>

              {/* Builder Tab */}
              {activeTab === "builder" && (
                <BuilderTab
                  assignment={assignment}
                  setAssignment={setAssignment}
                  savedAssignments={savedAssignments}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  loadedAssignmentName={loadedAssignmentName}
                  setLoadedAssignmentName={setLoadedAssignmentName}
                  isLoadingAssignment={isLoadingAssignment}
                  setIsLoadingAssignment={setIsLoadingAssignment}
                  importedDoc={importedDoc}
                  setImportedDoc={setImportedDoc}
                  docEditorModal={docEditorModal}
                  setDocEditorModal={setDocEditorModal}
                  modelAnswersLoading={modelAnswersLoading}
                  config={config}
                  fileInputRef={fileInputRef}
                  skipAutoSaveRef={skipAutoSaveRef}
                  loadAssignment={loadAssignment}
                  deleteAssignment={deleteAssignment}
                  saveAssignmentConfig={saveAssignmentConfig}
                  exportAssignment={exportAssignment}
                  handleDocImport={handleDocImport}
                  openDocEditor={openDocEditor}
                  handleGenerateModelAnswers={handleGenerateModelAnswers}
                  removeMarker={removeMarker}
                  addQuestion={addQuestion}
                  updateQuestion={updateQuestion}
                  removeQuestion={removeQuestion}
                  addToast={addToast}
                  getMarkerText={getMarkerText}
                  getMarkerPoints={getMarkerPoints}
                  getMarkerType={getMarkerType}
                  calculateTotalPoints={calculateTotalPoints}
                  removeAllHighlightsFromHtml={removeAllHighlightsFromHtml}
                  applyAllHighlights={applyAllHighlights}
                  textToRichHtml={textToRichHtml}
                  markerLibrary={markerLibrary}
                />
              )}

              {/* Analytics Tab */}
              {activeTab === "analytics" && (
                <Suspense fallback={
                  <div className="glass-card" style={{ padding: "80px", textAlign: "center" }}>
                    <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>Loading Analytics...</h2>
                  </div>
                }>
                  <AnalyticsTab
                    config={config}
                    status={status}
                    periods={periods}
                    sortedPeriods={sortedPeriods}
                    savedAssignments={savedAssignments}
                    savedAssignmentData={savedAssignmentData}
                    addToast={addToast}
                    assessmentResults={assessmentResults}
                    teacherClasses={teacherClasses}
                  />
                </Suspense>
              )}

              {/* Admin Tab */}
              {activeTab === "admin" && isAdmin && (
                <Suspense fallback={
                  <div className="glass-card" style={{ padding: "80px", textAlign: "center" }}>
                    <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>Loading Admin...</h2>
                  </div>
                }>
                  <AdminTab school={adminSchool} />
                </Suspense>
              )}

              {/* Planner Tab — extracted into tabs/PlannerTab.jsx in PR 1
                  of the Planner tab extraction sprint (plan
                  docs/superpowers/plans/2026-05-04-planner-tab-extraction.md).
                  PR 2 converted to always-mounted with display:none style —
                  same precedent as Assistant tab (App.jsx:7497-7508) and
                  Grade tab (App.jsx:7074). PR 3 moved the calendar slice
                  (calendarData + 14 calendar UI states + 11 calendar
                  helpers + 2 calendar useEffects) into PlannerTab.
                  `plannerMode` stays here so TutorialOverlay (rendered at
                  the App level) can flip Planner sub-modes during tutorial
                  steps without a request/response bridge. */}
              <div style={{ display: activeTab === "planner" ? "block" : "none" }}>
                <PlannerTab
                  status={status}
                  setStatus={setStatus}
                  config={config}
                  setConfig={setConfig}
                  user={user}
                  activeTab={activeTab}
                  addToast={addToast}
                  studentAccommodations={studentAccommodations}
                  lessonPlan={lessonPlan}
                  setLessonPlan={setLessonPlan}
                  generatedAssignment={generatedAssignment}
                  setGeneratedAssignment={setGeneratedAssignment}
                  assessmentConfig={assessmentConfig}
                  setAssessmentConfig={setAssessmentConfig}
                  selectedStandards={selectedStandards}
                  setSelectedStandards={setSelectedStandards}
                  unitConfig={unitConfig}
                  setUnitConfig={setUnitConfig}
                  standards={standards}
                  setStandards={setStandards}
                  setAssignment={setAssignment}
                  uploadedDocs={uploadedDocs}
                  setUploadedDocs={setUploadedDocs}
                  generatedAssessment={generatedAssessment}
                  setGeneratedAssessment={setGeneratedAssessment}
                  rubric={rubric}
                  setRubric={setRubric}
                  globalAINotes={globalAINotes}
                  setGlobalAINotes={setGlobalAINotes}
                  supportDocs={supportDocs}
                  setSupportDocs={setSupportDocs}
                  savedAssignments={savedAssignments}
                  setSavedAssignments={setSavedAssignments}
                  teacherClasses={teacherClasses}
                  setTeacherClasses={setTeacherClasses}
                  periods={periods}
                  setPeriods={setPeriods}
                  savedAssignmentData={savedAssignmentData}
                  setSavedAssignmentData={setSavedAssignmentData}
                  contentOnly={contentOnly}
                  setContentOnly={setContentOnly}
                  assessmentTemplates={assessmentTemplates}
                  setAssessmentTemplates={setAssessmentTemplates}
                  uploadingTemplate={uploadingTemplate}
                  setUploadingTemplate={setUploadingTemplate}
                  plannerMode={plannerMode}
                  setPlannerMode={setPlannerMode}
                  assessmentLoading={assessmentLoading}
                  setAssessmentLoading={setAssessmentLoading}
                  gradingAssessment={gradingAssessment}
                  setGradingAssessment={setGradingAssessment}
                  savingAssessment={savingAssessment}
                  setSavingAssessment={setSavingAssessment}
                  saveAssessmentName={saveAssessmentName}
                  setSaveAssessmentName={setSaveAssessmentName}
                  assessmentAnswers={assessmentAnswers}
                  setAssessmentAnswers={setAssessmentAnswers}
                  assessmentGradingResults={assessmentGradingResults}
                  setAssessmentGradingResults={setAssessmentGradingResults}
                  selectedSources={selectedSources}
                  setSelectedSources={setSelectedSources}
                  selectedAssessmentResults={selectedAssessmentResults}
                  setSelectedAssessmentResults={setSelectedAssessmentResults}
                  publishedAssessments={publishedAssessments}
                  setPublishedAssessments={setPublishedAssessments}
                  loadingPublished={loadingPublished}
                  setLoadingPublished={setLoadingPublished}
                  inProgressDrafts={inProgressDrafts}
                  setInProgressDrafts={setInProgressDrafts}
                  loadingResults={loadingResults}
                  setLoadingResults={setLoadingResults}
                  sharedResources={sharedResources}
                  setSharedResources={setSharedResources}
                  loadingSharedResources={loadingSharedResources}
                  setLoadingSharedResources={setLoadingSharedResources}
                  contentSubmissionsGroups={contentSubmissionsGroups}
                  setContentSubmissionsGroups={setContentSubmissionsGroups}
                  savedAssessments={savedAssessments}
                  setSavedAssessments={setSavedAssessments}
                  loadingSavedAssessments={loadingSavedAssessments}
                  setLoadingSavedAssessments={setLoadingSavedAssessments}
                  savedLessons={savedLessons}
                  setSavedLessons={setSavedLessons}
                  allTeacherTags={allTeacherTags}
                  setAllTeacherTags={setAllTeacherTags}
                  selectedTagFilter={selectedTagFilter}
                  setSelectedTagFilter={setSelectedTagFilter}
                  loadAssignment={loadAssignment}
                  saveAssignmentConfig={saveAssignmentConfig}
                  domainNameMap={domainNameMap}
                  getDomains={getDomains}
                  scrollToDomain={scrollToDomain}
                  toggleStandard={toggleStandard}
                  standardsScrollRef={standardsScrollRef}
                  assessmentStandardsScrollRef={assessmentStandardsScrollRef}
                  deleteSavedAssessment={deleteSavedAssessment}
                  loadSavedAssessment={loadSavedAssessment}
                  saveAssessmentHandler={saveAssessmentHandler}
                  generateAssessmentHandler={generateAssessmentHandler}
                  gradeAssessmentAnswersHandler={gradeAssessmentAnswersHandler}
                  exportAssessmentHandler={exportAssessmentHandler}
                  exportAssessmentForPlatformHandler={exportAssessmentForPlatformHandler}
                  deletePublishedAssessment={deletePublishedAssessment}
                  toggleAssessmentStatus={toggleAssessmentStatus}
                  fetchAssessmentResults={fetchAssessmentResults}
                  fetchPublishedAssessments={fetchPublishedAssessments}
                  fetchSavedAssessments={fetchSavedAssessments}
                  fetchSavedLessons={fetchSavedLessons}
                  fetchSharedResources={fetchSharedResources}
                  fetchTeacherClasses={fetchTeacherClasses}
                  fetchTeacherTags={fetchTeacherTags}
                  handleDeleteAllSharedResources={handleDeleteAllSharedResources}
                  handleDeleteSharedResource={handleDeleteSharedResource}
                  getActiveAssignment={getActiveAssignment}
                  setActiveAssignment={setActiveAssignment}
                  getTotalQuestionCount={getTotalQuestionCount}
                  distributeDOK={distributeDOK}
                  distributePoints={distributePoints}
                  distributeQuestions={distributeQuestions}
                  redistributePoints={redistributePoints}
                  exportLessonPlanHandler={exportLessonPlanHandler}
                  getSubjectSectionDefaults={getSubjectSectionDefaults}
                  itemMatchesTagFilter={itemMatchesTagFilter}
                  setActiveTab={setActiveTab}
                  setLoadedAssignmentName={setLoadedAssignmentName}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Focus Export Modal */}
      {focusExportModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            className="glass-card"
            style={{
              borderRadius: "12px",
              width: "100%",
              maxWidth: "500px",
              padding: "25px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h2
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Download" size={24} />
                Export to Focus
              </h2>
              <button
                onClick={() => setFocusExportModal(false)}
                style={{
                  background: "var(--glass-bg)",
                  border: "1px solid var(--glass-border)",
                  cursor: "pointer",
                  padding: "8px",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon name="X" size={20} />
              </button>
            </div>

            <p
              style={{
                color: "var(--text-secondary)",
                marginBottom: "20px",
                fontSize: "0.9rem",
              }}
            >
              Generate a CSV file formatted for Focus SIS import with Student_ID
              and Score columns.
            </p>


            {/* Group results by assignment — filter out one-off student uploads
                (config mismatches where the "assignment" is actually a filename) */}
            {(() => {
              const assignmentCounts = {};
              status.results.forEach((r) => {
                const a = r.assignment || "Unknown";
                assignmentCounts[a] = (assignmentCounts[a] || 0) + 1;
              });
              const assignments = Object.keys(assignmentCounts)
                .filter((a) => assignmentCounts[a] >= 2 || Object.keys(assignmentCounts).length <= 3)
                .sort((a, b) => assignmentCounts[b] - assignmentCounts[a]);
              const periods = [
                ...new Set(status.results.map((r) => r.period || "All")),
              ];
              return (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "15px",
                  }}
                >
                  <div>
                    <label className="label">Assignment</label>
                    <select
                      id="focus-assignment"
                      className="input"
                      defaultValue={assignments[0]}
                    >
                      {assignments.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </div>
                  {periods.length > 1 && (
                    <div>
                      <label className="label">Period</label>
                      <select
                        id="focus-period"
                        className="input"
                        defaultValue="all"
                      >
                        <option value="all">All Periods</option>
                        {periods
                          .filter((p) => p !== "All")
                          .map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--glass-bg)",
                      borderRadius: "8px",
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Icon
                      name="Info"
                      size={14}
                      style={{ marginRight: "6px", verticalAlign: "middle" }}
                    />
                    Students without a Student_ID will be matched by name using
                    Claude AI.
                  </div>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px",
                    padding: "10px 12px", borderRadius: "8px", cursor: "pointer",
                    background: "var(--glass-bg)", fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                  }}>
                    <input
                      type="checkbox"
                      checked={focusIncludeLetterGrade}
                      onChange={(e) => setFocusIncludeLetterGrade(e.target.checked)}
                      style={{ accentColor: "#6366f1" }}
                    />
                    Include Letter Grade column
                  </label>
                  <button
                    onClick={async () => {
                      setFocusExportLoading(true);
                      try {
                        const assignment =
                          document.getElementById("focus-assignment")?.value;
                        const period =
                          document.getElementById("focus-period")?.value ||
                          "all";

                        // Filter results (use editedResults if available, to include curves/edits)
                        const sourceResults = editedResults.length > 0 ? editedResults : status.results;
                        let resultsToExport = sourceResults.filter(
                          (r) =>
                            (r.assignment || "Unknown") === assignment &&
                            (period === "all" ||
                              (r.period || "All") === period),
                        );

                        const authHdrs = await getAuthHeaders();
                        const response = await fetch("/api/export-focus-csv", {
                          method: "POST",
                          headers: { "Content-Type": "application/json", ...authHdrs },
                          body: JSON.stringify({
                            results: resultsToExport,
                            assignment,
                            period,
                            periods: periods.map((p) => ({ name: p })),
                            include_letter_grade: focusIncludeLetterGrade,
                          }),
                        });

                        const data = await response.json();
                        if (data.csv) {
                          // Download the CSV
                          const blob = new Blob([data.csv], {
                            type: "text/csv",
                          });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = data.filename || "focus_grades.csv";
                          document.body.appendChild(a);
                          a.click();
                          document.body.removeChild(a);
                          URL.revokeObjectURL(url);

                          addToast(
                            `Exported ${data.count} grades to ${data.filename}`,
                            "success",
                          );
                          setFocusExportModal(false);
                        } else {
                          addToast(data.error || "Export failed", "error");
                        }
                      } catch (err) {
                        addToast("Export error: " + err.message, "error");
                      } finally {
                        setFocusExportLoading(false);
                      }
                    }}
                    disabled={focusExportLoading || status.results.length === 0}
                    className="btn btn-primary"
                    style={{ width: "100%", marginTop: "10px" }}
                  >
                    {focusExportLoading ? (
                      <>
                        <Icon
                          name="Loader2"
                          size={18}
                          style={{ animation: "spin 1s linear infinite" }}
                        />
                        Generating CSV with Claude...
                      </>
                    ) : (
                      <>
                        <Icon name="Download" size={18} />
                        Download Focus CSV
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => setFocusExportModal(false)}
                    className="btn btn-secondary"
                    style={{ width: "100%", marginTop: "10px" }}
                  >
                    Cancel
                  </button>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {/* Curve Modal */}
      <CurveModal
        open={curveModal.show}
        onClose={() => setCurveModal({ ...curveModal, show: false })}
        curveType={curveModal.curveType}
        setCurveType={(val) => setCurveModal({ ...curveModal, curveType: val })}
        curveValue={curveModal.curveValue}
        setCurveValue={(val) => setCurveModal({ ...curveModal, curveValue: val })}
        periodLabel={resultsPeriodFilter}
        onApply={applyCurve}
      />

      {/* Toast Notifications */}
      <div
        style={{
          position: "fixed",
          top: "20px",
          right: "20px",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          maxWidth: "350px",
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-card fade-in"
            style={{
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background:
                toast.type === "success"
                  ? "rgba(74,222,128,0.15)"
                  : toast.type === "warning"
                    ? "rgba(251,191,36,0.15)"
                    : toast.type === "error"
                      ? "rgba(248,113,113,0.15)"
                      : "rgba(96,165,250,0.15)",
              border: `1px solid ${
                toast.type === "success"
                  ? "rgba(74,222,128,0.4)"
                  : toast.type === "warning"
                    ? "rgba(251,191,36,0.4)"
                    : toast.type === "error"
                      ? "rgba(248,113,113,0.4)"
                      : "rgba(96,165,250,0.4)"
              }`,
              boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
            }}
          >
            <Icon
              name={
                toast.type === "success"
                  ? "CheckCircle"
                  : toast.type === "warning"
                    ? "AlertTriangle"
                    : toast.type === "error"
                      ? "XCircle"
                      : "Info"
              }
              size={18}
              style={{
                color:
                  toast.type === "success"
                    ? "#4ade80"
                    : toast.type === "warning"
                      ? "#fbbf24"
                      : toast.type === "error"
                        ? "#f87171"
                        : "#60a5fa",
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontSize: "0.9rem",
                color: "var(--text-primary)",
                flex: 1,
              }}
            >
              {toast.message}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeToast(toast.id);
              }}
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "4px 6px",
                color: "var(--text-secondary)",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="X" size={16} />
            </button>
          </div>
        ))}
      </div>


      {/* Save Lesson Modal moved into PlannerTab in PR 6b of the Planner
          extraction sprint. */}

      {/* PublishContentModal moved into PlannerTab in PR 7c (publish cluster). */}

      {/* NewUnitModal moved into PlannerTab in PR 7e (NewUnit + tag cluster). */}

      {/* ShareWithClassesModal moved into PlannerTab in PR 7d. */}

      {/* PublishedAssessmentModal moved into PlannerTab in PR 7c. */}

      {/* AttemptDrawer moved into PlannerTab in PR 7a of the Planner
          extraction sprint. */}
    </div>
  );
}

export default App;
