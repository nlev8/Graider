import { useEffect } from "react";
import * as api from "../services/api";
import { useSettingsAutoSave } from "../hooks/useSettingsAutoSave";
import { useBillingRedirect } from "../hooks/useBillingRedirect";
import { useAssignmentAutoSave } from "../hooks/useAssignmentAutoSave";
import { useGradingStatusPoll } from "../hooks/useGradingStatusPoll";
import { useGradingToast } from "../hooks/useGradingToast";
import { useOutlookSendPolling } from "../hooks/useOutlookSendPolling";

/*
 * useAppLifecycleEffects — segment 4 of 7 of the App.jsx finale split.
 * VERBATIM move of the contiguous App.jsx range 1082-1312: the big
 * settings/rubric/assignments/uploads/accommodations/lessons/api-keys startup
 * load (gated on userApproved), the builder-tab refresh, useSettingsAutoSave,
 * the onboarding-wizard first-run effect, useBillingRedirect,
 * useAssignmentAutoSave, the on-mount status fetch, useGradingStatusPoll
 * (owns the 500ms grading poll lifecycle — interval timing/cleanup untouched
 * inside that hook, which remains always-mounted via this always-called
 * segment), fetchPendingConfirmations + its refresh effect, useGradingToast,
 * the clear-standards effect, the analytics-tab class fetch, the VPortal
 * credential loads, and useOutlookSendPolling.
 * See useAppCoreState for the hook-order contract.
 */
export function useAppLifecycleEffects(ctx) {
  const {
    activeTab, addToast, assignment, config, confirmationStudentFilter, fetchTeacherClasses,
    globalAINotes, importedDoc, isLoadingAssignment, isLocalhost, loadedAssignmentName,
    pendingConfirmationFilenames, pendingConfirmationIds, removeToast, resultsPeriodFilter, rubric,
    setAccommodationPresets, setActiveTab, setApiKeys, setAssessmentTemplates, setAssignment,
    setConfig, setGlobalAINotes, setLoadedAssignmentName, setPendingConfirmationStudents,
    setPendingConfirmations, setPeriods, setRosters, setRubric, setSavedAssignmentData,
    setSavedAssignments, setSavedLessons, setSelectedStandards, setSettingsLoaded, setSettingsTab,
    setShowOnboardingWizard, setStandards, setStatus, setStudentAccommodations, setSupportDocs,
    setToasts, setVportalConfigured, setVportalEmail, settingsLoaded, skipAutoSaveRef, status,
    teacherClasses, userApproved,
  } = ctx;

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

  return {
    fetchPendingConfirmations, outlookSendStatus, setOutlookSendStatus, outlookSendPolling,
    setOutlookSendPolling,
  };
}
