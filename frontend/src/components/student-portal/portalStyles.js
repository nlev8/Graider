// Style constants moved verbatim from StudentPortal.jsx (CQ wave-6 split).
// Every value is a static CSS-variable string with no dependency on component
// state, so hoisting them to module scope is behavior-preserving: light/dark
// theming flows through the CSS vars set by `data-theme` on <body>, exactly
// as it did when these objects were rebuilt inside the component each render.
// (errorBg/errorBorder/errorText were already unused at the time of the split
// — the error banners inline their own var(--danger-*) strings — but they are
// kept to preserve the original surface byte-for-byte.)

export const containerStyle = {
  minHeight: "100vh",
  background: "linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-mid) 50%, var(--bg-gradient-end) 100%)",
  color: "var(--text-primary)",
  fontFamily: "system-ui, -apple-system, sans-serif",
};

export const cardStyle = {
  background: "var(--modal-content-bg)",
  border: "1px solid var(--glass-border)",
  borderRadius: "16px",
  padding: "30px",
  maxWidth: "600px",
  width: "100%",
  margin: "0 auto",
};

export var subtextColor = "var(--text-secondary)";
export var borderColor = "var(--glass-border)";
export var errorBg = "var(--danger-bg)";
export var errorBorder = "var(--danger-border)";
export var errorText = "var(--danger-light)";
export var inputBg = "var(--input-bg)";
export var inputColor = "var(--text-primary)";

export const inputStyle = {
  width: "100%",
  padding: "15px 20px",
  fontSize: "1.2rem",
  border: "2px solid " + borderColor,
  borderRadius: "10px",
  background: inputBg,
  color: inputColor,
  textAlign: "center",
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  outline: "none",
};

export const buttonStyle = {
  padding: "15px 30px",
  fontSize: "1.1rem",
  fontWeight: 600,
  border: "none",
  borderRadius: "10px",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "10px",
  width: "100%",
  background: "linear-gradient(135deg, var(--accent-secondary), var(--accent-primary))",
  color: "white",
};
