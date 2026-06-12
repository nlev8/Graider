import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import {
  styles,
  sectionHeadingStyle,
  BORDER,
  GREEN,
  RED,
  TEXT,
  TEXT_DIM,
  LIGHT_TEXT,
  LIGHT_TEXT_DIM,
} from "./district-setup/theme";
import PasswordField from "./district-setup/PasswordField";
import createConfigFormHandlers from "./district-setup/createConfigFormHandlers";
import SisProviderSection from "./district-setup/SisProviderSection";
import AiKeysSection from "./district-setup/AiKeysSection";
import SchoolAdminsSection from "./district-setup/SchoolAdminsSection";
import ConfigSummarySection from "./district-setup/ConfigSummarySection";
import ChangePasswordSection from "./district-setup/ChangePasswordSection";

// CQ wave-5 split: ConfigForm's section markup + handlers moved verbatim to
// ./district-setup/* (theme.js, PasswordField, createConfigFormHandlers,
// *Section components). ConfigForm stays the always-mounted owner of ALL
// config/admin/password state and threads it down via props.

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
        React.createElement(PasswordField, { isDark: isDark,
          value: password,
          onChange: function(e) { setPassword(e.target.value); },
          placeholder: needsSetup ? "Min 8 characters" : "Enter password",
          show: showPass,
          setShow: setShowPass,
          autoComplete: needsSetup ? "new-password" : "current-password",
        }),
        needsSetup ? React.createElement(React.Fragment, null,
          React.createElement("label", { style: styles.label }, "Confirm Password"),
          React.createElement(PasswordField, { isDark: isDark,
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
  var txt = isDark ? TEXT : LIGHT_TEXT;
  var txtDim = isDark ? TEXT_DIM : LIGHT_TEXT_DIM;

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
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "SSO Admin Access"),
    React.createElement("div", { style: styles.helperText }, "Grant district- or school-level admin access to users who sign in through Graider-managed SSO (matched by email at login)"),

    // Current designations list
    admins.length > 0 ? React.createElement("div", { style: { marginTop: "12px" } },
      admins.map(function(a) {
        return React.createElement("div", {
          key: a.email,
          style: Object.assign({}, styles.summaryItem, { alignItems: "center" }),
        },
          React.createElement("span", { style: { color: txt } },
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
    ) : React.createElement("div", { style: { color: txtDim, fontSize: "13px", marginTop: "8px" } }, "No SSO admin designations yet"),

    // Add designation form
    React.createElement("div", { style: { marginTop: "20px", padding: "16px", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid " + BORDER } },
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: txt, marginBottom: "12px" } }, "Add Designation"),

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
  var isDark = !props || props.isDark !== false;
  var txt = isDark ? TEXT : LIGHT_TEXT;
  var txtDim = isDark ? TEXT_DIM : LIGHT_TEXT_DIM;
  var dataState = useState(null);
  var data = dataState[0];
  var setData = dataState[1];

  var loadingState = useState(true);
  var loading = loadingState[0];
  var setLoading = loadingState[1];

  useEffect(function() {
    api.getDistrictAnalytics().then(function(res) {
      setLoading(false);
      if (res) {
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
      React.createElement("div", { style: { fontSize: "24px", fontWeight: "700", color: txt } }, valueText),
      React.createElement("div", { style: { fontSize: "12px", color: txtDim, marginTop: "4px" } }, labelText)
    );
  }

  var body;
  if (loading) {
    body = React.createElement("div", { style: { color: txtDim, fontSize: "13px", marginTop: "8px" } }, "Loading analytics...");
  } else if (!data) {
    body = React.createElement("div", { style: { color: txtDim, fontSize: "13px", marginTop: "8px" } }, "Analytics are not available right now");
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
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: txt, marginTop: "20px", marginBottom: "10px" } }, "Grade Distribution"),
      React.createElement("div", null,
        gradeKeys.map(function(k) {
          var count = grades[k] || 0;
          var pct = maxGrade > 0 ? Math.round((count / maxGrade) * 100) : 0;
          return React.createElement("div", {
            key: k,
            style: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" },
          },
            React.createElement("span", { style: { width: "16px", color: txtDim, fontSize: "13px", fontWeight: "600" } }, k),
            React.createElement("div", { style: { flex: 1, height: "14px", background: "rgba(255,255,255,0.05)", borderRadius: "7px", overflow: "hidden" } },
              React.createElement("div", { style: { width: pct + "%", height: "100%", background: gradeColors[k], borderRadius: "7px" } })
            ),
            React.createElement("span", { style: { width: "32px", textAlign: "right", color: txt, fontSize: "13px" } }, String(count))
          );
        })
      ),

      // Teacher list
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: txt, marginTop: "20px", marginBottom: "10px" } }, "Teachers"),
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
              React.createElement("div", { style: { color: txt, fontSize: "13px", fontWeight: "500" } }, t.name || "Unknown"),
              React.createElement("div", { style: { color: txtDim, fontSize: "12px" } }, t.email || "")
            ),
            React.createElement("div", { style: { color: txtDim, fontSize: "12px", textAlign: "right" } },
              (t.classes_count || 0) + " classes • " + (t.students_count || 0) + " students • " + (t.assessments_count || 0) + " assessments"
            )
          );
        })
      ) : React.createElement("div", { style: { color: txtDim, fontSize: "13px", marginTop: "8px" } }, "No teacher activity yet"),

      // Approximate note
      data.approximate ? React.createElement("div", {
        style: { fontSize: "12px", color: txtDim, marginTop: "12px", fontStyle: "italic" },
      }, "Counts are approximate above 100k rows.") : null
    );
  }

  return React.createElement(React.Fragment, null,
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "District Analytics"),
    React.createElement("div", { style: styles.helperText }, "School-wide rollup across all teachers and assessments"),
    body
  );
}

