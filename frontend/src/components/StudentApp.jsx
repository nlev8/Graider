import React, { useState, useEffect } from "react";
import StudentLogin from "./StudentLogin";
import StudentDashboard from "./StudentDashboard";

export default function StudentApp() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [studentInfo, setStudentInfo] = useState(null);
  const [classInfo, setClassInfo] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    var params = new URLSearchParams(window.location.search);
    var cleverFlag = params.get("clever");
    var cleverCode = params.get("code");

    if (cleverFlag === "1" && cleverCode) {
      // Clean the URL to remove the auth code from browser bar
      window.history.replaceState({}, document.title, "/student");

      // Exchange auth code for session token
      fetch("/api/clever/student-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: cleverCode }),
      })
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.error) {
            setChecking(false);
            return;
          }
          var token = data.token;
          localStorage.setItem("student_token", token);

          return fetch("/api/student/session", {
            headers: { "X-Student-Token": token },
          })
            .then(function(r) { return r.json(); })
            .then(function(sessionData) {
              if (sessionData.valid) {
                var studentData = sessionData.student || {};
                var classData = sessionData.class_info || {};
                localStorage.setItem("student_info", JSON.stringify(studentData));
                localStorage.setItem("student_class", JSON.stringify(classData));
                setStudentInfo(studentData);
                setClassInfo(classData);
                setLoggedIn(true);
              }
            });
        })
        .catch(function(err) {
          console.error("Clever student auth failed:", err);
          localStorage.removeItem("student_token");
        })
        .finally(function() { setChecking(false); });
      return;
    } else {
      var token = localStorage.getItem("student_token");
      var savedStudent = localStorage.getItem("student_info");
      var savedClass = localStorage.getItem("student_class");

      if (token && savedStudent) {
        fetch("/api/student/session", {
          headers: { "X-Student-Token": token },
        })
          .then(function(r) { return r.json(); })
          .then(function(data) {
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
          .catch(function(err) {
            console.error("Session check failed:", err);
          })
          .finally(function() { setChecking(false); });
      } else {
        setChecking(false);
      }
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
