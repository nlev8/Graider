import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (global tag
// filter bar — Content Tagging). Stateless.
export default function TagFilterBar({ allTeacherTags, selectedTagFilter, setSelectedTagFilter }) {
  return (
                      <div className="glass-card" style={{ padding: "12px 16px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <Icon name="Tag" size={16} style={{ color: "var(--text-secondary)" }} />
                        <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Filter by tag:</label>
                        <select
                          value={selectedTagFilter}
                          onChange={function(e) { setSelectedTagFilter(e.target.value); }}
                          className="input"
                          style={{ padding: "6px 12px", fontSize: "0.85rem", minWidth: "220px" }}
                        >
                          <option value="all">All content ({allTeacherTags.length} tags)</option>
                          {allTeacherTags.map(function(t) {
                            return <option key={t} value={t}>{t}</option>;
                          })}
                        </select>
                        {selectedTagFilter !== 'all' && (
                          <button
                            onClick={function() { setSelectedTagFilter('all'); }}
                            className="btn btn-secondary"
                            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                          >
                            Clear
                          </button>
                        )}
                      </div>
  );
}
