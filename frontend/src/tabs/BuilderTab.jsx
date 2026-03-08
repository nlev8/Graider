import React from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";

/**
 * BuilderTab - Extracted from App.jsx
 *
 * Props needed:
 *
 * State variables:
 *   - assignment, setAssignment
 *   - savedAssignments, setSavedAssignments (setSavedAssignments not directly used but kept for consistency)
 *   - savedAssignmentData, setSavedAssignmentData
 *   - savedAssignmentsExpanded, setSavedAssignmentsExpanded
 *   - loadedAssignmentName, setLoadedAssignmentName
 *   - isLoadingAssignment, setIsLoadingAssignment
 *   - importedDoc, setImportedDoc
 *   - docEditorModal, setDocEditorModal
 *   - modelAnswersLoading
 *   - config (global settings object, needs config.subject)
 *
 * Refs:
 *   - fileInputRef
 *   - skipAutoSaveRef
 *
 * Callbacks:
 *   - loadAssignment(name)
 *   - deleteAssignment(name)
 *   - saveAssignmentConfig()
 *   - exportAssignment(format)
 *   - handleDocImport(e)
 *   - openDocEditor()
 *   - handleGenerateModelAnswers()
 *   - removeMarker(marker, index)
 *   - addQuestion()
 *   - updateQuestion(index, field, value)
 *   - removeQuestion(index)
 *   - addToast(message, type)
 *
 * Utility functions:
 *   - getMarkerText(marker)
 *   - getMarkerPoints(marker)
 *   - getMarkerType(marker)
 *   - calculateTotalPoints(markers, effortPoints)
 *   - removeAllHighlightsFromHtml(html)
 *   - applyAllHighlights(html, markers, excludeMarkers)
 *
 * Constants:
 *   - markerLibrary
 */

