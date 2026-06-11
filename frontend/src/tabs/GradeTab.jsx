import React, { useState, useEffect, useRef } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";
import ErrorBanner from "./grade/ErrorBanner";
import GradingModesPanel from "./grade/GradingModesPanel";
import ActivityMonitorCard from "./grade/ActivityMonitorCard";
import PeriodFilter from "./grade/PeriodFilter";
import StudentFilter from "./grade/StudentFilter";
import AssignmentFilter from "./grade/AssignmentFilter";
import ActiveFiltersSummary from "./grade/ActiveFiltersSummary";
import RegradeToggles from "./grade/RegradeToggles";
import IndividualUploadPanel from "./grade/IndividualUploadPanel";
import GradingProgress from "./grade/GradingProgress";
import useIndividualUpload from "./grade/useIndividualUpload";

/*
 * Grade tab — fully extracted. By end of PR 4, App.jsx no longer declares any
 * Grade-specific useState; this component owns its own state.
 *
 * Per docs/superpowers/plans/2026-05-03-grade-tab-extraction.md:
 *   - PR 1 was the pure JSX lift.
 *   - PR 2 moved toggles + the showActivityLog vertical slice.
 *   - PR 3 moved selectedPeriod / periodStudents / gradeFilterAssignment /
 *     individualUpload / gradeAssignment plus their handlers.
 *   - PR 4 moved gradeFilterStudent as pure local UI state and deleted the
 *     dead portal-era file-selection branch (matching-files UI, selectedFiles,
 *     availableFiles, fileMatchesPeriodStudent helper, cost estimate banner)
 *     plus the dead gradeImportedDoc setter call.
 *
 * CQ wave-2 split (this revision): the 1,625-line component function is now a
 * thin shell composing ./grade/* sections (wave-1 tabs/analytics + tabs/results
 * precedent). All state stays GradeTab-owned and is threaded down as props —
 * behavior-preserving, no logic changes:
 *   - ErrorBanner, GradingModesPanel, ActivityMonitorCard
 *   - PeriodFilter, StudentFilter, AssignmentFilter, ActiveFiltersSummary
 *   - RegradeToggles (skip-verified / exclude-graded / exclude-approved)
 *   - IndividualUploadPanel (+ StudentNameAutocomplete, IndividualResultCard)
 *   - GradingProgress
 *   - useIndividualUpload hook (individualUpload state slice + handlers +
 *     blob-URL revoke effect)
 *
 * Mount: this component is always-mounted with display:none-style hiding from
 * App.jsx (Assistant-tab precedent), so local state survives tab switches.
 *
 * Closures the JSX still captures (props):
 *   --- App-shell state (read-only) ---
 *   status, config, globalAINotes
 *   savedAssignments, savedAssignmentData, periods, sortedPeriods
 *   emailApprovals
 *
 *   --- App-shell mutators ---
 *   setStatus               - Used by error-banner Dismiss + handleIndividualGrade
 *   setSavedAssignmentData  - SHARED MUTABLE state (Codex Round 2 #4); written
 *                             from completion-only toggle and due-date editor.
 *   addToast                - App-shell utility
 *
 * GradeTab-owned state:
 *   PR 2: gradingModesExpanded, showActivityLog, skipVerified,
 *         excludeGradedStudents, excludeApprovedStudents, logRef,
 *         auto-scroll log effect, auto-expand-on-error effect.
 *   PR 3: selectedPeriod, periodStudents, gradeFilterAssignment,
 *         individualUpload, gradeAssignment, loadPeriodStudents,
 *         handleIndividualFileSelect, handleIndividualGrade,
 *         clearIndividualUpload, getStudentSuggestions,
 *         blob-URL revoke effect for individualUpload.preview.
 *   PR 4: gradeFilterStudent (pure local UI filter).
 */

