import React from "react";

// Class Selection + Period Selection (period only shown when NOT publishing
// to a class). JSX moved verbatim from PublishContentModal.jsx (CQ wave-7
// split); the inner `{!classId && (...)}` conditional is preserved as-is.
export default function ClassPeriodSection({
  classId,
  setClassId,
  teacherClasses,
  settings,
  setSettings,
  periods,
  onPeriodChange,
}) {
  return (
    <>
      {/* Class Selection */}
      <div style={{ marginBottom: "15px" }}>
        <label className="label" style={{ marginBottom: "6px" }}>Publish to Class (optional)</label>
        <select className="input" value={classId} onChange={(e) => setClassId(e.target.value)} style={{ width: "100%", background: "rgba(255,255,255,0.08)", color: "#e2e8f0", border: "1px solid rgba(255,255,255,0.2)", borderRadius: "8px" }}>
          <option value="">Join Code Only (no class)</option>
          {teacherClasses.map((cls) => (
            <option key={cls.id} value={cls.id}>{cls.name} ({cls.join_code})</option>
          ))}
        </select>
        <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
          {classId ? "Students log in with email + class code to access this." : "Anyone with the join code can access this (anonymous)."}
        </p>
      </div>

      {/* Period Selection — only show when NOT publishing to a class */}
      {!classId && (<div style={{ marginBottom: "20px" }}>
        <label style={{ display: "block", marginBottom: "8px", fontWeight: 600, fontSize: "0.95rem" }}>
          Period (Optional)
        </label>
        <select
          value={settings.periodFilename}
          onChange={(e) => {
            const filename = e.target.value;
            const selectedPeriod = periods.find(p => p.filename === filename);
            setSettings({
              ...settings,
              periodFilename: filename,
              period: selectedPeriod ? selectedPeriod.period_name : '',
              selectedStudents: [],
            });
            onPeriodChange(filename);
          }}
          style={{
            width: "100%",
            padding: "10px 12px",
            borderRadius: "8px",
            border: "1px solid rgba(255,255,255,0.2)",
            background: "rgba(255,255,255,0.08)",
            color: "#e2e8f0",
            fontSize: "0.95rem",
          }}
        >
          <option value="">-- No Period (Open to All) --</option>
          {periods.map((p) => (
            <option key={p.filename} value={p.filename}>{p.name}</option>
          ))}
        </select>
      </div>)}
    </>
  );
}
