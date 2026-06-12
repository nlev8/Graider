import React from "react";
import * as api from "../../services/api";
import { styles, sectionHeadingStyle, BORDER, GREEN, TEXT, TEXT_DIM } from "./theme";

// School Admins section (current-admins table + invite-code creation form with
// debounced teacher search). Markup moved verbatim from ConfigForm in
// DistrictSetup.jsx (CQ wave-5 split); every piece of state (admin list,
// search text/results/timer, selected teachers, generated invite) stays in
// ConfigForm and arrives via props so nothing resets if this subtree ever
// becomes conditional.
export default function SchoolAdminsSection(props) {
  var isDark = props.isDark;
  var txt = props.txt;
  var txtDim = props.txtDim;
  var inputStyleThemed = props.inputStyleThemed;
  var adminList = props.adminList;
  var setAdminList = props.setAdminList;
  var adminSchoolName = props.adminSchoolName;
  var setAdminSchoolName = props.setAdminSchoolName;
  var adminTeacherSearch = props.adminTeacherSearch;
  var setAdminTeacherSearch = props.setAdminTeacherSearch;
  var adminSearchResults = props.adminSearchResults;
  var setAdminSearchResults = props.setAdminSearchResults;
  var adminManualTeachers = props.adminManualTeachers;
  var setAdminManualTeachers = props.setAdminManualTeachers;
  var adminInviteCode = props.adminInviteCode;
  var setAdminInviteCode = props.setAdminInviteCode;
  var searchTimer = props.searchTimer;
  var setSearchTimer = props.setSearchTimer;
  var creatingInvite = props.creatingInvite;
  var setCreatingInvite = props.setCreatingInvite;

  return React.createElement(React.Fragment, null,
    // Section 3: School Admins
    React.createElement("div", { style: sectionHeadingStyle(isDark) }, "School Admins"),
    React.createElement("div", { style: styles.helperText }, "Invite teachers to become school-level administrators"),

    // Current admins table
    adminList.length > 0 ? React.createElement("div", { style: { marginTop: "12px" } },
      React.createElement("table", { style: { width: "100%", borderCollapse: "collapse", fontSize: "13px" } },
        React.createElement("thead", null,
          React.createElement("tr", { style: { borderBottom: "1px solid " + BORDER } },
            React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: txtDim, fontWeight: "500" } }, "Name"),
            React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: txtDim, fontWeight: "500" } }, "School"),
            React.createElement("th", { style: { textAlign: "left", padding: "8px 4px", color: txtDim, fontWeight: "500" } }, "Granted"),
            React.createElement("th", { style: { textAlign: "right", padding: "8px 4px" } }, "")
          )
        ),
        React.createElement("tbody", null,
          adminList.map(function(admin) {
            return React.createElement("tr", { key: admin.user_id, style: { borderBottom: "1px solid " + BORDER } },
              React.createElement("td", { style: { padding: "8px 4px", color: txt } }, admin.name || admin.email || "Unknown"),
              React.createElement("td", { style: { padding: "8px 4px", color: txt } }, admin.school || "-"),
              React.createElement("td", { style: { padding: "8px 4px", color: txtDim } }, admin.granted_at ? new Date(admin.granted_at).toLocaleDateString() : "-"),
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
    ) : React.createElement("div", { style: { color: txtDim, fontSize: "13px", marginTop: "8px" } }, "No school admins yet"),

    // Create invite form
    React.createElement("div", { style: { marginTop: "20px", padding: "16px", background: "rgba(255,255,255,0.02)", borderRadius: "10px", border: "1px solid " + BORDER } },
      React.createElement("div", { style: { fontSize: "14px", fontWeight: "600", color: txt, marginBottom: "12px" } }, "Create Admin Invite"),

      React.createElement("label", { style: styles.label }, "School Name"),
      React.createElement("input", {
        style: inputStyleThemed,
        value: adminSchoolName,
        onChange: function(e) { setAdminSchoolName(e.target.value); },
        placeholder: "Lincoln Middle School",
      }),

      React.createElement("label", { style: Object.assign({}, styles.label, { marginTop: "14px" }) }, "Pre-assign Teachers (optional)"),
      React.createElement("input", {
        style: inputStyleThemed,
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
        React.createElement("div", { style: { fontSize: "12px", color: txtDim, marginBottom: "6px" } }, "Invite Code"),
        React.createElement("div", {
          style: { fontSize: "24px", fontWeight: "700", color: GREEN, letterSpacing: "2px", cursor: "pointer", fontFamily: "monospace" },
          title: "Click to copy",
          onClick: function() {
            navigator.clipboard.writeText(adminInviteCode.code);
          },
        }, adminInviteCode.code),
        React.createElement("div", { style: { fontSize: "12px", color: txtDim, marginTop: "8px" } },
          "Expires: " + new Date(adminInviteCode.expires_at).toLocaleDateString() + " \u2022 Click code to copy"
        )
      ) : null
    )
  );
}
