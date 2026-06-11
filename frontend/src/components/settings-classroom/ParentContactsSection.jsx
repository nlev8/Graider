import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function ParentContactsSection({ addToast, parentContacts, parentContactsInputRef, setParentContactMapping, setUploadingParentContacts, uploadingParentContacts }) {
  return (
            <div style={{ marginTop: "30px" }}>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Contact"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Parent Contacts
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload class list Excel file with parent email and phone
                columns. Used for Focus export and Outlook email generation.
              </p>

              <input
                ref={parentContactsInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: "none" }}
                onChange={async (e) => {
                  var file = e.target.files?.[0];
                  if (!file) return;
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.previewParentContacts(file);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      var suggested = result.suggested_mapping || {};
                      setParentContactMapping({
                        show: true,
                        preview: result,
                        mapping: {
                          name_col: suggested.name_col || "",
                          name_format: suggested.name_format || "last_first",
                          id_col: suggested.id_col || "",
                          id_strip_digits: suggested.id_strip_digits || 0,
                          contact_cols: suggested.contact_cols || [],
                          period_col: suggested.period_col || "",
                        },
                      });
                    }
                  } catch (err) {
                    addToast("Upload failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                  e.target.value = "";
                }}
              />

              <button
                onClick={() => parentContactsInputRef.current?.click()}
                className="btn btn-secondary"
                disabled={uploadingParentContacts}
                style={{ marginBottom: "15px" }}
              >
                <Icon name="Upload" size={18} />
                {uploadingParentContacts ? "Reading file..." : "Upload Class List (.xlsx, .csv)"}
              </button>

              {parentContacts && parentContacts.count > 0 && (
                <div
                  style={{
                    padding: "12px 15px",
                    background: "var(--input-bg)",
                    borderRadius: "8px",
                    border: "1px solid var(--glass-border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                    {parentContacts.count} students loaded
                  </div>
                  <div style={{ color: "var(--text-secondary)" }}>
                    {parentContacts.with_email} with parent email
                    {parentContacts.without_email > 0 && (
                      <span style={{ color: "#f59e0b" }}>
                        {" "}({parentContacts.without_email} missing email)
                      </span>
                    )}
                  </div>
                  {parentContacts.period_stats && (
                    <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {Object.entries(parentContacts.period_stats).map(function(entry) {
                        return (
                          <span
                            key={entry[0]}
                            style={{
                              padding: "2px 8px",
                              background: "rgba(99,102,241,0.15)",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                            }}
                          >
                            {entry[0]}: {entry[1].total}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
  );
}
