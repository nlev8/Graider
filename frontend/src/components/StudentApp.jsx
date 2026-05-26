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
    // SSO callbacks: clever|classlink single-enrollment (code) or multi (select).
    var ssoProvider = params.get("clever") === "1" ? "clever"
                    : params.get("classlink") === "1" ? "classlink" : null;
    var ssoCode = params.get("code");
    var selectProvider = params.get("clever_select") === "1" ? "clever"
                       : params.get("classlink_select") === "1" ? "classlink" : null;
    var selToken = params.get("sel");

    if (selectProvider && selToken) {
      window.history.replaceState({}, document.title, "/student");
      fetch("/api/" + selectProvider + "/select-class?selection_token=" + encodeURIComponent(selToken))
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data && data.classes && data.classes.length) {
            setClassPicker({ provider: selectProvider, selectionToken: selToken, classes: data.classes });
          }
        })
        .catch(function(err) { console.error("SSO class options failed:", err); })
        .finally(function() { setChecking(false); });
      return;
    }

    if (ssoProvider && ssoCode) {
      window.history.replaceState({}, document.title, "/student");
      fetch("/api/" + ssoProvider + "/student-token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: ssoCode }),
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
          console.error("SSO student auth failed:", err);
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

  function chooseClass(classId) {
    setChecking(true);
    fetch("/api/" + classPicker.provider + "/select-class", {
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
        console.error("SSO class selection failed:", err);
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
              <button key={c.class_id} onClick={function() { chooseClass(c.class_id); }} style={{ padding: "14px 18px", borderRadius: "10px", border: "1px solid #334155", background: "#1e293b", color: "#e2e8f0", fontSize: "1rem", textAlign: "left", cursor: "pointer" }}>
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
