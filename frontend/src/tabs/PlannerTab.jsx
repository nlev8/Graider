import React, { useState, useEffect } from "react";
import Icon from "../components/Icon";
import StandardCard from "../components/StandardCard";
import PublishedAssessmentModal from "../components/PublishedAssessmentModal";
import PublishContentModal from "../components/PublishContentModal";
import PlannerCalendar from "../components/PlannerCalendar";
import PlannerTools from "../components/PlannerTools";
import NewUnitModal from "../components/NewUnitModal";
import ShareWithClassesModal from "../components/ShareWithClassesModal";
import AttemptDrawer from "../components/AttemptDrawer";
import PlatformExportMenu from "../components/PlatformExportMenu";
import { AssignmentPlayer } from "../components";
import QuestionEditToolbar from "../components/QuestionEditToolbar";
import QuestionEditOverlay from "../components/QuestionEditOverlay";
import MatchingCards from "../components/MatchingCards";
import * as api from "../services/api";
import { checkRequirementsMismatch } from "../utils/standardsMismatch";

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
  const [editMode, setEditMode] = useState(false);
  const [selectedQuestions, setSelectedQuestions] = useState(new Set());
  const [editingQuestion, setEditingQuestion] = useState(null); // "sIdx-qIdx" key
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());
  const [sectionsDropdownOpen, setSectionsDropdownOpen] = useState(false);

  useEffect(() => {
    setEditMode(false);
    setSelectedQuestions(new Set());
    setEditingQuestion(null);
    setRegeneratingQuestions(new Set());
  }, [lessonPlan, generatedAssignment, generatedAssessment]);

  const toggleQuestionSelect = (qKey) => {
    setSelectedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(qKey)) next.delete(qKey);
      else next.add(qKey);
      return next;
    });
  };

  const selectAllQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const keys = new Set();
    a.sections.forEach((s, sIdx) => {
      (s.questions || []).forEach((_, qIdx) => keys.add(sIdx + "-" + qIdx));
    });
    setSelectedQuestions(keys);
  };

  const saveEditedQuestion = (sIdx, qIdx, updatedQuestion) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const copy = JSON.parse(JSON.stringify(a));
    if (copy.sections[sIdx]?.questions?.[qIdx]) {
      updatedQuestion.number = copy.sections[sIdx].questions[qIdx].number;
      copy.sections[sIdx].questions[qIdx] = updatedQuestion;
      copy.sections[sIdx].points = copy.sections[sIdx].questions.reduce(
        (sum, q) => sum + (q.points || 0), 0
      );
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);
      setActiveAssignment(copy);
    }
    setEditingQuestion(null);
    addToast("Question updated", "success");
  };

  const deleteSelectedQuestions = () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;
    const copy = JSON.parse(JSON.stringify(a));
    const deleteCount = selectedQuestions.size;

    copy.sections.forEach((section, sIdx) => {
      section.questions = (section.questions || []).filter(
        (_, qIdx) => !selectedQuestions.has(sIdx + "-" + qIdx)
      );
      section.questions.forEach((q, i) => { q.number = i + 1; });
      section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
    });

    copy.sections = copy.sections.filter((s) => s.questions && s.questions.length > 0);
    copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

    setActiveAssignment(copy);
    setSelectedQuestions(new Set());
    addToast(deleteCount + " question(s) removed", "success");
  };

  const regenerateSelectedQuestions = async () => {
    const a = getActiveAssignment();
    if (!a?.sections || selectedQuestions.size === 0) return;

    const questionsToReplace = [];
    const existingQuestions = [];

    a.sections.forEach((section, sIdx) => {
      (section.questions || []).forEach((q, qIdx) => {
        const key = sIdx + "-" + qIdx;
        if (selectedQuestions.has(key)) {
          questionsToReplace.push({
            section_index: sIdx,
            question_index: qIdx,
            question_type: q.question_type || q.type || "short_answer",
            points: q.points || 1,
            dok: q.dok || 1,
            standard: q.standard || "",
          });
        } else {
          existingQuestions.push(q.question || "");
        }
      });
    });

    setRegeneratingQuestions(new Set(selectedQuestions));

    try {
      const data = await api.regenerateQuestions(
        questionsToReplace,
        existingQuestions,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });

      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, q) => sum + (q.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setSelectedQuestions(new Set());

      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast(data.replacements.length + " question(s) regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

  const regenerateOneQuestion = async (sIdx, qIdx) => {
    const a = getActiveAssignment();
    if (!a?.sections) return;
    const q = a.sections[sIdx]?.questions?.[qIdx];
    if (!q) return;

    const key = sIdx + "-" + qIdx;
    setRegeneratingQuestions(new Set([key]));

    const existingTexts = [];
    a.sections.forEach((s) => {
      (s.questions || []).forEach((ques) => existingTexts.push(ques.question || ""));
    });

    try {
      const data = await api.regenerateQuestions(
        [{
          section_index: sIdx,
          question_index: qIdx,
          question_type: q.question_type || q.type || "short_answer",
          points: q.points || 1,
          dok: q.dok || 1,
          standard: q.standard || "",
        }],
        existingTexts,
        {
          grade: config.grade_level || "",
          subject: config.subject || "",
          globalAINotes: config.globalAINotes || "",
          requirements: unitConfig.requirements || "",
        }
      );

      if (data.error) {
        addToast("Regeneration error: " + data.error, "error");
        return;
      }

      const copy = JSON.parse(JSON.stringify(a));
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          r.question.number = section.questions[r.question_index].number;
          section.questions[r.question_index] = r.question;
        }
      });
      copy.sections.forEach((section) => {
        section.points = section.questions.reduce((sum, ques) => sum + (ques.points || 0), 0);
      });
      copy.total_points = copy.sections.reduce((sum, s) => sum + (s.points || 0), 0);

      setActiveAssignment(copy);
      setEditingQuestion(null);
      const costMsg = data.usage?.cost_display ? " (" + data.usage.cost_display + ")" : "";
      addToast("Question regenerated" + costMsg, "success");
    } catch (e) {
      addToast("Regeneration failed: " + e.message, "error");
    } finally {
      setRegeneratingQuestions(new Set());
    }
  };

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
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: (lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) ? "1fr" : "300px 1fr",
                      gap: "25px",
                    }}
                  >
                    {/* Sidebar — hidden when viewing a generated assignment; visible for lesson plans so user can configure & create assignments */}
                    {!(lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "20px",
                      }}
                    >
                      {/* Unit Details */}
                      <div className="glass-card" style={{ padding: "20px" }}>
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "15px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="FileText" size={20} /> Details
                        </h3>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "15px",
                          }}
                        >
                          <div>
                            <label className="label">Content Type</label>
                            <select
                              className="input"
                              value={unitConfig.type}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  type: e.target.value,
                                })
                              }
                            >
                              <option value="Unit Plan">Unit Plan</option>
                              <option value="Lesson Plan">Lesson Plan</option>
                              <option value="Assignment">Assignment</option>
                              <option value="Project">Project</option>
                            </select>
                          </div>
                          <div>
                            <label className="label">Title</label>
                            <input
                              type="text"
                              className="input"
                              value={unitConfig.title}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  title: e.target.value,
                                })
                              }
                              placeholder={
                                {
                                  'Math': 'e.g., Solving Systems of Linear Equations',
                                  'Science': 'e.g., Cell Structure and Function',
                                  'English/ELA': 'e.g., Analyzing Argumentative Texts',
                                  'US History': 'e.g., Causes of the American Revolution',
                                  'World History': 'e.g., Rise and Fall of the Roman Empire',
                                  'Social Studies': 'e.g., Rights and Responsibilities of Citizens',
                                  'Civics': 'e.g., Foundations of American Government',
                                  'Geography': 'e.g., Climate Zones and Human Adaptation',
                                }[config.subject] || 'e.g., Lesson Title'
                              }
                            />
                          </div>
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "1fr 1fr",
                              gap: "12px",
                            }}
                          >
                            <div>
                              <label className="label">Duration (Days)</label>
                              <input
                                type="number"
                                className="input"
                                value={unitConfig.duration}
                                onChange={(e) =>
                                  setUnitConfig({
                                    ...unitConfig,
                                    duration: parseInt(e.target.value) || 1,
                                  })
                                }
                                min="1"
                                max="20"
                              />
                            </div>
                            <div>
                              <label className="label">Period Length</label>
                              <input
                                type="number"
                                className="input"
                                value={unitConfig.periodLength}
                                onChange={(e) =>
                                  setUnitConfig({
                                    ...unitConfig,
                                    periodLength:
                                      parseInt(e.target.value) || 50,
                                  })
                                }
                                min="20"
                                max="120"
                              />
                            </div>
                          </div>
                          {unitConfig.type === "Assignment" && (
                            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px" }}>
                              <div>
                                <label className="label">Total Questions</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={unitConfig.totalQuestions}
                                  onChange={(e) =>
                                    setUnitConfig({
                                      ...unitConfig,
                                      totalQuestions: parseInt(e.target.value) || 10,
                                    })
                                  }
                                  min="5"
                                  max="50"
                                />
                              </div>
                            </div>
                          )}
                          {/* Reference Documents */}
                          <div>
                            <label className="label" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <Icon name="FileUp" size={14} />
                              Reference Documents
                              {uploadedDocs.length > 0 && <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>({uploadedDocs.length})</span>}
                            </label>
                            <input type="file" id="doc-upload-sidebar" multiple accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp,.txt" style={{ display: "none" }} onChange={handleDocUpload} />
                            <div style={{ display: "flex", gap: "6px", marginBottom: uploadedDocs.length > 0 ? "8px" : "0" }}>
                              <button className="btn btn-secondary" onClick={() => document.getElementById("doc-upload-sidebar").click()} disabled={docUploading} style={{ padding: "5px 12px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "5px", flex: 1 }}>
                                <Icon name="Upload" size={13} />
                                {docUploading ? "Uploading..." : "Upload"}
                              </button>
                              {uploadedDocs.length > 0 && (
                                <button className="btn btn-primary" onClick={handleMatchStandards} disabled={matchingInProgress} style={{ padding: "5px 12px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "5px", flex: 1 }}>
                                  <Icon name="Target" size={13} />
                                  {matchingInProgress ? "Matching..." : "Match Standards"}
                                </button>
                              )}
                            </div>
                            {uploadedDocs.length > 0 && (
                              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                {uploadedDocs.map((doc, idx) => (
                                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "6px", background: "rgba(139, 92, 246, 0.1)", border: "1px solid rgba(139, 92, 246, 0.3)", borderRadius: "6px", padding: "4px 8px", fontSize: "0.8rem" }}>
                                    <Icon name={["png","jpg","jpeg","gif","webp"].includes((doc.filename || "").split(".").pop().toLowerCase()) ? "Image" : "FileText"} size={12} />
                                    <span style={{ fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.filename}</span>
                                    <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", flexShrink: 0 }}>{doc.size < 1024 ? doc.size + "B" : Math.round(doc.size / 1024) + "KB"}</span>
                                    <button onClick={() => removeUploadedDoc(idx)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px", fontSize: "0.9rem", lineHeight: 1, flexShrink: 0 }}>×</button>
                                  </div>
                                ))}
                              </div>
                            )}
                            {matchResults && matchResults.matched_standards && matchResults.matched_standards.length > 0 && (
                              <div style={{ background: "var(--glass-bg)", borderRadius: "8px", padding: "8px", border: "1px solid var(--glass-border)", marginTop: "8px" }}>
                                <div style={{ fontSize: "0.75rem", fontWeight: 600, marginBottom: "6px" }}>
                                  {matchResults.matched_standards.filter((a) => a.confidence >= 0.4).length} matching standards — click to select
                                </div>
                                {matchResults.matched_standards.filter((a) => a.confidence >= 0.2).slice(0, 8).map((a, idx) => {
                                  const isSelected = selectedStandards.includes(a.code);
                                  const color = a.confidence >= 0.7 ? "#22c55e" : a.confidence >= 0.4 ? "#f59e0b" : "#ef4444";
                                  return (
                                    <div key={idx} onClick={() => {
                                      if (isSelected) {
                                        setSelectedStandards(prev => prev.filter(c => c !== a.code));
                                      } else {
                                        setSelectedStandards(prev => [...prev, a.code]);
                                      }
                                    }} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px", padding: "4px 6px", borderRadius: "6px", cursor: "pointer", background: isSelected ? "rgba(99, 102, 241, 0.15)" : "transparent", border: isSelected ? "1px solid rgba(99, 102, 241, 0.4)" : "1px solid transparent", transition: "all 0.15s ease" }}>
                                      <Icon name={isSelected ? "CheckCircle" : "Circle"} size={12} style={{ color: isSelected ? "#6366f1" : "var(--text-muted)", flexShrink: 0 }} />
                                      <span style={{ fontWeight: 600, fontSize: "0.7rem", minWidth: "70px", flexShrink: 0 }}>{a.code}</span>
                                      <div style={{ flex: 1, height: "4px", background: "var(--glass-border)", borderRadius: "2px", overflow: "hidden" }}>
                                        <div style={{ width: Math.round(a.confidence * 100) + "%", height: "100%", borderRadius: "2px", background: color }} />
                                      </div>
                                      <span style={{ fontSize: "0.7rem", fontWeight: 600, color: color, flexShrink: 0 }}>{Math.round(a.confidence * 100)}%</span>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>

                          {uploadedDocs.length > 0 && (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 0" }}>
                            <input
                              type="checkbox"
                              id="content-only-toggle"
                              checked={contentOnly}
                              onChange={function(e) { setContentOnly(e.target.checked); }}
                              style={{ width: "16px", height: "16px", cursor: "pointer" }}
                            />
                            <label htmlFor="content-only-toggle" style={{ fontSize: "0.82rem", cursor: "pointer", color: "var(--text-secondary)" }}>
                              Only create questions from uploaded content
                            </label>
                          </div>
                          )}

                          <div>
                            <label className="label">
                              Additional Requirements
                            </label>
                            <textarea
                              className="input"
                              value={unitConfig.requirements}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  requirements: e.target.value,
                                })
                              }
                              placeholder={
                                {
                                  'Math': 'e.g., Include word problems with real-world scenarios, focus on showing work step-by-step',
                                  'Science': 'e.g., Include a lab component with data collection, tie to real-world applications',
                                  'English/ELA': 'e.g., Include text-dependent questions, require evidence-based responses with citations',
                                  'US History': 'e.g., Use primary source documents, include analysis of cause and effect',
                                  'World History': 'e.g., Compare perspectives from multiple civilizations, include map analysis',
                                  'Social Studies': 'e.g., Connect to current events, include civic action component',
                                  'Civics': 'e.g., Reference the U.S. Constitution, include a debate or discussion prompt',
                                  'Geography': 'e.g., Include map skills practice, analyze human-environment interaction',
                                }[config.subject] || 'e.g., Any special instructions for this lesson...'
                              }
                              style={{ minHeight: "80px" }}
                            />
                          </div>
                          {/* Assignment Sections Dropdown - visible when content type is Assignment */}
                          {unitConfig.type === "Assignment" && (
                            <div style={{
                              border: "1px solid var(--glass-border)",
                              borderRadius: "10px",
                              overflow: "hidden",
                            }}>
                              <button
                                type="button"
                                onClick={() => setAssignmentSectionsOpen(!assignmentSectionsOpen)}
                                style={{
                                  width: "100%",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  background: "var(--glass-bg)",
                                  border: "none",
                                  cursor: "pointer",
                                  padding: "10px 14px",
                                  color: "inherit",
                                }}
                              >
                                <span style={{ fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                                  <Icon name="LayoutGrid" size={16} /> Sections
                                  <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--text-muted)" }}>
                                    ({Object.values(assignmentQuestionCounts).filter(function(v) { return v > 0; }).length} types)
                                  </span>
                                </span>
                                <Icon name={assignmentSectionsOpen ? "ChevronUp" : "ChevronDown"} size={16} />
                              </button>
                              {assignmentSectionsOpen && (
                                <div style={{ padding: "10px 14px", borderTop: "1px solid var(--glass-border)" }}>
                                  {(function() {
                                    var totalAssigned = Object.values(assignmentQuestionCounts).reduce(function(a, b) { return a + b; }, 0);
                                    var totalTarget = unitConfig.totalQuestions || 10;
                                    var statusColor = totalAssigned === totalTarget ? "#22c55e" : totalAssigned > totalTarget ? "#ef4444" : "#f59e0b";
                                    return (
                                      React.createElement('div', {
                                        style: { fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px", color: statusColor }
                                      },
                                        totalAssigned + "/" + totalTarget + " assigned" +
                                        (totalAssigned < totalTarget ? " — AI will distribute " + (totalTarget - totalAssigned) + " remaining" : "") +
                                        (totalAssigned > totalTarget ? " — exceeds total by " + (totalAssigned - totalTarget) : "")
                                      )
                                    );
                                  })()}
                                  {[
                                    { key: "multiple_choice", label: "Multiple Choice", group: "core" },
                                    { key: "short_answer", label: "Short Answer", group: "core" },
                                    { key: "math_computation", label: "Math Computation", group: "stem" },
                                    { key: "geometry_visual", label: "Geometry", group: "stem" },
                                    { key: "graphing", label: "Graphing", group: "stem" },
                                    { key: "data_analysis", label: "Data Analysis", group: "stem" },
                                    { key: "extended_writing", label: "Extended Writing", group: "optional" },
                                    { key: "vocabulary", label: "Vocabulary", group: "optional" },
                                    { key: "true_false", label: "True / False", group: "optional" },
                                    { key: "florida_fast", label: "FL FAST Items", group: "optional" },
                                  ].map(function(cat, idx, arr) {
                                    var prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                    var showDivider = cat.group !== prevGroup;
                                    var groupLabels = { core: "Core", stem: "STEM", optional: "Optional" };
                                    var groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                    var count = assignmentQuestionCounts[cat.key] || 0;
                                    return (
                                      React.createElement('div', { key: cat.key },
                                        showDivider ? React.createElement('div', {
                                          style: { fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase",
                                            letterSpacing: "0.05em", color: groupColors[cat.group],
                                            marginTop: idx > 0 ? "4px" : 0, marginBottom: "2px" }
                                        }, groupLabels[cat.group]) : null,
                                        React.createElement('div', {
                                          style: { display: "flex", alignItems: "center", justifyContent: "space-between",
                                            padding: "4px 8px", borderRadius: "6px", fontSize: "0.82rem",
                                            background: count > 0 ? "rgba(99,102,241,0.1)" : "transparent" }
                                        },
                                          React.createElement('span', { style: { color: count > 0 ? "var(--text-primary)" : "var(--text-muted)" } }, cat.label),
                                          React.createElement('input', {
                                            type: "number",
                                            min: 0,
                                            max: unitConfig.totalQuestions || 50,
                                            value: count,
                                            onChange: function(e) {
                                              var val = parseInt(e.target.value) || 0;
                                              var updated = Object.assign({}, assignmentQuestionCounts);
                                              updated[cat.key] = Math.max(0, val);
                                              setAssignmentQuestionCounts(updated);
                                            },
                                            style: { width: "50px", padding: "3px 6px", borderRadius: "6px",
                                              border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                                              color: "var(--text-primary)", fontSize: "0.82rem", textAlign: "center" }
                                          })
                                        )
                                      )
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Brainstorm Button */}
                          <button
                            onClick={brainstormIdeasHandler}
                            disabled={
                              brainstormLoading ||
                              (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
                              opacity:
                                brainstormLoading ||
                                (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                            }}
                          >
                            {brainstormLoading ? (
                              <Icon
                                name="Loader2"
                                size={18}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                            ) : (
                              <Icon name="Lightbulb" size={18} />
                            )}
                            {brainstormLoading
                              ? "Brainstorming..."
                              : "Brainstorm " + unitConfig.type + " Ideas"}
                          </button>

                          {/* Generate Plan Button */}
                          <button
                            onClick={() => generateLessonPlan(false)}
                            disabled={
                              plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-primary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
                              opacity:
                                plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                            }}
                          >
                            {plannerLoading ? (
                              <Icon
                                name="Loader2"
                                size={18}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                            ) : (
                              <Icon name="Sparkles" size={18} />
                            )}
                            {plannerLoading
                              ? (unitConfig.type === "Assignment" ? "Creating Assignment..." : "Creating...")
                              : selectedIdea
                                ? "Create from Idea"
                                : "Create"}
                          </button>

                          {/* Generate Variations Button */}
                          <button
                            onClick={() => generateLessonPlan(true)}
                            disabled={
                              plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              opacity:
                                plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                              fontSize: "0.85rem",
                            }}
                          >
                            <Icon name="Layers" size={16} />
                            {"Generate 3 " + unitConfig.type + " Variations"}
                          </button>
                        </div>
                      </div>
                    </div>
                    )}

                    {/* Main Content */}
                    <div>
                      {/* Brainstormed Ideas Section - Full Width */}
                      {brainstormIdeas.length > 0 &&
                        !lessonPlan &&
                        lessonVariations.length === 0 && (
                          <div
                            className="glass-card"
                            style={{ padding: "25px", marginBottom: "20px" }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "20px",
                              }}
                            >
                              <h3
                                style={{
                                  fontSize: "1.2rem",
                                  fontWeight: 700,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                  margin: 0,
                                }}
                              >
                                <Icon
                                  name="Lightbulb"
                                  size={24}
                                  style={{ color: "#f59e0b" }}
                                />{" "}
                                {unitConfig.type + " Ideas"}
                              </h3>
                              <button
                                onClick={() => { setBrainstormIdeas([]); setSelectedIdea(null); }}
                                className="btn btn-secondary"
                                style={{
                                  padding: "6px 12px",
                                  fontSize: "0.85rem",
                                }}
                              >
                                <Icon name="X" size={14} /> Clear
                              </button>
                            </div>
                            <p
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                                marginBottom: "20px",
                              }}
                            >
                              Select an idea to develop into a full lesson plan,
                              or use it as inspiration.
                            </p>
                            <div
                              style={{
                                display: "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fill, minmax(300px, 1fr))",
                                gap: "15px",
                              }}
                            >
                              {brainstormIdeas.map((idea) => (
                                <div
                                  key={idea.id}
                                  onClick={() => {
                                    setSelectedIdea(
                                      selectedIdea?.id === idea.id
                                        ? null
                                        : idea,
                                    );
                                    if (selectedIdea?.id !== idea.id) {
                                      setUnitConfig((prev) => ({
                                        ...prev,
                                        title: idea.title,
                                      }));
                                    }
                                  }}
                                  style={{
                                    padding: "20px",
                                    borderRadius: "12px",
                                    background:
                                      selectedIdea?.id === idea.id
                                        ? "rgba(99,102,241,0.15)"
                                        : "var(--input-bg)",
                                    border:
                                      selectedIdea?.id === idea.id
                                        ? "2px solid var(--accent-primary)"
                                        : "1px solid var(--glass-border)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "flex-start",
                                      marginBottom: "10px",
                                    }}
                                  >
                                    <h4
                                      style={{
                                        fontWeight: 600,
                                        fontSize: "1.05rem",
                                        margin: 0,
                                        flex: 1,
                                      }}
                                    >
                                      {idea.title}
                                    </h4>
                                    <span
                                      style={{
                                        padding: "4px 12px",
                                        borderRadius: "12px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginLeft: "10px",
                                        background:
                                          idea.approach === "Activity-Based"
                                            ? "rgba(16,185,129,0.2)"
                                            : idea.approach === "Discussion"
                                              ? "rgba(99,102,241,0.2)"
                                              : idea.approach === "Project"
                                                ? "rgba(245,158,11,0.2)"
                                                : idea.approach === "Simulation"
                                                  ? "rgba(236,72,153,0.2)"
                                                  : "rgba(107,114,128,0.2)",
                                        color:
                                          idea.approach === "Activity-Based"
                                            ? "#10b981"
                                            : idea.approach === "Discussion"
                                              ? "#6366f1"
                                              : idea.approach === "Project"
                                                ? "#f59e0b"
                                                : idea.approach === "Simulation"
                                                  ? "#ec4899"
                                                  : "#6b7280",
                                      }}
                                    >
                                      {idea.approach}
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                      marginBottom: "12px",
                                      lineHeight: 1.5,
                                    }}
                                  >
                                    {idea.brief}
                                  </p>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                      marginBottom: "6px",
                                    }}
                                  >
                                    <strong>Hook:</strong> {idea.hook}
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "0.85rem",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    <strong>Activity:</strong>{" "}
                                    {idea.key_activity}
                                  </div>
                                  {idea.tools_used && idea.tools_used !== "None - hands-on activity" && (
                                    <div
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                        marginTop: "6px",
                                        display: "flex",
                                        alignItems: "flex-start",
                                        gap: "6px",
                                      }}
                                    >
                                      <Icon name="Monitor" size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
                                      <span><strong>Tools:</strong> {idea.tools_used}</span>
                                    </div>
                                  )}
                                  {selectedIdea?.id === idea.id && (
                                    <div
                                      style={{
                                        marginTop: "12px",
                                        padding: "10px",
                                        background: "rgba(99,102,241,0.1)",
                                        borderRadius: "8px",
                                        fontSize: "0.85rem",
                                        color: "var(--accent-light)",
                                      }}
                                    >
                                      <Icon
                                        name="CheckCircle"
                                        size={14}
                                        style={{
                                          marginRight: "6px",
                                          verticalAlign: "middle",
                                        }}
                                      />
                                      Selected - Click "Generate" to create
                                      lesson plan
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      {/* Lesson Variations Display */}
                      {lessonVariations.length > 0 && !lessonPlan && (
                        <div
                          className="glass-card"
                          style={{
                            padding: "30px",
                            maxHeight: "80vh",
                            overflowY: "auto",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "25px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid var(--glass-border)",
                            }}
                          >
                            <div>
                              <h2
                                style={{
                                  fontSize: "1.5rem",
                                  fontWeight: 700,
                                  marginBottom: "5px",
                                }}
                              >
                                <Icon
                                  name="Layers"
                                  size={24}
                                  style={{
                                    marginRight: "10px",
                                    verticalAlign: "middle",
                                    color: "var(--accent-primary)",
                                  }}
                                />
                                {(unitConfig.type || "Lesson Plan") + " Variations"}
                              </h2>
                              <p
                                style={{
                                  color: "var(--text-secondary)",
                                  fontSize: "0.9rem",
                                }}
                              >
                                Compare {lessonVariations.length} different
                                approaches for this {(unitConfig.type || "lesson plan").toLowerCase()}
                              </p>
                            </div>
                            <button
                              onClick={() => setLessonVariations([])}
                              className="btn btn-secondary"
                            >
                              <Icon name="X" size={16} /> Close
                            </button>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "20px",
                            }}
                          >
                            {lessonVariations.map((variation, idx) => (
                              <div
                                key={idx}
                                style={{
                                  padding: "20px",
                                  background: "var(--input-bg)",
                                  borderRadius: "12px",
                                  border: "1px solid var(--glass-border)",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "flex-start",
                                    marginBottom: "15px",
                                  }}
                                >
                                  <div>
                                    <span
                                      style={{
                                        display: "inline-block",
                                        padding: "4px 12px",
                                        borderRadius: "15px",
                                        fontSize: "0.75rem",
                                        fontWeight: 600,
                                        marginBottom: "8px",
                                        background:
                                          idx === 0
                                            ? "rgba(16,185,129,0.2)"
                                            : idx === 1
                                              ? "rgba(99,102,241,0.2)"
                                              : "rgba(245,158,11,0.2)",
                                        color:
                                          idx === 0
                                            ? "#10b981"
                                            : idx === 1
                                              ? "#6366f1"
                                              : "#f59e0b",
                                      }}
                                    >
                                      {variation.approach ||
                                        `Variation ${idx + 1}`}
                                    </span>
                                    <h3
                                      style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 600,
                                        margin: "8px 0",
                                      }}
                                    >
                                      {variation.title}
                                    </h3>
                                    <p
                                      style={{
                                        color: "var(--text-secondary)",
                                        fontSize: "0.9rem",
                                        lineHeight: 1.5,
                                      }}
                                    >
                                      {variation.overview}
                                    </p>
                                  </div>
                                  <button
                                    onClick={() => {
                                      setLessonPlan(variation);
                                      setLessonVariations([]);
                                    }}
                                    className="btn btn-primary"
                                    style={{ flexShrink: 0 }}
                                  >
                                    <Icon name="Check" size={16} /> {"Use This " + (unitConfig.type || "Plan")}
                                  </button>
                                </div>
                                {/* Content preview - varies by type */}
                                {variation.sections ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Sections:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.sections.map((s, si) => (
                                        <li key={si}>
                                          {s.name} ({s.points || 0} pts, {(s.questions || []).length} questions)
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : variation.phases ? (
                                  <div style={{ marginTop: "10px" }}>
                                    <strong
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-primary)",
                                      }}
                                    >
                                      Phases:
                                    </strong>
                                    <ul
                                      style={{
                                        margin: "5px 0 0 20px",
                                        fontSize: "0.85rem",
                                        color: "var(--text-secondary)",
                                      }}
                                    >
                                      {variation.phases.map((p, pi) => (
                                        <li key={pi}>
                                          {p.name} ({p.duration})
                                        </li>
                                      ))}
                                    </ul>
                                    {variation.total_points && (
                                      <p
                                        style={{
                                          fontSize: "0.8rem",
                                          color: "var(--text-muted)",
                                          marginTop: "5px",
                                        }}
                                      >
                                        Total: {variation.total_points} points
                                      </p>
                                    )}
                                  </div>
                                ) : (
                                  <>
                                    {variation.essential_questions && (
                                      <div style={{ marginTop: "10px" }}>
                                        <strong
                                          style={{
                                            fontSize: "0.85rem",
                                            color: "var(--text-primary)",
                                          }}
                                        >
                                          Essential Questions:
                                        </strong>
                                        <ul
                                          style={{
                                            margin: "5px 0 0 20px",
                                            fontSize: "0.85rem",
                                            color: "var(--text-secondary)",
                                          }}
                                        >
                                          {variation.essential_questions
                                            .slice(0, 2)
                                            .map((q, i) => (
                                              <li key={i}>{q}</li>
                                            ))}
                                        </ul>
                                      </div>
                                    )}
                                    {variation.days && (
                                      <div
                                        style={{
                                          marginTop: "10px",
                                          fontSize: "0.85rem",
                                          color: "var(--text-muted)",
                                        }}
                                      >
                                        <Icon
                                          name="Calendar"
                                          size={14}
                                          style={{
                                            marginRight: "6px",
                                            verticalAlign: "middle",
                                          }}
                                        />
                                        {variation.days.length} day
                                        {variation.days.length !== 1
                                          ? "s"
                                          : ""}{" "}
                                        planned
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Single Lesson Plan Display */}
                      {lessonPlan ? (
                        <div
                          className="glass-card"
                          style={{
                            padding: "30px",
                            maxHeight: "80vh",
                            overflowY: "auto",
                          }}
                        >
                          {/* Header */}
                          <div
                            style={{
                              marginBottom: "25px",
                              borderBottom: "1px solid var(--glass-border)",
                              paddingBottom: "20px",
                            }}
                          >
                            <h2
                              style={{
                                fontSize: "1.8rem",
                                fontWeight: 700,
                                marginBottom: "10px",
                              }}
                            >
                              {lessonPlan.title}
                            </h2>
                            <p
                              style={{
                                color: "var(--text-secondary)",
                                lineHeight: "1.6",
                                marginBottom: "20px",
                              }}
                            >
                              {lessonPlan.overview}
                            </p>
                            <div
                              style={{
                                display: "flex",
                                gap: "10px",
                                alignItems: "center",
                                flexWrap: "wrap",
                              }}
                            >
                              {lessonPlan.sections && !lessonPlan.days ? (
                                /* Assignment-type content: Export PDF, Answer Key, Interactive Preview, Set Up Grading */
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "docx", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as DOCX!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} /> Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Student worksheet exported as PDF!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(lessonPlan, "pdf", true, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) {
                                          addToast("Error: " + result.error, "error");
                                        } else {
                                          addToast("Answer key exported as PDF!", "success");
                                        }
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} /> Answer Key
                                  </button>
                                  <button
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} /> {previewShowAnswers ? "Hide Answers" : "Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      let gradingNotes = "ANSWER KEY for " + lessonPlan.title + "\n\n";
                                      (lessonPlan.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (lessonPlan.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        lessonPlan.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }
                                      const markers = (lessonPlan.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      setAssignment({
                                        ...assignment,
                                        title: lessonPlan.title || "",
                                        totalPoints: lessonPlan.total_points || 100,
                                        customMarkers: markers,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px", background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} /> Set Up Grading
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} /> {editMode ? "Exit Edit" : "Edit Questions"}
                                  </button>
                                </>
                              ) : generatedAssignment ? (
                                /* Assignment was created from this lesson — export it as PDF */
                                <>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "docx", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as DOCX!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} /> Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", false, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Assignment exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export assignment as PDF with graphics"
                                  >
                                    <Icon name="Download" size={16} /> Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result = await api.exportGeneratedAssignment(generatedAssignment, "pdf", true, { teacher_name: config.teacher_name, subject: config.subject });
                                        if (result.error) addToast("Error: " + result.error, "error");
                                        else addToast("Answer key exported as PDF!", "success");
                                      } catch (e) {
                                        addToast("Export failed: " + e.message, "error");
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} /> Answer Key
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} /> {editMode ? "Exit Edit" : "Edit Questions"}
                                  </button>
                                </>
                              ) : (
                                /* Lesson plan / project: standard Export + Save */
                                <>
                                  <button
                                    onClick={exportLessonPlanHandler}
                                    className="btn btn-secondary"
                                  >
                                    <Icon name="Download" size={16} /> Export
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => setShowSaveLesson(true)}
                                className="btn btn-secondary"
                                title="Save for use in assessment generation"
                              >
                                <Icon name="FolderPlus" size={16} /> Save to Unit
                              </button>
                              <button
                                onClick={() => { setPlannerMode("tools"); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 14px", background: "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(8,145,178,0.15))", border: "1px solid rgba(6,182,212,0.3)" }}
                                title="Generate study guide from this content"
                              >
                                <Icon name="BookOpen" size={16} /> Study Guide
                              </button>
                              {(lessonPlan.sections || generatedAssignment) && !lessonPlan.phases && (
                                <button
                                  onClick={publishAssessmentHandler}
                                  disabled={publishingAssessment}
                                  className="btn"
                                  style={{ padding: "8px 16px", background: "linear-gradient(135deg, #8b5cf6, #6366f1)" }}
                                >
                                  <Icon name={publishingAssessment ? "Loader" : "Share2"} size={16} />
                                  {publishingAssessment ? "Publishing..." : "Publish to Portal"}
                                </button>
                              )}
                              {/* Assignment/Essay/Project creation is handled via the Details sidebar Content Type selector */}
                              <div style={{ flex: 1 }} />
                              <button
                                onClick={() => {
                                  setLessonPlan(null);
                                  setSelectedIdea(null);
                                  setBrainstormIdeas([]);
                                  setGeneratedAssignment(null);
                                }}
                                className="btn btn-secondary"
                              >
                                Close
                              </button>
                            </div>
                          </div>


                          {/* Standards aligned to this content */}
                          {selectedStandards.length > 0 && lessonPlan.sections && (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "12px" }}>
                              {selectedStandards.map((code) => {
                                const std = standards.find((s) => s.code === code);
                                return (
                                  <span
                                    key={code}
                                    title={std?.benchmark || code}
                                    style={{
                                      padding: "3px 8px",
                                      background: "rgba(139,92,246,0.15)",
                                      color: "#a78bfa",
                                      borderRadius: "8px",
                                      fontSize: "0.75rem",
                                      fontWeight: 500,
                                      maxWidth: "280px",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {code}{std?.benchmark ? ": " + std.benchmark : ""}
                                  </span>
                                );
                              })}
                            </div>
                          )}

                          {/* Content display - varies by type */}
                          {lessonPlan.sections && !lessonPlan.days ? (
                            /* Assignment display - interactive AssignmentPlayer */
                            <>
                              {editMode && (
                                <QuestionEditToolbar
                                  selectedCount={selectedQuestions.size}
                                  totalCount={getTotalQuestionCount()}
                                  onSelectAll={selectAllQuestions}
                                  onDeselectAll={() => setSelectedQuestions(new Set())}
                                  onDeleteSelected={deleteSelectedQuestions}
                                  onRegenerateSelected={regenerateSelectedQuestions}
                                  onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  isRegenerating={regeneratingQuestions.size > 0}
                                />
                              )}
                              <AssignmentPlayer
                                assignment={lessonPlan}
                                showAnswers={previewShowAnswers}
                                results={previewResults}
                                editMode={editMode}
                                selectedQuestions={selectedQuestions}
                                editingQuestion={editingQuestion}
                                regeneratingQuestions={regeneratingQuestions}
                                onToggleSelect={toggleQuestionSelect}
                                onStartEdit={setEditingQuestion}
                                onSaveEdit={saveEditedQuestion}
                                onCancelEdit={() => setEditingQuestion(null)}
                                onRegenerateOne={regenerateOneQuestion}
                                onSubmit={async (answers) => {
                                  try {
                                    const published = await api.publishAssignment(lessonPlan);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />
                            </>
                          ) : lessonPlan.phases ? (
                            /* Project display - phases with tasks */
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "20px",
                              }}
                            >
                              {lessonPlan.driving_question && (
                                <div
                                  style={{
                                    background: "rgba(99,102,241,0.1)",
                                    borderRadius: "12px",
                                    padding: "15px",
                                    border: "1px solid rgba(99,102,241,0.2)",
                                  }}
                                >
                                  <strong style={{ color: "#818cf8" }}>Driving Question:</strong>{" "}
                                  <span style={{ fontSize: "0.95rem" }}>{lessonPlan.driving_question}</span>
                                </div>
                              )}
                              {lessonPlan.total_points && (
                                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                  Total: {lessonPlan.total_points} points
                                </p>
                              )}
                              {(lessonPlan.phases || []).map((phase, i) => (
                                <div
                                  key={i}
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "25px",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      gap: "15px",
                                      marginBottom: "15px",
                                      paddingBottom: "10px",
                                      borderBottom: "1px solid var(--glass-border)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "40px",
                                        height: "40px",
                                        borderRadius: "10px",
                                        background: "linear-gradient(135deg, #10b981, #06b6d4)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontWeight: 700,
                                        fontSize: "1rem",
                                        flexShrink: 0,
                                      }}
                                    >
                                      {phase.phase || i + 1}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <h3 style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "4px" }}>
                                        {phase.name}
                                      </h3>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {phase.duration}
                                      </span>
                                    </div>
                                  </div>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "10px", lineHeight: 1.5 }}>
                                    {phase.description}
                                  </p>
                                  {phase.tasks && (
                                    <ul style={{ margin: "0 0 10px 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {phase.tasks.map((t, ti) => (
                                        <li key={ti} style={{ marginBottom: "4px" }}>{t}</li>
                                      ))}
                                    </ul>
                                  )}
                                  {phase.deliverable && (
                                    <p style={{ fontSize: "0.85rem", color: "#10b981" }}>
                                      <strong>Deliverable:</strong> {phase.deliverable}
                                    </p>
                                  )}
                                </div>
                              ))}
                              {lessonPlan.final_deliverable && (
                                <div
                                  style={{
                                    background: "rgba(16,185,129,0.1)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                    border: "1px solid rgba(16,185,129,0.2)",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px", color: "#10b981" }}>
                                    <Icon name="Award" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Final Deliverable
                                  </h3>
                                  <p style={{ fontSize: "0.9rem", marginBottom: "8px" }}>
                                    <strong>Format:</strong> {lessonPlan.final_deliverable.format}
                                  </p>
                                  {lessonPlan.final_deliverable.requirements && (
                                    <ul style={{ margin: "0 0 0 20px", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                                      {lessonPlan.final_deliverable.requirements.map((r, ri) => (
                                        <li key={ri}>{r}</li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              )}
                              {lessonPlan.rubric && lessonPlan.rubric.criteria && (
                                <div
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "20px",
                                  }}
                                >
                                  <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "10px" }}>
                                    <Icon name="ClipboardList" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                                    Rubric
                                  </h3>
                                  {lessonPlan.rubric.criteria.map((c, ci) => (
                                    <div key={ci} style={{ marginBottom: "10px", paddingBottom: "10px", borderBottom: ci < lessonPlan.rubric.criteria.length - 1 ? "1px solid var(--glass-border)" : "none" }}>
                                      <strong style={{ fontSize: "0.9rem" }}>{c.name}</strong>
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: "8px" }}>({c.points} pts)</span>
                                      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "4px" }}>{c.description}</p>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : (
                            /* Lesson Plan / Unit Plan display - days */
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "30px",
                              }}
                            >
                              {(lessonPlan.days || []).map((day, i) => (
                                <div
                                  key={i}
                                  style={{
                                    background: "var(--input-bg)",
                                    borderRadius: "16px",
                                    padding: "25px",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      gap: "15px",
                                      marginBottom: "20px",
                                      paddingBottom: "15px",
                                      borderBottom:
                                        "1px solid var(--glass-border)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "50px",
                                        height: "50px",
                                        borderRadius: "12px",
                                        background:
                                          "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontWeight: 700,
                                        fontSize: "1.2rem",
                                      }}
                                    >
                                      {day.day}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <h3
                                        style={{
                                          fontSize: "1.3rem",
                                          fontWeight: 600,
                                          marginBottom: "8px",
                                        }}
                                      >
                                        {day.topic}
                                      </h3>
                                      <p
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "var(--text-primary)",
                                        }}
                                      >
                                        <strong style={{ color: "#10b981" }}>
                                          Objective:
                                        </strong>{" "}
                                        {day.objective}
                                      </p>
                                    </div>
                                  </div>

                                  {day.bell_ringer && (
                                    <div
                                      style={{
                                        marginBottom: "15px",
                                        padding: "15px",
                                        background: "rgba(165,180,252,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(165,180,252,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#a5b4fc",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="Zap" size={14} /> Bell Ringer
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.bell_ringer === "object"
                                          ? day.bell_ringer.prompt
                                          : day.bell_ringer}
                                      </p>
                                    </div>
                                  )}

                                  {day.activity && (
                                    <div
                                      style={{
                                        marginBottom: "15px",
                                        padding: "15px",
                                        background: "rgba(74,222,128,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(74,222,128,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#4ade80",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="Activity" size={14} /> Main
                                        Activity
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.activity === "object"
                                          ? day.activity.description
                                          : day.activity}
                                      </p>
                                    </div>
                                  )}

                                  {day.assessment && (
                                    <div
                                      style={{
                                        padding: "15px",
                                        background: "rgba(248,113,113,0.1)",
                                        borderRadius: "10px",
                                        border: "1px solid rgba(248,113,113,0.2)",
                                      }}
                                    >
                                      <h4
                                        style={{
                                          fontSize: "0.9rem",
                                          color: "#f87171",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <Icon name="CheckCircle" size={14} />{" "}
                                        Assessment
                                      </h4>
                                      <p style={{ fontSize: "0.9rem" }}>
                                        {typeof day.assessment === "object"
                                          ? day.assessment.description
                                          : day.assessment}
                                      </p>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Generated Assignment Section */}
                          {generatedAssignment && (
                            <div
                              style={{
                                marginTop: "30px",
                                padding: "25px",
                                background:
                                  "linear-gradient(135deg, rgba(16,185,129,0.1), rgba(6,182,212,0.1))",
                                borderRadius: "16px",
                                border: "1px solid rgba(16,185,129,0.3)",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "flex-start",
                                  marginBottom: "20px",
                                }}
                              >
                                <div>
                                  <h3
                                    style={{
                                      fontSize: "1.4rem",
                                      fontWeight: 700,
                                      marginBottom: "8px",
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "10px",
                                    }}
                                  >
                                    <Icon
                                      name="FileText"
                                      size={24}
                                      style={{ color: "#10b981" }}
                                    />
                                    {generatedAssignment.title}
                                  </h3>
                                  <div
                                    style={{
                                      display: "flex",
                                      gap: "10px",
                                      flexWrap: "wrap",
                                    }}
                                  >
                                    <span
                                      style={{
                                        padding: "4px 10px",
                                        background: "rgba(16,185,129,0.2)",
                                        color: "#10b981",
                                        borderRadius: "12px",
                                        fontSize: "0.8rem",
                                        fontWeight: 500,
                                      }}
                                    >
                                      {generatedAssignment.type
                                        ?.charAt(0)
                                        .toUpperCase() +
                                        generatedAssignment.type?.slice(1)}
                                    </span>
                                    {generatedAssignment.time_estimate && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(99,102,241,0.2)",
                                          color: "#818cf8",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        <Icon
                                          name="Clock"
                                          size={12}
                                          style={{ marginRight: "4px" }}
                                        />
                                        {generatedAssignment.time_estimate}
                                      </span>
                                    )}
                                    {generatedAssignment.total_points && (
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          background: "rgba(251,191,36,0.2)",
                                          color: "#fbbf24",
                                          borderRadius: "12px",
                                          fontSize: "0.8rem",
                                        }}
                                      >
                                        {generatedAssignment.total_points}{" "}
                                        points
                                      </span>
                                    )}
                                  </div>
                                  {selectedStandards.length > 0 && (
                                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                                      {selectedStandards.map((code) => {
                                        const std = standards.find((s) => s.code === code);
                                        return (
                                          <span
                                            key={code}
                                            title={std?.benchmark || code}
                                            style={{
                                              padding: "3px 8px",
                                              background: "rgba(139,92,246,0.15)",
                                              color: "#a78bfa",
                                              borderRadius: "8px",
                                              fontSize: "0.75rem",
                                              fontWeight: 500,
                                              maxWidth: "280px",
                                              overflow: "hidden",
                                              textOverflow: "ellipsis",
                                              whiteSpace: "nowrap",
                                            }}
                                          >
                                            {code}{std?.benchmark ? ": " + std.benchmark : ""}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "docx",
                                            false,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as DOCX!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as Word Doc (Graider tables)"
                                  >
                                    <Icon name="FileText" size={16} />
                                    Export DOCX
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            false,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Student worksheet exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export student version as PDF"
                                  >
                                    <Icon name="Download" size={16} />
                                    Export PDF
                                  </button>
                                  <button
                                    onClick={async () => {
                                      try {
                                        const result =
                                          await api.exportGeneratedAssignment(
                                            generatedAssignment,
                                            "pdf",
                                            true,
                                            { teacher_name: config.teacher_name, subject: config.subject },
                                          );
                                        if (result.error) {
                                          addToast(
                                            "Error: " + result.error,
                                            "error",
                                          );
                                        } else {
                                          addToast(
                                            "Answer key exported as PDF!",
                                            "success",
                                          );
                                        }
                                      } catch (e) {
                                        addToast(
                                          "Export failed: " + e.message,
                                          "error",
                                        );
                                      }
                                    }}
                                    className="btn btn-secondary"
                                    style={{ padding: "8px 14px" }}
                                    title="Export teacher version with answers as PDF"
                                  >
                                    <Icon name="Key" size={16} />
                                    Answer Key
                                  </button>
                                  <button
                                    onClick={() => setPreviewShowAnswers(prev => !prev)}
                                    className={previewShowAnswers ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(previewShowAnswers ? { background: "linear-gradient(135deg, #10b981, #059669)" } : {}) }}
                                    title={previewShowAnswers ? "Hide answer key in preview" : "Show answer key in preview"}
                                  >
                                    <Icon name={previewShowAnswers ? "EyeOff" : "Eye"} size={16} />
                                    {previewShowAnswers ? " Hide Answers" : " Show Answers"}
                                  </button>
                                  <button
                                    onClick={() => {
                                      // Build answer key as grading notes
                                      let gradingNotes = "ANSWER KEY for " + generatedAssignment.title + "\n\n";
                                      (generatedAssignment.sections || []).forEach((section) => {
                                        gradingNotes += "--- " + section.name + " (" + section.points + " pts) ---\n";
                                        (section.questions || []).forEach((q) => {
                                          gradingNotes += "Q" + q.number + ": " + q.answer + " (" + q.points + " pts)\n";
                                        });
                                        gradingNotes += "\n";
                                      });
                                      if (generatedAssignment.rubric?.criteria) {
                                        gradingNotes += "--- Rubric ---\n";
                                        generatedAssignment.rubric.criteria.forEach((c) => {
                                          gradingNotes += c.name + " (" + c.points + " pts): " + c.description + "\n";
                                        });
                                      }

                                      // Map sections to customMarkers, normalized so markers + effort = 100
                                      const effortPts = assignment.effortPoints ?? 15;
                                      const rawMarkers = (generatedAssignment.sections || []).map((section) => ({
                                        start: section.name + ":",
                                        points: section.points || 10,
                                        type: "written",
                                      }));
                                      const rawTotal = rawMarkers.reduce((sum, m) => sum + m.points, 0);
                                      const available = 100 - effortPts;
                                      const markers = rawTotal > 0 && rawTotal !== available
                                        ? rawMarkers.map((m) => ({
                                            ...m,
                                            points: Math.round((m.points / rawTotal) * available),
                                          }))
                                        : rawMarkers;
                                      // Fix rounding drift so total is exactly 100
                                      const markerSum = markers.reduce((s, m) => s + m.points, 0);
                                      if (markers.length > 0 && markerSum !== available) {
                                        markers[0].points += available - markerSum;
                                      }

                                      setAssignment({
                                        ...assignment,
                                        title: generatedAssignment.title || "",
                                        totalPoints: generatedAssignment.total_points || 100,
                                        customMarkers: markers,
                                        effortPoints: effortPts,
                                        gradingNotes: gradingNotes.trim(),
                                        useSectionPoints: true,
                                        sectionTemplate: "Custom",
                                      });
                                      setLoadedAssignmentName("");
                                      setActiveTab("builder");
                                      addToast("Assignment loaded into Grading Setup with answer key and section markers", "success");
                                    }}
                                    className="btn btn-primary"
                                    style={{
                                      padding: "8px 14px",
                                      background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                                    }}
                                    title="Set up grading configuration for this assignment"
                                  >
                                    <Icon name="Settings" size={16} />
                                    Set Up Grading
                                  </button>
                                  <button
                                    onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                    className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                    style={{ padding: "8px 14px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                    title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                  >
                                    <Icon name={editMode ? "X" : "Pencil"} size={16} />
                                    {editMode ? " Exit Edit" : " Edit Questions"}
                                  </button>
                                  <button
                                    onClick={() => setGeneratedAssignment(null)}
                                    className="btn btn-secondary"
                                    style={{ padding: "6px 12px" }}
                                  >
                                    <Icon name="X" size={16} />
                                  </button>
                                </div>
                              </div>

                              {editMode && (
                                <QuestionEditToolbar
                                  selectedCount={selectedQuestions.size}
                                  totalCount={getTotalQuestionCount()}
                                  onSelectAll={selectAllQuestions}
                                  onDeselectAll={() => setSelectedQuestions(new Set())}
                                  onDeleteSelected={deleteSelectedQuestions}
                                  onRegenerateSelected={regenerateSelectedQuestions}
                                  onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  isRegenerating={regeneratingQuestions.size > 0}
                                />
                              )}
                              <AssignmentPlayer
                                assignment={generatedAssignment}
                                showAnswers={previewShowAnswers}
                                results={previewResults}
                                editMode={editMode}
                                selectedQuestions={selectedQuestions}
                                editingQuestion={editingQuestion}
                                regeneratingQuestions={regeneratingQuestions}
                                onToggleSelect={toggleQuestionSelect}
                                onStartEdit={setEditingQuestion}
                                onSaveEdit={saveEditedQuestion}
                                onCancelEdit={() => setEditingQuestion(null)}
                                onRegenerateOne={regenerateOneQuestion}
                                onSubmit={async (answers) => {
                                  try {
                                    const published = await api.publishAssignment(generatedAssignment);
                                    const result = await api.submitAssignment(published.assignment_id, answers, "Teacher Preview");
                                    setPreviewResults(result.results);
                                    addToast("Assignment graded! Score: " + result.results.percent + "%", "success");
                                  } catch (err) { addToast("Error grading: " + err.message, "error"); }
                                }}
                              />

                              {/* Rubric */}
                              {generatedAssignment.rubric?.criteria && (
                                <div
                                  style={{
                                    padding: "15px",
                                    background: "rgba(251,191,36,0.1)",
                                    borderRadius: "10px",
                                    border: "1px solid rgba(251,191,36,0.2)",
                                  }}
                                >
                                  <h4
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "#fbbf24",
                                      marginBottom: "10px",
                                      fontWeight: 600,
                                    }}
                                  >
                                    <Icon
                                      name="Award"
                                      size={14}
                                      style={{ marginRight: "6px" }}
                                    />
                                    Grading Rubric
                                  </h4>
                                  {generatedAssignment.rubric.criteria.map(
                                    (c, cIdx) => (
                                      <div
                                        key={cIdx}
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          padding: "8px 0",
                                          borderBottom:
                                            cIdx <
                                            generatedAssignment.rubric.criteria
                                              .length -
                                              1
                                              ? "1px solid rgba(251,191,36,0.2)"
                                              : "none",
                                        }}
                                      >
                                        <span style={{ fontWeight: 500 }}>
                                          {c.name}
                                        </span>
                                        <span
                                          style={{
                                            color: "var(--text-secondary)",
                                            fontSize: "0.9rem",
                                          }}
                                        >
                                          {c.points} pts - {c.description}
                                        </span>
                                      </div>
                                    ),
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="glass-card" style={{ padding: "25px" }}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "15px",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1.1rem",
                                fontWeight: 700,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="Library" size={20} /> Select Standards
                              ({selectedStandards.length})
                            </h3>
                            <span
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              {standards.length} standards available
                            </span>
                          </div>

                          {/* Current config display */}
                          <div
                            style={{
                              display: "flex",
                              gap: "10px",
                              marginBottom: "15px",
                              flexWrap: "wrap",
                            }}
                          >
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(99,102,241,0.15)",
                                color: "var(--accent-light)",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="MapPin"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {{
                                FL: "Florida",
                                TX: "Texas",
                                CA: "California",
                                NY: "New York",
                                GA: "Georgia",
                                NC: "North Carolina",
                                VA: "Virginia",
                                OH: "Ohio",
                                PA: "Pennsylvania",
                                IL: "Illinois",
                              }[config.state] || config.state}
                            </span>
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(74,222,128,0.15)",
                                color: "#4ade80",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="GraduationCap"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              Grade {config.grade_level}
                            </span>
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(251,191,36,0.15)",
                                color: "#fbbf24",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="BookOpen"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {config.subject}
                            </span>
                          </div>

                          {/* Domain jump bar */}
                          {standards.length > 0 && getDomains(standards).length > 1 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                              {getDomains(standards).map((domain) => {
                                const count = selectedStandards.filter((c) => c.split(".")[2] === domain).length;
                                return (
                                  <button key={domain} onClick={() => scrollToDomain(standardsScrollRef, domain)}
                                    style={{
                                      padding: "4px 10px", fontSize: "0.75rem", fontWeight: 600,
                                      borderRadius: "20px", border: "none", cursor: "pointer",
                                      background: count > 0 ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                                      color: count > 0 ? "#a78bfa" : "var(--text-secondary)",
                                      transition: "all 0.2s",
                                    }}
                                  >
                                    {domainNameMap[domain] || domain}{count > 0 ? " (" + count + ")" : ""}
                                  </button>
                                );
                              })}
                            </div>
                          )}

                          <div
                            ref={standardsScrollRef}
                            style={{ maxHeight: "500px", overflowY: "auto" }}
                          >
                            {plannerLoading && standards.length === 0 ? (
                              <div
                                style={{
                                  textAlign: "center",
                                  padding: "40px",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                <Icon
                                  name="Loader2"
                                  size={30}
                                  style={{
                                    animation: "spin 1s linear infinite",
                                  }}
                                />
                                <p style={{ marginTop: "10px" }}>
                                  Loading standards...
                                </p>
                              </div>
                            ) : standards.length > 0 ? (
                              standards.map((std) => (
                                <div key={std.code} data-domain={std.code.split(".")[2]}>
                                <StandardCard
                                  standard={std}
                                  isSelected={selectedStandards.includes(
                                    std.code,
                                  )}
                                  onToggle={() => toggleStandard(std.code)}
                                  isExpanded={expandedStandards.includes(
                                    std.code,
                                  )}
                                  onExpand={() =>
                                    setExpandedStandards((prev) =>
                                      prev.includes(std.code)
                                        ? prev.filter((c) => c !== std.code)
                                        : [...prev, std.code],
                                    )
                                  }
                                />
                                </div>
                              ))
                            ) : (
                              <div
                                style={{
                                  textAlign: "center",
                                  padding: "40px",
                                  background: "var(--glass-bg)",
                                  borderRadius: "12px",
                                }}
                              >
                                <Icon
                                  name="FileQuestion"
                                  size={40}
                                  style={{
                                    color: "var(--text-muted)",
                                    marginBottom: "15px",
                                  }}
                                />
                                <p
                                  style={{
                                    color: "var(--text-secondary)",
                                    marginBottom: "10px",
                                  }}
                                >
                                  No standards found for Grade{" "}
                                  {config.grade_level} {config.subject}.
                                </p>
                                <p
                                  style={{
                                    color: "var(--text-muted)",
                                    fontSize: "0.85rem",
                                  }}
                                >
                                  Try a different grade level or subject in
                                  Settings.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  )}

                  {/* Assessment Generator Mode */}
                  {plannerMode === "assessment" && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "350px 1fr",
                        gap: "25px",
                      }}
                    >
                      {/* Assessment Config Sidebar */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Assessment Type */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <h3
                            style={{
                              fontSize: "1.1rem",
                              fontWeight: 700,
                              marginBottom: "15px",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="Settings" size={20} /> Assessment Settings
                          </h3>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "15px",
                            }}
                          >
                            <div>
                              <label className="label">Assessment Type</label>
                              <select
                                className="input"
                                value={assessmentConfig.type}
                                onChange={(e) =>
                                  setAssessmentConfig({
                                    ...assessmentConfig,
                                    type: e.target.value,
                                  })
                                }
                              >
                                <option value="quiz">Quiz</option>
                                <option value="test">Test</option>
                                <option value="benchmark">Benchmark Assessment</option>
                                <option value="formative">Formative Check</option>
                              </select>
                            </div>
                            <div>
                              <label className="label">Title (Optional)</label>
                              <input
                                type="text"
                                className="input"
                                value={assessmentConfig.title}
                                onChange={(e) =>
                                  setAssessmentConfig({
                                    ...assessmentConfig,
                                    title: e.target.value,
                                  })
                                }
                                placeholder="Auto-generated from standards"
                              />
                            </div>
                            <div>
                              <label className="label">Target Period</label>
                              {periods.length > 0 ? (
                                <select
                                  className="input"
                                  value={assessmentConfig.targetPeriod}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      targetPeriod: e.target.value,
                                    })
                                  }
                                  style={{ width: "100%" }}
                                >
                                  <option value="">-- No specific period --</option>
                                  {periods.map((p) => (
                                    <option key={p.filename} value={p.period_name}>{p.period_name}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type="text"
                                  className="input"
                                  value={assessmentConfig.targetPeriod}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      targetPeriod: e.target.value,
                                    })
                                  }
                                  placeholder="e.g., Period 1, Advanced, Standard"
                                  style={{ width: "100%" }}
                                />
                              )}
                              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                                Match to your Global AI Instructions
                              </p>
                            </div>
                            <div style={{ display: "flex", gap: "15px" }}>
                              <div style={{ flex: 1 }}>
                                <label className="label">Total Questions</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.totalQuestions}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    const newTotal = val === '' ? '' : parseInt(val);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalQuestions: newTotal,
                                    });
                                  }}
                                  onBlur={(e) => {
                                    const val = parseInt(e.target.value) || 10;
                                    const clamped = Math.max(5, Math.min(50, val));
                                    const newTypes = distributeQuestions(clamped);
                                    const newDok = distributeDOK(clamped);
                                    const newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);

                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalQuestions: clamped,
                                      questionTypes: newTypes,
                                      dokDistribution: newDok,
                                      pointsPerType: newPointsPerType,
                                    });
                                  }}
                                  min="5"
                                  max="50"
                                />
                              </div>
                              <div style={{ flex: 1 }}>
                                <label className="label">Total Points</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.totalPoints}
                                  onChange={(e) => {
                                    const val = e.target.value;
                                    // Allow empty while typing, parse as number
                                    const newTotalPoints = val === '' ? '' : parseInt(val);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalPoints: newTotalPoints,
                                    });
                                  }}
                                  onBlur={(e) => {
                                    // On blur, ensure valid value and recalculate points
                                    const val = parseInt(e.target.value) || 30;
                                    const clamped = Math.max(10, Math.min(200, val));
                                    const newPointsPerType = distributePoints(clamped, assessmentConfig.questionTypes);
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      totalPoints: clamped,
                                      pointsPerType: newPointsPerType,
                                    });
                                  }}
                                  min="10"
                                  max="200"
                                />
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Section Categories Dropdown */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <button
                            type="button"
                            onClick={() => setSectionsDropdownOpen(!sectionsDropdownOpen)}
                            style={{
                              width: "100%",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              padding: 0,
                              color: "inherit",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1rem",
                                fontWeight: 700,
                                margin: 0,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="LayoutGrid" size={18} /> Assessment Sections
                              <span style={{
                                fontSize: "0.75rem",
                                fontWeight: 400,
                                color: "var(--text-muted)",
                                marginLeft: "4px",
                              }}>
                                ({Object.values(assessmentConfig.sectionCategories || {}).filter(function(v) { return v > 0; }).length} types)
                              </span>
                            </h3>
                            <Icon name={sectionsDropdownOpen ? "ChevronUp" : "ChevronDown"} size={18} />
                          </button>

                          {sectionsDropdownOpen && (
                            <div style={{ marginTop: "15px" }}>
                              {(function() {
                                var totalAssigned = Object.values(assessmentConfig.sectionCategories || {}).reduce(function(a, b) { return a + b; }, 0);
                                var totalTarget = assessmentConfig.totalQuestions || 20;
                                var statusColor = totalAssigned === totalTarget ? "#22c55e" : totalAssigned > totalTarget ? "#ef4444" : "#f59e0b";
                                return (
                                  React.createElement('div', {
                                    style: { fontSize: "0.8rem", fontWeight: 600, marginBottom: "8px", color: statusColor }
                                  },
                                    totalAssigned + "/" + totalTarget + " assigned" +
                                    (totalAssigned < totalTarget ? " — AI will distribute " + (totalTarget - totalAssigned) + " remaining" : "") +
                                    (totalAssigned > totalTarget ? " — exceeds total by " + (totalAssigned - totalTarget) : "")
                                  )
                                );
                              })()}
                              <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "8px" }}>
                                Set question counts per section. FL FAST-aligned defaults are pre-set.
                              </p>
                              {[
                                { key: "multiple_choice", label: "Multiple Choice", group: "core" },
                                { key: "short_answer", label: "Short Answer", group: "core" },
                                { key: "math_computation", label: "Math Computation", group: "stem" },
                                { key: "geometry_visual", label: "Geometry", group: "stem" },
                                { key: "graphing", label: "Graphing", group: "stem" },
                                { key: "data_analysis", label: "Data Analysis", group: "stem" },
                                { key: "extended_writing", label: "Extended Writing", group: "optional" },
                                { key: "vocabulary", label: "Vocabulary", group: "optional" },
                                { key: "true_false", label: "True / False", group: "optional" },
                                { key: "florida_fast", label: "FL FAST Items", group: "optional" },
                              ].map(function(cat, idx, arr) {
                                var prevGroup = idx > 0 ? arr[idx - 1].group : null;
                                var showDivider = cat.group !== prevGroup;
                                var groupLabels = { core: "FL FAST Core", stem: "STEM Visuals", optional: "Optional" };
                                var groupColors = { core: "#22c55e", stem: "#6366f1", optional: "var(--text-muted)" };
                                var count = (assessmentConfig.sectionCategories || {})[cat.key] || 0;
                                return (
                                  React.createElement('div', { key: cat.key },
                                    showDivider ? React.createElement('div', {
                                      style: { fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
                                        letterSpacing: "0.05em", color: groupColors[cat.group],
                                        marginTop: idx > 0 ? "8px" : 0, marginBottom: "4px" }
                                    }, groupLabels[cat.group]) : null,
                                    React.createElement('div', {
                                      style: { display: "flex", alignItems: "center", justifyContent: "space-between",
                                        padding: "6px 10px", borderRadius: "8px", fontSize: "0.9rem",
                                        background: count > 0 ? "rgba(99,102,241,0.1)" : "transparent",
                                        border: "1px solid " + (count > 0 ? "rgba(99,102,241,0.3)" : "rgba(255,255,255,0.05)"),
                                        transition: "all 0.2s" }
                                    },
                                      React.createElement('span', { style: { color: count > 0 ? "var(--text-primary)" : "var(--text-muted)", fontWeight: 500 } }, cat.label),
                                      React.createElement('input', {
                                        type: "number",
                                        min: 0,
                                        max: assessmentConfig.totalQuestions || 50,
                                        value: count,
                                        onChange: function(e) {
                                          var val = parseInt(e.target.value) || 0;
                                          var newCats = Object.assign({}, assessmentConfig.sectionCategories);
                                          newCats[cat.key] = Math.max(0, val);
                                          var newTypes = distributeQuestions(assessmentConfig.totalQuestions || 20, newCats);
                                          var newPointsPerType = distributePoints(assessmentConfig.totalPoints || 30, newTypes);
                                          setAssessmentConfig(Object.assign({}, assessmentConfig, {
                                            sectionCategories: newCats,
                                            questionTypes: newTypes,
                                            pointsPerType: newPointsPerType,
                                          }));
                                        },
                                        style: { width: "55px", padding: "4px 6px", borderRadius: "6px",
                                          border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                                          color: "var(--text-primary)", fontSize: "0.9rem", textAlign: "center" }
                                      })
                                    )
                                  )
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Question Types */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <h3
                            style={{
                              fontSize: "1rem",
                              fontWeight: 700,
                              marginBottom: "15px",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="List" size={18} /> Question Types
                          </h3>
                          {/* Column Headers */}
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              marginBottom: "8px",
                              paddingBottom: "8px",
                              borderBottom: "1px solid rgba(255,255,255,0.1)",
                            }}
                          >
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", flex: 1 }}>Type</span>
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", width: "70px", textAlign: "center" }}>Count</span>
                            <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.6)", width: "70px", textAlign: "center" }}>Points</span>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "12px",
                            }}
                          >
                            {[
                              { key: "multiple_choice", label: "Multiple Choice", defaultPts: 1 },
                              { key: "short_answer", label: "Short Answer", defaultPts: 2 },
                              { key: "extended_response", label: "Extended Response", defaultPts: 4 },
                              { key: "true_false", label: "True/False", defaultPts: 1 },
                              { key: "matching", label: "Matching", defaultPts: 1 },
                              { key: "math_equation", label: "Math Equation (STEM)", defaultPts: 2 },
                              { key: "data_table", label: "Data Table (STEM)", defaultPts: 3 },
                              { key: "multiselect", label: "Multiselect (FAST)", defaultPts: 2 },
                              { key: "multi_part", label: "Multi-Part (FAST)", defaultPts: 2 },
                              { key: "grid_match", label: "Grid Match (FAST)", defaultPts: 3 },
                              { key: "inline_dropdown", label: "Inline Dropdown (FAST)", defaultPts: 2 },
                            ].map((qType) => (
                              <div
                                key={qType.key}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <label style={{ fontSize: "0.9rem", flex: 1 }}>{qType.label}</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.questionTypes[qType.key] || 0}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      questionTypes: {
                                        ...assessmentConfig.questionTypes,
                                        [qType.key]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px", textAlign: "center" }}
                                  min="0"
                                  max="30"
                                  title="Number of questions"
                                />
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.pointsPerType?.[qType.key] ?? qType.defaultPts}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      pointsPerType: {
                                        ...assessmentConfig.pointsPerType,
                                        [qType.key]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px", textAlign: "center", marginLeft: "8px" }}
                                  min="0"
                                  max="100"
                                  title="Points per question"
                                />
                              </div>
                            ))}
                          </div>
                          {/* Totals Display */}
                          <div
                            style={{
                              marginTop: "15px",
                              paddingTop: "12px",
                              borderTop: "1px solid rgba(255,255,255,0.1)",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total Questions:</span>
                              {(() => {
                                const calculated = Object.values(assessmentConfig.questionTypes || {}).reduce((a, b) => a + b, 0);
                                const target = assessmentConfig.totalQuestions || 20;
                                const matches = calculated === target;
                                return (
                                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                    <span style={{ fontSize: "1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                      {calculated}
                                    </span>
                                    {!matches && (
                                      <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                        (target: {target})
                                      </span>
                                    )}
                                  </span>
                                );
                              })()}
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total Points:</span>
                            {(() => {
                              const calculated = Object.entries(assessmentConfig.questionTypes || {}).reduce((total, [key, count]) => {
                                const pts = assessmentConfig.pointsPerType?.[key] || { multiple_choice: 1, short_answer: 2, extended_response: 4, true_false: 1, matching: 1 }[key] || 1;
                                return total + (count * pts);
                              }, 0);
                              const target = assessmentConfig.totalPoints || 30;
                              const matches = calculated === target;
                              return (
                                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                  <span style={{ fontSize: "1.1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                    {calculated}
                                  </span>
                                  {!matches && (
                                    <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                      (target: {target})
                                    </span>
                                  )}
                                </span>
                              );
                            })()}
                            </div>
                          </div>
                        </div>

                        {/* DOK Distribution */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <h3
                            style={{
                              fontSize: "1rem",
                              fontWeight: 700,
                              marginBottom: "15px",
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                            }}
                          >
                            <Icon name="BarChart3" size={18} /> DOK Distribution
                          </h3>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "12px",
                            }}
                          >
                            {[
                              { level: "1", label: "DOK 1 - Recall", color: "#22c55e" },
                              { level: "2", label: "DOK 2 - Skills", color: "#3b82f6" },
                              { level: "3", label: "DOK 3 - Strategic", color: "#f59e0b" },
                              { level: "4", label: "DOK 4 - Extended", color: "#ef4444" },
                            ].map((dok) => (
                              <div
                                key={dok.level}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <label
                                  style={{
                                    fontSize: "0.9rem",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                  }}
                                >
                                  <span
                                    style={{
                                      width: "12px",
                                      height: "12px",
                                      borderRadius: "50%",
                                      background: dok.color,
                                    }}
                                  />
                                  {dok.label}
                                </label>
                                <input
                                  type="number"
                                  className="input"
                                  value={assessmentConfig.dokDistribution[dok.level] || 0}
                                  onChange={(e) =>
                                    setAssessmentConfig({
                                      ...assessmentConfig,
                                      dokDistribution: {
                                        ...assessmentConfig.dokDistribution,
                                        [dok.level]: parseInt(e.target.value) || 0,
                                      },
                                    })
                                  }
                                  style={{ width: "70px" }}
                                  min="0"
                                  max="20"
                                />
                              </div>
                            ))}
                          </div>
                          {/* DOK Total Display */}
                          <div
                            style={{
                              marginTop: "12px",
                              paddingTop: "12px",
                              borderTop: "1px solid rgba(255,255,255,0.1)",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>Total:</span>
                            {(() => {
                              const calculated = Object.values(assessmentConfig.dokDistribution || {}).reduce((a, b) => a + b, 0);
                              const target = assessmentConfig.totalQuestions || 20;
                              const matches = calculated === target;
                              return (
                                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                  <span style={{ fontSize: "1rem", fontWeight: 700, color: matches ? "#22c55e" : "#f59e0b" }}>
                                    {calculated}
                                  </span>
                                  {!matches && (
                                    <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.5)" }}>
                                      (target: {target})
                                    </span>
                                  )}
                                </span>
                              );
                            })()}
                          </div>
                        </div>

                        {/* Generate Button */}
                        <button
                          onClick={generateAssessmentHandler}
                          disabled={(selectedStandards.length === 0 && uploadedDocs.length === 0) || assessmentLoading}
                          className="btn btn-primary"
                          style={{
                            padding: "14px 24px",
                            fontSize: "1rem",
                            opacity: (selectedStandards.length === 0 && uploadedDocs.length === 0) ? 0.5 : 1,
                          }}
                        >
                          {assessmentLoading ? (
                            <>
                              <Icon name="Loader2" size={20} className="spin" />
                              Generating Assessment...
                            </>
                          ) : (
                            <>
                              <Icon name="Sparkles" size={20} />
                              Generate Assessment
                            </>
                          )}
                        </button>
                      </div>

                      {/* Main Content Area */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Content Sources Panel */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                            <div>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "5px", display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="BookOpen" size={20} />
                                Content Sources
                              </h3>
                              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                Select lessons and assignments to generate questions from your actual instruction
                              </p>
                            </div>
                            <button
                              onClick={fetchSavedLessons}
                              className="btn btn-secondary"
                              style={{ padding: "6px 12px" }}
                            >
                              <Icon name="RefreshCw" size={14} />
                            </button>
                          </div>

                          {Object.keys(savedLessons.units || {}).length === 0 ? (
                            <div style={{
                              padding: "20px",
                              background: "rgba(255,255,255,0.03)",
                              borderRadius: "10px",
                              textAlign: "center"
                            }}>
                              <Icon name="FolderOpen" size={24} style={{ color: "var(--text-muted)", marginBottom: "10px" }} />
                              <p style={{ color: "var(--text-secondary)", marginBottom: "10px" }}>
                                No saved lessons yet
                              </p>
                              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                Save lessons from the Lesson Planner to use them here. Saved assignments from the Assignment Builder will also appear below.
                              </p>
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
                              {Object.entries(savedLessons.units).map(([unitName, lessons]) => (
                                <div key={unitName}>
                                  <h4 style={{
                                    fontSize: "0.9rem",
                                    fontWeight: 600,
                                    marginBottom: "10px",
                                    color: "var(--primary)"
                                  }}>
                                    {unitName}
                                  </h4>
                                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                                    {lessons.map((lesson) => {
                                      const isSelected = selectedSources.some(
                                        s => s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename
                                      );
                                      return (
                                        <button
                                          key={lesson.filename}
                                          onClick={async () => {
                                            if (isSelected) {
                                              setSelectedSources(selectedSources.filter(
                                                s => !(s.type === 'lesson' && s.unit === unitName && s.filename === lesson.filename)
                                              ));
                                            } else {
                                              // Load full lesson content
                                              const data = await api.loadLesson(unitName, lesson.filename);
                                              if (data.lesson) {
                                                setSelectedSources([...selectedSources, {
                                                  type: 'lesson',
                                                  unit: unitName,
                                                  filename: lesson.filename,
                                                  title: lesson.title,
                                                  content: data.lesson
                                                }]);
                                              }
                                            }
                                          }}
                                          style={{
                                            padding: "8px 14px",
                                            borderRadius: "8px",
                                            border: isSelected ? "2px solid var(--primary)" : "1px solid var(--glass-border)",
                                            background: isSelected ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.05)",
                                            color: isSelected ? "var(--primary)" : "var(--text-primary)",
                                            cursor: "pointer",
                                            fontSize: "0.85rem",
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "6px"
                                          }}
                                        >
                                          <Icon name={isSelected ? "CheckCircle" : "FileText"} size={14} />
                                          {lesson.title}
                                        </button>
                                      );
                                    })}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Saved Assignments Section */}
                          {savedAssignments.length > 0 && (
                            <div style={{ marginTop: "20px", paddingTop: "15px", borderTop: "1px solid var(--glass-border)" }}>
                              <h4 style={{
                                fontSize: "0.9rem",
                                fontWeight: 600,
                                marginBottom: "10px",
                                color: "var(--accent-primary)",
                                display: "flex",
                                alignItems: "center",
                                gap: "8px"
                              }}>
                                <Icon name="ClipboardList" size={16} />
                                Saved Assignments
                              </h4>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                                {savedAssignments.map((assignmentName) => {
                                  const isSelected = selectedSources.some(
                                    s => s.type === 'assignment' && s.filename === assignmentName
                                  );
                                  return (
                                    <button
                                      key={assignmentName}
                                      onClick={async () => {
                                        if (isSelected) {
                                          setSelectedSources(selectedSources.filter(
                                            s => !(s.type === 'assignment' && s.filename === assignmentName)
                                          ));
                                        } else {
                                          // Load full assignment content
                                          const data = await api.loadAssignment(assignmentName);
                                          if (data.assignment) {
                                            setSelectedSources([...selectedSources, {
                                              type: 'assignment',
                                              filename: assignmentName,
                                              title: data.assignment.title || assignmentName,
                                              content: data.assignment
                                            }]);
                                          }
                                        }
                                      }}
                                      style={{
                                        padding: "8px 14px",
                                        borderRadius: "8px",
                                        border: isSelected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                        background: isSelected ? "rgba(251, 191, 36, 0.2)" : "rgba(255,255,255,0.05)",
                                        color: isSelected ? "var(--accent-primary)" : "var(--text-primary)",
                                        cursor: "pointer",
                                        fontSize: "0.85rem",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "6px"
                                      }}
                                    >
                                      <Icon name={isSelected ? "CheckCircle" : "FileText"} size={14} />
                                      {savedAssignmentData[assignmentName]?.title || assignmentName}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {selectedSources.length > 0 && (
                            <div style={{
                              marginTop: "15px",
                              padding: "10px 15px",
                              background: "rgba(34, 197, 94, 0.1)",
                              borderRadius: "8px",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between"
                            }}>
                              <span style={{ color: "#22c55e", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}>
                                <Icon name="Check" size={16} />
                                {selectedSources.length} source{selectedSources.length > 1 ? 's' : ''} selected - questions will be based on this content
                              </span>
                              <button
                                onClick={() => setSelectedSources([])}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  fontSize: "0.85rem"
                                }}
                              >
                                Clear
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Standards Selection */}
                        <div className="glass-card" style={{ padding: "20px" }}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "15px",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1.1rem",
                                fontWeight: 700,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="Target" size={20} />
                              Select Standards ({selectedStandards.length} selected)
                            </h3>
                            {selectedStandards.length > 0 && (
                              <button
                                onClick={() => setSelectedStandards([])}
                                className="btn btn-secondary"
                                style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                              >
                                Clear All
                              </button>
                            )}
                          </div>
                          {/* Domain jump bar */}
                          {standards.length > 0 && getDomains(standards).length > 1 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                              {getDomains(standards).map((domain) => {
                                const count = selectedStandards.filter((c) => c.split(".")[2] === domain).length;
                                return (
                                  <button key={domain} onClick={() => scrollToDomain(assessmentStandardsScrollRef, domain)}
                                    style={{
                                      padding: "4px 10px", fontSize: "0.75rem", fontWeight: 600,
                                      borderRadius: "20px", border: "none", cursor: "pointer",
                                      background: count > 0 ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                                      color: count > 0 ? "#a78bfa" : "var(--text-secondary)",
                                      transition: "all 0.2s",
                                    }}
                                  >
                                    {domainNameMap[domain] || domain}{count > 0 ? " (" + count + ")" : ""}
                                  </button>
                                );
                              })}
                            </div>
                          )}

                          <div
                            ref={assessmentStandardsScrollRef}
                            style={{
                              maxHeight: "300px",
                              overflowY: "auto",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            {plannerLoading ? (
                              <div style={{ textAlign: "center", padding: "20px" }}>
                                <Icon name="Loader2" size={24} className="spin" />
                                <p style={{ marginTop: "10px" }}>Loading standards...</p>
                              </div>
                            ) : standards.length > 0 ? (
                              standards.map((std) => (
                                <div
                                  key={std.code}
                                  data-domain={std.code.split(".")[2]}
                                  onClick={() => toggleStandard(std.code)}
                                  style={{
                                    padding: "12px 15px",
                                    background: selectedStandards.includes(std.code)
                                      ? "rgba(139, 92, 246, 0.15)"
                                      : "var(--glass-bg)",
                                    border: selectedStandards.includes(std.code)
                                      ? "1px solid rgba(139, 92, 246, 0.4)"
                                      : "1px solid var(--glass-border)",
                                    borderRadius: "10px",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "flex-start",
                                      gap: "12px",
                                    }}
                                  >
                                    <div
                                      style={{
                                        width: "20px",
                                        height: "20px",
                                        borderRadius: "6px",
                                        border: selectedStandards.includes(std.code)
                                          ? "none"
                                          : "2px solid var(--glass-border)",
                                        background: selectedStandards.includes(std.code)
                                          ? "linear-gradient(135deg, #8b5cf6, #6366f1)"
                                          : "transparent",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        flexShrink: 0,
                                        marginTop: "2px",
                                      }}
                                    >
                                      {selectedStandards.includes(std.code) && (
                                        <Icon name="Check" size={14} style={{ color: "#fff" }} />
                                      )}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                      <div
                                        style={{
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "10px",
                                          marginBottom: "4px",
                                        }}
                                      >
                                        <span style={{ fontWeight: 700, color: "var(--accent-primary)" }}>
                                          {std.code}
                                        </span>
                                        <span
                                          style={{
                                            padding: "2px 8px",
                                            borderRadius: "12px",
                                            fontSize: "0.75rem",
                                            fontWeight: 600,
                                            background:
                                              std.dok === 1
                                                ? "rgba(34, 197, 94, 0.15)"
                                                : std.dok === 2
                                                  ? "rgba(59, 130, 246, 0.15)"
                                                  : std.dok === 3
                                                    ? "rgba(245, 158, 11, 0.15)"
                                                    : "rgba(239, 68, 68, 0.15)",
                                            color:
                                              std.dok === 1
                                                ? "#22c55e"
                                                : std.dok === 2
                                                  ? "#3b82f6"
                                                  : std.dok === 3
                                                    ? "#f59e0b"
                                                    : "#ef4444",
                                          }}
                                        >
                                          DOK {std.dok}
                                        </span>
                                      </div>
                                      <p
                                        style={{
                                          fontSize: "0.85rem",
                                          color: "var(--text-secondary)",
                                          margin: 0,
                                          lineHeight: 1.4,
                                        }}
                                      >
                                        {std.benchmark.length > 150
                                          ? std.benchmark.slice(0, 150) + "..."
                                          : std.benchmark}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))
                            ) : (
                              <div style={{ textAlign: "center", padding: "30px" }}>
                                <Icon
                                  name="FileQuestion"
                                  size={40}
                                  style={{ color: "var(--text-muted)", marginBottom: "10px" }}
                                />
                                <p style={{ color: "var(--text-secondary)" }}>
                                  No standards found. Check your grade and subject in Settings.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Generated Assessment Preview */}
                        {generatedAssessment && (
                          <div className="glass-card" style={{ padding: "25px" }}>
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "flex-start",
                                marginBottom: "20px",
                              }}
                            >
                              <div>
                                <h2
                                  style={{
                                    fontSize: "1.4rem",
                                    fontWeight: 700,
                                    marginBottom: "8px",
                                  }}
                                >
                                  {generatedAssessment.title}
                                </h2>
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "15px",
                                    fontSize: "0.9rem",
                                    color: "var(--text-secondary)",
                                    alignItems: "center",
                                  }}
                                >
                                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                    <Icon name="Award" size={14} />
                                    <input
                                      type="number"
                                      min="1"
                                      value={generatedAssessment.total_points}
                                      onChange={(e) => {
                                        const newTotal = parseInt(e.target.value) || 1;
                                        redistributePoints(newTotal);
                                      }}
                                      style={{
                                        width: "60px",
                                        padding: "4px 8px",
                                        background: "rgba(255,255,255,0.1)",
                                        border: "1px solid var(--glass-border)",
                                        borderRadius: "6px",
                                        color: "var(--text-primary)",
                                        fontSize: "0.9rem",
                                        textAlign: "center",
                                      }}
                                    />
                                    <span>points</span>
                                  </div>
                                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                                    <Icon name="Clock" size={14} />
                                    {generatedAssessment.time_limit != null ? (
                                      <>
                                        <input
                                          type="number"
                                          min="1"
                                          value={generatedAssessment.time_limit}
                                          onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            setGeneratedAssessment({ ...generatedAssessment, time_limit: val > 0 ? val : 1 });
                                          }}
                                          style={{
                                            width: "60px",
                                            padding: "4px 8px",
                                            background: "rgba(255,255,255,0.1)",
                                            border: "1px solid var(--glass-border)",
                                            borderRadius: "6px",
                                            color: "var(--text-primary)",
                                            fontSize: "0.9rem",
                                            textAlign: "center",
                                          }}
                                        />
                                        <span>min</span>
                                        <button
                                          onClick={() => setGeneratedAssessment({ ...generatedAssessment, time_limit: null })}
                                          style={{
                                            background: "none",
                                            border: "none",
                                            color: "var(--text-muted)",
                                            cursor: "pointer",
                                            padding: "2px 4px",
                                            fontSize: "0.85rem",
                                            lineHeight: 1,
                                          }}
                                          title="Remove time limit"
                                        >
                                          ✕
                                        </button>
                                      </>
                                    ) : (
                                      <button
                                        onClick={() => setGeneratedAssessment({ ...generatedAssessment, time_limit: 30 })}
                                        style={{
                                          background: "none",
                                          border: "none",
                                          color: "var(--accent-secondary)",
                                          cursor: "pointer",
                                          padding: "0",
                                          fontSize: "0.85rem",
                                          textDecoration: "none",
                                        }}
                                        onMouseEnter={(e) => e.target.style.textDecoration = "underline"}
                                        onMouseLeave={(e) => e.target.style.textDecoration = "none"}
                                      >
                                        + Set time limit
                                      </button>
                                    )}
                                  </div>
                                  <span>
                                    {generatedAssessment.sections?.reduce(
                                      (sum, s) => sum + (s.questions?.length || 0),
                                      0
                                    )}{" "}
                                    questions
                                  </span>
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "15px" }}>
                                <button
                                  onClick={() => {
                                    setGeneratedAssessment(null);
                                    setAssessmentAnswers({});
                                    setSelectedSources([]);
                                  }}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: "rgba(239, 68, 68, 0.2)",
                                    border: "1px solid rgba(239, 68, 68, 0.3)"
                                  }}
                                  title="Clear assessment and start over"
                                >
                                  <Icon name="X" size={16} />
                                  Clear
                                </button>
                                <button
                                  onClick={() => exportAssessmentHandler(false)}
                                  className="btn btn-secondary"
                                  style={{ padding: "8px 16px" }}
                                >
                                  <Icon name="FileText" size={16} />
                                  Word Doc
                                </button>
                                <button
                                  onClick={() => exportAssessmentHandler(true)}
                                  className="btn btn-secondary"
                                  style={{ padding: "8px 16px" }}
                                >
                                  <Icon name="Key" size={16} />
                                  With Answer Key
                                </button>
                                <button
                                  onClick={gradeAssessmentAnswersHandler}
                                  disabled={gradingAssessment || Object.keys(assessmentAnswers).length === 0}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: Object.keys(assessmentAnswers).length > 0 ? "linear-gradient(135deg, #22c55e, #16a34a)" : "rgba(255,255,255,0.1)",
                                    opacity: Object.keys(assessmentAnswers).length === 0 ? 0.5 : 1,
                                  }}
                                >
                                  <Icon name={gradingAssessment ? "Loader" : "CheckCircle"} size={16} />
                                  {gradingAssessment ? "Grading..." : "Grade My Answers"}
                                </button>
                                <button
                                  onClick={() => { setEditMode((prev) => !prev); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                  className={editMode ? "btn btn-primary" : "btn btn-secondary"}
                                  style={{ padding: "8px 16px", ...(editMode ? { background: "linear-gradient(135deg, #f59e0b, #d97706)" } : {}) }}
                                  title={editMode ? "Exit edit mode" : "Edit individual questions"}
                                >
                                  <Icon name={editMode ? "X" : "Pencil"} size={16} />
                                  {editMode ? " Exit Edit" : " Edit Questions"}
                                </button>
                                <div style={{ position: "relative" }}>
                                  <button
                                    onClick={() => setShowPlatformExport(!showPlatformExport)}
                                    className="btn btn-primary"
                                    style={{ padding: "8px 16px" }}
                                  >
                                    <Icon name="Upload" size={16} />
                                    Export to Platform
                                    <Icon name="ChevronDown" size={14} style={{ marginLeft: "4px" }} />
                                  </button>
                                  <PlatformExportMenu
                                    open={showPlatformExport}
                                    onSelect={(platformId) => {
                                      exportAssessmentForPlatformHandler(platformId);
                                      setShowPlatformExport(false);
                                    }}
                                  />
                                </div>
                                <button
                                  onClick={publishAssessmentHandler}
                                  disabled={publishingAssessment}
                                  className="btn"
                                  style={{
                                    padding: "8px 16px",
                                    background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
                                  }}
                                >
                                  <Icon name={publishingAssessment ? "Loader" : "Share2"} size={16} />
                                  {publishingAssessment ? "Publishing..." : "Publish to Portal"}
                                </button>
                              </div>
                            </div>

                            {/* Save Assessment Section */}
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                marginBottom: "20px",
                                padding: "15px",
                                background: "var(--glass-bg)",
                                borderRadius: "10px",
                              }}
                            >
                              <Icon name="Save" size={20} style={{ color: "var(--accent-secondary)" }} />
                              <input
                                type="text"
                                placeholder="Assessment name..."
                                value={saveAssessmentName}
                                onChange={(e) => setSaveAssessmentName(e.target.value)}
                                style={{
                                  flex: 1,
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                  border: "1px solid var(--glass-border)",
                                  background: "var(--surface)",
                                  color: "var(--text-primary)",
                                  fontSize: "0.9rem",
                                }}
                              />
                              <button
                                onClick={saveAssessmentHandler}
                                disabled={savingAssessment || !saveAssessmentName.trim()}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name={savingAssessment ? "Loader" : "Save"} size={16} />
                                {savingAssessment ? "Saving..." : "Save for Later"}
                              </button>
                            </div>

                            {/* DOK Summary */}
                            {generatedAssessment.dok_summary && (
                              <div
                                style={{
                                  display: "flex",
                                  gap: "15px",
                                  marginBottom: "20px",
                                  padding: "15px",
                                  background: "var(--glass-bg)",
                                  borderRadius: "10px",
                                }}
                              >
                                {[
                                  { level: 1, color: "#22c55e", label: "DOK 1" },
                                  { level: 2, color: "#3b82f6", label: "DOK 2" },
                                  { level: 3, color: "#f59e0b", label: "DOK 3" },
                                  { level: 4, color: "#ef4444", label: "DOK 4" },
                                ].map((dok) => (
                                  <div
                                    key={dok.level}
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: "8px",
                                    }}
                                  >
                                    <span
                                      style={{
                                        width: "10px",
                                        height: "10px",
                                        borderRadius: "50%",
                                        background: dok.color,
                                      }}
                                    />
                                    <span style={{ fontSize: "0.85rem" }}>
                                      {dok.label}:{" "}
                                      {generatedAssessment.dok_summary[`dok_${dok.level}_count`] || 0}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Instructions */}
                            {generatedAssessment.instructions && (
                              <div
                                style={{
                                  padding: "15px",
                                  background: "rgba(99, 102, 241, 0.1)",
                                  borderRadius: "10px",
                                  marginBottom: "20px",
                                }}
                              >
                                <strong>Instructions:</strong> {generatedAssessment.instructions}
                              </div>
                            )}

                            {/* Edit Toolbar */}
                            {editMode && (
                              <QuestionEditToolbar
                                selectedCount={selectedQuestions.size}
                                totalCount={getTotalQuestionCount()}
                                onSelectAll={selectAllQuestions}
                                onDeselectAll={() => setSelectedQuestions(new Set())}
                                onDeleteSelected={deleteSelectedQuestions}
                                onRegenerateSelected={regenerateSelectedQuestions}
                                onDoneEditing={() => { setEditMode(false); setSelectedQuestions(new Set()); setEditingQuestion(null); }}
                                isRegenerating={regeneratingQuestions.size > 0}
                              />
                            )}

                            {/* Sections */}
                            {generatedAssessment.sections?.map((section, sIdx) => (
                              <div key={sIdx} style={{ marginBottom: "25px" }}>
                                <h4
                                  style={{
                                    fontSize: "1.1rem",
                                    fontWeight: 700,
                                    marginBottom: "10px",
                                    color: "var(--accent-primary)",
                                  }}
                                >
                                  {section.name}
                                </h4>
                                {section.instructions && (
                                  <p
                                    style={{
                                      fontSize: "0.9rem",
                                      color: "var(--text-secondary)",
                                      marginBottom: "15px",
                                      fontStyle: "italic",
                                    }}
                                  >
                                    {section.instructions}
                                  </p>
                                )}
                                <div
                                  style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: "12px",
                                  }}
                                >
                                  {section.questions?.map((q, qIdx) => {
                                    const qCard = (
                                    <div
                                      key={qIdx}
                                      style={{
                                        padding: "15px",
                                        background: "var(--glass-bg)",
                                        borderRadius: "10px",
                                        borderLeft: `4px solid ${
                                          q.dok === 1
                                            ? "#22c55e"
                                            : q.dok === 2
                                              ? "#3b82f6"
                                              : q.dok === 3
                                                ? "#f59e0b"
                                                : "#ef4444"
                                        }`,
                                      }}
                                    >
                                      <div
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <span style={{ fontWeight: 700 }}>
                                          {q.number}. {q.question}
                                        </span>
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "8px",
                                            fontSize: "0.75rem",
                                            flexWrap: "wrap",
                                          }}
                                        >
                                          {q.type && (
                                            <span
                                              style={{
                                                padding: "2px 8px",
                                                borderRadius: "8px",
                                                background: "rgba(100, 116, 139, 0.15)",
                                                color: "#94a3b8",
                                                textTransform: "capitalize",
                                              }}
                                            >
                                              {q.type.replace(/_/g, " ")}
                                            </span>
                                          )}
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background: "rgba(139, 92, 246, 0.15)",
                                              color: "#8b5cf6",
                                            }}
                                          >
                                            {q.points} pt{q.points > 1 ? "s" : ""}
                                          </span>
                                          <span
                                            style={{
                                              padding: "2px 8px",
                                              borderRadius: "8px",
                                              background:
                                                q.dok === 1
                                                  ? "rgba(34, 197, 94, 0.15)"
                                                  : q.dok === 2
                                                    ? "rgba(59, 130, 246, 0.15)"
                                                    : q.dok === 3
                                                      ? "rgba(245, 158, 11, 0.15)"
                                                      : "rgba(239, 68, 68, 0.15)",
                                              color:
                                                q.dok === 1
                                                  ? "#22c55e"
                                                  : q.dok === 2
                                                    ? "#3b82f6"
                                                    : q.dok === 3
                                                      ? "#f59e0b"
                                                      : "#ef4444",
                                            }}
                                          >
                                            DOK {q.dok}
                                          </span>
                                        </div>
                                      </div>
                                      {/* Quality warning badge */}
                                      {q.warning && (
                                        <div style={{
                                          padding: "6px 10px",
                                          background: q.warning_severity === "error" ? "rgba(239,68,68,0.15)" : q.warning_severity === "info" ? "rgba(59,130,246,0.15)" : "rgba(245,158,11,0.15)",
                                          border: q.warning_severity === "error" ? "1px solid rgba(239,68,68,0.3)" : q.warning_severity === "info" ? "1px solid rgba(59,130,246,0.3)" : "1px solid rgba(245,158,11,0.3)",
                                          borderRadius: "6px",
                                          fontSize: "0.8rem",
                                          color: q.warning_severity === "error" ? "#ef4444" : q.warning_severity === "info" ? "#3b82f6" : "#f59e0b",
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "6px",
                                          marginBottom: "8px",
                                        }}>
                                          <Icon name="AlertTriangle" size={14} />
                                          {q.warning}
                                        </div>
                                      )}
                                      {/* Multiple Choice Options - Interactive */}
                                      {q.options && q.options.length > 0 && (
                                        <div
                                          style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            gap: "8px",
                                            marginTop: "12px",
                                            paddingLeft: "15px",
                                          }}
                                        >
                                          {q.options.map((opt, oIdx) => {
                                            const answerKey = `${sIdx}-${qIdx}`;
                                            const isSelected = assessmentAnswers[answerKey] === oIdx;
                                            return (
                                              <label
                                                key={oIdx}
                                                onClick={() => setAssessmentAnswers({...assessmentAnswers, [answerKey]: oIdx})}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  gap: "10px",
                                                  padding: "10px 12px",
                                                  borderRadius: "8px",
                                                  cursor: "pointer",
                                                  background: isSelected ? "rgba(99, 102, 241, 0.2)" : "rgba(255,255,255,0.03)",
                                                  border: isSelected ? "2px solid var(--accent-primary)" : "2px solid transparent",
                                                  transition: "all 0.15s ease",
                                                }}
                                              >
                                                <span style={{
                                                  width: "20px",
                                                  height: "20px",
                                                  borderRadius: "50%",
                                                  border: isSelected ? "6px solid var(--accent-primary)" : "2px solid var(--text-muted)",
                                                  background: isSelected ? "white" : "transparent",
                                                  flexShrink: 0,
                                                }}></span>
                                                <span style={{ fontSize: "0.9rem", color: isSelected ? "white" : "var(--text-secondary)" }}>{opt}</span>
                                              </label>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {/* True/False Options - Interactive */}
                                      {q.type === "true_false" && (
                                        <div
                                          style={{
                                            display: "flex",
                                            gap: "15px",
                                            marginTop: "12px",
                                            paddingLeft: "15px",
                                          }}
                                        >
                                          {["True", "False"].map((tf) => {
                                            const answerKey = `${sIdx}-${qIdx}`;
                                            const isSelected = assessmentAnswers[answerKey] === tf;
                                            return (
                                              <label
                                                key={tf}
                                                onClick={() => setAssessmentAnswers({...assessmentAnswers, [answerKey]: tf})}
                                                style={{
                                                  display: "flex",
                                                  alignItems: "center",
                                                  gap: "10px",
                                                  padding: "12px 24px",
                                                  borderRadius: "8px",
                                                  cursor: "pointer",
                                                  background: isSelected ? (tf === "True" ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)") : "rgba(255,255,255,0.03)",
                                                  border: isSelected ? `2px solid ${tf === "True" ? "#22c55e" : "#ef4444"}` : "2px solid var(--text-muted)",
                                                  transition: "all 0.15s ease",
                                                }}
                                              >
                                                <span style={{
                                                  width: "20px",
                                                  height: "20px",
                                                  borderRadius: "50%",
                                                  border: isSelected ? `6px solid ${tf === "True" ? "#22c55e" : "#ef4444"}` : "2px solid var(--text-muted)",
                                                  background: isSelected ? "white" : "transparent",
                                                  flexShrink: 0,
                                                }}></span>
                                                <span style={{ fontSize: "0.95rem", fontWeight: 600, color: isSelected ? (tf === "True" ? "#22c55e" : "#ef4444") : "var(--text-secondary)" }}>{tf}</span>
                                              </label>
                                            );
                                          })}
                                        </div>
                                      )}
                                      {/* Matching - Interactive card game */}
                                      {q.type === "matching" && q.terms && q.definitions && (
                                        <MatchingCards
                                          terms={q.terms}
                                          definitions={q.definitions}
                                          correctAnswer={q.answer}
                                          showAnswers={previewShowAnswers}
                                          onMatch={function(matches, shuffledDefs) {
                                            var newAnswers = Object.assign({}, assessmentAnswers);
                                            Object.entries(matches).forEach(function(entry) {
                                              var tIdx = entry[0];
                                              var sdIdx = entry[1];
                                              var originalIdx = shuffledDefs && shuffledDefs[sdIdx] ? shuffledDefs[sdIdx].originalIdx : sdIdx;
                                              var matchKey = sIdx + "-" + qIdx + "-match-" + tIdx;
                                              newAnswers[matchKey] = String.fromCharCode(65 + originalIdx);
                                            });
                                            setAssessmentAnswers(newAnswers);
                                          }}
                                        />
                                      )}
                                      {/* Short Answer - Interactive text input */}
                                      {q.type === "short_answer" && !q.options && !q.terms && (
                                        <div style={{ marginTop: "12px", paddingLeft: "15px" }}>
                                          <textarea
                                            value={assessmentAnswers[`${sIdx}-${qIdx}`] || ""}
                                            onChange={(e) => setAssessmentAnswers({...assessmentAnswers, [`${sIdx}-${qIdx}`]: e.target.value})}
                                            placeholder="Type your answer here..."
                                            rows={3}
                                            style={{
                                              width: "100%",
                                              padding: "12px",
                                              borderRadius: "8px",
                                              border: "1px solid var(--text-muted)",
                                              background: "rgba(255,255,255,0.03)",
                                              color: "white",
                                              fontSize: "0.9rem",
                                              resize: "vertical",
                                              fontFamily: "inherit",
                                            }}
                                          />
                                        </div>
                                      )}
                                      {/* Extended Response - Interactive textarea */}
                                      {q.type === "extended_response" && !q.options && !q.terms && (
                                        <div style={{ marginTop: "12px", paddingLeft: "15px" }}>
                                          {q.rubric && (
                                            <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "10px", padding: "8px 12px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "6px", borderLeft: "3px solid #f59e0b" }}>
                                              <strong>Scoring Criteria:</strong> {q.rubric}
                                            </div>
                                          )}
                                          <textarea
                                            value={assessmentAnswers[`${sIdx}-${qIdx}`] || ""}
                                            onChange={(e) => setAssessmentAnswers({...assessmentAnswers, [`${sIdx}-${qIdx}`]: e.target.value})}
                                            placeholder="Write your extended response here. Be sure to include evidence and analysis to support your answer..."
                                            rows={6}
                                            style={{
                                              width: "100%",
                                              padding: "15px",
                                              borderRadius: "8px",
                                              border: "1px solid var(--text-muted)",
                                              background: "rgba(255,255,255,0.03)",
                                              color: "white",
                                              fontSize: "0.9rem",
                                              resize: "vertical",
                                              fontFamily: "inherit",
                                              lineHeight: 1.6,
                                            }}
                                          />
                                          <div style={{ marginTop: "6px", fontSize: "0.8rem", color: "var(--text-muted)", textAlign: "right" }}>
                                            {(assessmentAnswers[`${sIdx}-${qIdx}`] || "").split(/\s+/).filter(w => w).length} words
                                          </div>
                                        </div>
                                      )}
                                      {q.standard && (
                                        <div
                                          style={{
                                            marginTop: "8px",
                                            fontSize: "0.8rem",
                                            color: "var(--text-muted)",
                                          }}
                                        >
                                          Standard: {q.standard}
                                        </div>
                                      )}
                                    </div>
                                    );
                                    return editMode ? (
                                      <QuestionEditOverlay
                                        key={qIdx}
                                        question={q}
                                        sectionIndex={sIdx}
                                        questionIndex={qIdx}
                                        isSelected={selectedQuestions.has(sIdx + "-" + qIdx)}
                                        isEditing={editingQuestion === sIdx + "-" + qIdx}
                                        isRegenerating={regeneratingQuestions.has(sIdx + "-" + qIdx)}
                                        onToggleSelect={toggleQuestionSelect}
                                        onStartEdit={setEditingQuestion}
                                        onSaveEdit={saveEditedQuestion}
                                        onCancelEdit={() => setEditingQuestion(null)}
                                        onRegenerateOne={regenerateOneQuestion}
                                      >
                                        {qCard}
                                      </QuestionEditOverlay>
                                    ) : qCard;
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Student Portal Dashboard */}
                  {plannerMode === "dashboard" && (
                    <div className="fade-in">
                      {/* Teacher's Classes */}
                      <div className="glass-card" style={{ padding: "20px", marginBottom: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                  <Icon name="School" size={20} />
                                  Your Classes
                              </h3>
                              <button onClick={fetchTeacherClasses} className="btn btn-secondary" style={{ padding: "8px 12px", fontSize: "0.85rem" }}>
                                  <Icon name="RefreshCw" size={16} /> Refresh
                              </button>
                          </div>
                          {teacherClasses.length === 0 ? (
                              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                                  No classes yet. Classes are created automatically when you sync your roster via Clever, ClassLink, or CSV import.
                              </p>
                          ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {teacherClasses.map(function(cls) {
                                      return (
                                          <div key={cls.id} style={{
                                              padding: "12px 15px",
                                              background: "rgba(255,255,255,0.03)",
                                              borderRadius: "10px",
                                              border: "1px solid rgba(255,255,255,0.1)",
                                              display: "flex",
                                              justifyContent: "space-between",
                                              alignItems: "center",
                                          }}>
                                              <div>
                                                  <div style={{ fontWeight: 600 }}>{cls.name}</div>
                                                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                                      {"Code: " + cls.join_code + " | " + (cls.subject || "No subject") + " | " + ((cls.class_students || [{}])[0]?.count || 0) + " students"}
                                                  </div>
                                              </div>
                                          </div>
                                      );
                                  })}
                              </div>
                          )}
                      </div>
                      {/* Global tag filter — Content Tagging */}
                      <div className="glass-card" style={{ padding: "12px 16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon name="Tag" size={16} style={{ color: "var(--text-secondary)" }} />
                        <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Filter by tag:</label>
                        <select
                          value={selectedTagFilter}
                          onChange={function(e) { setSelectedTagFilter(e.target.value); }}
                          className="input"
                          style={{ padding: "6px 12px", fontSize: "0.85rem", minWidth: "220px" }}
                        >
                          <option value="all">All content ({allTeacherTags.length} tags)</option>
                          {allTeacherTags.map(function(t) {
                            return <option key={t} value={t}>{t}</option>;
                          })}
                        </select>
                        {selectedTagFilter !== 'all' && (
                          <button
                            onClick={function() { setSelectedTagFilter('all'); }}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Clear
                          </button>
                        )}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: selectedAssessmentResults ? "1fr 1fr" : "1fr", gap: "25px" }}>
                        {/* Published Content Lists — separated by content type */}
                        {[
                          { type: "assessment", label: "Published Assessments", icon: "ClipboardList", emptyText: "No published assessments yet.", emptyHint: "Generate an assessment and click \"Publish to Portal\" to get started." },
                          { type: "assignment", label: "Published Assignments", icon: "FileText", emptyText: "No published assignments yet.", emptyHint: "Generate an assignment and click \"Publish to Portal\" to get started." },
                        ].map((section) => {
                          var sectionItems = publishedAssessments.filter(function(a) {
                            return (a.content_type || "assessment") === section.type && itemMatchesTagFilter(a);
                          });
                          return (
                        <div key={section.type} className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                              <Icon name={section.icon} size={20} />
                              {section.label}
                              <span style={{ fontSize: "0.75rem", fontWeight: 400, color: "var(--text-secondary)", background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "10px" }}>{sectionItems.length}</span>
                            </h3>
                            {section.type === "assessment" && (
                            <button
                              onClick={function() { fetchPublishedAssessments(); fetchSharedResources(); fetchTeacherTags(); }}
                              className="btn btn-secondary"
                              style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                              disabled={loadingPublished}
                            >
                              <Icon name={loadingPublished ? "Loader2" : "RefreshCw"} size={16} className={loadingPublished ? "spin" : ""} />
                              Refresh
                            </button>
                            )}
                          </div>

                          {loadingPublished ? (
                            <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                              <Icon name="Loader2" size={32} className="spin" />
                              <p style={{ marginTop: "10px" }}>Loading...</p>
                            </div>
                          ) : sectionItems.length === 0 ? (
                            <div style={{ textAlign: "center", padding: "30px", color: "var(--text-secondary)" }}>
                              <Icon name="FileQuestion" size={36} style={{ opacity: 0.5, marginBottom: "10px" }} />
                              <p style={{ fontSize: "0.9rem" }}>{section.emptyText}</p>
                              <p style={{ fontSize: "0.8rem", marginTop: "5px", opacity: 0.7 }}>{section.emptyHint}</p>
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              {sectionItems.map((assessment) => (
                                <div
                                  key={assessment.join_code}
                                  style={{
                                    padding: "15px",
                                    background: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "rgba(139, 92, 246, 0.2)"
                                      : "rgba(255,255,255,0.03)",
                                    borderRadius: "10px",
                                    border: selectedAssessmentResults?.joinCode === assessment.join_code
                                      ? "1px solid var(--accent-primary)"
                                      : "1px solid rgba(255,255,255,0.1)",
                                    cursor: "pointer",
                                    transition: "all 0.2s",
                                  }}
                                  onClick={() => fetchAssessmentResults(assessment.join_code)}
                                >
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontWeight: 600, marginBottom: "5px" }}>{assessment.title}</div>
                                      <div style={{ display: "flex", alignItems: "center", gap: "15px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Hash" size={14} />
                                          {assessment.join_code}
                                        </span>
                                        <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                          <Icon name="Users" size={14} />
                                          {assessment.submission_count || 0} submissions
                                        </span>
                                        {assessment.period && (
                                          <span style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                            <Icon name="Clock" size={14} />
                                            {assessment.period}
                                          </span>
                                        )}
                                      </div>
                                      {assessment.is_makeup && (
                                        <span
                                          style={{
                                            marginTop: "8px",
                                            padding: "3px 8px",
                                            background: "rgba(245, 158, 11, 0.2)",
                                            color: "#f59e0b",
                                            borderRadius: "4px",
                                            fontSize: "0.75rem",
                                            fontWeight: 600,
                                          }}
                                        >
                                          Makeup Exam
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                      <span
                                        style={{
                                          padding: "4px 10px",
                                          borderRadius: "12px",
                                          fontSize: "0.75rem",
                                          fontWeight: 600,
                                          background: assessment.is_active ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)",
                                          color: assessment.is_active ? "#22c55e" : "#ef4444",
                                        }}
                                      >
                                        {assessment.is_active ? "Active" : "Closed"}
                                      </span>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); toggleAssessmentStatus(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                                        title={assessment.is_active ? "Deactivate" : "Activate"}
                                      >
                                        <Icon name={assessment.is_active ? "Pause" : "Play"} size={16} />
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); deletePublishedAssessment(assessment.join_code); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", padding: "5px", color: "#ef4444" }}
                                        title="Delete"
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                  <div style={{ marginTop: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                    Created: {new Date(assessment.created_at).toLocaleDateString()}
                                  </div>
                                  {renderTagRow(assessment, function(updates) {
                                    setPublishedAssessments(function(prev) {
                                      return prev.map(function(a) {
                                        if (a.join_code === assessment.join_code || a.id === assessment.id) return Object.assign({}, a, updates);
                                        return a;
                                      });
                                    });
                                  })}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                          );
                        })}

                        {/* Shared Resources Section */}
                        <div className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="BookOpen" size={20} />
                            Shared Resources
                          </h3>
                          {loadingSharedResources ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Loading...</p>
                          ) : sharedResources.length === 0 ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                              No shared resources yet. Use "Share with Class" on flashcards, study guides, or slide decks to share them with students.
                            </p>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {sharedResources.filter(itemMatchesTagFilter).map(function(res) {
                                var typeIcon = res.content_type === 'flashcards' ? 'Layers'
                                  : res.content_type === 'study_guide' ? 'FileText'
                                  : res.content_type === 'slide_deck' ? 'Monitor'
                                  : 'File';
                                var typeLabel = res.content_type === 'flashcards' ? 'Flashcards'
                                  : res.content_type === 'study_guide' ? 'Study Guide'
                                  : res.content_type === 'slide_deck' ? 'Slide Deck'
                                  : res.content_type;
                                var sameTitle = sharedResources.filter(function(r) { return r.title === res.title; });
                                var isFirst = sameTitle[0] && sameTitle[0].id === res.id;
                                return (
                                  <div key={res.id} style={{
                                    display: "flex", alignItems: "center", gap: "12px",
                                    padding: "10px 14px", borderRadius: "10px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                  }}>
                                    <Icon name={typeIcon} size={18} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {res.title}
                                      </div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                      </div>
                                      {renderTagRow(res, function(updates) {
                                        setSharedResources(function(prev) {
                                          return prev.map(function(r) { return r.id === res.id ? Object.assign({}, r, updates) : r; });
                                        });
                                      })}
                                    </div>
                                    <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                                      {isFirst && sameTitle.length > 1 && (
                                        <button
                                          onClick={function() { if (confirm('Delete "' + res.title + '" from all ' + sameTitle.length + ' classes?')) handleDeleteAllSharedResources(res.title); }}
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                                          title="Delete from all classes"
                                        >
                                          Delete All ({sameTitle.length})
                                        </button>
                                      )}
                                      <button
                                        onClick={function() { handleDeleteSharedResource(res.id, res.title + ' (' + res.class_name + ')'); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)", padding: "4px" }}
                                        title={"Delete from " + res.class_name}
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Submissions Detail Panel */}
                        {selectedAssessmentResults && (
                          <div className="glass-card" style={{ padding: "20px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                <Icon name="BarChart3" size={20} />
                                {selectedAssessmentResults.title}
                              </h3>
                              <button
                                onClick={() => setSelectedAssessmentResults(null)}
                                style={{ background: "none", border: "none", cursor: "pointer", padding: "5px" }}
                              >
                                <Icon name="X" size={20} />
                              </button>
                            </div>

                            {/* Stats Summary */}
                            {selectedAssessmentResults.submissions.length > 0 && (
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "15px", marginBottom: "20px" }}>
                                <div style={{ padding: "15px", background: "rgba(34, 197, 94, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#22c55e" }}>
                                    {selectedAssessmentResults.submissions.length}
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Submissions</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(99, 102, 241, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#6366f1" }}>
                                    {Math.round(selectedAssessmentResults.submissions.reduce((sum, s) => sum + (s.percentage || 0), 0) / selectedAssessmentResults.submissions.length)}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Avg Score</div>
                                </div>
                                <div style={{ padding: "15px", background: "rgba(245, 158, 11, 0.1)", borderRadius: "10px", textAlign: "center" }}>
                                  <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f59e0b" }}>
                                    {Math.max(...selectedAssessmentResults.submissions.map(s => s.percentage || 0))}%
                                  </div>
                                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>High Score</div>
                                </div>
                              </div>
                            )}

                            {/* In Progress Drafts */}
                            {inProgressDrafts.length > 0 && (
                              <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                                <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                                  <Icon name="Clock" size={16} />
                                  In Progress ({inProgressDrafts.length})
                                </h4>
                                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                  {inProgressDrafts.map(function(d) {
                                    var elapsedMin = Math.floor((d.elapsed_seconds || 0) / 60);
                                    return (
                                      <div key={d.submission_id} style={{
                                        display: "flex", alignItems: "center", justifyContent: "space-between",
                                        padding: "10px 14px", borderRadius: "8px",
                                        background: "var(--warning-bg)", border: "1px solid var(--warning-border)",
                                      }}>
                                        <div>
                                          <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{d.student_name}</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                            {d.answered_count} questions answered {String.fromCharCode(8226)} {elapsedMin} min elapsed
                                          </div>
                                        </div>
                                        <button
                                          onClick={async function() {
                                            if (!confirm('End ' + d.student_name + "'s attempt? Their current answers will be submitted.")) return;
                                            try {
                                              var res = await api.endStudentAttempt(d.submission_id);
                                              if (res.success) {
                                                addToast('Ended attempt for ' + d.student_name, 'success');
                                                setInProgressDrafts(function(prev) { return prev.filter(function(x) { return x.submission_id !== d.submission_id; }); });
                                              } else {
                                                addToast(res.error || 'Failed to end attempt', 'error');
                                              }
                                            } catch (e) {
                                              addToast('Failed: ' + e.message, 'error');
                                            }
                                          }}
                                          className="btn btn-secondary"
                                          style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                                        >
                                          End attempt
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Standards Summary Card */}
                            {selectedAssessmentResults && selectedAssessmentResults.submissions && selectedAssessmentResults.submissions.length > 0 && (() => {
                              var byStandard = {};
                              selectedAssessmentResults.submissions.forEach(function(sub) {
                                var mastery = sub.results && sub.results.standards_mastery;
                                if (!mastery) return;
                                Object.keys(mastery).forEach(function(code) {
                                  var m = mastery[code];
                                  // Phase 4.3 Sprint 2 — backend may emit either old flat shape or
                                  // new {overall, by_dok} shape (only Student Report Card route emits
                                  // by_dok in its response; the rest preserve flat — but defend at
                                  // every read site).
                                  var ov = (m && m.overall) ? m.overall : (m || {});
                                  if (!byStandard[code]) byStandard[code] = { earned: 0, possible: 0, question_count: ov.question_count };
                                  byStandard[code].earned += ov.points_earned || 0;
                                  byStandard[code].possible += ov.points_possible || 0;
                                });
                              });
                              var codes = Object.keys(byStandard);
                              if (codes.length === 0) return null;
                              return (
                                <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                                    <Icon name="Target" size={16} />
                                    Standards in this Assessment ({codes.length})
                                  </h4>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    {codes.map(function(code) {
                                      var s = byStandard[code];
                                      var pct = s.possible > 0 ? Math.round((s.earned / s.possible) * 100) : 0;
                                      var barColor = pct >= 80 ? "var(--success)" : pct >= 60 ? "var(--warning)" : "var(--danger)";
                                      return (
                                        <div key={code} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 12px", borderRadius: "8px", background: "var(--glass-bg)" }}>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, fontFamily: "monospace", minWidth: "100px" }}>{code}</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", minWidth: "70px" }}>{s.question_count} Q{s.question_count === 1 ? '' : 's'}</div>
                                          <div style={{ flex: 1, height: "6px", background: "var(--glass-bg)", borderRadius: "3px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                                            <div style={{ width: pct + "%", height: "100%", background: barColor, transition: "width 0.3s" }} />
                                          </div>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: "50px", textAlign: "right" }}>{pct}%</div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })()}

                            {/* Student Submissions List */}
                            {loadingResults ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="Loader2" size={32} className="spin" />
                              </div>
                            ) : selectedAssessmentResults.submissions.length === 0 ? (
                              <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                                <Icon name="UserX" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                                <p>No submissions yet.</p>
                                <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>
                                  Share code <strong>{selectedAssessmentResults.joinCode}</strong> with students.
                                </p>
                              </div>
                            ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "400px", overflowY: "auto" }}>
                                {selectedAssessmentResults.submissions.map((submission, idx) => (
                                  <div
                                    key={idx}
                                    style={{
                                      padding: "12px 15px",
                                      background: "rgba(255,255,255,0.03)",
                                      borderRadius: "8px",
                                      border: "1px solid rgba(255,255,255,0.1)",
                                      display: "flex",
                                      justifyContent: "space-between",
                                      alignItems: "center",
                                    }}
                                  >
                                    <div>
                                      <div style={{ fontWeight: 600, display: "flex", alignItems: "center" }}>
                                        {submission.student_name}
                                        {(() => {
                                          var group = contentSubmissionsGroups.find(function(g) { return g.student_id === submission.student_id || g.student_name === submission.student_name; });
                                          if (!group || group.attempts.length <= 1) return null;
                                          var curAttempt = (submission.results && submission.results.attempt_number) || submission.attempt_number || 1;
                                          return (
                                            <button
                                              onClick={function(e) { e.stopPropagation(); setAttemptDrawerStudent(group); }}
                                              style={{ fontSize: "0.7rem", padding: "3px 8px", borderRadius: "10px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)", color: "var(--text-secondary)", cursor: "pointer", marginLeft: "8px" }}
                                              title="View all attempts"
                                            >
                                              Attempt {curAttempt} of {group.attempts.length}
                                            </button>
                                          );
                                        })()}
                                      </div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {new Date(submission.submitted_at).toLocaleString()}
                                        {submission.time_taken_seconds && (
                                          <span> · {Math.floor(submission.time_taken_seconds / 60)}m {submission.time_taken_seconds % 60}s</span>
                                        )}
                                      </div>
                                    </div>
                                    <div style={{ textAlign: "right" }}>
                                      <div style={{
                                        fontSize: "1.2rem",
                                        fontWeight: 700,
                                        color: submission.percentage >= 80 ? "#22c55e" : submission.percentage >= 60 ? "#f59e0b" : "#ef4444"
                                      }}>
                                        {submission.percentage?.toFixed(0) || 0}%
                                      </div>
                                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                        {submission.score}/{submission.total_points} pts
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Saved Assessments Section */}
                      <div className="glass-card" style={{ padding: "20px", marginTop: "25px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="Archive" size={20} />
                            Saved Assessments
                          </h3>
                          <button
                            onClick={fetchSavedAssessments}
                            className="btn btn-secondary"
                            style={{ padding: "8px 12px", fontSize: "0.85rem" }}
                            disabled={loadingSavedAssessments}
                          >
                            <Icon name={loadingSavedAssessments ? "Loader2" : "RefreshCw"} size={16} className={loadingSavedAssessments ? "spin" : ""} />
                            Refresh
                          </button>
                        </div>

                        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                          Load a saved assessment to view, modify, or publish it for makeup exams.
                        </p>

                        {loadingSavedAssessments ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="Loader2" size={32} className="spin" />
                            <p style={{ marginTop: "10px" }}>Loading saved assessments...</p>
                          </div>
                        ) : savedAssessments.length === 0 ? (
                          <div style={{ textAlign: "center", padding: "40px", color: "var(--text-secondary)" }}>
                            <Icon name="FolderOpen" size={48} style={{ opacity: 0.5, marginBottom: "15px" }} />
                            <p>No saved assessments.</p>
                            <p style={{ fontSize: "0.9rem", marginTop: "5px" }}>Generate an assessment and use "Save for Later" to save it.</p>
                          </div>
                        ) : (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
                            {savedAssessments.map((assessment) => (
                              <div
                                key={assessment.filename}
                                style={{
                                  padding: "15px",
                                  background: "rgba(255,255,255,0.03)",
                                  borderRadius: "10px",
                                  border: "1px solid rgba(255,255,255,0.1)",
                                }}
                              >
                                <div style={{ fontWeight: 600, marginBottom: "8px" }}>{assessment.name}</div>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                                  <Icon name="FileText" size={14} />
                                  {assessment.question_count || '?'} questions
                                  <span>·</span>
                                  <Icon name="Target" size={14} />
                                  {assessment.total_points || '?'} pts
                                </div>
                                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                                  Saved: {new Date(assessment.saved_at).toLocaleDateString()}
                                </div>
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <button
                                    onClick={() => loadSavedAssessment(assessment.filename)}
                                    className="btn btn-primary"
                                    style={{ padding: "6px 12px", fontSize: "0.85rem", flex: 1 }}
                                  >
                                    <Icon name="Download" size={14} />
                                    Load
                                  </button>
                                  <button
                                    onClick={() => deleteSavedAssessment(assessment.filename)}
                                    className="btn"
                                    style={{ padding: "6px 10px", fontSize: "0.85rem", background: "rgba(239, 68, 68, 0.2)", color: "#ef4444" }}
                                    title="Delete"
                                  >
                                    <Icon name="Trash2" size={14} />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
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
