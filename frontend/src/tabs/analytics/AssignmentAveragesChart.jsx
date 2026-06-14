import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import Icon from "../../components/Icon";
import DeferredMount from "./DeferredMount";

// Assignment Averages chart card — extracted from GradeChartsSection (CQ wave 2 split).
// Pure-prop child: reads only containerRef, chartWidth, assignmentStats. No state/effects.
function AssignmentAveragesChart({ containerRef, chartWidth, assignmentStats }) {
  return (
    <div ref={containerRef} className="glass-card" style={{ padding: "25px", minWidth: 0, overflow: "hidden" }}>
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
        {chartWidth > 0 && (<BarChart
          width={chartWidth}
          height={200}
          data={assignmentStats || []}
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
  );
}

export default AssignmentAveragesChart;
