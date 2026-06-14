import React, { useState } from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import SlideDeckConfigPanel from "./SlideDeckConfigPanel";
import SlideDeckResults from "./SlideDeckResults";

/*
 * Slide Deck Generator card, relocated verbatim from PlannerTools.jsx
 * (CQ wave-5 split). The slide* useState block moved with the card;
 * the card is unconditionally mounted by the always-mounted PlannerTools
 * shell, so state lifetime is unchanged. Prop names match the original
 * identifiers so the JSX is byte-identical.
 *
 * CQ wave-8 split (#cq8-07): config/resource panel extracted to
 * SlideDeckConfigPanel; results panel extracted to SlideDeckResults.
 * All state and handlers remain here.
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
  const [slideTemplate, setSlideTemplate] = useState('minimal');

  return (
                      <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <Icon name="Presentation" size={22} style={{ color: "#8b5cf6" }} />
                          Slide Deck Generator
                        </h3>
                        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                          Generate a professional slide deck with AI-generated graphics from your lesson plan. Export as PowerPoint.
                        </p>

                        <SlideDeckConfigPanel
                          slideCount={slideCount}
                          setSlideCount={setSlideCount}
                          slideImages={slideImages}
                          setSlideImages={setSlideImages}
                          slideFormat={slideFormat}
                          setSlideFormat={setSlideFormat}
                          slideTemplate={slideTemplate}
                          setSlideTemplate={setSlideTemplate}
                          slideDeckInstructions={slideDeckInstructions}
                          setSlideDeckInstructions={setSlideDeckInstructions}
                          slideResourcesLoading={slideResourcesLoading}
                          slideResourceList={slideResourceList}
                          slideResources={slideResources}
                          setSlideResources={setSlideResources}
                          onBrowseResources={async function() {
                            setSlideResourcesLoading(true);
                            try {
                              var data = await api.listResources();
                              setSlideResourceList(data.resources || []);
                            } catch (err) {
                              addToast('Failed to load resources', 'error');
                            }
                            setSlideResourcesLoading(false);
                          }}
                        />

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
                                  template: slideTemplate,
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
                          <SlideDeckResults
                            slideDeck={slideDeck}
                            addToast={addToast}
                            onShare={shareWithClass}
                          />
                        )}
                      </div>
  );
}
