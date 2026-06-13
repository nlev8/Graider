import { useState, useEffect, useRef, useCallback } from "react";
import * as api from "../services/api";
import { defaultColPercents } from "./appConstants";
import { track as phTrack } from "../services/posthog";
import { useSubscription } from "../hooks/useSubscription";
import { usePortalSubmissions } from "../hooks/usePortalSubmissions";
import { useToasts } from "../hooks/useToasts";
import { useFocusPolling } from "../hooks/useFocusPolling";

/*
 * useAppCoreState — segment 1 of 7 of the App.jsx finale split (CQ campaign).
 * VERBATIM move of the contiguous App.jsx range 293-700 (minus the
 * MODEL_COST_PER_ASSIGNMENT + EDTECH_TOOLS + defaultColPercents constants,
 * hoisted to ./appConstants.js): core config/apiKeys state, Focus-export +
 * VPortal + pending-confirmation state, grading `status`, activeTab,
 * admin/onboarding/tutorial/settings-tab state, useSubscription, the
 * resizable Results-table column cluster, the admin-status effect,
 * usePortalSubmissions, the assessment-results 30s poll, useToasts (+ the
 * lastResultCount ref consumed by useAppResultsSync's graded-toast effect),
 * useFocusPolling, and sidebarCollapsed.
 *
 * HOOK ORDER: the seven segment hooks are contiguous slices called from App()
 * in their original source order, so the flattened hook sequence — and
 * therefore React's effect execution order — is identical to pre-split main.
 */
export function useAppCoreState(ctx) {
  const {
    isLocalhost, user, userApproved,
  } = ctx;

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

  return {
    config, setConfig, apiKeys, setApiKeys, focusExportModal, setFocusExportModal,
    focusExportLoading, setFocusExportLoading, focusIncludeLetterGrade, setFocusIncludeLetterGrade,
    gradesApproved, setGradesApproved, vportalEmail, setVportalEmail, vportalConfigured,
    setVportalConfigured, pendingConfirmations, setPendingConfirmations,
    pendingConfirmationStudents, setPendingConfirmationStudents, confirmationStudentFilter,
    setConfirmationStudentFilter, pendingConfirmationIds, pendingConfirmationFilenames, status,
    setStatus, activeTab, _setActiveTab, setActiveTab, isAdmin, setIsAdmin, adminSchool,
    setAdminSchool, showOnboardingWizard, setShowOnboardingWizard, showTutorial, setShowTutorial,
    tutorialStep, setTutorialStep, settingsTab, setSettingsTab, subscription, setSubscription,
    subscriptionLoading, setSubscriptionLoading, colWidths, setColWidths, tableRef, resizingCol,
    resizeStartX, resizeStartW, initColWidths, handleResizeStart, assessmentResults,
    setAssessmentResults, resultsPeriodFilter, setResultsPeriodFilter, globalAINotes,
    setGlobalAINotes, portalSubmissions, toasts, setToasts, addToast, removeToast, lastResultCount,
    focusCommsStatus, setFocusCommsStatus, focusCommsPolling, setFocusCommsPolling,
    focusCommentsStatus, setFocusCommentsStatus, focusCommentsPolling, setFocusCommentsPolling,
    sidebarCollapsed, setSidebarCollapsed,
  };
}
