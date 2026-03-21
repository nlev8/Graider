import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error: error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0f172a",
          color: "white",
          fontFamily: "Inter, sans-serif",
          padding: "40px",
        }}>
          <div style={{ textAlign: "center", maxWidth: "500px" }}>
            <h1 style={{ fontSize: "2rem", marginBottom: "15px" }}>Something went wrong</h1>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "25px" }}>
              An unexpected error occurred. Please refresh the page to continue.
            </p>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: "12px 24px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                color: "white",
                border: "none",
                cursor: "pointer",
                fontSize: "1rem",
                fontWeight: 600,
              }}
            >
              Refresh Page
            </button>
            {this.state.error && (
              <details style={{ marginTop: "20px", textAlign: "left", fontSize: "0.8rem", color: "rgba(255,255,255,0.4)" }}>
                <summary>Error details</summary>
                <pre style={{ whiteSpace: "pre-wrap", marginTop: "10px" }}>
                  {this.state.error.toString()}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
