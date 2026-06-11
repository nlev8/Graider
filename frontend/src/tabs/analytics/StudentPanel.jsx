import React, { useState, useCallback, useMemo, useTransition } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from "recharts";
import Icon from "../../components/Icon";
import DeferredMount from "./DeferredMount";
import ScatterSection from "./ScatterSection";
import StaticSections from "./StaticSections";
import StudentTable from "./StudentTable";

// Selected-student stat cards — verbatim from the first selectedStudent IIFE
// in StudentPanel (CQ wave 1 split). Plain component: renders whenever
// StudentPanel renders with a selected student, exactly as before.
function SelectedStudentStats({ filteredAnalytics, selectedStudent }) {
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
}

// Rubric Performance radar + category bars — verbatim from the second
// selectedStudent IIFE in StudentPanel (CQ wave 1 split).
function RubricPerformance({ filteredAnalytics, selectedStudent }) {
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
}

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

        {selectedStudent && (
          <SelectedStudentStats
            filteredAnalytics={filteredAnalytics}
            selectedStudent={selectedStudent}
          />
        )}

        {selectedStudent && (
          <RubricPerformance
            filteredAnalytics={filteredAnalytics}
            selectedStudent={selectedStudent}
          />
        )}

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

export default StudentPanel;
