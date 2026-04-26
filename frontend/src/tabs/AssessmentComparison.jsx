import React, { useState, useEffect } from "react";
import * as api from "../services/api";

function gradeColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

// Custom SVG box plot — recharts has no native box plot.
// This is a FIVE-NUMBER-SUMMARY plot (min/Q1/median/Q3/max). No outlier treatment;
// whiskers extend to absolute min/max (NOT 1.5×IQR fences). If outlier display is
// ever requested by teachers, port the IQR-fence math from
// frontend/src/components/InteractiveBoxPlot.jsx (which is the input widget — never
// modify or import it from here; this read-only component owns its own math).
function BoxPlotRow({ assessments }) {
  var width = Math.max(600, assessments.length * 110);
  var height = 200;
  var pad = { top: 16, right: 24, bottom: 40, left: 48 };
  var plotH = height - pad.top - pad.bottom;
  var boxW = 60;
  var slotW = (width - pad.left - pad.right) / Math.max(assessments.length, 1);

  function yFor(pct) {
    return pad.top + plotH - (pct / 100) * plotH;
  }

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {/* Y axis ticks at 0, 25, 50, 70, 85, 100 */}
      {[0, 25, 50, 70, 85, 100].map(function(t) {
        var y = yFor(t);
        var stroke = (t === 70 || t === 85) ? (t === 85 ? "var(--success)" : "var(--warning)") : "var(--glass-border)";
        var dash = (t === 70 || t === 85) ? "3 3" : undefined;
        return (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke={stroke} strokeDasharray={dash} />
            <text x={pad.left - 8} y={y + 4} fontSize="10" textAnchor="end" fill="var(--text-secondary)">{t}</text>
          </g>
        );
      })}
      {/* Box per assessment */}
      {assessments.map(function(a, i) {
        if (a.n === 0) {
          return (
            <g key={a.content_id}>
              <text x={pad.left + slotW * i + slotW / 2} y={yFor(50)} fontSize="11" textAnchor="middle" fill="var(--text-muted)">no data</text>
              <text x={pad.left + slotW * i + slotW / 2} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">{a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}</text>
            </g>
          );
        }
        var color = gradeColor(a.mean);
        var cx = pad.left + slotW * i + slotW / 2;
        var x0 = cx - boxW / 2;
        var yMin = yFor(a.min);
        var yMax = yFor(a.max);
        var yQ1 = yFor(a.q1);
        var yQ3 = yFor(a.q3);
        var yMed = yFor(a.median);
        return (
          <g key={a.content_id}>
            {/* Whiskers */}
            <line x1={cx} x2={cx} y1={yMin} y2={yQ1} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx} x2={cx} y1={yQ3} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMin} y2={yMin} stroke={color.text} strokeWidth="1.5" />
            <line x1={cx - 12} x2={cx + 12} y1={yMax} y2={yMax} stroke={color.text} strokeWidth="1.5" />
            {/* Box */}
            <rect x={x0} y={yQ3} width={boxW} height={Math.max(yQ1 - yQ3, 1)} fill={color.bg} stroke={color.text} strokeWidth="1.5" />
            {/* Median line */}
            <line x1={x0} x2={x0 + boxW} y1={yMed} y2={yMed} stroke={color.text} strokeWidth="2" />
            {/* X-axis label */}
            <text x={cx} y={height - pad.bottom + 16} fontSize="10" textAnchor="middle" fill="var(--text-secondary)">
              {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
            </text>
            <title>{a.title + ": median " + a.median + "%, IQR " + a.q1 + "-" + a.q3 + ", n=" + a.n}</title>
          </g>
        );
      })}
    </svg>
  );
}

