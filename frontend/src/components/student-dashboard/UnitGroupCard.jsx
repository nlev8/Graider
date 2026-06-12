import React from "react";

// ============ UNIT GROUP CARD ============
// JSX (and the render-scoped isExpanded/displayName/counts/allGraded/
// isMostRecent locals, plus the statusColors lookup table) moved verbatim
// from the sortedUnits.map callback in StudentDashboard.jsx (CQ wave-7
// split). State (expandedUnits, selectedResource, flippedCards) and the
// fetch wiring (openContent, token) stay in the always-mounted
// StudentDashboard shell and are threaded through as props.
export default function UnitGroupCard(props) {
  const {
    unitName, unitIdx, group,
    expandedUnits, setExpandedUnits,
    openContent, token,
    setSelectedResource, setFlippedCards,
  } = props;

  const statusColors = {
    not_started: { bg: "var(--btn-secondary-bg)", text: "var(--text-secondary)", label: "Not Started" },
    in_progress: { bg: "var(--warning-bg)", text: "var(--warning)", label: "In Progress" },
    submitted: { bg: "rgba(59,130,246,0.2)", text: "var(--info)", label: "Submitted" },
    graded: { bg: "var(--success-bg)", text: "var(--success)", label: "Graded" },
    returned: { bg: "rgba(168,85,247,0.2)", text: "var(--accent-light)", label: "Returned" },
  };

  var isExpanded = expandedUnits[unitName] || false;
  var displayName = unitName || 'General';
  var assignmentCount = group.assignments.length;
  var resourceCount = group.resources.length;
  var allGraded = assignmentCount > 0 && group.assignments.every(function(a) { return a.status === 'graded'; });
  var isMostRecent = unitIdx === 0 && unitName;

  return (
    <div style={{ borderRadius: "12px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
      <div
        onClick={function() {
          setExpandedUnits(function(prev) {
            var next = Object.assign({}, prev);
            next[unitName] = !prev[unitName];
            return next;
          });
        }}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 18px", cursor: "pointer",
          background: isExpanded ? "rgba(99,102,241,0.06)" : "var(--card-bg)",
          transition: "background 0.15s",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "1rem", transition: "transform 0.2s", display: "inline-block", transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)" }}>
            {String.fromCharCode(9654)}
          </span>
          <div>
            <div style={{ fontSize: "1rem", fontWeight: 700 }}>{displayName}</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
              {assignmentCount > 0 ? assignmentCount + ' assignment' + (assignmentCount === 1 ? '' : 's') : ''}
              {assignmentCount > 0 && resourceCount > 0 ? ' ' + String.fromCharCode(183) + ' ' : ''}
              {resourceCount > 0 ? resourceCount + ' study material' + (resourceCount === 1 ? '' : 's') : ''}
              {allGraded ? ' ' + String.fromCharCode(183) + ' All graded ' + String.fromCharCode(10003) : ''}
            </div>
          </div>
        </div>
        {isMostRecent && (
          <span style={{ fontSize: "0.7rem", padding: "3px 10px", background: "rgba(99,102,241,0.12)", borderRadius: "10px", color: "var(--accent-primary)", fontWeight: 600 }}>
            Current
          </span>
        )}
      </div>

      {isExpanded && (
        <div style={{ padding: "16px 18px", background: "var(--card-bg-light)" }}>
          {assignmentCount > 0 && (
            <div style={{ marginBottom: resourceCount > 0 ? "16px" : "0" }}>
              <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "8px" }}>
                Assignments
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                {group.assignments.map(function(item) {
                  var st = statusColors[item.status] || statusColors.not_started;
                  var isClickable = item.status !== 'graded';
                  return (
                    <div
                      key={item.content_id}
                      onClick={function() { if (isClickable) openContent(item); }}
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "10px 14px", borderRadius: "8px",
                        background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                        cursor: isClickable ? "pointer" : "default",
                        transition: "border-color 0.2s",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{item.title}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                          {item.content_type === 'assessment' ? 'Assessment' : 'Assignment'}
                          {item.due_date ? ' ' + String.fromCharCode(8226) + ' Due ' + new Date(item.due_date).toLocaleDateString() : ''}
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <span style={{
                          padding: "3px 10px", borderRadius: "16px", fontSize: "0.7rem",
                          fontWeight: 600, background: st.bg, color: st.text,
                        }}>
                          {st.label}
                        </span>
                        {item.score != null && (
                          <div style={{ fontSize: "0.85rem", fontWeight: 600, marginTop: "4px" }}>
                            {item.percentage != null ? Math.round(item.percentage) + '%' : item.score}
                            {item.letter_grade ? ' (' + item.letter_grade + ')' : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {resourceCount > 0 && (
            <div>
              <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: "8px" }}>
                Study Materials
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "8px" }}>
                {group.resources.map(function(res) {
                  var icon = res.content_type === 'study_guide' ? String.fromCharCode(128214)
                    : res.content_type === 'flashcards' ? String.fromCharCode(128196)
                    : res.content_type === 'slide_deck' ? String.fromCharCode(128253)
                    : String.fromCharCode(128196);
                  var typeLabel = res.content_type === 'study_guide' ? 'Study Guide'
                    : res.content_type === 'flashcards' ? 'Flashcards'
                    : res.content_type === 'slide_deck' ? 'Slide Deck'
                    : res.content_type;
                  return (
                    <div
                      key={res.id}
                      onClick={function() {
                        if (res._fromDashboard) {
                          fetch('/api/student/content/' + res.content_id, {
                            headers: { 'X-Student-Token': token }
                          })
                            .then(function(r) { return r.json(); })
                            .then(function(data) {
                              if (data.content) {
                                setSelectedResource({ id: res.content_id, title: res.title, content_type: res.content_type, content: data.content });
                                setFlippedCards({});
                              }
                            })
                            .catch(function() {});
                        } else {
                          fetch('/api/student/resource/' + res.id, {
                            headers: { 'X-Student-Token': token }
                          })
                            .then(function(r) { return r.json(); })
                            .then(function(data) {
                              if (data.resource) {
                                setSelectedResource(data.resource);
                                setFlippedCards({});
                              }
                            })
                            .catch(function() {});
                        }
                      }}
                      style={{
                        padding: "12px 14px", borderRadius: "8px",
                        background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                        cursor: "pointer", transition: "transform 0.1s",
                      }}
                    >
                      <div style={{ fontSize: "1.3rem", marginBottom: "4px" }}>{icon}</div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{res.title}</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: "2px" }}>{typeLabel}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
