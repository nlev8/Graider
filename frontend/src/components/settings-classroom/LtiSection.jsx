import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function LtiSection(props) {
  const { addToast, ltiPlatforms, ltiShowForm, ltiToolConfig, setLtiPlatforms, setLtiShowForm } = props;
  return (
            <div style={{
              marginTop: "20px", padding: "18px", background: "var(--card-bg)",
              borderRadius: "12px", border: "1px solid var(--glass-border)",
            }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="Shield" size={18} />
                LTI 1.3 Integration
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                Connect Graider to your LMS (Canvas, Schoology, etc.) for single sign-on launches and grade passback. LTI works alongside any roster provider.
              </p>

              {/* Tool Configuration — read-only URLs for LMS admin */}
              {ltiToolConfig && (
                <div style={{
                  marginBottom: "14px", padding: "12px", background: "rgba(99,102,241,0.06)",
                  borderRadius: "8px", border: "1px solid rgba(99,102,241,0.15)",
                }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>
                    Tool Configuration (provide these to your LMS admin)
                  </div>
                  {[
                    { label: "OIDC Login URL", value: ltiToolConfig.oidc_login_url },
                    { label: "Launch URL", value: ltiToolConfig.launch_url },
                    { label: "JWKS URL", value: ltiToolConfig.jwks_url },
                    { label: "Redirect URI", value: ltiToolConfig.redirect_uri },
                  ].map(function(item) {
                    return (
                      <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                        <span style={{ fontSize: "0.78rem", fontWeight: 600, minWidth: "120px", color: "var(--text-secondary)" }}>{item.label}:</span>
                        <span style={{ fontSize: "0.78rem", flex: 1, fontFamily: "monospace", wordBreak: "break-all", color: "var(--text-primary)" }}>{item.value || "—"}</span>
                        <button
                          type="button"
                          onClick={function() {
                            navigator.clipboard.writeText(item.value || '');
                            addToast("Copied " + item.label, "success");
                          }}
                          style={{
                            background: "none", border: "1px solid var(--glass-border)", borderRadius: "6px",
                            padding: "3px 8px", cursor: "pointer", fontSize: "0.72rem", color: "var(--text-secondary)",
                            display: "flex", alignItems: "center", gap: "4px", flexShrink: 0,
                          }}
                        >
                          <Icon name="Copy" size={12} />
                          Copy
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Registered Platforms */}
              {ltiPlatforms.length > 0 && (
                <div style={{ marginBottom: "14px" }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "8px" }}>Registered Platforms</div>
                  <div style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                      <thead>
                        <tr style={{ background: "rgba(99,102,241,0.06)" }}>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Name</th>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Issuer</th>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Client ID</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", fontWeight: 600 }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {ltiPlatforms.map(function(p, idx) {
                          return (
                            <tr key={idx} style={{ borderTop: "1px solid var(--glass-border)" }}>
                              <td style={{ padding: "8px 12px" }}>{p.name || "—"}</td>
                              <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "0.75rem", wordBreak: "break-all" }}>{p.issuer}</td>
                              <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "0.75rem" }}>{p.client_id}</td>
                              <td style={{ padding: "8px 12px", textAlign: "right" }}>
                                <button
                                  type="button"
                                  onClick={function() {
                                    if (window.confirm("Remove platform " + (p.name || p.issuer) + "?")) {
                                      api.deleteLTIPlatform(p.issuer).then(function(result) {
                                        if (result.status === 'ok') {
                                          setLtiPlatforms(function(prev) { return prev.filter(function(x) { return x.issuer !== p.issuer; }); });
                                          addToast("Platform removed", "success");
                                        } else {
                                          addToast(result.error || "Delete failed", "error");
                                        }
                                      }).catch(function(err) {
                                        addToast("Delete failed: " + err.message, "error");
                                      });
                                    }
                                  }}
                                  style={{
                                    background: "none", border: "none", cursor: "pointer",
                                    color: "#ef4444", padding: "4px",
                                  }}
                                >
                                  <Icon name="Trash2" size={14} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Add Platform toggle */}
              {!ltiShowForm && (
                <button
                  type="button"
                  onClick={function() { setLtiShowForm(true); }}
                  style={{
                    background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", borderRadius: "8px",
                    padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem",
                    color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px", fontWeight: 600,
                  }}
                >
                  <Icon name="Plus" size={14} />
                  Add Platform
                </button>
              )}

              {/* Add Platform Form */}
              <LtiAddPlatformForm {...props} />

              {/* Grade Sync to LMS */}
              <LtiGradeSync {...props} />
            </div>
  );
}

function LtiAddPlatformForm({ addToast, ltiNewPlatform, ltiSaving, ltiShowForm, ltiToolConfig, setLtiNewPlatform, setLtiPlatforms, setLtiSaving, setLtiShowForm, setLtiToolConfig }) {
  if (!(ltiShowForm)) return null;
  return (
                <div style={{
                  padding: "14px", background: "rgba(99,102,241,0.04)",
                  borderRadius: "8px", border: "1px solid rgba(99,102,241,0.15)", marginTop: "8px",
                }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "10px" }}>New Platform Registration</div>

                  {/* LMS Preset Buttons */}
                  <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <button
                      type="button"
                      onClick={function() {
                        var issuer = ltiNewPlatform.issuer || '';
                        setLtiNewPlatform(function(prev) {
                          return Object.assign({}, prev, {
                            name: prev.name || 'Canvas',
                            auth_login_url: issuer ? issuer + "/api/lti/authorize_redirect" : prev.auth_login_url,
                            auth_token_url: issuer ? issuer + "/login/oauth2/token" : prev.auth_token_url,
                            jwks_url: issuer ? issuer + "/api/lti/security/jwks" : prev.jwks_url,
                          });
                        });
                        if (!issuer) addToast("Enter the Issuer URL first, then click Canvas again to auto-fill URLs", "info");
                      }}
                      style={{
                        background: "rgba(239,108,0,0.1)", border: "1px solid rgba(239,108,0,0.3)", borderRadius: "6px",
                        padding: "5px 12px", cursor: "pointer", fontSize: "0.78rem", color: "#ef6c00", fontWeight: 600,
                      }}
                    >
                      Canvas
                    </button>
                    <button
                      type="button"
                      onClick={function() {
                        setLtiNewPlatform(function(prev) {
                          return Object.assign({}, prev, {
                            name: prev.name || 'Schoology',
                            auth_login_url: "https://lti.schoology.com/lti/authorize",
                            auth_token_url: "https://lti.schoology.com/lti/token",
                            jwks_url: "https://lti.schoology.com/lti/.well-known/jwks",
                          });
                        });
                      }}
                      style={{
                        background: "rgba(33,150,243,0.1)", border: "1px solid rgba(33,150,243,0.3)", borderRadius: "6px",
                        padding: "5px 12px", cursor: "pointer", fontSize: "0.78rem", color: "#2196f3", fontWeight: 600,
                      }}
                    >
                      Schoology
                    </button>
                  </div>

                  <div style={{ display: "grid", gap: "8px" }}>
                    <input
                      type="text" placeholder="Platform Name (e.g. Canvas, Schoology)"
                      value={ltiNewPlatform.name}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { name: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Issuer URL (required)" required
                      value={ltiNewPlatform.issuer}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { issuer: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Client ID (required)" required
                      value={ltiNewPlatform.client_id}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { client_id: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Authorization URL (required)" required
                      value={ltiNewPlatform.auth_login_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { auth_login_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Token URL (required)" required
                      value={ltiNewPlatform.auth_token_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { auth_token_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="JWKS URL (required)" required
                      value={ltiNewPlatform.jwks_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { jwks_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Deployment IDs (comma-separated, optional)"
                      value={ltiNewPlatform.deployment_ids}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { deployment_ids: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                    <button
                      type="button"
                      disabled={ltiSaving || !ltiNewPlatform.issuer || !ltiNewPlatform.client_id || !ltiNewPlatform.auth_login_url || !ltiNewPlatform.auth_token_url || !ltiNewPlatform.jwks_url}
                      onClick={async function() {
                        setLtiSaving(true);
                        try {
                          var payload = Object.assign({}, ltiNewPlatform, {
                            deployment_ids: ltiNewPlatform.deployment_ids.split(',').map(function(s) { return s.trim(); }).filter(Boolean),
                          });
                          var result = await api.registerLTIPlatform(payload);
                          if (result.status === 'ok') {
                            setLtiPlatforms(result.platforms || []);
                            setLtiToolConfig(result.tool_config || ltiToolConfig);
                            setLtiNewPlatform({ name: '', issuer: '', client_id: '', auth_login_url: '', auth_token_url: '', jwks_url: '', deployment_ids: '' });
                            setLtiShowForm(false);
                            addToast("Platform registered", "success");
                          } else {
                            addToast(result.error || "Registration failed", "error");
                          }
                        } catch (err) {
                          addToast("Registration failed: " + err.message, "error");
                        }
                        setLtiSaving(false);
                      }}
                      style={{
                        background: "var(--accent)", color: "white", border: "none", borderRadius: "8px",
                        padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", fontWeight: 600,
                        opacity: (ltiSaving || !ltiNewPlatform.issuer || !ltiNewPlatform.client_id) ? 0.5 : 1,
                      }}
                    >
                      {ltiSaving ? "Saving..." : "Register Platform"}
                    </button>
                    <button
                      type="button"
                      onClick={function() {
                        setLtiShowForm(false);
                        setLtiNewPlatform({ name: '', issuer: '', client_id: '', auth_login_url: '', auth_token_url: '', jwks_url: '', deployment_ids: '' });
                      }}
                      style={{
                        background: "none", border: "1px solid var(--glass-border)", borderRadius: "8px",
                        padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", color: "var(--text-secondary)",
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
  );
}

function LtiGradeSync({ addToast, ltiContexts, ltiSelectedContext, ltiSyncLabel, ltiSyncMaxScore, ltiSyncResult, ltiSyncScores, ltiSyncing, setLtiSelectedContext, setLtiSyncLabel, setLtiSyncMaxScore, setLtiSyncResult, setLtiSyncScores, setLtiSyncing }) {
  return (
              <div style={{ marginTop: "18px", borderTop: "1px solid var(--glass-border)", paddingTop: "14px" }}>
                <h4 style={{ fontSize: "0.92rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Icon name="Upload" size={16} />
                  Grade Sync to LMS
                </h4>

                {ltiContexts.length === 0 ? (
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                    Launch Graider from your LMS to enable grade sync. No LTI course contexts are available yet.
                  </p>
                ) : (
                  <div>
                    {/* Context selector */}
                    <div style={{ marginBottom: "10px" }}>
                      <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Course</label>
                      <select
                        value={ltiSelectedContext ? ltiSelectedContext.context_id : ''}
                        onChange={function(e) {
                          var ctx = ltiContexts.find(function(c) { return c.context_id === e.target.value; });
                          setLtiSelectedContext(ctx || null);
                          setLtiSyncResult(null);
                          if (ctx && ctx.students) {
                            setLtiSyncScores(ctx.students.map(function(s) { return { student_name: s.name || s.user_id, score: '' }; }));
                          } else {
                            setLtiSyncScores([]);
                          }
                        }}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                      >
                        <option value="">Select a course...</option>
                        {ltiContexts.map(function(ctx) {
                          return (
                            <option key={ctx.context_id} value={ctx.context_id}>
                              {ctx.context_title + " (" + (ctx.student_count || 0) + " students)"}
                            </option>
                          );
                        })}
                      </select>
                    </div>

                    {/* Score entry area — shown when context selected */}
                    {ltiSelectedContext && (
                      <div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "10px" }}>
                          <div>
                            <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Gradebook Column Name</label>
                            <input
                              type="text" placeholder="e.g. Chapter 5 Quiz"
                              value={ltiSyncLabel}
                              onChange={function(e) { setLtiSyncLabel(e.target.value); }}
                              style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Max Score</label>
                            <input
                              type="number" min="1" value={ltiSyncMaxScore}
                              onChange={function(e) { setLtiSyncMaxScore(parseInt(e.target.value) || 100); }}
                              style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                            />
                          </div>
                        </div>

                        {/* Student scores */}
                        {ltiSyncScores.length > 0 && (
                          <div style={{ marginBottom: "10px" }}>
                            <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>Student Scores</div>
                            <div style={{ maxHeight: "200px", overflowY: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
                              {ltiSyncScores.map(function(entry, idx) {
                                return (
                                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 10px", borderBottom: idx < ltiSyncScores.length - 1 ? "1px solid var(--glass-border)" : "none" }}>
                                    <span style={{ flex: 1, fontSize: "0.82rem" }}>{entry.student_name}</span>
                                    <input
                                      type="number" min="0" placeholder="Score"
                                      value={entry.score}
                                      onChange={function(e) {
                                        var val = e.target.value;
                                        setLtiSyncScores(function(prev) {
                                          var updated = prev.slice();
                                          updated[idx] = Object.assign({}, updated[idx], { score: val });
                                          return updated;
                                        });
                                      }}
                                      style={{ width: "80px", padding: "4px 8px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.82rem", textAlign: "right" }}
                                    />
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Sync button */}
                        <button
                          type="button"
                          disabled={ltiSyncing || !ltiSyncLabel}
                          onClick={async function() {
                            setLtiSyncing(true);
                            setLtiSyncResult(null);
                            try {
                              var scoresToSend = ltiSyncScores.filter(function(s) { return s.score !== '' && s.score !== null; }).map(function(s) { return { student_name: s.student_name, score: parseFloat(s.score) }; });
                              var result = await api.syncLTIGrades({
                                platform_issuer: ltiSelectedContext.platform_issuer,
                                context_id: ltiSelectedContext.context_id,
                                label: ltiSyncLabel,
                                max_score: ltiSyncMaxScore,
                                scores: scoresToSend,
                              });
                              setLtiSyncResult(result);
                              if (result.status === 'ok') {
                                addToast((result.synced || 0) + " scores synced to LMS", "success");
                              } else {
                                addToast(result.error || "Sync failed", "error");
                              }
                            } catch (err) {
                              addToast("Sync failed: " + err.message, "error");
                            }
                            setLtiSyncing(false);
                          }}
                          style={{
                            background: "var(--accent)", color: "white", border: "none", borderRadius: "8px",
                            padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", fontWeight: 600,
                            opacity: (ltiSyncing || !ltiSyncLabel) ? 0.5 : 1,
                            display: "flex", alignItems: "center", gap: "6px",
                          }}
                        >
                          <Icon name="Upload" size={14} />
                          {ltiSyncing ? "Syncing..." : "Sync Grades"}
                        </button>

                        {/* Sync result */}
                        {ltiSyncResult && ltiSyncResult.status === 'ok' && (
                          <div style={{ marginTop: "10px", padding: "10px", background: "rgba(34,197,94,0.08)", borderRadius: "8px", border: "1px solid rgba(34,197,94,0.2)" }}>
                            <div style={{ fontSize: "0.82rem", color: "#22c55e", fontWeight: 600 }}>
                              {(ltiSyncResult.synced || 0) + "/" + (ltiSyncResult.total || 0) + " scores synced successfully"}
                            </div>
                            {ltiSyncResult.unmatched_students && ltiSyncResult.unmatched_students.length > 0 && (
                              <div style={{ marginTop: "6px", padding: "8px", background: "rgba(234,179,8,0.08)", borderRadius: "6px", border: "1px solid rgba(234,179,8,0.2)" }}>
                                <div style={{ fontSize: "0.78rem", color: "#eab308", fontWeight: 600, marginBottom: "4px" }}>Unmatched Students</div>
                                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                                  {ltiSyncResult.unmatched_students.join(", ")}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
  );
}
