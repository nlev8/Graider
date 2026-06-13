import { useState, useRef } from "react";

/*
 * useAppContentState — segment 2 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 702-953 (minus
 * HIGHLIGHT_COLORS, hoisted to ./appConstants.js): the Builder `assignment`
 * cluster, imported-doc/doc-editor state, highlighter mode, the Results
 * edit/email/approval state cluster, Planner standards/lesson state,
 * savedLessons/selectedSources, unitConfig + assessmentConfig, and the
 * distributeQuestions helper (reads assessmentConfig via closure exactly as
 * before). No ctx inputs — this segment referenced nothing declared before it.
 * See useAppCoreState for the hook-order contract.
 */
export function useAppContentState() {
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

  return {
    assignment, setAssignment, savedAssignments, setSavedAssignments, savedAssignmentData,
    setSavedAssignmentData, modelAnswersLoading, setModelAnswersLoading, loadedAssignmentName,
    setLoadedAssignmentName, isLoadingAssignment, setIsLoadingAssignment, skipAutoSaveRef,
    importedDoc, setImportedDoc, docEditorModal, setDocEditorModal, highlighterMode,
    setHighlighterMode, editedResults, setEditedResults, reviewModal, setReviewModal,
    reviewModalTab, setReviewModalTab, reviewModalRightTab, setReviewModalRightTab,
    showAIReasoning, setShowAIReasoning, emailPreview, setEmailPreview, emailStatus,
    setEmailStatus, emailApprovals, setEmailApprovals, sentEmails, setSentEmails,
    autoApproveEmails, setAutoApproveEmails, editedEmails, setEditedEmails, curveModal,
    setCurveModal, standards, setStandards, selectedStandards, setSelectedStandards,
    standardsScrollRef, assessmentStandardsScrollRef, lessonPlan, setLessonPlan,
    generatedAssignment, setGeneratedAssignment, uploadedDocs, setUploadedDocs, contentOnly,
    setContentOnly, savedLessons, setSavedLessons, selectedSources, setSelectedSources, unitConfig,
    setUnitConfig, assessmentConfig, setAssessmentConfig, distributeQuestions,
  };
}
