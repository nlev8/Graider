import React from "react";

export default function TeacherProfileSection(props) {
  const { availableStates, config, setConfig } = props;
  return (
              <>
            {/* Teacher & School Info */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: "20px",
              }}
            >
              <div>
                <label className="label">Teacher Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.teacher_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_name: e.target.value,
                    }))
                  }
                  placeholder="Mr. Smith"
                />
              </div>
              <div>
                <label className="label">Teacher Email</label>
                <input
                  type="email"
                  className="input"
                  value={config.teacher_email}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_email: e.target.value,
                    }))
                  }
                  placeholder="teacher@school.edu"
                />
                <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                  Students will reply to this email
                </span>
              </div>
              <div>
                <label className="label">School Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.school_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      school_name: e.target.value,
                    }))
                  }
                  placeholder="Lincoln Middle School"
                />
              </div>
            </div>

            {/* State, Grade Level, Subject */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "20px",
                marginTop: "20px",
              }}
            >
              <div>
                <label className="label">State</label>
                <select
                  className="input"
                  value={config.state}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      state: e.target.value,
                    }))
                  }
                >
                  {availableStates.length > 0 ? availableStates.map((s) => (
                    <option key={s.code} value={s.code}>{s.name}</option>
                  )) : (
                    <option value={config.state}>{config.state}</option>
                  )}
                </select>
              </div>

              <div>
                <label className="label">Grade Level</label>
                <select
                  className="input"
                  value={config.grade_level}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      grade_level: e.target.value,
                    }))
                  }
                >
                  <option value="6">6th Grade</option>
                  <option value="7">7th Grade</option>
                  <option value="8">8th Grade</option>
                  <option value="9">9th Grade</option>
                  <option value="10">10th Grade</option>
                  <option value="11">11th Grade</option>
                  <option value="12">12th Grade</option>
                </select>
              </div>

              <div>
                <label className="label">Subject</label>
                <select
                  className="input"
                  value={config.subject}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      subject: e.target.value,
                    }))
                  }
                >
                  <option value="US History">U.S. History</option>
                  <option value="World History">World History</option>
                  <option value="Social Studies">Social Studies</option>
                  <option value="Civics">Civics</option>
                  <option value="Geography">Geography</option>
                  <option value="English/ELA">English/ELA</option>
                  <option value="Math">Math</option>
                  <option value="Science">Science</option>
                  <option value="Spanish">Spanish</option>
                  <option value="French">French</option>
                  <option value="World Languages">World Languages</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            {/* Email Signature */}
            <div>
              <label className="label">Email Signature</label>
              <textarea
                className="input"
                value={config.email_signature}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    email_signature: e.target.value,
                  }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.stopPropagation();
                  }
                }}
                placeholder={"Best regards," + String.fromCharCode(10) + "Mr. Smith" + String.fromCharCode(10) + "Room 204 | Office Hours: Mon-Fri 3-4pm"}
                rows={4}
                style={{ resize: "vertical", minHeight: "100px", fontFamily: "inherit", lineHeight: "1.5" }}
              />
              <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                Appears at the end of grade feedback emails
              </span>
            </div>
              </>
  );
}
