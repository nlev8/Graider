import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function PeriodUploadControls({ addToast, focusImportProgress, focusImporting, newPeriodName, periodInputRef, setFocusImportProgress, setFocusImporting, setNewPeriodName, setPeriods, setUploadingPeriod, uploadingPeriod }) {
  return (
    <>
      <input
        ref={periodInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        style={{ display: "none" }}
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          if (!newPeriodName.trim()) {
            addToast(
              "Please enter a period name first",
              "warning",
            );
            e.target.value = "";
            return;
          }
          setUploadingPeriod(true);
          try {
            const result = await api.uploadPeriod(
              file,
              newPeriodName,
            );
            if (result.error) {
              addToast(result.error, "error");
            } else {
              const periodsData = await api.listPeriods();
              setPeriods(periodsData.periods || []);
              setNewPeriodName("");
            }
          } catch (err) {
            addToast("Upload failed: " + err.message, "error");
          }
          setUploadingPeriod(false);
          e.target.value = "";
        }}
      />

      <div
        style={{
          display: "flex",
          gap: "10px",
          marginBottom: "15px",
        }}
      >
        <input
          type="text"
          className="input"
          placeholder="Period name (e.g., Period 1, Block A)"
          value={newPeriodName}
          onChange={(e) => setNewPeriodName(e.target.value)}
          style={{ maxWidth: "250px" }}
        />
        <button
          onClick={() => periodInputRef.current?.click()}
          className="btn btn-secondary"
          disabled={uploadingPeriod || !newPeriodName.trim()}
          style={{
            opacity:
              !newPeriodName.trim() || uploadingPeriod
                ? 0.5
                : 1,
            cursor:
              !newPeriodName.trim() || uploadingPeriod
                ? "not-allowed"
                : "pointer",
          }}
          title={
            !newPeriodName.trim()
              ? "Enter a period name first"
              : ""
          }
        >
          <Icon name="Upload" size={18} />
          {uploadingPeriod
            ? "Uploading..."
            : "Upload CSV/Excel"}
        </button>
        <div style={{ position: "relative" }}>
          <button
            className="btn"
            onClick={(e) => {
              e.stopPropagation();
              const el = e.currentTarget.nextElementSibling;
              if (el) el.style.display = el.style.display === "none" ? "block" : "none";
            }}
            style={{ padding: "8px", minWidth: 0, borderRadius: "50%", width: "36px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center" }}
            title="How to export roster from Focus"
          >
            <Icon name="HelpCircle" size={18} style={{ color: "var(--accent-primary)" }} />
          </button>
          <div style={{ display: "none", position: "absolute", top: "42px", right: 0, zIndex: 100, width: "320px", background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "12px", padding: "16px", boxShadow: "0 8px 30px rgba(0,0,0,0.3)" }}>
            <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
              <Icon name="FileSpreadsheet" size={16} style={{ color: "var(--accent-primary)" }} />
              Export from Focus SIS
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
              <p style={{ margin: "0 0 6px" }}><strong>Reports {'>'} Student Listings {'>'} CSV</strong></p>
              <p style={{ margin: "0 0 6px" }}>Required columns: Student ID, First Name, Last Name, Email</p>
              <p style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>Column names are detected automatically (e.g. "student_id", "StudentID", or "Student ID" all work).</p>
              <p style={{ margin: 0, color: "var(--text-muted)" }}>Combined "Student Name" columns with "Last, First" format are also supported.</p>
            </div>
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "15px" }}>
        {!newPeriodName.trim() && (
          <p
            style={{
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              margin: 0,
            }}
          >
            Enter a period name above, then click Upload
          </p>
        )}
        <button
          onClick={async () => {
            if (focusImporting) return;
            setFocusImporting(true);
            setFocusImportProgress("Starting Focus import...");
            try {
              const res = await api.importFromFocus();
              if (res.error) {
                addToast(res.error, "error");
                setFocusImporting(false);
                return;
              }
              // Poll for status
              const pollInterval = setInterval(async () => {
                try {
                  const status = await api.getFocusImportStatus();
                  setFocusImportProgress(status.progress || "");
                  if (status.status === "completed") {
                    clearInterval(pollInterval);
                    setFocusImporting(false);
                    setFocusImportProgress("");
                    const r = status.result || {};
                    addToast("Imported " + (r.periods_imported || 0) + " periods, " + (r.total_students || 0) + " students, " + (r.total_contacts || 0) + " parent contacts", "success");
                    const periodsData = await api.listPeriods();
                    setPeriods(periodsData.periods || []);
                  } else if (status.status === "failed") {
                    clearInterval(pollInterval);
                    setFocusImporting(false);
                    setFocusImportProgress("");
                    addToast("Focus import failed: " + (status.error || "Unknown error"), "error");
                  }
                } catch (err) {
                  clearInterval(pollInterval);
                  setFocusImporting(false);
                  setFocusImportProgress("");
                }
              }, 2000);
            } catch (err) {
              addToast("Failed to start Focus import: " + err.message, "error");
              setFocusImporting(false);
              setFocusImportProgress("");
            }
          }}
          className="btn btn-secondary"
          disabled={focusImporting}
          style={{ marginLeft: "auto", opacity: focusImporting ? 0.6 : 1, whiteSpace: "nowrap" }}
        >
          <Icon name="Download" size={18} />
          {focusImporting ? "Importing..." : "Import from Focus"}
        </button>
      </div>

      {/* Focus import progress banner */}
      {focusImporting && focusImportProgress && (
        <div style={{
          padding: "10px 15px",
          marginBottom: "15px",
          background: "rgba(59, 130, 246, 0.1)",
          border: "1px solid rgba(59, 130, 246, 0.3)",
          borderRadius: "8px",
          fontSize: "0.85rem",
          color: "#60a5fa",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}>
          <Icon name="Loader" size={16} style={{ animation: "spin 1s linear infinite" }} />
          {focusImportProgress}
        </div>
      )}
    </>
  );
}
