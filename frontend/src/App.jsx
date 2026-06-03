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
import { supabase } from "./services/supabase";
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

  // Auth state — user is "sticky": once logged in, can ONLY be cleared
  // by explicit handleLogout(). This prevents all spurious sign-out events
  // from kicking the user out (Supabase internal auto-refresh failures,
  // race conditions, etc.).
  const [user, _setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [userApproved, setUserApproved] = useState(null); // null=loading, true/false
  const [aiNoticeDismissed, setAiNoticeDismissed] = useState(function() {
    return localStorage.getItem('graider_ai_notice_dismissed') === 'true';
  });
  const logoutIntentRef = useRef(false);

  function setUser(u) {
    if (u == null && !logoutIntentRef.current) {
      // Block all automatic setUser(null) — only explicit logout can clear
      console.warn('Blocked automatic setUser(null)');
      return;
    }
    logoutIntentRef.current = false;
    _setUser(u);
    window.__graiderUser = u;  // lets api.js detect Clever users
  }

  // Check URL hash for recovery token BEFORE Supabase consumes it
  const [showPasswordReset, setShowPasswordReset] = useState(() => {
    const hash = window.location.hash;
    return hash.includes('type=recovery');
  });

  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  // Initialize PostHog (skip on localhost)
  useEffect(() => {
    if (!isLocalhost) initPostHog();
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    // Check for Clever login redirect (before localhost check — works everywhere)
    const urlParams = new URLSearchParams(window.location.search);
    const cleverLogin = urlParams.get('clever_login');
    const cleverError = urlParams.get('clever_error');

    if (cleverLogin === 'success') {
      fetch('/api/clever/session')
        .then(function(r) { return r.json() })
        .then(function(data) {
          if (data.authenticated) {
            _setUser({
              id: 'clever:' + data.clever_id,
              email: data.email,
              user_metadata: {
                name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''),
                approved: true,
              },
            });
            window.__graiderUser = { id: 'clever:' + data.clever_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'clever' };
            setAuthLoading(false);
          }
        })
        .catch(function(err) { console.error('Clever session check failed:', err) });
      window.history.replaceState({}, '', '/');
      return;
    }
    if (cleverError) {
      console.error('Clever login error:', cleverError);
      var cleverErrorMessages = {
        'missing_code': 'Login was cancelled or interrupted. Please try again.',
        'state_mismatch': 'Login session expired. Please try again.',
        'token_exchange_failed': 'Could not complete login with Clever. Please try again.',
        'user_fetch_failed': 'Could not retrieve your account information from Clever.',
        'students_use_portal': 'Student accounts should use the student portal, not the teacher login.',
        'student_not_enrolled': 'Your account was not found. Ask your teacher to sync the class roster.',
        'unsupported_role': 'This account type is not supported.',
      };
      var friendlyMsg = cleverErrorMessages[cleverError] || ('Clever login failed: ' + cleverError);
      // Store error so LoginScreen can display it
      window.__cleverLoginError = friendlyMsg;
      window.history.replaceState({}, '', '/');
    }

    // Check for ClassLink login redirect
    var classlinkLogin = urlParams.get('classlink_login');
    var classlinkError = urlParams.get('classlink_error');

    if (classlinkLogin === 'success') {
      fetch('/api/classlink/session')
        .then(function(r) { return r.json() })
        .then(function(data) {
          if (data.authenticated) {
            _setUser({
              id: data.user_id,
              email: data.email,
              user_metadata: {
                name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''),
                approved: true,
              },
            });
            window.__graiderUser = { id: data.user_id, email: data.email, name: ((data.name || {}).first || '') + ' ' + ((data.name || {}).last || ''), auth_source: 'classlink' };
            setAuthLoading(false);
          }
        })
        .catch(function(err) { console.error('ClassLink session check failed:', err) });
      window.history.replaceState({}, '', '/');
      return;
    }
    if (classlinkError) {
      console.error('ClassLink login error:', classlinkError);
      var classlinkErrorMessages = {
        'no_code': 'Login was cancelled or interrupted. Please try again.',
        'state_mismatch': 'Login session expired. Please try again.',
        'token_failed': 'Could not complete login with ClassLink. Please try again.',
        'no_token': 'Could not complete login with ClassLink. Please try again.',
        'token_error': 'Could not complete login with ClassLink. Please try again.',
        'userinfo_failed': 'Could not retrieve your account information from ClassLink.',
        'userinfo_error': 'Could not retrieve your account information from ClassLink.',
        'account_conflict': 'We could not match your ClassLink account to a Graider account. Please contact your administrator.',
      };
      var classlinkFriendlyMsg = classlinkErrorMessages[classlinkError] || ('ClassLink login failed: ' + classlinkError);
      window.__cleverLoginError = classlinkFriendlyMsg;
      window.history.replaceState({}, '', '/');
    }

    if (isLocalhost) {
      _setUser({ id: 'local-dev', email: 'dev@localhost' });
      setAuthLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data: { session } }) => {
      _setUser(session?.user ?? null);
      setAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT') {
        // Only clear user if explicit logout was requested
        if (logoutIntentRef.current) {
          _setUser(null);
          approvalConfirmedRef.current = false;
          logoutIntentRef.current = false;
        }
      } else if (session?.user) {
        _setUser(session.user);
      }
      if (event === 'PASSWORD_RECOVERY') {
        setShowPasswordReset(true);
      }
    });

    // auth-expired is only honored for explicit logout flow
    function handleAuthExpired() {
      console.warn('auth-expired event received, ignoring (use Sign Out button)');
    }
    window.addEventListener('auth-expired', handleAuthExpired);

    return () => {
      subscription.unsubscribe();
      window.removeEventListener('auth-expired', handleAuthExpired);
    };
  }, []);

  // Approval gate check
  const approvalConfirmedRef = useRef(false);
  useEffect(() => {
    if (!user || isLocalhost) {
      setUserApproved(true);
      approvalConfirmedRef.current = true;
      return;
    }

    // Once confirmed, don't re-check on token refreshes
    if (approvalConfirmedRef.current) {
      setUserApproved(true);
      return;
    }

    // Check local JWT metadata first (instant, no API call)
    if (user.user_metadata && user.user_metadata.approved) {
      setUserApproved(true);
      approvalConfirmedRef.current = true;
      return;
    }

    // JWT metadata may be stale — call backend for fresh check via admin API
    async function checkApproval() {
      try {
        const { getAuthHeaders } = await import('./services/api');
        const headers = await getAuthHeaders();
        const res = await fetch('/api/auth/approval-status', {
          headers: { ...headers },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.approved === true) {
            approvalConfirmedRef.current = true;
            setUserApproved(true);
          } else {
            setUserApproved(false);
          }
        } else if (res.status === 403) {
          // Explicitly denied — user is not approved
          setUserApproved(false);
        }
        // On 500/network errors, leave userApproved as null (loading)
        // so the user sees a spinner instead of being kicked out
      } catch {
        // Network error — don't kick user out, keep showing loading
        console.warn('Approval check failed (network error), will retry');
      }
    }
    checkApproval();

    function handleNotApproved() {
      // Only kick out if we never confirmed approval in this session
      if (!approvalConfirmedRef.current) {
        checkApproval();
      }
    }
    window.addEventListener('account-not-approved', handleNotApproved);
    return () => window.removeEventListener('account-not-approved', handleNotApproved);
  }, [user, isLocalhost]);

  // Identify user in PostHog when they log in
  useEffect(() => {
    if (user && !isLocalhost) identifyUser(user);
  }, [user]);

  async function handleLogout() {
    // Clear SSO sessions for all providers (idempotent — no-op when not authenticated)
    await Promise.allSettled([
      fetch('/api/clever/logout', { method: 'POST', credentials: 'include' }),
      fetch('/api/classlink/logout', { method: 'POST', credentials: 'include' }),
    ]);
    logoutIntentRef.current = true;
    approvalConfirmedRef.current = false;
    resetUser();
    await supabase.auth.signOut();
    _setUser(null);
    window.__graiderUser = null;
  }

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
  const getSubjectSectionDefaults = (subject) => {
    const s = (subject || '').toLowerCase();
    const isMath = s.includes('math') || s.includes('algebra') || s.includes('geometry') || s.includes('calculus') || s.includes('statistics');
    const isScience = s.includes('science') || s.includes('biology') || s.includes('chemistry') || s.includes('physics') || s.includes('earth');
    const isELA = s.includes('ela') || s.includes('english') || s.includes('reading') || s.includes('writing') || s.includes('language arts') || s.includes('literature');
    const isWorldLang = s.includes('spanish') || s.includes('french') || s.includes('world lang') || s.includes('german') || s.includes('italian') || s.includes('portuguese') || s.includes('chinese') || s.includes('japanese');
    const isSocialStudies = s.includes('history') || s.includes('social') || s.includes('civics') || s.includes('economics') || s.includes('geography') || s.includes('government');

    if (isMath) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: true,
        geometry_visual: true,
        graphing: true,
        data_analysis: true,
        extended_writing: false,
        vocabulary: false,
        true_false: false,
      };
    }
    if (isScience) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: true,
        data_analysis: true,
        extended_writing: false,
        vocabulary: true,
        true_false: false,
      };
    }
    if (isELA) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: false,
        data_analysis: false,
        extended_writing: true,
        vocabulary: true,
        true_false: false,
      };
    }
    if (isWorldLang) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: false,
        data_analysis: false,
        extended_writing: true,
        vocabulary: true,
        true_false: true,
      };
    }
    if (isSocialStudies) {
      return {
        multiple_choice: true,
        short_answer: true,
        math_computation: false,
        geometry_visual: false,
        graphing: false,
        data_analysis: false,
        extended_writing: true,
        vocabulary: true,
        true_false: true,
      };
    }
    // Default — generic
    return {
      multiple_choice: true,
      short_answer: true,
      math_computation: false,
      geometry_visual: false,
      graphing: false,
      data_analysis: false,
      extended_writing: true,
      vocabulary: false,
      true_false: false,
    };
  };

  // Update assessment section categories when subject changes. The
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
  const distributeDOK = (total) => {
    // Standard distribution: 20% DOK1, 40% DOK2, 30% DOK3, 10% DOK4
    const dok1 = Math.round(total * 0.20);
    const dok2 = Math.round(total * 0.40);
    const dok3 = Math.round(total * 0.30);
    const dok4 = total - dok1 - dok2 - dok3; // remainder
    return {
      "1": Math.max(0, dok1),
      "2": Math.max(0, dok2),
      "3": Math.max(0, dok3),
      "4": Math.max(0, dok4),
    };
  };

  // Helper function to distribute points per type to reach total
  const distributePoints = (totalPoints, questionTypes) => {
    // Base ratios: ER=4, SA=2, MC=TF=Matching=1
    const baseRatios = {
      multiple_choice: 1,
      short_answer: 2,
      true_false: 1,
      matching: 1,
      extended_response: 4,
    };

    // Get active types (count > 0)
    const activeTypes = Object.entries(questionTypes).filter(([, count]) => count > 0);
    if (activeTypes.length === 0) return { ...baseRatios };

    // Calculate weighted sum with base ratios
    let weightedSum = 0;
    activeTypes.forEach(([type, count]) => {
      weightedSum += count * (baseRatios[type] || 1);
    });

    if (weightedSum === 0) return { ...baseRatios };

    // Scale factor to reach target total
    const scale = totalPoints / weightedSum;

    // Apply scale and floor (start low, then add)
    const newPoints = { ...baseRatios };
    activeTypes.forEach(([type]) => {
      newPoints[type] = Math.max(1, Math.floor(baseRatios[type] * scale));
    });

    // Calculate current total
    const calcTotal = () => {
      let total = 0;
      activeTypes.forEach(([type, count]) => {
        total += count * newPoints[type];
      });
      return total;
    };

    // Iteratively adjust to hit target
    // Sort by ratio (highest first) - prefer adding to complex question types
    const sortedByRatio = [...activeTypes].sort((a, b) => (baseRatios[b[0]] || 1) - (baseRatios[a[0]] || 1));

    let iterations = 0;
    while (calcTotal() < totalPoints && iterations < 100) {
      // Add 1 point to the type that gets us closest to target
      let bestType = null;
      let bestDiff = Infinity;

      for (const [type, count] of sortedByRatio) {
        const newTotal = calcTotal() + count;
        const diff = Math.abs(totalPoints - newTotal);
        if (diff < bestDiff && newTotal <= totalPoints) {
          bestDiff = diff;
          bestType = type;
        }
      }

      if (bestType) {
        newPoints[bestType]++;
      } else {
        // Can't get closer without overshooting, pick smallest increment
        const [smallestType] = [...activeTypes].sort((a, b) => a[1] - b[1]);
        if (smallestType) newPoints[smallestType[0]]++;
        break;
      }
      iterations++;
    }

    return newPoints;
  };
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


  // Handle Stripe redirect URL params (?billing=success or ?billing=cancel)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const billingParam = params.get("billing");
    if (billingParam === "success") {
      addToast("Subscription activated successfully!", "success");
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (billingParam === "cancel") {
      addToast("Checkout cancelled", "info");
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    } else if (billingParam === "portal-return") {
      setActiveTab("settings");
      setSettingsTab("billing");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  // Auto-save Builder assignment when it changes (debounced)
  useEffect(() => {
    if (!settingsLoaded) return;
    if (!assignment.title) return; // Don't save assignments without a title
    if (isLoadingAssignment) return; // Don't save while loading an assignment
    // Skip auto-save right after loading — data is already on disk
    if (skipAutoSaveRef.current) {
      skipAutoSaveRef.current = false;
      return;
    }

    const saveTimeout = setTimeout(async () => {
      // Double-check we're not in the middle of loading
      if (isLoadingAssignment) return;

      try {
        let dataToSave = { ...assignment, importedDoc };
        // Compare sanitized names to detect real renames (not just special-char differences)
        // Backend sanitizes titles to filenames by keeping only [a-zA-Z0-9 \-_]
        const sanitizeForFilename = (s) => s.replace(/[^a-zA-Z0-9 \-_]/g, '').trim();
        const isRename =
          loadedAssignmentName && sanitizeForFilename(loadedAssignmentName) !== sanitizeForFilename(assignment.title);

        // If title changed from a previously loaded assignment, add old name to aliases
        if (isRename) {
          const currentAliases = assignment.aliases || [];
          if (!currentAliases.includes(loadedAssignmentName)) {
            dataToSave.aliases = [...currentAliases, loadedAssignmentName];
            // Also update local state with new alias
            setAssignment((prev) => ({ ...prev, aliases: dataToSave.aliases }));
          }
        }

        const saveResult = await api.saveAssignmentConfig(dataToSave);

        // Only proceed if save was successful
        if (saveResult.status === "saved") {
          // If renamed, delete the old assignment file (alias is preserved in new file)
          if (isRename) {
            try {
              await api.deleteAssignment(loadedAssignmentName);
              console.log(`Renamed assignment: "${loadedAssignmentName}" → "${assignment.title}" (old name saved as alias)`);
            } catch (deleteErr) {
              console.error("Failed to delete old assignment file:", deleteErr);
              // Don't fail the whole operation if delete fails
            }
          }

          if (isRename) {
            // Full list refresh on rename (list structure changed)
            const list = await api.listAssignments();
            if (list.assignments) setSavedAssignments(list.assignments);
            if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
          } else {
            // Normal save — update this card's data locally without full refresh
            const cardKey = sanitizeForFilename(assignment.title);
            setSavedAssignmentData(prev => ({
              ...prev,
              [cardKey]: {
                ...(prev[cardKey] || {}),
                rubricType: assignment.rubricType || 'standard',
                completionOnly: assignment.completionOnly || false,
                countsTowardsGrade: assignment.countsTowardsGrade !== false,
                title: assignment.title,
                aliases: assignment.aliases || [],
              }
            }));
          }
          // Update loaded assignment name to reflect current title
          setLoadedAssignmentName(assignment.title);
        } else if (saveResult.error) {
          console.error("Failed to save assignment:", saveResult.error);
          addToast("Failed to save assignment: " + saveResult.error, "error");
        }
      } catch (error) {
        console.error("Failed to auto-save assignment:", error);
      }
    }, 1500); // Debounce 1.5 seconds (slightly longer for assignment changes)

    return () => clearTimeout(saveTimeout);
  }, [assignment, importedDoc, settingsLoaded, loadedAssignmentName, isLoadingAssignment]);

  // Fetch status once on mount (catch in-progress grading on page refresh)
  useEffect(() => {
    api.getStatus().then(setStatus).catch(() => {});
  }, []);

  // Poll status while grading. Closes audit MINOR (Codex full-codebase
  // audit 2026-05-06): the previous fixed-500ms interval amplified
  // multi-tab load (~2 req/sec/tab × N tabs) and server cost grew
  // linearly with idle teachers staring at the grading screen. Now
  // the cadence backs off exponentially (500ms → 1s → 2s → 4s → 8s)
  // while grading is steady, and snaps back to 500ms whenever the
  // server reports activity (log line, result, or progress tick) so
  // the UI stays responsive when work IS happening. Tab visibility
  // throttling further reduces traffic when the tab is hidden.
  useEffect(() => {
    if (!status.is_running) return;
    let cancelled = false;
    let timeoutId = null;
    let generation = 0;          // monotonic; bumped by visibilitychange to invalidate stale ticks
    let currentDelay = 500;
    const MIN_DELAY = 500;
    const MAX_DELAY = 8000;
    const HIDDEN_DELAY = 15000;
    let lastLogLen = (status.log && status.log.length) || 0;
    let lastResultsLen = (status.results && status.results.length) || 0;
    let lastProgress = status.progress || 0;

    const tick = async (myGen) => {
      if (cancelled) return;
      // Round-2 Codex LOW fold: if a visibility event bumped the
      // generation while this tick was queued OR awaiting, this stale
      // chain MUST NOT schedule its own next tick. The fresh chain
      // started by the visibility handler owns scheduling now.
      if (myGen !== generation) return;
      try {
        const data = await api.getStatus();
        if (cancelled || myGen !== generation) return;
        setStatus(data);
        const newLogLen = (data.log && data.log.length) || 0;
        const newResultsLen = (data.results && data.results.length) || 0;
        const newProgress = data.progress || 0;
        const sawActivity = (
          newLogLen > lastLogLen ||
          newResultsLen > lastResultsLen ||
          newProgress > lastProgress
        );
        lastLogLen = newLogLen;
        lastResultsLen = newResultsLen;
        lastProgress = newProgress;
        if (!data.is_running) {
          // Grading finished — let the effect cleanup re-trigger via
          // the `is_running` dep change.
          return;
        }
        // Activity → snap to MIN_DELAY. Idle → exponential backoff.
        if (sawActivity) {
          currentDelay = MIN_DELAY;
        } else {
          currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
        }
      } catch (error) {
        // Round-3 Codex LOW fold: stale rejected polls (myGen !==
        // generation) must NOT mutate the shared currentDelay or they
        // would partially undo the visibility-driven snap-back from
        // the new chain.
        if (cancelled || myGen !== generation) return;
        console.error("Status poll error:", error);
        // Network errors → also back off so we don't hammer a flaky API.
        currentDelay = Math.min(currentDelay * 2, MAX_DELAY);
      }
      if (cancelled || myGen !== generation) return;
      const nextDelay = (typeof document !== 'undefined' && document.hidden)
        ? Math.max(currentDelay, HIDDEN_DELAY)
        : currentDelay;
      timeoutId = setTimeout(() => tick(myGen), nextDelay);
    };

    // Round-1 Codex LOW fold (revised in round-2): when the tab becomes
    // visible again, pull the next tick forward so the user doesn't
    // see stale status for up to 15s. We bump `generation` so any
    // in-flight or queued tick from the prior chain self-cancels its
    // re-scheduling — preventing duplicate parallel polling chains.
    const onVisibilityChange = () => {
      if (cancelled) return;
      if (typeof document !== 'undefined' && !document.hidden) {
        currentDelay = MIN_DELAY;
        if (timeoutId) clearTimeout(timeoutId);
        // If a tick is in-flight, it'll see myGen !== generation and
        // bail out of re-scheduling. We schedule the new chain now;
        // even if both fire `getStatus` once, the stale chain stops
        // after its current tick instead of forking a parallel loop.
        generation += 1;
        const myGen = generation;
        timeoutId = setTimeout(() => tick(myGen), 0);
      }
    };
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange);
    }

    const initialGen = generation;
    timeoutId = setTimeout(() => tick(initialGen), currentDelay);
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibilityChange);
      }
    };
  }, [status.is_running]);

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

  // Persistent grading toast
  const gradingToastId = useRef(null);
  const wasGrading = useRef(false);

  useEffect(() => {
    if (status.is_running && !wasGrading.current) {
      // Grading just started - show persistent toast
      wasGrading.current = true;
      gradingToastId.current = addToast(
        `Grading in progress... ${status.current_file || ''}`,
        "info",
        0 // persistent
      );
    } else if (status.is_running && gradingToastId.current) {
      // Update the toast message with current file
      setToasts(prev => prev.map(t =>
        t.id === gradingToastId.current
          ? { ...t, message: `Grading: ${status.current_file || 'Processing...'}` }
          : t
      ));
    } else if (!status.is_running && wasGrading.current) {
      // Track grading completion
      if (!isLocalhost && status.results) {
        phTrack('grading_completed', {
          result_count: status.results.length,
          cost: status.session_cost?.total_cost || 0,
          cost_limit_hit: !!status.cost_limit_hit,
        });
      }
      // Grading just finished - remove persistent toast
      wasGrading.current = false;
      if (gradingToastId.current) {
        removeToast(gradingToastId.current);
        gradingToastId.current = null;
      }
      if (status.cost_limit_hit) {
        addToast("Grading auto-stopped: cost limit of $" + (config.cost_limit_per_session || 0).toFixed(2) + " reached. Progress saved.", "warning", 8000);
      }
      if (status.results && status.results.length > 0) {
        const costStr = status.session_cost?.total_cost > 0 ? ` (API cost: $${status.session_cost.total_cost.toFixed(4)})` : "";
        addToast(`Grading complete! ${status.results.length} assignments graded.${costStr}`, "success");
        // Resubmission summary notification
        const resubCount = status.results.filter(r => r.is_resubmission).length;
        if (resubCount > 0) {
          const keptCount = status.results.filter(r => r.is_resubmission && r.kept_higher).length;
          const improvedCount = resubCount - keptCount;
          let msg = resubCount + " resubmission(s) detected.";
          if (improvedCount > 0) msg += " " + improvedCount + " improved.";
          if (keptCount > 0) msg += " " + keptCount + " kept original (higher) grade.";
          addToast(msg, "info", 8000);
        }
      }
    }
  }, [status.is_running, status.current_file, status.results]);

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

  // Auto-save edited results to backend (debounced)
  useEffect(() => {
    if (!editedResults.length) return;

    // Find results that have been edited
    const editedItems = editedResults.filter((r) => r.edited && r.filename);
    if (!editedItems.length) return;

    const saveTimeout = setTimeout(async () => {
      for (const item of editedItems) {
        try {
          await api.updateResult(item.filename, {
            score: item.score,
            letter_grade: item.letter_grade,
            feedback: item.feedback,
          });
          // Mark as saved by clearing the edited flag
          setEditedResults((prev) =>
            prev.map((r) =>
              r.filename === item.filename ? { ...r, edited: false } : r
            )
          );
        } catch (error) {
          console.error("Failed to save result:", error);
        }
      }
    }, 1000); // 1 second debounce

    return () => clearTimeout(saveTimeout);
  }, [editedResults]);

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
  const handleDocImport = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImportedDoc({ text: "", html: "", filename: file.name, loading: true });
    try {
      const data = await api.parseDocument(file);
      if (data.error) {
        addToast("Error parsing document: " + data.error, "error");
        setImportedDoc({ text: "", html: "", filename: "", loading: false });
      } else {
        // Use filename as title (cleaner than document metadata which is often generic)
        const newTitle = file.name
          .replace(/\.(docx|pdf|doc|txt)$/i, "")
          .replace(/_/g, " ")
          .replace(/\s+/g, " ")
          .trim();

        // Sanitize title the same way backend does for filename comparison
        const safeTitle = newTitle.replace(/[^a-zA-Z0-9 \-_]/g, "").trim();

        // Check if this assignment already exists (compare sanitized names)
        const existingName = savedAssignments.find(
          (name) => name.toLowerCase() === safeTitle.toLowerCase(),
        );

        if (existingName) {
          const confirmLoad = window.confirm(
            `An assignment named "${existingName}" already exists.\n\nClick OK to load existing settings with this document, or Cancel to skip.`,
          );
          if (confirmLoad) {
            // Load existing assignment config but use the NEW document text
            try {
              const existingData = await api.loadAssignment(existingName);
              if (existingData.assignment) {
                setAssignment({
                  title: existingData.assignment.title || "",
                  subject: existingData.assignment.subject || "Social Studies",
                  totalPoints: existingData.assignment.totalPoints || 100,
                  instructions: existingData.assignment.instructions || "",
                  questions: existingData.assignment.questions || [],
                  customMarkers: existingData.assignment.customMarkers || [],
                  excludeMarkers: existingData.assignment.excludeMarkers || [],
                  gradingNotes: existingData.assignment.gradingNotes || "",
                  responseSections:
                    existingData.assignment.responseSections || [],
                });
                setLoadedAssignmentName(existingName);
                // Use the freshly parsed document text, not the (possibly empty) saved one
                setImportedDoc({
                  text: data.text || "",
                  html: data.html || "",
                  filename: file.name,
                  loading: false,
                });
                // Open doc editor with highlights from existing markers
                let docHtml = data.html || "";
                const loadedMarkers = existingData.assignment.customMarkers || [];
                const loadedExcludes = existingData.assignment.excludeMarkers || [];
                if (loadedMarkers.length > 0 || loadedExcludes.length > 0) {
                  let cleanHtml = removeAllHighlightsFromHtml(docHtml);
                  docHtml = applyAllHighlights(cleanHtml, loadedMarkers, loadedExcludes);
                }
                setDocEditorModal({
                  show: true,
                  editedHtml: docHtml,
                  viewMode: "formatted",
                });
              }
            } catch (loadErr) {
              console.error("Failed to load existing assignment:", loadErr);
            }
            return;
          }
          // User chose not to load existing - cancel the import
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
          return;
        }

        setImportedDoc({
          text: data.text || "",
          html: data.html || "",
          filename: file.name,
          loading: false,
        });
        setLoadedAssignmentName("");
        setDocEditorModal({
          show: true,
          editedHtml: data.html || "",
          viewMode: "formatted",
        });
        if (!assignment.title) {
          setAssignment({ ...assignment, title: newTitle });
        }
      }
    } catch (err) {
      addToast("Error: " + err.message, "error");
      setImportedDoc({ text: "", html: "", filename: "", loading: false });
    }
  };

  const openDocEditor = () => {
    if (importedDoc.text || importedDoc.html) {
      let html = importedDoc.html;
      // Re-generate HTML from text if current HTML has no real formatting
      const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(html);
      if (!hasFormatting && importedDoc.text) {
        html = textToRichHtml(importedDoc.text);
        setImportedDoc({ ...importedDoc, html });
      }

      // If no markers but HTML has highlights, clean orphaned highlights
      const hasHighlights = html && html.includes('data-marker-id=');
      const hasMarkers = (assignment.customMarkers || []).length > 0;

      const hasExcludeMarkers = (assignment.excludeMarkers || []).length > 0;
      if (hasHighlights && !hasMarkers && !hasExcludeMarkers) {
        html = removeAllHighlightsFromHtml(html);
        // Also update importedDoc to persist the cleanup
        setImportedDoc({ ...importedDoc, html });
      }

      setDocEditorModal({
        show: true,
        editedHtml: html,
        viewMode: "formatted",
      });
    }
  };

  const addSelectedAsMarker = () => {
    let text = "";
    try {
      if (docHtmlRef.current?.contentDocument) {
        const sel = docHtmlRef.current.contentDocument.getSelection();
        if (sel) text = sel.toString().trim();
      }
    } catch (e) {}
    if (!text) {
      const sel = window.getSelection();
      text = sel ? sel.toString().trim() : "";
    }
    if (text && text.length > 2 && text.length < 2000) {
      if (highlighterMode === "start") {
        // Adding a new start marker
        const exists = (assignment.customMarkers || []).some(m =>
          typeof m === 'string' ? m === text : m.start === text
        );
        if (!exists) {
          const newMarkers = [...(assignment.customMarkers || []), text];
          const markerIndex = newMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.start,
            `start-${markerIndex}`
          );

          setAssignment({ ...assignment, customMarkers: newMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Start marker added (green)", "success");
        }
      } else if (highlighterMode === "exclude") {
        // Adding an exclude marker - section to NOT grade
        const exists = (assignment.excludeMarkers || []).some(m => m === text);
        if (!exists) {
          const newExcludeMarkers = [...(assignment.excludeMarkers || []), text];
          const excludeIndex = newExcludeMarkers.length - 1;

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.exclude,
            `exclude-${excludeIndex}`
          );

          setAssignment({ ...assignment, excludeMarkers: newExcludeMarkers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("Exclude marker added (orange) - this section will NOT be graded", "success");
        } else {
          addToast("This section is already marked as excluded", "warning");
        }
      } else {
        // Adding an end marker - attach to the last marker that doesn't have one
        const markers = [...(assignment.customMarkers || [])];
        const lastWithoutEnd = markers.findIndex((m, i) => {
          // Find first marker without an end marker
          return typeof m === 'string' || !m.end;
        });

        if (lastWithoutEnd >= 0) {
          const startText = getMarkerText(markers[lastWithoutEnd]);
          markers[lastWithoutEnd] = { start: startText, end: text };

          // Apply highlight to HTML
          const newHtml = highlightTextInHtml(
            docEditorModal.editedHtml,
            text,
            HIGHLIGHT_COLORS.end,
            `end-${lastWithoutEnd}`
          );

          setAssignment({ ...assignment, customMarkers: markers });
          setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
          addToast("End marker added (red)", "success");
        } else {
          addToast("Add a start marker first", "warning");
        }
      }
    } else if (text.length <= 2) {
      addToast("Please select more text (at least 3 characters)", "warning");
    } else if (text.length >= 2000) {
      addToast(
        "Selection too long. Please select less text (under 2000 characters)",
        "warning",
      );
    }
  };

  // Helper to get marker text (handles both string and object formats)
  const getMarkerText = (marker) => {
    return typeof marker === 'string' ? marker : marker.start;
  };

  // Helper to get end marker (if exists)
  const getEndMarker = (marker) => {
    return typeof marker === 'object' ? marker.end : null;
  };

  // Get marker points (default 10 if not specified)
  const getMarkerPoints = (marker) => {
    if (typeof marker === 'string') return 10;
    return marker.points || 10;
  };

  // Get marker type (default "written")
  const getMarkerType = (marker) => {
    if (typeof marker === 'string') return 'written';
    return marker.type || 'written';
  };

  // Calculate total points from markers
  const calculateTotalPoints = (markers, effortPoints = 15) => {
    const markerTotal = (markers || []).reduce((sum, m) => sum + getMarkerPoints(m), 0);
    return markerTotal + effortPoints;
  };

  // Convert old string marker to new format
  const normalizeMarker = (marker) => {
    if (typeof marker === 'string') {
      return { start: marker, points: 10, type: 'written' };
    }
    if (marker.start && !marker.points) {
      return { ...marker, points: 10, type: marker.type || 'written' };
    }
    return marker;
  };

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

  const removeMarker = (marker, markerIndex) => {
    const markerText = getMarkerText(marker);

    // Remove ALL highlights and re-apply remaining ones (avoids index mismatch issues)
    let cleanHtml = removeAllHighlightsFromHtml(docEditorModal.editedHtml);

    // Filter out the removed marker
    const remainingMarkers = (assignment.customMarkers || []).filter(
      (m) => getMarkerText(m) !== markerText,
    );

    // Re-apply highlights for remaining markers AND exclude markers
    const newHtml = applyAllHighlights(cleanHtml, remainingMarkers, assignment.excludeMarkers);

    setAssignment({
      ...assignment,
      customMarkers: remainingMarkers,
    });

    // Update BOTH docEditorModal AND importedDoc
    setDocEditorModal({ ...docEditorModal, editedHtml: newHtml });
    setImportedDoc({ ...importedDoc, html: newHtml });
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
  const normalizeText = (str) => {
    if (!str) return str;
    return str
      .replace(/[\u2018\u2019\u201A\u201B]/g, "'")  // Smart single quotes to straight
      .replace(/[\u201C\u201D\u201E\u201F]/g, '"')  // Smart double quotes to straight
      .replace(/[\u2013\u2014]/g, '-')              // En-dash and em-dash to hyphen
      .replace(/\u2026/g, '...')                    // Ellipsis to dots
      .replace(/\u00A0/g, ' ');                     // Non-breaking space to regular space
  };

  // Build a mapping from plain text positions to HTML positions
  // Entity-aware: &amp; maps to a single plain text character (&)
  const buildTextToHtmlMap = (html) => {
    const map = []; // map[plainTextIndex] = htmlIndex
    let inTag = false;
    let plainIndex = 0;

    for (let i = 0; i < html.length; i++) {
      if (html[i] === '<') {
        inTag = true;
      } else if (html[i] === '>') {
        inTag = false;
      } else if (!inTag) {
        // HTML entity (e.g., &amp; &lt; &#123;) → one plain text char
        if (html[i] === '&') {
          const semiPos = html.indexOf(';', i);
          if (semiPos !== -1 && semiPos - i <= 8) {
            map[plainIndex] = i;
            plainIndex++;
            i = semiPos; // skip to ';' (loop will i++ past it)
            continue;
          }
        }
        map[plainIndex] = i;
        plainIndex++;
      }
    }
    map[plainIndex] = html.length; // End marker
    return map;
  };

  // Extract plain text from HTML (strips tags and decodes entities)
  const htmlToPlainText = (html) => {
    let text = html.replace(/<[^>]*>/g, '');
    // Decode common HTML entities so search text matches
    text = text
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .replace(/&#39;|&apos;/g, "'")
      .replace(/&nbsp;/g, ' ')
      .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code)))
      .replace(/&#x([0-9a-fA-F]+);/g, (_, code) => String.fromCharCode(parseInt(code, 16)));
    return text;
  };

  // Highlight text in HTML with a colored span (handles multi-line markers)
  const highlightTextInHtml = (html, text, color, markerId, searchAfterPos = 0) => {
    if (!text || !html) return html;

    // Check if already highlighted
    if (html.includes(`data-marker-id="${markerId}"`)) {
      return html; // Already highlighted
    }

    // If text spans multiple lines, highlight each line separately
    // This handles cross-paragraph selections where a single span wrapper breaks
    // Split on newlines, carriage returns, or multiple spaces (browsers vary)
    const lines = text.split(/[\n\r]+/).map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length > 1) {
      let result = html;
      let currentOffset = searchAfterPos;
      for (let li = 0; li < lines.length; li++) {
        // Find where this line matches BEFORE highlighting (to track position)
        const plainBefore = htmlToPlainText(result);
        const normalizedBefore = normalizeText(plainBefore).toLowerCase();
        const lineNorm = normalizeText(lines[li]).replace(/\s+/g, ' ').trim().toLowerCase();
        const linePos = normalizedBefore.indexOf(lineNorm, currentOffset);

        result = highlightTextInHtml(result, lines[li], color, `${markerId}-line${li}`, currentOffset);

        // Advance offset past this match so next line searches further in the document
        if (linePos !== -1) {
          currentOffset = linePos + lineNorm.length;
        }
      }
      return result;
    }

    // Normalize the search text
    const normalizedSearchText = normalizeText(text).replace(/\s+/g, ' ').trim();

    // Extract plain text from HTML and normalize it
    const plainText = htmlToPlainText(html);
    const normalizedPlainText = normalizeText(plainText);

    // Build mapping from plain text positions to HTML positions
    const textToHtmlMap = buildTextToHtmlMap(html);

    // Try to find the normalized search text in normalized plain text
    // Use case-insensitive search, starting from searchAfterPos
    const searchLower = normalizedSearchText.toLowerCase();
    const plainLower = normalizedPlainText.toLowerCase();

    let matchStart = plainLower.indexOf(searchLower, searchAfterPos);

    // If exact match fails, try matching with flexible whitespace
    if (matchStart === -1) {
      // Create regex that allows any whitespace between words
      const words = normalizedSearchText.split(/\s+/).filter(w => w.length > 0);
      if (words.length > 0) {
        const flexPattern = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s+');
        const flexRegex = new RegExp(flexPattern, 'gi');
        let flexMatch;
        while ((flexMatch = flexRegex.exec(normalizedPlainText)) !== null) {
          if (flexMatch.index >= searchAfterPos) {
            matchStart = flexMatch.index;
            break;
          }
        }
      }
    }

    if (matchStart !== -1) {
      // Find match end in plain text
      const matchEnd = matchStart + normalizedSearchText.length;

      // Map to HTML positions
      const htmlStart = textToHtmlMap[matchStart];
      // Find the HTML end position - need to find where the last matched character ends
      let htmlEnd = textToHtmlMap[matchEnd] || html.length;

      // Adjust htmlEnd to include any trailing content before the next tag
      // This ensures we capture the full matched text even with length differences
      const remainingPlain = normalizedPlainText.substring(matchStart, matchEnd);
      let plainIdx = matchStart;
      let htmlIdx = htmlStart;

      // Walk through character by character to find exact HTML end
      while (plainIdx < matchEnd && htmlIdx < html.length) {
        if (html[htmlIdx] === '<') {
          // Skip HTML tag
          while (htmlIdx < html.length && html[htmlIdx] !== '>') htmlIdx++;
          htmlIdx++; // Skip '>'
        } else if (html[htmlIdx] === '&') {
          // HTML entity — skip to closing ';'
          const semiPos = html.indexOf(';', htmlIdx);
          if (semiPos !== -1 && semiPos - htmlIdx <= 8) {
            htmlIdx = semiPos + 1;
          } else {
            htmlIdx++;
          }
          plainIdx++;
        } else {
          plainIdx++;
          htmlIdx++;
        }
      }
      htmlEnd = htmlIdx;

      // Extract the HTML content to wrap
      const matchedHtml = html.substring(htmlStart, htmlEnd);

      // If matched range crosses block elements, extract the text content of each
      // block and highlight them individually (a span can't validly wrap across <p> tags)
      if (/<\/?(?:p|div|h[1-6]|li|br)\b/i.test(matchedHtml)) {
        // Extract individual text segments from the matched HTML
        const textSegments = matchedHtml
          .replace(/<[^>]*>/g, '\n')  // Replace tags with newlines
          .split('\n')
          .map(s => s.trim())
          .filter(s => s.length > 0);

        if (textSegments.length > 1) {
          // Re-highlight each text segment individually in the full HTML
          let result = html;
          for (let si = 0; si < textSegments.length; si++) {
            result = highlightTextInHtml(result, textSegments[si], color, `${markerId}-seg${si}`);
          }
          return result;
        }
      }

      // Single element — wrap normally
      const highlightSpan = `<span data-marker-id="${markerId}" style="background:${color.bg};border-bottom:2px solid ${color.border};padding:2px 0;">${matchedHtml}</span>`;

      return html.substring(0, htmlStart) + highlightSpan + html.substring(htmlEnd);
    }

    console.log('Highlight match failed for:', text.substring(0, 50) + '...');
    console.log('Searching for:', searchLower.substring(0, 80));
    console.log('Plain text excerpt:', plainLower.substring(0, 300));
    return html; // No match found
  };

  // Remove highlight from HTML by marker ID
  const removeHighlightFromHtml = (html, markerId) => {
    if (!html) return html;
    // Remove the span but keep the inner content (handles nested tags)
    // Match opening span with marker ID, then capture everything until closing span
    const regex = new RegExp(`<span[^>]*data-marker-id="${markerId}"[^>]*>(.*?)</span>`, 'gis');
    return html.replace(regex, '$1');
  };

  // Convert plain text (from AI-generated assignments) to rich HTML matching docx-parsed format
  const textToRichHtml = (text) => {
    const style = '<style>body{font-family:Georgia,serif;line-height:1.6}table{border-collapse:collapse;width:100%;margin:15px 0}td,th{border:1px solid #ccc;padding:8px 12px;text-align:left}th{background:#f5f5f5;font-weight:bold}p{margin:10px 0}h1,h2,h3{margin:20px 0 10px 0}</style>';
    const lines = text.split('\n');
    const parts = [style];
    let qNum = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const escaped = line.replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const trimmed = escaped.trim();
      if (!trimmed) continue;
      // First line = title
      if (i === 0) { parts.push('<h1><strong>' + escaped + '</strong></h1>'); continue; }
      // Name/Date/Period
      if (/^(Name|Date|Period):/.test(trimmed)) {
        const [label, ...rest] = escaped.split(':');
        parts.push('<p><strong>' + label + ': </strong>' + rest.join(':') + '</p>');
        continue;
      }
      // ALL-CAPS = section heading
      if (trimmed === trimmed.toUpperCase() && /[A-Z]/.test(trimmed) && !/^_+$/.test(trimmed)) {
        parts.push('<h2><strong>' + escaped + '</strong></h2>');
        continue;
      }
      // Numbered question (N) ...)
      const qMatch = trimmed.match(/^(\d+)\)\s+(.+)/);
      if (qMatch) {
        qNum++;
        parts.push(
          '<table><tr><td><p>[GRAIDER:QUESTION:' + qNum + ']<strong>  ' + escaped + '</strong></p></td></tr>' +
          '<tr><td><p><strong>Your Answer:</strong></p><p><em>Type your answer here...</em></p></td></tr></table>'
        );
        // Skip following Response/Answer/underscore lines (they're replaced by the table)
        while (i + 1 < lines.length && /^(Response|Answer|_{5,})/.test(lines[i + 1].trim())) i++;
        continue;
      }
      // Vocab term (word: ___)
      if (/^.+:\s*_{5,}/.test(trimmed)) {
        const term = escaped.split(':')[0];
        parts.push('<table><tr><td><p><strong>' + term + ':</strong> ' + '_'.repeat(60) + '</p></td></tr></table>');
        continue;
      }
      // Skip standalone underscore lines
      if (/^_+$/.test(trimmed)) continue;
      // Default
      parts.push('<p>' + escaped + '</p>');
    }
    return parts.join('\n');
  };

  // Remove ALL marker highlights from HTML (for clean reset)
  const removeAllHighlightsFromHtml = (html) => {
    if (!html) return html;
    // Remove all spans with data-marker-id attribute
    return html.replace(/<span[^>]*data-marker-id="[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
  };

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

  const saveAssignmentConfig = async () => {
    if (!assignment.title) {
      addToast("Please enter a title", "warning");
      return;
    }
    try {
      // Use editedHtml if available (preserves marker highlights)
      const docToSave = docEditorModal.editedHtml
        ? { ...importedDoc, html: docEditorModal.editedHtml }
        : importedDoc;
      const dataToSave = { ...assignment, importedDoc: docToSave };
      await api.saveAssignmentConfig(dataToSave);
      addToast("Assignment saved!", "success");
      setLoadedAssignmentName(assignment.title);
      const list = await api.listAssignments();
      if (list.assignments) setSavedAssignments(list.assignments);
      if (list.assignmentData) setSavedAssignmentData(list.assignmentData);
    } catch (e) {
      addToast("Error saving: " + e.message, "error");
    }
  };

  const loadAssignment = async (name) => {
    try {
      setIsLoadingAssignment(true); // Prevent auto-save during load
      skipAutoSaveRef.current = true; // Don't auto-save data we just loaded
      const data = await api.loadAssignment(name);
      if (data.assignment) {
        // Set importedDoc FIRST to prevent race condition
        if (data.assignment.importedDoc) {
          let loadedHtml = data.assignment.importedDoc.html || "";
          // Re-generate HTML from text if current HTML has no real formatting (just <p> tags)
          const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(loadedHtml);
          if (!hasFormatting && data.assignment.importedDoc.text) {
            loadedHtml = textToRichHtml(data.assignment.importedDoc.text);
            data.assignment.importedDoc.html = loadedHtml;
          }
          // Clean orphaned exclude marker spans
          const loadedExcludes = data.assignment.excludeMarkers || [];
          if (loadedHtml.includes('data-marker-id="exclude-')) {
            if (loadedExcludes.length === 0) {
              // No exclude markers at all — strip all exclude spans
              while (loadedHtml.includes('data-marker-id="exclude-')) {
                loadedHtml = loadedHtml.replace(/<span[^>]*data-marker-id="exclude-[^"]*"[^>]*>(.*?)<\/span>/gis, '$1');
              }
            } else {
              // Has some exclude markers — strip any orphaned spans with index >= array length
              const excludeIdRegex = /data-marker-id="exclude-(\d+)(?:-[^"]*)?"/g;
              let idMatch;
              const foundIndices = new Set();
              while ((idMatch = excludeIdRegex.exec(loadedHtml)) !== null) {
                foundIndices.add(parseInt(idMatch[1]));
              }
              for (const idx of foundIndices) {
                if (idx >= loadedExcludes.length) {
                  const orphanRegex = new RegExp(`<span[^>]*data-marker-id="exclude-${idx}(?:-[^"]*)?\"[^>]*>(.*?)<\\/span>`, 'gis');
                  while (orphanRegex.test(loadedHtml)) {
                    orphanRegex.lastIndex = 0;
                    loadedHtml = loadedHtml.replace(orphanRegex, '$1');
                  }
                }
              }
            }
          }
          const cleanDoc = { ...data.assignment.importedDoc, html: loadedHtml };
          setImportedDoc(cleanDoc);
          // Also restore the highlighted HTML to the editor
          if (loadedHtml) {
            setDocEditorModal(prev => ({
              ...prev,
              editedHtml: loadedHtml
            }));
          }
        } else {
          setImportedDoc({ text: "", html: "", filename: "", loading: false });
        }
        // Load markers and section point settings
        const useSectionPts = data.assignment.useSectionPoints || false;
        const effortPts = data.assignment.effortPoints ?? 15;
        let markers = data.assignment.customMarkers || [];

        // Only migrate markers if section points is enabled
        if (useSectionPts && markers.length > 0) {
          // Check if markers need migration (any string markers or markers without points)
          const needsMigration = markers.some(m =>
            typeof m === 'string' || (typeof m === 'object' && !m.points)
          );

          if (needsMigration) {
            // Distribute remaining points (100 - effort) evenly among markers
            const availablePoints = 100 - effortPts;
            const pointsPerMarker = Math.floor(availablePoints / markers.length);
            const remainder = availablePoints % markers.length;

            markers = markers.map((m, i) => {
              const markerText = typeof m === 'string' ? m : m.start;
              const markerType = typeof m === 'object' ? (m.type || 'written') : 'written';
              // Give first marker any remainder points
              const pts = pointsPerMarker + (i === 0 ? remainder : 0);
              return { start: markerText, points: pts, type: markerType };
            });
          }
        }

        setAssignment({
          title: data.assignment.title || "",
          subject: data.assignment.subject || "Social Studies",
          totalPoints: data.assignment.totalPoints || 100,
          instructions: data.assignment.instructions || "",
          questions: data.assignment.questions || [],
          customMarkers: markers,
          excludeMarkers: data.assignment.excludeMarkers || [],
          gradingNotes: data.assignment.gradingNotes || "",
          responseSections: data.assignment.responseSections || [],
          aliases: data.assignment.aliases || [],
          completionOnly: data.assignment.completionOnly || false,
          rubricType: data.assignment.rubricType || "standard",
          customRubric: data.assignment.customRubric || null,
          useSectionPoints: useSectionPts,
          sectionTemplate: data.assignment.sectionTemplate || "Custom",
          effortPoints: effortPts,
          dueDate: data.assignment.dueDate || "",
          latePenalty: {
            enabled: false,
            type: "points_per_day",
            amount: 10,
            tiers: [
              { daysLate: 1, penalty: 10 },
              { daysLate: 3, penalty: 25 },
              { daysLate: 7, penalty: 50 },
            ],
            maxPenalty: 50,
            gracePeriodHours: 0,
            ...(data.assignment.latePenalty || {}),
          },
        });
        setLoadedAssignmentName(name);
      }
      // Small delay before allowing auto-save again
      setTimeout(() => setIsLoadingAssignment(false), 500);
    } catch (e) {
      setIsLoadingAssignment(false);
      addToast("Error loading: " + e.message, "error");
    }
  };

  const deleteAssignment = async (name) => {
    if (!confirm(`Delete "${name}"?\n\nThis will permanently remove the assignment config, grading notes, answer key, and all grading setup. This cannot be undone.`)) return;
    try {
      await api.deleteAssignment(name);
      setSavedAssignments(savedAssignments.filter((a) => a !== name));
      addToast(`"${name}" deleted`, "success");
      if (loadedAssignmentName === name) {
        setAssignment({
          title: "",
          subject: "Social Studies",
          totalPoints: 100,
          instructions: "",
          questions: [],
          customMarkers: [],
          excludeMarkers: [],
          gradingNotes: "",
          responseSections: [],
          aliases: [],
          completionOnly: false,
          rubricType: "standard",
          customRubric: null,
          useSectionPoints: false,
          sectionTemplate: "Custom",
          effortPoints: 15,
          dueDate: "",
          latePenalty: {
            enabled: false,
            type: "points_per_day",
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
        setLoadedAssignmentName("");
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  const exportAssignment = async (format) => {
    try {
      // Convert customMarkers to questions format for backend
      const exportData = { ...assignment };
      if ((!exportData.questions || exportData.questions.length === 0) && exportData.customMarkers?.length > 0) {
        exportData.questions = exportData.customMarkers.map((m, i) => ({
          marker: (typeof m === 'string' ? m : m.start) || ('Section ' + (i + 1)),
          prompt: '',
          points: typeof m === 'object' ? (m.points || 10) : 10,
          type: typeof m === 'object' ? (m.type || 'written') : 'written',
        }));
      }
      const data = await api.exportAssignment({ assignment: exportData, format });
      if (data.error) addToast("Error: " + data.error, "error");
      else addToast("Assignment exported!", "success");
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

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
  const generateAssessmentHandler = async () => {
    if (!config.subject) {
      addToast("Please select a subject in Settings before generating", "warning");
      return;
    }
    if (!config.grade_level) {
      addToast("Please select a grade level in Settings before generating", "warning");
      return;
    }
    if (selectedStandards.length === 0 && uploadedDocs.length === 0) {
      addToast("Please select at least one standard or upload reference documents", "warning");
      return;
    }
    const mismatchCheck = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
    if (mismatchCheck.mismatch) addToast(mismatchCheck.message, "warning", 6000);
    setAssessmentLoading(true);
    setGeneratedAssessment(null);
    try {
      // Get full standard objects
      const fullStandards = selectedStandards.map((code) => {
        return standards.find((s) => s.code === code) || { code, benchmark: code };
      });

      // Auto-generate title if not provided
      const title = assessmentConfig.title ||
        `${config.subject || "Subject"} ${assessmentConfig.type.charAt(0).toUpperCase() + assessmentConfig.type.slice(1)} - ${selectedStandards.slice(0, 2).join(", ")}${selectedStandards.length > 2 ? "..." : ""}`;

      // Merge uploaded docs into content sources
      const allSources = [...selectedSources];
      for (const doc of uploadedDocs) {
        allSources.push({ type: "document", content: { text: doc.text, filename: doc.filename } });
      }

      const data = await api.generateAssessment(
        fullStandards,
        {
          grade: config.grade_level,
          subject: config.subject,
          teacher_name: config.teacher_name,
          globalAINotes: globalAINotes,
          requirements: unitConfig.requirements || "",
          contentOnly: contentOnly,
        },
        { ...assessmentConfig, title, sectionCategories: Object.fromEntries(Object.entries(assessmentConfig.sectionCategories).map(function(e) { return [e[0], e[1] > 0]; })), questionTypeCounts: Object.fromEntries(Object.entries(assessmentConfig.sectionCategories).filter(function(e) { return e[1] > 0; })) },
        allSources
      );

      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else if (data.assessment) {
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({}); // Clear previous answers
        addToast("Assessment generated successfully!", "success");
        if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
      }
    } catch (e) {
      addToast("Error generating assessment: " + e.message, "error");
    } finally {
      setAssessmentLoading(false);
    }
  };

  const redistributePoints = (newTotal) => {
    if (!generatedAssessment) return;
    const currentTotal = generatedAssessment.total_points || 100;
    if (newTotal === currentTotal || newTotal < 1) return;

    const sections = (generatedAssessment.sections || []).map(s => {
      const questions = (s.questions || []).map(q => ({
        ...q,
        points: Math.max(1, Math.round((q.points || 1) * newTotal / currentTotal))
      }));
      return { ...s, questions, points: questions.reduce((sum, q) => sum + q.points, 0) };
    });

    const actualTotal = sections.reduce((sum, s) => sum + s.points, 0);
    if (actualTotal !== newTotal && sections.length > 0) {
      const lastSection = sections[sections.length - 1];
      if (lastSection.questions.length > 0) {
        const lastQ = lastSection.questions[lastSection.questions.length - 1];
        lastQ.points += (newTotal - actualTotal);
        lastSection.points += (newTotal - actualTotal);
      }
    }

    setGeneratedAssessment({ ...generatedAssessment, sections, total_points: newTotal });
  };

  const exportAssessmentHandler = async (includeAnswerKey = false) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessment(generatedAssessment, includeAnswerKey);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        // Download the document
        const link = document.createElement("a");
        link.href = "data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64," + data.document;
        link.download = data.filename || "assessment.docx";
        link.click();
        addToast("Assessment exported!", "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

  const exportAssessmentForPlatformHandler = async (platform) => {
    if (!generatedAssessment) return;
    try {
      const data = await api.exportAssessmentForPlatform(generatedAssessment, platform);
      if (data.error) {
        addToast("Error exporting: " + data.error, "error");
      } else if (data.document) {
        const mimeTypes = {
          csv: "text/csv",
          xml: "application/xml",
          txt: "text/plain",
          json: "application/json",
        };
        const mimeType = mimeTypes[data.format] || data.mime_type || "application/octet-stream";
        const link = document.createElement("a");
        link.href = `data:${mimeType};base64,${data.document}`;
        link.download = data.filename;
        link.click();
        addToast(`Exported for ${platform}!`, "success");
      }
    } catch (e) {
      addToast("Error exporting: " + e.message, "error");
    }
  };

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

  // Save assessment locally for later use (makeup exams)
  const saveAssessmentHandler = async () => {
    if (!generatedAssessment) {
      addToast("No assessment to save", "warning");
      return;
    }
    if (!saveAssessmentName.trim()) {
      addToast("Please enter a name for the assessment", "warning");
      return;
    }
    setSavingAssessment(true);
    try {
      const data = await api.saveAssessmentLocally(generatedAssessment, saveAssessmentName.trim());
      if (data.error) {
        addToast("Error saving: " + data.error, "error");
      } else if (data.success) {
        addToast("Assessment saved successfully!", "success");
        setSaveAssessmentName('');
        // Refresh saved assessments list
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error saving assessment: " + e.message, "error");
    } finally {
      setSavingAssessment(false);
    }
  };

  // Fetch saved lessons for assessment content sources
  const fetchSavedLessons = async () => {
    try {
      const data = await api.listLessons();
      if (data.units) {
        setSavedLessons(data);
      }
    } catch (e) {
      console.error("Error loading saved lessons:", e);
    }
  };

  // Fetch saved assessments
  const fetchSavedAssessments = async () => {
    setLoadingSavedAssessments(true);
    try {
      const data = await api.listSavedAssessments();
      if (data.assessments) {
        setSavedAssessments(data.assessments);
      }
    } catch (e) {
      console.error("Error loading saved assessments:", e);
    } finally {
      setLoadingSavedAssessments(false);
    }
  };

  // Load a saved assessment
  const loadSavedAssessment = async (filename) => {
    try {
      const data = await api.loadSavedAssessment(filename);
      if (data.error) {
        addToast("Error loading assessment: " + data.error, "error");
      } else if (data.assessment) {
        if (!data.assessment.time_limit && data.assessment.time_limit !== 0) {
          const match = data.assessment.time_estimate?.match(/(\d+)/);
          data.assessment.time_limit = match ? parseInt(match[1]) : null;
        }
        setGeneratedAssessment(data.assessment);
        setAssessmentAnswers({});
        setAssessmentGradingResults(null);
        addToast("Assessment loaded!", "success");
      }
    } catch (e) {
      addToast("Error loading assessment: " + e.message, "error");
    }
  };

  // Delete a saved assessment
  const deleteSavedAssessment = async (filename) => {
    if (!confirm("Delete this saved assessment?")) return;
    try {
      const data = await api.deleteSavedAssessment(filename);
      if (data.error) {
        addToast("Error deleting: " + data.error, "error");
      } else {
        addToast("Assessment deleted", "success");
        fetchSavedAssessments();
      }
    } catch (e) {
      addToast("Error deleting assessment: " + e.message, "error");
    }
  };

  // Grade assessment answers with AI
  const gradeAssessmentAnswersHandler = async () => {
    if (!generatedAssessment || Object.keys(assessmentAnswers).length === 0) {
      addToast("Please answer at least one question first", "warning");
      return;
    }
    setGradingAssessment(true);
    setAssessmentGradingResults(null);
    try {
      const data = await api.gradeAssessmentAnswers(generatedAssessment, assessmentAnswers);
      if (data.error) {
        addToast("Error grading: " + data.error, "error");
      } else if (data.results) {
        setAssessmentGradingResults(data.results);
        addToast(`Graded! Score: ${data.results.score}/${data.results.total_points} (${data.results.percentage}%)`, "success");
      }
      if (data.usage) addToast("Grading cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
    } catch (e) {
      addToast("Error grading assessment: " + e.message, "error");
    } finally {
      setGradingAssessment(false);
    }
  };

  // Fetch published assessments for teacher dashboard
  const fetchPublishedAssessments = async () => {
    setLoadingPublished(true);
    try {
      const data = await api.getPublishedAssessments();
      if (data.assessments) {
        setPublishedAssessments(data.assessments);
      }
    } catch (e) {
      addToast("Error loading assessments: " + e.message, "error");
    } finally {
      setLoadingPublished(false);
    }
  };

  const fetchSharedResources = async () => {
    setLoadingSharedResources(true);
    try {
      const data = await api.getSharedResources();
      if (data.resources) {
        setSharedResources(data.resources);
      }
    } catch (e) {
      console.error("Error loading shared resources:", e);
    } finally {
      setLoadingSharedResources(false);
    }
  };

  const fetchTeacherTags = async () => {
    try {
      const data = await api.getTeacherTags();
      if (data && data.tags) setAllTeacherTags(data.tags);
    } catch (e) {
      console.error('Error loading teacher tags:', e);
    }
  };

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

  const handleDeleteSharedResource = async (id, title) => {
    try {
      var data = await api.deleteSharedResource(id);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.id !== id; }); });
        addToast('Deleted "' + title + '"', 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };

  const handleDeleteAllSharedResources = async (title) => {
    try {
      var data = await api.deleteSharedResourcesBulk(title);
      if (data.success) {
        setSharedResources(function(prev) { return prev.filter(function(r) { return r.title !== title; }); });
        addToast('Deleted "' + title + '" from ' + data.deleted + ' class' + (data.deleted === 1 ? '' : 'es'), 'success');
      } else {
        addToast(data.error || 'Failed to delete', 'error');
      }
    } catch (e) {
      addToast('Failed to delete: ' + e.message, 'error');
    }
  };

  // Fetch results for a specific assessment
  const fetchContentSubmissions = async (contentId) => {
    try {
      var data = await api.getContentSubmissions(contentId);
      if (data && data.students) {
        setContentSubmissionsGroups(data.students);
      } else {
        setContentSubmissionsGroups([]);
      }
    } catch (e) {
      console.error("Error loading content submissions:", e);
      setContentSubmissionsGroups([]);
    }
  };

  const fetchAssessmentResults = async (joinCode) => {
    setLoadingResults(true);
    try {
      const data = await api.getAssessmentResults(joinCode);
      if (data.error) {
        addToast("Error: " + data.error, "error");
      } else {
        setSelectedAssessmentResults({
          joinCode,
          title: data.title,
          submissions: data.submissions || [],
          stats: data.stats || {},
        });
        if (joinCode && joinCode.length > 10) {
          fetchContentSubmissions(joinCode);
        } else {
          setContentSubmissionsGroups([]);
        }
      }
      // Try to fetch in-progress drafts — only works for class-based content (UUID)
      if (joinCode && joinCode.length > 10) {
        try {
          var inProg = await api.getInProgressDrafts(joinCode);
          if (inProg && inProg.drafts) {
            setInProgressDrafts(inProg.drafts);
          } else {
            setInProgressDrafts([]);
          }
        } catch (e) {
          setInProgressDrafts([]);
        }
      } else {
        setInProgressDrafts([]);
      }
    } catch (e) {
      addToast("Error loading results: " + e.message, "error");
    } finally {
      setLoadingResults(false);
    }
  };

  // Toggle assessment active status
  const toggleAssessmentStatus = async (joinCode) => {
    try {
      const data = await api.toggleAssessmentStatus(joinCode);
      if (data.success) {
        addToast(data.is_active ? "Assessment activated" : "Assessment deactivated", "success");
        fetchPublishedAssessments();
        fetchSharedResources();
        fetchTeacherTags();
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

  // Delete published assessment
  const deletePublishedAssessment = async (joinCode) => {
    if (!confirm("Delete this assessment and all its submissions?")) return;
    try {
      const data = await api.deletePublishedAssessment(joinCode);
      if (data.success) {
        addToast("Assessment deleted", "success");
        setPublishedAssessments(prev => prev.filter(a => a.join_code !== joinCode));
        if (selectedAssessmentResults?.joinCode === joinCode) {
          setSelectedAssessmentResults(null);
        }
      }
    } catch (e) {
      addToast("Error: " + e.message, "error");
    }
  };

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
  const getLetterGrade = (score) => {
    const s = parseInt(score) || 0;
    return s >= 90 ? "A" : s >= 80 ? "B" : s >= 70 ? "C" : s >= 60 ? "D" : "F";
  };

  // Apply curve to filtered results
  const applyCurve = () => {
    const { curveType, curveValue } = curveModal;
    const val = parseFloat(curveValue) || 0;
    if (val === 0) {
      addToast("Please enter a curve value", "warning");
      return;
    }

    // Get indices of filtered results (based on period filter)
    const filteredIndices = [];
    status.results.forEach((r, idx) => {
      if (resultsPeriodFilter && r.period !== resultsPeriodFilter) return;
      filteredIndices.push(idx);
    });

    if (filteredIndices.length === 0) {
      addToast("No results to curve", "warning");
      return;
    }

    // Apply curve to each result
    const newEditedResults = editedResults.length > 0 ? [...editedResults] : [...status.results];
    const newEditedEmails = { ...editedEmails };
    let curvedCount = 0;

    filteredIndices.forEach((idx) => {
      const result = status.results[idx];
      const oldScore = parseInt(result.score) || 0;
      const oldGrade = result.letter_grade || getLetterGrade(oldScore);

      // Calculate new score based on curve type
      let newScore;
      if (curveType === "add") {
        newScore = Math.min(100, Math.max(0, oldScore + val));
      } else if (curveType === "percent") {
        newScore = Math.min(100, Math.max(0, Math.round(oldScore * (1 + val / 100))));
      } else if (curveType === "set_min") {
        newScore = Math.max(val, oldScore);
      }

      const newGrade = getLetterGrade(newScore);

      // Skip if no change
      if (newScore === oldScore) return;

      curvedCount++;

      // Update the result
      if (!newEditedResults[idx]) newEditedResults[idx] = { ...result };
      newEditedResults[idx] = {
        ...newEditedResults[idx],
        score: newScore,
        letter_grade: newGrade,
        edited: true,
      };

      // Update feedback if it contains the old score/grade
      let feedback = newEditedResults[idx].feedback || "";
      if (feedback) {
        // Replace score patterns like "85/100" or "Score: 85"
        feedback = feedback.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");
        feedback = feedback.replace(new RegExp("Score:\\s*" + oldScore, "gi"), "Score: " + newScore);
        feedback = feedback.replace(new RegExp("\\b" + oldScore + "%", "g"), newScore + "%");
        // Replace letter grade if mentioned
        if (oldGrade !== newGrade) {
          feedback = feedback.replace(new RegExp("\\(" + oldGrade + "\\)", "g"), "(" + newGrade + ")");
          feedback = feedback.replace(new RegExp("Grade:\\s*" + oldGrade + "\\b", "gi"), "Grade: " + newGrade);
        }
        newEditedResults[idx].feedback = feedback;
      }

      // Update email if it exists
      if (newEditedEmails[idx]) {
        let subject = newEditedEmails[idx].subject || "";
        let body = newEditedEmails[idx].body || "";

        // Update subject
        subject = subject.replace(new RegExp(": " + oldGrade + "$"), ": " + newGrade);

        // Update body
        body = body.replace(new RegExp("GRADE: " + oldScore + "/100 \\(" + oldGrade + "\\)"), "GRADE: " + newScore + "/100 (" + newGrade + ")");
        body = body.replace(new RegExp(oldScore + "/100", "g"), newScore + "/100");

        newEditedEmails[idx] = { ...newEditedEmails[idx], subject, body };
      }
    });

    // Sync to state
    setEditedResults(newEditedResults);
    setEditedEmails(newEditedEmails);

    // Also update status.results
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      filteredIndices.forEach((idx) => {
        if (newEditedResults[idx]) {
          updatedResults[idx] = { ...newEditedResults[idx] };
        }
      });
      return { ...prev, results: updatedResults };
    });

    setCurveModal({ ...curveModal, show: false });
    addToast(`Applied ${curveType === "add" ? "+" + val + " points" : curveType === "percent" ? "+" + val + "%" : "min " + val} curve to ${curvedCount} result${curvedCount !== 1 ? "s" : ""}`, "success");
  };

  const sendEmails = async () => {
    setEmailPreview({ ...emailPreview, show: false });
    const results = editedResults.length > 0 ? editedResults : status.results;
    if (results.length === 0) return;
    setEmailStatus({
      sending: true,
      sent: 0,
      failed: 0,
      message: "Sending emails...",
    });
    try {
      const data = await api.sendEmails(results, config.teacher_email, config.teacher_name, config.email_signature);
      setEmailStatus({
        sending: false,
        sent: data.sent || 0,
        failed: data.failed || 0,
        message: data.error
          ? `Error: ${data.error}`
          : `Sent ${data.sent} emails${data.failed > 0 ? `, ${data.failed} failed` : ""}`,
      });
    } catch (e) {
      setEmailStatus({
        sending: false,
        sent: 0,
        failed: 0,
        message: `Error: ${e.message}`,
      });
    }
  };

  // Send email for a single student
  const sendSingleEmail = async (result, index) => {
    const edited = editedEmails[index];
    const emailToUse = edited?.email || result.student_email;
    if (!emailToUse) {
      addToast("No email address for " + result.student_name, "error");
      return;
    }
    try {
      const emailResult = {
        ...result,
        student_email: emailToUse,
        custom_email_subject: edited?.subject || `Grade Report: ${result.assignment}`,
        custom_email_body: edited?.body || getDefaultEmailBody(index),
      };
      const response = await api.sendOutlookEmails({
        results: [emailResult],
        type: "student",
        teacher_name: config.teacher_name,
        email_signature: config.email_signature,
      });
      if (response.error) {
        addToast(response.error, "error");
      } else {
        setOutlookSendPolling(true);
        setOutlookSendStatus({ status: "running", sent: 0, total: response.total || 1, failed: 0, message: "Sending..." });
        addToast("Sending via Outlook to " + result.student_name, "info");
      }
    } catch (e) {
      addToast("Error sending email: " + e.message, "error");
    }
  };

  // Update approval status with persistence
  const updateApprovalStatus = async (index, approval) => {
    setEmailApprovals((prev) => ({ ...prev, [index]: approval }));
    // Also update the result object so the useEffect that rebuilds approvals
    // from status.results will preserve this approval
    setStatus((prev) => {
      const updatedResults = [...prev.results];
      if (updatedResults[index]) {
        updatedResults[index] = { ...updatedResults[index], email_approval: approval };
      }
      return { ...prev, results: updatedResults };
    });
    // Persist to backend
    const result = status.results[index];
    if (result?.filename) {
      try {
        await api.updateApproval(result.filename, approval);
      } catch (e) {
        console.error("Error saving approval:", e);
      }
    }
  };

  // Bulk update approvals with persistence
  const updateApprovalsBulk = async (approvals) => {
    setEmailApprovals(approvals);
    // Build filename -> approval map for API
    const filenameApprovals = {};
    Object.entries(approvals).forEach(([idx, approval]) => {
      const result = status.results[parseInt(idx)];
      if (result?.filename) {
        filenameApprovals[result.filename] = approval;
      }
    });
    if (Object.keys(filenameApprovals).length > 0) {
      try {
        await api.updateApprovalsBulk(filenameApprovals);
      } catch (e) {
        console.error("Error saving approvals:", e);
      }
    }
  };

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
