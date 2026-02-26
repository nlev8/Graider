import React, { useState } from "react";

export default function StudentLogin({ onLogin }) {
  const [email, setEmail] = useState("");
  const [classCode, setClassCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
      justifyContent: "center", background: "linear-gradient(135deg, #0f172a, #1e293b)",
      fontFamily: "Inter, sans-serif",
    }}>
      <div style={{
        background: "rgba(30,41,59,0.95)", borderRadius: "16px",
        padding: "40px", maxWidth: "400px", width: "90%",
        border: "1px solid rgba(99,102,241,0.3)",
      }}>
        <h1 style={{ color: "white", fontSize: "1.5rem", fontWeight: 700, marginBottom: "8px", textAlign: "center" }}>
          Graider Student Portal
        </h1>
        <p style={{ color: "#94a3b8", textAlign: "center", marginBottom: "24px", fontSize: "0.9rem" }}>
          Enter your school email and class code to get started
        </p>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "16px" }}>
            <label style={{ color: "#cbd5e1", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
              School Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.name@school.edu"
              style={{
                width: "100%", padding: "12px", borderRadius: "8px",
                background: "rgba(15,23,42,0.8)", border: "1px solid rgba(99,102,241,0.3)",
                color: "white", fontSize: "1rem", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label style={{ color: "#cbd5e1", fontSize: "0.85rem", display: "block", marginBottom: "6px" }}>
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
                background: "rgba(15,23,42,0.8)", border: "1px solid rgba(99,102,241,0.3)",
                color: "white", fontSize: "1.2rem", fontWeight: 600, letterSpacing: "3px",
                textAlign: "center", outline: "none", boxSizing: "border-box",
              }}
            />
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: "8px", padding: "10px 14px", marginBottom: "16px",
              color: "#fca5a5", fontSize: "0.85rem",
            }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} style={{
            width: "100%", padding: "14px", borderRadius: "10px",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            color: "white", fontSize: "1rem", fontWeight: 600, border: "none",
            cursor: loading ? "wait" : "pointer", opacity: loading ? 0.7 : 1,
          }}>
            {loading ? "Logging in..." : "Enter Portal"}
          </button>
        </form>
      </div>
    </div>
  );
}
