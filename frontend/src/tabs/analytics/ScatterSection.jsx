import React, { useState, useRef, useLayoutEffect } from "react";
import Icon from "../../components/Icon";
import DeferredMount from "./DeferredMount";
import ScatterProficiencyChart from "./ScatterProficiencyChart";

// Memoized scatter chart — skips re-render when only selectedStudent changes.
// The recharts <ScatterChart> body is extracted into ScatterProficiencyChart
// (CQ wave-3/4 split, pure-prop); this wrapper keeps the width-measurement
// state/ref and the card chrome.
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
        {scatterWidth > 0 && (
          <ScatterProficiencyChart
            filteredAnalytics={filteredAnalytics}
            scatterWidth={scatterWidth}
            onStudentClick={onStudentClick}
          />
        )}
      </DeferredMount>
    </div>
  );
});

export default ScatterSection;
