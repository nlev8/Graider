import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function PeriodsSection(props) {
  const { addToast, focusImportProgress, focusImporting, newPeriodName, periodInputRef, setFocusImportProgress, setFocusImporting, setNewPeriodName, setPeriods, setUploadingPeriod, sortedPeriods, uploadingPeriod } = props;
  return (
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "25px",
                marginTop: "25px",
              }}
            >
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
                  name="Clock"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Class Periods
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload separate rosters for each class period, or import directly from Focus SIS
              </p>

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

              {/* Period Cards - Expandable */}
              {sortedPeriods.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {sortedPeriods.map((period) => (
                    <PeriodCard key={period.filename} period={period} {...props} />
                  ))}
                </div>
              )}
            </div>
  );
}

function PeriodCard(props) {
  const { addToast, expandedPeriod, period, setAddingStudent, setEditingStudentId, setExpandedPeriod, setExpandedStudents, setLoadingExpandedStudents, setPeriods } = props;
  return (
                    <div key={period.filename} style={{ borderRadius: "8px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
                      {/* Period Header Row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          padding: "10px 15px",
                          background: expandedPeriod === period.filename ? "rgba(245, 158, 11, 0.08)" : "var(--input-bg)",
                          cursor: "pointer",
                        }}
                        onClick={async () => {
                          if (expandedPeriod === period.filename) {
                            setExpandedPeriod(null);
                            setExpandedStudents([]);
                            setEditingStudentId(null);
                            setAddingStudent(false);
                            return;
                          }
                          setExpandedPeriod(period.filename);
                          setLoadingExpandedStudents(true);
                          setEditingStudentId(null);
                          setAddingStudent(false);
                          try {
                            const [studentsRes, contactsRes] = await Promise.all([
                              api.getPeriodStudents(period.filename),
                              api.getParentContacts(),
                            ]);
                            const students = studentsRes.students || [];
                            const contacts = contactsRes.contacts || {};
                            // Merge contact info into student list
                            // student_email comes from contacts (backend merges from grading results)
                            const merged = students.map(s => {
                              const contact = contacts[s.id] || {};
                              return {
                                ...s,
                                student_email: contact.student_email || "",
                                parent_emails: contact.parent_emails || [],
                                parent_phones: contact.parent_phones || [],
                              };
                            });
                            setExpandedStudents(merged);
                          } catch (err) {
                            addToast("Failed to load students: " + err.message, "error");
                            setExpandedStudents([]);
                          }
                          setLoadingExpandedStudents(false);
                        }}
                      >
                        <Icon
                          name={expandedPeriod === period.filename ? "ChevronDown" : "ChevronRight"}
                          size={16}
                          style={{ color: "#f59e0b", flexShrink: 0 }}
                        />
                        <Icon name="Users" size={16} style={{ color: "#f59e0b", flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "8px" }}>
                            {period.period_name}
                            {period.course_codes && period.course_codes.length > 0 && (
                              <span style={{ fontSize: "0.7rem", padding: "1px 6px", borderRadius: "4px", background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", fontWeight: 500 }}>
                                {period.course_codes.join(", ")}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                            {period.row_count} students{period.imported_from === "focus" ? " (Focus SIS)" : ""}
                          </div>
                        </div>
                        <select
                          value={period.class_level || "standard"}
                          onClick={(e) => e.stopPropagation()}
                          onChange={async (e) => {
                            e.stopPropagation();
                            const newLevel = e.target.value;
                            await api.updatePeriodLevel(period.filename, newLevel);
                            const data = await api.listPeriods();
                            setPeriods(data.periods || []);
                          }}
                          style={{
                            padding: "4px 8px",
                            borderRadius: "6px",
                            border: "1px solid var(--glass-border)",
                            background: period.class_level === "advanced" ? "rgba(139, 92, 246, 0.2)" : period.class_level === "support" ? "rgba(244, 114, 182, 0.2)" : "var(--input-bg)",
                            color: period.class_level === "advanced" ? "#a78bfa" : period.class_level === "support" ? "#f472b6" : "var(--text-primary)",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          <option value="standard">Standard</option>
                          <option value="advanced">Advanced</option>
                          <option value="support">Support</option>
                        </select>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (confirm("Delete " + period.period_name + "?")) {
                              await api.deletePeriod(period.filename);
                              const data = await api.listPeriods();
                              setPeriods(data.periods || []);
                              if (expandedPeriod === period.filename) {
                                setExpandedPeriod(null);
                                setExpandedStudents([]);
                              }
                            }
                          }}
                          style={{ padding: "4px 6px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>

                      {/* Expanded Student List */}
                      {expandedPeriod === period.filename && (
                        <PeriodStudentList {...props} />
                      )}
                    </div>
  );
}

function PeriodStudentList({ addToast, addingStudent, editStudentData, editingStudentId, expandedStudents, loadingExpandedStudents, newStudent, period, setAddingStudent, setEditStudentData, setEditingStudentId, setExpandedStudents, setNewStudent, setPeriods }) {
  return (
                        <div style={{ borderTop: "1px solid var(--glass-border)", padding: "10px 15px", background: "var(--bg-secondary)" }}>
                          {loadingExpandedStudents ? (
                            <div style={{ textAlign: "center", padding: "20px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                              <Icon name="Loader" size={18} style={{ animation: "spin 1s linear infinite", marginRight: "8px" }} />
                              Loading students...
                            </div>
                          ) : expandedStudents.length === 0 ? (
                            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", textAlign: "center", padding: "10px" }}>No students found</p>
                          ) : (
                            <div style={{ overflowX: "auto" }}>
                              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                                <thead>
                                  <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Student Name</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>ID</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Student Email</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Emails</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Phones</th>
                                    <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600, width: "80px" }}>Actions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedStudents.map((student) => (
                                    <tr key={student.id || student.full} style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                      {editingStudentId === student.id ? (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.student_name || ""} onChange={(e) => setEditStudentData({...editStudentData, student_name: e.target.value})} style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-muted)" }}>{student.id}</td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="email" value={editStudentData.student_email || ""} onChange={(e) => setEditStudentData({...editStudentData, student_email: e.target.value})} placeholder="student@school.edu" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_emails || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_emails: e.target.value})} placeholder="email1, email2" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_phones || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_phones: e.target.value})} placeholder="(386) 555-1234" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            <button
                                              onClick={async () => {
                                                try {
                                                  const emails = editStudentData.parent_emails ? editStudentData.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                                  const phones = editStudentData.parent_phones ? editStudentData.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                                  await api.updateStudent({
                                                    period_filename: period.filename,
                                                    student_id: student.id,
                                                    student_name: editStudentData.student_name,
                                                    student_email: editStudentData.student_email || "",
                                                    parent_emails: emails,
                                                    parent_phones: phones,
                                                  });
                                                  setEditingStudentId(null);
                                                  // Refresh
                                                  const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                  const contacts = contactsRes.contacts || {};
                                                  setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                  addToast("Student updated", "success");
                                                } catch (err) {
                                                  addToast("Update failed: " + err.message, "error");
                                                }
                                              }}
                                              style={{ padding: "2px 6px", background: "rgba(74, 222, 128, 0.2)", border: "1px solid rgba(74, 222, 128, 0.4)", borderRadius: "4px", color: "#4ade80", cursor: "pointer", fontSize: "0.75rem", marginRight: "4px" }}
                                            >Save</button>
                                            <button
                                              onClick={() => setEditingStudentId(null)}
                                              style={{ padding: "2px 6px", background: "none", border: "1px solid var(--glass-border)", borderRadius: "4px", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.75rem" }}
                                            >Cancel</button>
                                          </td>
                                        </>
                                      ) : (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>{student.full || (student.first + " " + student.last)}</td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-secondary)" }}>{student.id || "\u2014"}</td>
                                          <td style={{ padding: "6px 8px", color: student.student_email ? "var(--text-primary)" : "var(--text-muted)" }}>{student.student_email || "\u2014"}</td>
                                          <td style={{ padding: "6px 8px", color: student.parent_emails.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_emails.length > 0 ? student.parent_emails.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", color: student.parent_phones.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_phones.length > 0 ? student.parent_phones.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            {student.id && (
                                              <>
                                                <button
                                                  onClick={() => {
                                                    setEditingStudentId(student.id);
                                                    setEditStudentData({
                                                      student_name: student.full || (student.first + " " + student.last),
                                                      student_email: student.student_email || "",
                                                      parent_emails: student.parent_emails.join(", "),
                                                      parent_phones: student.parent_phones.join(", "),
                                                    });
                                                  }}
                                                  title="Edit"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Pencil" size={13} /></button>
                                                <button
                                                  onClick={async () => {
                                                    if (!confirm("Remove " + (student.full || student.first + " " + student.last) + " from this period?")) return;
                                                    try {
                                                      await api.removeStudent({ period_filename: period.filename, student_id: student.id });
                                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                      const contacts = contactsRes.contacts || {};
                                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                      const periodsData = await api.listPeriods();
                                                      setPeriods(periodsData.periods || []);
                                                      addToast("Student removed", "success");
                                                    } catch (err) {
                                                      addToast("Remove failed: " + err.message, "error");
                                                    }
                                                  }}
                                                  title="Remove"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Trash2" size={13} /></button>
                                              </>
                                            )}
                                          </td>
                                        </>
                                      )}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Add Student Form */}
                          {addingStudent ? (
                            <div style={{ marginTop: "10px", padding: "10px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                                <input type="text" placeholder="Student Name (Last; First)" value={newStudent.name} onChange={(e) => setNewStudent({...newStudent, name: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Student ID" value={newStudent.student_id} onChange={(e) => setNewStudent({...newStudent, student_id: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Grade (e.g., 06)" value={newStudent.grade} onChange={(e) => setNewStudent({...newStudent, grade: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="email" placeholder="Student Email" value={newStudent.student_email} onChange={(e) => setNewStudent({...newStudent, student_email: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Emails (comma-separated)" value={newStudent.parent_emails} onChange={(e) => setNewStudent({...newStudent, parent_emails: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Phones (comma-separated)" value={newStudent.parent_phones} onChange={(e) => setNewStudent({...newStudent, parent_phones: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                              </div>
                              <div style={{ display: "flex", gap: "8px" }}>
                                <button
                                  onClick={async () => {
                                    if (!newStudent.name.trim()) { addToast("Student name is required", "warning"); return; }
                                    try {
                                      const emails = newStudent.parent_emails ? newStudent.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                      const phones = newStudent.parent_phones ? newStudent.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                      const res = await api.addStudent({
                                        period_filename: period.filename,
                                        student_name: newStudent.name,
                                        student_id: newStudent.student_id,
                                        student_email: newStudent.student_email,
                                        grade: newStudent.grade,
                                        parent_emails: emails,
                                        parent_phones: phones,
                                      });
                                      if (res.error) { addToast(res.error, "error"); return; }
                                      setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' });
                                      setAddingStudent(false);
                                      // Refresh
                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                      const contacts = contactsRes.contacts || {};
                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                      const periodsData = await api.listPeriods();
                                      setPeriods(periodsData.periods || []);
                                      addToast("Student added", "success");
                                    } catch (err) {
                                      addToast("Add failed: " + err.message, "error");
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Add Student</button>
                                <button
                                  onClick={() => { setAddingStudent(false); setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' }); }}
                                  className="btn btn-secondary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setAddingStudent(true)}
                              style={{
                                marginTop: "10px",
                                padding: "6px 12px",
                                background: "none",
                                border: "1px dashed var(--glass-border)",
                                borderRadius: "6px",
                                color: "var(--text-secondary)",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                width: "100%",
                                justifyContent: "center",
                              }}
                            >
                              <Icon name="Plus" size={14} />
                              Add Student
                            </button>
                          )}
                        </div>
  );
}
