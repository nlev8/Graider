import React, { useState, useEffect } from "react";
import * as api from "../services/api";

var PURPLE = "#7c3aed";
var BG = "#0a0a0a";
var CARD_BG = "rgba(255,255,255,0.03)";
var BORDER = "rgba(255,255,255,0.08)";
var TEXT = "#e5e5e5";
var TEXT_DIM = "#999";
var GREEN = "#22c55e";
var RED = "#ef4444";

var styles = {
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

function PasswordField(props) {
  var show = props.show;
  var setShow = props.setShow;
  return React.createElement("div", { style: styles.passwordWrap },
    React.createElement("input", {
      type: show ? "text" : "password",
      value: props.value,
      onChange: props.onChange,
      placeholder: props.placeholder || "",
      style: Object.assign({}, styles.input, { paddingRight: "60px" }),
      autoComplete: props.autoComplete || "off",
    }),
    React.createElement("button", {
      type: "button",
      style: styles.toggleBtn,
      onClick: function() { setShow(!show); },
    }, show ? "Hide" : "Show")
  );
}

function LoginGate(props) {
  var isDark = props.isDark !== false;
  var needsSetup = props.needsSetup;
  var onSuccess = props.onSuccess;
  var error = props.error;
  var setError = props.setError;

  var passState = useState("");
  var password = passState[0];
  var setPassword = passState[1];

  var confirmState = useState("");
  var confirm = confirmState[0];
  var setConfirm = confirmState[1];

  var showState = useState(false);
  var showPass = showState[0];
  var setShowPass = showState[1];

  var loadingState = useState(false);
  var loading = loadingState[0];
  var setLoading = loadingState[1];

  function handleSubmit(e) {
    e.preventDefault();
    if (needsSetup) {
      if (password.length < 8) {
        setError("Password must be at least 8 characters");
        return;
      }
      if (password !== confirm) {
        setError("Passwords do not match");
        return;
      }
    }
    setLoading(true);
    setError("");
    api.districtAuth(password, needsSetup).then(function(res) {
      setLoading(false);
      if (res && res.error) {
        setError(res.error);
      } else {
        onSuccess();
      }
    }).catch(function(err) {
      setLoading(false);
      setError("Connection error");
    });
  }

  var pageStyle = Object.assign({}, styles.page, isDark ? {} : { background: "#f5f5f5" });
  var cardStyle = Object.assign({}, styles.card, isDark ? {} : { background: "#fff", border: "1px solid #e0e0e0", color: "#333" });
  var inputStyleThemed = isDark ? styles.input : Object.assign({}, styles.input, { background: "#f9f9f9", border: "1px solid #ddd", color: "#333" });
  var labelStyleThemed = isDark ? styles.label : Object.assign({}, styles.label, { color: "#555" });

  var toggleThemeBtn = React.createElement("button", {
    onClick: props.toggleTheme,
    style: { position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", fontSize: "1.5rem", padding: "4px" },
    title: isDark ? "Switch to light mode" : "Switch to dark mode",
  }, isDark ? "☀️" : "🌙");

  return React.createElement("div", { style: pageStyle },
    toggleThemeBtn,
    React.createElement("div", { style: cardStyle },
      React.createElement("div", { style: styles.logo },
        React.createElement("img", { src: isDark ? "/graider-brain-dark.png" : "/graider-brain-light.png", alt: "Graider", style: { width: 48, height: 48, marginBottom: 8 } }),
        React.createElement("div", { style: Object.assign({}, styles.logoText, isDark ? {} : { color: "#7c3aed" }) }, "Graider"),
        React.createElement("div", { style: Object.assign({}, styles.subtitle, isDark ? {} : { color: "#888" }) }, "District Administration")
      ),
      React.createElement("h2", { style: Object.assign({}, styles.heading, isDark ? {} : { color: "#333" }) },
        needsSetup ? "Create District Admin Password" : "District Admin Login"
      ),
      React.createElement("form", { onSubmit: handleSubmit },
        React.createElement("label", { style: styles.label }, "Password"),
        React.createElement(PasswordField, {
          value: password,
          onChange: function(e) { setPassword(e.target.value); },
          placeholder: needsSetup ? "Min 8 characters" : "Enter password",
          show: showPass,
          setShow: setShowPass,
          autoComplete: needsSetup ? "new-password" : "current-password",
        }),
        needsSetup ? React.createElement(React.Fragment, null,
          React.createElement("label", { style: styles.label }, "Confirm Password"),
          React.createElement(PasswordField, {
            value: confirm,
            onChange: function(e) { setConfirm(e.target.value); },
            placeholder: "Re-enter password",
            show: showPass,
            setShow: setShowPass,
            autoComplete: "new-password",
          })
        ) : null,
        error ? React.createElement("div", { style: styles.error }, error) : null,
        React.createElement("button", {
          type: "submit",
          style: Object.assign({}, styles.btn, loading ? { opacity: 0.6 } : {}),
          disabled: loading,
        }, loading ? "Authenticating..." : (needsSetup ? "Create Password" : "Log In"))
      )
    )
  );
}

export function SsoAdminSection(props) {
  var isDark = props.isDark !== false;

  var adminsState = useState([]);
  var admins = adminsState[0];
  var setAdmins = adminsState[1];

  var emailState = useState("");
  var email = emailState[0];
  var setEmail = emailState[1];

  var tierState = useState("district");
  var tier = tierState[0];
  var setTier = tierState[1];

  var schoolState = useState("");
  var school = schoolState[0];
  var setSchool = schoolState[1];

  var savingState = useState(false);
  var saving = savingState[0];
  var setSaving = savingState[1];

  var errorState = useState("");
  var error = errorState[0];
  var setError = errorState[1];

  function refresh() {
    api.listSsoAdmins().then(function(res) {
      if (res && res.admins) {
        setAdmins(res.admins);
      }
    }).catch(function() {});
  }

  useEffect(function() {
    refresh();
  }, []);

  function handleAdd() {
    var em = email.trim();
    if (!em) {
      setError("Email is required");
      return;
    }
    if (tier === "school" && !school.trim()) {
      setError("School is required for a School Admin designation");
      return;
    }
    setSaving(true);
    setError("");
    api.addSsoAdmin(em, tier, tier === "school" ? school.trim() : undefined).then(function(res) {
      setSaving(false);
      if (res && res.error) {
        setError(res.error);
        return;
      }
      setEmail("");
      setSchool("");
      refresh();
    }).catch(function() {
      setSaving(false);
      setError("Failed to save designation");
    });
  }

  function handleRemove(targetEmail) {
    api.removeSsoAdmin(targetEmail).then(function(res) {
      if (res && res.error) {
        setError(res.error);
        return;
      }
      refresh();
    }).catch(function() {
      setError("Failed to remove designation");
    });
  }

  var labelStyle = isDark ? styles.label : Object.assign({}, styles.label, { color: "#555" });
  var inputStyle = isDark ? styles.input : Object.assign({}, styles.input, { background: "#f9f9f9", border: "1px solid #ddd", color: "#333" });

  return React.createElement(React.Fragment, null,
    React.createElement("div", { style: styles.sectionHeading }, "SSO Admin Access"),
    React.createElement("div", { style: styles.helperText }, "Grant district- or school-level admin access to users who sign in through Graider-managed SSO (matched by email at login)"),

    // Current designations list
    admins.length > 0 ? React.createElement("div", { style: { marginTop: "12px" } },
      admins.map(function(a) {
        return React.createElement("div", {
          key: a.email,
          style: Object.assign({}, styles.summaryItem, { alignItems: "center" }),
        },
          React.createElement("span", { style: { color: TEXT } },
            a.email,
            " — ",
            a.tier === "district" ? "District Admin" : "School Admin",
            a.school ? (" — " + a.school) : ""
          ),
          React.createElement("button", {
            type: "button",
            style: Object.assign({}, styles.btnDanger, { marginTop: 0, padding: "4px 10px", fontSize: "12px" }),
            onClick: function() { handleRemove(a.email); },
          }, "Remove")
        );
      })
    ) : React.createElement("div", { style: { color: TEXT_DIM, fontSize: "13px", marginTop: "8px" } }, "No SSO admin designations yet"),

    // Add designation form
    React.createElement("div", { style: { marginTop: "20px", padding: "16px", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid " + BORDER } },
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: TEXT, marginBottom: "12px" } }, "Add Designation"),

      React.createElement("label", { style: labelStyle }, "Email"),
      React.createElement("input", {
        style: inputStyle,
        type: "email",
        value: email,
        onChange: function(e) { setEmail(e.target.value); },
        placeholder: "teacher@district.org email",
      }),

      React.createElement("label", { style: Object.assign({}, labelStyle, { marginTop: "12px" }) }, "Access Level"),
      React.createElement("select", {
        style: inputStyle,
        value: tier,
        onChange: function(e) { setTier(e.target.value); },
      },
        React.createElement("option", { value: "district" }, "District Admin"),
        React.createElement("option", { value: "school" }, "School Admin")
      ),

      tier === "school" ? React.createElement(React.Fragment, null,
        React.createElement("label", { style: Object.assign({}, labelStyle, { marginTop: "12px" }) }, "School"),
        React.createElement("input", {
          style: inputStyle,
          value: school,
          onChange: function(e) { setSchool(e.target.value); },
          placeholder: "Lincoln Middle School",
        })
      ) : null,

      React.createElement("button", {
        type: "button",
        style: Object.assign({}, styles.btnSmall, { marginTop: "14px" }, saving ? { opacity: 0.6 } : {}),
        disabled: saving,
        onClick: handleAdd,
      }, saving ? "Saving..." : "Add"),

      error ? React.createElement("div", { style: styles.error }, error) : null
    )
  );
}

export function DistrictAnalyticsSection(props) {
  var isDark = props.isDark !== false;

  var dataState = useState(null);
  var data = dataState[0];
  var setData = dataState[1];

  var loadingState = useState(true);
  var loading = loadingState[0];
  var setLoading = loadingState[1];

  useEffect(function() {
    api.getDistrictAnalytics().then(function(res) {
      setLoading(false);
      if (res && !res.error) {
        setData(res);
      }
    }).catch(function() {
      setLoading(false);
    });
  }, []);

  var gradeColors = { A: GREEN, B: "#84cc16", C: "#eab308", D: "#f97316", F: RED };

  function statCard(labelText, valueText) {
    return React.createElement("div", {
      key: labelText,
      style: {
        flex: "1 1 120px",
        minWidth: "110px",
        padding: "14px",
        background: "rgba(255,255,255,0.03)",
        border: "1px solid " + BORDER,
        borderRadius: "10px",
        textAlign: "center",
      },
    },
      React.createElement("div", { style: { fontSize: "24px", fontWeight: "700", color: TEXT } }, valueText),
      React.createElement("div", { style: { fontSize: "12px", color: TEXT_DIM, marginTop: "4px" } }, labelText)
    );
  }

  var body;
  if (loading) {
    body = React.createElement("div", { style: { color: TEXT_DIM, fontSize: "13px", marginTop: "8px" } }, "Loading analytics...");
  } else if (!data) {
    body = React.createElement("div", { style: { color: TEXT_DIM, fontSize: "13px", marginTop: "8px" } }, "Analytics are not available right now");
  } else {
    var overview = data.overview || {};
    var grades = overview.grade_distribution || {};
    var teachers = data.teachers || [];
    var avg = (overview.average_score === null || overview.average_score === undefined)
      ? "—"
      : (overview.average_score + "%");
    var gradeKeys = ["A", "B", "C", "D", "F"];
    var maxGrade = gradeKeys.reduce(function(m, k) {
      var v = grades[k] || 0;
      return v > m ? v : m;
    }, 0);

    body = React.createElement(React.Fragment, null,
      // Stat cards
      React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "12px" } },
        statCard("Teachers", String(overview.total_teachers || 0)),
        statCard("Students", String(overview.total_students || 0)),
        statCard("Assessments", String(overview.total_assessments || 0)),
        statCard("Average Score", avg)
      ),

      // Grade distribution bars
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: TEXT, marginTop: "20px", marginBottom: "10px" } }, "Grade Distribution"),
      React.createElement("div", null,
        gradeKeys.map(function(k) {
          var count = grades[k] || 0;
          var pct = maxGrade > 0 ? Math.round((count / maxGrade) * 100) : 0;
          return React.createElement("div", {
            key: k,
            style: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" },
          },
            React.createElement("span", { style: { width: "16px", color: TEXT_DIM, fontSize: "13px", fontWeight: "600" } }, k),
            React.createElement("div", { style: { flex: 1, height: "14px", background: "rgba(255,255,255,0.05)", borderRadius: "7px", overflow: "hidden" } },
              React.createElement("div", { style: { width: pct + "%", height: "100%", background: gradeColors[k], borderRadius: "7px" } })
            ),
            React.createElement("span", { style: { width: "32px", textAlign: "right", color: TEXT, fontSize: "13px" } }, String(count))
          );
        })
      ),

      // Teacher list
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: TEXT, marginTop: "20px", marginBottom: "10px" } }, "Teachers"),
      teachers.length > 0 ? React.createElement("div", {
        style: { maxHeight: "260px", overflowY: "auto", border: "1px solid " + BORDER, borderRadius: "10px" },
      },
        teachers.map(function(t) {
          return React.createElement("div", {
            key: t.user_id,
            style: {
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "10px 12px",
              borderBottom: "1px solid " + BORDER,
            },
          },
            React.createElement("div", null,
              React.createElement("div", { style: { color: TEXT, fontSize: "13px", fontWeight: "500" } }, t.name || "Unknown"),
              React.createElement("div", { style: { color: TEXT_DIM, fontSize: "12px" } }, t.email || "")
            ),
            React.createElement("div", { style: { color: TEXT_DIM, fontSize: "12px", textAlign: "right" } },
              (t.classes_count || 0) + " classes • " + (t.students_count || 0) + " students • " + (t.assessments_count || 0) + " assessments"
            )
          );
        })
      ) : React.createElement("div", { style: { color: TEXT_DIM, fontSize: "13px", marginTop: "8px" } }, "No teacher activity yet"),

      // Approximate note
      data.approximate ? React.createElement("div", {
        style: { fontSize: "12px", color: TEXT_DIM, marginTop: "12px", fontStyle: "italic" },
      }, "Counts are approximate above 100k rows.") : null
    );
  }

  return React.createElement(React.Fragment, null,
    React.createElement("div", { style: styles.sectionHeading }, "District Analytics"),
    React.createElement("div", { style: styles.helperText }, "School-wide rollup across all teachers and assessments"),
    body
  );
}

