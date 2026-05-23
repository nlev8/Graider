import React, { useState, useEffect } from "react";
import Icon from "../components/Icon";
import PublishedAssessmentModal from "../components/PublishedAssessmentModal";
import PublishContentModal from "../components/PublishContentModal";
import PlannerCalendar from "../components/PlannerCalendar";
import PlannerTools from "../components/PlannerTools";
import PlannerLesson from "../components/PlannerLesson";
import PlannerAssessment from "../components/PlannerAssessment";
import PlannerDashboard from "../components/PlannerDashboard";
import NewUnitModal from "../components/NewUnitModal";
import ShareWithClassesModal from "../components/ShareWithClassesModal";
import AttemptDrawer from "../components/AttemptDrawer";
import PlatformExportMenu from "../components/PlatformExportMenu";
import QuestionEditToolbar from "../components/QuestionEditToolbar";
import QuestionEditOverlay from "../components/QuestionEditOverlay";
import MatchingCards from "../components/MatchingCards";
import * as api from "../services/api";
import { checkRequirementsMismatch } from "../utils/standardsMismatch";
import { useQuestionEditing } from "../hooks/useQuestionEditing";

/*
 * Planner tab — presentational extraction (PR 1 of 7).
 * Per docs/superpowers/plans/2026-05-04-planner-tab-extraction.md.
 *
 * Pure JSX lift from App.jsx:7574-13515. State ownership stays in App.jsx;
 * PlannerTab receives all closures as props. Subsequent PRs (2-7)
 * progressively move ~91 Planner-only state pairs into this component.
 *
 * Mount strategy: PR 1 keeps the existing conditional mount in App.jsx.
 * PR 2 Step 0 will convert to always-mounted display:none.
 */

