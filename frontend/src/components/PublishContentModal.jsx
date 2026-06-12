/**
 * PublishContentModal — modal for publishing the currently-active piece
 * of generated content (assessment or assignment) either via a join code
 * or to a class. Settings include:
 *
 *   - assessment / assignment content type (auto-detected, header label
 *     branches on it)
 *   - assessment category (formative / summative, assessments only)
 *   - target class (or "Join Code Only" for anonymous publishing)
 *   - period scope (only when not class-published)
 *   - makeup-exam mode with per-student selection (assessments only)
 *   - apply IEP/504 accommodations toggle
 *   - timing — content-type aware: time limit + availability window for
 *     assessments, due date for assignments
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showPublishModal`. Lifted as a presentational component; App.jsx
 * still owns all the related state and the final
 * `confirmPublishAssessment` action.
 *
 * Split into publish-content-modal/* sections (CQ wave-7, 2026-06-11):
 * this shell keeps the open guard, the derived isAssessment /
 * publishDisabled values, and the overlay + card chrome; each section's
 * JSX moved verbatim, with the shell's conditional gates becoming
 * early-return-null guards inside the conditional sections.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   settings: publishSettings object
 *   setSettings: (next) => void  (passed plain `setPublishSettings`)
 *   classId: string  (publishClassId)
 *   setClassId: (id) => void  (setPublishClassId)
 *   teacherClasses: Array<{ id, name, join_code }>
 *   periods: Array<{ filename, name }>
 *   onPeriodChange: (filename) => void  (calls loadPublishModalStudents)
 *   modalStudents: Array<{ first, last, id?, email? }>  (publishModalStudents)
 *   loadingStudents: bool  (loadingPublishStudents)
 *   studentAccommodations: Record<id, accommodation>
 *   publishing: bool  (publishingAssessment)
 *   onPublish: () => void  (confirmPublishAssessment)
 */
import React from "react";
import Icon from "./Icon";
import AssessmentCategoryToggle from "./publish-content-modal/AssessmentCategoryToggle";
import ClassPeriodSection from "./publish-content-modal/ClassPeriodSection";
import MakeupToggle from "./publish-content-modal/MakeupToggle";
import StudentSelection from "./publish-content-modal/StudentSelection";
import AccommodationsToggle from "./publish-content-modal/AccommodationsToggle";
import TimingSection from "./publish-content-modal/TimingSection";
import ModalActions from "./publish-content-modal/ModalActions";

export default function PublishContentModal({
  open,
  onClose,
  settings,
  setSettings,
  classId,
  setClassId,
  teacherClasses,
  periods,
  onPeriodChange,
  modalStudents,
  loadingStudents,
  studentAccommodations,
  publishing,
  onPublish,
}) {
  if (!open) return null;

  const isAssessment = settings.contentType === 'assessment';
  const publishDisabled = publishing
    || (settings.isMakeup && settings.selectedStudents.length === 0)
    || (isAssessment && !settings.timeLimit);

  return (
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
      onClick={() => onClose()}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#1e293b",
          color: "#e2e8f0",
          borderRadius: "16px",
          padding: "30px",
          maxWidth: "600px",
          width: "100%",
          maxHeight: "80vh",
          overflowY: "auto",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="Share2" size={24} style={{ color: "var(--accent-primary)" }} />
          {'Publish ' + (isAssessment ? 'Assessment' : 'Assignment')}
        </h2>

        {/* Content type is auto-detected from the generated content — no toggle needed */}

        <AssessmentCategoryToggle
          isAssessment={isAssessment}
          settings={settings}
          setSettings={setSettings}
        />

        <ClassPeriodSection
          classId={classId}
          setClassId={setClassId}
          teacherClasses={teacherClasses}
          settings={settings}
          setSettings={setSettings}
          periods={periods}
          onPeriodChange={onPeriodChange}
        />

        <MakeupToggle
          isAssessment={isAssessment}
          settings={settings}
          setSettings={setSettings}
        />

        <StudentSelection
          settings={settings}
          setSettings={setSettings}
          modalStudents={modalStudents}
          loadingStudents={loadingStudents}
          studentAccommodations={studentAccommodations}
        />

        <AccommodationsToggle
          settings={settings}
          setSettings={setSettings}
          studentAccommodations={studentAccommodations}
        />

        <TimingSection
          isAssessment={isAssessment}
          settings={settings}
          setSettings={setSettings}
        />

        <ModalActions
          isAssessment={isAssessment}
          settings={settings}
          publishing={publishing}
          publishDisabled={publishDisabled}
          onClose={onClose}
          onPublish={onPublish}
        />
      </div>
    </div>
  );
}
