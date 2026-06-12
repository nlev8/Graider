import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx (Shared
// Resources card). Stateless.
export default function SharedResourcesCard({ handleDeleteAllSharedResources, handleDeleteSharedResource, itemMatchesTagFilter, loadingSharedResources, renderTagRow, setSharedResources, sharedResources }) {
  return (
                        <div className="glass-card" style={{ padding: "20px", marginBottom: "16px" }}>
                          <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "10px" }}>
                            <Icon name="BookOpen" size={20} />
                            Shared Resources
                          </h3>
                          {loadingSharedResources ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Loading...</p>
                          ) : sharedResources.length === 0 ? (
                            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                              No shared resources yet. Use "Share with Class" on flashcards, study guides, or slide decks to share them with students.
                            </p>
                          ) : (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              {sharedResources.filter(itemMatchesTagFilter).map(function(res) {
                                var typeIcon = res.content_type === 'flashcards' ? 'Layers'
                                  : res.content_type === 'study_guide' ? 'FileText'
                                  : res.content_type === 'slide_deck' ? 'Monitor'
                                  : 'File';
                                var typeLabel = res.content_type === 'flashcards' ? 'Flashcards'
                                  : res.content_type === 'study_guide' ? 'Study Guide'
                                  : res.content_type === 'slide_deck' ? 'Slide Deck'
                                  : res.content_type;
                                var sameTitle = sharedResources.filter(function(r) { return r.title === res.title; });
                                var isFirst = sameTitle[0] && sameTitle[0].id === res.id;
                                return (
                                  <div key={res.id} style={{
                                    display: "flex", alignItems: "center", gap: "12px",
                                    padding: "10px 14px", borderRadius: "10px",
                                    background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                  }}>
                                    <Icon name={typeIcon} size={18} style={{ color: "var(--accent-primary)", flexShrink: 0 }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: "0.9rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {res.title}
                                      </div>
                                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                                        {typeLabel} {String.fromCharCode(8226)} {res.class_name} {String.fromCharCode(8226)} {new Date(res.created_at).toLocaleDateString()}
                                      </div>
                                      {renderTagRow(res, function(updates) {
                                        setSharedResources(function(prev) {
                                          return prev.map(function(r) { return r.id === res.id ? Object.assign({}, r, updates) : r; });
                                        });
                                      })}
                                    </div>
                                    <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                                      {isFirst && sameTitle.length > 1 && (
                                        <button
                                          onClick={function() { if (confirm('Delete "' + res.title + '" from all ' + sameTitle.length + ' classes?')) handleDeleteAllSharedResources(res.title); }}
                                          className="btn btn-secondary"
                                          style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                                          title="Delete from all classes"
                                        >
                                          Delete All ({sameTitle.length})
                                        </button>
                                      )}
                                      <button
                                        onClick={function() { handleDeleteSharedResource(res.id, res.title + ' (' + res.class_name + ')'); }}
                                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--danger)", padding: "4px" }}
                                        title={"Delete from " + res.class_name}
                                      >
                                        <Icon name="Trash2" size={16} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
  );
}
