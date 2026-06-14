import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function PeriodStudentTable({ addToast, editStudentData, editingStudentId, expandedStudents, loadingExpandedStudents, period, setEditStudentData, setEditingStudentId, setExpandedStudents, setPeriods }) {
  return (
    <div style={{ overflowX: "auto" }}>
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
                      <td style={{ padding: "6px 8px", color: "var(--text-secondary)" }}>{student.id || "—"}</td>
                      <td style={{ padding: "6px 8px", color: student.student_email ? "var(--text-primary)" : "var(--text-muted)" }}>{student.student_email || "—"}</td>
                      <td style={{ padding: "6px 8px", color: student.parent_emails.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                        {student.parent_emails.length > 0 ? student.parent_emails.join(", ") : "—"}
                      </td>
                      <td style={{ padding: "6px 8px", color: student.parent_phones.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                        {student.parent_phones.length > 0 ? student.parent_phones.join(", ") : "—"}
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
    </div>
  );
}