export default React.memo(function BuilderTab({
  assignment,
  setAssignment,
  savedAssignments,
  savedAssignmentData,
  setSavedAssignmentData,
  savedAssignmentsExpanded,
  setSavedAssignmentsExpanded,
  loadedAssignmentName,
  setLoadedAssignmentName,
  isLoadingAssignment,
  setIsLoadingAssignment,
  importedDoc,
  setImportedDoc,
  docEditorModal,
  setDocEditorModal,
  modelAnswersLoading,
  standardsAlignment,
  alignmentLoading,
  rewriteLoading,
  handleAlignToStandards,
  handleRewriteForAlignment,
  config,
  fileInputRef,
  skipAutoSaveRef,
  loadAssignment,
  deleteAssignment,
  saveAssignmentConfig,
  exportAssignment,
  handleDocImport,
  openDocEditor,
  handleGenerateModelAnswers,
  removeMarker,
  addQuestion,
  updateQuestion,
  removeQuestion,
  addToast,
  getMarkerText,
  getMarkerPoints,
  getMarkerType,
  calculateTotalPoints,
  removeAllHighlightsFromHtml,
  applyAllHighlights,
  textToRichHtml,
  markerLibrary,
}) {
  return (
                <div data-tutorial="builder-card" className="fade-in">
                  {/* Saved Assignments - Collapsible */}
                  <div
                    data-tutorial="builder-saved"
                    className="glass-card"
                    style={{ padding: "15px 20px", marginBottom: "20px" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        cursor: "pointer",
                      }}
                      onClick={() =>
                        setSavedAssignmentsExpanded(!savedAssignmentsExpanded)
                      }
                    >
                      <h3
                        style={{
                          fontSize: "1rem",
                          fontWeight: 600,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          margin: 0,
                        }}
                      >
                        <Icon
                          name={
                            savedAssignmentsExpanded
                              ? "ChevronDown"
                              : "ChevronRight"
                          }
                          size={18}
                          style={{ color: "var(--text-secondary)" }}
                        />
                        <Icon
                          name="FolderOpen"
                          size={18}
                          style={{ color: "#10b981" }}
                        />
                        Saved Assignments ({savedAssignments.length})
                      </h3>
                    </div>

                    {savedAssignmentsExpanded && (
                      <>
                        {savedAssignments.length === 0 ? (
                          <p
                            style={{
                              textAlign: "center",
                              padding: "20px",
                              color: "var(--text-muted)",
                              margin: 0,
                            }}
                          >
                            No saved assignments yet. Create one below!
                          </p>
                        ) : (
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns:
                                "repeat(auto-fill, minmax(250px, 1fr))",
                              gap: "10px",
                              marginTop: "15px",
                            }}
                          >
                            {savedAssignments.map((name) => {
                              const countsTowardsGrade = savedAssignmentData[name]?.countsTowardsGrade ?? true;
                              return (
                              <div
                                key={name}
                                style={{
                                  padding: "12px 15px",
                                  background:
                                    loadedAssignmentName === name
                                      ? "rgba(99,102,241,0.2)"
                                      : !countsTowardsGrade
                                        ? "rgba(100,100,100,0.1)"
                                        : "var(--input-bg)",
                                  borderRadius: "10px",
                                  border: !countsTowardsGrade
                                    ? "1px dashed rgba(100,100,100,0.4)"
                                    : "1px solid var(--glass-border)",
                                  outline: loadedAssignmentName === name
                                    ? "2px solid rgba(99,102,241,0.5)"
                                    : "none",
                                  outlineOffset: "-1px",
                                  cursor: "pointer",
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  opacity: countsTowardsGrade ? 1 : 0.6,
                                }}
                                onClick={() => loadAssignment(name)}
                                onDoubleClick={async () => {
                                  setIsLoadingAssignment(true); // Prevent auto-save during load
                                  skipAutoSaveRef.current = true; // Don't auto-save data we just loaded
                                  const data = await api.loadAssignment(name);
                                  if (data.assignment) {
                                    // Set importedDoc FIRST to prevent race condition
                                    if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
                                      setImportedDoc(data.assignment.importedDoc);
                                    } else {
                                      setImportedDoc({ text: "", html: "", filename: "", loading: false });
                                    }

                                    // Load the assignment
                                    setAssignment({
                                      title: data.assignment.title || "",
                                      subject: data.assignment.subject || "Social Studies",
                                      totalPoints: data.assignment.totalPoints || 100,
                                      instructions: data.assignment.instructions || "",
                                      questions: data.assignment.questions || [],
                                      customMarkers: data.assignment.customMarkers || [],
                                      gradingNotes: data.assignment.gradingNotes || "",
                                      responseSections: data.assignment.responseSections || [],
                                      aliases: data.assignment.aliases || [],
                                    });
                                    setLoadedAssignmentName(name);
                                    setTimeout(() => setIsLoadingAssignment(false), 500);

                                    // If there's an imported doc, open the editor modal
                                    if (data.assignment.importedDoc?.html || data.assignment.importedDoc?.text) {
                                      // Use HTML if available, otherwise convert plain text to simple HTML
                                      let docHtml = data.assignment.importedDoc.html || '';
                                      const hasFormatting = /<(h[1-6]|strong|em|b |table|th|td|div class|style)/.test(docHtml);
                                      if (!hasFormatting && data.assignment.importedDoc.text) {
                                        docHtml = textToRichHtml(data.assignment.importedDoc.text);
                                      }
                                      // Re-apply highlights from loaded markers onto the HTML
                                      const loadedMarkers = data.assignment.customMarkers || [];
                                      const loadedExcludes = data.assignment.excludeMarkers || [];
                                      if (loadedMarkers.length > 0 || loadedExcludes.length > 0) {
                                        let cleanHtml = removeAllHighlightsFromHtml(docHtml);
                                        docHtml = applyAllHighlights(cleanHtml, loadedMarkers, loadedExcludes);
                                      }
                                      setDocEditorModal({
                                        show: true,
                                        editedHtml: docHtml,
                                        viewMode: 'formatted'
                                      });
                                      const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
                                      addToast(
                                        `Loaded "${name}" with ${markerCount} marker${markerCount !== 1 ? 's' : ''}`,
                                        'success'
                                      );
                                    } else {
                                      // No document - check if it has markers
                                      const markerCount = (data.assignment.questions?.length || 0) + (data.assignment.customMarkers?.length || 0);
                                      if (markerCount > 0) {
                                        addToast(`"${name}" has ${markerCount} marker${markerCount !== 1 ? 's' : ''} but no document. Re-import the document to view.`, 'warning');
                                      } else {
                                        addToast(`"${name}" has no document or markers. Import a document to get started.`, 'info');
                                      }
                                    }
                                  } else {
                                    setIsLoadingAssignment(false);
                                  }
                                }}
                                title="Double-click to open document with markers"
                              >
                                <div
                                  style={{
                                    fontWeight: 500,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    fontSize: "0.9rem",
                                    flex: 1,
                                  }}
                                >
                                  <Icon
                                    name={
                                      savedAssignmentData[name]?.completionOnly
                                        ? "CheckCircle"
                                        : "FileText"
                                    }
                                    size={14}
                                    style={{
                                      color: savedAssignmentData[name]
                                        ?.completionOnly
                                        ? "#22c55e"
                                        : "#a5b4fc",
                                    }}
                                  />
                                  {name}
                                  {savedAssignmentData[name]?.completionOnly && (
                                    <span
                                      style={{
                                        fontSize: "0.7rem",
                                        background: "rgba(34, 197, 94, 0.2)",
                                        color: "#22c55e",
                                        padding: "2px 6px",
                                        borderRadius: "4px",
                                        marginLeft: "4px",
                                      }}
                                    >
                                      Completion
                                    </span>
                                  )}
                                  {savedAssignmentData[name]?.rubricType && savedAssignmentData[name]?.rubricType !== 'standard' && !savedAssignmentData[name]?.completionOnly && (
                                    <span
                                      style={{
                                        fontSize: "0.65rem",
                                        background: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "rgba(251, 191, 36, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'essay' ? "rgba(99, 102, 241, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "rgba(34, 211, 238, 0.2)" :
                                                   savedAssignmentData[name]?.rubricType === 'custom' ? "rgba(139, 92, 246, 0.2)" : "rgba(100,100,100,0.2)",
                                        color: savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? "#fbbf24" :
                                               savedAssignmentData[name]?.rubricType === 'essay' ? "#818cf8" :
                                               savedAssignmentData[name]?.rubricType === 'cornell-notes' ? "#22d3ee" :
                                               savedAssignmentData[name]?.rubricType === 'custom' ? "#a78bfa" : "#888",
                                        padding: "2px 6px",
                                        borderRadius: "4px",
                                        marginLeft: "4px",
                                        textTransform: "uppercase",
                                        fontWeight: 600,
                                      }}
                                    >
                                      {savedAssignmentData[name]?.rubricType === 'fill-in-blank' ? 'Fill-in' :
                                       savedAssignmentData[name]?.rubricType === 'cornell-notes' ? 'Cornell' :
                                       savedAssignmentData[name]?.rubricType}
                                    </span>
                                  )}
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                  {/* Download button for generated worksheets */}
                                  {savedAssignmentData[name]?.worksheetDownloadUrl && (
                                    <a
                                      href={savedAssignmentData[name].worksheetDownloadUrl}
                                      download
                                      onClick={(e) => e.stopPropagation()}
                                      style={{
                                        padding: "4px",
                                        background: "none",
                                        border: "none",
                                        color: "#6366f1",
                                        cursor: "pointer",
                                        display: "flex",
                                        alignItems: "center",
                                      }}
                                      title="Download worksheet (.docx)"
                                    >
                                      <Icon name="Download" size={14} />
                                    </a>
                                  )}
                                  {/* Star toggle for "counts towards grade" */}
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      const currentValue = savedAssignmentData[name]?.countsTowardsGrade ?? true;
                                      const newValue = !currentValue;
                                      setSavedAssignmentData(prev => ({
                                        ...prev,
                                        [name]: { ...prev[name], countsTowardsGrade: newValue },
                                      }));
                                      try {
                                        const fullData = await api.loadAssignment(name);
                                        if (fullData.assignment) {
                                          await api.saveAssignmentConfig({
                                            ...fullData.assignment,
                                            countsTowardsGrade: newValue,
                                          });
                                        }
                                        addToast(
                                          newValue
                                            ? `"${name}" will count towards grade`
                                            : `"${name}" excluded from grade calculation`,
                                          "success"
                                        );
                                      } catch (err) {
                                        console.error("Error saving:", err);
                                      }
                                    }}
                                    style={{
                                      padding: "4px",
                                      background: "none",
                                      border: "none",
                                      cursor: "pointer",
                                      color: (savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "#fbbf24" : "var(--text-muted)",
                                    }}
                                    title={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Counts towards grade (click to exclude)" : "Excluded from grade (click to include)"}
                                  >
                                    <Icon name={(savedAssignmentData[name]?.countsTowardsGrade ?? true) ? "Star" : "StarOff"} size={14} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      deleteAssignment(name);
                                    }}
                                    style={{
                                      padding: "4px",
                                      background: "none",
                                      border: "none",
                                      color: "var(--text-muted)",
                                      cursor: "pointer",
                                    }}
                                  >
                                    <Icon name="Trash2" size={14} />
                                  </button>
                                </div>
                              </div>
                            );
                            })}
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Assignment Editor */}
                  <div className="glass-card" style={{ padding: "30px" }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "25px",
                      }}
                    >
                      <h2
                        style={{
                          fontSize: "1.3rem",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <Icon name="FileEdit" size={24} />
                        {assignment.title
                          ? `Editing: ${assignment.title}`
                          : "New Assignment"}
                      </h2>
                      {assignment.title && (
                        <span
                          style={{
                            fontSize: "0.85rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {(assignment.customMarkers || []).length} markers
                        </span>
                      )}
                    </div>

                    {/* Assignment Details */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "2fr 1fr 1fr",
                        gap: "15px",
                        marginBottom: "25px",
                      }}
                    >
                      <div>
                        <label className="label">Assignment Title</label>
                        <input
                          type="text"
                          className="input"
                          value={assignment.title}
                          onChange={(e) =>
                            setAssignment({
                              ...assignment,
                              title: e.target.value,
                            })
                          }
                          placeholder="e.g., Louisiana Purchase Quiz"
                        />
                      </div>
                      <div style={{ gridColumn: "1 / -1" }}>
                        <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          Aliases (Alternative Names)
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                            - helps match student files with different naming
                          </span>
                        </label>
                        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
                          {(assignment.aliases || []).map((alias, i) => (
                            <span
                              key={i}
                              style={{
                                padding: "4px 10px",
                                background: "rgba(139, 92, 246, 0.2)",
                                border: "1px solid rgba(139, 92, 246, 0.4)",
                                borderRadius: "6px",
                                fontSize: "0.85rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                              }}
                            >
                              {alias}
                              <button
                                onClick={() => setAssignment({
                                  ...assignment,
                                  aliases: assignment.aliases.filter((_, idx) => idx !== i)
                                })}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  padding: "0",
                                  fontSize: "1rem",
                                  lineHeight: 1,
                                }}
                                title="Remove alias"
                              >
                                ×
                              </button>
                            </span>
                          ))}
                        </div>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <input
                            type="text"
                            className="input"
                            placeholder="Add alias (e.g., Chapter 10 Section 2)"
                            style={{ flex: 1 }}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && e.target.value.trim()) {
                                e.preventDefault();
                                const newAlias = e.target.value.trim();
                                if (!assignment.aliases?.includes(newAlias)) {
                                  setAssignment({
                                    ...assignment,
                                    aliases: [...(assignment.aliases || []), newAlias]
                                  });
                                }
                                e.target.value = "";
                              }
                            }}
                          />
                          <button
                            className="btn btn-secondary"
                            style={{ padding: "8px 16px" }}
                            onClick={(e) => {
                              const input = e.target.previousSibling;
                              if (input.value.trim()) {
                                const newAlias = input.value.trim();
                                if (!assignment.aliases?.includes(newAlias)) {
                                  setAssignment({
                                    ...assignment,
                                    aliases: [...(assignment.aliases || []), newAlias]
                                  });
                                }
                                input.value = "";
                              }
                            }}
                          >
                            Add
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="label">Subject</label>
                        <input
                          type="text"
                          className="input"
                          value={config.subject || "Social Studies"}
                          disabled
                          style={{
                            background: "var(--glass-hover)",
                            color: "var(--text-secondary)",
                          }}
                          title="Subject is set in Settings tab"
                        />
                      </div>
                      <div>
                        <label className="label">Total Points</label>
                        <input
                          type="number"
                          className="input"
                          value={assignment.totalPoints}
                          onChange={(e) => {
                            const val = e.target.value;
                            setAssignment({
                              ...assignment,
                              totalPoints: val === '' ? '' : parseInt(val),
                            });
                          }}
                          onBlur={(e) => {
                            const val = parseInt(e.target.value) || 100;
                            setAssignment({
                              ...assignment,
                              totalPoints: val,
                            });
                          }}
                          disabled={assignment.completionOnly}
                          style={
                            assignment.completionOnly ? { opacity: 0.5 } : {}
                          }
                        />
                      </div>
                    </div>

                    {/* Due Date & Late Policy */}
                    <div style={{ marginBottom: "25px", padding: "20px", background: "var(--glass-bg)", borderRadius: "12px", border: "1px solid var(--glass-border)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                        <Icon name="Clock" size={20} style={{ color: "var(--accent-primary)" }} />
                        <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>Due Date & Late Policy</h3>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "end", marginBottom: "16px" }}>
                        <div>
                          <label className="label">Due Date</label>
                          <input
                            type="datetime-local"
                            className="input"
                            value={assignment.dueDate}
                            onChange={(e) => setAssignment({ ...assignment, dueDate: e.target.value })}
                          />
                        </div>
                        {assignment.dueDate && (
                          <button
                            className="btn btn-secondary"
                            onClick={() => setAssignment({ ...assignment, dueDate: "" })}
                            style={{ height: "42px" }}
                            title="Clear due date"
                          >
                            <Icon name="X" size={16} />
                          </button>
                        )}
                      </div>
                      {assignment.dueDate && (
                        <>
                          <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer", marginBottom: assignment.latePenalty.enabled ? "16px" : 0 }}>
                            <input
                              type="checkbox"
                              checked={assignment.latePenalty.enabled}
                              onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, enabled: e.target.checked } })}
                            />
                            <span style={{ fontSize: "0.9rem", fontWeight: 500 }}>Enable late penalty</span>
                          </label>
                          {assignment.latePenalty.enabled && (
                            <div style={{ padding: "16px", background: "rgba(245,158,11,0.08)", borderRadius: "10px", border: "1px solid rgba(245,158,11,0.2)" }}>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "12px" }}>
                                <div>
                                  <label className="label">Penalty Type</label>
                                  <select
                                    className="input"
                                    value={assignment.latePenalty.type}
                                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, type: e.target.value } })}
                                  >
                                    <option value="points_per_day">Points per day</option>
                                    <option value="percent_per_day">Percent per day</option>
                                    <option value="tiered">Tiered brackets</option>
                                  </select>
                                </div>
                                {assignment.latePenalty.type !== "tiered" && (
                                  <div>
                                    <label className="label">
                                      {assignment.latePenalty.type === "points_per_day" ? "Points / day" : "% / day"}
                                    </label>
                                    <input
                                      type="number"
                                      className="input"
                                      min="0"
                                      value={assignment.latePenalty.amount}
                                      onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, amount: parseInt(e.target.value) || 0 } })}
                                    />
                                  </div>
                                )}
                              </div>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: assignment.latePenalty.type === "tiered" ? "12px" : 0 }}>
                                <div>
                                  <label className="label">Max Penalty {assignment.latePenalty.type === "points_per_day" ? "(pts)" : "(%)"}</label>
                                  <input
                                    type="number"
                                    className="input"
                                    min="0"
                                    value={assignment.latePenalty.maxPenalty}
                                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, maxPenalty: parseInt(e.target.value) || 0 } })}
                                  />
                                </div>
                                <div>
                                  <label className="label">Grace Period (hours)</label>
                                  <input
                                    type="number"
                                    className="input"
                                    min="0"
                                    value={assignment.latePenalty.gracePeriodHours}
                                    onChange={(e) => setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, gracePeriodHours: parseInt(e.target.value) || 0 } })}
                                  />
                                </div>
                              </div>
                              {assignment.latePenalty.type === "tiered" && (
                                <div>
                                  <label className="label">Tier Brackets</label>
                                  {(assignment.latePenalty.tiers || []).map((tier, ti) => (
                                    <div key={ti} style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "8px" }}>
                                      <input
                                        type="number"
                                        className="input"
                                        min="1"
                                        value={tier.daysLate}
                                        onChange={(e) => {
                                          const newTiers = [...assignment.latePenalty.tiers];
                                          newTiers[ti] = { ...tier, daysLate: parseInt(e.target.value) || 1 };
                                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                                        }}
                                        style={{ width: "80px" }}
                                        title="Days late"
                                      />
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>days =</span>
                                      <input
                                        type="number"
                                        className="input"
                                        min="0"
                                        value={tier.penalty}
                                        onChange={(e) => {
                                          const newTiers = [...assignment.latePenalty.tiers];
                                          newTiers[ti] = { ...tier, penalty: parseInt(e.target.value) || 0 };
                                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                                        }}
                                        style={{ width: "80px" }}
                                        title="Penalty percent"
                                      />
                                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>%</span>
                                      <button
                                        className="btn"
                                        onClick={() => {
                                          const newTiers = assignment.latePenalty.tiers.filter((_, i) => i !== ti);
                                          setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: newTiers } });
                                        }}
                                        style={{ padding: "4px 8px", minWidth: 0, color: "#f87171" }}
                                        title="Remove tier"
                                      >
                                        <Icon name="Trash2" size={14} />
                                      </button>
                                    </div>
                                  ))}
                                  <button
                                    className="btn btn-secondary"
                                    onClick={() => {
                                      const lastTier = assignment.latePenalty.tiers[assignment.latePenalty.tiers.length - 1];
                                      const newDay = lastTier ? lastTier.daysLate + 2 : 1;
                                      const newPenalty = lastTier ? Math.min(lastTier.penalty + 15, 100) : 10;
                                      setAssignment({ ...assignment, latePenalty: { ...assignment.latePenalty, tiers: [...assignment.latePenalty.tiers, { daysLate: newDay, penalty: newPenalty }] } });
                                    }}
                                    style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                                  >
                                    <Icon name="Plus" size={14} /> Add Tier
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>

                    {/* Import Document */}
                    <div
                      data-tutorial="builder-import"
                      style={{
                        marginBottom: "25px",
                        padding: "20px",
                        background: "rgba(251,191,36,0.1)",
                        borderRadius: "12px",
                        border: "1px solid rgba(251,191,36,0.3)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <h3
                            style={{
                              fontSize: "1rem",
                              fontWeight: 600,
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              marginBottom: "5px",
                            }}
                          >
                            <Icon name="FileUp" size={20} />
                            Import Document & Mark Sections
                          </h3>
                          <p
                            style={{
                              fontSize: "0.85rem",
                              color: "var(--text-secondary)",
                              margin: 0,
                            }}
                          >
                            {importedDoc.text ? (
                              <>
                                <strong style={{ color: "#fbbf24" }}>
                                  {importedDoc.filename}
                                </strong>{" "}
                                loaded
                              </>
                            ) : (
                              "Import a Word or PDF to highlight gradeable sections"
                            )}
                          </p>
                        </div>
                        <div style={{ display: "flex", gap: "10px" }}>
                          <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleDocImport}
                            accept=".docx,.pdf,.doc,.txt"
                            style={{ display: "none" }}
                          />
                          {importedDoc.text && (
                            <>
                              <button
                                onClick={openDocEditor}
                                className="btn btn-secondary"
                              >
                                <Icon name="Edit" size={16} />
                                Edit & Mark
                              </button>
                              <button
                                onClick={() => {
                                  setImportedDoc({
                                    text: "",
                                    html: "",
                                    filename: "",
                                    loading: false,
                                  });
                                  setAssignment({
                                    ...assignment,
                                    title: "",
                                    customMarkers: [],
                                  });
                                  setLoadedAssignmentName("");
                                }}
                                className="btn btn-secondary"
                                style={{
                                  background: "rgba(239,68,68,0.2)",
                                  color: "#ef4444",
                                }}
                                title="Clear imported document"
                              >
                                <Icon name="Trash2" size={16} />
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => fileInputRef.current?.click()}
                            className="btn btn-primary"
                            style={{
                              background:
                                "linear-gradient(135deg, #f59e0b, #d97706)",
                            }}
                          >
                            <Icon name="Upload" size={16} />
                            {importedDoc.loading
                              ? "Loading..."
                              : "Import Word/PDF"}
                          </button>
                        </div>
                      </div>

                      {/* Section Point Values Toggle */}
                      <div style={{ marginTop: "20px", marginBottom: "15px", padding: "15px", background: "rgba(59,130,246,0.1)", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.2)" }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="Sliders" size={18} style={{ color: "#3b82f6" }} />
                            <span style={{ fontWeight: "600" }}>Use Section Point Values</span>
                          </div>
                          <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={assignment.useSectionPoints || false}
                              onChange={(e) => {
                                const enabled = e.target.checked;
                                if (enabled) {
                                  // When enabling, add point values to existing markers (distribute evenly)
                                  const existingMarkers = assignment.customMarkers || [];
                                  const effortPts = assignment.effortPoints ?? 15;
                                  let markersWithPoints;

                                  if (existingMarkers.length > 0) {
                                    // Distribute remaining points evenly among existing markers
                                    const availablePoints = 100 - effortPts;
                                    const pointsPerMarker = Math.floor(availablePoints / existingMarkers.length);
                                    const remainder = availablePoints % existingMarkers.length;

                                    markersWithPoints = existingMarkers.map((m, i) => {
                                      const markerText = typeof m === 'string' ? m : m.start;
                                      const markerType = typeof m === 'object' ? (m.type || 'written') : 'written';
                                      const pts = pointsPerMarker + (i === 0 ? remainder : 0);
                                      return { start: markerText, points: pts, type: markerType };
                                    });
                                  } else {
                                    // No markers - create a default Content section
                                    markersWithPoints = [{ start: "Content", points: 100 - effortPts, type: "written" }];
                                  }

                                  setAssignment({
                                    ...assignment,
                                    useSectionPoints: true,
                                    customMarkers: markersWithPoints,
                                    effortPoints: effortPts,
                                    sectionTemplate: "Custom",
                                  });
                                } else {
                                  setAssignment({ ...assignment, useSectionPoints: false });
                                }
                              }}
                              style={{ width: "18px", height: "18px", cursor: "pointer" }}
                            />
                          </label>
                        </div>
                        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "8px" }}>
                          {assignment.useSectionPoints
                            ? "Grade each section with specific point values"
                            : "Use standard rubric (Content 40, Completeness 25, Writing 20, Effort 15)"}
                        </div>
                      </div>

                      {/* Section Point Summary - Only show when toggle is ON */}
                      {assignment.useSectionPoints && (
                        <div style={{ marginBottom: "20px", padding: "15px", background: "rgba(59,130,246,0.05)", borderRadius: "8px", border: "1px solid rgba(59,130,246,0.15)" }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <Icon name="Calculator" size={16} style={{ color: "#3b82f6" }} />
                              <span style={{ fontWeight: "500", fontSize: "14px" }}>Point Distribution</span>
                            </div>
                            <button
                              onClick={() => {
                                // Redistribute points evenly among existing markers
                                const markers = assignment.customMarkers || [];
                                if (markers.length === 0) return;
                                const effortPts = assignment.effortPoints || 15;
                                const availablePoints = 100 - effortPts;
                                const pointsPerMarker = Math.floor(availablePoints / markers.length);
                                const remainder = availablePoints % markers.length;
                                const redistributed = markers.map((m, i) => ({
                                  ...m,
                                  start: typeof m === 'string' ? m : m.start,
                                  points: pointsPerMarker + (i === 0 ? remainder : 0),
                                }));
                                setAssignment({ ...assignment, customMarkers: redistributed });
                              }}
                              className="btn btn-secondary"
                              style={{ fontSize: "12px", padding: "4px 10px" }}
                            >
                              Distribute Evenly
                            </button>
                          </div>
                          <div style={{ padding: "8px", background: "rgba(0,0,0,0.1)", borderRadius: "4px", fontSize: "13px" }}>
                            <strong>Total Points:</strong> {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15)}
                            {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15) !== 100 && (
                              <span style={{ color: "#ef4444", marginLeft: "10px" }}>
                                (Should equal 100)
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Manual Marker Input */}
                      <div
                        style={{
                          marginTop: "15px",
                          display: "flex",
                          gap: "10px",
                          alignItems: "center",
                        }}
                      >
                        <input
                          type="text"
                          id="manualMarkerInput"
                          placeholder="Type a marker phrase and press Add..."
                          className="input"
                          style={{ flex: 1 }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && e.target.value.trim()) {
                              const newMarker = e.target.value.trim();
                              if (
                                !(assignment.customMarkers || []).includes(
                                  newMarker,
                                )
                              ) {
                                setAssignment({
                                  ...assignment,
                                  customMarkers: [
                                    ...(assignment.customMarkers || []),
                                    newMarker,
                                  ],
                                });
                              }
                              e.target.value = "";
                            }
                          }}
                        />
                        <button
                          onClick={() => {
                            const input =
                              document.getElementById("manualMarkerInput");
                            if (input?.value.trim()) {
                              const newMarker = input.value.trim();
                              if (
                                !(assignment.customMarkers || []).includes(
                                  newMarker,
                                )
                              ) {
                                setAssignment({
                                  ...assignment,
                                  customMarkers: [
                                    ...(assignment.customMarkers || []),
                                    newMarker,
                                  ],
                                });
                              }
                              input.value = "";
                            }
                          }}
                          className="btn btn-secondary"
                        >
                          <Icon name="Plus" size={16} />
                          Add
                        </button>
                      </div>

                      {/* Grading Sections with Points - Only show when toggle is ON */}
                      {assignment.useSectionPoints && (
                        <div style={{ marginTop: "15px" }}>
                          <div style={{ fontWeight: "600", marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                            <Icon name="Target" size={16} />
                            Grading Sections
                          </div>
                          {(assignment.customMarkers || []).length === 0 ? (
                            <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "10px", background: "rgba(0,0,0,0.05)", borderRadius: "6px" }}>
                              No sections defined. Select a template above or add sections manually.
                            </div>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {assignment.customMarkers.map((marker, i) => {
                                const markerName = typeof marker === 'string' ? marker : marker.start;
                                return (
                                <React.Fragment key={i}>
                                <div style={{
                                  display: "flex", alignItems: "center", gap: "8px", padding: "10px",
                                  background: "rgba(251,191,36,0.15)", borderRadius: "6px", border: "1px solid rgba(251,191,36,0.3)"
                                }}>
                                  <Icon name="Target" size={14} style={{ color: "#f59e0b", flexShrink: 0 }} />
                                  <input
                                    type="text"
                                    value={getMarkerText(marker)}
                                    onChange={(e) => {
                                      const updated = [...assignment.customMarkers];
                                      if (typeof updated[i] === "string") {
                                        updated[i] = { start: e.target.value, points: 10, type: "written" };
                                      } else {
                                        updated[i] = { ...updated[i], start: e.target.value };
                                      }
                                      setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                    }}
                                    className="input"
                                    style={{ flex: 1, padding: "4px 8px", fontSize: "13px" }}
                                    placeholder="Section name..."
                                  />
                                  <input
                                    type="number"
                                    value={getMarkerPoints(marker)}
                                    onChange={(e) => {
                                      const updated = [...assignment.customMarkers];
                                      const pts = parseInt(e.target.value) || 0;
                                      if (typeof updated[i] === "string") {
                                        updated[i] = { start: updated[i], points: pts, type: "written" };
                                      } else {
                                        updated[i] = { ...updated[i], points: pts };
                                      }
                                      setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                    }}
                                    style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                    min="0"
                                    max="100"
                                  />
                                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
                                  <select
                                    value={getMarkerType(marker)}
                                    onChange={(e) => {
                                      const updated = [...assignment.customMarkers];
                                      if (typeof updated[i] === "string") {
                                        updated[i] = { start: updated[i], points: 10, type: e.target.value };
                                      } else {
                                        updated[i] = { ...updated[i], type: e.target.value };
                                      }
                                      setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: "Custom" });
                                    }}
                                    style={{ padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", fontSize: "12px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                  >
                                    <option value="written">Written</option>
                                    <option value="short_answer">Short Answer</option>
                                    <option value="multiple_choice">Multiple Choice</option>
                                    <option value="fill-blank">Fill-blank</option>
                                    <option value="vocabulary">Vocabulary</option>
                                    <option value="matching">Matching</option>
                                    <option value="true_false">True/False</option>
                                    <option value="math_equation">Math Equation</option>
                                    <option value="data_table">Data Table</option>
                                  </select>
                                  <button
                                    onClick={() => removeMarker(marker, i)}
                                    style={{ background: "none", border: "none", cursor: "pointer", padding: "4px", color: "#ef4444" }}
                                  >
                                    <Icon name="X" size={14} />
                                  </button>
                                </div>
                                {/* Model answer preview */}
                                {assignment.modelAnswers && assignment.modelAnswers[markerName] && (
                                  <div style={{ marginLeft: "24px", marginBottom: "4px" }}>
                                    <label style={{ fontSize: "11px", color: "var(--text-secondary)", display: "block", marginBottom: "2px" }}>
                                      Model Answer:
                                    </label>
                                    <textarea className="input"
                                      value={assignment.modelAnswers[markerName]}
                                      onChange={(e) => {
                                        const updated = Object.assign({}, assignment.modelAnswers);
                                        updated[markerName] = e.target.value;
                                        setAssignment({ ...assignment, modelAnswers: updated });
                                      }}
                                      style={{ fontSize: "12px", minHeight: "60px", backgroundColor: "var(--bg-tertiary)", opacity: 0.9 }}
                                    />
                                  </div>
                                )}
                                </React.Fragment>
                                );
                              })}
                              {/* Effort Points (always present) */}
                              <div style={{
                                display: "flex", alignItems: "center", gap: "8px", padding: "10px",
                                background: "rgba(34,197,94,0.15)", borderRadius: "6px", border: "1px solid rgba(34,197,94,0.3)"
                              }}>
                                <Icon name="Star" size={14} style={{ color: "#22c55e", flexShrink: 0 }} />
                                <span style={{ flex: 1, fontSize: "13px", fontWeight: "500" }}>Effort & Engagement</span>
                                <input
                                  type="number"
                                  value={assignment.effortPoints || 15}
                                  onChange={(e) => setAssignment({ ...assignment, effortPoints: parseInt(e.target.value) || 0, sectionTemplate: "Custom" })}
                                  style={{ width: "60px", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", textAlign: "center", fontSize: "13px", background: "var(--input-bg)", color: "var(--text-primary)" }}
                                  min="0"
                                  max="30"
                                />
                                <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>pts</span>
                                <div style={{ width: "90px" }}></div> {/* Spacer to align with other rows */}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Marker Library */}
                    <div
                      data-tutorial="builder-markers"
                      style={{
                        marginBottom: "25px",
                        padding: "15px 20px",
                        background: "rgba(99,102,241,0.1)",
                        borderRadius: "12px",
                        border: "1px solid rgba(99,102,241,0.2)",
                      }}
                    >
                      <label
                        style={{
                          display: "block",
                          fontSize: "0.9rem",
                          fontWeight: 600,
                          marginBottom: "10px",
                        }}
                      >
                        <Icon
                          name="Bookmark"
                          size={16}
                          style={{ marginRight: "8px" }}
                        />
                        Suggested Markers for{" "}
                        {config.subject || "Social Studies"}
                      </label>
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        {(
                          markerLibrary[config.subject] ||
                          markerLibrary["Social Studies"] ||
                          []
                        ).map((marker, i) => (
                          <span
                            key={i}
                            style={{
                              padding: "6px 12px",
                              background: "var(--btn-secondary-bg)",
                              borderRadius: "6px",
                              fontSize: "0.85rem",
                              cursor: "pointer",
                            }}
                            onClick={() => {
                              // Check if marker already exists (handle both string and object formats)
                              const exists = (assignment.customMarkers || []).some(m =>
                                typeof m === 'string' ? m === marker : m.start === marker
                              );
                              if (!exists) {
                                setAssignment({
                                  ...assignment,
                                  customMarkers: [
                                    ...(assignment.customMarkers || []),
                                    marker,
                                  ],
                                });
                              }
                            }}
                            title="Click to add"
                          >
                            {typeof marker === 'string' ? marker : marker.start}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Rubric Type Selector */}
                    <div data-tutorial="builder-rubric" style={{ marginBottom: "25px" }}>
                      <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Icon name="Scale" size={16} style={{ color: "#8b5cf6" }} />
                        Assignment Rubric
                      </label>
                      <select
                        className="input"
                        value={assignment.rubricType || "standard"}
                        onChange={(e) => {
                          const newType = e.target.value;
                          setAssignment({
                            ...assignment,
                            rubricType: newType,
                            // Auto-set grading notes for fill-in-blank if not already set
                            gradingNotes: newType === "fill-in-blank" && !assignment.gradingNotes
                              ? "This is a Fill-in-the-Blank activity. Grade on accuracy and completion only."
                              : assignment.gradingNotes,
                          });
                        }}
                        style={{ marginBottom: "10px" }}
                      >
                        <option value="standard">Standard (Use Global Rubric)</option>
                        <option value="fill-in-blank">Fill-in-the-Blank (Accuracy + Completion)</option>
                        <option value="essay">Essay/Written Response (Writing Quality Focus)</option>
                        <option value="cornell-notes">Cornell Notes (Structure + Summary)</option>
                        <option value="completion-only">Completion Only (No AI Grading)</option>
                        <option value="custom">Custom Rubric...</option>
                      </select>

                      {/* Rubric Preview/Description */}
                      {assignment.rubricType && assignment.rubricType !== "standard" && assignment.rubricType !== "custom" && (
                        <div style={{
                          padding: "12px",
                          background: "rgba(139, 92, 246, 0.1)",
                          borderRadius: "8px",
                          fontSize: "0.85rem",
                          color: "var(--text-secondary)",
                          marginBottom: "10px",
                        }}>
                          {assignment.rubricType === "fill-in-blank" && (
                            <div><strong>Categories:</strong> Accuracy (70%) + Completion (30%)<br/>Spelling errors ignored if intent is clear.</div>
                          )}
                          {assignment.rubricType === "essay" && (
                            <div><strong>Categories:</strong> Content (35%) + Writing Quality (30%) + Analysis (20%) + Effort (15%)</div>
                          )}
                          {assignment.rubricType === "cornell-notes" && (
                            <div><strong>Categories:</strong> Content (40%) + Note Structure (25%) + Summary (20%) + Effort (15%)</div>
                          )}
                          {assignment.rubricType === "completion-only" && (
                            <div><strong>No AI grading.</strong> Just tracks that the assignment was submitted.</div>
                          )}
                        </div>
                      )}

                      {/* Custom Rubric Editor */}
                      {assignment.rubricType === "custom" && (
                        <div style={{
                          padding: "15px",
                          background: "rgba(139, 92, 246, 0.08)",
                          borderRadius: "10px",
                          border: "1px solid rgba(139, 92, 246, 0.2)",
                        }}>
                          <div style={{ fontWeight: 600, marginBottom: "12px", fontSize: "0.9rem" }}>
                            Custom Rubric Categories
                          </div>
                          {(assignment.customRubric || [
                            { name: "Content Accuracy", weight: 40 },
                            { name: "Completeness", weight: 25 },
                            { name: "Writing Quality", weight: 20 },
                            { name: "Effort", weight: 15 },
                          ]).map((cat, i) => (
                            <div key={i} style={{ display: "flex", gap: "10px", marginBottom: "8px", alignItems: "center" }}>
                              <input
                                className="input"
                                value={cat.name}
                                onChange={(e) => {
                                  const newRubric = [...(assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ])];
                                  newRubric[i] = { ...newRubric[i], name: e.target.value };
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                placeholder="Category name"
                                style={{ flex: 1 }}
                              />
                              <input
                                className="input"
                                type="number"
                                value={cat.weight}
                                onChange={(e) => {
                                  const newRubric = [...(assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ])];
                                  newRubric[i] = { ...newRubric[i], weight: parseInt(e.target.value) || 0 };
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                style={{ width: "70px" }}
                                min="0"
                                max="100"
                              />
                              <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>%</span>
                              <button
                                onClick={() => {
                                  const newRubric = (assignment.customRubric || [
                                    { name: "Content Accuracy", weight: 40 },
                                    { name: "Completeness", weight: 25 },
                                    { name: "Writing Quality", weight: 20 },
                                    { name: "Effort", weight: 15 },
                                  ]).filter((_, idx) => idx !== i);
                                  setAssignment({ ...assignment, customRubric: newRubric });
                                }}
                                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                              >
                                <Icon name="X" size={16} />
                              </button>
                            </div>
                          ))}
                          <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                          <button
                            onClick={() => {
                              const newRubric = [...(assignment.customRubric || [
                                { name: "Content Accuracy", weight: 40 },
                                { name: "Completeness", weight: 25 },
                                { name: "Writing Quality", weight: 20 },
                                { name: "Effort", weight: 15 },
                              ]), { name: "", weight: 0 }];
                              setAssignment({ ...assignment, customRubric: newRubric });
                            }}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.85rem" }}
                          >
                            <Icon name="Plus" size={14} /> Add Category
                          </button>
                          <button
                            onClick={() => {
                              setAssignment({ ...assignment, customRubric: [
                                { name: "Content Accuracy", weight: 40 },
                                { name: "Completeness", weight: 25 },
                                { name: "Writing Quality", weight: 20 },
                                { name: "Effort", weight: 15 },
                              ]});
                            }}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.85rem" }}
                          >
                            <Icon name="RotateCcw" size={14} /> Reset to Default
                          </button>
                          </div>
                          <div style={{ marginTop: "10px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                            Total: {(assignment.customRubric || [
                              { name: "Content Accuracy", weight: 40 },
                              { name: "Completeness", weight: 25 },
                              { name: "Writing Quality", weight: 20 },
                              { name: "Effort", weight: 15 },
                            ]).reduce((sum, c) => sum + (c.weight || 0), 0)}%
                            {(assignment.customRubric || []).reduce((sum, c) => sum + (c.weight || 0), 0) !== 100 && (
                              <span style={{ color: "#f59e0b" }}> (should be 100%)</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Generate Model Answers */}
                    {assignment.customMarkers && assignment.customMarkers.length > 0
                     && importedDoc && (importedDoc.text || importedDoc.html) && (
                      <div style={{ marginTop: "12px", marginBottom: "12px" }}>
                        <button className="btn btn-secondary" onClick={handleGenerateModelAnswers}
                          disabled={modelAnswersLoading}
                          style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {modelAnswersLoading
                            ? <><Icon name="Loader2" size={14} className="spinning" /> Generating...</>
                            : <><Icon name="Sparkles" size={14} /> Generate Model Answers</>}
                        </button>
                        {assignment.modelAnswers && Object.keys(assignment.modelAnswers).length > 0 && (
                          <span style={{ marginLeft: "8px", fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", display: "inline-block" }}>
                            {Object.keys(assignment.modelAnswers).length + " sections answered"}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Align to Standards */}
                    {importedDoc && (importedDoc.text || importedDoc.html) && (
                      <div style={{ marginTop: "12px", marginBottom: "20px" }}>
                        <button
                          className="btn btn-secondary"
                          onClick={handleAlignToStandards}
                          disabled={alignmentLoading}
                          style={{ display: "flex", alignItems: "center", gap: "6px" }}
                        >
                          {alignmentLoading
                            ? <><Icon name="Loader2" size={14} className="spinning" /> Analyzing Standards...</>
                            : <><Icon name="BookOpen" size={14} /> Align to Standards</>}
                        </button>

                        {standardsAlignment && (
                          <div style={{
                            marginTop: "15px",
                            padding: "20px",
                            background: "rgba(99,102,241,0.08)",
                            borderRadius: "12px",
                            border: "1px solid rgba(99,102,241,0.3)",
                          }}>
                            {/* Overall Score */}
                            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "15px" }}>
                              <h4 style={{ margin: 0, fontSize: "1rem" }}>Standards Alignment</h4>
                              <div style={{
                                flex: 1, height: "8px", background: "rgba(255,255,255,0.1)",
                                borderRadius: "4px", overflow: "hidden"
                              }}>
                                <div style={{
                                  width: Math.round((standardsAlignment.overall_alignment_score || 0) * 100) + "%",
                                  height: "100%",
                                  background: (standardsAlignment.overall_alignment_score || 0) > 0.7 ? "#4ade80"
                                    : (standardsAlignment.overall_alignment_score || 0) > 0.4 ? "#fbbf24" : "#ef4444",
                                  borderRadius: "4px",
                                  transition: "width 0.5s ease",
                                }} />
                              </div>
                              <span style={{ fontWeight: 600, minWidth: "40px", textAlign: "right" }}>
                                {Math.round((standardsAlignment.overall_alignment_score || 0) * 100)}%
                              </span>
                            </div>

                            {/* Matched Standards */}
                            {(standardsAlignment.matched_standards || []).map(function(std, idx) {
                              return (
                                <div key={std.code || idx} style={{
                                  padding: "10px 12px",
                                  background: "var(--input-bg)",
                                  borderRadius: "8px",
                                  marginBottom: "8px",
                                  borderLeft: "3px solid " + (std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444"),
                                }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <strong style={{ fontSize: "0.9rem" }}>{std.code}</strong>
                                    <span style={{
                                      fontSize: "0.8rem", fontWeight: 600,
                                      color: std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444",
                                    }}>{Math.round(std.confidence * 100)}% match</span>
                                  </div>
                                  <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "var(--text-primary)" }}>{std.benchmark}</p>
                                  {std.evidence && (
                                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "2px 0" }}>
                                      <em>Evidence:</em> {std.evidence}
                                    </p>
                                  )}
                                  {std.alignment_notes && (
                                    <p style={{ fontSize: "0.8rem", color: "#fbbf24", margin: "2px 0" }}>{std.alignment_notes}</p>
                                  )}
                                </div>
                              );
                            })}

                            {/* Suggestions */}
                            {(standardsAlignment.suggestions || []).length > 0 && (
                              <div style={{ marginTop: "12px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Improvement Suggestions</h5>
                                <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.85rem" }}>
                                  {standardsAlignment.suggestions.map(function(s, i) {
                                    return <li key={i} style={{ marginBottom: "4px" }}>{s}</li>;
                                  })}
                                </ul>
                              </div>
                            )}

                            {/* Question Analysis */}
                            {(standardsAlignment.question_analysis || []).filter(function(q) { return q.rewrite_suggestion; }).length > 0 && (
                              <div style={{ marginTop: "15px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Question-Level Analysis</h5>
                                {standardsAlignment.question_analysis.filter(function(q) { return q.rewrite_suggestion; }).map(function(q, i) {
                                  return (
                                    <div key={i} style={{
                                      padding: "10px 12px",
                                      background: "var(--input-bg)",
                                      borderRadius: "8px",
                                      marginBottom: "8px",
                                    }}>
                                      <p style={{ fontSize: "0.85rem", margin: "0 0 4px" }}>
                                        <strong>Q:</strong> {(q.question_text || "").substring(0, 120)}{(q.question_text || "").length > 120 ? "..." : ""}
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                                        Aligned to: {q.aligned_standard || "None"} ({q.alignment_quality || "unknown"})
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "#fbbf24" }}>{q.rewrite_suggestion}</p>
                                      <button
                                        className="btn btn-secondary"
                                        onClick={function() {
                                          handleRewriteForAlignment([{
                                            original_text: q.question_text,
                                            target_standard: q.aligned_standard,
                                            rewrite_goal: q.rewrite_suggestion
                                          }]);
                                        }}
                                        disabled={rewriteLoading}
                                        style={{ fontSize: "0.8rem", padding: "4px 10px", marginTop: "6px" }}
                                      >
                                        {rewriteLoading ? "Rewriting..." : "Rewrite This Question"}
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Rewrites */}
                            {standardsAlignment.rewrites && standardsAlignment.rewrites.length > 0 && (
                              <div style={{ marginTop: "15px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Rewritten Questions</h5>
                                {standardsAlignment.rewrites.map(function(r, i) {
                                  return (
                                    <div key={i} style={{
                                      padding: "10px 12px",
                                      background: "var(--input-bg)",
                                      borderRadius: "8px",
                                      marginBottom: "8px",
                                      borderLeft: "3px solid #4ade80",
                                    }}>
                                      <p style={{ fontSize: "0.8rem", margin: "0 0 4px", color: "var(--text-secondary)" }}>
                                        <strong>Original:</strong> {r.original_text}
                                      </p>
                                      <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "#4ade80" }}>
                                        <strong>Rewritten:</strong> {r.rewritten_text}
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                                        <em>{r.standard_code}:</em> {r.change_explanation}
                                      </p>
                                      <button
                                        className="btn btn-secondary"
                                        onClick={function() {
                                          navigator.clipboard.writeText(r.rewritten_text);
                                        }}
                                        style={{ fontSize: "0.75rem", padding: "2px 8px", marginTop: "4px" }}
                                      >
                                        Copy Rewrite
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Cost info */}
                            {standardsAlignment.usage && (
                              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "10px", textAlign: "right" }}>
                                {standardsAlignment.usage.cost_display || ""}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Grading Notes */}
                    <div data-tutorial="builder-notes" style={{ marginBottom: "25px" }}>
                      <label className="label">
                        Assignment-Specific Grading Notes
                      </label>
                      <textarea
                        className="input"
                        value={assignment.gradingNotes}
                        onChange={(e) =>
                          setAssignment({
                            ...assignment,
                            gradingNotes: e.target.value,
                          })
                        }
                        placeholder="Special instructions for grading this assignment..."
                        style={{ minHeight: "100px" }}
                      />
                    </div>

                    {/* Questions */}
                    <div data-tutorial="builder-questions" style={{ marginBottom: "20px" }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "15px",
                        }}
                      >
                        <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
                          Questions ({assignment.questions.length}) -{" "}
                          {assignment.questions.reduce(
                            (sum, q) => sum + (q.points || 0),
                            0,
                          )}{" "}
                          pts
                        </h3>
                        <button
                          onClick={addQuestion}
                          className="btn btn-primary"
                        >
                          <Icon name="Plus" size={16} /> Add Question
                        </button>
                      </div>

                      {assignment.questions.length === 0 ? (
                        <div
                          style={{
                            textAlign: "center",
                            padding: "40px",
                            background: "var(--input-bg)",
                            borderRadius: "12px",
                            color: "var(--text-muted)",
                          }}
                        >
                          <Icon name="FileQuestion" size={40} />
                          <p style={{ marginTop: "10px" }}>
                            No questions yet. Click "Add Question" to start
                            building.
                          </p>
                        </div>
                      ) : (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "15px",
                          }}
                        >
                          {assignment.questions.map((q, i) => (
                            <div
                              key={q.id}
                              style={{
                                background: "var(--glass-bg)",
                                borderRadius: "12px",
                                border: "1px solid var(--glass-border)",
                                padding: "20px",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  marginBottom: "15px",
                                }}
                              >
                                <span
                                  style={{
                                    fontSize: "0.9rem",
                                    fontWeight: 600,
                                    color: "#a5b4fc",
                                  }}
                                >
                                  Question {i + 1}
                                </span>
                                <button
                                  onClick={() => removeQuestion(i)}
                                  style={{
                                    padding: "6px 10px",
                                    borderRadius: "6px",
                                    border: "none",
                                    background: "rgba(248,113,113,0.2)",
                                    color: "#f87171",
                                    cursor: "pointer",
                                  }}
                                >
                                  <Icon name="Trash2" size={14} />
                                </button>
                              </div>
                              <div
                                style={{
                                  display: "grid",
                                  gridTemplateColumns: "1fr 150px 100px",
                                  gap: "12px",
                                  marginBottom: "12px",
                                }}
                              >
                                <div>
                                  <label
                                    className="label"
                                    style={{ fontSize: "0.8rem" }}
                                  >
                                    Marker
                                  </label>
                                  <select
                                    className="input"
                                    value={q.marker}
                                    onChange={(e) =>
                                      updateQuestion(
                                        i,
                                        "marker",
                                        e.target.value,
                                      )
                                    }
                                  >
                                    {(
                                      markerLibrary[assignment.subject] ||
                                      markerLibrary["Other"]
                                    ).map((m) => (
                                      <option key={m} value={m}>
                                        {m}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                <div>
                                  <label
                                    className="label"
                                    style={{ fontSize: "0.8rem" }}
                                  >
                                    Type
                                  </label>
                                  <select
                                    className="input"
                                    value={q.type}
                                    onChange={(e) =>
                                      updateQuestion(i, "type", e.target.value)
                                    }
                                  >
                                    <option value="short_answer">
                                      Short Answer
                                    </option>
                                    <option value="essay">Essay</option>
                                    <option value="fill_blank">
                                      Fill in Blank
                                    </option>
                                    <option value="multiple_choice">
                                      Multiple Choice
                                    </option>
                                  </select>
                                </div>
                                <div>
                                  <label
                                    className="label"
                                    style={{ fontSize: "0.8rem" }}
                                  >
                                    Points
                                  </label>
                                  <input
                                    type="number"
                                    className="input"
                                    value={q.points}
                                    onChange={(e) =>
                                      updateQuestion(
                                        i,
                                        "points",
                                        parseInt(e.target.value) || 0,
                                      )
                                    }
                                    min="0"
                                  />
                                </div>
                              </div>
                              <div>
                                <label
                                  className="label"
                                  style={{ fontSize: "0.8rem" }}
                                >
                                  Question/Prompt
                                </label>
                                <textarea
                                  className="input"
                                  value={q.prompt}
                                  onChange={(e) =>
                                    updateQuestion(i, "prompt", e.target.value)
                                  }
                                  placeholder="Enter the question..."
                                  style={{ minHeight: "60px" }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Export Buttons */}
                    <div
                      data-tutorial="builder-save"
                      style={{
                        display: "flex",
                        gap: "15px",
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      {assignment.title && (
                        <span
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            color: "#4ade80",
                            fontSize: "0.85rem",
                            padding: "8px 12px",
                            background: "rgba(74,222,128,0.1)",
                            border: "1px solid rgba(74,222,128,0.3)",
                            borderRadius: "8px",
                          }}
                        >
                          <Icon
                            name="Check"
                            size={14}
                            style={{ color: "#4ade80" }}
                          />
                          Auto-saves
                        </span>
                      )}
                      <button
                        onClick={saveAssignmentConfig}
                        disabled={!assignment.title}
                        className="btn btn-secondary"
                        style={{ opacity: !assignment.title ? 0.5 : 1 }}
                      >
                        <Icon name="Save" size={18} /> Save Now
                      </button>
                      <button
                        onClick={() => exportAssignment("docx")}
                        disabled={!assignment.title}
                        className="btn btn-secondary"
                        style={{ opacity: !assignment.title ? 0.5 : 1 }}
                      >
                        <Icon name="FileText" size={18} /> Export Word Doc
                      </button>
                      <button
                        onClick={() => exportAssignment("pdf")}
                        disabled={!assignment.title}
                        className="btn btn-secondary"
                        style={{ opacity: !assignment.title ? 0.5 : 1 }}
                      >
                        <Icon name="FileType" size={18} /> Export PDF
                      </button>
                    </div>
                  </div>
                </div>
  );
});
