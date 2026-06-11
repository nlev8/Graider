import React, { useState, useRef, useLayoutEffect, useMemo } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import Icon from "../../components/Icon";
import DeferredMount from "./DeferredMount";
import { studentNameMatchesPeriod } from "./helpers";

// Stats cards row — moved verbatim out of GradeChartsSection (CQ wave 1 split).
// Plain (non-memo) component: it was inline JSX before, so it still renders
// exactly when GradeChartsSection renders.
function StatsCards({ filteredAnalytics }) {
  return (
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
  );
}

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
    const measure = () => {
      if (distRef.current) setDistWidth(distRef.current.clientWidth - 50);
      if (avgRef.current) setAvgWidth(avgRef.current.clientWidth - 50);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
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
    <StatsCards filteredAnalytics={filteredAnalytics} />

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
      <div ref={distRef} className="glass-card" style={{ padding: "25px", minWidth: 0, overflow: "hidden" }}>
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

      <div ref={avgRef} className="glass-card" style={{ padding: "25px", minWidth: 0, overflow: "hidden" }}>
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

export default GradeChartsSection;