function ConfigForm(props) {
  var isDark = props.isDark !== false;
  var onLogout = props.onLogout;

  var configState = useState({
    sis_type: "clever",
    clever_client_id: "",
    clever_client_secret: "",
    clever_redirect_uri: "",
    clever_district_token: "",
    oneroster_base_url: "",
    oneroster_client_id: "",
    oneroster_client_secret: "",
    oneroster_token_url: "",
    oneroster_school_id: "",
    openai_api_key: "",
    anthropic_api_key: "",
    gemini_api_key: "",
  });
  var config = configState[0];
  var setConfig = configState[1];

  var hasKeysState = useState({ has_openai: false, has_anthropic: false, has_gemini: false });
  var hasKeys = hasKeysState[0];
  var setHasKeys = hasKeysState[1];

  var sisTypeState = useState("clever");
  var sisType = sisTypeState[0];
  var setSisType = sisTypeState[1];

  var loadingState = useState(true);
  var loading = loadingState[0];
  var setLoading = loadingState[1];

  var sisSavedState = useState(false);
  var sisSaved = sisSavedState[0];
  var setSisSaved = sisSavedState[1];

  var keysSavedState = useState(false);
  var keysSaved = keysSavedState[0];
  var setKeysSaved = keysSavedState[1];

  var testResultState = useState(null);
  var testResult = testResultState[0];
  var setTestResult = testResultState[1];

  var testingState = useState(false);
  var testing = testingState[0];
  var setTesting = testingState[1];

  var savingState = useState(false);
  var saving = savingState[0];
  var setSaving = savingState[1];

  var errorState = useState("");
  var error = errorState[0];
  var setError = errorState[1];

  var showSecretsState = useState({});
  var showSecrets = showSecretsState[0];
  var setShowSecrets = showSecretsState[1];

  // School admin invite state
  var adminSchoolState = useState('');
  var adminSchoolName = adminSchoolState[0];
  var setAdminSchoolName = adminSchoolState[1];

  var adminSearchState = useState('');
  var adminTeacherSearch = adminSearchState[0];
  var setAdminTeacherSearch = adminSearchState[1];

  var adminResultsState = useState([]);
  var adminSearchResults = adminResultsState[0];
  var setAdminSearchResults = adminResultsState[1];

  var adminManualState = useState([]);
  var adminManualTeachers = adminManualState[0];
  var setAdminManualTeachers = adminManualState[1];

  var adminCodeState = useState(null);
  var adminInviteCode = adminCodeState[0];
  var setAdminInviteCode = adminCodeState[1];

  var adminListState = useState([]);
  var adminList = adminListState[0];
  var setAdminList = adminListState[1];

  var adminSearchTimer = useState(null);
  var searchTimer = adminSearchTimer[0];
  var setSearchTimer = adminSearchTimer[1];

  var adminCreating = useState(false);
  var creatingInvite = adminCreating[0];
  var setCreatingInvite = adminCreating[1];

  var changePwState = useState(false);
  var showChangePw = changePwState[0];
  var setShowChangePw = changePwState[1];

  var curPwState = useState("");
  var currentPw = curPwState[0];
  var setCurrentPw = curPwState[1];

  var newPwState = useState("");
  var newPw = newPwState[0];
  var setNewPw = newPwState[1];

  var pwMsgState = useState("");
  var pwMsg = pwMsgState[0];
  var setPwMsg = pwMsgState[1];

  var pwErrState = useState("");
  var pwErr = pwErrState[0];
  var setPwErr = pwErrState[1];

  useEffect(function() {
    api.listAdmins().then(function(res) {
      if (res && res.admins) {
        setAdminList(res.admins);
      }
    }).catch(function() {});
    api.getDistrictConfig().then(function(res) {
      setLoading(false);
      if (res && !res.error) {
        var c = res.config || res;
        var type = c.sis_type || "clever";
        setSisType(type);
        setConfig(function(prev) {
          return Object.assign({}, prev, {
            sis_type: type,
            clever_client_id: c.clever_client_id || "",
            clever_client_secret: "",
            clever_redirect_uri: c.clever_redirect_uri || "",
            clever_district_token: "",
            oneroster_base_url: c.oneroster_base_url || "",
            oneroster_client_id: c.oneroster_client_id || "",
            oneroster_client_secret: "",
            oneroster_token_url: c.oneroster_token_url || "",
            oneroster_school_id: c.oneroster_school_id || "",
          });
        });
        setHasKeys({
          has_openai: !!c.has_openai,
          has_anthropic: !!c.has_anthropic,
          has_gemini: !!c.has_gemini,
          has_clever_secret: !!c.has_clever_secret,
          has_clever_token: !!c.has_clever_token,
          has_oneroster_secret: !!c.has_oneroster_secret,
        });
      }
    }).catch(function() {
      setLoading(false);
    });
  }, []);

  function updateField(field, value) {
    setConfig(function(prev) {
      var next = Object.assign({}, prev);
      next[field] = value;
      return next;
    });
    setSisSaved(false);
    setKeysSaved(false);
  }

  function toggleSecret(key) {
    setShowSecrets(function(prev) {
      var next = Object.assign({}, prev);
      next[key] = !prev[key];
      return next;
    });
  }

  function handleSaveSIS() {
    setSaving(true);
    setError("");
    setSisSaved(false);
    var payload = { sis_type: sisType };
    if (sisType === "clever") {
      payload.clever_client_id = config.clever_client_id;
      if (config.clever_client_secret) payload.clever_client_secret = config.clever_client_secret;
      payload.clever_redirect_uri = config.clever_redirect_uri;
      if (config.clever_district_token) payload.clever_district_token = config.clever_district_token;
    } else {
      payload.oneroster_base_url = config.oneroster_base_url;
      payload.oneroster_client_id = config.oneroster_client_id;
      if (config.oneroster_client_secret) payload.oneroster_client_secret = config.oneroster_client_secret;
      payload.oneroster_token_url = config.oneroster_token_url;
      payload.oneroster_school_id = config.oneroster_school_id;
    }
    api.saveDistrictConfig(payload).then(function(res) {
      setSaving(false);
      if (res && res.error) {
        setError(res.error);
      } else {
        setSisSaved(true);
        // Update has_keys indicators
        if (sisType === "clever") {
          setHasKeys(function(prev) {
            return Object.assign({}, prev, {
              has_clever_secret: prev.has_clever_secret || !!config.clever_client_secret,
              has_clever_token: prev.has_clever_token || !!config.clever_district_token,
            });
          });
        } else {
          setHasKeys(function(prev) {
            return Object.assign({}, prev, {
              has_oneroster_secret: prev.has_oneroster_secret || !!config.oneroster_client_secret,
            });
          });
        }
      }
    }).catch(function() {
      setSaving(false);
      setError("Failed to save");
    });
  }

  function handleTestConnection() {
    setTesting(true);
    setTestResult(null);
    api.testDistrictConnection().then(function(res) {
      setTesting(false);
      setTestResult(res);
    }).catch(function() {
      setTesting(false);
      setTestResult({ error: "Connection failed" });
    });
  }

  function handleSaveKeys() {
    setSaving(true);
    setError("");
    setKeysSaved(false);
    var payload = { ai_keys: true };
    if (config.openai_api_key) payload.openai_api_key = config.openai_api_key;
    if (config.anthropic_api_key) payload.anthropic_api_key = config.anthropic_api_key;
    if (config.gemini_api_key) payload.gemini_api_key = config.gemini_api_key;
    api.saveDistrictConfig(payload).then(function(res) {
      setSaving(false);
      if (res && res.error) {
        setError(res.error);
      } else {
        setKeysSaved(true);
        setHasKeys(function(prev) {
          return Object.assign({}, prev, {
            has_openai: prev.has_openai || !!config.openai_api_key,
            has_anthropic: prev.has_anthropic || !!config.anthropic_api_key,
            has_gemini: prev.has_gemini || !!config.gemini_api_key,
          });
        });
      }
    }).catch(function() {
      setSaving(false);
      setError("Failed to save keys");
    });
  }

  function handleChangePassword() {
    setPwMsg("");
    setPwErr("");
    if (newPw.length < 8) {
      setPwErr("New password must be at least 8 characters");
      return;
    }
    api.changeDistrictPassword(currentPw, newPw).then(function(res) {
      if (res && res.error) {
        setPwErr(res.error);
      } else {
        setPwMsg("Password changed successfully");
        setCurrentPw("");
        setNewPw("");
      }
    }).catch(function() {
      setPwErr("Failed to change password");
    });
  }

  function handleLogout() {
    api.districtLogout().then(function() {
      onLogout();
    });
  }

  function applyPreset(preset) {
    if (preset === "classlink") {
      updateField("oneroster_token_url", config.oneroster_base_url.replace(/\/ims\/oneroster\/.*/, "") + "/oauth/token");
    } else if (preset === "powerschool") {
      updateField("oneroster_token_url", config.oneroster_base_url.replace(/\/ws\/.*/, "") + "/oauth/access_token");
    }
  }

  if (loading) {
    return React.createElement("div", { style: styles.page },
      React.createElement("div", { style: styles.card },
        React.createElement("div", { style: { textAlign: "center", color: TEXT_DIM } }, "Loading configuration...")
      )
    );
  }

  var configPageStyle = Object.assign({}, styles.page, isDark ? {} : { background: "#f5f5f5" });
  var configCardStyle = Object.assign({}, styles.configCard, isDark ? {} : { background: "#fff", border: "1px solid #e0e0e0", color: "#333" });

  var toggleThemeBtnConfig = React.createElement("button", {
    onClick: props.toggleTheme,
    style: { position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", fontSize: "1.5rem", padding: "4px" },
    title: isDark ? "Switch to light mode" : "Switch to dark mode",
  }, isDark ? "☀️" : "🌙");

  return React.createElement("div", { style: configPageStyle },
    toggleThemeBtnConfig,
    React.createElement("div", { style: configCardStyle },
      // Header
      React.createElement("div", { style: styles.logo },
        React.createElement("img", { src: isDark ? "/graider-brain-dark.png" : "/graider-brain-light.png", alt: "Graider", style: { width: 48, height: 48, marginBottom: 8 } }),
        React.createElement("div", { style: Object.assign({}, styles.logoText, isDark ? {} : { color: "#7c3aed" }) }, "Graider"),
        React.createElement("div", { style: Object.assign({}, styles.subtitle, isDark ? {} : { color: "#888" }) }, "District Configuration")
      ),

      // Section 1: SIS Provider
      React.createElement("div", { style: styles.sectionHeading }, "SIS Provider"),
      React.createElement("div", { style: styles.radioGroup },
        React.createElement("label", { style: styles.radioLabel },
          React.createElement("input", {
            type: "radio",
            name: "sis_type",
            value: "clever",
            checked: sisType === "clever",
            onChange: function() { setSisType("clever"); setSisSaved(false); },
          }),
          "Clever"
        ),
        React.createElement("label", { style: styles.radioLabel },
          React.createElement("input", {
            type: "radio",
            name: "sis_type",
            value: "oneroster",
            checked: sisType === "oneroster",
            onChange: function() { setSisType("oneroster"); setSisSaved(false); },
          }),
          "OneRoster"
        )
      ),

      // Clever fields
      sisType === "clever" ? React.createElement(React.Fragment, null,
        React.createElement("label", { style: styles.label }, "Client ID"),
        React.createElement("input", {
          style: styles.input,
          value: config.clever_client_id,
          onChange: function(e) { updateField("clever_client_id", e.target.value); },
          placeholder: "Clever application client ID",
        }),
        React.createElement("label", { style: styles.label },
          "Client Secret",
          hasKeys.has_clever_secret ? React.createElement("span", {
            style: Object.assign({}, styles.badge, styles.badgeGreen),
          }, "Saved") : null
        ),
        React.createElement(PasswordField, {
          value: config.clever_client_secret,
          onChange: function(e) { updateField("clever_client_secret", e.target.value); },
          placeholder: hasKeys.has_clever_secret ? "Leave blank to keep current" : "Clever client secret",
          show: !!showSecrets.clever_secret,
          setShow: function() { toggleSecret("clever_secret"); },
        }),
        React.createElement("label", { style: styles.label }, "Redirect URI"),
        React.createElement("input", {
          style: styles.input,
          value: config.clever_redirect_uri,
          onChange: function(e) { updateField("clever_redirect_uri", e.target.value); },
          placeholder: "https://app.graider.live/api/clever/callback",
        }),
        React.createElement("label", { style: styles.label },
          "District Token (optional)",
          hasKeys.has_clever_token ? React.createElement("span", {
            style: Object.assign({}, styles.badge, styles.badgeGreen),
          }, "Saved") : null
        ),
        React.createElement(PasswordField, {
          value: config.clever_district_token,
          onChange: function(e) { updateField("clever_district_token", e.target.value); },
          placeholder: hasKeys.has_clever_token ? "Leave blank to keep current" : "For Secure Sync (optional)",
          show: !!showSecrets.clever_token,
          setShow: function() { toggleSecret("clever_token"); },
        })
      ) : null,

      // OneRoster fields
      sisType === "oneroster" ? React.createElement(React.Fragment, null,
        React.createElement("label", { style: styles.label }, "Base URL"),
        React.createElement("input", {
          style: styles.input,
          value: config.oneroster_base_url,
          onChange: function(e) { updateField("oneroster_base_url", e.target.value); },
          placeholder: "https://sis.district.org/ims/oneroster/v1p1",
        }),
        React.createElement("label", { style: styles.label }, "Client ID"),
        React.createElement("input", {
          style: styles.input,
          value: config.oneroster_client_id,
          onChange: function(e) { updateField("oneroster_client_id", e.target.value); },
          placeholder: "OAuth 2.0 client ID",
        }),
        React.createElement("label", { style: styles.label },
          "Client Secret",
          hasKeys.has_oneroster_secret ? React.createElement("span", {
            style: Object.assign({}, styles.badge, styles.badgeGreen),
          }, "Saved") : null
        ),
        React.createElement(PasswordField, {
          value: config.oneroster_client_secret,
          onChange: function(e) { updateField("oneroster_client_secret", e.target.value); },
          placeholder: hasKeys.has_oneroster_secret ? "Leave blank to keep current" : "OAuth 2.0 client secret",
          show: !!showSecrets.oneroster_secret,
          setShow: function() { toggleSecret("oneroster_secret"); },
        }),
        React.createElement("label", { style: styles.label }, "Token URL (optional)"),
        React.createElement("input", {
          style: styles.input,
          value: config.oneroster_token_url,
          onChange: function(e) { updateField("oneroster_token_url", e.target.value); },
          placeholder: "Auto-detected if blank",
        }),
        React.createElement("div", null,
          React.createElement("button", {
            type: "button",
            style: styles.presetBtn,
            onClick: function() { applyPreset("classlink"); },
          }, "ClassLink"),
          React.createElement("button", {
            type: "button",
            style: styles.presetBtn,
            onClick: function() { applyPreset("powerschool"); },
          }, "PowerSchool")
        ),
        React.createElement("label", { style: styles.label }, "School ID (optional)"),
        React.createElement("input", {
          style: styles.input,
          value: config.oneroster_school_id,
          onChange: function(e) { updateField("oneroster_school_id", e.target.value); },
          placeholder: "sourcedId to scope roster",
        })
      ) : null,

      // Test + Save buttons for SIS
      React.createElement("div", { style: { display: "flex", gap: "10px", marginTop: "16px" } },
        React.createElement("button", {
          type: "button",
          style: Object.assign({}, styles.btnSmall, { flex: 1 }),
          onClick: handleTestConnection,
          disabled: testing,
        }, testing ? "Testing..." : "Test Connection"),
        React.createElement("button", {
          type: "button",
          style: Object.assign({}, styles.btnSmall, { flex: 1 }),
          onClick: handleSaveSIS,
          disabled: saving,
        }, saving ? "Saving..." : "Save SIS Config")
      ),
      sisSaved ? React.createElement("span", {
        style: Object.assign({}, styles.badge, styles.badgeGreen, { marginTop: "8px", display: "inline-block" }),
      }, "Saved") : null,
      testResult ? React.createElement("div", {
        style: testResult.error ? styles.error : styles.success,
      }, testResult.error ? "Error: " + testResult.error : "Connection successful") : null,

      // Section 2: AI API Keys
      React.createElement("div", { style: styles.sectionHeading }, "AI API Keys"),
      React.createElement("div", { style: styles.helperText }, "Teachers can override with their own keys in Settings"),

      React.createElement("label", { style: styles.label },
        "OpenAI API Key",
        hasKeys.has_openai ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, {
        value: config.openai_api_key,
        onChange: function(e) { updateField("openai_api_key", e.target.value); },
        placeholder: hasKeys.has_openai ? "Leave blank to keep current" : "sk-...",
        show: !!showSecrets.openai,
        setShow: function() { toggleSecret("openai"); },
      }),

      React.createElement("label", { style: styles.label },
        "Anthropic API Key",
        hasKeys.has_anthropic ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, {
        value: config.anthropic_api_key,
        onChange: function(e) { updateField("anthropic_api_key", e.target.value); },
        placeholder: hasKeys.has_anthropic ? "Leave blank to keep current" : "sk-ant-...",
        show: !!showSecrets.anthropic,
        setShow: function() { toggleSecret("anthropic"); },
      }),

      React.createElement("label", { style: styles.label },
        "Gemini API Key",
        hasKeys.has_gemini ? React.createElement("span", {
          style: Object.assign({}, styles.badge, styles.badgeGreen),
        }, "Saved") : null
      ),
      React.createElement(PasswordField, {
        value: config.gemini_api_key,
        onChange: function(e) { updateField("gemini_api_key", e.target.value); },
        placeholder: hasKeys.has_gemini ? "Leave blank to keep current" : "AIza...",
        show: !!showSecrets.gemini,
        setShow: function() { toggleSecret("gemini"); },
      }),

      React.createElement("button", {
        type: "button",
        style: styles.btnSmall,
        onClick: handleSaveKeys,
        disabled: saving,
      }, saving ? "Saving..." : "Save Keys"),
      keysSaved ? React.createElement("span", {
        style: Object.assign({}, styles.badge, styles.badgeGreen, { marginLeft: "10px" }),
      }, "Saved") : null,

      error ? React.createElement("div", { style: styles.error }, error) : null,

      // Section 3: School Admins
      React.createElement("div", { style: styles.sectionHeading }, "School Admins"),
      React.createElement("div", { style: styles.helperText }, "Invite teachers to become school-level administrators"),

      // Current admins table
      adminList.length > 0 ? React.createElement("div", { style: { marginTop: "12px" } },
        React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "13px" } },
          React.createElement("thead", null,
            React.createElement("tr", { style: { borderBottom: "1px solid " + BORDER } },
              React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: TEXT_DIM, fontWeight: "500" } }, "Name"),
              React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: TEXT_DIM, fontWeight: "500" } }, "School"),
              React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: TEXT_DIM, fontWeight: "500" } }, "Granted"),
              React.createElement("th", { style: { textAlign: "right", padding: "8px 4px" } }, "")
            )
          ),
          React.createElement("tbody", null,
            adminList.map(function(admin) {
              return React.createElement("tr", { key: admin.user_id, style: { borderBottom: "1px solid " + BORDER } },
                React.createElement("td", { style: { padding: "8px 4px", color: TEXT } }, admin.name || admin.email || "Unknown"),
                React.createElement("td", { style: { padding: "8px 4px", color: TEXT } }, admin.school || "-"),
                React.createElement("td", { style: { padding: "8px 4px", color: TEXT_DIM } }, admin.granted_at ? new Date(admin.granted_at).toLocaleDateString() : "-"),
                React.createElement("td", { style: { padding: "8px 4px", textAlign: "right" } },
                  React.createElement("button", {
                    type: "button",
                    style: Object.assign({}, styles.btnDanger, { marginTop: 0, padding: "4px 10px", fontSize: "12px" }),
                    onClick: function() {
                      if (confirm("Revoke admin access for " + (admin.name || admin.email || "this user") + "?")) {
                        api.revokeAdmin(admin.user_id).then(function(res) {
                          if (res && !res.error) {
                            setAdminList(function(prev) {
                              return prev.filter(function(a) { return a.user_id !== admin.user_id; });
                            });
                          }
                        }).catch(function() {});
                      }
                    },
                  }, "Revoke")
                )
              );
            })
          )
        )
      ) : React.createElement("div", { style: { color: TEXT_DIM, fontSize: "13px", marginTop: "8px" } }, "No school admins yet"),

      // Create invite form
      React.createElement("div", { style: { marginTop: "20px", padding: "16px", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid " + BORDER } },
        React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: TEXT, marginBottom: "12px" } }, "Create Admin Invite"),

        React.createElement("label", { style: styles.label }, "School Name"),
        React.createElement("input", {
          style: styles.input,
          value: adminSchoolName,
          onChange: function(e) { setAdminSchoolName(e.target.value); },
          placeholder: "Lincoln Middle School",
        }),

        React.createElement("label", { style: Object.assign({}, styles.label, { marginTop: "14px" }) }, "Pre-assign Teachers (optional)"),
        React.createElement("input", {
          style: styles.input,
          value: adminTeacherSearch,
          onChange: function(e) {
            var val = e.target.value;
            setAdminTeacherSearch(val);
            if (searchTimer) clearTimeout(searchTimer);
            if (val.length >= 2) {
              setSearchTimer(setTimeout(function() {
                api.searchTeachers(val).then(function(res) {
                  setAdminSearchResults(res.teachers || []);
                }).catch(function() { setAdminSearchResults([]); });
              }, 300));
            } else {
              setAdminSearchResults([]);
            }
          },
          placeholder: "Search by name or email...",
        }),

        // Search results dropdown
        adminSearchResults.length > 0 ? React.createElement("div", {
          style: { background: "rgba(255,255,255,0.06)", border: "1px solid " + BORDER, borderRadius: "8px", marginTop: "4px", maxHeight: "150px", overflowY: "auto" },
        },
          adminSearchResults.map(function(teacher) {
            var alreadyAdded = adminManualTeachers.some(function(t) { return t.id === teacher.id; });
            return React.createElement("div", {
              key: teacher.id,
              style: { padding: "8px 12px", cursor: alreadyAdded ? "default" : "pointer", color: alreadyAdded ? TEXT_DIM : TEXT, fontSize: "13px", borderBottom: "1px solid " + BORDER },
              onClick: function() {
                if (alreadyAdded) return;
                setAdminManualTeachers(function(prev) { return prev.concat([teacher]); });
                setAdminTeacherSearch('');
                setAdminSearchResults([]);
              },
            }, (teacher.name || teacher.email) + (alreadyAdded ? " (added)" : ""));
          })
        ) : null,

        // Selected teachers chips
        adminManualTeachers.length > 0 ? React.createElement("div", { style: { display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" } },
          adminManualTeachers.map(function(teacher) {
            return React.createElement("span", {
              key: teacher.id,
              style: { display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 10px", background: "rgba(99,102,241,0.15)", color: "#a5b4fc", borderRadius: "12px", fontSize: "12px" },
            },
              teacher.name || teacher.email,
              React.createElement("button", {
                type: "button",
                style: { background: "none", border: "none", color: "#a5b4fc", cursor: "pointer", fontSize: "14px", padding: "0 2px", lineHeight: "1" },
                onClick: function() {
                  setAdminManualTeachers(function(prev) {
                    return prev.filter(function(t) { return t.id !== teacher.id; });
                  });
                },
              }, "\u00d7")
            );
          })
        ) : null,

        React.createElement("button", {
          type: "button",
          style: Object.assign({}, styles.btnSmall, { marginTop: "14px" }, creatingInvite ? { opacity: 0.6 } : {}),
          disabled: creatingInvite || !adminSchoolName.trim(),
          onClick: function() {
            setCreatingInvite(true);
            setAdminInviteCode(null);
            var teacherIds = adminManualTeachers.map(function(t) { return t.id; });
            api.createAdminInvite(adminSchoolName.trim(), teacherIds).then(function(res) {
              setCreatingInvite(false);
              if (res && res.code) {
                setAdminInviteCode(res);
                // Refresh admin list
                api.listAdmins().then(function(r) {
                  if (r && r.admins) setAdminList(r.admins);
                }).catch(function() {});
              }
            }).catch(function() {
              setCreatingInvite(false);
            });
          },
        }, creatingInvite ? "Generating..." : "Generate Invite Code"),

        // Generated invite code display
        adminInviteCode ? React.createElement("div", {
          style: { marginTop: "16px", padding: "16px", background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)", borderRadius: "10px", textAlign: "center" },
        },
          React.createElement("div", { style: { fontSize: "12px", color: TEXT_DIM, marginBottom: "6px" } }, "Invite Code"),
          React.createElement("div", {
            style: { fontSize: "24px", fontWeight: "700", color: GREEN, letterSpacing: "2px", cursor: "pointer", fontFamily: "monospace" },
            title: "Click to copy",
            onClick: function() {
              navigator.clipboard.writeText(adminInviteCode.code);
            },
          }, adminInviteCode.code),
          React.createElement("div", { style: { fontSize: "12px", color: TEXT_DIM, marginTop: "8px" } },
            "Expires: " + new Date(adminInviteCode.expires_at).toLocaleDateString() + " \u2022 Click code to copy"
          )
        ) : null
      ),

      // Section 3b: SSO Admin Access (Graider-managed SSO designations)
      React.createElement(SsoAdminSection, { isDark: isDark }),

      // Section 3c: District Analytics (school-wide rollup)
      React.createElement(DistrictAnalyticsSection, { isDark: isDark }),

      // Section 4: Configuration Summary + Logout
      React.createElement("div", { style: styles.sectionHeading }, "Configuration Summary"),

      React.createElement("div", { style: styles.summaryItem },
        React.createElement("span", null, "SIS Provider"),
        React.createElement("span", { style: { fontWeight: "600" } }, sisType === "clever" ? "Clever" : "OneRoster")
      ),
      React.createElement("div", { style: styles.summaryItem },
        React.createElement("span", null, "SIS Credentials"),
        React.createElement("span", null,
          (sisType === "clever" ? (config.clever_client_id ? "Configured" : "Not set") : (config.oneroster_base_url ? "Configured" : "Not set"))
        )
      ),
      React.createElement("div", { style: styles.summaryItem },
        React.createElement("span", null, "OpenAI"),
        React.createElement("span", null, hasKeys.has_openai ? "Configured" : "Not set")
      ),
      React.createElement("div", { style: styles.summaryItem },
        React.createElement("span", null, "Anthropic"),
        React.createElement("span", null, hasKeys.has_anthropic ? "Configured" : "Not set")
      ),
      React.createElement("div", { style: styles.summaryItem },
        React.createElement("span", null, "Gemini"),
        React.createElement("span", null, hasKeys.has_gemini ? "Configured" : "Not set")
      ),

      // Change Password
      React.createElement("div", { style: { marginTop: "20px" } },
        React.createElement("button", {
          type: "button",
          style: styles.btnOutline,
          onClick: function() { setShowChangePw(!showChangePw); setPwMsg(""); setPwErr(""); },
        }, showChangePw ? "Cancel" : "Change Password"),
        showChangePw ? React.createElement("div", { style: { marginTop: "12px" } },
          React.createElement("label", { style: styles.label }, "Current Password"),
          React.createElement("input", {
            type: "password",
            style: styles.input,
            value: currentPw,
            onChange: function(e) { setCurrentPw(e.target.value); },
          }),
          React.createElement("label", { style: styles.label }, "New Password"),
          React.createElement("input", {
            type: "password",
            style: styles.input,
            value: newPw,
            onChange: function(e) { setNewPw(e.target.value); },
            placeholder: "Min 8 characters",
          }),
          React.createElement("button", {
            type: "button",
            style: styles.btnSmall,
            onClick: handleChangePassword,
          }, "Update Password"),
          pwMsg ? React.createElement("div", { style: styles.success }, pwMsg) : null,
          pwErr ? React.createElement("div", { style: styles.error }, pwErr) : null
        ) : null
      ),

      // Logout
      React.createElement("button", {
        type: "button",
        style: Object.assign({}, styles.btnDanger, { marginTop: "20px" }),
        onClick: handleLogout,
      }, "Log Out")
    )
  );
}

