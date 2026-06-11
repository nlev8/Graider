import React, { useState, useRef, useLayoutEffect } from "react";
import {
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
} from "recharts";
import Icon from "../../components/Icon";
import DeferredMount from "./DeferredMount";

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

export default ScatterSection;
