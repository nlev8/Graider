import React, { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import * as api from "../services/api";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: String.fromCharCode(8212) };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

function formatDate(iso) {
  if (!iso) return String.fromCharCode(8212);
  try {
    var d = new Date(iso);
    return (d.getMonth() + 1) + "/" + d.getDate();
  } catch (e) {
    return String.fromCharCode(8212);
  }
}

export default function StudentReportCard({ classId, studentId, attemptMode, onClose }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [expandedStandard, setExpandedStandard] = useState(null);

  useEffect(function() {
    if (!classId || !studentId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getStudentReportCard(classId, studentId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res || res.error) {
          setError((res && res.error) || 'Failed to load report card');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        setError((e && e.message) || 'Failed to load report card');
      })
      .finally(function() {
        if (!cancelled) setLoading(false);
      });
    return function() { cancelled = true; };
  }, [classId, studentId, attemptMode]);

  // Drawer (z-index 9500, BELOW cell popover at 9999)
  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        zIndex: 9500, display: "flex", justifyContent: "flex-end",
      }}
      onClick={onClose}
    >
      {/* Backdrop */}
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.4)" }} />

      {/* Drawer panel */}
      <div
        className="glass-card"
        style={{
          position: "relative", width: "min(600px, 100vw)", height: "100%",
          background: "var(--card-bg)", borderLeft: "1px solid var(--glass-border)",
          boxShadow: "-4px 0 20px rgba(0,0,0,0.2)", padding: "24px",
          overflowY: "auto",
        }}
        onClick={function(e) { e.stopPropagation(); }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{data ? data.student_name : 'Student'}</h3>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              {data ? data.class_name : ''} {String.fromCharCode(8226)} attempt mode: {attemptMode || 'latest'}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.4rem" }}
          >
            {String.fromCharCode(10005)}
          </button>
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: "60px" }}>
            <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading...</p>
          </div>
        )}

        {error && (
          <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>{error}</div>
        )}

        {data && !loading && !error && (
          <div>
            {/* Trajectory chart */}
            <div style={{ marginBottom: "24px" }}>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Mastery trajectory</h4>
              {data.trajectory.length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  This student hasn{String.fromCharCode(8217)}t submitted anything in this class yet.
                </p>
              ) : (
                <div style={{ width: "100%", height: "200px" }}>
                  <ResponsiveContainer>
                    <LineChart data={data.trajectory.map(function(t) {
                      return {
                        name: formatDate(t.submitted_at),
                        percentage: t.percentage,
                        title: t.title,
                        attempt_number: t.attempt_number,
                      };
                    })}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={function(val, _key, ctx) {
                          var p = ctx && ctx.payload || {};
                          return [val + '%', p.title + ' (attempt ' + p.attempt_number + ')'];
                        }}
                      />
                      <ReferenceLine y={70} stroke="var(--warning)" strokeDasharray="3 3" />
                      <ReferenceLine y={85} stroke="var(--success)" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="percentage" stroke="var(--accent-primary)" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Standards breakdown */}
            <div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>Standards (worst first)</h4>
              {data.standards_breakdown.length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>No graded standards yet.</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {data.standards_breakdown.map(function(s) {
                    var color = masteryColor(s.percentage);
                    var isExpanded = expandedStandard === s.code;
                    return (
                      <div key={s.code} style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "10px 12px", background: color.bg }}>
                        <div
                          onClick={function() { setExpandedStandard(isExpanded ? null : s.code); }}
                          style={{ display: "flex", justifyContent: "space-between", cursor: "pointer", alignItems: "center" }}
                        >
                          <div>
                            <div style={{ fontFamily: "monospace", fontSize: "0.85rem", fontWeight: 700, color: color.text }}>
                              {s.code}
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                              {s.points_earned}/{s.points_possible} pts {String.fromCharCode(8226)} {s.question_count} questions
                            </div>
                          </div>
                          <div style={{ fontWeight: 700, color: color.text, fontSize: "1rem" }}>{color.label}</div>
                        </div>
                        {isExpanded && (
                          <div style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px solid var(--glass-border)", display: "flex", flexDirection: "column", gap: "6px" }}>
                            {s.contributing_submissions.map(function(c, i) {
                              return (
                                <div key={i} style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                                  <strong style={{ color: "var(--text-primary)" }}>{c.title}</strong>
                                  {' '}{String.fromCharCode(8212)}{' '}
                                  {c.points_earned}/{c.points_possible} pts ({c.percentage}%)
                                  {' '}{String.fromCharCode(8226)}{' '}
                                  attempt {c.attempt_number} {String.fromCharCode(8226)} {formatDate(c.submitted_at)}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
