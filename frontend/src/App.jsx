import React from "react";
import PasswordResetScreen from "./components/PasswordResetScreen";
import CurveModal from "./components/CurveModal";
import StudentPortal from "./components/StudentPortal";
import StudentApp from "./components/StudentApp";
import LoginScreen from "./components/LoginScreen";
import DistrictSetup from "./components/DistrictSetup";
import { AuthLoadingScreen, ApprovalCheckingScreen, NotApprovedScreen } from "./components/AuthScreens";
import Sidebar from "./components/Sidebar";
import { useTheme } from "./hooks/useTheme";
import { useAuthSession } from "./hooks/useAuthSession";
// ── App.jsx finale split (CQ campaign: every function ≤300 LOC) ─────────────
// The former ~2,677-line App function now lives in src/app/: seven contiguous
// segment hooks own the state/effects/handlers, five stateless section
// components own the render. Each file header cites the pre-split App.jsx
// line range it was moved from, verbatim.
import { useAppCoreState } from "./app/useAppCoreState";
import { useAppContentState } from "./app/useAppContentState";
import { useAppAssessmentDashboardState } from "./app/useAppAssessmentDashboardState";
import { useAppLifecycleEffects } from "./app/useAppLifecycleEffects";
import { useAppResultsSync } from "./app/useAppResultsSync";
import { useAppBuilderHandlers } from "./app/useAppBuilderHandlers";
import { useAppPlannerResultsHandlers } from "./app/useAppPlannerResultsHandlers";
import AppHeaderBar from "./app/AppHeaderBar";
import AppModals from "./app/AppModals";
import AppTabPanels from "./app/AppTabPanels";
import FocusExportModal from "./app/FocusExportModal";
import ToastStack from "./app/ToastStack";

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

  // The seven segment hooks are CONTIGUOUS verbatim slices of the pre-split
  // App body, called unconditionally in their original source order — so the
  // flattened React hook sequence (and therefore the effect execution order,
  // including the always-mounted 500ms grading-status poll inside
  // useAppLifecycleEffects → useGradingStatusPoll) is identical to main.
  // Later segments receive earlier segments' values via ctx spreads.
  const core = useAppCoreState({ isLocalhost, user, userApproved });
  const content = useAppContentState();
  const dash = useAppAssessmentDashboardState({
    config: core.config,
    assessmentConfig: content.assessmentConfig,
    setAssessmentConfig: content.setAssessmentConfig,
    distributeQuestions: content.distributeQuestions,
  });
  const lifecycle = useAppLifecycleEffects({ ...core, ...content, ...dash, isLocalhost, userApproved });
  const resultsSync = useAppResultsSync({ ...core, ...content, ...dash });
  const builderHandlers = useAppBuilderHandlers({ ...core, ...content, ...dash });
  const plannerHandlers = useAppPlannerResultsHandlers({
    ...core, ...content, ...dash, ...lifecycle, ...builderHandlers,
  });

  // Only what the shell itself renders is destructured; everything else flows
  // to the section components through the ctx spreads below.
  const {
    status, activeTab, setActiveTab, sidebarCollapsed, setSidebarCollapsed, isAdmin,
    resultsPeriodFilter, toasts, removeToast, addToast,
    focusExportModal, setFocusExportModal, focusExportLoading, setFocusExportLoading,
    focusIncludeLetterGrade, setFocusIncludeLetterGrade,
  } = core;
  const { curveModal, setCurveModal, editedResults } = content;
  const { handleStartGrading, handleStopGrading } = builderHandlers;
  const { applyCurve } = plannerHandlers;

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
      {/* Overlay mounts (onboarding, tutorial, email preview, review,
          doc editor) — first children of the root div exactly as pre-split;
          see AppModals for why Focus/Curve/Toasts are NOT in there. */}
      <AppModals
        {...core}
        {...content}
        {...dash}
        {...builderHandlers}
        {...plannerHandlers}
        user={user}
        theme={theme}
        toggleTheme={toggleTheme}
      />

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
          <AppHeaderBar
            status={status}
            handleStartGrading={handleStartGrading}
            handleStopGrading={handleStopGrading}
            theme={theme}
            toggleTheme={toggleTheme}
          />

          <div style={{ padding: activeTab === "results" ? "20px 15px" : "30px", flex: 1, overflowY: "auto" }}>
            <div style={{ maxWidth: activeTab === "results" ? "none" : "1400px", margin: "0 auto" }}>
              <AppTabPanels
                {...core}
                {...content}
                {...dash}
                {...lifecycle}
                {...resultsSync}
                {...builderHandlers}
                {...plannerHandlers}
                user={user}
                theme={theme}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Focus Export Modal */}
      <FocusExportModal
        focusExportModal={focusExportModal}
        setFocusExportModal={setFocusExportModal}
        focusExportLoading={focusExportLoading}
        setFocusExportLoading={setFocusExportLoading}
        focusIncludeLetterGrade={focusIncludeLetterGrade}
        setFocusIncludeLetterGrade={setFocusIncludeLetterGrade}
        status={status}
        editedResults={editedResults}
        addToast={addToast}
      />

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
      <ToastStack toasts={toasts} removeToast={removeToast} />
    </div>
  );
}

export default App;
