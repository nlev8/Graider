import React, { useState } from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

/*
 * Flashcard Generator card, relocated verbatim from PlannerTools.jsx
 * (CQ wave-5 split). The flashcard* useState block moved with the card;
 * the card is unconditionally mounted by the always-mounted PlannerTools
 * shell, so state lifetime is unchanged. Prop names match the original
 * identifiers so the JSX is byte-identical.
 */
export default function FlashcardGenerator({ config, lessonPlan, generatedAssignment, uploadedDocs, addToast, shareWithClass }) {
  const [flashcards, setFlashcards] = useState(null);
  const [flashcardsGenerating, setFlashcardsGenerating] = useState(false);
  const [flashcardInstructions, setFlashcardInstructions] = useState('');
  const [flashcardCount, setFlashcardCount] = useState(15);

  return (
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
  );
}
