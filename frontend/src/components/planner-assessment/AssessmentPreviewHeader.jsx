import React from "react";
import Icon from "../Icon";
import PlatformExportMenu from "../PlatformExportMenu";

export default function AssessmentPreviewHeader(props) {
  const { assessmentAnswers, editMode, exportAssessmentForPlatformHandler, exportAssessmentHandler, generatedAssessment, gradeAssessmentAnswersHandler, gradingAssessment, publishAssessmentHandler, publishingAssessment, redistributePoints, setAssessmentAnswers, setEditMode, setEditingQuestion, setGeneratedAssessment, setSelectedQuestions, setSelectedSources, setShowPlatformExport, showPlatformExport } = props;
  return (
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
  );
}
