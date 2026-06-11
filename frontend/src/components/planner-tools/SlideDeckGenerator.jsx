import React, { useState } from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

/*
 * Slide Deck Generator card, relocated verbatim from PlannerTools.jsx
 * (CQ wave-5 split). The slide* useState block moved with the card;
 * the card is unconditionally mounted by the always-mounted PlannerTools
 * shell, so state lifetime is unchanged. Prop names match the original
 * identifiers so the JSX is byte-identical.
 */
export default function SlideDeckGenerator({ config, lessonPlan, generatedAssignment, addToast, shareWithClass }) {
  const [slideDeck, setSlideDeck] = useState(null);
  const [slideDeckGenerating, setSlideDeckGenerating] = useState(false);
  const [slideDeckInstructions, setSlideDeckInstructions] = useState('');
  const [slideResources, setSlideResources] = useState([]);
  const [slideResourceList, setSlideResourceList] = useState([]);
  const [slideResourcesLoading, setSlideResourcesLoading] = useState(false);
  const [slideCount, setSlideCount] = useState(10);
  const [slideImages, setSlideImages] = useState(true);
  const [slideFormat, setSlideFormat] = useState('detailed');

  return (
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
  );
}
