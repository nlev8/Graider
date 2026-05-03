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

        {/* Assessment Category Toggle — assessments only */}
        {isAssessment && (
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          <button
            onClick={() => setSettings({...settings, assessmentCategory: 'formative'})}
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              border: settings.assessmentCategory === 'formative' ? "2px solid #22c55e" : "1px solid rgba(255,255,255,0.15)",
              background: settings.assessmentCategory === 'formative' ? "rgba(34, 197, 94, 0.15)" : "rgba(255,255,255,0.05)",
              color: settings.assessmentCategory === 'formative' ? "#86efac" : "#94a3b8",
              cursor: "pointer",
              textAlign: "left",
              transition: "all 0.2s",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Formative</div>
            <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>Quizzes, checks for understanding</div>
          </button>
          <button
            onClick={() => setSettings({...settings, assessmentCategory: 'summative'})}
            style={{
              flex: 1,
              padding: "10px 14px",
              borderRadius: "8px",
              border: settings.assessmentCategory === 'summative' ? "2px solid #ef4444" : "1px solid rgba(255,255,255,0.15)",
              background: settings.assessmentCategory === 'summative' ? "rgba(239, 68, 68, 0.15)" : "rgba(255,255,255,0.05)",
              color: settings.assessmentCategory === 'summative' ? "#fca5a5" : "#94a3b8",
              cursor: "pointer",
              textAlign: "left",
              transition: "all 0.2s",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Summative</div>
            <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>Unit tests, midterms, finals</div>
          </button>
        </div>
        )}

        {/* Class Selection */}
        <div style={{ marginBottom: "15px" }}>
          <label className="label" style={{ marginBottom: "6px" }}>Publish to Class (optional)</label>
          <select className="input" value={classId} onChange={(e) => setClassId(e.target.value)} style={{ width: "100%", background: "rgba(255,255,255,0.08)", color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.2)", borderRadius: "8px" }}>
            <option value="">Join Code Only (no class)</option>
            {teacherClasses.map((cls) => (
              <option key={cls.id} value={cls.id}>{cls.name} ({cls.join_code})</option>
            ))}
          </select>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
            {classId ? "Students log in with email + class code to access this." : "Anyone with the join code can access this (anonymous)."}
          </p>
        </div>

        {/* Period Selection — only show when NOT publishing to a class */}
        {!classId && (<div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
            Period (Optional)
          </label>
          <select
            value={settings.periodFilename}
            onChange={(e) => {
              const filename = e.target.value;
              const selectedPeriod = periods.find(p => p.filename === filename);
              setSettings({
                ...settings,
                periodFilename: filename,
                period: selectedPeriod ? selectedPeriod.period_name : '',
                selectedStudents: [],
              });
              onPeriodChange(filename);
            }}
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(255,255,255,0.08)",
              color: "#e2e8f0",
              fontSize: "0.95rem",
            }}
          >
            <option value="">-- No Period (Open to All) --</option>
            {periods.map((p) => (
              <option key={p.filename} value={p.filename}>{p.name}</option>
            ))}
          </select>
        </div>)}

        {/* Makeup Exam Toggle — assessments only */}
        {isAssessment && (
        <div style={{ marginBottom: "20px" }}>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
              padding: "12px 15px",
              background: settings.isMakeup ? "rgba(139, 92, 246, 0.1)" : "rgba(255,255,255,0.05)",
              border: settings.isMakeup ? "1px solid #8b5cf6" : "1px solid rgba(255,255,255,0.15)",
              borderRadius: "8px",
            }}
          >
            <input
              type="checkbox"
              checked={settings.isMakeup}
              onChange={(e) => setSettings({ ...settings, isMakeup: e.target.checked, selectedStudents: [] })}
              style={{ width: "18px", height: "18px", accentColor: "var(--accent-primary)" }}
            />
            <div>
              <div style={{ fontWeight: 600 }}>Makeup Exam</div>
              <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
                Restrict to selected students only
              </div>
            </div>
          </label>
        </div>
        )}

        {/* Student Selection (only shown for makeup exams with a period selected) */}
        {settings.isMakeup && settings.periodFilename && (
          <div style={{ marginBottom: "20px" }}>
            <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
              Select Students ({settings.selectedStudents.length} selected)
            </label>
            {loadingStudents ? (
              <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8" }}>
                <Icon name="Loader" size={24} className="spin" />
                <div style={{ marginTop: "10px" }}>Loading students...</div>
              </div>
            ) : modalStudents.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "#94a3b8" }}>
                No students in this period
              </div>
            ) : (
              <div
                style={{
                  maxHeight: "200px",
                  overflowY: "auto",
                  border: "1px solid rgba(255,255,255,0.15)",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.05)",
                }}
              >
                {modalStudents.map((student, idx) => {
                  const studentName = student.first + ' ' + student.last;
                  const isSelected = settings.selectedStudents.includes(studentName);
                  const studentId = student.id || student.email || studentName;
                  const hasAccommodation = studentAccommodations[studentId];
                  return (
                    <label
                      key={idx}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "10px 12px",
                        borderBottom: idx < modalStudents.length - 1 ? "1px solid rgba(255,255,255,0.15)" : "none",
                        cursor: "pointer",
                        background: isSelected ? "rgba(139, 92, 246, 0.1)" : "transparent",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSettings({ ...settings, selectedStudents: [...settings.selectedStudents, studentName] });
                          } else {
                            setSettings({ ...settings, selectedStudents: settings.selectedStudents.filter(s => s !== studentName) });
                          }
                        }}
                        style={{ width: "16px", height: "16px", accentColor: "var(--accent-primary)" }}
                      />
                      <span style={{ flex: 1 }}>{studentName}</span>
                      {hasAccommodation && (
                        <span
                          style={{
                            padding: "2px 8px",
                            background: "rgba(59, 130, 246, 0.2)",
                            color: "#3b82f6",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                          }}
                        >
                          IEP/504
                        </span>
                      )}
                    </label>
                  );
                })}
              </div>
            )}
            {settings.isMakeup && modalStudents.length > 0 && (
              <div style={{ marginTop: "8px", display: "flex", gap: "10px" }}>
                <button
                  onClick={() => setSettings({ ...settings, selectedStudents: modalStudents.map(s => s.first + ' ' + s.last) })}
                  className="btn btn-secondary"
                  style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                >
                  Select All
                </button>
                <button
                  onClick={() => setSettings({ ...settings, selectedStudents: [] })}
                  className="btn btn-secondary"
                  style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                >
                  Clear
                </button>
              </div>
            )}
          </div>
        )}

        {/* Apply Accommodations Toggle */}
        {settings.periodFilename && Object.keys(studentAccommodations).length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                cursor: "pointer",
                padding: "12px 15px",
                background: settings.applyAccommodations ? "rgba(59, 130, 246, 0.1)" : "rgba(255,255,255,0.05)",
                border: settings.applyAccommodations ? "1px solid #3b82f6" : "1px solid rgba(255,255,255,0.15)",
                borderRadius: "8px",
              }}
            >
              <input
                type="checkbox"
                checked={settings.applyAccommodations}
                onChange={(e) => setSettings({ ...settings, applyAccommodations: e.target.checked })}
                style={{ width: "18px", height: "18px", accentColor: "#3b82f6" }}
              />
              <div>
                <div style={{ fontWeight: 600 }}>Apply IEP/504 Accommodations</div>
                <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
                  Students with accommodations will see modified instructions
                </div>
              </div>
            </label>
          </div>
        )}

        {/* Timing — content-type aware */}
        <div style={{ marginBottom: "25px" }}>
          <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
            {'Time Limit' + (isAssessment ? ' *' : ' (Optional)')}
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <input
              type="number"
              min="0"
              value={settings.timeLimit || ''}
              onChange={(e) => setSettings({ ...settings, timeLimit: e.target.value ? parseInt(e.target.value) : null })}
              placeholder={isAssessment ? "Required" : "No limit"}
              style={{
                width: "120px",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "1px solid rgba(255,255,255,0.2)",
                background: "rgba(255,255,255,0.08)",
                color: "#e2e8f0",
                fontSize: "0.95rem",
              }}
            />
            <span style={{ color: "#94a3b8" }}>minutes</span>
          </div>
          {isAssessment ? (
            <div style={{ marginTop: "12px", display: "flex", gap: "10px" }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Available From</label>
                <input
                  type="datetime-local"
                  value={settings.availableFrom}
                  onChange={(e) => setSettings({ ...settings, availableFrom: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: "8px",
                    border: "1px solid rgba(255,255,255,0.2)",
                    background: "rgba(255,255,255,0.08)",
                    color: "#e2e8f0",
                    fontSize: "0.85rem",
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Available Until</label>
                <input
                  type="datetime-local"
                  value={settings.availableUntil}
                  onChange={(e) => setSettings({ ...settings, availableUntil: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "8px 10px",
                    borderRadius: "8px",
                    border: "1px solid rgba(255,255,255,0.2)",
                    background: "rgba(255,255,255,0.08)",
                    color: "#e2e8f0",
                    fontSize: "0.85rem",
                  }}
                />
              </div>
            </div>
          ) : (
            <div style={{ marginTop: "12px" }}>
              <label style={{ display: "block", marginBottom: "4px", fontSize: "0.85rem", color: "#94a3b8" }}>Due Date</label>
              <input
                type="datetime-local"
                value={settings.dueDate}
                onChange={(e) => setSettings({ ...settings, dueDate: e.target.value })}
                style={{
                  width: "100%",
                  maxWidth: "250px",
                  padding: "8px 10px",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,255,255,0.2)",
                  background: "rgba(255,255,255,0.08)",
                  color: "#e2e8f0",
                  fontSize: "0.85rem",
                }}
              />
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            onClick={() => onClose()}
            className="btn btn-secondary"
            style={{ padding: "10px 20px" }}
          >
            Cancel
          </button>
          <button
            onClick={onPublish}
            disabled={publishDisabled}
            className="btn btn-primary"
            style={{
              padding: "10px 24px",
              background: settings.contentType === 'assignment' ? "linear-gradient(135deg, #22c55e, #16a34a)" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
            }}
          >
            <Icon name={publishing ? "Loader" : "Share2"} size={16} />
            {publishing ? "Publishing..." : 'Publish ' + (isAssessment ? 'Assessment' : 'Assignment')}
          </button>
        </div>
      </div>
    </div>
  );
}