export default function DistrictSetup() {
  var authState = useState(false);
  var authenticated = authState[0];
  var setAuthenticated = authState[1];

  var needsSetupState = useState(null);
  var themeState = useState(function() {
    return localStorage.getItem('graider_district_theme') || 'dark';
  });
  var districtTheme = themeState[0];
  var setDistrictTheme = themeState[1];
  var isDark = districtTheme !== 'light';

  var needsSetup = needsSetupState[0];
  var setNeedsSetup = needsSetupState[1];

  var checkingState = useState(true);
  var checking = checkingState[0];
  var setChecking = checkingState[1];

  var errorState = useState("");
  var error = errorState[0];
  var setError = errorState[1];

  useEffect(function() {
    // Check if already authenticated or needs first-time setup
    api.getDistrictConfigStatus().then(function(res) {
      setChecking(false);
      if (res && res.needs_setup) {
        setNeedsSetup(true);
      } else {
        setNeedsSetup(false);
      }
      // Try loading config to see if session is active
      api.getDistrictConfig().then(function(cfgRes) {
        if (cfgRes && !cfgRes.error) {
          setAuthenticated(true);
        }
      }).catch(function() {});
    }).catch(function() {
      setChecking(false);
      setNeedsSetup(true);
    });
  }, []);

  if (checking) {
    return React.createElement("div", { style: styles.page },
      React.createElement("div", { style: styles.card },
        React.createElement("div", { style: { textAlign: "center", color: TEXT_DIM } }, "Loading...")
      )
    );
  }

  if (!authenticated) {
    return React.createElement(LoginGate, {
      needsSetup: needsSetup,
      onSuccess: function() { setAuthenticated(true); },
      error: error,
      setError: setError,
      isDark: isDark,
      toggleTheme: function() {
        var next = isDark ? "light" : "dark";
        setDistrictTheme(next);
        localStorage.setItem("graider_district_theme", next);
      },
    });
  }

  return React.createElement(ConfigForm, {
    onLogout: function() { setAuthenticated(false); },
    isDark: isDark,
    toggleTheme: function() {
      var next = isDark ? "light" : "dark";
      setDistrictTheme(next);
      localStorage.setItem("graider_district_theme", next);
    },
  });
}
