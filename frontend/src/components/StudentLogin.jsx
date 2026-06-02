import React, { useState } from "react";
import Icon from "./Icon";

export default function StudentLogin({ onLogin }) {
  const [email, setEmail] = useState("");
  const [classCode, setClassCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Theme toggle
  var [lightMode, setLightMode] = useState(function() {
    var saved = localStorage.getItem("portal-theme");
    if (saved) {
      document.body.setAttribute("data-theme", saved);
      return saved === "light";
    }
    return false;
  });

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email.trim() || !classCode.trim()) {
      setError("Please enter both your email and class code");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/student/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          class_code: classCode.trim().toUpperCase(),
        }),
      });

      const data = await response.json();
      if (data.success) {
        localStorage.setItem("student_token", data.token);
        localStorage.setItem("student_info", JSON.stringify(data.student));
        localStorage.setItem("student_class", JSON.stringify(data.class));
        onLogin(data);
      } else {
        setError(data.error || "Login failed");
      }
    } catch (e) {
      setError("Could not connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", background: "linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end))",
      fontFamily: "Inter, sans-serif",
    }}>
      <button
        onClick={function() {
          var next = !lightMode;
          setLightMode(next);
          var theme = next ? "light" : "dark";
          document.body.setAttribute("data-theme", theme);
          localStorage.setItem("portal-theme", theme);
        }}
        style={{
          position: "fixed", top: "12px", right: "12px", zIndex: 200,
          background: "var(--btn-secondary-bg)",
          border: "none", borderRadius: "8px", padding: "8px",
          cursor: "pointer", color: "var(--text-secondary)",
        }}
        title={lightMode ? "Switch to dark mode" : "Switch to light mode"}
      >
        <Icon name={lightMode ? "Moon" : "Sun"} size={18} />
      </button>
      <div style={{
        background: "var(--header-bg)", borderRadius: "16px",
        padding: "40px", maxWidth: "400px", width: "90%",
        border: "1px solid var(--glass-border)",
      }}>
        <h1 style={{ color: "var(--text-primary)", fontSize: "1.5rem", fontWeight: 700, marginBottom: "8px", textAlign: "center" }}>
          Graider Student Portal
        </h1>
        <p style={{ color: "var(--text-secondary)", textAlign: "center", marginBottom: "24px", fontSize: "0.9rem" }}>
          Enter your school email and class code to get started
        </p>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ color: "var(--text-muted)", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
              School Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.name@school.edu"
              style={{
                width: "100%", padding: "12px", borderRadius: "8px",
                background: "var(--input-bg)", border: "1px solid var(--input-border)",
                color: "var(--text-primary)", fontSize: "1rem", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label style={{ color: "var(--text-muted)", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
              Class Code
            </label>
            <input
              type="text"
              value={classCode}
              onChange={(e) => setClassCode(e.target.value.toUpperCase())}
              placeholder="e.g. ABC123"
              maxLength={6}
              style={{
                width: "100%", padding: "12px", borderRadius: "8px",
                background: "var(--input-bg)", border: "1px solid var(--input-border)",
                color: "var(--text-primary)", fontSize: "1.2rem", fontWeight: 600, letterSpacing: "3px",
                textAlign: "center", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div style={{
              background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
              borderRadius: "8px", padding: "10px 14px", marginBottom: "16px",
              color: "var(--danger-light)", fontSize: "0.85rem",
            }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "14px", borderRadius: "10px",
            background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
            color: "white", fontSize: "1rem", fontWeight: 600, border: "none",
            cursor: loading ? "wait" : "pointer", opacity: loading ? 0.7 : 1,
          }}>
            {loading ? "Logging in..." : "Enter Portal"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "20px 0" }}>
          <div style={{ flex: 1, height: "1px", background: "var(--glass-border)" }} />
          <span style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>or sign in with your school account</span>
          <div style={{ flex: 1, height: "1px", background: "var(--glass-border)" }} />
        </div>

        <button type="button" onClick={() => { window.location.href = "/api/classlink/login-url?redirect=1"; }} style={{
          width: "100%", padding: "12px", borderRadius: "10px", marginBottom: "10px",
          background: "var(--input-bg)", border: "1px solid var(--input-border)",
          color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
        }}>
          <svg width="20" height="20" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <path d="M80 55c0-16.6-13.4-30-30-30-12.7 0-23.6 7.9-28 19C13.4 44 6 51.4 6 61c0 11 9 20 20 20h54c8.8 0 16-7.2 16-16 0-7.3-5-13.5-12-15.3C83.3 48 80 51.2 80 55z" fill="#2196F3"/>
            <circle cx="50" cy="42" r="8" fill="white"/>
            <path d="M38 62c0-6.6 5.4-12 12-12s12 5.4 12 12" stroke="white" strokeWidth="4" fill="none" strokeLinecap="round"/>
          </svg>
          Sign in with ClassLink
        </button>
        <button type="button" onClick={() => { window.location.href = "/api/clever/login-url?redirect=1"; }} style={{
          width: "100%", padding: "12px", borderRadius: "10px",
          background: "var(--input-bg)", border: "1px solid var(--input-border)",
          color: "var(--text-primary)", fontSize: "0.95rem", fontWeight: 600, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
        }}>
          <svg width="18" height="18" viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="56" height="56" rx="14" fill="#4274F6"/>
            <path d="M32.8 16.4C29.2 14.3 24.6 14.5 21.2 17C17.8 19.5 16.2 23.7 17 27.8C17.8 31.9 20.8 35.1 24.8 36.2C28.8 37.3 33 35.9 35.6 32.8" stroke="white" strokeWidth="4.5" strokeLinecap="round"/>
          </svg>
          Sign in with Clever
        </button>
      </div>
    </div>
  );
}
