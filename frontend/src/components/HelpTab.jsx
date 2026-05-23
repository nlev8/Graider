import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import DOMPurify from "dompurify";

export default function HelpTab({ activeTab, setShowTutorial, setTutorialStep }) {
  const [helpManual, setHelpManual] = useState("");
  const [helpSearch, setHelpSearch] = useState("");
  const [helpExpanded, setHelpExpanded] = useState({});

  // Verbatim from App.jsx load effect; dep array [activeTab] preserved exactly (do NOT add helpManual).
  useEffect(() => {
    if (activeTab === "help" && !helpManual) {
      fetch("/api/user-manual")
        .then(r => r.json())
        .then(data => { if (data.content) setHelpManual(data.content); })
        .catch(() => {});
    }
  }, [activeTab]);

  if (activeTab !== "help") return null;

  return (
                <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                  {/* Tutorial Replay Card */}
                  <div className="glass-card" style={{
                    padding: "24px",
                    background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08))",
                    border: "1px solid rgba(99,102,241,0.25)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
                      <div>
                        <h3 style={{ margin: "0 0 4px", fontSize: "1.1rem", color: "var(--text-primary)" }}>
                          <Icon name="PlayCircle" size={18} style={{ marginRight: 8, verticalAlign: "middle", color: "var(--accent)" }} />
                          Interactive Tutorial
                        </h3>
                        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          Walk through all 37 steps to learn every feature in Graider
                        </p>
                      </div>
                      <button
                        className="btn btn-primary"
                        onClick={() => { setTutorialStep(0); setShowTutorial(true); }}
                        style={{ padding: "10px 24px", fontWeight: 600, fontSize: "0.9rem" }}
                      >
                        <Icon name="PlayCircle" size={16} style={{ marginRight: 6 }} />
                        Replay Tutorial
                      </button>
                    </div>
                  </div>

                  {/* Report a Bug Card */}
                  <div className="glass-card" style={{
                    padding: "24px",
                    background: "linear-gradient(135deg, rgba(239,68,68,0.08), rgba(245,158,11,0.06))",
                    border: "1px solid rgba(239,68,68,0.2)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
                      <div>
                        <h3 style={{ margin: "0 0 4px", fontSize: "1.1rem", color: "var(--text-primary)" }}>
                          <Icon name="Bug" size={18} style={{ marginRight: 8, verticalAlign: "middle", color: "#ef4444" }} />
                          Found a Bug?
                        </h3>
                        <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          Help us improve Graider by reporting issues, unexpected behavior, or suggestions
                        </p>
                      </div>
                      <a
                        href="https://docs.google.com/forms/d/e/1FAIpQLSc0dD7mZYUrQNxzYqHeA299Ms_NNXrH2cSaRUv1qXiYmMkBFw/viewform"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary"
                        style={{ padding: "10px 24px", fontWeight: 600, fontSize: "0.9rem", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}
                      >
                        <Icon name="ExternalLink" size={16} />
                        Report Bug
                      </a>
                    </div>
                  </div>

                  {/* Search Bar */}
                  <div style={{ position: "relative" }}>
                    <Icon name="Search" size={16} style={{
                      position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)",
                      color: "var(--text-muted)", pointerEvents: "none",
                    }} />
                    <input
                      type="text"
                      placeholder="Search the user manual..."
                      value={helpSearch}
                      onChange={e => {
                        const q = e.target.value;
                        setHelpSearch(q);
                        if (q.trim()) {
                          // Auto-expand matching sections
                          const expanded = {};
                          helpManual.split(/^## /m).slice(1).forEach((sec, i) => {
                            if (sec.toLowerCase().includes(q.toLowerCase())) expanded[i] = true;
                          });
                          setHelpExpanded(expanded);
                        } else {
                          setHelpExpanded({});
                        }
                      }}
                      style={{
                        width: "100%", padding: "12px 16px 12px 40px",
                        borderRadius: "12px", border: "1px solid var(--glass-border)",
                        background: "var(--glass-bg)", color: "var(--text-primary)",
                        fontSize: "0.9rem", outline: "none", boxSizing: "border-box",
                      }}
                    />
                    {helpSearch && (
                      <button onClick={() => { setHelpSearch(""); setHelpExpanded({}); }} style={{
                        position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                        background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4,
                      }}>
                        <Icon name="X" size={14} />
                      </button>
                    )}
                  </div>

                  {/* Manual Sections */}
                  {!helpManual ? (
                    <div className="glass-card" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
                      <Icon name="Loader" size={20} style={{ animation: "spin 1s linear infinite", marginBottom: 8 }} />
                      <div>Loading user manual...</div>
                    </div>
                  ) : (() => {
                    const sections = helpManual.split(/^## /m).slice(1).map((raw, i) => {
                      const nlIdx = raw.indexOf("\n");
                      return { title: raw.substring(0, nlIdx).trim(), body: raw.substring(nlIdx + 1).trim(), index: i };
                    });
                    const query = helpSearch.trim().toLowerCase();
                    const filtered = query
                      ? sections.filter(s => s.title.toLowerCase().includes(query) || s.body.toLowerCase().includes(query))
                      : sections;
                    if (filtered.length === 0) {
                      return (
                        <div className="glass-card" style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)" }}>
                          <Icon name="SearchX" size={24} style={{ marginBottom: 8, opacity: 0.5 }} />
                          <div>No sections match "{helpSearch}"</div>
                        </div>
                      );
                    }
                    return filtered.map(sec => {
                      const isOpen = !!helpExpanded[sec.index];
                      return (
                        <div key={sec.index} className="glass-card" style={{ padding: 0, overflow: "hidden" }}>
                          <div
                            onClick={() => setHelpExpanded(prev => ({ ...prev, [sec.index]: !prev[sec.index] }))}
                            style={{
                              display: "flex", alignItems: "center", justifyContent: "space-between",
                              padding: "14px 20px", cursor: "pointer", userSelect: "none",
                            }}
                          >
                            <span style={{ fontWeight: 600, fontSize: "0.95rem", color: "var(--text-primary)" }}>{sec.title}</span>
                            <Icon name={isOpen ? "ChevronDown" : "ChevronRight"} size={16} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                          </div>
                          {isOpen && (
                            <div style={{
                              padding: "0 20px 18px",
                              fontSize: "0.88rem",
                              lineHeight: 1.7,
                              color: "var(--text-secondary)",
                              borderTop: "1px solid var(--glass-border)",
                              paddingTop: "14px",
                            }}>
                              <div dangerouslySetInnerHTML={{ __html: (() => {
                                let html = sec.body;
                                // Code blocks
                                html = html.replace(/```[\s\S]*?```/g, m => {
                                  const inner = m.slice(3, -3).replace(/^\w+\n/, "");
                                  return '<pre style="background:rgba(0,0,0,0.2);padding:12px;border-radius:8px;overflow-x:auto;font-size:0.82em;margin:8px 0"><code>' + inner.replace(/</g, "&lt;").replace(/>/g, "&gt;") + '</code></pre>';
                                });
                                // Sub-sub headings
                                html = html.replace(/^#### (.+)$/gm, '<h5 style="margin:12px 0 4px;font-size:0.9em;color:var(--text-primary)">$1</h5>');
                                // Sub headings
                                html = html.replace(/^### (.+)$/gm, '<h4 style="margin:14px 0 6px;font-size:0.95em;color:var(--text-primary)">$1</h4>');
                                // Bold
                                html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                                // Italic
                                html = html.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
                                // Inline code
                                html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(99,102,241,0.15);padding:2px 6px;border-radius:4px;font-size:0.85em">$1</code>');
                                // Links
                                html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--accent-light);text-decoration:underline">$1</a>');
                                // Unordered lists
                                html = html.replace(/^[-*] (.+)$/gm, '<li style="margin-left:16px;list-style:disc">$1</li>');
                                // Ordered lists
                                html = html.replace(/^\d+\. (.+)$/gm, '<li style="margin-left:16px;list-style:decimal">$1</li>');
                                // Paragraphs
                                html = html.replace(/\n\n/g, '<br/><br/>');
                                html = html.replace(/\n/g, '<br/>');
                                return DOMPurify.sanitize(html);
                              })() }} />
                            </div>
                          )}
                        </div>
                      );
                    });
                  })()}
                </div>
  );
}
