import React, { useState } from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

/*
 * Study Guide Generator card, relocated verbatim from PlannerTools.jsx
 * (CQ wave-5 split). The studyGuide* useState block moved with the card;
 * the card is unconditionally mounted by the always-mounted PlannerTools
 * shell, so state lifetime is unchanged. Prop names match the original
 * identifiers so the JSX is byte-identical.
 */
export default function StudyGuideGenerator({ config, lessonPlan, generatedAssignment, addToast, shareWithClass }) {
  const [studyGuide, setStudyGuide] = useState(null);
  const [studyGuideGenerating, setStudyGuideGenerating] = useState(false);
  const [studyGuideInstructions, setStudyGuideInstructions] = useState('');

  return (
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
  );
}
