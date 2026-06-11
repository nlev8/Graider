import React from "react";
import Icon from "../Icon";
import { getAuthHeaders } from "../../services/api";
import ExportStudentDataControl from "./ExportStudentDataControl";
import ImportStudentDataControl from "./ImportStudentDataControl";

export default function DataManagementSection(props) {
  const { addToast } = props;
  return (
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Data Management
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <button
                    onClick={async () => {
                      try {
                        const authHdrs = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/data-summary",
                          { headers: { ...authHdrs } },
                        );
                        const data = await response.json();
                        alert(
                          `Data Storage Summary\n\n` +
                            `• Grading Results: ${data.results.count} records\n` +
                            `• Settings: ${data.settings.exists ? "Saved" : "Not saved"}\n` +
                            `• Audit Log: ${data.audit_log.exists ? "Active" : "Not started"}\n\n` +
                            `Data Locations:\n` +
                            data.data_locations.join("\n"),
                        );
                      } catch (err) {
                        addToast(
                          "Failed to fetch data summary",
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Database" size={16} />
                    View Data Summary
                  </button>

                  <button
                    onClick={async () => {
                      try {
                        const authHdrs2 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/export-data",
                          { headers: { ...authHdrs2 } },
                        );
                        const data = await response.json();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `graider_export_${new Date().toISOString().split("T")[0]}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast("Failed to export data", "error");
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export All Data
                  </button>

                  {/* Export Individual Student Data */}
                  <ExportStudentDataControl {...props} />

                  {/* Import Student Data */}
                  <ImportStudentDataControl {...props} />

                  <button
                    onClick={async () => {
                      if (
                        !confirm(
                          "⚠️ DELETE ALL STUDENT DATA?\n\n" +
                            "This will permanently delete:\n" +
                            "• All grading results\n" +
                            "• Current session data\n\n" +
                            "This action cannot be undone.\n\n" +
                            "Type 'DELETE' in the next prompt to confirm.",
                        )
                      )
                        return;

                      const confirmText = prompt(
                        "Type DELETE to confirm:",
                      );
                      if (confirmText !== "DELETE") {
                        addToast("Deletion cancelled", "warning");
                        return;
                      }

                      try {
                        const authHdrs3 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/delete-all-data",
                          {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                              ...authHdrs3,
                            },
                            body: JSON.stringify({ confirm: true }),
                          },
                        );
                        const data = await response.json();
                        if (data.status === "success") {
                          addToast(
                            "All student data has been deleted",
                            "success",
                          );
                          setTimeout(
                            () => window.location.reload(),
                            1000,
                          );
                        } else {
                          addToast(
                            "Error: " + (data.error || "Unknown error"),
                            "error",
                          );
                        }
                      } catch (err) {
                        addToast(
                          "Failed to delete data: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-danger"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Trash2" size={16} />
                    Delete All Data
                  </button>
                </div>
              </div>
  );
}
