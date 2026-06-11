import React, { useState } from "react";
import Icon from "../components/Icon";
import useAnalyticsData from "./analytics/useAnalyticsData";
import GradeChartsSection from "./analytics/GradeChartsSection";
import StudentPanel from "./analytics/StudentPanel";
import ItemAnalysisPanel from "./analytics/ItemAnalysisPanel";
import AnalyticsFiltersHeader from "./analytics/AnalyticsFiltersHeader";
import ClassScopedView from "./analytics/ClassScopedView";

/**
 * AnalyticsTab - Extracted from App.jsx
 *
 * Props:
 *   config              - read config.assignments_folder
 *   status              - read status.results.length (trigger re-fetch)
 *   periods             - class period objects (shared with other tabs)
 *   sortedPeriods       - sorted periods (shared with other tabs)
 *   savedAssignments    - assignment name list (shared)
 *   savedAssignmentData - assignment config data (shared)
 *   addToast            - toast notification function
 */

export default React.memo(function AnalyticsTab({
  config,
  status,
  periods,
  sortedPeriods,
  savedAssignments,
  savedAssignmentData,
  addToast,
  assessmentResults,
  teacherClasses,
}) {
  const [selectedItemAnalysis, setSelectedItemAnalysis] = useState(null);
  const [itemAnalysisOpen, setItemAnalysisOpen] = useState(false);
  // Phase 2: Progress Rank grid class selector
  var [selectedClassForGrid, setSelectedClassForGrid] = useState('all');
  // Phase 3a: sub-tab switcher inside class-scoped view
  // Phase 4.2 #6: added 'effectiveness' option for the Remediation Effectiveness dashboard.
  var [classView, setClassView] = useState('progressRank'); // 'progressRank' | 'gradebook' | 'compare' | 'effectiveness'

  // Data state, fetch effects, and period filtering live in the hook (CQ split).
  const {
    analytics,
    analyticsLoading,
    chartsOverlay,
    chartsReady,
    analyticsPeriod,
    setAnalyticsPeriod,
    analyticsClassPeriod,
    setAnalyticsClassPeriod,
    analyticsSource,
    setAnalyticsSource,
    periodStudentMap,
    filteredAnalytics,
  } = useAnalyticsData({ periods, status });

  // --- Render ---
  return (
                <div data-tutorial="analytics-card" className="fade-in">
                  {/* Class selector — Phase 2 Progress Rank grid entry point */}
                  <div className="glass-card" style={{ padding: "14px 20px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "12px" }}>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Class:</label>
                    <select
                      value={selectedClassForGrid}
                      onChange={function(e) { setSelectedClassForGrid(e.target.value); setClassView('progressRank'); }}
                      className="input"
                      style={{ padding: "6px 12px", fontSize: "0.9rem", minWidth: "200px" }}
                    >
                      <option value="all">All Classes</option>
                      {(teacherClasses || []).map(function(c) {
                        return <option key={c.id} value={c.id}>{c.name}</option>;
                      })}
                    </select>
                  </div>

                  {selectedClassForGrid !== 'all' ? (
                  <ClassScopedView
                    selectedClassForGrid={selectedClassForGrid}
                    classView={classView}
                    setClassView={setClassView}
                    addToast={addToast}
                  />
                  ) : analyticsLoading ? (
                    <div
                      className="glass-card"
                      style={{ padding: "80px", textAlign: "center" }}
                    >
                      <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                      <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>
                        Generating Analytics...
                      </h2>
                      <p style={{ color: "var(--text-secondary)", marginTop: "8px", fontSize: "0.9rem" }}>
                        Crunching the numbers
                      </p>
                    </div>
                  ) : !filteredAnalytics || filteredAnalytics.error ? (
                    <div
                      className="glass-card"
                      style={{ padding: "60px", textAlign: "center" }}
                    >
                      <Icon name="BarChart3" size={64} />
                      <h2 style={{ marginTop: "20px", fontSize: "1.5rem" }}>
                        No Data Yet
                      </h2>
                      <p
                        style={{
                          color: "var(--text-secondary)",
                          marginTop: "10px",
                        }}
                      >
                        Grade some assignments to see analytics here.
                      </p>
                    </div>
                  ) : (
                    <div style={{ position: "relative" }}>
                      {chartsOverlay && (
                        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 50, background: "#6366f1", borderRadius: "12px", padding: "14px 24px", boxShadow: "0 4px 20px rgba(99,102,241,0.4)", willChange: "transform", display: "flex", alignItems: "center", gap: "12px" }}>
                          <div style={{ width: "22px", height: "22px", border: "3px solid rgba(255,255,255,0.3)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
                          <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#fff", whiteSpace: "nowrap" }}>Generating Analytics...</span>
                        </div>
                      )}
                      <div style={chartsOverlay ? { filter: "blur(3px)", opacity: 0.4, transition: "filter 0.4s ease, opacity 0.4s ease", pointerEvents: "none" } : { filter: "none", opacity: 1, transition: "filter 0.4s ease, opacity 0.4s ease" }}>
                      {/* Period + Quarter Filters & Export */}
                      <AnalyticsFiltersHeader
                        sortedPeriods={sortedPeriods}
                        analyticsClassPeriod={analyticsClassPeriod}
                        setAnalyticsClassPeriod={setAnalyticsClassPeriod}
                        analyticsPeriod={analyticsPeriod}
                        setAnalyticsPeriod={setAnalyticsPeriod}
                        filteredAnalytics={filteredAnalytics}
                        addToast={addToast}
                      />

                      {/* Source Filter */}
                      <div style={{ display: "flex", gap: "6px", marginBottom: "12px" }}>
                        {[{key: 'all', label: 'All'}, {key: 'assignments', label: 'Assignments'}, {key: 'assessments', label: 'Assessments'}].map(function(opt) {
                          var isActive = analyticsSource === opt.key;
                          return React.createElement('button', {
                            key: opt.key,
                            onClick: function() { setAnalyticsSource(opt.key); },
                            style: {
                              padding: "6px 14px", borderRadius: "8px", border: "none",
                              fontSize: "0.8rem", fontWeight: isActive ? 600 : 400, cursor: "pointer",
                              background: isActive ? "#7c3aed" : "rgba(255,255,255,0.06)",
                              color: isActive ? "white" : "var(--text-secondary)",
                              transition: "all 0.2s",
                            },
                          }, opt.label);
                        })}
                      </div>

                      {/* Formative vs Summative Summary */}
                      {analytics && analytics.assessment_category_summary && (analytics.assessment_category_summary.formative_count > 0 || analytics.assessment_category_summary.summative_count > 0) && (
                        <div style={{
                          padding: "16px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                          borderRadius: "12px", marginBottom: "16px",
                        }}>
                          <div style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                            <Icon name="BarChart3" size={16} />
                            Assessment Category Comparison
                          </div>
                          <div style={{ display: "flex", gap: "20px" }}>
                            <div style={{ flex: 1, textAlign: "center", padding: "12px", background: "rgba(34,197,94,0.08)", borderRadius: "8px", border: "1px solid rgba(34,197,94,0.2)" }}>
                              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#22c55e" }}>
                                {analytics.assessment_category_summary.formative_average != null ? analytics.assessment_category_summary.formative_average + '%' : '\u2014'}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                                {'Formative Avg (' + analytics.assessment_category_summary.formative_count + ' scores)'}
                              </div>
                            </div>
                            <div style={{ flex: 1, textAlign: "center", padding: "12px", background: "rgba(239,68,68,0.08)", borderRadius: "8px", border: "1px solid rgba(239,68,68,0.2)" }}>
                              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#ef4444" }}>
                                {analytics.assessment_category_summary.summative_average != null ? analytics.assessment_category_summary.summative_average + '%' : '\u2014'}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                                {'Summative Avg (' + analytics.assessment_category_summary.summative_count + ' scores)'}
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Item Analysis Panel */}
                      <ItemAnalysisPanel
                        assessmentResults={assessmentResults}
                        selectedItemAnalysis={selectedItemAnalysis}
                        setSelectedItemAnalysis={setSelectedItemAnalysis}
                        itemAnalysisOpen={itemAnalysisOpen}
                        setItemAnalysisOpen={setItemAnalysisOpen}
                      />

                      {chartsReady && (
                        <>
                          <GradeChartsSection filteredAnalytics={filteredAnalytics} periodStudentMap={periodStudentMap} />

                          <StudentPanel
                            filteredAnalytics={filteredAnalytics}
                            periodStudentMap={periodStudentMap}
                            sortedPeriods={sortedPeriods}
                            savedAssignments={savedAssignments}
                            savedAssignmentData={savedAssignmentData}
                            config={config}
                            status={status}
                            addToast={addToast}
                            periods={periods}
                          />
                        </>
                      )}
                      </div>
                    </div>
                  )}
                </div>
  );
});
