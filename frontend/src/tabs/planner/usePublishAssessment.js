import { useState } from "react";
import * as api from "../../services/api";

/*
 * usePublishAssessment — owns the publish cluster, relocated verbatim from
 * PlannerTab.jsx (CQ wave-3 split; mirrors the wave-2 useIndividualUpload
 * precedent for state/handler clusters).
 *
 * History: this cluster moved App.jsx → PlannerTab in PR 7c of the Planner
 * extraction sprint (7 useStates + publishAssessmentHandler /
 * loadPublishModalStudents / confirmPublishAssessment). Per plan #190 Task 7,
 * the globally-rendered publish modals + their state ownership belong to the
 * planner workflow.
 *
 * studentAccommodations stays in App as a prop (used by 3 tabs).
 * teacherClasses, periods, config, addToast, fetchTeacherClasses,
 * fetchPublishedAssessments, fetchSharedResources, fetchTeacherTags,
 * getActiveAssignment, generatedAssignment, lessonPlan are all App-shell
 * props, received here as hook args.
 *
 * Behavior-preserving notes: handlers are intentionally NOT memoized (no
 * useCallback) — same as the pre-split plain-const declarations recreated
 * each render. The hook is called unconditionally from the PlannerTab shell.
 */
export default function usePublishAssessment({
  getActiveAssignment,
  generatedAssignment,
  lessonPlan,
  config,
  addToast,
  studentAccommodations,
  teacherClasses,
  fetchTeacherClasses,
  fetchPublishedAssessments,
  fetchSharedResources,
  fetchTeacherTags,
}) {
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishSettings, setPublishSettings] = useState({
    period: '',
    periodFilename: '',
    isMakeup: false,
    selectedStudents: [],
    timeLimit: null,
    applyAccommodations: true,
    contentType: 'assessment',
    assessmentCategory: 'formative',
    showScoreImmediately: false,
    showCorrectAnswers: false,
    allowMultipleAttempts: false,
    dueDate: '',
    availableFrom: '',
    availableUntil: '',
  });
  const [publishClassId, setPublishClassId] = useState('');
  const [publishModalStudents, setPublishModalStudents] = useState([]);
  const [loadingPublishStudents, setLoadingPublishStudents] = useState(false);
  const [publishedAssessmentModal, setPublishedAssessmentModal] = useState({ show: false, joinCode: "", joinLink: "" });
  const [publishingAssessment, setPublishingAssessment] = useState(false);

  const publishAssessmentHandler = () => {
    var content = getActiveAssignment();
    if (!content) {
      addToast("No content to publish", "warning");
      return;
    }
    var detectedType = 'assessment';
    if (generatedAssignment || (lessonPlan && lessonPlan.sections && !lessonPlan.days)) {
      detectedType = 'assignment';
    }
    setPublishSettings({
      period: '',
      periodFilename: '',
      isMakeup: false,
      selectedStudents: [],
      timeLimit: detectedType === 'assignment' ? null : (content.time_limit || null),
      applyAccommodations: true,
      contentType: detectedType,
      assessmentCategory: 'formative',
    });
    setPublishModalStudents([]);
    setPublishClassId('');
    fetchTeacherClasses();
    setShowPublishModal(true);
  };

  const loadPublishModalStudents = async (periodFilename) => {
    if (!periodFilename) {
      setPublishModalStudents([]);
      return;
    }
    setLoadingPublishStudents(true);
    try {
      const data = await api.getPeriodStudents(periodFilename);
      if (data.students) {
        setPublishModalStudents(data.students);
      }
    } catch (e) {
      console.error("Failed to load period students:", e);
      setPublishModalStudents([]);
    } finally {
      setLoadingPublishStudents(false);
    }
  };

  const confirmPublishAssessment = async () => {
    var contentToPublish = getActiveAssignment();
    if (!contentToPublish) return;

    setPublishingAssessment(true);
    try {
      let studentAccommodationsMap = {};
      if (publishSettings.applyAccommodations && publishModalStudents.length > 0) {
        publishModalStudents.forEach(student => {
          const studentId = student.id || student.email || (student.first + ' ' + student.last);
          const accommodation = studentAccommodations[studentId];
          if (accommodation) {
            studentAccommodationsMap[student.first + ' ' + student.last] = accommodation;
          }
        });
      }

      let restrictedStudents = null;
      if (publishSettings.isMakeup && publishSettings.selectedStudents.length > 0) {
        restrictedStudents = publishSettings.selectedStudents;
      }

      let data;
      if (publishClassId) {
        const contentType = publishSettings.contentType;
        const settings = {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          show_correct_answers: publishSettings.showCorrectAnswers,
          show_score_immediately: publishSettings.showScoreImmediately,
          content_type: publishSettings.contentType,
          assessment_category: publishSettings.assessmentCategory,
          allow_multiple_attempts: publishSettings.allowMultipleAttempts,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
          due_date: publishSettings.dueDate || null,
          available_from: publishSettings.availableFrom || null,
          available_until: publishSettings.availableUntil || null,
        };
        data = await api.publishToClass(publishClassId, contentToPublish, contentType, contentToPublish.title || 'Untitled', settings, publishSettings.dueDate || null);
      } else {
        data = await api.publishAssessmentToPortal(contentToPublish, {
          teacher_name: config.teacher_name || "Teacher",
          teacher_email: config.teacher_email,
          show_correct_answers: publishSettings.showCorrectAnswers,
          show_score_immediately: publishSettings.showScoreImmediately,
          content_type: publishSettings.contentType,
          assessment_category: publishSettings.assessmentCategory,
          allow_multiple_attempts: publishSettings.allowMultipleAttempts,
          period: publishSettings.period,
          restricted_students: restrictedStudents,
          student_accommodations: studentAccommodationsMap,
          time_limit_minutes: publishSettings.timeLimit,
          due_date: publishSettings.dueDate || null,
          available_from: publishSettings.availableFrom || null,
          available_until: publishSettings.availableUntil || null,
        });
      }

      if (data.error) {
        addToast("Error publishing: " + data.error, "error");
      } else if (data.success) {
        setShowPublishModal(false);
        var selectedClass = publishClassId ? teacherClasses.find(function(c) { return c.id === publishClassId; }) : null;
        setPublishedAssessmentModal({
          show: true,
          joinCode: publishClassId ? (selectedClass ? selectedClass.join_code : "") : data.join_code,
          joinLink: publishClassId ? (window.location.origin + "/student") : data.join_link,
          isClassBased: !!publishClassId,
          className: selectedClass ? selectedClass.name : "",
        });
        addToast("Published to student portal!", "success");
        fetchPublishedAssessments();
        fetchSharedResources();
        fetchTeacherTags();
      }
    } catch (e) {
      addToast("Error publishing: " + e.message, "error");
    } finally {
      setPublishingAssessment(false);
    }
  };

  return {
    showPublishModal, setShowPublishModal,
    publishSettings, setPublishSettings,
    publishClassId, setPublishClassId,
    publishModalStudents,
    loadingPublishStudents,
    publishedAssessmentModal, setPublishedAssessmentModal,
    publishingAssessment,
    publishAssessmentHandler,
    loadPublishModalStudents,
    confirmPublishAssessment,
  };
}