export default function GradeTab(props) {
  const {
    status,
    config,
    globalAINotes,
    savedAssignments,
    savedAssignmentData,
    setSavedAssignmentData,
    setStatus,
    addToast,
    periods,
    sortedPeriods,
    emailApprovals,
  } = props;

  // PR 2 — local Grade-tab state (pure toggles + showActivityLog vertical slice).
  const [gradingModesExpanded, setGradingModesExpanded] = useState(false);
  const [showActivityLog, setShowActivityLog] = useState(false);
  const [skipVerified, setSkipVerified] = useState(false);
  const [excludeGradedStudents, setExcludeGradedStudents] = useState(false);
  const [excludeApprovedStudents, setExcludeApprovedStudents] = useState(false);
  const logRef = useRef(null);

  // PR 3 — local Grade-tab state (individual-upload + period + assignment-config slice).
  const [selectedPeriod, setSelectedPeriod] = useState("");
  const [periodStudents, setPeriodStudents] = useState([]);
  const [gradeFilterAssignment, setGradeFilterAssignment] = useState("");

  // PR 4 — local Grade-tab state (pure UI filter; no App-level effect, no dead helpers).
  const [gradeFilterStudent, setGradeFilterStudent] = useState("");
  const [gradeAssignment, setGradeAssignment] = useState({
    title: "",
    customMarkers: [],
    excludeMarkers: [],
    gradingNotes: "",
    responseSections: [],
  });

  // CQ wave-2 — individualUpload state slice + handlers + blob-revoke effect
  // live in the hook (wave-1 useAnalyticsData precedent).
  const {
    individualUpload,
    setIndividualUpload,
    handleIndividualFileSelect,
    handleIndividualGrade,
    clearIndividualUpload,
    getStudentSuggestions,
  } = useIndividualUpload({
    config,
    globalAINotes,
    periods,
    selectedPeriod,
    periodStudents,
    gradeAssignment,
    addToast,
    setStatus,
  });

  // Auto-scroll the activity log to the bottom when new entries arrive.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [status.log]);

  // Auto-expand the Activity Monitor when an error occurs so the user sees it.
  useEffect(() => {
    if (status.error) {
      setShowActivityLog(true);
    }
  }, [status.error]);

  // PR 3 — Load students from selected period (was App-level loadPeriodStudents).
  const loadPeriodStudents = async (periodFilename) => {
    if (!periodFilename) {
      setPeriodStudents([]);
      return;
    }
    try {
      const data = await api.getPeriodStudents(periodFilename);
      if (data.students) {
        setPeriodStudents(data.students);
      }
    } catch (e) {
      console.error("Failed to load period students:", e);
      setPeriodStudents([]);
    }
  };

  return (
    <div data-tutorial="grade-card" className="fade-in">
      <ErrorBanner status={status} setStatus={setStatus} />

      <GradingModesPanel
        savedAssignments={savedAssignments}
        savedAssignmentData={savedAssignmentData}
        setSavedAssignmentData={setSavedAssignmentData}
        addToast={addToast}
        gradingModesExpanded={gradingModesExpanded}
        setGradingModesExpanded={setGradingModesExpanded}
      />

      <ActivityMonitorCard
        status={status}
        showActivityLog={showActivityLog}
        setShowActivityLog={setShowActivityLog}
        logRef={logRef}
      />

      {/* Full width layout */}
      <div className="glass-card" style={{ padding: "25px" }}>
        <h2
          style={{
            fontSize: "1.3rem",
            fontWeight: 700,
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Icon name="Play" size={24} />
          Start Grading
        </h2>

        <PeriodFilter
          periods={periods}
          sortedPeriods={sortedPeriods}
          selectedPeriod={selectedPeriod}
          setSelectedPeriod={setSelectedPeriod}
          setGradeFilterStudent={setGradeFilterStudent}
          loadPeriodStudents={loadPeriodStudents}
          periodStudents={periodStudents}
        />

        <StudentFilter
          selectedPeriod={selectedPeriod}
          periodStudents={periodStudents}
          sortedPeriods={sortedPeriods}
          gradeFilterStudent={gradeFilterStudent}
          setGradeFilterStudent={setGradeFilterStudent}
        />

        <AssignmentFilter
          savedAssignments={savedAssignments}
          savedAssignmentData={savedAssignmentData}
          gradeFilterAssignment={gradeFilterAssignment}
          setGradeFilterAssignment={setGradeFilterAssignment}
          setGradeAssignment={setGradeAssignment}
          addToast={addToast}
        />

        <ActiveFiltersSummary
          gradeFilterStudent={gradeFilterStudent}
          gradeFilterAssignment={gradeFilterAssignment}
          setGradeFilterStudent={setGradeFilterStudent}
          setGradeFilterAssignment={setGradeFilterAssignment}
        />

        {/* PR 4 deleted the dead "Matching Files Preview" block here — it
            depended on availableFiles (always empty after the portal-only
            workflow shipped) and selectedFiles (a stub). The whole block
            was unreachable. */}

        <RegradeToggles
          status={status}
          emailApprovals={emailApprovals}
          savedAssignmentData={savedAssignmentData}
          gradeFilterAssignment={gradeFilterAssignment}
          skipVerified={skipVerified}
          setSkipVerified={setSkipVerified}
          excludeGradedStudents={excludeGradedStudents}
          setExcludeGradedStudents={setExcludeGradedStudents}
          excludeApprovedStudents={excludeApprovedStudents}
          setExcludeApprovedStudents={setExcludeApprovedStudents}
        />

        {/* Grading Notes removed from Grade tab — use Grading Setup (Builder) instead */}

        <IndividualUploadPanel
          individualUpload={individualUpload}
          setIndividualUpload={setIndividualUpload}
          periodStudents={periodStudents}
          getStudentSuggestions={getStudentSuggestions}
          handleIndividualFileSelect={handleIndividualFileSelect}
          handleIndividualGrade={handleIndividualGrade}
          clearIndividualUpload={clearIndividualUpload}
        />

        <GradingProgress status={status} />

        {/* PR 4 deleted the pre-grading cost-estimate banner here — it gated
            on selectedFiles.length > 0, which was always 0 after the dead
            portal-era selection branch was removed. */}

      </div>
    </div>
  );
}