export default function AssessmentComparison({ classId }) {
  var [available, setAvailable] = useState([]);
  var [bootstrapLoading, setBootstrapLoading] = useState(true);
  var [bootstrapError, setBootstrapError] = useState(null);
  var [selectedContentIds, setSelectedContentIds] = useState([]);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(false);
  var [error, setError] = useState(null);
  var [searchQuery, setSearchQuery] = useState('');

  // Bootstrap: fetch the list of class assessments via the gradebook endpoint.
  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setBootstrapLoading(true);
    setBootstrapError(null);
    setSelectedContentIds([]);
    setData(null);
    api.getClassGradebook(classId, 'latest')
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setBootstrapError((res && res.error) || 'Failed to load assessments');
          setAvailable([]);
        } else {
          // Gradebook returns both assessments and assignments. The compare endpoint
          // also enforces content_type='assessment' as a 403 guard, but we filter
          // client-side so non-assessments never appear in the picker.
          // (If the gradebook response omits content_type on a row, fall through —
          // the backend guard will catch it.)
          var assessmentsOnly = (res.assessments || []).filter(function(a) {
            return !a.content_type || a.content_type === 'assessment';
          });
          setAvailable(assessmentsOnly);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setBootstrapError((e && e.message) || 'Failed to load assessments');
      })
      .finally(function() { if (!cancelled) setBootstrapLoading(false); });
    return function() { cancelled = true; };
  }, [classId]);

  // Comparison fetch when selection is valid.
  useEffect(function() {
    if (selectedContentIds.length < 2 || selectedContentIds.length > 6) {
      setData(null);
      return;
    }
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassAssessmentComparison(classId, selectedContentIds, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load comparison');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load comparison');
      })
      .finally(function() { if (!cancelled) setLoading(false); });
    return function() { cancelled = true; };
  }, [classId, selectedContentIds, attemptMode]);

  function toggleSelection(contentId) {
    if (selectedContentIds.indexOf(contentId) >= 0) {
      setSelectedContentIds(selectedContentIds.filter(function(id) { return id !== contentId; }));
    } else if (selectedContentIds.length < 6) {
      setSelectedContentIds(selectedContentIds.concat([contentId]));
    }
  }

  var btnStyle = function(active) {
    return {
      padding: "6px 14px", borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
    };
  };

  if (bootstrapLoading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--text-secondary)" }}>Loading assessments...</p>
      </div>
    );
  }
  if (bootstrapError) {
    return <div className="glass-card" style={{ padding: "40px", color: "var(--danger)", textAlign: "center" }}>{bootstrapError}</div>;
  }

  var filteredAvailable = available.filter(function(a) {
    return !searchQuery || a.title.toLowerCase().indexOf(searchQuery.toLowerCase()) >= 0;
  });

  var orderedSelected = selectedContentIds.map(function(cid) {
    return available.find(function(a) { return a.content_id === cid; });
  }).filter(Boolean);

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Compare Assessments
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {selectedContentIds.length} of 6 selected {String.fromCharCode(8226)} pick 2-6 assessments
      </p>

      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
      </div>

      {/* Picker */}
      {available.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
          No assessments published to this class yet.
        </p>
      ) : (
        <div style={{ marginBottom: "20px" }}>
          <input
            type="text"
            value={searchQuery}
            onChange={function(e) { setSearchQuery(e.target.value); }}
            placeholder="Search assessments..."
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
      )}

      {/* Comparison output */}
      {selectedContentIds.length < 2 ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>
          Pick at least 2 assessments to compare.
        </p>
      ) : loading ? (
        <p style={{ color: "var(--text-secondary)", padding: "20px", textAlign: "center" }}>Loading comparison...</p>
      ) : error ? (
        <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>{error}</div>
      ) : data ? (
        <div>
          {/* Stat cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px", marginBottom: "20px" }}>
            {data.assessments.map(function(a) {
              var color = gradeColor(a.n > 0 ? a.mean : null);
              var ratePct = Math.round((a.submission_rate || 0) * 100);
              return (
                <div key={a.content_id} style={{ padding: "12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: color.bg }}>
                  <div style={{ fontSize: "0.85rem", fontWeight: 700, color: color.text, marginBottom: "4px" }}>{a.title}</div>
                  {a.n > 0 ? (
                    <div style={{ fontSize: "1.4rem", fontWeight: 700, color: color.text }}>
                      {a.mean}%
                    </div>
                  ) : (
                    <div style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-muted)" }}>
                      No submissions yet
                    </div>
                  )}
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                    {a.n} of {data.class_roster_size} {String.fromCharCode(8226)} {ratePct}% submitted
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    Max points: {a.max_points}
                    {a.n > 0 ? " " + String.fromCharCode(8226) + " median " + a.median + "%" : ""}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Box plot row */}
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Score distribution</h4>
          <div style={{ overflowX: "auto", marginBottom: "20px", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "8px" }}>
            <BoxPlotRow assessments={orderedSelected.map(function(o) {
              return data.assessments.find(function(a) { return a.content_id === o.content_id; }) || o;
            })} />
          </div>

          {/* Standards heatmap */}
          <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Standards coverage</h4>
          {data.standards_matrix.standards.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              No standards-tagged questions on these assessments.
            </p>
          ) : (
            <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "10px 14px", textAlign: "left", fontSize: "0.75rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)" }}>Standard</th>
                    {orderedSelected.map(function(a) {
                      return (
                        <th key={a.content_id} style={{ padding: "10px 8px", fontSize: "0.7rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "100px", textAlign: "center" }}>
                          {a.title.length > 12 ? a.title.slice(0, 11) + String.fromCharCode(8230) : a.title}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {data.standards_matrix.standards.map(function(code) {
                    return (
                      <tr key={code}>
                        <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", padding: "8px 14px", fontFamily: "monospace", fontSize: "0.75rem", borderBottom: "1px solid var(--glass-border)" }}>{code}</td>
                        {orderedSelected.map(function(a) {
                          var cell = (data.standards_matrix.cells[a.content_id] || {})[code];
                          var color = gradeColor(cell ? cell.percentage : null);
                          return (
                            <td key={a.content_id} title={cell ? code + " on " + a.title + ": " + cell.percentage + "% (" + cell.students_assessed + " students)" : "Not covered"}
                                style={{ padding: "8px", textAlign: "center", borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", background: color.bg, color: color.text, fontSize: "0.75rem", fontWeight: 600 }}>
                              {color.label}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
