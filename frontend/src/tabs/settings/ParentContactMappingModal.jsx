import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/*
 * ParentContactMappingModal — the parent-contact spreadsheet column-mapping
 * modal, relocated verbatim from SettingsTab.jsx (CQ wave-9 split). The
 * `{parentContactMapping.show && parentContactMapping.preview && ...}` guard
 * became the early return below.
 */
export default function ParentContactMappingModal({
  parentContactMapping,
  setParentContactMapping,
  uploadingParentContacts,
  setUploadingParentContacts,
  setParentContacts,
  addToast,
}) {
  if (!(parentContactMapping.show && parentContactMapping.preview)) return null;

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
              maxWidth: "560px",
              maxHeight: "85vh",
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
                Map Parent Contact Columns
              </h3>
              <button
                onClick={() => setParentContactMapping({ show: false, preview: null, mapping: null })}
                style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer" }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "6px" }}>
              {parentContactMapping.preview.sheets.length > 1
                ? parentContactMapping.preview.sheets.length + " sheets detected (each sheet = one period)"
                : parentContactMapping.preview.sheets[0].row_count + " rows detected"}
            </p>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "20px" }}>
              Graider auto-detects emails (contains @) and phone numbers in the selected contact columns.
            </p>

            {/* Name Column */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Student Name Column</label>
              <select
                className="input"
                value={parentContactMapping.mapping?.name_col || ""}
                onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { name_col: e.target.value }) }); }); }}
              >
                <option value="">-- Select Column --</option>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  return <option key={h} value={h}>{h}</option>;
                })}
              </select>
            </div>

            {/* Name Format */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Name Format</label>
              <div style={{ display: "flex", gap: "15px", marginTop: "4px" }}>
                {[
                  { value: "last_first", label: "Last, First" },
                  { value: "first_last", label: "First Last" },
                  { value: "single", label: "Single name" },
                ].map(function(opt) {
                  return (
                    <label key={opt.value} style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input
                        type="radio"
                        name="pcNameFormat"
                        checked={parentContactMapping.mapping?.name_format === opt.value}
                        onChange={function() { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { name_format: opt.value }) }); }); }}
                      />
                      {opt.label}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Student ID Column */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Student ID Column (optional)</label>
              <select
                className="input"
                value={parentContactMapping.mapping?.id_col || ""}
                onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { id_col: e.target.value }) }); }); }}
              >
                <option value="">-- None --</option>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  return <option key={h} value={h}>{h}</option>;
                })}
              </select>
            </div>

            {/* Strip Digits */}
            {parentContactMapping.mapping?.id_col && (
              <div style={{ marginBottom: "15px" }}>
                <label className="label">Strip last N digits from Student ID (grade code)</label>
                <input
                  type="number"
                  className="input"
                  min="0"
                  max="4"
                  value={parentContactMapping.mapping?.id_strip_digits || 0}
                  onChange={function(e) {
                    var val = Math.max(0, Math.min(4, parseInt(e.target.value) || 0));
                    setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { id_strip_digits: val }) }); });
                  }}
                  style={{ width: "80px" }}
                />
                <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                  Set to 2 if IDs have a 2-digit grade suffix (e.g., 12345678906 becomes 123456789)
                </p>
              </div>
            )}

            {/* Contact Columns */}
            <div style={{ marginBottom: "15px" }}>
              <label className="label">Contact Columns (email and phone)</label>
              <div style={{ maxHeight: "150px", overflow: "auto", padding: "8px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                  var isChecked = (parentContactMapping.mapping?.contact_cols || []).indexOf(h) !== -1;
                  return (
                    <label key={h} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "4px 0", fontSize: "0.85rem", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={function() {
                          setParentContactMapping(function(prev) {
                            var cols = prev.mapping?.contact_cols || [];
                            var updated = isChecked ? cols.filter(function(c) { return c !== h; }) : cols.concat([h]);
                            return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { contact_cols: updated }) });
                          });
                        }}
                      />
                      {h}
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Period Column (only for single-sheet files) */}
            {parentContactMapping.preview.sheets.length === 1 && (
              <div style={{ marginBottom: "15px" }}>
                <label className="label">Period Column (optional)</label>
                <select
                  className="input"
                  value={parentContactMapping.mapping?.period_col || ""}
                  onChange={function(e) { setParentContactMapping(function(prev) { return Object.assign({}, prev, { mapping: Object.assign({}, prev.mapping, { period_col: e.target.value }) }); }); }}
                >
                  <option value="">-- None --</option>
                  {(parentContactMapping.preview.sheets[0]?.headers || []).map(function(h) {
                    return <option key={h} value={h}>{h}</option>;
                  })}
                </select>
              </div>
            )}

            {parentContactMapping.preview.sheets.length > 1 && (
              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "15px", fontStyle: "italic" }}>
                Period will be set from sheet names: {parentContactMapping.preview.sheets.map(function(s) { return s.name; }).join(", ")}
              </p>
            )}

            {/* Action Buttons */}
            <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
              <button
                onClick={async function() {
                  if (!parentContactMapping.mapping?.name_col) {
                    addToast("Please select a name column", "error");
                    return;
                  }
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.saveParentContactMapping(parentContactMapping.mapping);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      addToast(
                        "Imported " + result.unique_students + " students (" + result.with_email + " with email)",
                        "success"
                      );
                      var contactsData = await api.getParentContacts();
                      setParentContacts(contactsData);
                      setParentContactMapping({ show: false, preview: null, mapping: null });
                    }
                  } catch (err) {
                    addToast("Import failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                }}
                className="btn btn-primary"
                disabled={uploadingParentContacts}
              >
                <Icon name="Save" size={18} />
                {uploadingParentContacts ? "Importing..." : "Save & Import"}
              </button>
              <button
                onClick={function() { setParentContactMapping({ show: false, preview: null, mapping: null }); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
  );
}
