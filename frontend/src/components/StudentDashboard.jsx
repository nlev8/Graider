import React, { useState, useEffect } from "react";
import StudentPortal from "./StudentPortal";

export default function StudentDashboard({ studentInfo, classInfo, onLogout }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeContent, setActiveContent] = useState(null);
  const token = localStorage.getItem("student_token");

  useEffect(() => {
    loadDashboard();
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
        onBack={() => { setActiveContent(null); loadDashboard(); }}
      />
    );
  }

  const statusColors = {
    not_started: { bg: "rgba(100,116,139,0.2)", text: "#94a3b8", label: "Not Started" },
    in_progress: { bg: "rgba(234,179,8,0.2)", text: "#fbbf24", label: "In Progress" },
    submitted: { bg: "rgba(59,130,246,0.2)", text: "#60a5fa", label: "Submitted" },
    graded: { bg: "rgba(34,197,94,0.2)", text: "#4ade80", label: "Graded" },
    returned: { bg: "rgba(168,85,247,0.2)", text: "#c084fc", label: "Returned" },
  };

  return (
    <div style={{
      minHeight: "100vh", background: "linear-gradient(135deg, #0f172a, #1e293b)",
      fontFamily: "Inter, sans-serif", color: "white",
    }}>
      <div style={{
        background: "rgba(30,41,59,0.95)", borderBottom: "1px solid rgba(99,102,241,0.2)",
        padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <h1 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>
            {studentInfo.first_name} {studentInfo.last_name}
          </h1>
          <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "2px 0 0" }}>
            {classInfo.name}{classInfo.subject ? " \u2022 " + classInfo.subject : ""}
          </p>
        </div>
        <button onClick={handleLogout} style={{
          padding: "8px 16px", borderRadius: "8px", background: "rgba(239,68,68,0.2)",
          border: "1px solid rgba(239,68,68,0.3)", color: "#fca5a5", cursor: "pointer",
          fontSize: "0.85rem",
        }}>
          Log Out
        </button>
      </div>

      <div style={{ maxWidth: "800px", margin: "0 auto", padding: "24px" }}>
        <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "16px", color: "#e2e8f0" }}>
          Your Assignments
        </h2>

        {loading ? (
          <p style={{ color: "#64748b" }}>Loading...</p>
        ) : items.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "60px 20px",
            background: "rgba(30,41,59,0.5)", borderRadius: "12px",
            border: "1px solid rgba(99,102,241,0.1)",
          }}>
            <p style={{ color: "#64748b", fontSize: "1.1rem" }}>No assignments yet</p>
            <p style={{ color: "#475569", fontSize: "0.85rem" }}>
              Your teacher will publish assignments here
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {items.map((item) => {
              const st = statusColors[item.status] || statusColors.not_started;
              const isClickable = item.status !== "graded";
              return (
                <div
                  key={item.content_id}
                  onClick={() => isClickable && openContent(item)}
                  style={{
                    background: "rgba(30,41,59,0.8)", borderRadius: "12px",
                    border: "1px solid rgba(99,102,241,0.15)", padding: "16px 20px",
                    cursor: isClickable ? "pointer" : "default",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    transition: "border-color 0.2s",
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 4px" }}>
                      {item.title}
                    </h3>
                    <p style={{ color: "#64748b", fontSize: "0.8rem", margin: 0 }}>
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
                      <p style={{ color: "#e2e8f0", fontSize: "0.9rem", fontWeight: 600, margin: "6px 0 0" }}>
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
      </div>
    </div>
  );
}
