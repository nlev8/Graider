import React, { useState, useEffect } from "react";
import StudentLogin from "./StudentLogin";
import StudentDashboard from "./StudentDashboard";

export default function StudentApp() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [studentInfo, setStudentInfo] = useState(null);
  const [classInfo, setClassInfo] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("student_token");
    const savedStudent = localStorage.getItem("student_info");
    const savedClass = localStorage.getItem("student_class");

    if (token && savedStudent) {
      fetch("/api/student/session", {
        headers: { "X-Student-Token": token },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.valid) {
            setStudentInfo(JSON.parse(savedStudent));
            setClassInfo(JSON.parse(savedClass || "{}"));
            setLoggedIn(true);
          } else {
            localStorage.removeItem("student_token");
            localStorage.removeItem("student_info");
            localStorage.removeItem("student_class");
          }
        })
        .catch(() => {})
        .finally(() => setChecking(false));
    } else {
      setChecking(false);
    }
  }, []);

  if (checking) {
    return (
      <div style={{
        minHeight: "100vh", display: "flex", alignItems: "center",
        justifyContent: "center", background: "#0f172a", color: "#64748b",
        fontFamily: "Inter, sans-serif",
      }}>
        Loading...
      </div>
    );
  }

  if (!loggedIn) {
    return (
      <StudentLogin
        onLogin={(data) => {
          setStudentInfo(data.student);
          setClassInfo(data.class);
          setLoggedIn(true);
        }}
      />
    );
  }

  return (
    <StudentDashboard
      studentInfo={studentInfo}
      classInfo={classInfo}
      onLogout={() => {
        setLoggedIn(false);
        setStudentInfo(null);
        setClassInfo(null);
      }}
    />
  );
}
