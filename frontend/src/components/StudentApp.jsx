import React, { useState, useEffect } from "react";
import StudentLogin from "./StudentLogin";
import StudentDashboard from "./StudentDashboard";

export default function StudentApp() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [studentInfo, setStudentInfo] = useState(null);
  const [classInfo, setClassInfo] = useState(null);
  const [checking, setChecking] = useState(true);
  const [classPicker, setClassPicker] = useState(null);

  useEffect(() => {
    var params = new URLSearchParams(window.location.search);
    var cleverFlag = params.get("clever");
    var cleverCode = params.get("code");
    var cleverSelect = params.get("clever_select");
    var selToken = params.get("sel");

    if (cleverSelect === "1" && selToken) {
      // Multi-enrolled Clever student (Task A): fetch the candidate
      // classes and show a picker instead of silently choosing.
      window.history.replaceState({}, document.title, "/student");
      fetch("/api/clever/select-class?selection_token=" + encodeURIComponent(selToken))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data && data.classes && data.classes.length) {
            setClassPicker({ selectionToken: selToken, classes: data.classes });
          }
        })
        .catch(function(err) { console.error("Clever class options failed:", err); })
        .finally(function() { setChecking(false); });
      return;
    }

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

  function chooseCleverClass(classId) {
    setChecking(true);
    fetch("/api/clever/select-class", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection_token: classPicker.selectionToken, class_id: classId }),
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.error || !data.token) { setChecking(false); return; }
        var token = data.token;
        localStorage.setItem("student_token", token);
        return fetch("/api/student/session", { headers: { "X-Student-Token": token } })
          .then(function(r) { return r.json(); })
          .then(function(sessionData) {
            if (sessionData.valid) {
              var studentData = sessionData.student || {};
              var classData = sessionData.class_info || {};
              localStorage.setItem("student_info", JSON.stringify(studentData));
              localStorage.setItem("student_class", JSON.stringify(classData));
              setStudentInfo(studentData);
              setClassInfo(classData);
              setClassPicker(null);
              setLoggedIn(true);
            }
          });
      })
      .catch(function(err) {
        console.error("Clever class selection failed:", err);
        localStorage.removeItem("student_token");
      })
      .finally(function() { setChecking(false); });
  }

  if (classPicker) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#0f172a", color: "#e2e8f0", fontFamily: "Inter, sans-serif", padding: "24px" }}>
        <h2 style={{ marginBottom: "8px", fontSize: "1.3rem" }}>Choose your class</h2>
        <p style={{ marginBottom: "20px", color: "#64748b", fontSize: "0.9rem" }}>You're enrolled in more than one class. Pick the one to open.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", width: "100%", maxWidth: "360px" }}>
          {classPicker.classes.map(function(c) {
            return (
              <button key={c.class_id} onClick={function() { chooseCleverClass(c.class_id); }} style={{ padding: "14px 18px", borderRadius: "10px", border: "1px solid #334155", background: "#1e293b", color: "#e2e8f0", fontSize: "1rem", textAlign: "left", cursor: "pointer" }}>
                <span style={{ fontWeight: 600 }}>{c.name}</span>
                {c.subject ? <span style={{ color: "#64748b", marginLeft: "8px", fontSize: "0.85rem" }}>{c.subject}</span> : null}
              </button>
            );
          })}
        </div>
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
