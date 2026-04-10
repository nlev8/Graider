import React, { useState, useEffect } from "react";
import StudentPortal from "./StudentPortal";
import FlashcardView from "./FlashcardView";

var RESOURCE_TYPES = ['study_guide', 'flashcards', 'slide_deck'];

export default function StudentDashboard({ studentInfo, classInfo, onLogout }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeContent, setActiveContent] = useState(null);
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [selectedResource, setSelectedResource] = useState(null);
  const [flippedCards, setFlippedCards] = useState({});
  const token = localStorage.getItem("student_token");

  // Split dashboard items into assignments vs resources
  var assignmentItems = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) === -1; });
  var dashboardResources = items.filter(function(i) { return RESOURCE_TYPES.indexOf(i.content_type) !== -1; }).map(function(i) {
    return { id: i.content_id, title: i.title, content_type: i.content_type, _fromDashboard: true, content_id: i.content_id };
  });
  var resourceIds = resources.map(function(r) { return r.id; });
  var allResources = resources.concat(dashboardResources.filter(function(dr) { return resourceIds.indexOf(dr.id) === -1; }));

  // Apply stored student portal theme on mount
  React.useEffect(function() {
    var saved = localStorage.getItem("portal-theme");
    if (saved) document.body.setAttribute("data-theme", saved);
  }, []);

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(function() {
    if (!token) return;
    fetch('/api/student/resources', {
      headers: { 'X-Student-Token': token }
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        setResources(data.resources || []);
        setResourcesLoading(false);
      })
      .catch(function() { setResourcesLoading(false); });
  }, []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/student/dashboard", {
        headers: { "X-Student-Token": token },
      });
      const data = await response.json();
      if (data.items) setItems(data.items);
    } catch (e) {
      console.error("Failed to load dashboard:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("student_token");
    localStorage.removeItem("student_info");
    localStorage.removeItem("student_class");
    onLogout();
  };

  const openContent = async (item) => {
    try {
      const response = await fetch("/api/student/content/" + item.content_id, {
        headers: { "X-Student-Token": token },
      });
      const data = await response.json();
      if (data.content) {
        setActiveContent({
          ...data,
          studentName: studentInfo.first_name + " " + studentInfo.last_name,
        });
      }
    } catch (e) {
      console.error("Failed to load content:", e);
    }
  };

  if (activeContent) {
    return (
      <StudentPortal
        preloadedAssessment={activeContent.content}
        preloadedStudentName={activeContent.studentName}
        contentId={activeContent.content_id}
        studentToken={token}
        preloadedSettings={activeContent.settings}
        onBack={() => { setActiveContent(null); loadDashboard(); }}
      />
    );
  }

  const statusColors = {
    not_started: { bg: "var(--btn-secondary-bg)", text: "var(--text-secondary)", label: "Not Started" },
    in_progress: { bg: "var(--warning-bg)", text: "var(--warning)", label: "In Progress" },
    submitted: { bg: "rgba(59,130,246,0.2)", text: "var(--info)", label: "Submitted" },
    graded: { bg: "var(--success-bg)", text: "var(--success)", label: "Graded" },
    returned: { bg: "rgba(168,85,247,0.2)", text: "var(--accent-light)", label: "Returned" },
  };

  return (
    <div style={{
      minHeight: "100vh", background: "linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end))",
      fontFamily: "Inter, sans-serif", color: "var(--text-primary)",
    }}>
      <div style={{
        background: "var(--header-bg)", borderBottom: "1px solid var(--glass-border)",
        padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <h1 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>
            {studentInfo.first_name} {studentInfo.last_name}
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", margin: "2px 0 0" }}>
            {classInfo.name}{classInfo.subject ? " \u2022 " + classInfo.subject : ""}
          </p>
        </div>
        <button onClick={handleLogout} style={{
          padding: "8px 16px", borderRadius: "8px", background: "var(--danger-bg)",
          border: "1px solid var(--danger-border)", color: "var(--danger-light)", cursor: "pointer",
          fontSize: "0.85rem",
        }}>
          Log Out
        </button>
      </div>

      <div style={{ maxWidth: "800px", margin: "0 auto", padding: "24px" }}>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px", color: "var(--text-primary)" }}>
          Your Assignments
        </h2>

        {loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
        ) : assignmentItems.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            background: "var(--card-bg-light)", borderRadius: "12px",
            border: "1px solid var(--glass-border)",
          }}>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem" }}>No assignments yet</p>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Your teacher will publish assignments here
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {assignmentItems.map((item) => {
              const st = statusColors[item.status] || statusColors.not_started;
              const isClickable = item.status !== "graded";
              return (
                <div
                  key={item.content_id}
                  onClick={() => isClickable && openContent(item)}
                  style={{
                    background: "var(--card-bg)", borderRadius: "12px",
                    border: "1px solid var(--glass-border)", padding: "16px 20px",
                    cursor: isClickable ? "pointer" : "default",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    transition: "border-color 0.2s",
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 4px" }}>
                      {item.title}
                    </h3>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", margin: 0 }}>
                      {item.content_type === "assessment" ? "Assessment" : "Assignment"}
                      {item.due_date ? " \u2022 Due " + new Date(item.due_date).toLocaleDateString() : ""}
                    </p>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{
                      padding: "4px 12px", borderRadius: "20px", fontSize: "0.75rem",
                      fontWeight: 600, background: st.bg, color: st.text,
                    }}>
                      {st.label}
                    </span>
                    {item.score != null && (
                      <p style={{ color: "var(--text-primary)", fontSize: "0.9rem", fontWeight: 600, margin: "6px 0 0" }}>
                        {item.percentage != null ? Math.round(item.percentage) + "%" : item.score}
                        {item.letter_grade ? " (" + item.letter_grade + ")" : ""}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Resources Section */}
        {allResources.length > 0 && (
          <div style={{ marginTop: "24px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "1.2rem" }}>{String.fromCharCode(128218)}</span>
              Study Materials
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
              {allResources.map(function(res) {
                var icon = res.content_type === 'study_guide' ? String.fromCharCode(128214)
                  : res.content_type === 'flashcards' ? String.fromCharCode(128196)
                  : res.content_type === 'slide_deck' ? String.fromCharCode(128253)
                  : String.fromCharCode(128196);
                var typeLabel = res.content_type === 'study_guide' ? 'Study Guide'
                  : res.content_type === 'flashcards' ? 'Flashcards'
                  : res.content_type === 'slide_deck' ? 'Slide Deck'
                  : res.content_type;
                return (
                  <div
                    key={res.id}
                    onClick={function() {
                      if (res._fromDashboard) {
                        fetch('/api/student/content/' + res.content_id, {
                          headers: { 'X-Student-Token': token }
                        })
                          .then(function(r) { return r.json(); })
                          .then(function(data) {
                            if (data.content) {
                              setSelectedResource({ id: res.content_id, title: res.title, content_type: res.content_type, content: data.content });
                              setFlippedCards({});
                            }
                          })
                          .catch(function() {});
                      } else {
                        fetch('/api/student/resource/' + res.id, {
                          headers: { 'X-Student-Token': token }
                        })
                          .then(function(r) { return r.json(); })
                          .then(function(data) {
                            if (data.resource) {
                              setSelectedResource(data.resource);
                              setFlippedCards({});
                            }
                          })
                          .catch(function() {});
                      }
                    }}
                    style={{
                      padding: "16px",
                      borderRadius: "12px",
                      border: "1px solid var(--glass-border)",
                      background: "var(--card-bg)",
                      cursor: "pointer",
                      transition: "transform 0.1s",
                    }}
                  >
                    <div style={{ fontSize: "1.5rem", marginBottom: "8px" }}>{icon}</div>
                    <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{res.title}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>{typeLabel}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Resource Viewer Modal */}
        {selectedResource && (
          <div style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "var(--modal-bg)", display: "flex", alignItems: "center",
            justifyContent: "center", zIndex: 1000, padding: "20px",
          }} onClick={function() { setSelectedResource(null); }}>
            <div
              style={{
                background: "var(--modal-content-bg)", borderRadius: "16px",
                padding: "24px", maxWidth: "700px", width: "100%",
                maxHeight: "80vh", overflowY: "auto",
              }}
              onClick={function(e) { e.stopPropagation(); }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{selectedResource.title}</h3>
                <button onClick={function() { setSelectedResource(null); }} style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "var(--text-secondary)" }}>{String.fromCharCode(10005)}</button>
              </div>

              {selectedResource.content_type === 'study_guide' && selectedResource.content && (
                <div>
                  {(selectedResource.content.sections || []).map(function(section, si) {
                    return (
                      <div key={si} style={{ marginBottom: "16px" }}>
                        <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>{section.heading}</h4>
                        {section.content && section.content.map(function(point, pi) {
                          return <p key={pi} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px", color: "var(--text-muted)" }}>{String.fromCharCode(8226)} {point}</p>;
                        })}
                        {section.terms && section.terms.map(function(item, ti) {
                          return <p key={ti} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px", color: "var(--text-muted)" }}><strong>{item.term}:</strong> {item.definition}</p>;
                        })}
                        {section.questions && section.questions.map(function(qa, qi) {
                          return (
                            <div key={qi} style={{ marginBottom: "8px", paddingLeft: "12px" }}>
                              <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>{qi + 1}. {qa.question}</p>
                              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", paddingLeft: "16px" }}>Answer: {qa.answer}</p>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              )}

              {selectedResource.content_type === 'flashcards' && selectedResource.content && (
                <FlashcardView data={selectedResource.content} />
              )}

              {selectedResource.content_type === 'slide_deck' && (
                <div style={{ textAlign: "center", padding: "20px" }}>
                  <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                    This slide deck contains {(selectedResource.content.slides || []).length} slides.
                  </p>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    Download the PowerPoint file from your teacher to view the full presentation.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