function ConfigForm(props) {
  var isDark = props.isDark !== false;
  var txt = isDark ? TEXT : LIGHT_TEXT;
  var txtDim = isDark ? TEXT_DIM : LIGHT_TEXT_DIM;
  var inputStyleThemed = isDark ? styles.input : Object.assign({}, styles.input, { background: "#f9f9f9", border: "1px solid #ddd", color: "#333" });
  var radioLabelStyle = isDark ? styles.radioLabel : Object.assign({}, styles.radioLabel, { color: LIGHT_TEXT });
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

  // Handlers moved verbatim to createConfigFormHandlers (CQ wave-5 split);
  // re-created each render with the current state values, exactly as the
  // inline definitions were.
  var handlers = createConfigFormHandlers({
    config: config, sisType: sisType, currentPw: currentPw, newPw: newPw, onLogout: onLogout,
    setConfig: setConfig, setSisSaved: setSisSaved, setKeysSaved: setKeysSaved,
    setSaving: setSaving, setError: setError, setHasKeys: setHasKeys,
    setTesting: setTesting, setTestResult: setTestResult, setShowSecrets: setShowSecrets,
    setPwMsg: setPwMsg, setPwErr: setPwErr, setCurrentPw: setCurrentPw, setNewPw: setNewPw,
  });

  if (loading) {
    return React.createElement("div", { style: styles.page },
      React.createElement("div", { style: styles.card },
        React.createElement("div", { style: { textAlign: "center", color: txtDim } }, "Loading configuration...")
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

      // Section 1: SIS Provider (Clever/OneRoster credentials + test/save)
      React.createElement(SisProviderSection, {
        isDark: isDark, inputStyleThemed: inputStyleThemed, radioLabelStyle: radioLabelStyle,
        sisType: sisType, setSisType: setSisType, setSisSaved: setSisSaved,
        config: config, updateField: handlers.updateField,
        hasKeys: hasKeys, showSecrets: showSecrets, toggleSecret: handlers.toggleSecret,
        applyPreset: handlers.applyPreset,
        handleTestConnection: handlers.handleTestConnection, handleSaveSIS: handlers.handleSaveSIS,
        testing: testing, saving: saving, sisSaved: sisSaved, testResult: testResult,
      }),

      // Section 2: AI API Keys
      React.createElement(AiKeysSection, {
        isDark: isDark, config: config, updateField: handlers.updateField,
        hasKeys: hasKeys, showSecrets: showSecrets, toggleSecret: handlers.toggleSecret,
        handleSaveKeys: handlers.handleSaveKeys, saving: saving, keysSaved: keysSaved,
      }),

      // Shared save-error line (set by both the SIS and AI-keys save handlers)
      error ? React.createElement("div", { style: styles.error }, error) : null,

      // Section 3: School Admins
      React.createElement(SchoolAdminsSection, {
        isDark: isDark, txt: txt, txtDim: txtDim, inputStyleThemed: inputStyleThemed,
        adminList: adminList, setAdminList: setAdminList,
        adminSchoolName: adminSchoolName, setAdminSchoolName: setAdminSchoolName,
        adminTeacherSearch: adminTeacherSearch, setAdminTeacherSearch: setAdminTeacherSearch,
        adminSearchResults: adminSearchResults, setAdminSearchResults: setAdminSearchResults,
        adminManualTeachers: adminManualTeachers, setAdminManualTeachers: setAdminManualTeachers,
        adminInviteCode: adminInviteCode, setAdminInviteCode: setAdminInviteCode,
        searchTimer: searchTimer, setSearchTimer: setSearchTimer,
        creatingInvite: creatingInvite, setCreatingInvite: setCreatingInvite,
      }),

      // Section 3b: SSO Admin Access (Graider-managed SSO designations)
      React.createElement(SsoAdminSection, { isDark: isDark }),

      // Section 3c: District Analytics (school-wide rollup)
      React.createElement(DistrictAnalyticsSection, { isDark: isDark }),

      // Section 4: Configuration Summary
      React.createElement(ConfigSummarySection, { isDark: isDark, sisType: sisType, config: config, hasKeys: hasKeys }),

      // Change Password
      React.createElement(ChangePasswordSection, {
        inputStyleThemed: inputStyleThemed,
        showChangePw: showChangePw, setShowChangePw: setShowChangePw,
        setPwMsg: setPwMsg, setPwErr: setPwErr, pwMsg: pwMsg, pwErr: pwErr,
        currentPw: currentPw, setCurrentPw: setCurrentPw, newPw: newPw, setNewPw: setNewPw,
        handleChangePassword: handlers.handleChangePassword,
      }),

      // Logout
      React.createElement("button", {
        type: "button",
        style: Object.assign({}, styles.btnDanger, { marginTop: "20px" }),
        onClick: handlers.handleLogout,
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
  var txt = isDark ? TEXT : LIGHT_TEXT;
  var txtDim = isDark ? TEXT_DIM : LIGHT_TEXT_DIM;

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
        React.createElement("div", { style: { textAlign: "center", color: txtDim } }, "Loading...")
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
