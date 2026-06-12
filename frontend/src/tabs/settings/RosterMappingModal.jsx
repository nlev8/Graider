import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/*
 * RosterMappingModal — the roster CSV column-mapping modal, relocated
 * verbatim from SettingsTab.jsx (CQ wave-9 split). The
 * `{rosterMappingModal.show && ...}` guard became the early return below.
 */
export default function RosterMappingModal({
  rosterMappingModal,
  setRosterMappingModal,
  setRosters,
  addToast,
}) {
  if (!rosterMappingModal.show) return null;

  return (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "500px",
              maxHeight: "80vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                Map Roster Columns
              </h3>
              <button
                onClick={() =>
                  setRosterMappingModal({ show: false, roster: null })
                }
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p
              style={{
                fontSize: "0.9rem",
                color: "var(--text-secondary)",
                marginBottom: "20px",
              }}
            >
              Map your CSV columns to the required fields
            </p>

            {[
              "student_id",
              "student_name",
              "first_name",
              "last_name",
              "student_email",
              "parent_email",
            ].map((field) => (
              <div key={field} style={{ marginBottom: "15px" }}>
                <label
                  className="label"
                  style={{ textTransform: "capitalize" }}
                >
                  {field.replace(/_/g, " ")}
                </label>
                <select
                  className="input"
                  value={
                    rosterMappingModal.roster?.column_mapping?.[
                      field
                    ] || ""
                  }
                  onChange={(e) => {
                    const newMapping = {
                      ...rosterMappingModal.roster?.column_mapping,
                      [field]: e.target.value,
                    };
                    setRosterMappingModal((prev) => ({
                      ...prev,
                      roster: {
                        ...prev.roster,
                        column_mapping: newMapping,
                      },
                    }));
                  }}
                >
                  <option value="">-- Select Column --</option>
                  {(rosterMappingModal.roster?.headers || []).map(
                    (header) => (
                      <option key={header} value={header}>
                        {header}
                      </option>
                    ),
                  )}
                </select>
              </div>
            ))}

            <div
              style={{
                display: "flex",
                gap: "10px",
                marginTop: "20px",
              }}
            >
              <button
                onClick={async () => {
                  try {
                    await api.saveRosterMapping(
                      rosterMappingModal.roster.filename,
                      rosterMappingModal.roster.column_mapping,
                    );
                    const data = await api.listRosters();
                    setRosters(data.rosters || []);
                    setRosterMappingModal({
                      show: false,
                      roster: null,
                    });
                  } catch (err) {
                    addToast(
                      "Error saving mapping: " + err.message,
                      "error",
                    );
                  }
                }}
                className="btn btn-primary"
              >
                <Icon name="Save" size={18} />
                Save Mapping
              </button>
              <button
                onClick={() =>
                  setRosterMappingModal({ show: false, roster: null })
                }
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
  );
}
