import React from "react";
import Icon from "../Icon";

export default function GlobalInstructionsSection(props) {
  const { globalAINotes, setGlobalAINotes } = props;
  return (
            <div>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="MessageSquare" size={20} style={{ color: "#6366f1" }} />
                Global AI Instructions
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                These instructions apply to both grading AND assessment generation. Include differentiation rules for periods here.
              </p>
              <textarea
                className="input"
                value={globalAINotes}
                onChange={(e) => setGlobalAINotes(e.target.value)}
                placeholder="Example: For assessment generation, Periods 1,2,5 are advanced (7th-8th grade level). Periods 4,6,7 should be 6th grade level only."
                style={{ minHeight: "120px", resize: "vertical" }}
              />
            </div>
  );
}
