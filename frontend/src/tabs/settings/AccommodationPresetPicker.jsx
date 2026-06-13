import React from "react";
import Icon from "../../components/Icon";

/*
 * AccommodationPresetPicker — the "Select Accommodation Presets" checkbox
 * list of the accommodation modal, relocated verbatim from SettingsTab.jsx
 * (CQ wave-9 split). Stateless; selection state stays in
 * useSettingsModalsState and arrives as props.
 */
export default function AccommodationPresetPicker({
  accommodationPresets,
  selectedAccommodationPresets,
  setSelectedAccommodationPresets,
}) {
  return (
            <div style={{ marginBottom: "20px" }}>
              <label className="label">
                Select Accommodation Presets
              </label>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  maxHeight: "200px",
                  overflowY: "auto",
                }}
              >
                {accommodationPresets.map((preset) => (
                  <label
                    key={preset.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      padding: "10px",
                      background: selectedAccommodationPresets.includes(
                        preset.id,
                      )
                        ? "rgba(244, 114, 182, 0.15)"
                        : "var(--input-bg)",
                      borderRadius: "8px",
                      border: selectedAccommodationPresets.includes(
                        preset.id,
                      )
                        ? "1px solid rgba(244, 114, 182, 0.4)"
                        : "1px solid var(--input-border)",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedAccommodationPresets.includes(
                        preset.id,
                      )}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedAccommodationPresets([
                            ...selectedAccommodationPresets,
                            preset.id,
                          ]);
                        } else {
                          setSelectedAccommodationPresets(
                            selectedAccommodationPresets.filter(
                              (id) => id !== preset.id,
                            ),
                          );
                        }
                      }}
                      style={{ marginTop: "2px" }}
                    />
                    <div>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: "0.85rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        <Icon
                          name={preset.icon || "FileText"}
                          size={14}
                          style={{ color: "#f472b6" }}
                        />
                        {preset.name}
                      </div>
                      <div
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          marginTop: "2px",
                        }}
                      >
                        {preset.description}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
  );
}
