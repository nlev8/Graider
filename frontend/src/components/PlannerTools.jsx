import React, { useState } from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function PlannerTools({ config, lessonPlan, generatedAssignment, globalAINotes, uploadedDocs, addToast, shareWithClass }) {
  // Study guide
  const [studyGuide, setStudyGuide] = useState(null);
  const [studyGuideGenerating, setStudyGuideGenerating] = useState(false);
  const [studyGuideInstructions, setStudyGuideInstructions] = useState('');
  // Flashcards
  const [flashcards, setFlashcards] = useState(null);
  const [flashcardsGenerating, setFlashcardsGenerating] = useState(false);
  const [flashcardInstructions, setFlashcardInstructions] = useState('');
  const [flashcardCount, setFlashcardCount] = useState(15);
  // Slide deck
  const [slideDeck, setSlideDeck] = useState(null);
  const [slideDeckGenerating, setSlideDeckGenerating] = useState(false);
  const [slideDeckInstructions, setSlideDeckInstructions] = useState('');
  const [slideResources, setSlideResources] = useState([]);
  const [slideResourceList, setSlideResourceList] = useState([]);
  const [slideResourcesLoading, setSlideResourcesLoading] = useState(false);
  const [slideCount, setSlideCount] = useState(10);
  const [slideImages, setSlideImages] = useState(true);
  const [slideFormat, setSlideFormat] = useState('detailed');
  // Reading level
  const [rlInput, setRlInput] = useState('');
  const [rlTargetLevel, setRlTargetLevel] = useState('6');
  const [rlPreserveTerms, setRlPreserveTerms] = useState([]);
  const [rlTermInput, setRlTermInput] = useState('');
  const [rlLoading, setRlLoading] = useState(false);
  const [rlResult, setRlResult] = useState(null);
  const [rlExtracting, setRlExtracting] = useState(false);
  const [rlFiles, setRlFiles] = useState([]);

  return (
                    <div className="fade-in">
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

                      {/* Study Guide Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="BookOpen" size={22} style={{ color: "#06b6d4" }} />
                          Study Guide Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate a study guide from your lesson plan or pasted content. Includes key concepts, vocabulary, review questions, and summary.
                        </p>

                        <div style={{ marginBottom: "12px" }}>
                          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                            Custom Instructions (optional)
                          </label>
                          <textarea
                            value={studyGuideInstructions}
                            onChange={(e) => setStudyGuideInstructions(e.target.value)}
                            placeholder="e.g., Focus on vocabulary from Chapter 5, include diagram descriptions, emphasize lab safety..."
                            style={{ width: "100%", minHeight: "60px", padding: "10px", borderRadius: "8px", border: "1px solid var(--input-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem", resize: "vertical" }}
                          />
                        </div>

                        <button
                          onClick={async () => {
                            setStudyGuideGenerating(true);
                            setStudyGuide(null);
                            try {
                              var content = '';
                              var nl = String.fromCharCode(10);
                              if (lessonPlan && lessonPlan.overview) {
                                content = lessonPlan.overview + nl + (lessonPlan.days || []).map(function(d) { return 'Day ' + d.day + ': ' + d.topic; }).join(nl);
                              }
                              if (generatedAssignment) {
                                var sections = generatedAssignment.sections || generatedAssignment.questions || [];
                                content += nl + sections.map(function(s) {
                                  if (s.questions) return s.name + ': ' + s.questions.map(function(q) { return q.question; }).join(', ');
                                  return s.question || '';
                                }).join(nl);
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan or assessment first, or use the Reading Level Adjuster to paste content.', 'warning');
                                setStudyGuideGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-study-guide', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : generatedAssignment && generatedAssignment.title ? generatedAssignment.title : 'Study Guide') + ' - Study Guide',
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  globalAINotes: config.globalAINotes || '',
                                  instructions: studyGuideInstructions,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setStudyGuide(data.study_guide);
                                addToast('Study guide generated!', 'success');
                                // Auto-save to resources
                                api.saveResource(data.study_guide, 'study_guide', data.title || 'Study Guide');
                              }
                            } catch (err) {
                              addToast('Failed to generate study guide: ' + err.message, 'error');
                            }
                            setStudyGuideGenerating(false);
                          }}
                          disabled={studyGuideGenerating || (!lessonPlan && !generatedAssignment)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #06b6d4, #0891b2)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {studyGuideGenerating ? (
                            <><Icon name="Loader" size={16} className="spinning" /> Generating...</>
                          ) : (
                            <><Icon name="BookOpen" size={16} /> Generate Study Guide</>
                          )}
                        </button>

                        {studyGuide && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {studyGuide.title || 'Study Guide'}
                            </h4>

                            {(studyGuide.sections || []).map(function(section, si) {
                              return (
                                <div key={si} style={{ marginBottom: "16px" }}>
                                  <h5 style={{ fontSize: "0.95rem", fontWeight: 600, color: "#06b6d4", marginBottom: "8px" }}>
                                    {section.heading}
                                  </h5>
                                  {section.content && section.content.map(function(point, pi) {
                                    return <p key={pi} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}>{String.fromCharCode(8226)} {point}</p>;
                                  })}
                                  {section.terms && section.terms.map(function(item, ti) {
                                    return <p key={ti} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}><strong>{item.term}:</strong> {item.definition}</p>;
                                  })}
                                  {section.questions && section.questions.map(function(qa, qi) {
                                    return (
                                      <div key={qi} style={{ marginBottom: "8px", paddingLeft: "12px" }}>
                                        <p style={{ fontSize: "0.85rem", fontWeight: 600 }}>{qi + 1}. {qa.question}</p>
                                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", paddingLeft: "16px" }}>Answer: {qa.answer}</p>
                                      </div>
                                    );
                                  })}
                                </div>
                              );
                            })}

                            <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                              <button
                                onClick={async () => {
                                  try {
                                    var resp = await fetch('/api/export-study-guide', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ study_guide: studyGuide, format: 'docx' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (studyGuide.title || 'Study Guide') + '.docx';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileText" size={16} /> Export DOCX
                              </button>
                              <button
                                onClick={async () => {
                                  try {
                                    var resp = await fetch('/api/export-study-guide', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ study_guide: studyGuide, format: 'pdf' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (studyGuide.title || 'Study Guide') + '.pdf';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileDown" size={16} /> Export PDF
                              </button>
                              <button
                                onClick={function() { shareWithClass(studyGuide, 'study_guide', studyGuide.title || 'Study Guide'); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="Share2" size={16} /> Share with Class
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Flashcard Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Layers" size={22} style={{ color: "#f59e0b" }} />
                          Flashcard Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate printable flashcards from your lesson plan or content. Terms on front, definitions on back.
                        </p>

                        <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
                          <div style={{ flex: 1 }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                              Number of cards
                            </label>
                            <select
                              value={flashcardCount}
                              onChange={function(e) { setFlashcardCount(parseInt(e.target.value)); }}
                              className="input"
                              style={{ maxWidth: "120px" }}
                            >
                              <option value={10}>10</option>
                              <option value={15}>15</option>
                              <option value={20}>20</option>
                              <option value={25}>25</option>
                              <option value={30}>30</option>
                            </select>
                          </div>
                          <div style={{ flex: 2 }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>
                              Custom Instructions (optional)
                            </label>
                            <input
                              type="text"
                              value={flashcardInstructions}
                              onChange={function(e) { setFlashcardInstructions(e.target.value); }}
                              placeholder="e.g., Focus on Chapter 5 vocabulary only"
                              className="input"
                            />
                          </div>
                        </div>

                        <button
                          onClick={async function() {
                            setFlashcardsGenerating(true);
                            setFlashcards(null);
                            try {
                              var content = '';
                              if (lessonPlan && lessonPlan.overview) {
                                content = lessonPlan.overview + String.fromCharCode(10) + (lessonPlan.days || []).map(function(d) { return 'Day ' + d.day + ': ' + d.topic; }).join(String.fromCharCode(10));
                              }
                              if (generatedAssignment) {
                                var sections = generatedAssignment.sections || generatedAssignment.questions || [];
                                content += String.fromCharCode(10) + sections.map(function(s) {
                                  if (s.questions) return s.name + ': ' + s.questions.map(function(q) { return q.question; }).join(', ');
                                  return s.question || '';
                                }).join(String.fromCharCode(10));
                              }
                              if (!content.trim() && uploadedDocs.length > 0) {
                                content = uploadedDocs.map(function(doc) { return doc.filename + ':' + String.fromCharCode(10) + doc.text; }).join(String.fromCharCode(10) + String.fromCharCode(10));
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan, assessment, or upload resources first.', 'warning');
                                setFlashcardsGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-flashcards', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : generatedAssignment && generatedAssignment.title ? generatedAssignment.title : 'Flashcards') + ' - Flashcards',
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  globalAINotes: config.globalAINotes || '',
                                  instructions: flashcardInstructions,
                                  cardCount: flashcardCount,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setFlashcards(data.flashcards);
                                addToast('Flashcards generated!', 'success');
                                api.saveResource(data.flashcards, 'flashcards', data.title || 'Flashcards');
                              }
                            } catch (err) {
                              addToast('Failed to generate flashcards: ' + err.message, 'error');
                            }
                            setFlashcardsGenerating(false);
                          }}
                          disabled={flashcardsGenerating || (!lessonPlan && !generatedAssignment && uploadedDocs.length === 0)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #f59e0b, #d97706)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {flashcardsGenerating ? (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }), " Generating...")
                          ) : (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Layers", size: 16 }), " Generate Flashcards")
                          )}
                        </button>

                        {flashcards && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {flashcards.title || 'Flashcards'} ({(flashcards.cards || []).length} cards)
                            </h4>

                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "12px", marginBottom: "16px" }}>
                              {(flashcards.cards || []).map(function(card, ci) {
                                return (
                                  <div key={ci} style={{ padding: "16px", borderRadius: "10px", border: "1px solid var(--border)", background: "var(--input-bg)" }}>
                                    <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#f59e0b", marginBottom: "8px" }}>
                                      {card.term}
                                    </div>
                                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                                      {card.definition}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                onClick={async function() {
                                  try {
                                    var resp = await fetch('/api/export-flashcards', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ flashcards: flashcards, format: 'pdf' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (flashcards.title || 'Flashcards') + '.pdf';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileDown" size={16} /> Export PDF
                              </button>
                              <button
                                onClick={async function() {
                                  try {
                                    var resp = await fetch('/api/export-flashcards', {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' },
                                      body: JSON.stringify({ flashcards: flashcards, format: 'docx' }),
                                    });
                                    var blob = await resp.blob();
                                    var url = URL.createObjectURL(blob);
                                    var a = document.createElement('a');
                                    a.href = url;
                                    a.download = (flashcards.title || 'Flashcards') + '.docx';
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { addToast('Export failed', 'error'); }
                                }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="FileText" size={16} /> Export DOCX
                              </button>
                              <button
                                onClick={function() { shareWithClass(flashcards, 'flashcards', flashcards.title || 'Flashcards'); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="Share2" size={16} /> Share with Class
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Slide Deck Generator */}
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Presentation" size={22} style={{ color: "#8b5cf6" }} />
                          Slide Deck Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate a professional slide deck with AI-generated graphics from your lesson plan. Export as PowerPoint.
                        </p>

                        <div style={{ display: "flex", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Slides</label>
                            <select value={slideCount} onChange={function(e) { setSlideCount(parseInt(e.target.value)); }} className="input" style={{ maxWidth: "100px" }}>
                              <option value={8}>8</option>
                              <option value={10}>10</option>
                              <option value={12}>12</option>
                              <option value={15}>15</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>AI Graphics</label>
                            <select value={slideImages ? "yes" : "no"} onChange={function(e) { setSlideImages(e.target.value === "yes"); }} className="input" style={{ maxWidth: "160px" }}>
                              <option value="yes">With graphics</option>
                              <option value="no">Text only</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Format</label>
                            <select value={slideFormat} onChange={function(e) { setSlideFormat(e.target.value); }} className="input" style={{ maxWidth: "180px" }}>
                              <option value="detailed">Detailed Deck</option>
                              <option value="presenter">Presenter Slides</option>
                            </select>
                          </div>
                          <div style={{ flex: 1, minWidth: "200px" }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Instructions (optional)</label>
                            <input type="text" value={slideDeckInstructions} onChange={function(e) { setSlideDeckInstructions(e.target.value); }} placeholder="e.g., Focus on vocabulary, include comparison slides" className="input" />
                          </div>
                        </div>

                        {/* Resource picker */}
                        <div style={{ marginBottom: "12px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                            <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Include saved resources</label>
                            <button
                              onClick={async function() {
                                setSlideResourcesLoading(true);
                                try {
                                  var data = await api.listResources();
                                  setSlideResourceList(data.resources || []);
                                } catch (err) {
                                  addToast('Failed to load resources', 'error');
                                }
                                setSlideResourcesLoading(false);
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                              disabled={slideResourcesLoading}
                            >
                              {slideResourcesLoading ? 'Loading...' : 'Browse'}
                            </button>
                          </div>
                          {slideResourceList.length > 0 && (
                            <div style={{ maxHeight: "120px", overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px", padding: "6px" }}>
                              {slideResourceList.map(function(res) {
                                var isSelected = slideResources.some(function(r) { return r.id === res.id; });
                                return (
                                  React.createElement('label', { key: res.id, style: { display: "flex", alignItems: "center", gap: "8px", padding: "4px 6px", fontSize: "0.8rem", cursor: "pointer", borderRadius: "4px", background: isSelected ? "rgba(139,92,246,0.1)" : "transparent" } },
                                    React.createElement('input', {
                                      type: "checkbox",
                                      checked: isSelected,
                                      onChange: function() {
                                        if (isSelected) {
                                          setSlideResources(slideResources.filter(function(r) { return r.id !== res.id; }));
                                        } else {
                                          setSlideResources(slideResources.concat([res]));
                                        }
                                      }
                                    }),
                                    React.createElement('span', { style: { fontWeight: 500 } }, res.title || 'Untitled'),
                                    React.createElement('span', { style: { color: "var(--text-secondary)", fontSize: "0.7rem" } }, res.content_type || '')
                                  )
                                );
                              })}
                            </div>
                          )}
                          {slideResources.length > 0 && (
                            React.createElement('p', { style: { fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" } },
                              slideResources.length + ' resource(s) selected')
                          )}
                        </div>

                        <button
                          onClick={async function() {
                            setSlideDeckGenerating(true);
                            setSlideDeck(null);
                            try {
                              var content = '';
                              if (lessonPlan && lessonPlan.overview) {
                                content = lessonPlan.overview + String.fromCharCode(10) + (lessonPlan.days || []).map(function(d) { return 'Day ' + d.day + ': ' + d.topic; }).join(String.fromCharCode(10));
                              }
                              if (generatedAssignment) {
                                var sections = generatedAssignment.sections || generatedAssignment.questions || [];
                                content += String.fromCharCode(10) + sections.map(function(s) {
                                  if (s.questions) return s.name + ': ' + s.questions.map(function(q) { return q.question; }).join(', ');
                                  return s.question || '';
                                }).join(String.fromCharCode(10));
                              }
                              // Append selected resource content
                              if (slideResources.length > 0) {
                                for (var ri = 0; ri < slideResources.length; ri++) {
                                  try {
                                    var resData = await api.loadResource(slideResources[ri].id);
                                    if (resData && resData.resource) {
                                      var rc = resData.resource.content;
                                      if (typeof rc === 'object') rc = JSON.stringify(rc);
                                      content += String.fromCharCode(10) + '--- Resource: ' + (slideResources[ri].title || '') + ' ---' + String.fromCharCode(10) + (rc || '').substring(0, 4000);
                                    }
                                  } catch (err) { /* skip failed resource loads */ }
                                }
                              }
                              if (!content.trim()) {
                                addToast('Generate a lesson plan, assessment, or select resources first.', 'warning');
                                setSlideDeckGenerating(false);
                                return;
                              }
                              var resp = await fetch('/api/generate-slides', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  title: (lessonPlan && lessonPlan.title ? lessonPlan.title : 'Slide Deck'),
                                  content: content,
                                  lessonPlan: lessonPlan && lessonPlan.overview ? lessonPlan : undefined,
                                  subject: config.subject || '',
                                  grade: config.grade || '',
                                  globalAINotes: config.globalAINotes || '',
                                  instructions: slideDeckInstructions,
                                  slideCount: slideCount,
                                  generateImages: slideImages,
                                  maxImages: 5,
                                  deckFormat: slideFormat,
                                }),
                              });
                              var data = await resp.json();
                              if (data.error) {
                                addToast(data.error, 'error');
                              } else {
                                setSlideDeck(data.slides);
                                addToast('Slide deck generated! (' + data.slide_count + ' slides, ' + data.images_generated + ' graphics)', 'success');
                              }
                            } catch (err) {
                              addToast('Failed to generate slides: ' + err.message, 'error');
                            }
                            setSlideDeckGenerating(false);
                          }}
                          disabled={slideDeckGenerating || (!lessonPlan && !generatedAssignment && slideResources.length === 0)}
                          className="btn btn-primary"
                          style={{ padding: "10px 24px", background: "linear-gradient(135deg, #8b5cf6, #6366f1)", display: "flex", alignItems: "center", gap: "8px" }}
                        >
                          {slideDeckGenerating ? (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }),
                              slideDeckGenerating ? " Generating slides..." : " Generate")
                          ) : (
                            React.createElement(React.Fragment, null,
                              React.createElement(Icon, { name: "Presentation", size: 16 }), " Generate Slide Deck")
                          )}
                        </button>

                        {slideDeck && (
                          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
                            <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
                              {slideDeck.title || 'Slide Deck'} ({(slideDeck.slides || []).length} slides)
                            </h4>

                            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px", maxHeight: "400px", overflowY: "auto" }}>
                              {(slideDeck.slides || []).map(function(slide, si) {
                                return (
                                  <div key={si} style={{ padding: "12px 16px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--input-bg)", display: "flex", gap: "12px", alignItems: "flex-start" }}>
                                    <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#8b5cf6", minWidth: "24px" }}>{si + 1}</span>
                                    <div>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{slide.title}</div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                                        {slide.layout} {slide.image_prompt ? ' + graphic' : ''}
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            <button
                              onClick={async function() {
                                try {
                                  addToast('Assembling PowerPoint...', 'info');
                                  var resp = await fetch('/api/export-slides', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ slides: slideDeck }),
                                  });
                                  if (!resp.ok) {
                                    var err = await resp.json();
                                    addToast(err.error || 'Export failed', 'error');
                                    return;
                                  }
                                  var blob = await resp.blob();
                                  var url = URL.createObjectURL(blob);
                                  var a = document.createElement('a');
                                  a.href = url;
                                  a.download = (slideDeck.title || 'Slides') + '.pptx';
                                  a.click();
                                  URL.revokeObjectURL(url);
                                  addToast('PowerPoint downloaded!', 'success');
                                } catch (err) { addToast('Export failed: ' + err.message, 'error'); }
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
                            >
                              <Icon name="Download" size={16} /> Download PowerPoint (.pptx)
                            </button>
                            <button
                              onClick={function() { shareWithClass(slideDeck, 'slide_deck', slideDeck.title || 'Slide Deck'); }}
                              className="btn btn-secondary"
                              style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
                            >
                              <Icon name="Share2" size={16} /> Share with Class
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
  );
}
