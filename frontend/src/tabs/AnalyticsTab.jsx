import React, { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback, useTransition } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  ScatterChart,
  Scatter,
  Cell,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import Icon from "../components/Icon";
import * as api from "../services/api";

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

// --- Shared helpers (module-level for use by memoized sub-components) ---
var stripNamePunctuation = function(s) { return s.replace(/['\u2018\u2019\-]/g, ''); };

const studentNameMatchesPeriod = (studentName, students) => {
  if (!students || students.length === 0) return true;
  const nameWords = stripNamePunctuation((studentName || "").toLowerCase()).replace(/[,;.]/g, " ").split(/\s+/).filter(Boolean);
  return students.some((student) => {
    const first = stripNamePunctuation((student.first || "").toLowerCase().trim());
    const last = stripNamePunctuation((student.last || "").toLowerCase().trim());
    if (!first && !last) return false;
    const searchWords = [first, last].join(" ").split(/\s+/).filter(Boolean);
    return searchWords.every((sw) =>
      nameWords.some((nw) => nw.startsWith(sw) || sw.startsWith(nw))
    );
  });
};

// Defers heavy children (charts) to after first paint using a non-blocking transition.
// Shows a height-matched placeholder instantly so layout doesn't shift.
function DeferredMount({ children, height }) {
  const [show, setShow] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        obs.disconnect();
        React.startTransition(() => setShow(true));
      }
    }, { rootMargin: "200px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  if (!show) return <div ref={ref} style={{ height }} />;
  return children;
}

// Memoized scatter chart — skips re-render when only selectedStudent changes
const ScatterSection = React.memo(function ScatterSection({ filteredAnalytics, onStudentClick }) {
  const scatterRef = useRef(null);
  const [scatterWidth, setScatterWidth] = useState(0);
  useLayoutEffect(() => {
    if (scatterRef.current) setScatterWidth(scatterRef.current.clientWidth);
  }, []);
  return (
    <div
      ref={scatterRef}
      data-tutorial="analytics-scatter"
      className="glass-card"
      style={{ padding: "25px", marginBottom: "20px", contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}
    >
      <h3
        style={{
          fontSize: "1.1rem",
          fontWeight: 700,
          marginBottom: "10px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <Icon name="Target" size={20} />
        Student Proficiency vs Growth
      </h3>
      <p
        style={{
          fontSize: "0.85rem",
          color: "var(--text-secondary)",
          marginBottom: "15px",
        }}
      >
        Click any dot to view that student's detailed
        progress. Quadrants show performance patterns.
      </p>
      <DeferredMount height={350}>
        {scatterWidth > 0 && (<ScatterChart
          width={scatterWidth}
          height={350}
          margin={{
            top: 20,
            right: 30,
            bottom: 60,
            left: 50,
          }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--glass-border)"
          />
          <XAxis
            type="number"
            dataKey="proficiency"
            name="Proficiency"
            domain={[0, 100]}
            tick={{
              fill: "var(--text-secondary)",
              fontSize: 11,
            }}
            label={{
              value: "Average Score (%)",
              position: "insideBottom",
              offset: -5,
              fill: "var(--text-secondary)",
              fontSize: 12,
            }}
          />
          <YAxis
            type="number"
            dataKey="growth"
            name="Growth"
            domain={[-30, 100]}
            tick={{
              fill: "var(--text-secondary)",
              fontSize: 11,
            }}
            label={{
              value: "Growth (pts)",
              angle: -90,
              position: "insideLeft",
              fill: "var(--text-secondary)",
              fontSize: 12,
            }}
          />
          <ZAxis
            type="number"
            dataKey="assignments"
            range={[60, 200]}
            name="Assignments"
          />
          <ReferenceLine
            x={70}
            stroke="#f59e0b"
            strokeDasharray="5 5"
          />
          <ReferenceLine
            y={0}
            stroke="#6366f1"
            strokeDasharray="5 5"
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const d = payload[0]?.payload;
              if (!d) return null;
              return (
                <div style={{
                  background: "var(--modal-content-bg)",
                  border: "1px solid var(--glass-border)",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                }}>
                  <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--text-primary)", marginBottom: "6px" }}>
                    {d.name}
                  </div>
                  <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "3px" }}>
                    <span>Avg Score: {d.proficiency}%</span>
                    <span>Growth: {d.growth > 0 ? "+" : ""}{d.growth} pts</span>
                    <span>Assignments: {d.assignments}</span>
                  </div>
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="bottom"
            align="center"
            wrapperStyle={{
              paddingTop: "20px",
              fontSize: "11px",
            }}
            payload={[
              {
                value: "Star Performer",
                type: "circle",
                color: "#10b981",
              },
              {
                value: "Improving",
                type: "circle",
                color: "#f59e0b",
              },
              {
                value: "Stable",
                type: "circle",
                color: "#6366f1",
              },
              {
                value: "Needs Support",
                type: "circle",
                color: "#ef4444",
              },
            ]}
          />
          <Scatter
            animationDuration={400}
            name="Students"
            data={(
              filteredAnalytics.student_progress || []
            ).map((s) => {
              const grades = s.grades || [];
              let growth = 0;
              if (grades.length >= 2) {
                const firstHalf = grades.slice(
                  0,
                  Math.ceil(grades.length / 2),
                );
                const secondHalf = grades.slice(
                  Math.ceil(grades.length / 2),
                );
                const firstAvg =
                  firstHalf.reduce(
                    (sum, g) => sum + g.score,
                    0,
                  ) / firstHalf.length;
                const secondAvg =
                  secondHalf.reduce(
                    (sum, g) => sum + g.score,
                    0,
                  ) / secondHalf.length;
                growth = Math.round(secondAvg - firstAvg);
              }
              return {
                name: s.name,
                proficiency: s.average,
                growth: growth,
                assignments: grades.length,
                trend: s.trend,
              };
            })}
            onClick={(data) => {
              if (data && data.name)
                onStudentClick(data.name);
            }}
            style={{ cursor: "pointer" }}
          >
            {(filteredAnalytics.student_progress || []).map(
              (s, index) => {
                const isLow = s.average < 70;
                const grades = s.grades || [];
                let growth = 0;
                if (grades.length >= 2) {
                  const firstHalf = grades.slice(
                    0,
                    Math.ceil(grades.length / 2),
                  );
                  const secondHalf = grades.slice(
                    Math.ceil(grades.length / 2),
                  );
                  const firstAvg =
                    firstHalf.reduce(
                      (sum, g) => sum + g.score,
                      0,
                    ) / firstHalf.length;
                  const secondAvg =
                    secondHalf.reduce(
                      (sum, g) => sum + g.score,
                      0,
                    ) / secondHalf.length;
                  growth = secondAvg - firstAvg;
                }
                let color = "#6366f1"; // Default purple
                if (isLow && growth <= 0)
                  color = "#ef4444"; // Red - struggling
                else if (isLow && growth > 0)
                  color = "#f59e0b"; // Orange - improving
                else if (!isLow && growth < -5)
                  color = "#f97316"; // Dark orange - declining
                else if (!isLow && growth >= 5)
                  color = "#10b981"; // Green - star
                return <Cell key={index} fill={color} />;
              },
            )}
          </Scatter>
        </ScatterChart>)}
      </DeferredMount>
    </div>
  );
});

// Memoized stats + grade distribution + assignment averages — skips re-render when only selectedStudent changes
const GradeChartsSection = React.memo(function GradeChartsSection({ filteredAnalytics, periodStudentMap }) {
  const [distributionView, setDistributionView] = useState("overall");
  const [selectedAssignments, setSelectedAssignments] = useState(new Set());
  const [assignmentDropdownOpen, setAssignmentDropdownOpen] = useState(false);
  const distRef = useRef(null);
  const avgRef = useRef(null);
  const [distWidth, setDistWidth] = useState(0);
  const [avgWidth, setAvgWidth] = useState(0);
  useLayoutEffect(() => {
    if (distRef.current) setDistWidth(distRef.current.clientWidth);
    if (avgRef.current) setAvgWidth(avgRef.current.clientWidth);
  }, []);

  const uniqueAssignmentNames = useMemo(() => {
    if (!filteredAnalytics) return [];
    const names = new Set();
    (filteredAnalytics.all_grades || []).forEach((g) => { if (g.assignment) names.add(g.assignment); });
    return [...names].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  }, [filteredAnalytics]);

  const distributionData = useMemo(() => {
    if (!filteredAnalytics || distributionView === "overall") return null;
    let grades = filteredAnalytics.all_grades || [];
    if (grades.length === 0) return [];
    if (distributionView === "by_assignment" && selectedAssignments.size > 0) {
      grades = grades.filter((g) => selectedAssignments.has(g.assignment));
    }
    const groups = {};
    if (distributionView === "by_period") {
      const periodNames = Object.keys(periodStudentMap);
      if (periodNames.length === 0) return [];
      grades.forEach((g) => {
        const period = periodNames.find((pn) => studentNameMatchesPeriod(g.student_name, periodStudentMap[pn]));
        if (!period) return;
        if (!groups[period]) groups[period] = [];
        groups[period].push(g.score);
      });
    } else {
      grades.forEach((g) => {
        const key = g.assignment || "Unknown";
        if (!groups[key]) groups[key] = [];
        groups[key].push(g.score);
      });
    }
    return Object.entries(groups).map(([name, scores]) => {
      const mean = scores.length > 0 ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length * 10) / 10 : 0;
      const passing = scores.filter((s) => s >= 60).length;
      return {
        name: distributionView === "by_period" ? name.replace(/^Period\s*/i, "Pd. ") : name.length > 20 ? name.slice(0, 20) + "..." : name,
        A: scores.filter((s) => s >= 90).length,
        B: scores.filter((s) => s >= 80 && s < 90).length,
        C: scores.filter((s) => s >= 70 && s < 80).length,
        D: scores.filter((s) => s >= 60 && s < 70).length,
        F: scores.filter((s) => s < 60).length,
        total: scores.length,
        mean,
        passRate: scores.length > 0 ? Math.round(passing / scores.length * 1000) / 10 : 0,
      };
    }).sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  }, [filteredAnalytics, distributionView, selectedAssignments, periodStudentMap]);

  return (
    <>
    {/* Stats Cards */}
    <div
      data-tutorial="analytics-stats"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "15px",
        marginBottom: "20px",
      }}
    >
      {[
        {
          label: "Total Graded",
          value:
            filteredAnalytics.class_stats
              ?.total_assignments || 0,
          icon: "FileCheck",
          color: "#6366f1",
        },
        {
          label: "Students",
          value:
            filteredAnalytics.class_stats?.total_students ||
            0,
          icon: "Users",
          color: "#8b5cf6",
        },
        {
          label: "Class Average",
          value: `${filteredAnalytics.class_stats?.class_average || 0}%`,
          icon: "TrendingUp",
          color: "#10b981",
        },
        {
          label: "Highest Score",
          value: `${filteredAnalytics.class_stats?.highest || 0}%`,
          icon: "Trophy",
          color: "#f59e0b",
        },
      ].map((stat, i) => (
        <div
          key={i}
          className="glass-card"
          style={{ padding: "20px" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginBottom: "10px",
            }}
          >
            <div
              style={{
                background: `${stat.color}20`,
                padding: "8px",
                borderRadius: "10px",
              }}
            >
              <Icon name={stat.icon} size={20} />
            </div>
            <span
              style={{
                color: "var(--text-secondary)",
                fontSize: "0.9rem",
              }}
            >
              {stat.label}
            </span>
          </div>
          <div
            style={{
              fontSize: "2rem",
              fontWeight: 800,
              color: stat.color,
            }}
          >
            {stat.value}
          </div>
        </div>
      ))}
    </div>

    {/* Charts */}
    <div
      data-tutorial="analytics-charts"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: "20px",
        marginBottom: "20px",
      }}
    >
      <div ref={distRef} className="glass-card" style={{ padding: "25px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "8px" }}>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px", margin: 0 }}>
            <Icon name="PieChart" size={20} />
            Grade Distribution
          </h3>
          <div style={{ display: "flex", gap: "2px", background: "var(--glass-bg)", borderRadius: "8px", padding: "2px" }}>
            {[{ id: "overall", label: "Overall" }, { id: "by_period", label: "By Period" }, { id: "by_assignment", label: "By Assignment" }].map((v) => (
              <button key={v.id} onClick={() => { setDistributionView(v.id); if (v.id !== "by_assignment") setAssignmentDropdownOpen(false); }} style={{ padding: "5px 10px", borderRadius: "6px", border: "none", background: distributionView === v.id ? "var(--accent-primary)" : "transparent", color: distributionView === v.id ? "white" : "var(--text-secondary)", cursor: "pointer", fontSize: "0.75rem", fontWeight: distributionView === v.id ? 600 : 500, transition: "all 0.2s" }}>{v.label}</button>
            ))}
          </div>
        </div>
        {distributionView === "by_assignment" && uniqueAssignmentNames.length > 0 && (
          <div style={{ position: "relative", marginBottom: "10px" }}>
            <button onClick={() => setAssignmentDropdownOpen(!assignmentDropdownOpen)} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "5px 10px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "var(--glass-bg)", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.75rem", width: "100%" }}>
              <Icon name="Filter" size={13} />
              <span style={{ flex: 1, textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selectedAssignments.size === 0 ? "All Assignments (" + uniqueAssignmentNames.length + ")" : selectedAssignments.size + " of " + uniqueAssignmentNames.length + " selected"}</span>
              <Icon name={assignmentDropdownOpen ? "ChevronUp" : "ChevronDown"} size={13} />
            </button>
            {assignmentDropdownOpen && (
              <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 50, marginTop: "4px", background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", boxShadow: "0 8px 24px rgba(0,0,0,0.3)", maxHeight: "180px", overflowY: "auto", padding: "4px" }}>
                <button onClick={() => { setSelectedAssignments(new Set()); }} style={{ width: "100%", padding: "5px 8px", border: "none", background: selectedAssignments.size === 0 ? "var(--accent-primary)" : "transparent", color: selectedAssignments.size === 0 ? "white" : "var(--text-secondary)", borderRadius: "4px", cursor: "pointer", fontSize: "0.73rem", textAlign: "left", fontWeight: 600 }}>All Assignments</button>
                {uniqueAssignmentNames.map((name) => {
                  const checked = selectedAssignments.has(name);
                  return (
                    <label key={name} style={{ display: "flex", alignItems: "center", gap: "6px", padding: "4px 8px", borderRadius: "4px", cursor: "pointer", fontSize: "0.73rem", color: "var(--text-primary)", background: checked ? "rgba(var(--accent-primary-rgb, 99,102,241), 0.1)" : "transparent" }}>
                      <input type="checkbox" checked={checked} onChange={() => { setSelectedAssignments((prev) => { const next = new Set(prev); if (next.has(name)) next.delete(name); else next.add(name); return next; }); }} style={{ accentColor: "var(--accent-primary)" }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        )}
        {distributionView === "overall" ? (
          <>
            <DeferredMount height={200}>
              {distWidth > 0 && (<PieChart width={distWidth} height={200}>
                <Pie
                  animationDuration={400}
                  data={[
                    { name: "A", value: filteredAnalytics.class_stats?.grade_distribution?.A || 0 },
                    { name: "B", value: filteredAnalytics.class_stats?.grade_distribution?.B || 0 },
                    { name: "C", value: filteredAnalytics.class_stats?.grade_distribution?.C || 0 },
                    { name: "D", value: filteredAnalytics.class_stats?.grade_distribution?.D || 0 },
                    { name: "F", value: filteredAnalytics.class_stats?.grade_distribution?.F || 0 },
                  ].filter((d) => d.value > 0)}
                  cx="50%" cy="50%" outerRadius={70} dataKey="value"
                  label={({ name, value }) => name + ": " + value}
                >
                  {["#4ade80", "#60a5fa", "#fbbf24", "#f97316", "#ef4444"].map((c, i) => (
                    <Cell key={i} fill={c} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>)}
            </DeferredMount>
            <div style={{ display: "flex", justifyContent: "center", gap: "16px", marginTop: "8px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              <span>Mean: {filteredAnalytics.class_stats?.class_average || 0}%</span>
              <span>Pass rate: {filteredAnalytics.class_stats?.total_assignments > 0 ? Math.round(((filteredAnalytics.class_stats.grade_distribution?.A || 0) + (filteredAnalytics.class_stats.grade_distribution?.B || 0) + (filteredAnalytics.class_stats.grade_distribution?.C || 0) + (filteredAnalytics.class_stats.grade_distribution?.D || 0)) / filteredAnalytics.class_stats.total_assignments * 1000) / 10 : 0}%</span>
            </div>
          </>
        ) : (
          <>
            <DeferredMount height={200}>
              {distWidth > 0 && (<BarChart width={distWidth} height={200} data={distributionData || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" />
                <XAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} interval={0} angle={distributionView === "by_assignment" ? -25 : 0} textAnchor={distributionView === "by_assignment" ? "end" : "middle"} height={distributionView === "by_assignment" ? 50 : 30} />
                <YAxis tick={{ fill: "var(--text-secondary)" }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px" }} />
                <Bar dataKey="A" stackId="grades" fill="#4ade80" animationDuration={400} />
                <Bar dataKey="B" stackId="grades" fill="#60a5fa" animationDuration={400} />
                <Bar dataKey="C" stackId="grades" fill="#fbbf24" animationDuration={400} />
                <Bar dataKey="D" stackId="grades" fill="#f97316" animationDuration={400} />
                <Bar dataKey="F" stackId="grades" fill="#ef4444" radius={[4, 4, 0, 0]} animationDuration={400} />
              </BarChart>)}
            </DeferredMount>
            <div style={{ display: "flex", justifyContent: "center", gap: "12px", marginTop: "6px", fontSize: "0.7rem" }}>
              {[{ label: "A", color: "#4ade80" }, { label: "B", color: "#60a5fa" }, { label: "C", color: "#fbbf24" }, { label: "D", color: "#f97316" }, { label: "F", color: "#ef4444" }].map((g) => (
                <span key={g.label} style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--text-secondary)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: g.color, display: "inline-block" }} />
                  {g.label}
                </span>
              ))}
            </div>
            {distributionData && distributionData.length > 0 && (
              <div style={{ display: "flex", justifyContent: "center", gap: "16px", marginTop: "8px", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                <span>Mean: {Math.round(distributionData.reduce((s, d) => s + d.mean * d.total, 0) / Math.max(1, distributionData.reduce((s, d) => s + d.total, 0)) * 10) / 10}%</span>
                <span>Pass rate: {Math.round(distributionData.reduce((s, d) => s + d.total - d.F, 0) / Math.max(1, distributionData.reduce((s, d) => s + d.total, 0)) * 1000) / 10}%</span>
              </div>
            )}
          </>
        )}
      </div>

      <div ref={avgRef} className="glass-card" style={{ padding: "25px" }}>
        <h3
          style={{
            fontSize: "1.1rem",
            fontWeight: 700,
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <Icon name="BarChart3" size={20} />
          Assignment Averages
        </h3>
        <DeferredMount height={200}>
          {avgWidth > 0 && (<BarChart
            width={avgWidth}
            height={200}
            data={filteredAnalytics.assignment_stats || []}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--glass-border)"
            />
            <XAxis
              dataKey="name"
              tick={{
                fill: "var(--text-secondary)",
                fontSize: 11,
              }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "var(--text-secondary)" }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--modal-content-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
              }}
            />
            <Bar
              dataKey="average"
              fill="#6366f1"
              radius={[4, 4, 0, 0]}
              animationDuration={400}
            />
          </BarChart>)}
        </DeferredMount>
      </div>
    </div>
    </>
  );
});

// StudentPanel — owns selectedStudent state so clicking a student does NOT re-render
// the parent AnalyticsTab (filters, grade charts, cost summary, etc.)
// StaticSections — Needs Attention, Top Performers, Cost Summary, Missing Assignments
// None depend on selectedStudent, so this skips re-render on student click
const StaticSections = React.memo(function StaticSections({
  filteredAnalytics, periodStudentMap, sortedPeriods,
  savedAssignments, savedAssignmentData, config, status, addToast, periods,
  onStudentClick,
}) {
  const [missingAssignmentFilter, setMissingAssignmentFilter] = useState("");
  const [missingPeriodFilter, setMissingPeriodFilter] = useState("");
  const [expandedPeriods, setExpandedPeriods] = useState(new Set());
  const [missingStudentFilter, setMissingStudentFilter] = useState("");
  const [assignmentViewMode, setAssignmentViewMode] = useState("missing"); // "missing" | "submitted"
  const [missingUploadedFiles, setMissingUploadedFiles] = useState([]);
  const [missingFilesLoading, setMissingFilesLoading] = useState(false);

  useEffect(() => {
    if (!config.assignments_folder) return;
    setMissingFilesLoading(true);
    api.listFiles(config.assignments_folder)
      .then((data) => setMissingUploadedFiles(data.files || []))
      .catch(() => setMissingUploadedFiles([]))
      .finally(() => setMissingFilesLoading(false));
  }, [config.assignments_folder, status.results.length]);

  return (
    <>
      {/* Needs Attention + Top Performers */}
      <div
        data-tutorial="analytics-alerts"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          marginBottom: "20px",
          contentVisibility: "auto",
          containIntrinsicSize: "auto 300px",
        }}
      >
        <div
          style={{
            background: "rgba(239,68,68,0.1)",
            borderRadius: "20px",
            border: "1px solid rgba(239,68,68,0.3)",
            padding: "25px",
          }}
        >
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              marginBottom: "15px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              color: "#f87171",
            }}
          >
            <Icon name="AlertTriangle" size={20} />
            Needs Attention
          </h3>
          {(filteredAnalytics.attention_needed || []).length ===
          0 ? (
            <p style={{ color: "var(--text-secondary)" }}>
              All students are doing well!
            </p>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}
            >
              {(filteredAnalytics.attention_needed || [])
                .slice(0, 5)
                .map((s, i) => (
                  <div
                    key={i}
                    onClick={() => onStudentClick(s.name)}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "10px 15px",
                      background: "var(--input-bg)",
                      borderRadius: "10px",
                      cursor: "pointer",
                    }}
                  >
                    <span
                      style={{
                        textDecoration: "underline dotted",
                      }}
                    >
                      {s.name}
                    </span>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <span
                        style={{
                          color: "#f87171",
                          fontWeight: 700,
                        }}
                      >
                        {s.average}%
                      </span>
                      <span
                        style={{
                          fontSize: "0.8rem",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background:
                            s.trend === "declining"
                              ? "rgba(239,68,68,0.3)"
                              : "rgba(251,191,36,0.3)",
                          color:
                            s.trend === "declining"
                              ? "#f87171"
                              : "#fbbf24",
                        }}
                      >
                        {s.trend}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div
          style={{
            background: "rgba(74,222,128,0.1)",
            borderRadius: "20px",
            border: "1px solid rgba(74,222,128,0.3)",
            padding: "25px",
          }}
        >
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              marginBottom: "15px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              color: "#4ade80",
            }}
          >
            <Icon name="Award" size={20} />
            Top Performers
          </h3>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            {(filteredAnalytics.top_performers || []).map(
              (s, i) => (
                <div
                  key={i}
                  onClick={() => onStudentClick(s.name)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 15px",
                    background: "var(--input-bg)",
                    borderRadius: "10px",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <span
                      style={{
                        width: "24px",
                        height: "24px",
                        borderRadius: "50%",
                        background:
                          i === 0
                            ? "#fbbf24"
                            : i === 1
                              ? "#94a3b8"
                              : i === 2
                                ? "#cd7f32"
                                : "var(--glass-border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                      }}
                    >
                      {i + 1}
                    </span>
                    <span
                      style={{
                        textDecoration: "underline dotted",
                      }}
                    >
                      {s.name}
                    </span>
                  </div>
                  <span
                    style={{
                      color: "#4ade80",
                      fontWeight: 700,
                    }}
                  >
                    {s.average}%
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      </div>

      {/* API Cost Summary */}
      {filteredAnalytics.cost_summary && (
        <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 200px" }}>
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
            <Icon name="DollarSign" size={20} />
            API Cost Tracker
          </h3>
          {/* Summary stats */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: "12px",
              marginBottom: "20px",
            }}
          >
            {[
              { label: "Total Spend", value: "$" + filteredAnalytics.cost_summary.total_cost.toFixed(4), color: "#f59e0b" },
              { label: "Avg / Student", value: "$" + filteredAnalytics.cost_summary.avg_cost_per_student.toFixed(4), color: "#6366f1" },
              { label: "Total Tokens", value: filteredAnalytics.cost_summary.total_tokens.toLocaleString(), color: "#10b981" },
              { label: "API Calls", value: filteredAnalytics.cost_summary.total_api_calls.toLocaleString(), color: "#8b5cf6" },
            ].map((stat) => (
              <div
                key={stat.label}
                style={{
                  textAlign: "center",
                  padding: "12px",
                  background: "rgba(0,0,0,0.15)",
                  borderRadius: "8px",
                }}
              >
                <div style={{ fontSize: "1.4rem", fontWeight: 700, color: stat.color }}>{stat.value}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{stat.label}</div>
              </div>
            ))}
          </div>
          {/* Cost by model */}
          {filteredAnalytics.cost_summary.by_model?.length > 0 && (
            <div style={{ marginBottom: "15px" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>By Model</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {filteredAnalytics.cost_summary.by_model.map((m) => (
                  <div
                    key={m.model}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "var(--input-bg)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span style={{ fontWeight: 500 }}>{m.model}</span>
                    <div style={{ display: "flex", gap: "16px", color: "var(--text-secondary)" }}>
                      <span>{m.count} graded</span>
                      <span>{m.tokens.toLocaleString()} tokens</span>
                      <span style={{ fontWeight: 600, color: "#f59e0b" }}>${m.cost.toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* Cost by assignment */}
          {filteredAnalytics.cost_summary.by_assignment?.length > 0 && (
            <div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>By Assignment</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {filteredAnalytics.cost_summary.by_assignment.map((a) => (
                  <div
                    key={a.assignment}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "8px 12px",
                      background: "var(--input-bg)",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span style={{ fontWeight: 500, maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.assignment}</span>
                    <div style={{ display: "flex", gap: "16px", color: "var(--text-secondary)" }}>
                      <span>{a.count} students</span>
                      <span style={{ fontWeight: 600, color: "#f59e0b" }}>${a.cost.toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Missing Assignments Section */}
      <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 400px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "20px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <h3
              style={{
                fontSize: "1.1rem",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: "10px",
                margin: 0,
              }}
            >
              <Icon name={assignmentViewMode === "missing" ? "UserX" : "CheckSquare"} size={20} />
              Assignment Tracker
            </h3>
            <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
              <button
                onClick={() => setAssignmentViewMode("missing")}
                style={{
                  padding: "4px 12px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  border: "none",
                  cursor: "pointer",
                  background: assignmentViewMode === "missing" ? "rgba(251,191,36,0.3)" : "transparent",
                  color: assignmentViewMode === "missing" ? "#b45309" : "var(--text-secondary)",
                }}
              >
                Missing
              </button>
              <button
                onClick={() => setAssignmentViewMode("submitted")}
                style={{
                  padding: "4px 12px",
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  border: "none",
                  borderLeft: "1px solid var(--glass-border)",
                  cursor: "pointer",
                  background: assignmentViewMode === "submitted" ? "rgba(16,185,129,0.3)" : "transparent",
                  color: assignmentViewMode === "submitted" ? "#059669" : "var(--text-secondary)",
                }}
              >
                Submitted
              </button>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => {
              if (!config.assignments_folder) {
                addToast(
                  "Set assignments folder in Settings first",
                  "error",
                );
                return;
              }
              setMissingFilesLoading(true);
              api
                .listFiles(config.assignments_folder)
                .then((data) =>
                  setMissingUploadedFiles(data.files || []),
                )
                .catch(() => setMissingUploadedFiles([]))
                .finally(() => setMissingFilesLoading(false));
            }}
            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
          >
            <Icon name="RefreshCw" size={14} />
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: "15px",
            flexWrap: "wrap",
            marginBottom: "20px",
          }}
        >
          <div style={{ flex: "1", minWidth: "180px" }}>
            <label
              style={{
                fontSize: "0.8rem",
                color: "#888",
                marginBottom: "4px",
                display: "block",
              }}
            >
              Period
            </label>
            <select
              className="input"
              value={missingPeriodFilter}
              onChange={(e) => {
                setMissingPeriodFilter(e.target.value);
                setMissingStudentFilter("");
              }}
              style={{ width: "100%" }}
            >
              <option value="">All Periods</option>
              {sortedPeriods.map((p) => (
                <option key={p.filename} value={p.filename}>
                  {p.period_name}
                </option>
              ))}
            </select>
          </div>
          <div style={{ flex: "1", minWidth: "180px" }}>
            <label
              style={{
                fontSize: "0.8rem",
                color: "#888",
                marginBottom: "4px",
                display: "block",
              }}
            >
              Student
            </label>
            <div style={{ position: "relative" }}>
              <input
                type="text"
                className="input"
                list="missing-student-suggestions"
                placeholder="Type or select student..."
                value={missingStudentFilter}
                onChange={(e) =>
                  setMissingStudentFilter(e.target.value)
                }
                onClick={(e) => {
                  if (missingStudentFilter) {
                    e.target.dataset.prev =
                      missingStudentFilter;
                    setMissingStudentFilter("");
                  }
                }}
                onBlur={(e) => {
                  if (
                    !missingStudentFilter &&
                    e.target.dataset.prev
                  ) {
                    setMissingStudentFilter(
                      e.target.dataset.prev,
                    );
                    e.target.dataset.prev = "";
                  }
                }}
                style={{
                  width: "100%",
                  paddingRight: missingStudentFilter
                    ? "30px"
                    : undefined,
                }}
              />
              {missingStudentFilter && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setMissingStudentFilter("");
                  }}
                  style={{
                    position: "absolute",
                    right: "8px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#888",
                    padding: "4px",
                    display: "flex",
                    alignItems: "center",
                  }}
                  title="Clear"
                >
                  <Icon name="X" size={14} />
                </button>
              )}
            </div>
            <datalist id="missing-student-suggestions">
              {(missingPeriodFilter
                ? (periodStudentMap[sortedPeriods.find(
                    (p) => p.filename === missingPeriodFilter,
                  )?.period_name] || [])
                : Object.values(periodStudentMap).flat()
              ).map((s, i) => {
                const name =
                  s.full ||
                  s.name ||
                  (
                    (s.first || "") +
                    " " +
                    (s.last || "")
                  ).trim();
                return <option key={i} value={name} />;
              })}
            </datalist>
          </div>
          <div style={{ flex: "1", minWidth: "180px" }}>
            <label
              style={{
                fontSize: "0.8rem",
                color: "#888",
                marginBottom: "4px",
                display: "block",
              }}
            >
              Assignment
            </label>
            <select
              className="input"
              value={missingAssignmentFilter}
              onChange={(e) =>
                setMissingAssignmentFilter(e.target.value)
              }
              style={{ width: "100%" }}
            >
              <option value="">All Assignments</option>
              {savedAssignments.map((name) => (
                <option key={name} value={name}>
                  {name}
                  {savedAssignmentData[name]?.completionOnly
                    ? " (Completion)"
                    : ""}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Missing Report */}
        {periods.length === 0 ? (
          <div
            style={{
              color: "#888",
              textAlign: "center",
              padding: "20px",
            }}
          >
            <Icon
              name="AlertCircle"
              size={24}
              style={{ marginBottom: "10px", opacity: 0.5 }}
            />
            <div>
              Upload period rosters in Settings to track missing
              assignments
            </div>
          </div>
        ) : missingFilesLoading ? (
          <div
            style={{
              color: "#888",
              textAlign: "center",
              padding: "20px",
            }}
          >
            Loading files...
          </div>
        ) : (
          (() => {
            // Get assignments to check
            const assignmentsToCheck = missingAssignmentFilter
              ? [missingAssignmentFilter]
              : savedAssignments;

            // Get periods to check
            const periodsToCheck = missingPeriodFilter
              ? sortedPeriods.filter(
                  (p) => p.filename === missingPeriodFilter,
                )
              : sortedPeriods;

            // Pre-normalize uploaded file names once (not per call)
            const uploadedNormed = missingUploadedFiles.map((f) => {
              let name = (f.name || f)
                .toLowerCase()
                .replace(/\.(docx|pdf|doc|txt)$/i, "");
              name = name.replace(/\s*\(\d+\)\s*$/, "");
              name = name.replace(/\s*-\s*copy\s*\d*$/i, "");
              return name
                .replace(/[^\w\s&']/g, " ")
                .replace(/_/g, " ")
                .replace(/\s+/g, " ")
                .trim();
            });

            // Pre-normalize assignment names once
            const assignmentNormed = {};
            assignmentsToCheck.forEach((assignmentName) => {
              const assignmentData = savedAssignmentData[assignmentName] || {};
              assignmentNormed[assignmentName] = [
                assignmentName.toLowerCase(),
                ...(assignmentData.aliases || []).map((a) => a.toLowerCase()),
                ...(assignmentData.importedFilename ? [assignmentData.importedFilename.replace(/\.\w+$/, "").toLowerCase()] : []),
              ].map((aName) => {
                const normName = aName.replace(/[^\w\s&']/g, " ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
                const words = normName.split(" ").filter((w) => w.length > 3);
                return { normName, words };
              });
            });

            // Cache results: "studentName|assignmentName" -> boolean
            const uploadCache = {};
            const hasUploaded = (studentName, assignmentName) => {
              const key = studentName + "|" + assignmentName;
              if (key in uploadCache) return uploadCache[key];

              const sName = studentName.toLowerCase();
              const sNorm = sName.replace(/[_\-\.,;]/g, " ").replace(/\s+/g, " ").trim();
              const nameParts = sNorm.split(" ");
              const nameThreshold = Math.max(2, nameParts.length - 1);
              const sJoined = sNorm.replace(/ /g, "");
              const normChecks = assignmentNormed[assignmentName] || [];

              const result = uploadedNormed.some((fNorm) => {
                const nameMatchCount = nameParts.filter((part) => fNorm.includes(part)).length;
                const hasStudentName = nameMatchCount >= nameThreshold || fNorm.includes(sJoined);
                if (!hasStudentName) return false;
                return normChecks.some(({ normName, words }) => {
                  if (fNorm.includes(normName)) return true;
                  if (normName.length > 15 && fNorm.includes(normName.slice(0, Math.min(normName.length, 35)))) return true;
                  if (words.length < 2) return false;
                  const matched = words.filter((w) => fNorm.includes(w)).length;
                  return matched >= Math.max(3, Math.ceil(words.length * 0.75));
                });
              });
              uploadCache[key] = result;
              return result;
            };

            // If filtering by student
            if (missingStudentFilter) {
              const studentLower =
                missingStudentFilter.toLowerCase();
              let studentInfo = null;
              let studentPeriod = null;

              for (const period of periodsToCheck) {
                const found = (periodStudentMap[period.period_name] || period.students || []).find(
                  (s) => {
                    const fullName = (
                      s.full ||
                      s.name ||
                      (
                        (s.first || "") +
                        " " +
                        (s.last || "")
                      ).trim()
                    ).toLowerCase();
                    return (
                      fullName.includes(studentLower) ||
                      studentLower.includes(fullName)
                    );
                  },
                );
                if (found) {
                  studentInfo = found;
                  studentPeriod = period.period_name;
                  break;
                }
              }

              const displayName = studentInfo
                ? studentInfo.full ||
                  studentInfo.name ||
                  (
                    (studentInfo.first || "") +
                    " " +
                    (studentInfo.last || "")
                  ).trim()
                : missingStudentFilter;

              const missing = assignmentsToCheck.filter(
                (a) => !hasUploaded(displayName, a),
              );
              const submitted = assignmentsToCheck.filter((a) =>
                hasUploaded(displayName, a),
              );

              return (
                <div>
                  <div
                    style={{
                      padding: "15px",
                      background: "rgba(0,0,0,0.2)",
                      borderRadius: "8px",
                      marginBottom: "15px",
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        marginBottom: "8px",
                      }}
                    >
                      {displayName}{" "}
                      {studentPeriod && (
                        <span
                          style={{
                            color: "#888",
                            fontWeight: 400,
                          }}
                        >
                          ({studentPeriod})
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: "20px",
                        fontSize: "0.9rem",
                      }}
                    >
                      <span>
                        <span
                          style={{
                            color: "#f59e0b",
                            fontWeight: 600,
                          }}
                        >
                          {missing.length}
                        </span>{" "}
                        missing
                      </span>
                      <span>
                        <span
                          style={{
                            color: "#10b981",
                            fontWeight: 600,
                          }}
                        >
                          {submitted.length}
                        </span>{" "}
                        uploaded
                      </span>
                      <span>
                        <span
                          style={{
                            color: "#6366f1",
                            fontWeight: 600,
                          }}
                        >
                          {assignmentsToCheck.length}
                        </span>{" "}
                        total
                      </span>
                    </div>
                  </div>
                  {missing.length > 0 ? (
                    <div>
                      <div
                        style={{
                          fontSize: "0.85rem",
                          color: "#888",
                          marginBottom: "10px",
                        }}
                      >
                        Missing:
                      </div>
                      <div
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "8px",
                        }}
                      >
                        {missing.map((a) => (
                          <span
                            key={a}
                            style={{
                              padding: "6px 12px",
                              background:
                                "rgba(251,191,36,0.15)",
                              borderRadius: "6px",
                              fontSize: "0.85rem",
                              color: "#b45309",
                              border: "1px solid rgba(180,83,9,0.3)",
                            }}
                          >
                            {a}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        color: "#10b981",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      <Icon name="CheckCircle" size={18} />
                      All assignments uploaded!
                    </div>
                  )}
                </div>
              );
            }

            // Default: show by period
            let totalMissing = 0;
            let totalStudents = 0;
            const periodReports = [];

            periodsToCheck.forEach((period) => {
              const students = periodStudentMap[period.period_name] || period.students || [];
              totalStudents += students.length;
              const studentsWithMissing = [];

              const showSubmitted = assignmentViewMode === "submitted";
              students.forEach((student) => {
                const name =
                  student.full ||
                  student.name ||
                  (
                    (student.first || "") +
                    " " +
                    (student.last || "")
                  ).trim();
                const missing = [];
                const submitted = [];
                assignmentsToCheck.forEach((a) => {
                  if (hasUploaded(name, a)) {
                    submitted.push(a);
                  } else {
                    missing.push(a);
                  }
                });
                if (missing.length > 0) {
                  studentsWithMissing.push({ name, missing, submitted });
                  totalMissing += missing.length;
                } else if (showSubmitted) {
                  studentsWithMissing.push({ name, missing: [], submitted });
                }
              });

              const studentsWithSubmitted = studentsWithMissing.filter(s => s.submitted.length > 0);
              const studentsActuallyMissing = studentsWithMissing.filter(s => s.missing.length > 0);

              periodReports.push({
                period: period.period_name,
                total: students.length,
                studentsWithMissing: studentsActuallyMissing,
                studentsWithSubmitted,
                allComplete: studentsActuallyMissing.length === 0,
              });
            });

            const totalSlots =
              totalStudents * assignmentsToCheck.length;
            const totalUploaded = totalSlots - totalMissing;

            return (
              <div>
                {/* Summary Stats */}
                <div
                  style={{
                    display: "flex",
                    gap: "20px",
                    marginBottom: "20px",
                    padding: "15px",
                    background: "rgba(0,0,0,0.2)",
                    borderRadius: "8px",
                  }}
                >
                  <div style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: "1.8rem",
                        fontWeight: 700,
                        color: "#f59e0b",
                      }}
                    >
                      {totalMissing}
                    </div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "#888",
                      }}
                    >
                      Missing
                    </div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: "1.8rem",
                        fontWeight: 700,
                        color: "#10b981",
                      }}
                    >
                      {totalUploaded}
                    </div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "#888",
                      }}
                    >
                      Uploaded
                    </div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: "1.8rem",
                        fontWeight: 700,
                        color: "#6366f1",
                      }}
                    >
                      {totalStudents}
                    </div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "#888",
                      }}
                    >
                      Students
                    </div>
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div
                      style={{
                        fontSize: "1.8rem",
                        fontWeight: 700,
                        color: "#8b5cf6",
                      }}
                    >
                      {assignmentsToCheck.length}
                    </div>
                    <div
                      style={{
                        fontSize: "0.75rem",
                        color: "#888",
                      }}
                    >
                      Assignments
                    </div>
                  </div>
                </div>

                {/* Per Period Breakdown */}
                <div style={{ display: "grid", gap: "12px" }}>
                  {periodReports.map((report) => {
                    const canCollapse = !missingPeriodFilter && periodReports.length > 1;
                    const isCollapsed = canCollapse && !expandedPeriods.has(report.period);
                    const displayStudents = assignmentViewMode === "submitted"
                      ? report.studentsWithSubmitted
                      : report.studentsWithMissing;
                    const isMissing = assignmentViewMode === "missing";
                    return (
                    <div
                      key={report.period}
                      style={{
                        padding: "12px 15px",
                        background: "rgba(0,0,0,0.15)",
                        borderRadius: "8px",
                        border: isMissing
                          ? (report.allComplete ? "1px solid rgba(16,185,129,0.3)" : "1px solid rgba(251,191,36,0.3)")
                          : "1px solid rgba(16,185,129,0.3)",
                      }}
                    >
                      <div
                        onClick={canCollapse ? () => {
                          setExpandedPeriods(prev => {
                            const next = new Set(prev);
                            if (next.has(report.period)) next.delete(report.period);
                            else next.add(report.period);
                            return next;
                          });
                        } : undefined}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          cursor: canCollapse ? "pointer" : "default",
                          marginBottom:
                            !isCollapsed && displayStudents.length > 0
                              ? "10px"
                              : 0,
                        }}
                      >
                        <span style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                          {canCollapse && (
                            <Icon name={isCollapsed ? "ChevronRight" : "ChevronDown"} size={16} style={{ opacity: 0.6 }} />
                          )}
                          {report.period}
                        </span>
                        <span style={{ fontSize: "0.85rem" }}>
                          {isMissing ? (
                            report.allComplete ? (
                              <span style={{ color: "#10b981" }}>
                                ✓ All complete
                              </span>
                            ) : (
                              <span style={{ color: "#b45309" }}>
                                {report.studentsWithMissing.length}{" "}
                                students missing work
                              </span>
                            )
                          ) : (
                            <span style={{ color: "#059669" }}>
                              {report.studentsWithSubmitted.length} students with submissions
                            </span>
                          )}
                        </span>
                      </div>
                      {!isCollapsed && displayStudents.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          {displayStudents.map(
                            (s, idx) => {
                              const items = isMissing ? s.missing : s.submitted;
                              return (
                              <div
                                key={idx}
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                  flexWrap: "wrap",
                                }}
                              >
                                <span
                                  style={{
                                    minWidth: "140px",
                                    fontWeight: 500,
                                    fontSize: "0.9rem",
                                  }}
                                >
                                  {s.name}
                                  {!isMissing && s.missing.length > 0 && (
                                    <span style={{ color: "#b45309", fontWeight: 400, fontSize: "0.75rem", marginLeft: "6px" }}>
                                      ({s.missing.length} missing)
                                    </span>
                                  )}
                                </span>
                                <div
                                  style={{
                                    display: "flex",
                                    gap: "5px",
                                    flexWrap: "wrap",
                                  }}
                                >
                                  {items.map((a) => (
                                    <span
                                      key={a}
                                      style={{
                                        padding: "2px 8px",
                                        background: isMissing
                                          ? "rgba(251,191,36,0.15)"
                                          : "rgba(16,185,129,0.15)",
                                        borderRadius: "4px",
                                        fontSize: "0.75rem",
                                        color: isMissing ? "#b45309" : "#059669",
                                        border: isMissing
                                          ? "1px solid rgba(180,83,9,0.3)"
                                          : "1px solid rgba(16,185,129,0.3)",
                                      }}
                                    >
                                      {a}
                                    </span>
                                  ))}
                                </div>
                              </div>
                              );
                            },
                          )}
                        </div>
                      )}
                    </div>
                    );
                  })}
                </div>
              </div>
            );
          })()
        )}
      </div>

    </>
  );
});

// StudentTable — memoized to skip re-render when selectedStudent changes for non-table reasons
const StudentTable = React.memo(function StudentTable({
  filteredAnalytics, selectedStudent, onStudentClick,
}) {
  const [studentSortCol, setStudentSortCol] = useState("name");
  const [studentSortDir, setStudentSortDir] = useState("asc");

  return (
      <div className="glass-card" style={{ padding: "25px", contentVisibility: "auto", containIntrinsicSize: "auto 500px" }}>
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
          <Icon name="Users" size={20} />
          All Students Overview
        </h3>
        <table>
          <thead>
            <tr>
              {[
                { key: "name", label: "Student" },
                { key: "assignments", label: "Assignments" },
                { key: "average", label: "Average" },
                { key: "content", label: "Content", small: true },
                { key: "completeness", label: "Complete", small: true },
                { key: "writing", label: "Writing", small: true },
                { key: "effort", label: "Effort", small: true },
                { key: "trend", label: "Trend" },
              ].map((col) => (
                <th
                  key={col.key}
                  onClick={() => {
                    if (studentSortCol === col.key) {
                      setStudentSortDir(studentSortDir === "asc" ? "desc" : "asc");
                    } else {
                      setStudentSortCol(col.key);
                      setStudentSortDir(col.key === "name" ? "asc" : "desc");
                    }
                  }}
                  style={{
                    textAlign: col.key === "name" ? "left" : "center",
                    fontSize: col.small ? "0.8rem" : undefined,
                    cursor: "pointer",
                    userSelect: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col.label}
                  {studentSortCol === col.key ? (
                    <span style={{ marginLeft: "4px", fontSize: "0.7rem" }}>
                      {studentSortDir === "asc" ? "\u25B2" : "\u25BC"}
                    </span>
                  ) : (
                    <span style={{ marginLeft: "4px", fontSize: "0.7rem", opacity: 0.3 }}>{"\u25BC"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(() => {
              const catStats = filteredAnalytics.category_stats || [];
              const rows = (filteredAnalytics.student_progress || []).slice();
              const trendOrder = { improving: 2, steady: 1, declining: 0 };
              rows.sort((a, b) => {
                let av, bv;
                if (studentSortCol === "name") {
                  av = a.name.toLowerCase();
                  bv = b.name.toLowerCase();
                } else if (studentSortCol === "assignments") {
                  av = (a.grades || []).length;
                  bv = (b.grades || []).length;
                } else if (studentSortCol === "average") {
                  av = a.average || 0;
                  bv = b.average || 0;
                } else if (studentSortCol === "trend") {
                  av = trendOrder[a.trend] ?? 1;
                  bv = trendOrder[b.trend] ?? 1;
                } else {
                  const ac = catStats.find((c) => c.name === a.name);
                  const bc = catStats.find((c) => c.name === b.name);
                  av = ac ? (ac[studentSortCol] || 0) : 0;
                  bv = bc ? (bc[studentSortCol] || 0) : 0;
                }
                if (av < bv) return studentSortDir === "asc" ? -1 : 1;
                if (av > bv) return studentSortDir === "asc" ? 1 : -1;
                return 0;
              });
              return rows;
            })().map(
              (s, i) => (
                <tr
                  key={i}
                  onClick={() => onStudentClick(s.name)}
                  style={{
                    cursor: "pointer",
                    background:
                      selectedStudent === s.name
                        ? "rgba(99,102,241,0.2)"
                        : "transparent",
                  }}
                >
                  <td
                    style={{
                      fontWeight: 600,
                      textDecoration: "underline dotted",
                    }}
                  >
                    {s.name}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {(s.grades || []).length}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <span
                      style={{
                        padding: "4px 12px",
                        borderRadius: "20px",
                        fontWeight: 700,
                        background:
                          s.average >= 90
                            ? "rgba(74,222,128,0.2)"
                            : s.average >= 80
                              ? "rgba(96,165,250,0.2)"
                              : s.average >= 70
                                ? "rgba(251,191,36,0.2)"
                                : "rgba(248,113,113,0.2)",
                        color:
                          s.average >= 90
                            ? "#4ade80"
                            : s.average >= 80
                              ? "#60a5fa"
                              : s.average >= 70
                                ? "#fbbf24"
                                : "#f87171",
                      }}
                    >
                      {s.average}%
                    </span>
                  </td>
                  {(() => {
                    const cats = (filteredAnalytics.category_stats || []).find((c) => c.name === s.name);
                    const catKeys = ["content", "completeness", "writing", "effort"];
                    return catKeys.map((key) => {
                      const val = cats ? (cats[key] || 0) : 0;
                      const barColor = val >= 80 ? "#4ade80" : val >= 60 ? "#60a5fa" : val >= 40 ? "#fbbf24" : "#f87171";
                      return (
                        <td key={key} style={{ textAlign: "center", padding: "8px 6px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "4px", justifyContent: "center" }}>
                            <div style={{ width: "40px", height: "6px", background: "rgba(148,163,184,0.15)", borderRadius: "3px", overflow: "hidden" }}>
                              <div style={{ height: "100%", width: Math.min(val, 100) + "%", background: barColor, borderRadius: "3px" }} />
                            </div>
                            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: barColor, minWidth: "28px" }}>{val}%</span>
                          </div>
                        </td>
                      );
                    });
                  })()}
                  <td style={{ textAlign: "center" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        color:
                          s.trend === "improving"
                            ? "#4ade80"
                            : s.trend === "declining"
                              ? "#f87171"
                              : "#94a3b8",
                      }}
                    >
                      <Icon
                        name={
                          s.trend === "improving"
                            ? "TrendingUp"
                            : s.trend === "declining"
                              ? "TrendingDown"
                              : "Minus"
                        }
                        size={16}
                      />
                      {s.trend}
                    </span>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>

  );
});

// StudentPanel — owns selectedStudent state so clicking a student does NOT re-render
// the parent AnalyticsTab (filters, grade charts, etc.)
const StudentPanel = React.memo(function StudentPanel({
  filteredAnalytics, periodStudentMap, sortedPeriods,
  savedAssignments, savedAssignmentData, config, status, addToast, periods,
}) {
  const [selectedStudent, setSelectedStudent] = useState(null);

  const [isPending, startTransition] = useTransition();
  const handleStudentSelect = useCallback((name) => {
    startTransition(() => {
      setSelectedStudent(name);
    });
  }, []);

  const progressChartData = useMemo(() => {
    if (!filteredAnalytics) return { data: [], width: 800 };
    let chartData = [];
    if (selectedStudent) {
      const sd = (filteredAnalytics.student_progress || []).find((s) => s.name === selectedStudent);
      chartData = (sd?.grades || []).slice().sort((a, b) => (a.date || "").localeCompare(b.date || "")).map((g) => ({ assignment: g.assignment, score: g.score, date: g.date }));
    } else {
      const assignmentMap = {};
      const assignmentOrder = [];
      for (const s of filteredAnalytics.student_progress || []) {
        for (const g of s.grades || []) {
          const key = g.assignment || "Unknown";
          if (!assignmentMap[key]) { assignmentMap[key] = { scores: [], date: g.date || "" }; assignmentOrder.push(key); }
          assignmentMap[key].scores.push(g.score);
          if (g.date > assignmentMap[key].date) assignmentMap[key].date = g.date;
        }
      }
      assignmentOrder.sort((a, b) => (assignmentMap[a].date || "").localeCompare(assignmentMap[b].date || ""));
      chartData = assignmentOrder.map((name) => {
        const scores = assignmentMap[name].scores;
        return { assignment: name, score: Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length), count: scores.length, date: assignmentMap[name].date };
      });
    }
    return { data: chartData, width: Math.max(800, chartData.length * 80) };
  }, [selectedStudent, filteredAnalytics]);

  return (
    <>
      {/* Proficiency vs Growth Scatterplot */}
      <ScatterSection
        filteredAnalytics={filteredAnalytics}
        onStudentClick={handleStudentSelect}
      />


      {/* Student Progress */}
      <div
        data-tutorial="analytics-progress"
        className="glass-card"
        style={{
          padding: "25px",
          marginBottom: "20px",
          border: selectedStudent
            ? "2px solid #6366f1"
            : undefined,
          opacity: isPending ? 0.6 : 1,
          transition: "opacity 0.15s ease",
          contentVisibility: "auto",
          containIntrinsicSize: "auto 500px",
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
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <Icon name="TrendingUp" size={20} />
            {selectedStudent
              ? `${selectedStudent}'s Progress`
              : "Student Progress Over Time"}
          </h3>
          {selectedStudent && (
            <button
              onClick={() => setSelectedStudent(null)}
              className="btn btn-secondary"
              style={{ padding: "6px 12px" }}
            >
              <Icon name="X" size={14} /> Clear Selection
            </button>
          )}
        </div>

        {selectedStudent &&
          (() => {
            const studentData = (
              filteredAnalytics.student_progress || []
            ).find((s) => s.name === selectedStudent);
            if (!studentData) return null;
            const grades = studentData.grades || [];
            const highest =
              grades.length > 0
                ? Math.max(...grades.map((g) => g.score))
                : 0;
            const lowest =
              grades.length > 0
                ? Math.min(...grades.map((g) => g.score))
                : 0;
            return (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "15px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    background: "rgba(99,102,241,0.1)",
                    borderRadius: "12px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      marginBottom: "5px",
                    }}
                  >
                    Average
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color: "#6366f1",
                    }}
                  >
                    {studentData.average}%
                  </div>
                </div>
                <div
                  style={{
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "12px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      marginBottom: "5px",
                    }}
                  >
                    Highest
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color: "#4ade80",
                    }}
                  >
                    {highest}%
                  </div>
                </div>
                <div
                  style={{
                    background: "rgba(248,113,113,0.1)",
                    borderRadius: "12px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      marginBottom: "5px",
                    }}
                  >
                    Lowest
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color: "#f87171",
                    }}
                  >
                    {lowest}%
                  </div>
                </div>
                <div
                  style={{
                    background: "rgba(251,191,36,0.1)",
                    borderRadius: "12px",
                    padding: "15px",
                    textAlign: "center",
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      marginBottom: "5px",
                    }}
                  >
                    Assignments
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color: "#fbbf24",
                    }}
                  >
                    {grades.length}
                  </div>
                </div>
              </div>
            );
          })()}

        {selectedStudent &&
          (() => {
            const studentCats = (filteredAnalytics.category_stats || []).find(
              (s) => s.name === selectedStudent,
            );
            if (!studentCats) return null;
            const allCats = filteredAnalytics.category_stats || [];
            const classAvg = {
              content: allCats.length > 0 ? Math.round(allCats.reduce((sum, s) => sum + (s.content || 0), 0) / allCats.length) : 0,
              completeness: allCats.length > 0 ? Math.round(allCats.reduce((sum, s) => sum + (s.completeness || 0), 0) / allCats.length) : 0,
              writing: allCats.length > 0 ? Math.round(allCats.reduce((sum, s) => sum + (s.writing || 0), 0) / allCats.length) : 0,
              effort: allCats.length > 0 ? Math.round(allCats.reduce((sum, s) => sum + (s.effort || 0), 0) / allCats.length) : 0,
            };
            const radarData = [
              { category: "Content", student: studentCats.content || 0, classAvg: classAvg.content },
              { category: "Completeness", student: studentCats.completeness || 0, classAvg: classAvg.completeness },
              { category: "Writing", student: studentCats.writing || 0, classAvg: classAvg.writing },
              { category: "Effort", student: studentCats.effort || 0, classAvg: classAvg.effort },
            ];
            const catDetails = [
              { key: "content", label: "Content Accuracy", icon: "CheckCircle", color: "#6366f1" },
              { key: "completeness", label: "Completeness", icon: "ListChecks", color: "#8b5cf6" },
              { key: "writing", label: "Writing Quality", icon: "PenTool", color: "#a855f7" },
              { key: "effort", label: "Effort & Engagement", icon: "Zap", color: "#c084fc" },
            ];
            return (
              <div style={{ marginBottom: "20px" }}>
                <h4 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Icon name="Target" size={18} />
                  Rubric Performance
                </h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", alignItems: "start" }}>
                  <div style={{ display: "flex", justifyContent: "center" }}>
                    <DeferredMount height={280}>
                      <RadarChart width={380} height={280} data={radarData} cy="45%" outerRadius={90}>
                        <PolarGrid stroke="rgba(148,163,184,0.3)" />
                        <PolarAngleAxis dataKey="category" tick={(props) => {
                          const { x, y, payload } = props;
                          let dx = 0, dy = 0, anchor = "middle";
                          if (payload.value === "Content") dy = -8;
                          if (payload.value === "Writing") dy = 8;
                          if (payload.value === "Effort") { dx = -6; anchor = "end"; }
                          if (payload.value === "Completeness") { dx = 6; anchor = "start"; }
                          return React.createElement("text", { x: x + dx, y: y + dy, textAnchor: anchor, fill: "var(--text-secondary)", fontSize: 12 }, payload.value);
                        }} />
                        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "var(--text-secondary)", fontSize: 10 }} />
                        <Radar name="Student" dataKey="student" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} animationDuration={400} />
                        <Radar name="Class Avg" dataKey="classAvg" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.1} animationDuration={400} />
                        <Legend />
                      </RadarChart>
                    </DeferredMount>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {catDetails.map((cat) => {
                      const score = studentCats[cat.key] || 0;
                      const avg = classAvg[cat.key] || 0;
                      const diff = score - avg;
                      const barColor = score >= 80 ? "#4ade80" : score >= 60 ? "#60a5fa" : score >= 40 ? "#fbbf24" : "#f87171";
                      return (
                        <div key={cat.key} style={{ background: "rgba(255,255,255,0.03)", borderRadius: "10px", padding: "12px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                            <span style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.85rem", fontWeight: 600 }}>
                              <Icon name={cat.icon} size={14} color={cat.color} />
                              {cat.label}
                            </span>
                            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: barColor }}>{score}%</span>
                          </div>
                          <div style={{ height: "6px", background: "rgba(148,163,184,0.15)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{ height: "100%", width: Math.min(score, 100) + "%", background: barColor, borderRadius: "3px", transition: "width 0.5s ease" }} />
                          </div>
                          <div style={{ fontSize: "0.75rem", color: diff >= 0 ? "#4ade80" : "#f87171", marginTop: "4px" }}>
                            {diff >= 0 ? "+" : ""}{parseFloat(diff.toFixed(1))}% vs class avg
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })()}

        {!selectedStudent && (
          <p
            style={{
              fontSize: "0.85rem",
              color: "var(--text-secondary)",
              marginBottom: "15px",
            }}
          >
            Click a student name below to view details
          </p>
        )}

        <div style={{ overflowX: "auto", overflowY: "hidden" }}>
          <DeferredMount height={300}>
          <LineChart
            width={progressChartData.width}
            height={300}
            data={progressChartData.data}
            margin={{ top: 15, bottom: 80, left: 10, right: 30 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" />
            <XAxis
              dataKey="assignment"
              tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={100}
              interval={0}
              tickFormatter={(value) => value && value.length > 25 ? value.substring(0, 25) + "..." : value}
            />
            <YAxis domain={[0, 100]} tick={{ fill: "var(--text-secondary)" }} />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0]?.payload;
                if (!d) return null;
                return (
                  <div style={{ background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "10px 14px", boxShadow: "0 4px 12px rgba(0,0,0,0.15)" }}>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)", marginBottom: "4px" }}>{d.assignment}</div>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span>{selectedStudent ? "Score" : "Class Avg"}: {d.score}%</span>
                      {d.count && <span>Students: {d.count}</span>}
                      {d.date && <span>Date: {d.date}</span>}
                    </div>
                  </div>
                );
              }}
            />
            <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={3} dot={{ fill: "#6366f1", r: 5 }} animationDuration={400} />
          </LineChart>
          </DeferredMount>
        </div>
      </div>


      <StaticSections
        filteredAnalytics={filteredAnalytics}
        periodStudentMap={periodStudentMap}
        sortedPeriods={sortedPeriods}
        savedAssignments={savedAssignments}
        savedAssignmentData={savedAssignmentData}
        config={config}
        status={status}
        addToast={addToast}
        periods={periods}
        onStudentClick={handleStudentSelect}
      />

      <StudentTable
        filteredAnalytics={filteredAnalytics}
        selectedStudent={selectedStudent}
        onStudentClick={handleStudentSelect}
      />
    </>
  );
});


export default React.memo(function AnalyticsTab({
  config,
  status,
  periods,
  sortedPeriods,
  savedAssignments,
  savedAssignmentData,
  addToast,
}) {
  // --- Analytics-specific state ---
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [chartsOverlay, setChartsOverlay] = useState(false);
  const [chartsReady, setChartsReady] = useState(false);
  const [analyticsPeriod, setAnalyticsPeriod] = useState("all");
  const [analyticsClassPeriod, setAnalyticsClassPeriod] = useState("");
  const [analyticsClassStudents, setAnalyticsClassStudents] = useState([]);
  const [periodStudentMap, setPeriodStudentMap] = useState({});


  // --- Effects ---

  // Fetch analytics data (component only mounts when tab is active)
  useEffect(() => {
    setAnalyticsLoading(true);
    setChartsOverlay(false);
    setChartsReady(false);
    api
      .getAnalytics(analyticsPeriod)
      .then((data) => {
        setAnalytics(data);
        // Phase 1: show overlay spinner (no charts yet)
        setChartsOverlay(true);
        setAnalyticsLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setAnalyticsLoading(false);
      });
  }, [analyticsPeriod, status.results.length]);

  // Phase 2: after overlay paints, mount charts underneath
  useEffect(() => {
    if (!chartsOverlay || chartsReady) return;
    // Double rAF ensures the overlay spinner is painted before charts mount
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setChartsReady(true);
      });
    });
    return () => cancelAnimationFrame(id);
  }, [chartsOverlay, chartsReady]);

  // Phase 3: remove overlay after charts render
  useEffect(() => {
    if (!chartsReady) return;
    const timer = setTimeout(() => setChartsOverlay(false), 4000);
    return () => clearTimeout(timer);
  }, [chartsReady]);

  // Load class period students for analytics filtering
  useEffect(() => {
    if (!analyticsClassPeriod) {
      setAnalyticsClassStudents([]);
      return;
    }
    api
      .getPeriodStudents(analyticsClassPeriod)
      .then((data) => {
        if (data.students) setAnalyticsClassStudents(data.students);
      })
      .catch(() => setAnalyticsClassStudents([]));
  }, [analyticsClassPeriod]);

  // Load all period rosters for By-Period distribution view
  useEffect(() => {
    if (periods.length === 0) return;
    Promise.all(
      periods.map((p) =>
        api.getPeriodStudents(p.filename).then((data) => ({ name: p.period_name, students: data.students || [] }))
          .catch(() => ({ name: p.period_name, students: [] }))
      )
    ).then((results) => {
      const map = {};
      results.forEach((r) => { map[r.name] = r.students; });
      setPeriodStudentMap(map);
    });
  }, [periods]);


  // --- Memos ---

  const filteredAnalytics = useMemo(() => {
    if (
      !analytics ||
      !analyticsClassPeriod ||
      analyticsClassStudents.length === 0
    ) {
      return analytics;
    }

    const filteredGrades = (analytics.all_grades || []).filter((g) =>
      studentNameMatchesPeriod(g.student_name, analyticsClassStudents),
    );

    const filteredProgress = (analytics.student_progress || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );

    const scores = filteredGrades.map((g) => g.score);
    const filteredClassStats = {
      total_assignments: filteredGrades.length,
      total_students: filteredProgress.length,
      class_average:
        scores.length > 0
          ? Math.round(
              (scores.reduce((a, b) => a + b, 0) / scores.length) * 10,
            ) / 10
          : 0,
      highest: scores.length > 0 ? Math.max(...scores) : 0,
      lowest: scores.length > 0 ? Math.min(...scores) : 0,
      grade_distribution: {
        A: scores.filter((s) => s >= 90).length,
        B: scores.filter((s) => s >= 80 && s < 90).length,
        C: scores.filter((s) => s >= 70 && s < 80).length,
        D: scores.filter((s) => s >= 60 && s < 70).length,
        F: scores.filter((s) => s < 60).length,
      },
    };

    const filteredAttention = (analytics.attention_needed || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );
    const filteredTop = filteredProgress
      .sort((a, b) => b.average - a.average)
      .slice(0, 5);

    const filteredCostTotal = filteredGrades.reduce((sum, g) => sum + (g.api_cost || 0), 0);
    const filteredCostSummary = analytics.cost_summary ? {
      ...analytics.cost_summary,
      total_cost: Math.round(filteredCostTotal * 10000) / 10000,
      total_tokens: filteredGrades.reduce((sum, g) => sum + (g.input_tokens || 0) + (g.output_tokens || 0), 0),
      total_api_calls: filteredGrades.reduce((sum, g) => sum + (g.api_calls || 0), 0),
      avg_cost_per_student: filteredGrades.length > 0 ? Math.round(filteredCostTotal / filteredGrades.length * 10000) / 10000 : 0,
    } : analytics.cost_summary;

    const filteredCategoryStats = (analytics.category_stats || []).filter((s) =>
      studentNameMatchesPeriod(s.name, analyticsClassStudents),
    );

    return {
      ...analytics,
      all_grades: filteredGrades,
      student_progress: filteredProgress,
      class_stats: filteredClassStats,
      attention_needed: filteredAttention,
      top_performers: filteredTop,
      cost_summary: filteredCostSummary,
      category_stats: filteredCategoryStats,
    };
  }, [analytics, analyticsClassPeriod, analyticsClassStudents]);


  // --- Render ---
  return (
                <div data-tutorial="analytics-card" className="fade-in">
                  {analyticsLoading ? (
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
                      {/* Period Filter */}
                      <div
                        data-tutorial="analytics-filters"
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "20px",
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
                          <Icon name="BarChart3" size={24} />
                          Class Analytics
                        </h2>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "15px",
                          }}
                        >
                          {/* Period Filter */}
                          {sortedPeriods.length > 0 && (
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                              }}
                            >
                              <label
                                style={{
                                  fontSize: "0.9rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                Period:
                              </label>
                              <select
                                value={analyticsClassPeriod}
                                onChange={(e) =>
                                  setAnalyticsClassPeriod(e.target.value)
                                }
                                className="input"
                                style={{ width: "auto" }}
                              >
                                <option value="">All Periods</option>
                                {sortedPeriods.map((p) => (
                                  <option key={p.filename} value={p.filename}>
                                    {p.period_name}
                                  </option>
                                ))}
                              </select>
                            </div>
                          )}
                          {/* Quarter Filter */}
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <label
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              Quarter:
                            </label>
                            <select
                              value={analyticsPeriod}
                              onChange={(e) =>
                                setAnalyticsPeriod(e.target.value)
                              }
                              className="input"
                              style={{ width: "auto" }}
                            >
                              <option value="all">All Quarters</option>
                              {(filteredAnalytics.available_periods || []).map(
                                (p) => (
                                  <option key={p} value={p}>
                                    {p}
                                  </option>
                                ),
                              )}
                            </select>
                          </div>
                          {/* Export District Report Button */}
                          <button
                            className="btn btn-secondary"
                            onClick={async () => {
                              try {
                                const report = await api.exportDistrictReport();
                                if (report.error) {
                                  addToast(report.error, "error");
                                  return;
                                }
                                const blob = new Blob(
                                  [JSON.stringify(report, null, 2)],
                                  { type: "application/json" },
                                );
                                const url = URL.createObjectURL(blob);
                                const a = document.createElement("a");
                                a.href = url;
                                a.download = `district_report_${new Date().toISOString().split("T")[0]}.json`;
                                a.click();
                                URL.revokeObjectURL(url);
                              } catch (err) {
                                addToast(
                                  "Failed to export report: " + err.message,
                                  "error",
                                );
                              }
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                            }}
                          >
                            <Icon name="Download" size={16} />
                            Export District Report
                          </button>
                        </div>
                      </div>

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
