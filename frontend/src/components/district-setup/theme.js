// Shared style constants for the district-setup surface. Moved verbatim from
// DistrictSetup.jsx in the CQ wave-5 split (ConfigForm 761 LOC → sections in
// this directory) so the extracted section components and the parent can share
// one source of truth without a circular import.
export var PURPLE = "#7c3aed";
export var BG = "#0a0a0a";
export var CARD_BG = "rgba(255,255,255,0.03)";
export var BORDER = "rgba(255,255,255,0.08)";
export var TEXT = "#e5e5e5";
export var TEXT_DIM = "#999";
export var GREEN = "#22c55e";
export var RED = "#ef4444";

export var styles = {
  page: {
    minHeight: "100vh",
    background: BG,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    color: TEXT,
    padding: "20px",
  },
  card: {
    background: CARD_BG,
    border: "1px solid " + BORDER,
    borderRadius: "16px",
    padding: "32px",
    width: "100%",
    maxWidth: "520px",
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
  },
  configCard: {
    background: CARD_BG,
    border: "1px solid " + BORDER,
    borderRadius: "16px",
    padding: "32px",
    width: "100%",
    maxWidth: "680px",
    maxHeight: "85vh",
    overflowY: "auto",
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
  },
  logo: {
    textAlign: "center",
    marginBottom: "24px",
  },
  logoText: {
    fontSize: "28px",
    fontWeight: "700",
    color: PURPLE,
    letterSpacing: "-0.5px",
  },
  subtitle: {
    fontSize: "13px",
    color: TEXT_DIM,
    marginTop: "4px",
  },
  heading: {
    fontSize: "20px",
    fontWeight: "600",
    marginBottom: "20px",
    color: TEXT,
  },
  sectionHeading: {
    fontSize: "16px",
    fontWeight: "600",
    marginBottom: "12px",
    marginTop: "28px",
    color: TEXT,
    borderBottom: "1px solid " + BORDER,
    paddingBottom: "8px",
  },
  label: {
    display: "block",
    fontSize: "13px",
    fontWeight: "500",
    color: TEXT_DIM,
    marginBottom: "6px",
    marginTop: "12px",
  },
  input: {
    width: "100%",
    padding: "10px 12px",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid " + BORDER,
    borderRadius: "8px",
    color: TEXT,
    fontSize: "14px",
    outline: "none",
    boxSizing: "border-box",
  },
  passwordWrap: {
    position: "relative",
    width: "100%",
  },
  toggleBtn: {
    position: "absolute",
    right: "8px",
    top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    color: TEXT_DIM,
    cursor: "pointer",
    fontSize: "12px",
    padding: "4px 8px",
  },
  btn: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "10px 20px",
    background: PURPLE,
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    fontSize: "14px",
    fontWeight: "600",
    cursor: "pointer",
    marginTop: "16px",
    width: "100%",
  },
  btnSmall: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 16px",
    background: PURPLE,
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: "500",
    cursor: "pointer",
    marginTop: "12px",
  },
  btnOutline: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 16px",
    background: "transparent",
    color: TEXT_DIM,
    border: "1px solid " + BORDER,
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: "500",
    cursor: "pointer",
    marginTop: "12px",
  },
  btnDanger: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "8px 16px",
    background: "rgba(239,68,68,0.15)",
    color: RED,
    border: "1px solid rgba(239,68,68,0.3)",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: "500",
    cursor: "pointer",
    marginTop: "12px",
  },
  presetBtn: {
    display: "inline-block",
    padding: "6px 14px",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid " + BORDER,
    borderRadius: "6px",
    color: TEXT_DIM,
    fontSize: "12px",
    cursor: "pointer",
    marginRight: "8px",
    marginTop: "8px",
  },
  badge: {
    display: "inline-block",
    padding: "4px 10px",
    borderRadius: "12px",
    fontSize: "12px",
    fontWeight: "600",
    marginLeft: "8px",
  },
  badgeGreen: {
    background: "rgba(34,197,94,0.15)",
    color: GREEN,
  },
  badgeRed: {
    background: "rgba(239,68,68,0.15)",
    color: RED,
  },
  error: {
    color: RED,
    fontSize: "13px",
    marginTop: "8px",
  },
  success: {
    color: GREEN,
    fontSize: "13px",
    marginTop: "8px",
  },
  helperText: {
    fontSize: "12px",
    color: TEXT_DIM,
    marginTop: "4px",
  },
  radioGroup: {
    display: "flex",
    gap: "16px",
    marginTop: "8px",
    marginBottom: "12px",
  },
  radioLabel: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    cursor: "pointer",
    fontSize: "14px",
    color: TEXT,
  },
  summaryItem: {
    display: "flex",
    justifyContent: "space-between",
    padding: "8px 0",
    borderBottom: "1px solid " + BORDER,
    fontSize: "13px",
  },
};

export var LIGHT_TEXT = "#333";
export var LIGHT_TEXT_DIM = "#666";
export var LIGHT_BORDER = "#e0e0e0";

// Section headings (and several body text nodes) hardcode the dark-mode
// TEXT/TEXT_DIM constants. On the light-mode white card that renders
// white-on-white (invisible). Theme them per the established isDark pattern.
export function sectionHeadingStyle(isDark) {
  return isDark
    ? styles.sectionHeading
    : Object.assign({}, styles.sectionHeading, { color: LIGHT_TEXT, borderBottom: "1px solid " + LIGHT_BORDER });
}
