import React, { useState, useEffect } from "react";
import StudentPortal from "./StudentPortal";
import DashboardHeader from "./student-dashboard/DashboardHeader";
import UnitGroupCard from "./student-dashboard/UnitGroupCard";
import ResourceViewerModal from "./student-dashboard/ResourceViewerModal";

var RESOURCE_TYPES = ['study_guide', 'flashcards', 'slide_deck'];

// Thin orchestrator after the CQ wave-7 split: all state, effects, data
// fetching, and the unit grouping/sorting derivations stay in this
// always-mounted shell; the header bar, per-unit accordion cards, and the
// resource viewer modal moved verbatim to student-dashboard/*.
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
    return { id: i.content_id, title: i.title, content_type: i.content_type, _fromDashboard: true, content_id: i.content_id, unit_name: i.unit_name || '', created_at: i.created_at || '' };
  });
  var resourceIds = resources.map(function(r) { return r.id; });
  var allResources = resources.concat(dashboardResources.filter(function(dr) { return resourceIds.indexOf(dr.id) === -1; }));

  var [expandedUnits, setExpandedUnits] = useState({});

  // Group all content by unit_name
  var unitGroups = {};
  assignmentItems.forEach(function(item) {
    var unit = item.unit_name || '';
    if (!unitGroups[unit]) unitGroups[unit] = { assignments: [], resources: [], newestDate: '' };
    unitGroups[unit].assignments.push(item);
    if (item.created_at && item.created_at > unitGroups[unit].newestDate) unitGroups[unit].newestDate = item.created_at;
  });
  allResources.forEach(function(res) {
    var unit = res.unit_name || '';
    if (!unitGroups[unit]) unitGroups[unit] = { assignments: [], resources: [], newestDate: '' };
    unitGroups[unit].resources.push(res);
    if (res.created_at && res.created_at > unitGroups[unit].newestDate) unitGroups[unit].newestDate = res.created_at;
  });

  // Sort units: most recent first, "General" (empty unit) always last
  var sortedUnits = Object.keys(unitGroups).sort(function(a, b) {
    if (!a) return 1;
    if (!b) return -1;
    return unitGroups[b].newestDate.localeCompare(unitGroups[a].newestDate);
  });

  // Auto-expand most recent unit on first render
  React.useEffect(function() {
    if (sortedUnits.length > 0 && Object.keys(expandedUnits).length === 0) {
      var first = sortedUnits[0];
      setExpandedUnits(function(prev) { var next = Object.assign({}, prev); next[first] = true; return next; });
    }
  }, [sortedUnits.length]);

  // Theme toggle
  var [lightMode, setLightMode] = useState(function() {
    var saved = localStorage.getItem("portal-theme");
    if (saved) {
      document.body.setAttribute("data-theme", saved);
      return saved === "light";
    }
    return false;
  });

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

  return (
    <div style={{
      minHeight: "100vh", background: "linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end))",
      fontFamily: "Inter, sans-serif", color: "var(--text-primary)",
    }}>
      <DashboardHeader
        studentInfo={studentInfo}
        classInfo={classInfo}
        lightMode={lightMode}
        setLightMode={setLightMode}
        handleLogout={handleLogout}
      />

      <div style={{ maxWidth: "800px", margin: "0 auto", padding: "24px" }}>
        {loading ? (
          <p style={{ color: "var(--text-secondary)" }}>Loading...</p>
        ) : sortedUnits.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            background: "var(--card-bg-light)", borderRadius: "12px",
            border: "1px solid var(--glass-border)",
          }}>
            <p style={{ color: "var(--text-secondary)", fontSize: "1.1rem" }}>No content yet</p>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Your teacher will publish assignments and study materials here
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {sortedUnits.map(function(unitName, unitIdx) {
              return (
                <UnitGroupCard
                  key={unitName || '__general__'}
                  unitName={unitName}
                  unitIdx={unitIdx}
                  group={unitGroups[unitName]}
                  expandedUnits={expandedUnits}
                  setExpandedUnits={setExpandedUnits}
                  openContent={openContent}
                  token={token}
                  setSelectedResource={setSelectedResource}
                  setFlippedCards={setFlippedCards}
                />
              );
            })}
          </div>
        )}

        {/* Resource Viewer Modal */}
        <ResourceViewerModal
          selectedResource={selectedResource}
          setSelectedResource={setSelectedResource}
        />
      </div>
    </div>
  );
}
