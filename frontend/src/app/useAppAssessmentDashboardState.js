import { useState, useEffect, useRef } from "react";
import * as api from "../services/api";
import { getSubjectSectionDefaults, distributePoints } from "../utils/assessmentDistribution";

/*
 * useAppAssessmentDashboardState — segment 3 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 955-1080: the
 * subject-change → section-defaults effect, generated-assessment state,
 * plannerMode, teacherClasses, templates, the teacher-dashboard
 * (published/shared/submissions/tags) state, saved assessments, file-upload
 * state (rosters/periods/supportDocs), IEP/504 accommodation state, the
 * rubric, shared refs, and the settingsLoaded gate.
 *
 * One DOCUMENTED relocation: fetchTeacherClasses (pre-split App.jsx
 * 1761-1769) moved here, next to the teacherClasses state it sets, because
 * useAppLifecycleEffects' analytics-tab effect (pre-split 1275-1279) calls it
 * and segment hooks only see values created before them. It is a plain
 * per-render closure either way — defining it earlier changes nothing.
 * See useAppCoreState for the hook-order contract.
 */
export function useAppAssessmentDashboardState(ctx) {
  const {
    assessmentConfig, config, distributeQuestions, setAssessmentConfig,
  } = ctx;

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

  // Fetch teacher's Clever classes for publish modal — moved from pre-split
  // App.jsx 1761-1769 (see header).
  const fetchTeacherClasses = async () => {
    try {
      const data = await api.listClasses();
      if (data.classes) setTeacherClasses(data.classes);
    } catch (e) {
      console.error("Failed to load classes:", e);
    }
  };

  return {
    generatedAssessment, setGeneratedAssessment, assessmentLoading, setAssessmentLoading,
    assessmentAnswers, setAssessmentAnswers, assessmentGradingResults, setAssessmentGradingResults,
    gradingAssessment, setGradingAssessment, plannerMode, setPlannerMode, teacherClasses,
    setTeacherClasses, assessmentTemplates, setAssessmentTemplates, uploadingTemplate,
    setUploadingTemplate, publishedAssessments, setPublishedAssessments, loadingPublished,
    setLoadingPublished, selectedAssessmentResults, setSelectedAssessmentResults, inProgressDrafts,
    setInProgressDrafts, loadingResults, setLoadingResults, contentSubmissionsGroups,
    setContentSubmissionsGroups, sharedResources, setSharedResources, loadingSharedResources,
    setLoadingSharedResources, allTeacherTags, setAllTeacherTags, selectedTagFilter,
    setSelectedTagFilter, savedAssessments, setSavedAssessments, loadingSavedAssessments,
    setLoadingSavedAssessments, savingAssessment, setSavingAssessment, saveAssessmentName,
    setSaveAssessmentName, rosters, setRosters, periods, setPeriods, supportDocs, setSupportDocs,
    uploadingRoster, setUploadingRoster, accommodationPresets, setAccommodationPresets,
    studentAccommodations, setStudentAccommodations, rubric, setRubric, fileInputRef, docHtmlRef,
    rosterInputRef, settingsLoaded, setSettingsLoaded, fetchTeacherClasses,
  };
}
