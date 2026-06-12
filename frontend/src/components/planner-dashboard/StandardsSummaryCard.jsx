import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (Standards
// Summary card inside the submissions detail panel). The original inline
// `{selectedAssessmentResults && ...submissions.length > 0 && (() => {...})()}`
// IIFE becomes this component; its guard chain and `codes.length === 0`
// early-out are preserved byte-for-byte as early returns (house pattern).
export default function StandardsSummaryCard({ selectedAssessmentResults }) {
  if (!(selectedAssessmentResults && selectedAssessmentResults.submissions && selectedAssessmentResults.submissions.length > 0)) return null;
  var byStandard = {};
  selectedAssessmentResults.submissions.forEach(function(sub) {
    var mastery = sub.results && sub.results.standards_mastery;
    if (!mastery) return;
    Object.keys(mastery).forEach(function(code) {
      var m = mastery[code];
      // Phase 4.3 Sprint 2 — backend may emit either old flat shape or
      // new {overall, by_dok} shape (only Student Report Card route emits
      // by_dok in its response; the rest preserve flat — but defend at
      // every read site).
      var ov = (m && m.overall) ? m.overall : (m || {});
      if (!byStandard[code]) byStandard[code] = { earned: 0, possible: 0, question_count: ov.question_count };
      byStandard[code].earned += ov.points_earned || 0;
      byStandard[code].possible += ov.points_possible || 0;
    });
  });
  var codes = Object.keys(byStandard);
  if (codes.length === 0) return null;
  return (
                                <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                                    <Icon name="Target" size={16} />
                                    Standards in this Assessment ({codes.length})
                                  </h4>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                                    {codes.map(function(code) {
                                      var s = byStandard[code];
                                      var pct = s.possible > 0 ? Math.round((s.earned / s.possible) * 100) : 0;
                                      var barColor = pct >= 80 ? "var(--success)" : pct >= 60 ? "var(--warning)" : "var(--danger)";
                                      return (
                                        <div key={code} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 12px", borderRadius: "8px", background: "var(--glass-bg)" }}>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, fontFamily: "monospace", minWidth: "100px" }}>{code}</div>
                                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", minWidth: "70px" }}>{s.question_count} Q{s.question_count === 1 ? '' : 's'}</div>
                                          <div style={{ flex: 1, height: "6px", background: "var(--glass-bg)", borderRadius: "3px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                                            <div style={{ width: pct + "%", height: "100%", background: barColor, transition: "width 0.3s" }} />
                                          </div>
                                          <div style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: "50px", textAlign: "right" }}>{pct}%</div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
  );
}
