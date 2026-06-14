import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AccommodationsImportExport({ addToast, setStudentAccommodations }) {
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
        Import & Export
      </div>
      <div
        style={{
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
        <label
          className="btn btn-secondary"
          style={{ fontSize: "0.85rem", cursor: "pointer" }}
        >
          <Icon name="Upload" size={16} />
          Import from CSV
          <input
            type="file"
            accept=".csv"
            style={{ display: "none" }}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                const result = await api.importAccommodations(
                  file,
                  "student_id",
                  "accommodation_type",
                  "accommodation_notes",
                );
                addToast(
                  "Import complete: " +
                    result.imported +
                    " imported, " +
                    result.skipped +
                    " skipped",
                  "success",
                );
                // Reload accommodations
                const data =
                  await api.getStudentAccommodations();
                if (data.accommodations)
                  setStudentAccommodations(
                    data.accommodations,
                  );
              } catch (err) {
                addToast(
                  "Import failed: " + err.message,
                  "error",
                );
              }
              e.target.value = "";
            }}
          />
        </label>
        <button
          onClick={async () => {
            try {
              const data = await api.exportAccommodations();
              const blob = new Blob(
                [JSON.stringify(data, null, 2)],
                { type: "application/json" },
              );
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download =
                "graider_accommodations_" +
                new Date().toISOString().split("T")[0] +
                ".json";
              a.click();
              URL.revokeObjectURL(url);
            } catch (err) {
              addToast(
                "Export failed: " + err.message,
                "error",
              );
            }
          }}
          className="btn btn-secondary"
          style={{ fontSize: "0.85rem" }}
        >
          <Icon name="Download" size={16} />
          Export Accommodations
        </button>
      </div>
      <p
        style={{
          fontSize: "0.75rem",
          color: "var(--text-muted)",
          marginTop: "10px",
        }}
      >
        CSV should have columns: student_id,
        accommodation_type, accommodation_notes (optional)
      </p>
    </div>
  );
}
