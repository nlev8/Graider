import React from "react";
import Icon from "./Icon";
import PrivacyFeaturesSection from "./settings-privacy/PrivacyFeaturesSection";
import DataManagementSection from "./settings-privacy/DataManagementSection";
import WritingProfilesSection from "./settings-privacy/WritingProfilesSection";
import TrustedWritersSection from "./settings-privacy/TrustedWritersSection";
import StudentHistoryModal from "./settings-privacy/StudentHistoryModal";

export default function SettingsPrivacy(props) {
  return (
              <div data-tutorial="settings-privacy">
            {/* FERPA Compliance & Data Privacy */}
            <div>
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
                  name="Shield"
                  size={20}
                  style={{ color: "#10b981" }}
                />
                Privacy & Data (FERPA)
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Graider is designed for FERPA compliance. Student names
                are sanitized before AI processing. Your data is stored
                securely on Graider's server and is never shared with
                third-party vendors or aggregated across districts.
              </p>

              {/* Privacy Features */}
              <PrivacyFeaturesSection />

              {/* Data Management Actions */}
              <DataManagementSection {...props} />

              {/* Student Writing Profiles */}
              <WritingProfilesSection {...props} />

              {/* Trusted Writers */}
              <TrustedWritersSection {...props} />

              {/* Student History Detail Modal */}
              <StudentHistoryModal {...props} />
            </div>
              </div>
  );
}
