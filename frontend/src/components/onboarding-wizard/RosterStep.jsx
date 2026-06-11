import Icon from "../Icon";

// Step 6 — Import Roster. Renders the SSO auto-sync branch (Clever/ClassLink)
// or the manual CSV-upload instructions. Stateless.
export default function RosterStep(props) {
  const { isSSOUser, isCleverUser } = props;
  if (isSSOUser) {
    var ssoProvider = isCleverUser ? "Clever" : "ClassLink";
    return (
      <div style={{ padding: "10px 0" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Your Roster is Ready</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.95rem" }}>
          {"Since you logged in with " + ssoProvider + ", your class roster syncs automatically from your district's SIS."}
        </p>

        <div style={{
          background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.3)",
          borderRadius: 12, padding: 16, marginBottom: 20,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <Icon name="CheckCircle" size={20} style={{ color: "#22c55e" }} />
            <span style={{ fontWeight: 600, fontSize: "1rem" }}>{"Connected via " + ssoProvider}</span>
          </div>
          <div style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
            <p style={{ margin: "0 0 8px" }}>Your roster was synced when you logged in. Graider will automatically:</p>
            {[
              { icon: "Users", text: "Import students and class sections from " + ssoProvider },
              { icon: "RefreshCw", text: "Keep your roster up to date on each login" },
              { icon: "Shield", text: "Detect IEP and ELL flags for accommodation suggestions" },
            ].map(function(item, i) {
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <Icon name={item.icon} size={16} style={{ color: "#22c55e" }} />
                  <span>{item.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{
          background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
          borderRadius: 12, padding: 16,
        }}>
          <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>
            Want to customize?
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: 0, lineHeight: 1.5 }}>
            In Settings &gt; Classroom, you can select specific sections to sync, review accommodation suggestions, and manually add or edit students as needed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Import Your Class Roster</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.95rem" }}>
        Upload a CSV or Excel file with your students so Graider can match them to their submissions.
      </p>

      <div style={{
        background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
        borderRadius: 12, padding: 16, marginBottom: 20,
      }}>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--accent-primary)", marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>
          How to upload
        </div>
        {[
          { num: "1", icon: "Download", text: "Export your class roster as CSV from your SIS (Student Information System)" },
          { num: "2", icon: "FileSpreadsheet", text: "Make sure it includes: Student ID, First Name, Last Name, Email" },
          { num: "3", icon: "Upload", text: "Upload to Graider in Settings > Classroom > Upload CSV/Excel" },
        ].map(function(s) {
          return (
            <div key={s.num} style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: "rgba(99,102,241,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, marginTop: 1,
              }}>
                <Icon name={s.icon} size={14} style={{ color: "var(--accent-primary)" }} />
              </div>
              <span style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                {s.text}
              </span>
            </div>
          );
        })}
      </div>

      <div style={{
        background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
        borderRadius: 12, padding: 16,
      }}>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: 10 }}>
          Example CSV format
        </div>
        <div style={{
          fontFamily: "monospace", fontSize: "0.8rem",
          background: "var(--input-bg)", borderRadius: 8, padding: 12,
          color: "var(--text-primary)", lineHeight: 1.6,
          overflow: "auto",
        }}>
          Student ID, First Name, Last Name, Email<br />
          12345, Maria, Santos, maria.santos@school.edu<br />
          12346, James, Wilson, james.wilson@school.edu
        </div>
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: 10, marginBottom: 0 }}>
          Column names are detected automatically. Combined name columns like "Student Name" with "Last, First" format also work. You can skip this step and upload rosters later in Settings.
        </p>
      </div>
    </div>
  );
}
