import React from "react";
import Icon from "./Icon";
import PlatformExportMenu from "./PlatformExportMenu";
import QuestionEditToolbar from "./QuestionEditToolbar";
import QuestionEditOverlay from "./QuestionEditOverlay";
import MatchingCards from "./MatchingCards";
import * as api from "../services/api";

export default function PlannerAssessment({ assessmentAnswers, assessmentConfig, assessmentLoading, assessmentStandardsScrollRef, deleteSelectedQuestions, distributeDOK, distributePoints, distributeQuestions, domainNameMap, editMode, editingQuestion, exportAssessmentForPlatformHandler, exportAssessmentHandler, fetchSavedLessons, generateAssessmentHandler, generatedAssessment, getDomains, getTotalQuestionCount, gradeAssessmentAnswersHandler, gradingAssessment, periods, plannerLoading, previewShowAnswers, publishAssessmentHandler, publishingAssessment, redistributePoints, regenerateOneQuestion, regenerateSelectedQuestions, regeneratingQuestions, saveAssessmentHandler, saveAssessmentName, saveEditedQuestion, savedAssignmentData, savedAssignments, savedLessons, savingAssessment, scrollToDomain, sectionsDropdownOpen, selectAllQuestions, selectedQuestions, selectedSources, selectedStandards, setAssessmentAnswers, setAssessmentConfig, setEditMode, setEditingQuestion, setGeneratedAssessment, setSaveAssessmentName, setSectionsDropdownOpen, setSelectedQuestions, setSelectedSources, setSelectedStandards, setShowPlatformExport, showPlatformExport, standards, toggleQuestionSelect, toggleStandard, uploadedDocs }) {
  return (
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
  );
}