export default function PlannerTab(props) {
  const {

    // App-shell state (read-only) — confirmed shared per plan #190
    status, setStatus, config, setConfig, user, activeTab, addToast,
    // 21 truly-shared states from plan #190
    lessonPlan, setLessonPlan,
    generatedAssignment, setGeneratedAssignment,
    assessmentConfig, setAssessmentConfig,
    selectedStandards, setSelectedStandards,
    unitConfig, setUnitConfig,
    standards, setStandards,
    assignment, setAssignment,
    uploadedDocs, setUploadedDocs,
    generatedAssessment, setGeneratedAssessment,
    rubric, setRubric,
    globalAINotes, setGlobalAINotes,
    supportDocs, setSupportDocs,
    savedAssignments, setSavedAssignments,
    teacherClasses, setTeacherClasses,
    periods, setPeriods,
    savedAssignmentData, setSavedAssignmentData,
    contentOnly, setContentOnly,
    assessmentTemplates, setAssessmentTemplates,
    uploadingTemplate, setUploadingTemplate,
    // ~91 Planner-only states (still in App until PR 2-7) — full list
    // discovered by build-fail iteration. Initial set:
    plannerMode, setPlannerMode,
    // plannerLoading, lessonVariations, brainstormIdeas, selectedIdea,
    // brainstormLoading, assignmentQuestionCounts moved into PlannerTab
    // in PR 8d (lesson-gen big cluster).
    // previewResults moved into PlannerTab in PR 8c.
    // docUploading moved into PlannerTab in PR 8b.
    // matchingInProgress + matchResults moved into PlannerTab in PR 8a.
    assessmentLoading, setAssessmentLoading,
    gradingAssessment, setGradingAssessment,
    savingAssessment, setSavingAssessment,
    saveAssessmentName, setSaveAssessmentName,
    assessmentAnswers, setAssessmentAnswers,
    assessmentGradingResults, setAssessmentGradingResults,
    selectedSources, setSelectedSources,
    selectedAssessmentResults, setSelectedAssessmentResults,
    publishedAssessments, setPublishedAssessments,
    loadingPublished, setLoadingPublished,
    inProgressDrafts, setInProgressDrafts,
    loadingResults, setLoadingResults,
    sharedResources, setSharedResources,
    loadingSharedResources, setLoadingSharedResources,
    contentSubmissionsGroups, setContentSubmissionsGroups,
    savedAssessments, setSavedAssessments,
    loadingSavedAssessments, setLoadingSavedAssessments,
    savedLessons, setSavedLessons,
    allTeacherTags, setAllTeacherTags,
    selectedTagFilter, setSelectedTagFilter,
    // newUnitModal + tagDropdownOpenFor moved into PlannerTab in PR 7e.
    // (singular selectedQuestion / setSelectedQuestion removed — Codex Round 1: phantom names not declared in App.jsx)
    // Handlers and constants — added by build-fail iteration. Initial:
    loadAssignment, saveAssignmentConfig,

    // PR 1 Codex Round 1 additions (missing closures):
    getActiveAssignment, setActiveAssignment,
    studentAccommodations,
    domainNameMap, getDomains, scrollToDomain, toggleStandard, standardsScrollRef, assessmentStandardsScrollRef, deleteSavedAssessment, loadSavedAssessment, saveAssessmentHandler, generateAssessmentHandler, gradeAssessmentAnswersHandler, exportAssessmentHandler, exportAssessmentForPlatformHandler, deletePublishedAssessment, toggleAssessmentStatus, fetchAssessmentResults, fetchPublishedAssessments, fetchSavedAssessments, fetchSavedLessons, fetchSharedResources, fetchTeacherClasses, fetchTeacherTags, handleDeleteAllSharedResources, handleDeleteSharedResource, getTotalQuestionCount, distributeDOK, distributePoints, distributeQuestions, redistributePoints, exportLessonPlanHandler, getSubjectSectionDefaults, itemMatchesTagFilter, setActiveTab, setLoadedAssignmentName,

  } = props;

  /*
   * `plannerMode` stays in App because TutorialOverlay (rendered at App
   * level, App.jsx:4982) drives tutorial steps that flip Planner sub-modes
   * via setPlannerMode. We keep it App-level rather than building a
   * request/response bridge for the tutorial. fetchTeacherClasses,
   * addToast, and activeTab also remain App-shell props.
   */
  /*
   * Save Lesson modal slice — moved into PlannerTab in PR 6b of the
   * Planner extraction sprint. The 3 modal states + the modal block at
   * the bottom of this file (rendered globally before — App.jsx:7853-
   * 7956) all live here now. `savedUnits` is no longer a state — it's
   * derived inline from `savedLessons.units` (which remains a truly-
   * shared App-shell prop) since they were always isomorphic.
   */
  const [showSaveLesson, setShowSaveLesson] = useState(false);
  const [saveLessonUnit, setSaveLessonUnit] = useState('');
  const [newUnitName, setNewUnitName] = useState('');
  const savedUnits = Object.keys((savedLessons && savedLessons.units) || {});

  /*
   * AttemptDrawer slice — moved from App.jsx in PR 7a of the Planner
   * extraction sprint. Smallest contained unit in the publish/share/
   * drawer cluster. Per plan #190 Task 7.
   */
  const [attemptDrawerStudent, setAttemptDrawerStudent] = useState(null);

  // showPlatformExport — moved into PlannerTab in PR 7b. Only truly-clean
  // state remaining in the assessment/publish cluster (zero App-level usage).
  const [showPlatformExport, setShowPlatformExport] = useState(false);

  /*
   * Publish cluster — moved from App in PR 7c of the Planner extraction
   * sprint. 7 useStates + 4 handlers + 2 modal blocks (PublishContentModal,
   * PublishedAssessmentModal). Per plan #190 Task 7's directive that these
   * globally-rendered modals + their state ownership belong to the planner
   * workflow.
   *
   * studentAccommodations stays in App as a prop (used by 3 tabs).
   * teacherClasses, periods, config, addToast, fetchTeacherClasses,
   * fetchPublishedAssessments, fetchSharedResources, fetchTeacherTags,
   * getActiveAssignment, generatedAssignment, lessonPlan are all already
   * App-shell props.
   */
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

  /*
   * ShareWithClasses cluster — moved from App in PR 7d of the Planner
   * extraction sprint. 4 useStates + 2 handlers + 1 modal block.
   * teacherClasses, setTeacherClasses, addToast, unitConfig, api are
   * already App-shell props/imports.
   */
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareModalContent, setShareModalContent] = useState(null);
  const [shareModalSelected, setShareModalSelected] = useState([]);
  const [shareModalSharing, setShareModalSharing] = useState(false);

  async function shareWithClass(content, contentType, title) {
    var classes = teacherClasses;
    if (!classes || classes.length === 0) {
      try {
        var data = await api.listClasses();
        if (data.classes && data.classes.length > 0) {
          classes = data.classes;
          setTeacherClasses(classes);
        }
      } catch (e) { /* fall through to check below */ }
    }
    if (!classes || classes.length === 0) {
      addToast('No classes found. Sync your roster first.', 'warning');
      return;
    }
    if (classes.length === 1) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: classes[0].id,
            content: content,
            content_type: contentType,
            title: title,
            settings: { unit_name: unitConfig.title || '' },
          }),
        });
        var result = await resp.json();
        if (result.error) {
          addToast(result.error, 'error');
        } else {
          addToast('Shared "' + title + '" with ' + classes[0].name, 'success');
        }
      } catch (err) {
        addToast('Failed to share: ' + err.message, 'error');
      }
      return;
    }
    setShareModalContent({ content: content, contentType: contentType, title: title, unitName: unitConfig.title || '' });
    setShareModalSelected([]);
    setShowShareModal(true);
  }

  async function executeShareWithClasses() {
    if (!shareModalContent || shareModalSelected.length === 0) return;
    setShareModalSharing(true);
    var successes = 0;
    var failures = 0;
    for (var i = 0; i < shareModalSelected.length; i++) {
      try {
        var resp = await fetch('/api/publish-to-class', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            class_id: shareModalSelected[i],
            content: shareModalContent.content,
            content_type: shareModalContent.contentType,
            title: shareModalContent.title,
            settings: { unit_name: shareModalContent.unitName || '' },
          }),
        });
        var result = await resp.json();
        if (result.error) {
          failures++;
        } else {
          successes++;
        }
      } catch (err) {
        failures++;
      }
    }
    setShareModalSharing(false);
    setShowShareModal(false);
    if (failures === 0) {
      addToast('Shared "' + shareModalContent.title + '" with ' + successes + ' class' + (successes === 1 ? '' : 'es'), 'success');
    } else if (successes > 0) {
      addToast('Shared with ' + successes + ' class' + (successes === 1 ? '' : 'es') + ', ' + failures + ' failed', 'warning');
    } else {
      addToast('Failed to share with any classes', 'error');
    }
  }

  /*
   * NewUnit + tag-cluster — moved from App.jsx in PR 7e of the Planner
   * extraction sprint. 2 useStates (newUnitModal + tagDropdownOpenFor),
   * 4 handlers (handleSetUnit/handleSetTags/handleAddTag/handleRemoveTag),
   * the renderTagRow helper (~140 LOC), and the NewUnitModal JSX block all
   * live here. allTeacherTags + setSharedResources + setPublishedAssessments
   * + addToast + fetchTeacherTags remain App-shell props (other consumers).
   * Codex Round 1 of PR 7e expanded this slice to include renderTagRow +
   * the 3 tag handlers because renderTagRow closes over setNewUnitModal +
   * the handlers; moving newUnitModal alone would orphan all the setter
   * call sites inside renderTagRow when it ran in PlannerTab.
   */
  const [newUnitModal, setNewUnitModal] = useState(null); // { resourceId, value, mode, existingTags } or null
  const [tagDropdownOpenFor, setTagDropdownOpenFor] = useState(null); // content_id or null

  var handleSetUnit = async function(contentId, unitName, onSuccess) {
    try {
      var data = await api.updateSharedResourceUnit(contentId, unitName);
      if (data && data.success) {
        if (onSuccess) onSuccess(unitName);
        addToast(unitName ? ('Set unit to "' + unitName + '"') : 'Cleared unit', 'success');
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to set unit: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleSetTags = async function(contentId, tags, onSuccess) {
    try {
      var data = await api.setContentTags(contentId, tags);
      if (data && data.success) {
        if (onSuccess) onSuccess(data.tags || tags);
        fetchTeacherTags();
      }
    } catch (e) {
      addToast('Failed to update tags: ' + (e.message || 'unknown'), 'error');
    }
  };

  var handleAddTag = function(contentId, existingTags, newTag, onSuccess) {
    var tags = (existingTags || []).slice();
    if (tags.indexOf(newTag) !== -1) return;
    tags.push(newTag);
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Added tag "' + newTag + '"', 'success');
    });
  };

  var handleRemoveTag = function(contentId, existingTags, tagToRemove, onSuccess) {
    var tags = (existingTags || []).filter(function(t) { return t !== tagToRemove; });
    handleSetTags(contentId, tags, function(saved) {
      if (onSuccess) onSuccess(saved);
      addToast('Removed tag "' + tagToRemove + '"', 'success');
    });
  };

  // Reusable inline tag row for published content
  var renderTagRow = function(item, onUpdate) {
    var itemId = item.id || item.content_id;
    if (!itemId) return null;
    var isDropdownOpen = tagDropdownOpenFor === itemId;
    var unitName = item.unit_name || '';
    var tags = item.tags || [];
    var availableTags = allTeacherTags.filter(function(t) {
      return t !== unitName && tags.indexOf(t) === -1;
    });

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", marginTop: "8px", position: "relative" }}>
        {unitName ? (
          <span
            onClick={function(e) {
              e.stopPropagation();
              handleSetUnit(itemId, '', function() { onUpdate({ unit_name: '' }); });
            }}
            style={{
              display: "inline-flex", alignItems: "center", gap: "4px",
              padding: "3px 10px", borderRadius: "12px",
              background: "rgba(99,102,241,0.15)", color: "var(--accent-primary)",
              fontSize: "0.72rem", fontWeight: 600, cursor: "pointer",
              border: "1px solid rgba(99,102,241,0.3)",
            }}
            title="Click to remove unit"
          >
            <Icon name="Folder" size={11} />
            {unitName}
          </span>
        ) : (
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontStyle: "italic" }}>
            No unit
          </span>
        )}
        {tags.map(function(t) {
          return (
            <span
              key={t}
              onClick={function(e) {
                e.stopPropagation();
                handleRemoveTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
              }}
              style={{
                padding: "3px 8px", borderRadius: "10px",
                background: "var(--glass-bg)", color: "var(--text-secondary)",
                fontSize: "0.7rem", cursor: "pointer",
                border: "1px solid var(--glass-border)",
              }}
              title="Click to remove tag"
            >
              {t}
            </span>
          );
        })}
        <button
          onClick={function(e) {
            e.stopPropagation();
            setTagDropdownOpenFor(isDropdownOpen ? null : itemId);
          }}
          style={{
            padding: "2px 8px", borderRadius: "10px",
            background: "var(--glass-bg)", color: "var(--text-secondary)",
            fontSize: "0.75rem", cursor: "pointer",
            border: "1px dashed var(--glass-border)",
          }}
          title="Add tag"
        >
          + Tag
        </button>
        {isDropdownOpen && (
          <div
            onClick={function(e) { e.stopPropagation(); }}
            style={{
              position: "absolute", top: "100%", left: 0, marginTop: "4px",
              background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)",
              borderRadius: "10px", padding: "8px", minWidth: "220px", maxHeight: "280px",
              overflowY: "auto", zIndex: 50,
              boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
            }}
          >
            {!unitName && allTeacherTags.length > 0 && (
              <div style={{ marginBottom: "6px" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>Set as unit</div>
                {allTeacherTags.slice(0, 5).map(function(t) {
                  return (
                    <div
                      key={'u-' + t}
                      onClick={function() {
                        setTagDropdownOpenFor(null);
                        handleSetUnit(itemId, t, function() { onUpdate({ unit_name: t }); });
                      }}
                      style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", display: "flex", alignItems: "center", gap: "6px" }}
                      onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                      onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <Icon name="Folder" size={12} style={{ color: "var(--accent-primary)" }} />
                      {t}
                    </div>
                  );
                })}
                <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
              </div>
            )}
            <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", padding: "4px 8px", letterSpacing: "0.05em" }}>
              {availableTags.length > 0 ? 'Add existing tag' : 'No other tags'}
            </div>
            {availableTags.map(function(t) {
              return (
                <div
                  key={'t-' + t}
                  onClick={function() {
                    setTagDropdownOpenFor(null);
                    handleAddTag(itemId, tags, t, function(saved) { onUpdate({ tags: saved }); });
                  }}
                  style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer" }}
                  onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
                  onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
                >
                  {t}
                </div>
              );
            })}
            <div style={{ height: "1px", background: "var(--glass-border)", margin: "6px 0" }} />
            <div
              onClick={function() {
                setTagDropdownOpenFor(null);
                setNewUnitModal({ resourceId: itemId, value: '', mode: unitName ? 'tag' : 'unit', existingTags: tags });
              }}
              style={{ padding: "6px 10px", fontSize: "0.8rem", borderRadius: "6px", cursor: "pointer", color: "var(--accent-primary)", fontWeight: 600 }}
              onMouseEnter={function(e) { e.currentTarget.style.background = 'var(--glass-bg)'; }}
              onMouseLeave={function(e) { e.currentTarget.style.background = 'transparent'; }}
            >
              + Create new tag...
            </div>
          </div>
        )}
      </div>
    );
  };

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

  /*
   * Lesson-core display states — moved into PlannerTab in PR 6a of the
   * Planner extraction sprint. Per plan #190 Task 6 (clean subset only;
   * the 10 lesson-gen-coupled states with App-level handler couplings
   * defer to a future PR).
   */
  const [expandedStandards, setExpandedStandards] = useState([]);
  const [assignmentSectionsOpen, setAssignmentSectionsOpen] = useState(false);
  const [previewShowAnswers, setPreviewShowAnswers] = useState(true);

  /*
   * Question-editing slice — owned locally by PlannerTab (PR 5 of the
   * Planner extraction sprint). Per plan #190 Task 5.
   *
   * The 6 helpers below (toggleQuestionSelect, selectAllQuestions,
   * saveEditedQuestion, deleteSelectedQuestions, regenerateSelectedQuestions,
   * regenerateOneQuestion) consume getActiveAssignment + setActiveAssignment
   * via props — those wrappers stay in App because the publish flow at
   * App.jsx:3681 + 3757 still calls them; they get extracted in PR 7.
   *
   * The reset useEffect below combines the two App-level reset effects
   * (formerly App.jsx:1212-1218 and App.jsx:1544-1549) into one with a
   * 3-element dep array — semantically equivalent because the body is
   * idempotent and only acts when the underlying assignment ref changes.
   */
  const {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  } = useQuestionEditing({
    getActiveAssignment, setActiveAssignment, addToast, config, unitConfig,
  });
  const [sectionsDropdownOpen, setSectionsDropdownOpen] = useState(false);

  useEffect(() => {
    setEditMode(false);
    setSelectedQuestions(new Set());
    setEditingQuestion(null);
    setRegeneratingQuestions(new Set());
  }, [lessonPlan, generatedAssignment, generatedAssessment]);

  /*
   * Matching cluster — moved from App.jsx in PR 8a of the Planner
   * extraction sprint (deferred-cluster #2 from PR 7e's session).
   * 2 useStates + 2 handlers. removeUploadedDoc moves with the cluster
   * because it calls setMatchResults(null) on doc removal — without it
   * the matchResults setter would be orphaned in App.
   *
   * uploadedDocs + setUploadedDocs + selectedStandards + standards +
   * config + addToast remain App-shell props (other consumers).
   */
  const [matchingInProgress, setMatchingInProgress] = useState(false);
  const [matchResults, setMatchResults] = useState(null);

  const handleMatchStandards = async () => {
    if (uploadedDocs.length === 0 || !config.subject || !config.grade_level) {
      addToast("Upload documents and set subject/grade first", "warning");
      return;
    }
    setMatchingInProgress(true);
    try {
      const combinedText = uploadedDocs.map(d => d.text).join("\n\n");
      const result = await api.alignDocumentToStandards({ documentText: combinedText, subject: config.subject, grade: config.grade_level });
      setMatchResults(result);
      if (result && result.matched_standards) {
        const matchedCodes = (result.matched_standards || []).filter(a => a.confidence >= 0.4).map(a => a.code);
        // Alert if currently selected standards conflict with document content
        if (selectedStandards.length > 0 && matchedCodes.length > 0) {
          const conflicts = selectedStandards.filter(code => !matchedCodes.includes(code));
          if (conflicts.length > 0) {
            addToast("Heads up: " + conflicts.length + " selected standard" + (conflicts.length > 1 ? "s" : "") + " (" + conflicts.join(", ") + ") may not align with your uploaded documents", "warning", 8000);
          }
        }
        if (matchedCodes.length > 0) {
          addToast(matchedCodes.length + " matching standards found — click to select", "info");
        } else {
          addToast("No strong standard matches found in uploaded documents", "warning");
        }
      }
    } catch (err) {
      addToast("Matching error: " + err.message, "error");
    } finally {
      setMatchingInProgress(false);
    }
  };

  const removeUploadedDoc = (index) => {
    setUploadedDocs(prev => prev.filter((_, i) => i !== index));
    setMatchResults(null);
  };

  /*
   * Preview cluster — moved from App.jsx in PR 8c of the Planner
   * extraction sprint. 1 useState + 1 reset useEffect. The effect
   * fires on lessonPlan or generatedAssignment ref change, clearing
   * stale preview results. lessonPlan + generatedAssignment remain
   * App-shell props.
   */
  const [previewResults, setPreviewResults] = useState(null);

  useEffect(() => {
    setPreviewResults(null);
  }, [lessonPlan, generatedAssignment]);

  /*
   * Lesson-gen big cluster — moved from App.jsx in PR 8d of the
   * Planner extraction sprint (deferred-cluster #2 final move).
   * 6 useStates + 2 handlers (brainstormIdeasHandler, generateLessonPlan)
   * + 2 effects (load-standards, subject-change-assignmentQuestionCounts).
   *
   * The dead-code generateAssignmentFromLessonHandler (no call sites
   * anywhere — orphaned) and its private states (assignmentLoading,
   * assignmentType) were also removed from App.jsx in this PR.
   *
   * App-shell deps reachable via props: config, addToast, selectedStandards,
   * uploadedDocs, standards, unitConfig, contentOnly, setLessonPlan,
   * setStandards, activeTab, getSubjectSectionDefaults (newly added prop).
   */
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [lessonVariations, setLessonVariations] = useState([]);
  const [brainstormIdeas, setBrainstormIdeas] = useState([]);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [brainstormLoading, setBrainstormLoading] = useState(false);
  const [assignmentQuestionCounts, setAssignmentQuestionCounts] = useState({
    multiple_choice: 4, short_answer: 2, math_computation: 0,
    geometry_visual: 0, graphing: 0, data_analysis: 0,
    extended_writing: 1, vocabulary: 0, true_false: 0, florida_fast: 0,
  });

  // Load standards when planner tab is active.
  useEffect(() => {
    if (activeTab === "planner" && config.subject) {
      setPlannerLoading(true);
      api
        .getStandards({
          state: config.state || "FL",
          grade: config.grade_level || "7",
          subject: config.subject,
        })
        .then((data) => {
          console.log("Standards loaded:", data);
          setStandards(data.standards || []);
        })
        .catch((e) => {
          console.error("Error loading standards:", e);
          setStandards([]);
        })
        .finally(() => {
          setPlannerLoading(false);
        });
    }
  }, [config.state, config.grade_level, config.subject, activeTab]);

  // Subject-change effect (assignmentQuestionCounts portion). The
  // assessmentConfig portion of the original combined effect remains in
  // App.jsx — they were independent halves merged by convenience.
  useEffect(() => {
    if (config.subject && getSubjectSectionDefaults) {
      var newCats = getSubjectSectionDefaults(config.subject);
      var assignTotal = 10;
      var enabledCount = Object.values(newCats).filter(Boolean).length || 1;
      var assignNumeric = Object.fromEntries(Object.entries(newCats).map(function(e) { return [e[0], e[1] ? Math.max(1, Math.round(assignTotal / enabledCount)) : 0]; }));
      setAssignmentQuestionCounts(assignNumeric);
    }
  }, [config.subject]);

  const brainstormIdeasHandler = async () => {
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
    setBrainstormLoading(true);
    setBrainstormIdeas([]);
    setSelectedIdea(null);
    setLessonPlan(null);
    setLessonVariations([]);
    try {
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        if (!std) return code;
        let text = std.code + ": " + std.benchmark;
        if (std.vocabulary && std.vocabulary.length > 0) {
          text += " | Key Vocabulary: " + std.vocabulary.join(", ");
        }
        if (std.learning_targets && std.learning_targets.length > 0) {
          text += " | Learning Targets: " + std.learning_targets.join("; ");
        }
        return text;
      });
      const data = await api.brainstormLessonIdeas({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
          requirements: unitConfig.requirements || "",
        },
      });
      if (data.error)
        addToast("Note: Using sample ideas - " + data.error, "info");
      setBrainstormIdeas(data.ideas || []);
      if (data.usage) addToast("Brainstorm cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
    } catch (e) {
      addToast("Error brainstorming: " + e.message, "error");
    } finally {
      setBrainstormLoading(false);
    }
  };

  const generateLessonPlan = async (generateVariations = false) => {
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
    setPlannerLoading(true);
    setLessonVariations([]);
    try {
      const fullStandards = selectedStandards.map((code) => {
        const std = standards.find((s) => s.code === code);
        if (!std) return code;
        let text = std.code + ": " + std.benchmark;
        if (std.vocabulary && std.vocabulary.length > 0) {
          text += " | Key Vocabulary: " + std.vocabulary.join(", ");
        }
        if (std.learning_targets && std.learning_targets.length > 0) {
          text += " | Learning Targets: " + std.learning_targets.join("; ");
        }
        return text;
      });
      const standardCodes = selectedStandards.join(", ");
      const autoTitle =
        unitConfig.title || (selectedIdea ? selectedIdea.title : "");

      const referenceDocs = uploadedDocs.map(doc => ({ filename: doc.filename, text: doc.text }));

      const data = await api.generateLessonPlan({
        standards: fullStandards,
        config: {
          state: config.state || "FL",
          grade: config.grade_level,
          subject: config.subject,
          availableTools: config.availableTools || [],
          ...unitConfig,
          title: autoTitle,
          standardCodes: standardCodes,
          sectionCategories: unitConfig.type === "Assignment" ? Object.fromEntries(Object.entries(assignmentQuestionCounts).map(function(e) { return [e[0], e[1] > 0]; })) : undefined,
          questionTypeCounts: unitConfig.type === "Assignment" ? assignmentQuestionCounts : undefined,
          contentOnly: contentOnly,
        },
        selectedIdea: selectedIdea,
        generateVariations: generateVariations,
        referenceDocs: referenceDocs,
      });
      if (data.error) addToast("Error: " + data.error, "error");
      else if (data.variations) {
        setLessonVariations(data.variations);
        addToast(
          `Generated ${data.variations.length} ${(unitConfig.type || 'lesson plan').toLowerCase()} variations!`,
          "success",
        );
      } else {
        setLessonPlan(data.plan || data);
      }
      if (data.usage) addToast("Generation cost: " + data.usage.cost_display + " (" + data.usage.total_tokens.toLocaleString() + " tokens)", "info");
    } catch (e) {
      addToast("Error generating plan: " + e.message, "error");
    } finally {
      setPlannerLoading(false);
    }
  };

  /*
   * Doc upload cluster — moved from App.jsx in PR 8b of the Planner
   * extraction sprint. 1 useState + 1 handler. uploadedDocs +
   * setUploadedDocs + addToast + api remain App-shell props/imports.
   */
  const [docUploading, setDocUploading] = useState(false);

  const handleDocUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setDocUploading(true);
    try {
      for (const file of files) {
        const textResult = await api.extractTextFromFile(file);
        if (textResult && textResult.text) {
          setUploadedDocs(prev => [...prev, {
            filename: file.name,
            size: file.size,
            text: textResult.text,
          }]);
        } else {
          addToast("Could not extract text from " + file.name, "warning");
        }
      }
    } catch (err) {
      addToast("Upload error: " + err.message, "error");
    } finally {
      setDocUploading(false);
      e.target.value = "";
    }
  };

  // Dashboard mode triggers a teacher-classes fetch — moved from App.jsx PR 3.
  useEffect(() => {
    if (plannerMode === "dashboard") {
      fetchTeacherClasses();
    }
  }, [plannerMode]);

  return (
                <div data-tutorial="planner-card" className="fade-in">
                  {/* Mode Toggle */}
                  <div
                    data-tutorial="planner-modes"
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "20px",
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      onClick={() => setPlannerMode("lesson")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "lesson"
                            ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "lesson"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "lesson" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="BookOpen" size={18} />
                      Lesson Planning
                    </button>
                    <button
                      onClick={() => setPlannerMode("assessment")}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "assessment"
                            ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "assessment"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "assessment" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="ClipboardCheck" size={18} />
                      Assessment Generator
                    </button>
                    <button
                      onClick={() => {
                        setPlannerMode("dashboard");
                        fetchPublishedAssessments();
                        fetchSharedResources();
                        fetchTeacherTags();
                        fetchSavedAssessments();
                      }}
                      className="btn"
                      style={{
                        padding: "10px 20px",
                        background:
                          plannerMode === "dashboard"
                            ? "linear-gradient(135deg, #22c55e, #16a34a)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "dashboard"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "dashboard" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Users" size={18} />
                      Student Portal
                    </button>
                    <button
                      onClick={() => setPlannerMode("calendar")}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "calendar"
                            ? "linear-gradient(135deg, #f59e0b, #d97706)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "calendar"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "calendar" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Calendar" size={18} />
                      Calendar
                    </button>
                    <button
                      onClick={() => { setPlannerMode("tools"); }}
                      style={{
                        padding: "10px 20px",
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        background:
                          plannerMode === "tools"
                            ? "linear-gradient(135deg, #06b6d4, #0891b2)"
                            : "var(--glass-bg)",
                        border:
                          plannerMode === "tools"
                            ? "none"
                            : "1px solid var(--glass-border)",
                        color: plannerMode === "tools" ? "#fff" : "var(--text-secondary)",
                        fontWeight: 600,
                        borderRadius: "10px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="Wrench" size={18} />
                      Tools
                    </button>
                  </div>

                  {/* Lesson Planning Mode */}
                  {plannerMode === "lesson" && (
                    <PlannerLesson
                      addToast={addToast}
                      assignment={assignment}
                      assignmentQuestionCounts={assignmentQuestionCounts}
                      assignmentSectionsOpen={assignmentSectionsOpen}
                      brainstormIdeas={brainstormIdeas}
                      brainstormIdeasHandler={brainstormIdeasHandler}
                      brainstormLoading={brainstormLoading}
                      config={config}
                      contentOnly={contentOnly}
                      deleteSelectedQuestions={deleteSelectedQuestions}
                      docUploading={docUploading}
                      domainNameMap={domainNameMap}
                      editMode={editMode}
                      editingQuestion={editingQuestion}
                      expandedStandards={expandedStandards}
                      exportLessonPlanHandler={exportLessonPlanHandler}
                      generateLessonPlan={generateLessonPlan}
                      generatedAssignment={generatedAssignment}
                      getDomains={getDomains}
                      getTotalQuestionCount={getTotalQuestionCount}
                      handleDocUpload={handleDocUpload}
                      handleMatchStandards={handleMatchStandards}
                      lessonPlan={lessonPlan}
                      lessonVariations={lessonVariations}
                      matchResults={matchResults}
                      matchingInProgress={matchingInProgress}
                      plannerLoading={plannerLoading}
                      previewResults={previewResults}
                      previewShowAnswers={previewShowAnswers}
                      publishAssessmentHandler={publishAssessmentHandler}
                      publishingAssessment={publishingAssessment}
                      regenerateOneQuestion={regenerateOneQuestion}
                      regenerateSelectedQuestions={regenerateSelectedQuestions}
                      regeneratingQuestions={regeneratingQuestions}
                      removeUploadedDoc={removeUploadedDoc}
                      saveEditedQuestion={saveEditedQuestion}
                      scrollToDomain={scrollToDomain}
                      selectAllQuestions={selectAllQuestions}
                      selectedIdea={selectedIdea}
                      selectedQuestions={selectedQuestions}
                      selectedStandards={selectedStandards}
                      setActiveTab={setActiveTab}
                      setAssignment={setAssignment}
                      setAssignmentQuestionCounts={setAssignmentQuestionCounts}
                      setAssignmentSectionsOpen={setAssignmentSectionsOpen}
                      setBrainstormIdeas={setBrainstormIdeas}
                      setContentOnly={setContentOnly}
                      setEditMode={setEditMode}
                      setEditingQuestion={setEditingQuestion}
                      setExpandedStandards={setExpandedStandards}
                      setGeneratedAssignment={setGeneratedAssignment}
                      setLessonPlan={setLessonPlan}
                      setLessonVariations={setLessonVariations}
                      setLoadedAssignmentName={setLoadedAssignmentName}
                      setPlannerMode={setPlannerMode}
                      setPreviewResults={setPreviewResults}
                      setPreviewShowAnswers={setPreviewShowAnswers}
                      setSelectedIdea={setSelectedIdea}
                      setSelectedQuestions={setSelectedQuestions}
                      setSelectedStandards={setSelectedStandards}
                      setShowSaveLesson={setShowSaveLesson}
                      setUnitConfig={setUnitConfig}
                      standards={standards}
                      standardsScrollRef={standardsScrollRef}
                      toggleQuestionSelect={toggleQuestionSelect}
                      toggleStandard={toggleStandard}
                      unitConfig={unitConfig}
                      uploadedDocs={uploadedDocs}
                      user={user}
                    />
                  )}

                  {/* Assessment Generator Mode */}
                  {plannerMode === "assessment" && (
                    <PlannerAssessment
                      assessmentAnswers={assessmentAnswers}
                      assessmentConfig={assessmentConfig}
                      assessmentLoading={assessmentLoading}
                      assessmentStandardsScrollRef={assessmentStandardsScrollRef}
                      assignment={assignment}
                      deleteSelectedQuestions={deleteSelectedQuestions}
                      distributeDOK={distributeDOK}
                      distributePoints={distributePoints}
                      distributeQuestions={distributeQuestions}
                      domainNameMap={domainNameMap}
                      editMode={editMode}
                      editingQuestion={editingQuestion}
                      exportAssessmentForPlatformHandler={exportAssessmentForPlatformHandler}
                      exportAssessmentHandler={exportAssessmentHandler}
                      fetchSavedLessons={fetchSavedLessons}
                      generateAssessmentHandler={generateAssessmentHandler}
                      generatedAssessment={generatedAssessment}
                      getDomains={getDomains}
                      getTotalQuestionCount={getTotalQuestionCount}
                      gradeAssessmentAnswersHandler={gradeAssessmentAnswersHandler}
                      gradingAssessment={gradingAssessment}
                      periods={periods}
                      plannerLoading={plannerLoading}
                      previewShowAnswers={previewShowAnswers}
                      publishAssessmentHandler={publishAssessmentHandler}
                      publishingAssessment={publishingAssessment}
                      redistributePoints={redistributePoints}
                      regenerateOneQuestion={regenerateOneQuestion}
                      regenerateSelectedQuestions={regenerateSelectedQuestions}
                      regeneratingQuestions={regeneratingQuestions}
                      saveAssessmentHandler={saveAssessmentHandler}
                      saveAssessmentName={saveAssessmentName}
                      saveEditedQuestion={saveEditedQuestion}
                      savedAssignmentData={savedAssignmentData}
                      savedAssignments={savedAssignments}
                      savedLessons={savedLessons}
                      savingAssessment={savingAssessment}
                      scrollToDomain={scrollToDomain}
                      sectionsDropdownOpen={sectionsDropdownOpen}
                      selectAllQuestions={selectAllQuestions}
                      selectedQuestions={selectedQuestions}
                      selectedSources={selectedSources}
                      selectedStandards={selectedStandards}
                      setAssessmentAnswers={setAssessmentAnswers}
                      setAssessmentConfig={setAssessmentConfig}
                      setEditMode={setEditMode}
                      setEditingQuestion={setEditingQuestion}
                      setGeneratedAssessment={setGeneratedAssessment}
                      setSaveAssessmentName={setSaveAssessmentName}
                      setSectionsDropdownOpen={setSectionsDropdownOpen}
                      setSelectedQuestions={setSelectedQuestions}
                      setSelectedSources={setSelectedSources}
                      setSelectedStandards={setSelectedStandards}
                      setShowPlatformExport={setShowPlatformExport}
                      showPlatformExport={showPlatformExport}
                      standards={standards}
                      toggleQuestionSelect={toggleQuestionSelect}
                      toggleStandard={toggleStandard}
                      uploadedDocs={uploadedDocs}
                    />
                  )}

                                    {/* Student Portal Dashboard */}
                  {plannerMode === "dashboard" && (
                    <PlannerDashboard
                      addToast={addToast}
                      allTeacherTags={allTeacherTags}
                      contentSubmissionsGroups={contentSubmissionsGroups}
                      deletePublishedAssessment={deletePublishedAssessment}
                      deleteSavedAssessment={deleteSavedAssessment}
                      fetchAssessmentResults={fetchAssessmentResults}
                      fetchPublishedAssessments={fetchPublishedAssessments}
                      fetchSavedAssessments={fetchSavedAssessments}
                      fetchSharedResources={fetchSharedResources}
                      fetchTeacherClasses={fetchTeacherClasses}
                      fetchTeacherTags={fetchTeacherTags}
                      handleDeleteAllSharedResources={handleDeleteAllSharedResources}
                      handleDeleteSharedResource={handleDeleteSharedResource}
                      inProgressDrafts={inProgressDrafts}
                      itemMatchesTagFilter={itemMatchesTagFilter}
                      loadSavedAssessment={loadSavedAssessment}
                      loadingPublished={loadingPublished}
                      loadingResults={loadingResults}
                      loadingSavedAssessments={loadingSavedAssessments}
                      loadingSharedResources={loadingSharedResources}
                      publishedAssessments={publishedAssessments}
                      renderTagRow={renderTagRow}
                      savedAssessments={savedAssessments}
                      selectedAssessmentResults={selectedAssessmentResults}
                      selectedTagFilter={selectedTagFilter}
                      setAttemptDrawerStudent={setAttemptDrawerStudent}
                      setInProgressDrafts={setInProgressDrafts}
                      setPublishedAssessments={setPublishedAssessments}
                      setSelectedAssessmentResults={setSelectedAssessmentResults}
                      setSelectedTagFilter={setSelectedTagFilter}
                      setSharedResources={setSharedResources}
                      sharedResources={sharedResources}
                      teacherClasses={teacherClasses}
                      toggleAssessmentStatus={toggleAssessmentStatus}
                    />
                  )}

                  {/* Calendar Mode */}
                  {plannerMode === "calendar" && (
                    <PlannerCalendar
                      active={activeTab === "planner"}
                      addToast={addToast}
                      savedLessons={savedLessons}
                      supportDocs={supportDocs}
                      setSupportDocs={setSupportDocs}
                    />
                  )}

                  {/* Tools Mode */}
                  {plannerMode === "tools" && (
                    <PlannerTools
                      config={config}
                      lessonPlan={lessonPlan}
                      generatedAssignment={generatedAssignment}
                      globalAINotes={globalAINotes}
                      uploadedDocs={uploadedDocs}
                      addToast={addToast}
                      shareWithClass={shareWithClass}
                    />
                  )}

      {/* AttemptDrawer — moved from App.jsx in PR 7a. */}
      <AttemptDrawer
        student={attemptDrawerStudent}
        onClose={() => setAttemptDrawerStudent(null)}
      />

      {/* PublishContentModal — moved from App.jsx in PR 7c. */}
      <PublishContentModal
        open={showPublishModal}
        onClose={() => setShowPublishModal(false)}
        settings={publishSettings}
        setSettings={setPublishSettings}
        classId={publishClassId}
        setClassId={setPublishClassId}
        teacherClasses={teacherClasses}
        periods={periods}
        onPeriodChange={loadPublishModalStudents}
        modalStudents={publishModalStudents}
        loadingStudents={loadingPublishStudents}
        studentAccommodations={studentAccommodations}
        publishing={publishingAssessment}
        onPublish={confirmPublishAssessment}
      />

      {/* PublishedAssessmentModal — moved from App.jsx in PR 7c. */}
      <PublishedAssessmentModal
        open={publishedAssessmentModal.show}
        onClose={() => setPublishedAssessmentModal({ show: false, joinCode: "", joinLink: "" })}
        joinCode={publishedAssessmentModal.joinCode}
        joinLink={publishedAssessmentModal.joinLink}
        isClassBased={publishedAssessmentModal.isClassBased}
        onCopied={() => addToast("Link copied to clipboard!", "success")}
      />

      {/* ShareWithClassesModal — moved from App.jsx in PR 7d. */}
      <ShareWithClassesModal
        open={showShareModal}
        onClose={() => setShowShareModal(false)}
        content={shareModalContent}
        setContent={setShareModalContent}
        selectedIds={shareModalSelected}
        setSelectedIds={setShareModalSelected}
        sharing={shareModalSharing}
        classes={teacherClasses}
        onShare={executeShareWithClasses}
      />

      {/* New Unit Name Modal — moved from App.jsx in PR 7e (NewUnit + tag cluster). */}
      <NewUnitModal
        open={!!newUnitModal}
        onClose={() => setNewUnitModal(null)}
        value={newUnitModal ? newUnitModal.value : ""}
        setValue={(val) => setNewUnitModal(newUnitModal ? { ...newUnitModal, value: val } : null)}
        mode={newUnitModal ? (newUnitModal.mode || "unit") : "unit"}
        onSubmit={async (val) => {
          if (!newUnitModal) return;
          const rid = newUnitModal.resourceId;
          const mode = newUnitModal.mode || "unit";
          const existing = newUnitModal.existingTags || [];
          setNewUnitModal(null);
          try {
            if (mode === "tag") {
              const data = await api.setContentTags(rid, existing.concat([val]));
              if (data.success) {
                const updatedTags = data.tags || existing.concat([val]);
                setSharedResources((prev) => prev.map((r) => r.id === rid ? { ...r, tags: updatedTags } : r));
                setPublishedAssessments((prev) => prev.map((a) => (a.id === rid || a.join_code === rid) ? { ...a, tags: updatedTags } : a));
                addToast('Added tag "' + val + '"', "success");
                fetchTeacherTags();
              }
            } else {
              const data2 = await api.updateSharedResourceUnit(rid, val);
              if (data2.success) {
                setSharedResources((prev) => prev.map((r) => r.id === rid ? { ...r, unit_name: val } : r));
                setPublishedAssessments((prev) => prev.map((a) => (a.id === rid || a.join_code === rid) ? { ...a, unit_name: val } : a));
                addToast('Set unit to "' + val + '"', "success");
                fetchTeacherTags();
              }
            }
          } catch (err) { addToast("Failed: " + (err.message || "unknown"), "error"); }
        }}
      />

      {/* Save Lesson Modal — moved from App.jsx:7853-7956 in PR 6b. */}
      {showSaveLesson && lessonPlan && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            padding: "20px",
          }}
          onClick={() => setShowSaveLesson(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="glass-card"
            style={{ padding: "30px", width: "400px", maxWidth: "90vw" }}
          >
            <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
              <Icon name="FolderPlus" size={24} style={{ color: "var(--primary)" }} />
              Save Lesson to Unit
            </h3>

            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
              Save this lesson to use it as a content source when generating assessments.
            </p>

            <div style={{ marginBottom: "15px" }}>
              <label className="label">Select Existing Unit</label>
              <select
                className="input"
                value={saveLessonUnit}
                onChange={(e) => {
                  setSaveLessonUnit(e.target.value);
                  if (e.target.value) setNewUnitName('');
                }}
                style={{ width: "100%" }}
              >
                <option value="">-- Select or create new --</option>
                {savedUnits.map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
            </div>

            {!saveLessonUnit && (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">Or Create New Unit</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., Unit 3 - Fractions"
                  value={newUnitName}
                  onChange={(e) => setNewUnitName(e.target.value)}
                  style={{ width: "100%" }}
                />
              </div>
            )}

            <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  setShowSaveLesson(false);
                  setSaveLessonUnit('');
                  setNewUnitName('');
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const unitName = saveLessonUnit || newUnitName;
                  if (!unitName) {
                    addToast('Please select or enter a unit name', 'error');
                    return;
                  }
                  try {
                    const result = await api.saveLessonPlan(lessonPlan, unitName);
                    if (result.error) {
                      addToast('Error: ' + result.error, 'error');
                    } else {
                      setShowSaveLesson(false);
                      setSaveLessonUnit('');
                      setNewUnitName('');
                      fetchSavedLessons();
                      addToast('Lesson saved to "' + unitName + '" — find it in the Resources tab under Content Sources', 'success');
                    }
                  } catch (err) {
                    addToast('Failed to save: ' + err.message, 'error');
                  }
                }}
                className="btn btn-primary"
                disabled={!saveLessonUnit && !newUnitName}
              >
                <Icon name="Save" size={16} />
                Save Lesson
              </button>
            </div>
          </div>
        </div>
      )}

                </div>
  );
}
