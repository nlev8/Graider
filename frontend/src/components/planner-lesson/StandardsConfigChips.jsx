import React from "react";
import Icon from "../Icon";

export default function StandardsConfigChips({ config }) {
  return (
    <div
      style={{
        display: "flex",
        gap: "10px",
        marginBottom: "15px",
        flexWrap: "wrap",
      }}
    >
      <span
        style={{
          padding: "6px 12px",
          borderRadius: "20px",
          background: "rgba(99,102,241,0.15)",
          color: "var(--accent-light)",
          fontSize: "0.85rem",
          fontWeight: 500,
        }}
      >
        <Icon
          name="MapPin"
          size={14}
          style={{
            marginRight: "6px",
            verticalAlign: "middle",
          }}
        />
        {{
          FL: "Florida",
          TX: "Texas",
          CA: "California",
          NY: "New York",
          GA: "Georgia",
          NC: "North Carolina",
          VA: "Virginia",
          OH: "Ohio",
          PA: "Pennsylvania",
          IL: "Illinois",
        }[config.state] || config.state}
      </span>
      <span
        style={{
          padding: "6px 12px",
          borderRadius: "20px",
          background: "rgba(74,222,128,0.15)",
          color: "#4ade80",
          fontSize: "0.85rem",
          fontWeight: 500,
        }}
      >
        <Icon
          name="GraduationCap"
          size={14}
          style={{
            marginRight: "6px",
            verticalAlign: "middle",
          }}
        />
        Grade {config.grade_level}
      </span>
      <span
        style={{
          padding: "6px 12px",
          borderRadius: "20px",
          background: "rgba(251,191,36,0.15)",
          color: "#fbbf24",
          fontSize: "0.85rem",
          fontWeight: 500,
        }}
      >
        <Icon
          name="BookOpen"
          size={14}
          style={{
            marginRight: "6px",
            verticalAlign: "middle",
          }}
        />
        {config.subject}
      </span>
    </div>
  );
}
