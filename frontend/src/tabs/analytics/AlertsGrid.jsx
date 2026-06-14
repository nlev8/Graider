import React from "react";
import Icon from "../../components/Icon";

/**
 * AlertsGrid — extracted from StaticSections (CQ wave-3 split, #cq8-04).
 * Renders the side-by-side "Needs Attention" + "Top Performers" cards.
 *
 * Pure-prop component: no state, effects, or fetches. All data flows in
 * from StaticSections via props.
 */
export default function AlertsGrid({ filteredAnalytics, onStudentClick }) {
  return (
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
        {(filteredAnalytics.attention_needed || []).length === 0 ? (
          <p style={{ color: "var(--text-secondary)" }}>
            All students are doing well!
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
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
                  <span style={{ textDecoration: "underline dotted" }}>
                    {s.name}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span style={{ color: "#f87171", fontWeight: 700 }}>
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
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {(filteredAnalytics.top_performers || []).map((s, i) => (
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
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
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
                <span style={{ textDecoration: "underline dotted" }}>
                  {s.name}
                </span>
              </div>
              <span style={{ color: "#4ade80", fontWeight: 700 }}>
                {s.average}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
