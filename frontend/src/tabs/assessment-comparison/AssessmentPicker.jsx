import React from "react";

// Assessment picker (search box + selectable chips) for the Compare
// Assessments tab (CQ wave-8 split). Stateless; selection + search state
// lives in the always-mounted shell. The per-render search filter moved
// here with the JSX that consumes it — it was a plain inline computation
// (no memoization), and stays one.
export default function AssessmentPicker({
  available, searchQuery, setSearchQuery, selectedContentIds, toggleSelection,
}) {
  if (available.length === 0) {
    return (
      <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
        No assessments published to this class yet.
      </p>
    );
  }

  var filteredAvailable = available.filter(function(a) {
    return !searchQuery || a.title.toLowerCase().indexOf(searchQuery.toLowerCase()) >= 0;
  });

  return (
    <div style={{ marginBottom: "20px" }}>
      <input
        type="text"
        value={searchQuery}
        onChange={function(e) { setSearchQuery(e.target.value); }}
        placeholder="Search assessments..."
        aria-label="Search assessments"
        className="input"
        style={{ width: "100%", maxWidth: "400px", marginBottom: "10px" }}
      />
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {filteredAvailable.map(function(a) {
          var isSelected = selectedContentIds.indexOf(a.content_id) >= 0;
          var atCap = !isSelected && selectedContentIds.length >= 6;
          return (
            <button
              key={a.content_id}
              onClick={function() { toggleSelection(a.content_id); }}
              disabled={atCap}
              style={{
                padding: "6px 12px", borderRadius: "16px",
                border: "1px solid " + (isSelected ? "var(--accent-primary)" : "var(--glass-border)"),
                background: isSelected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
                color: isSelected ? "var(--accent-primary)" : (atCap ? "var(--text-muted)" : "var(--text-primary)"),
                fontSize: "0.8rem", fontWeight: 500,
                cursor: atCap ? "not-allowed" : "pointer",
                opacity: atCap ? 0.5 : 1,
              }}
              title={atCap ? "Maximum 6 assessments" : a.title}
            >
              {a.title}
            </button>
          );
        })}
      </div>
    </div>
  );
}
