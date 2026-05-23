import React from "react";
import Icon from "./Icon";
import StandardCard from "./StandardCard";
import AssignmentPlayer from "./AssignmentPlayer";
import QuestionEditToolbar from "./QuestionEditToolbar";
import * as api from "../services/api";

export default function PlannerLesson({ addToast, assignment, assignmentQuestionCounts, assignmentSectionsOpen, brainstormIdeas, brainstormIdeasHandler, brainstormLoading, config, contentOnly, deleteSelectedQuestions, docUploading, domainNameMap, editMode, editingQuestion, expandedStandards, exportLessonPlanHandler, generateLessonPlan, generatedAssignment, getDomains, getTotalQuestionCount, handleDocUpload, handleMatchStandards, lessonPlan, lessonVariations, matchResults, matchingInProgress, plannerLoading, previewResults, previewShowAnswers, publishAssessmentHandler, publishingAssessment, regenerateOneQuestion, regenerateSelectedQuestions, regeneratingQuestions, removeUploadedDoc, saveEditedQuestion, scrollToDomain, selectAllQuestions, selectedIdea, selectedQuestions, selectedStandards, setActiveTab, setAssignment, setAssignmentQuestionCounts, setAssignmentSectionsOpen, setBrainstormIdeas, setContentOnly, setEditMode, setEditingQuestion, setExpandedStandards, setGeneratedAssignment, setLessonPlan, setLessonVariations, setLoadedAssignmentName, setPlannerMode, setPreviewResults, setPreviewShowAnswers, setSelectedIdea, setSelectedQuestions, setSelectedStandards, setShowSaveLesson, setUnitConfig, standards, standardsScrollRef, toggleQuestionSelect, toggleStandard, unitConfig, uploadedDocs, user }) {
  return (
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
  );
}
