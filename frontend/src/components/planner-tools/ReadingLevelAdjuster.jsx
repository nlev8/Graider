import React, { useState } from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

/*
 * Reading Level Adjuster card, relocated verbatim from PlannerTools.jsx
 * (CQ wave-5 split). The rl* useState block moved with the card; the card
 * is unconditionally mounted by the always-mounted PlannerTools shell, so
 * state lifetime is unchanged. Prop names match the original identifiers
 * so the JSX is byte-identical.
 */
export default function ReadingLevelAdjuster({ config, addToast }) {
  const [rlInput, setRlInput] = useState('');
  const [rlTargetLevel, setRlTargetLevel] = useState('6');
  const [rlPreserveTerms, setRlPreserveTerms] = useState([]);
  const [rlTermInput, setRlTermInput] = useState('');
  const [rlLoading, setRlLoading] = useState(false);
  const [rlResult, setRlResult] = useState(null);
  const [rlExtracting, setRlExtracting] = useState(false);
  const [rlFiles, setRlFiles] = useState([]);

  return (
                      <div className="glass-card" style={{ padding: "24px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="BookOpen" size={22} style={{ color: "#06b6d4" }} />
                          Reading Level Adjuster
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Upload documents or screenshots, or paste text directly. Adjust to a target reading level while preserving key terms.
                        </p>
                        <div style={{ marginBottom: "12px" }}>
                          <div
                            onDragOver={function(e) { e.preventDefault(); e.currentTarget.style.borderColor = '#06b6d4'; }}
                            onDragLeave={function(e) { e.currentTarget.style.borderColor = 'var(--input-border)'; }}
                            onDrop={async function(e) {
                              e.preventDefault();
                              e.currentTarget.style.borderColor = 'var(--input-border)';
                              var files = Array.from(e.dataTransfer.files);
                              if (files.length === 0) return;
                              setRlExtracting(true);
                              for (var i = 0; i < files.length; i++) {
                                try {
                                  var res = await api.extractTextFromFile(files[i]);
                                  if (res.error) { addToast(files[i].name + ': ' + res.error, 'error'); }
                                  else { setRlInput(function(prev) { return prev ? prev + '\n\n' + res.text : res.text; }); setRlFiles(function(prev) { return prev.concat([files[i].name]); }); }
                                } catch (err) { addToast('Failed to extract text from ' + files[i].name, 'error'); }
                              }
                              setRlExtracting(false);
                            }}
                            style={{ border: "2px dashed var(--input-border)", borderRadius: "8px", padding: "16px", textAlign: "center", cursor: "pointer", transition: "border-color 0.2s" }}
                            onClick={function() { document.getElementById('rl-file-input').click(); }}
                          >
                            <input
                              id="rl-file-input"
                              type="file"
                              accept=".docx,.pdf,.txt,.png,.jpg,.jpeg,.gif,.webp"
                              multiple
                              style={{ display: "none" }}
                              onChange={async function(e) {
                                var files = Array.from(e.target.files);
                                if (files.length === 0) return;
                                setRlExtracting(true);
                                for (var i = 0; i < files.length; i++) {
                                  try {
                                    var res = await api.extractTextFromFile(files[i]);
                                    if (res.error) { addToast(files[i].name + ': ' + res.error, 'error'); }
                                    else { setRlInput(function(prev) { return prev ? prev + '\n\n' + res.text : res.text; }); setRlFiles(function(prev) { return prev.concat([files[i].name]); }); }
                                  } catch (err) { addToast('Failed to extract text from ' + files[i].name, 'error'); }
                                }
                                setRlExtracting(false);
                                e.target.value = '';
                              }}
                            />
                            {rlExtracting ? (
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", color: "#06b6d4" }}>
                                <Icon name="Loader2" size={18} className="spinning" /> Extracting text...
                              </div>
                            ) : (
                              <div>
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                                  <Icon name="Upload" size={16} />
                                  <span>Drop files here or click to upload</span>
                                </div>
                                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px", opacity: 0.7 }}>
                                  Documents (.docx, .pdf, .txt) or screenshots (.png, .jpg)
                                </div>
                              </div>
                            )}
                          </div>
                          {rlFiles.length > 0 && (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                              {rlFiles.map(function(name, i) {
                                return (
                                  <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "rgba(6,182,212,0.1)", color: "#06b6d4", borderRadius: "6px", fontSize: "0.75rem" }}>
                                    <Icon name="FileText" size={12} /> {name}
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                        <textarea
                          value={rlInput}
                          onChange={function(e) { setRlInput(e.target.value); }}
                          placeholder="Paste text here or upload documents/screenshots above..."
                          rows={8}
                          style={{ width: "100%", padding: "12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem", resize: "vertical", marginBottom: "16px", fontFamily: "inherit" }}
                        />
                        <div style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap", marginBottom: "16px" }}>
                          <div style={{ flex: "0 0 auto" }}>
                            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Target Level</label>
                            <select
                              value={rlTargetLevel}
                              onChange={e => setRlTargetLevel(e.target.value)}
                              style={{ padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                            >
                              <option value="2">Grade 2</option>
                              <option value="3">Grade 3</option>
                              <option value="4">Grade 4</option>
                              <option value="5">Grade 5</option>
                              <option value="6">Grade 6</option>
                              <option value="7">Grade 7</option>
                              <option value="8">Grade 8</option>
                              <option value="9">Grade 9</option>
                              <option value="10">Grade 10</option>
                              <option value="11">Grade 11</option>
                              <option value="12">Grade 12</option>
                              <option value="Simplified">Simplified</option>
                              <option value="Advanced/AP">Advanced / AP</option>
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: "200px" }}>
                            <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Key Terms to Preserve</label>
                            <div style={{ display: "flex", gap: "6px" }}>
                              <input
                                type="text"
                                value={rlTermInput}
                                onChange={e => setRlTermInput(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter' && rlTermInput.trim()) {
                                    e.preventDefault()
                                    setRlPreserveTerms(prev => prev.indexOf(rlTermInput.trim()) === -1 ? prev.concat([rlTermInput.trim()]) : prev)
                                    setRlTermInput('')
                                  }
                                }}
                                placeholder="Type term and press Enter"
                                style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                              />
                            </div>
                          </div>
                          <button
                            onClick={async () => {
                              if (!rlInput.trim()) return
                              setRlLoading(true)
                              setRlResult(null)
                              try {
                                var res = await api.adjustReadingLevel(rlInput, rlTargetLevel, config.subject || '', rlPreserveTerms)
                                if (res.error) {
                                  addToast(res.error, 'error')
                                } else {
                                  setRlResult(res)
                                }
                              } catch (err) {
                                addToast('Error: ' + err.message, 'error')
                              } finally {
                                setRlLoading(false)
                              }
                            }}
                            className="btn btn-primary"
                            disabled={!rlInput.trim() || rlLoading}
                            style={{ padding: "8px 20px", background: "linear-gradient(135deg, #06b6d4, #0891b2)" }}
                          >
                            {rlLoading ? (
                              <><Icon name="Loader2" size={16} className="spin" /> Adjusting...</>
                            ) : (
                              <><Icon name="Wand2" size={16} /> Adjust</>
                            )}
                          </button>
                        </div>
                        {rlPreserveTerms.length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "16px" }}>
                            {rlPreserveTerms.map(function(term, i) {
                              return (
                                <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "3px 10px", background: "rgba(6,182,212,0.12)", color: "#06b6d4", borderRadius: "12px", fontSize: "0.8rem", fontWeight: 500 }}>
                                  {term}
                                  <button
                                    onClick={() => setRlPreserveTerms(prev => prev.filter(function(t) { return t !== term }))}
                                    style={{ background: "none", border: "none", color: "#06b6d4", cursor: "pointer", padding: "0 2px", fontSize: "1rem", lineHeight: 1 }}
                                  >
                                    x
                                  </button>
                                </span>
                              )
                            })}
                          </div>
                        )}
                        {rlResult && (
                          <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "16px", marginTop: "8px" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                              <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                                Estimated reading level: <span style={{ color: "#06b6d4", fontWeight: 700 }}>{rlResult.reading_level_estimate}</span>
                              </span>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(rlResult.adjusted_text)
                                  addToast('Copied to clipboard', 'success')
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "4px 12px", fontSize: "0.8rem" }}
                              >
                                <Icon name="Copy" size={14} /> Copy
                              </button>
                            </div>
                            <div style={{ padding: "12px", background: "var(--input-bg)", borderRadius: "8px", fontSize: "0.9rem", lineHeight: 1.6, color: "var(--text-primary)", whiteSpace: "pre-wrap", maxHeight: "300px", overflowY: "auto", marginBottom: "12px" }}>
                              {rlResult.adjusted_text}
                            </div>
                            {rlResult.vocabulary_changes && rlResult.vocabulary_changes.length > 0 && (
                              <div>
                                <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px" }}>Vocabulary Changes</h4>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 16px", fontSize: "0.8rem" }}>
                                  {rlResult.vocabulary_changes.map(function(vc, i) {
                                    return (
                                      <React.Fragment key={i}>
                                        <span style={{ color: "var(--text-secondary)", textDecoration: "line-through" }}>{vc.original}</span>
                                        <span style={{ color: "#06b6d4", fontWeight: 500 }}>{vc.replacement}</span>
                                      </React.Fragment>
                                    )
                                  })}
                                </div>
                              </div>
                            )}
                            {rlResult.usage && (
                              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "12px", textAlign: "right" }}>
                                {rlResult.usage.cost_display}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
  );
}
